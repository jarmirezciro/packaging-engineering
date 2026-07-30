import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const initialized = new WeakSet();
const instances = new Map();

function number(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
}

function getViewerSize(el) {
    const rect = el.getBoundingClientRect();
    const parentRect = el.parentElement ? el.parentElement.getBoundingClientRect() : null;
    const fallbackWidth = parentRect && parentRect.width ? parentRect.width : 600;
    const width = Math.max(
        1,
        Math.min(rect.width || el.clientWidth || fallbackWidth, fallbackWidth, 1200),
    );
    const height = Math.max(300, Math.min(rect.height || el.clientHeight || 420, 620));
    return { width, height };
}

function getSceneDimensions(sceneData) {
    const pallet = sceneData.pallet || {};
    const allowed = sceneData.allowed_footprint || {};
    const metadata = sceneData.metadata || {};
    const length = Math.max(number(allowed.length, pallet.length), number(pallet.length, 1), 1);
    const width = Math.max(number(allowed.width, pallet.width), number(pallet.width, 1), 1);
    const height = Math.max(
        number(metadata.total_render_height_mm),
        number(pallet.height) + number(metadata.stack_height_mm),
        1,
    );
    return { length, width, height };
}

function mapPosition(x, y, z, dims) {
    // Python: X=length, Y=width, Z=height.
    // Three.js: X=length, Y=height, Z=width.
    return new THREE.Vector3(
        number(x) - dims.length / 2,
        number(z),
        number(y) - dims.width / 2,
    );
}

function centerPosition(cuboid, dims) {
    return mapPosition(
        number(cuboid.x) + number(cuboid.dx) / 2,
        number(cuboid.y) + number(cuboid.dy) / 2,
        number(cuboid.z) + number(cuboid.dz) / 2,
        dims,
    );
}

function geometrySize(geometry) {
    const params = geometry && geometry.parameters ? geometry.parameters : {};
    if (Number.isFinite(params.width) && Number.isFinite(params.height) && Number.isFinite(params.depth)) {
        return { width: params.width, height: params.height, depth: params.depth };
    }

    geometry.computeBoundingBox();
    const box = geometry.boundingBox;
    return {
        width: Math.max(box.max.x - box.min.x, 0.001),
        height: Math.max(box.max.y - box.min.y, 0.001),
        depth: Math.max(box.max.z - box.min.z, 0.001),
    };
}

function externalCuboidEdgeGeometry(width, height, depth) {
    const x = width / 2;
    const y = height / 2;
    const z = depth / 2;
    const corners = [
        [-x, -y, -z], [x, -y, -z], [x, -y, z], [-x, -y, z],
        [-x, y, -z], [x, y, -z], [x, y, z], [-x, y, z],
    ];
    const edgePairs = [
        [0, 1], [1, 2], [2, 3], [3, 0],
        [4, 5], [5, 6], [6, 7], [7, 4],
        [0, 4], [1, 5], [2, 6], [3, 7],
    ];
    const vertices = [];
    edgePairs.forEach(([a, b]) => {
        vertices.push(...corners[a], ...corners[b]);
    });
    const edgeGeometry = new THREE.BufferGeometry();
    edgeGeometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
    return edgeGeometry;
}

function addEdges(mesh, target, edgeColor = 0x0f172a, opacity = 0.62) {
    // Draw only the 12 real cuboid edges. This avoids internal diagonal
    // triangle lines on carton/pallet faces in Three.js renders.
    const size = geometrySize(mesh.geometry);
    const lines = new THREE.LineSegments(
        externalCuboidEdgeGeometry(size.width, size.height, size.depth),
        new THREE.LineBasicMaterial({
            color: edgeColor,
            transparent: opacity < 1,
            opacity: opacity,
        }),
    );
    lines.position.copy(mesh.position);
    target.add(lines);
}

