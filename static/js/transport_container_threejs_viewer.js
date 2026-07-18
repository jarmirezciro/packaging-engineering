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
    const fallbackWidth = parentRect && parentRect.width ? parentRect.width : 720;
    const width = Math.max(
        1,
        Math.min(rect.width || el.clientWidth || fallbackWidth, fallbackWidth, 1400),
    );
    const height = Math.max(320, Math.min(rect.height || el.clientHeight || 420, 640));
    return { width, height };
}

function getDimensions(sceneData) {
    const unit = sceneData.transport_unit || {};
    return {
        length: Math.max(number(unit.length), 1),
        width: Math.max(number(unit.width), 1),
        height: Math.max(number(unit.height), 1),
    };
}

function mapPosition(x, y, z, dims) {
    // Python/Django: X=length, Y=width, Z=height.
    // Three.js:      X=length, Y=height, Z=width.
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

function addEdges(mesh, target, color = 0x0f172a, opacity = 0.7) {
    const edges = new THREE.LineSegments(
        new THREE.EdgesGeometry(mesh.geometry),
        new THREE.LineBasicMaterial({ color, transparent: opacity < 1, opacity }),
    );
    edges.position.copy(mesh.position);
    edges.rotation.copy(mesh.rotation);
    target.add(edges);
}

function addCuboid(target, cuboid, dims, options = {}) {
    const dx = Math.max(number(cuboid.dx), 0.001);
    const dy = Math.max(number(cuboid.dy), 0.001);
    const dz = Math.max(number(cuboid.dz), 0.001);
    const geometry = new THREE.BoxGeometry(dx, dz, dy);
    const opacity = options.opacity ?? number(cuboid.opacity, 1);
    const material = options.material || new THREE.MeshStandardMaterial({
        color: options.color || cuboid.color || "#f59e0b",
        roughness: options.roughness ?? 0.68,
        metalness: options.metalness ?? 0.01,
        transparent: opacity < 0.999,
        opacity,
        depthWrite: opacity >= 0.5,
        side: options.side || THREE.FrontSide,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.copy(centerPosition(cuboid, dims));
    target.add(mesh);
    if (options.edges !== false) {
        addEdges(mesh, target, options.edgeColor, options.edgeOpacity);
    }
    return mesh;
}

function addPanel(target, pythonPoints, dims) {
    const points = pythonPoints.map((point) => mapPosition(point[0], point[1], point[2], dims));
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    geometry.setIndex([0, 1, 2, 0, 2, 3]);
    geometry.computeVertexNormals();
    const mesh = new THREE.Mesh(
        geometry,
        new THREE.MeshStandardMaterial({
            color: 0xcbd5e1,
            transparent: true,
            opacity: 0.28,
            depthWrite: false,
            roughness: 0.8,
            side: THREE.DoubleSide,
        }),
    );
    target.add(mesh);
    const outline = new THREE.LineSegments(
        new THREE.EdgesGeometry(geometry),
        new THREE.LineBasicMaterial({ color: 0x475569, transparent: true, opacity: 0.9 }),
    );
    target.add(outline);
}

function addTransportUnit(target, dims) {
    const wallThickness = Math.max(Math.min(dims.height, dims.width) * 0.008, 4);
    const shellMaterial = new THREE.MeshStandardMaterial({
        color: 0x94a3b8,
        transparent: true,
        opacity: 0.075,
        depthWrite: false,
        roughness: 0.82,
        side: THREE.DoubleSide,
    });

    addCuboid(target, {
        x: 0, y: 0, z: -wallThickness,
        dx: dims.length, dy: dims.width, dz: wallThickness,
    }, dims, { color: "#e2e8f0", opacity: 0.72, edgeColor: 0x64748b, edgeOpacity: 0.45 });

    addCuboid(target, {
        x: 0, y: 0, z: 0,
        dx: dims.length, dy: wallThickness, dz: dims.height,
    }, dims, { material: shellMaterial, edges: false });
    addCuboid(target, {
        x: 0, y: dims.width - wallThickness, z: 0,
        dx: dims.length, dy: wallThickness, dz: dims.height,
    }, dims, { material: shellMaterial, edges: false });
    addCuboid(target, {
        x: 0, y: 0, z: dims.height - wallThickness,
        dx: dims.length, dy: dims.width, dz: wallThickness,
    }, dims, { material: shellMaterial, edges: false });
    addCuboid(target, {
        x: 0, y: 0, z: 0,
        dx: wallThickness, dy: dims.width, dz: dims.height,
    }, dims, { material: shellMaterial, edges: false });

    const frameGeometry = new THREE.BoxGeometry(dims.length, dims.height, dims.width);
    const frame = new THREE.LineSegments(
        new THREE.EdgesGeometry(frameGeometry),
        new THREE.LineBasicMaterial({ color: 0x334155, transparent: true, opacity: 0.9 }),
    );
    frame.position.set(0, dims.height / 2, 0);
    target.add(frame);

    // Preserve the current transport renderer's open rear-door convention at X=length.
    const angle = THREE.MathUtils.degToRad(135);
    const halfWidth = dims.width / 2;
    const outerX = dims.length + halfWidth * Math.sin(angle);
    const leftOuterY = halfWidth * Math.cos(angle);
    const rightOuterY = dims.width - halfWidth * Math.cos(angle);
    addPanel(target, [
        [dims.length, 0, 0],
        [outerX, leftOuterY, 0],
        [outerX, leftOuterY, dims.height],
        [dims.length, 0, dims.height],
    ], dims);
    addPanel(target, [
        [dims.length, dims.width, 0],
        [outerX, rightOuterY, 0],
        [outerX, rightOuterY, dims.height],
        [dims.length, dims.width, dims.height],
    ], dims);
}

function addItems(target, sceneData, dims) {
    (sceneData.items || []).forEach((item) => {
        addCuboid(target, item, dims, {
            color: item.color || "#f59e0b",
            opacity: number(item.opacity, 1),
            edgeColor: 0x0f172a,
            edgeOpacity: 0.72,
        });
    });
}

function updateFrustum(camera, dims, width, height) {
    const aspect = Math.max(width, 1) / Math.max(height, 1);
    const framedLength = dims.length + dims.width * 0.9;
    const desiredWidth = framedLength * 1.14;
    const desiredHeight = Math.max(dims.height * 1.55, dims.width * 1.85);
    const viewSize = Math.max(desiredHeight, desiredWidth / Math.max(aspect, 0.2), 1);
    camera.left = -viewSize * aspect / 2;
    camera.right = viewSize * aspect / 2;
    camera.top = viewSize / 2;
    camera.bottom = -viewSize / 2;
    camera.updateProjectionMatrix();
}

function setCameraView(instance, viewName) {
    const { camera, controls, dims } = instance;
    const maxDim = Math.max(dims.length, dims.width, dims.height);
    const distance = maxDim * 2.5;
    const target = new THREE.Vector3(0, dims.height * 0.46, 0);
    const views = {
        reset: new THREE.Vector3(distance * 0.82, distance * 0.58, distance * 0.88),
        top: new THREE.Vector3(0.001, distance * 1.25, 0.001),
        front: new THREE.Vector3(0, dims.height * 0.48, distance),
        side: new THREE.Vector3(distance, dims.height * 0.48, 0),
        opposite: new THREE.Vector3(-distance * 0.82, distance * 0.58, -distance * 0.88),
    };

    camera.zoom = 1;
    camera.position.copy(views[viewName] || views.reset);
    camera.up.set(0, 1, 0);
    camera.lookAt(target);
    camera.updateProjectionMatrix();
    controls.target.copy(target);
    controls.update();
    instance.currentViewName = viewName;
}

function initViewer(el) {
    if (initialized.has(el)) return;
    initialized.add(el);

    const script = document.getElementById(el.dataset.sceneScript || "");
    if (!script) {
        el.innerHTML = '<div class="transport-threejs-fallback">No transport scene data is available.</div>';
        return;
    }

    let sceneData;
    try {
        sceneData = JSON.parse(script.textContent || "{}");
    } catch (error) {
        el.innerHTML = '<div class="transport-threejs-fallback">The transport scene data could not be read.</div>';
        return;
    }

    if (!sceneData.transport_unit || !Array.isArray(sceneData.items)) {
        el.innerHTML = '<div class="transport-threejs-fallback">The transport scene is incomplete.</div>';
        return;
    }

    const dims = getDimensions(sceneData);
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
        el.innerHTML = '<div class="transport-threejs-fallback">WebGL could not start in this browser.</div>';
        console.error("KolliTransportThreeJs WebGL error:", error);
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
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -maxDim * 15, maxDim * 15);
    updateFrustum(camera, dims, initialSize.width, initialSize.height);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = true;
    controls.screenSpacePanning = true;

    scene.add(new THREE.HemisphereLight(0xffffff, 0xdbeafe, 1.65));
    const keyLight = new THREE.DirectionalLight(0xffffff, 1.3);
    keyLight.position.set(1.5, 2.4, 1.8);
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0xffffff, 0.5);
    fillLight.position.set(-1.5, 1.1, -1.2);
    scene.add(fillLight);

    const root = new THREE.Group();
    scene.add(root);
    addTransportUnit(root, dims);
    addItems(root, sceneData, dims);

    const instance = {
        scene,
        camera,
        controls,
        renderer,
        dims,
        currentViewName: "reset",
    };
    instances.set(el, instance);
    setCameraView(instance, "reset");

    const panel = el.closest(".transport-threejs-panel") || document;
    panel.querySelectorAll("[data-transport-threejs-view]").forEach((button) => {
        button.addEventListener("click", () => {
            setCameraView(instance, button.dataset.transportThreejsView || "reset");
        });
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

    const resizeTarget = el.closest(".transport-threejs-panel") || el.parentElement || el;
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
    document.querySelectorAll("[data-transport-threejs-viewer]").forEach(initViewer);
}

function captureViewer(instance, mimeType = "image/jpeg", quality = 0.88) {
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
        console.error("KolliTransportThreeJs capture error:", error);
        return "";
    }
}

function captureReportViews(viewerId) {
    const el = typeof viewerId === "string" ? document.getElementById(viewerId) : viewerId;
    const instance = el ? instances.get(el) : null;
    if (!instance) return null;

    const saved = {
        position: instance.camera.position.clone(),
        up: instance.camera.up.clone(),
        zoom: instance.camera.zoom,
        target: instance.controls.target.clone(),
        viewName: instance.currentViewName,
    };

    const snapshots = {};
    try {
        setCameraView(instance, "reset");
        snapshots.main = captureViewer(instance, "image/jpeg", 0.88);
        setCameraView(instance, "top");
        snapshots.top = captureViewer(instance, "image/jpeg", 0.88);
        setCameraView(instance, "opposite");
        snapshots.opposite = captureViewer(instance, "image/jpeg", 0.88);
    } finally {
        instance.camera.position.copy(saved.position);
        instance.camera.up.copy(saved.up);
        instance.camera.zoom = saved.zoom;
        instance.camera.updateProjectionMatrix();
        instance.controls.target.copy(saved.target);
        instance.controls.update();
        instance.currentViewName = saved.viewName;
        instance.renderer.render(instance.scene, instance.camera);
    }

    return snapshots.main && snapshots.top && snapshots.opposite ? snapshots : null;
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
    const viewerId = button ? button.dataset.transportThreejsPdfViewer : "";
    if (!form || !viewerId) {
        window.alert("The transport 3D viewer was not found. Refresh the page and run the analysis again.");
        return false;
    }

    const snapshots = captureReportViews(viewerId);
    if (!snapshots) {
        window.alert("The transport 3D views are not ready. Wait until the interactive preview is visible, then try again.");
        return false;
    }

    ensureHiddenField(form, "transport_threejs_snapshot_main").value = snapshots.main;
    ensureHiddenField(form, "transport_threejs_snapshot_top").value = snapshots.top;
    ensureHiddenField(form, "transport_threejs_snapshot_opposite").value = snapshots.opposite;
    return true;
}

function bindPdfExports() {
    document.querySelectorAll("[data-transport-threejs-pdf-button]").forEach((button) => {
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

window.KolliTransportThreeJs = window.KolliTransportThreeJs || {};
window.KolliTransportThreeJs.initAll = function () {
    initAll();
    bindPdfExports();
};
window.KolliTransportThreeJs.captureReportViews = captureReportViews;
window.KolliTransportThreeJs.preparePdfExport = preparePdfExport;
