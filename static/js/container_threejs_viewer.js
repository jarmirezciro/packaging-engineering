import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const initialized = new WeakSet();
const instances = new Map();

function number(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
}

function color(value, fallback) {
    return new THREE.Color(value || fallback);
}

function getViewerSize(el) {
    const rect = el.getBoundingClientRect();
    const parent = el.parentElement;
    const parentRect = parent ? parent.getBoundingClientRect() : null;

    // Use the parent width as a hard reference so the canvas cannot make
    // the viewer wider, then use setSize(..., false) to avoid style feedback.
    const rawWidth = rect.width || el.clientWidth || (parentRect ? parentRect.width : 0) || 600;
    const parentWidth = parentRect ? parentRect.width : rawWidth;
    const width = Math.max(320, Math.min(rawWidth, parentWidth, 1200));

    const rawHeight = rect.height || el.clientHeight || 420;
    const height = Math.max(320, Math.min(rawHeight, 620));

    return { width, height };
}

function getDims(sceneData) {
    const container = sceneData.container || {};
    return {
        length: Math.max(number(container.length, 1), 1),
        width: Math.max(number(container.width, 1), 1),
        height: Math.max(number(container.height, 1), 1),
    };
}

function mapPosition(x, y, z, dims) {
    // Python/Matplotlib convention: X=length, Y=width, Z=height.
    // Three.js convention here: X=length, Y=height, Z=width.
    return new THREE.Vector3(
        number(x) - dims.length / 2,
        number(z),
        number(y) - dims.width / 2,
    );
}

function centerPosition(cuboid, dims) {
    const x = number(cuboid.x) + number(cuboid.dx) / 2;
    const y = number(cuboid.y) + number(cuboid.dy) / 2;
    const z = number(cuboid.z) + number(cuboid.dz) / 2;
    return mapPosition(x, y, z, dims);
}

function addEdges(mesh, target, edgeColor = 0x111827, opacity = 0.65) {
    const edges = new THREE.EdgesGeometry(mesh.geometry);
    const material = new THREE.LineBasicMaterial({
        color: edgeColor,
        transparent: opacity < 1,
        opacity: opacity,
    });
    const lines = new THREE.LineSegments(edges, material);
    lines.position.copy(mesh.position);
    lines.rotation.copy(mesh.rotation);
    target.add(lines);
    return lines;
}

function addCuboid(target, cuboid, dims, options = {}) {
    const dx = Math.max(number(cuboid.dx), 0.001);
    const dy = Math.max(number(cuboid.dy), 0.001);
    const dz = Math.max(number(cuboid.dz), 0.001);

    const geometry = new THREE.BoxGeometry(dx, dz, dy);
    const opacity = options.opacity ?? number(cuboid.opacity, 1);
    const transparent = opacity < 0.999;
    const material = options.material || new THREE.MeshStandardMaterial({
        color: color(cuboid.color, options.color || "#f59e0b"),
        roughness: 0.72,
        metalness: 0.02,
        transparent: transparent,
        opacity: opacity,
        depthWrite: !transparent,
    });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.copy(centerPosition(cuboid, dims));
    target.add(mesh);

    if (options.edges !== false) {
        addEdges(mesh, target, options.edgeColor || 0x1e3a8a, options.edgeOpacity ?? 0.55);
    }

    return mesh;
}

function addContainerBody(target, dims) {
    const maxDim = Math.max(dims.length, dims.width, dims.height);
    const t = Math.max(maxDim * 0.006, 1);
    const panelMaterial = new THREE.MeshStandardMaterial({
        color: 0xd8c3a5,
        transparent: true,
        opacity: 0.22,
        roughness: 0.8,
        side: THREE.DoubleSide,
        depthWrite: false,
    });

    const parts = [
        // bottom
        { x: 0, y: 0, z: -t, dx: dims.length, dy: dims.width, dz: t },
        // left and right length walls
        { x: -t, y: 0, z: 0, dx: t, dy: dims.width, dz: dims.height },
        { x: dims.length, y: 0, z: 0, dx: t, dy: dims.width, dz: dims.height },
        // front/back width walls
        { x: 0, y: -t, z: 0, dx: dims.length, dy: t, dz: dims.height },
        { x: 0, y: dims.width, z: 0, dx: dims.length, dy: t, dz: dims.height },
    ];

    parts.forEach((part) => {
        const mesh = addCuboid(target, part, dims, {
            material: panelMaterial,
            edgeColor: 0x111827,
            edgeOpacity: 0.45,
        });
        mesh.renderOrder = 1;
    });
}