function addCuboid(target, cuboid, dims, options = {}) {
    const dx = Math.max(number(cuboid.dx), 0.001);
    const dy = Math.max(number(cuboid.dy), 0.001);
    const dz = Math.max(number(cuboid.dz), 0.001);
    const geometry = new THREE.BoxGeometry(dx, dz, dy);
    const material = options.material || new THREE.MeshStandardMaterial({
        color: options.color || "#2563eb",
        roughness: options.roughness ?? 0.7,
        metalness: options.metalness ?? 0.01,
        transparent: (options.opacity ?? 1) < 0.999,
        opacity: options.opacity ?? 1,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.copy(centerPosition(cuboid, dims));
    target.add(mesh);
    if (options.edges !== false) {
        addEdges(mesh, target, options.edgeColor, options.edgeOpacity);
    }
    return mesh;
}

function addPallet(target, sceneData, dims) {
    const pallet = sceneData.pallet || {};
    const length = Math.max(number(pallet.length), 1);
    const width = Math.max(number(pallet.width), 1);
    const height = Math.max(number(pallet.height), 1);
    const deckThickness = Math.min(
        Math.max(number(pallet.deck_thickness, height * 0.17), 1),
        height,
    );
    const runnerHeight = Math.max(height - deckThickness, 1);
    const wood = new THREE.MeshStandardMaterial({
        color: 0xc69a62,
        roughness: 0.88,
        metalness: 0,
    });
    const runnerWood = new THREE.MeshStandardMaterial({
        color: 0xa97842,
        roughness: 0.92,
        metalness: 0,
    });

    addCuboid(target, {
        x: 0,
        y: 0,
        z: runnerHeight,
        dx: length,
        dy: width,
        dz: deckThickness,
    }, dims, { material: wood, edgeColor: 0x6b4423, edgeOpacity: 0.55 });

    const runnerWidth = Math.max(Math.min(width / 6, 100), 24);
    [0, (width - runnerWidth) / 2, width - runnerWidth].forEach((y) => {
        addCuboid(target, {
            x: 0,
            y: y,
            z: 0,
            dx: length,
            dy: runnerWidth,
            dz: runnerHeight,
        }, dims, { material: runnerWood, edgeColor: 0x5b3b22, edgeOpacity: 0.5 });
    });
}

function addAllowedFootprint(target, sceneData, dims) {
    const pallet = sceneData.pallet || {};
    const allowed = sceneData.allowed_footprint || {};
    const lengthOverhang = number(allowed.length_overhang);
    const widthOverhang = number(allowed.width_overhang);
    if (lengthOverhang <= 0 && widthOverhang <= 0) return;

    const length = Math.max(number(allowed.length), number(pallet.length), 1);
    const width = Math.max(number(allowed.width), number(pallet.width), 1);
    const geometry = new THREE.BoxGeometry(length, 1, width);
    const outline = new THREE.LineSegments(
        new THREE.EdgesGeometry(geometry),
        new THREE.LineBasicMaterial({ color: 0xf97316, transparent: true, opacity: 0.8 }),
    );
    outline.position.copy(mapPosition(
        length / 2,
        width / 2,
        number(pallet.height) + 2,
        dims,
    ));
    target.add(outline);
}

function caseColor(placement) {
    const layer = Math.max(number(placement.layer, 1), 1);
    const alternate = placement.layer_kind === "interlock";
    const palettes = alternate
        ? ["#0f766e", "#0d9488", "#14b8a6"]
        : ["#1d4ed8", "#2563eb", "#3b82f6"];
    return palettes[(layer - 1) % palettes.length];
}

function addCases(target, sceneData, dims) {
    (sceneData.placements || []).forEach((placement) => {
        addCuboid(target, placement, dims, {
            color: caseColor(placement),
            edgeColor: 0x0f172a,
            edgeOpacity: 0.72,
            roughness: 0.66,
        });
    });
}

function computeViewSize(dims, aspect) {
    const diagonal = Math.hypot(dims.length, dims.width);
    const desiredWidth = diagonal * 1.28;
    const desiredHeight = dims.height * 1.42;
    return Math.max(desiredHeight, desiredWidth / Math.max(aspect, 0.2), 1);
}

function updateFrustum(camera, dims, width, height) {
    const aspect = Math.max(width, 1) / Math.max(height, 1);
    const viewSize = computeViewSize(dims, aspect);
    camera.left = -viewSize * aspect / 2;
    camera.right = viewSize * aspect / 2;
    camera.top = viewSize / 2;
    camera.bottom = -viewSize / 2;
    camera.updateProjectionMatrix();
}

function setCameraView(camera, controls, dims, viewName) {
    const maxDim = Math.max(dims.length, dims.width, dims.height);
    const distance = maxDim * 2.5;
    const target = new THREE.Vector3(0, dims.height * 0.46, 0);
    const views = {
        reset: new THREE.Vector3(distance * 0.82, distance * 0.62, distance * 0.88),
        top: new THREE.Vector3(0.001, distance * 1.2, 0.001),
        front: new THREE.Vector3(0, dims.height * 0.48, distance),
        side: new THREE.Vector3(distance, dims.height * 0.48, 0),
    };

    camera.zoom = 1;
    camera.position.copy(views[viewName] || views.reset);
    camera.up.set(0, 1, 0);
    camera.lookAt(target);
    camera.updateProjectionMatrix();
    controls.target.copy(target);
    controls.update();
}

function initViewer(el) {
    if (initialized.has(el)) return;
    initialized.add(el);

    const script = document.getElementById(el.dataset.sceneScript || "");
    if (!script) {
        el.innerHTML = '<div class="palletization-threejs-fallback">No pallet scene data is available.</div>';
        return;
    }

    let sceneData;
    try {
        sceneData = JSON.parse(script.textContent || "{}");
    } catch (error) {
        el.innerHTML = '<div class="palletization-threejs-fallback">The pallet scene data could not be read.</div>';
        return;
    }

    if (!sceneData.pallet || !Array.isArray(sceneData.placements) || sceneData.placements.length === 0) {
        el.innerHTML = '<div class="palletization-threejs-fallback">The pallet scene contains no carton placements.</div>';
        return;
    }

    const dims = getSceneDimensions(sceneData);
    const initialSize = getViewerSize(el);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf8fafc);

    let renderer;
    try {
        renderer = new THREE.WebGLRenderer({
            antialias: true,
            alpha: false,
            preserveDrawingBuffer: true,
        });
    } catch (error) {
        el.innerHTML = '<div class="palletization-threejs-fallback">WebGL could not start in this browser.</div>';
        console.error("KolliPalletizationThreeJs WebGL error:", error);
        return;
    }

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(initialSize.width, initialSize.height, false);
    renderer.domElement.style.width = "100%";
    renderer.domElement.style.height = "100%";
    renderer.domElement.style.maxWidth = "100%";
    renderer.domElement.style.display = "block";
    el.replaceChildren(renderer.domElement);

    const maxDim = Math.max(dims.length, dims.width, dims.height);
    const camera = new THREE.OrthographicCamera(
        -1,
        1,
        1,
        -1,
        -maxDim * 12,
        maxDim * 12,
    );
    updateFrustum(camera, dims, initialSize.width, initialSize.height);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = true;
    controls.screenSpacePanning = true;

    scene.add(new THREE.HemisphereLight(0xffffff, 0xdbeafe, 1.7));
    const keyLight = new THREE.DirectionalLight(0xffffff, 1.35);
    keyLight.position.set(1.5, 2.4, 1.8);
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0xffffff, 0.55);
    fillLight.position.set(-1.5, 1.1, -1.2);
    scene.add(fillLight);

    const root = new THREE.Group();
    scene.add(root);
    addPallet(root, sceneData, dims);
    addAllowedFootprint(root, sceneData, dims);
    addCases(root, sceneData, dims);

    let currentViewName = "reset";
    setCameraView(camera, controls, dims, currentViewName);

    const panel = el.closest(".palletization-threejs-panel") || document;
    panel.querySelectorAll("[data-palletization-threejs-view]").forEach((button) => {
        button.addEventListener("click", () => {
            currentViewName = button.dataset.palletizationThreejsView || "reset";
            setCameraView(camera, controls, dims, currentViewName);
        });
    });

    instances.set(el, {
        scene,
        camera,
        controls,
        renderer,
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

    let lastWidth = initialSize.width;
    let lastHeight = initialSize.height;
    let resizePending = false;

    function applyResize() {
        resizePending = false;
        const next = getViewerSize(el);
        if (Math.abs(next.width - lastWidth) < 1 && Math.abs(next.height - lastHeight) < 1) return;
        lastWidth = next.width;
        lastHeight = next.height;
        updateFrustum(camera, dims, next.width, next.height);
        renderer.setSize(next.width, next.height, false);
    }

    function requestResize() {
        if (resizePending) return;
        resizePending = true;
        window.requestAnimationFrame(applyResize);
    }

    const resizeTarget = el.closest(".palletization-threejs-panel") || el.parentElement || el;
    const resizeObserver = "ResizeObserver" in window ? new ResizeObserver(requestResize) : null;
    if (resizeObserver) resizeObserver.observe(resizeTarget);
    window.addEventListener("resize", requestResize);

    function animate() {
        controls.update();
        renderer.render(scene, camera);
        window.requestAnimationFrame(animate);
    }
    animate();
}

function initAll() {
    document.querySelectorAll("[data-palletization-threejs-viewer]").forEach(initViewer);
}

function captureViewer(viewerId, mimeType = "image/jpeg", quality = 0.88) {
    const el = typeof viewerId === "string" ? document.getElementById(viewerId) : viewerId;
    const instance = el ? instances.get(el) : null;
    if (!instance) return "";

    try {
        instance.controls.update();
        instance.renderer.render(instance.scene, instance.camera);
        const source = instance.renderer.domElement;
        if (!source.width || !source.height) return "";

        const maxWidth = 1400;
        const scale = Math.min(1, maxWidth / source.width);
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round(source.width * scale));
        canvas.height = Math.max(1, Math.round(source.height * scale));
        const context = canvas.getContext("2d");
        if (!context) return "";
        context.fillStyle = "#f8fafc";
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(source, 0, 0, canvas.width, canvas.height);
        return canvas.toDataURL(mimeType, quality);
    } catch (error) {
        console.error("KolliPalletizationThreeJs capture error:", error);
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

function preparePdfExport(button) {
    const form = button ? button.closest("form") : null;
    const viewerId = button ? button.dataset.palletizationThreejsPdfViewer : "";
    if (!form || !viewerId) {
        window.alert("The pallet 3D viewer was not found. Refresh the page and run the analysis again.");
        return false;
    }

    const snapshot = captureViewer(viewerId, "image/jpeg", 0.9);
    if (!snapshot) {
        window.alert("The pallet 3D view is not ready. Wait until the interactive preview is visible, then try again.");
        return false;
    }

    ensureHiddenField(form, "threejs_snapshot").value = snapshot;
    const viewer = document.getElementById(viewerId);
    const instance = viewer ? instances.get(viewer) : null;
    ensureHiddenField(form, "threejs_view_label").value = (
        instance && instance.getCurrentViewLabel
            ? instance.getCurrentViewLabel()
            : "Current interactive 3D view"
    );
    return true;
}

function bindPdfExports() {
    document.querySelectorAll("[data-palletization-threejs-pdf-button]").forEach((button) => {
        if (button.dataset.threejsPdfBound === "1") return;
        button.dataset.threejsPdfBound = "1";
        button.addEventListener("click", async (event) => {
            if (button.dataset.threejsPdfSubmitting === "1") {
                button.dataset.threejsPdfSubmitting = "0";
                return;
            }
            event.preventDefault();
            await new Promise((resolve) => window.requestAnimationFrame(resolve));
            if (!preparePdfExport(button)) return;

            const form = button.closest("form");
            if (!form) return;
            button.dataset.threejsPdfSubmitting = "1";
            if (form.requestSubmit) {
                form.requestSubmit(button);
            } else {
                if (button.formAction) form.action = button.formAction;
                if (button.formMethod) form.method = button.formMethod;
                form.submit();
            }
        });
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
        initAll();
        bindPdfExports();
    });
} else {
    initAll();
    bindPdfExports();
}

window.KolliPalletizationThreeJs = window.KolliPalletizationThreeJs || {};
window.KolliPalletizationThreeJs.initAll = function () {
    initAll();
    bindPdfExports();
};
window.KolliPalletizationThreeJs.captureViewer = captureViewer;
window.KolliPalletizationThreeJs.preparePdfExport = preparePdfExport;