function addQuad(target, points, dims, material, edgeColor = 0x111827) {
    const vertices = [];
    points.forEach((p) => {
        const mapped = mapPosition(p[0], p[1], p[2], dims);
        vertices.push(mapped.x, mapped.y, mapped.z);
    });

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
    geometry.setIndex([0, 1, 2, 0, 2, 3]);
    geometry.computeVertexNormals();

    const mesh = new THREE.Mesh(geometry, material);
    target.add(mesh);

    const edges = new THREE.EdgesGeometry(geometry);
    const lines = new THREE.LineSegments(
        edges,
        new THREE.LineBasicMaterial({ color: edgeColor, transparent: true, opacity: 0.45 }),
    );
    target.add(lines);
}

function addRscFlaps(target, dims, sceneData) {
    const rsc = sceneData.rsc || {};
    if (rsc.enabled === false) return;

    const lc = dims.length;
    const ac = dims.width;
    const hc = dims.height;
    const openingAngleDeg = number(rsc.openingAngleDeg, 130);
    const tiltDeg = Math.max(5, Math.min(openingAngleDeg - 80, 75));
    const theta = THREE.MathUtils.degToRad(tiltDeg);

    const majorLen = Math.max(ac * 0.5, 1);
    const minorLen = Math.max(Math.min(lc * 0.22, ac * 0.48), 1);
    const majorRun = majorLen * Math.cos(theta);
    const majorRise = majorLen * Math.sin(theta);
    const minorRun = minorLen * Math.cos(theta);
    const minorRise = minorLen * Math.sin(theta);

    const material = new THREE.MeshStandardMaterial({
        color: 0xc9a66b,
        transparent: true,
        opacity: 0.34,
        roughness: 0.85,
        side: THREE.DoubleSide,
        depthWrite: false,
    });

    const flaps = [
        [[0, 0, hc], [lc, 0, hc], [lc, -majorRun, hc + majorRise], [0, -majorRun, hc + majorRise]],
        [[0, ac, hc], [lc, ac, hc], [lc, ac + majorRun, hc + majorRise], [0, ac + majorRun, hc + majorRise]],
        [[0, 0, hc], [0, ac, hc], [-minorRun, ac, hc + minorRise], [-minorRun, 0, hc + minorRise]],
        [[lc, 0, hc], [lc, ac, hc], [lc + minorRun, ac, hc + minorRise], [lc + minorRun, 0, hc + minorRise]],
    ];

    flaps.forEach((quad) => addQuad(target, quad, dims, material));
}

function setCameraView(camera, controls, dims, viewName) {
    const maxDim = Math.max(dims.length, dims.width, dims.height);
    const target = new THREE.Vector3(0, dims.height * 0.45, 0);
    const distance = maxDim * 2.0;

    const views = {
        reset: new THREE.Vector3(distance * 0.85, distance * 0.55, distance * 0.85),
        top: new THREE.Vector3(0.001, distance * 1.1, 0.001),
        front: new THREE.Vector3(0, distance * 0.35, distance),
        side: new THREE.Vector3(distance, distance * 0.35, 0),
    };

    camera.position.copy(views[viewName] || views.reset);
    camera.up.set(0, 1, 0);
    camera.lookAt(target);
    controls.target.copy(target);
    controls.update();
}

function setupCamera(width, height, dims) {
    const aspect = Math.max(width, 1) / Math.max(height, 1);
    const maxDim = Math.max(dims.length, dims.width, dims.height);
    const viewSize = maxDim * 1.75;

    const camera = new THREE.OrthographicCamera(
        -viewSize * aspect / 2,
        viewSize * aspect / 2,
        viewSize / 2,
        -viewSize / 2,
        -maxDim * 10,
        maxDim * 10,
    );
    return { camera, viewSize };
}

function initViewer(el) {
    if (initialized.has(el)) return;
    initialized.add(el);

    const scriptId = el.dataset.sceneScript;
    const script = scriptId ? document.getElementById(scriptId) : null;
    if (!script) {
        el.innerHTML = '<div class="container-threejs-fallback">No 3D scene data available.</div>';
        return;
    }

    let sceneData;
    try {
        sceneData = JSON.parse(script.textContent || "{}");
    } catch (error) {
        el.innerHTML = '<div class="container-threejs-fallback">Could not read 3D scene data.</div>';
        return;
    }

    const productCount = Array.isArray(sceneData.products) ? sceneData.products.length : 0;
    const subboxCount = Array.isArray(sceneData.subboxes) ? sceneData.subboxes.length : 0;
    if (!sceneData.container || (productCount === 0 && subboxCount === 0)) {
        el.innerHTML = '<div class="container-threejs-fallback">3D scene loaded, but there are no products/subboxes to render.</div>';
        return;
    }

    const dims = getDims(sceneData);
    const initialSize = getViewerSize(el);
    const width = initialSize.width;
    const height = initialSize.height;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf8fafc);

    let renderer;
    try {
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true });
    } catch (error) {
        el.innerHTML = '<div class="container-threejs-fallback">WebGL could not start in this browser. Check graphics/WebGL settings.</div>';
        console.error('KolliContainerThreeJs WebGL error:', error);
        return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(width, height, false);
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    renderer.domElement.style.maxWidth = "100%";
    renderer.domElement.style.display = "block";
    el.replaceChildren(renderer.domElement);

    const { camera, viewSize } = setupCamera(width, height, dims);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.screenSpacePanning = true;

    scene.add(new THREE.HemisphereLight(0xffffff, 0xe2e8f0, 1.7));
    const dir = new THREE.DirectionalLight(0xffffff, 1.25);
    dir.position.set(1, 2, 1.5);
    scene.add(dir);

    const root = new THREE.Group();
    scene.add(root);

    const containerGroup = new THREE.Group();
    const subboxGroup = new THREE.Group();
    const productGroup = new THREE.Group();
    root.add(containerGroup, subboxGroup, productGroup);

    addContainerBody(containerGroup, dims);
    addRscFlaps(containerGroup, dims, sceneData);

    (sceneData.subboxes || []).forEach((box) => {
        addCuboid(subboxGroup, box, dims, {
            color: box.color || "#2563eb",
            opacity: number(box.opacity, 0.1),
            edgeColor: 0x111827,
            edgeOpacity: 0.22,
        });
    });

    const productMaterial = new THREE.MeshStandardMaterial({
        color: 0xf59e0b,
        roughness: 0.64,
        metalness: 0.02,
    });
    (sceneData.products || []).forEach((item) => {
        addCuboid(productGroup, item, dims, {
            material: productMaterial,
            edgeColor: 0x1e40af,
            edgeOpacity: 0.75,
        });
    });

    let currentViewName = "reset";
    setCameraView(camera, controls, dims, currentViewName);

    const panel = el.closest(".container-threejs-panel") || document;
    panel.querySelectorAll("[data-container-threejs-view]").forEach((button) => {
        button.addEventListener("click", () => {
            currentViewName = button.dataset.containerThreejsView || "reset";
            setCameraView(camera, controls, dims, currentViewName);
        });
    });

    const toggle = panel.querySelector('[data-container-threejs-toggle="subboxes"]');
    if (toggle) {
        toggle.addEventListener("change", () => {
            subboxGroup.visible = Boolean(toggle.checked);
        });
        subboxGroup.visible = Boolean(toggle.checked);
    }

    instances.set(el, {
        el,
        scene,
        camera,
        controls,
        renderer,
        dims,
        productCount,
        subboxCount,
        getCurrentViewLabel: () => {
            const labels = {
                reset: "Current interactive 3D view - reset/corner view",
                top: "Current interactive 3D view - top view",
                front: "Current interactive 3D view - front view",
                side: "Current interactive 3D view - side view",
            };
            return labels[currentViewName] || "Current interactive 3D view";
        },
    });

    let lastWidth = width;
    let lastHeight = height;
    let resizePending = false;

    function applyResize() {
        resizePending = false;
        const nextSize = getViewerSize(el);
        const nextWidth = nextSize.width;
        const nextHeight = nextSize.height;

        if (Math.abs(nextWidth - lastWidth) < 1 && Math.abs(nextHeight - lastHeight) < 1) {
            return;
        }

        lastWidth = nextWidth;
        lastHeight = nextHeight;

        const aspect = nextWidth / nextHeight;
        camera.left = -viewSize * aspect / 2;
        camera.right = viewSize * aspect / 2;
        camera.top = viewSize / 2;
        camera.bottom = -viewSize / 2;
        camera.updateProjectionMatrix();
        renderer.setSize(nextWidth, nextHeight, false);
    }

    function requestResize() {
        if (resizePending) return;
        resizePending = true;
        window.requestAnimationFrame(applyResize);
    }

    const resizeTarget = el.closest(".container-threejs-panel") || el.parentElement || el;
    const resizeObserver = "ResizeObserver" in window ? new ResizeObserver(requestResize) : null;
    if (resizeObserver) resizeObserver.observe(resizeTarget);
    window.addEventListener("resize", requestResize);

    function animate() {
        controls.update();
        renderer.render(scene, camera);
        requestAnimationFrame(animate);
    }
    animate();
}

function initAll() {
    document.querySelectorAll("[data-container-threejs-viewer]").forEach(initViewer);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
} else {
    initAll();
}

function captureViewer(viewerId, mimeType = "image/jpeg", quality = 0.88) {
    const el = typeof viewerId === "string" ? document.getElementById(viewerId) : viewerId;
    if (!el) return "";

    const instance = instances.get(el);
    if (!instance) return "";

    try {
        instance.controls.update();
        instance.renderer.render(instance.scene, instance.camera);

        const sourceCanvas = instance.renderer.domElement;
        const sourceWidth = sourceCanvas.width || 0;
        const sourceHeight = sourceCanvas.height || 0;
        if (!sourceWidth || !sourceHeight) return "";

        // Keep the POST payload comfortably below Django's default upload limits
        // while preserving enough quality for the PDF report.
        const maxExportWidth = 1400;
        const scale = Math.min(1, maxExportWidth / sourceWidth);
        const exportWidth = Math.max(1, Math.round(sourceWidth * scale));
        const exportHeight = Math.max(1, Math.round(sourceHeight * scale));

        const exportCanvas = document.createElement("canvas");
        exportCanvas.width = exportWidth;
        exportCanvas.height = exportHeight;
        const ctx = exportCanvas.getContext("2d");
        if (!ctx) return "";

        ctx.fillStyle = "#f8fafc";
        ctx.fillRect(0, 0, exportWidth, exportHeight);
        ctx.drawImage(sourceCanvas, 0, 0, exportWidth, exportHeight);

        return exportCanvas.toDataURL(mimeType, quality);
    } catch (error) {
        console.error("KolliContainerThreeJs capture error:", error);
        return "";
    }
}

function ensureHiddenField(form, name) {
    let field = form.querySelector('[name="' + name + '"]');
    if (!field) {
        field = document.createElement("input");
        field.type = "hidden";
        field.name = name;
        form.appendChild(field);
    }
    return field;
}

function preparePdfExport(target) {
    if (!target) return true;

    const button = target.matches && target.matches("[data-container-threejs-pdf-button]")
        ? target
        : null;
    const form = button ? button.closest("form") : target;
    if (!form) return true;

    const viewerId = button
        ? button.dataset.containerThreejsPdfViewer
        : form.dataset.containerThreejsPdfViewer;

    if (!viewerId) {
        window.alert("The 3D viewer was not found for this PDF export. Please refresh the page and run the analysis again.");
        return false;
    }

    const snapshot = captureViewer(viewerId, "image/jpeg", 0.9);
    if (!snapshot) {
        window.alert("The 3D view is not ready for PDF export yet. Please wait until the interactive preview is visible, then try again.");
        return false;
    }

    const snapshotField = ensureHiddenField(form, "threejs_snapshot");
    const labelField = ensureHiddenField(form, "threejs_view_label");
    snapshotField.value = snapshot;

    const el = document.getElementById(viewerId);
    const instance = el ? instances.get(el) : null;
    labelField.value = instance && instance.getCurrentViewLabel
        ? instance.getCurrentViewLabel()
        : "Current interactive 3D view";

    return true;
}

function bindPdfExports() {
    document.querySelectorAll("[data-container-threejs-pdf-button]").forEach((button) => {
        if (button.dataset.threejsPdfBound === "1") return;
        button.dataset.threejsPdfBound = "1";
        button.addEventListener("click", async (event) => {
            if (button.dataset.threejsPdfSubmitting === "1") {
                button.dataset.threejsPdfSubmitting = "0";
                return;
            }

            event.preventDefault();
            await new Promise((resolve) => window.requestAnimationFrame(resolve));
            const ok = preparePdfExport(button);
            if (!ok) return;

            const form = button.closest("form");
            if (!form) return;

            button.dataset.threejsPdfSubmitting = "1";
            if (form.requestSubmit) {
                form.requestSubmit(button);
            } else {
                // Fallback for older browsers. Keep formaction/formmethod manually.
                if (button.formAction) form.action = button.formAction;
                if (button.formMethod) form.method = button.formMethod;
                form.submit();
            }
        });
    });

    // Backward compatibility for any older standalone PDF forms still present.
    document.querySelectorAll("[data-container-threejs-pdf-form]").forEach((form) => {
        if (form.dataset.threejsPdfBound === "1") return;
        form.dataset.threejsPdfBound = "1";
        form.addEventListener("submit", () => preparePdfExport(form));
    });
}

// Also expose manual hooks in case a future HTMX/AJAX flow injects results.
window.KolliContainerThreeJs = window.KolliContainerThreeJs || {};
window.KolliContainerThreeJs.initAll = function () {
    initAll();
    bindPdfExports();
};
window.KolliContainerThreeJs.captureViewer = captureViewer;
window.KolliContainerThreeJs.preparePdfExport = preparePdfExport;

bindPdfExports();
