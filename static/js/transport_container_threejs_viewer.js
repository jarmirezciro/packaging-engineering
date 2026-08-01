import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { buildPalletizedLoadGroup } from "./palletized_load_threejs.js";

const initialized = new WeakSet();
const instances = new Map();

const TRANSPORT_VIEW_PRESETS = Object.freeze({
    loading: Object.freeze({
        direction: Object.freeze([0.82, 0.58, 0.88]),
        up: Object.freeze([0, 1, 0]),
        padding: 1.1,
    }),
    opposite: Object.freeze({
        direction: Object.freeze([-0.82, 0.58, -0.88]),
        up: Object.freeze([0, 1, 0]),
        padding: 1.1,
    }),
    top: Object.freeze({
        direction: Object.freeze([0, 1, 0]),
        up: Object.freeze([0, 0, -1]),
        padding: 1.1,
    }),
});

const TRANSPORT_REPORT_VIEWS = Object.freeze(["loading", "opposite", "top"]);
const TRANSPORT_REPORT_VIEWPORTS = Object.freeze({
    loading: Object.freeze({ width: 1400, height: 620 }),
    opposite: Object.freeze({ width: 1000, height: 640 }),
    top: Object.freeze({ width: 1000, height: 640 }),
});

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

const PALLET_ORIENTATION_BASES = {
    lwh: [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
    wlh: [[0, 0, -1], [0, 1, 0], [1, 0, 0]],
    lhw: [[1, 0, 0], [0, 0, -1], [0, 1, 0]],
    hlw: [[0, 0, 1], [1, 0, 0], [0, 1, 0]],
    whl: [[0, 1, 0], [0, 0, 1], [1, 0, 0]],
    hwl: [[0, 1, 0], [-1, 0, 0], [0, 0, 1]],
};

function setPalletOrientation(group, orientation) {
    const basis = PALLET_ORIENTATION_BASES[orientation];
    if (!basis) return false;
    const matrix = new THREE.Matrix4().makeBasis(
        new THREE.Vector3(...basis[0]),
        new THREE.Vector3(...basis[1]),
        new THREE.Vector3(...basis[2]),
    );
    group.setRotationFromMatrix(matrix);
    return true;
}

function addItems(target, sceneData, dims) {
    const visualizations = sceneData.workflow_visualizations || {};
    const palletPrototypes = new Map();

    (sceneData.items || []).forEach((item) => {
        const visualization = visualizations[item.visualization_ref];
        if (
            item.source_type === "palletization_result"
            && visualization
            && visualization.scene
            && visualization.bounds
            && item.pallet_orientation
        ) {
            let prototype = palletPrototypes.get(item.visualization_ref);
            if (!prototype) {
                prototype = buildPalletizedLoadGroup(visualization.scene, {
                    bounds: visualization.bounds,
                    showAllowedFootprint: false,
                });
                palletPrototypes.set(item.visualization_ref, prototype);
            }
            const palletizedLoad = prototype.clone(true);
            if (setPalletOrientation(palletizedLoad, item.pallet_orientation)) {
                palletizedLoad.position.copy(centerPosition(item, dims));
                palletizedLoad.userData.transportPlacement = {
                    x: number(item.x),
                    y: number(item.y),
                    z: number(item.z),
                    dx: number(item.dx),
                    dy: number(item.dy),
                    dz: number(item.dz),
                };
                target.add(palletizedLoad);
                return;
            }
        }

        addCuboid(target, item, dims, {
            color: item.color || "#f59e0b",
            opacity: number(item.opacity, 1),
            edgeColor: 0x0f172a,
            edgeOpacity: 0.72,
        });
    });
}

function cuboidsTouch(a, b, tolerance) {
    return (
        number(a.x) <= number(b.x) + number(b.dx) + tolerance
        && number(b.x) <= number(a.x) + number(a.dx) + tolerance
        && number(a.y) <= number(b.y) + number(b.dy) + tolerance
        && number(b.y) <= number(a.y) + number(a.dy) + tolerance
        && number(a.z) <= number(b.z) + number(b.dz) + tolerance
        && number(b.z) <= number(a.z) + number(a.dz) + tolerance
    );
}

function significantProductZones(items) {
    if (!items.length) return [];

    const dimensions = items.flatMap((item) => [number(item.dx), number(item.dy), number(item.dz)])
        .filter((value) => value > 0);
    const cellSize = Math.max(...dimensions, 1);
    const tolerance = Math.max(Math.min(...dimensions, cellSize) * 0.03, 1);
    const parents = items.map((_, index) => index);
    const buckets = new Map();

    function root(index) {
        while (parents[index] !== index) {
            parents[index] = parents[parents[index]];
            index = parents[index];
        }
        return index;
    }

    function join(a, b) {
        const rootA = root(a);
        const rootB = root(b);
        if (rootA !== rootB) parents[rootB] = rootA;
    }

    items.forEach((item, index) => {
        const ranges = [
            [number(item.x) - tolerance, number(item.x) + number(item.dx) + tolerance],
            [number(item.y) - tolerance, number(item.y) + number(item.dy) + tolerance],
            [number(item.z) - tolerance, number(item.z) + number(item.dz) + tolerance],
        ].map(([minimum, maximum]) => [
            Math.floor(minimum / cellSize),
            Math.floor(maximum / cellSize),
        ]);
        const candidates = new Set();
        const occupiedKeys = [];
        for (let x = ranges[0][0]; x <= ranges[0][1]; x += 1) {
            for (let y = ranges[1][0]; y <= ranges[1][1]; y += 1) {
                for (let z = ranges[2][0]; z <= ranges[2][1]; z += 1) {
                    const key = `${x}:${y}:${z}`;
                    occupiedKeys.push(key);
                    (buckets.get(key) || []).forEach((candidate) => candidates.add(candidate));
                }
            }
        }
        candidates.forEach((candidate) => {
            if (cuboidsTouch(item, items[candidate], tolerance)) join(index, candidate);
        });
        occupiedKeys.forEach((key) => {
            if (!buckets.has(key)) buckets.set(key, []);
            buckets.get(key).push(index);
        });
    });

    const components = new Map();
    items.forEach((item, index) => {
        const componentRoot = root(index);
        if (!components.has(componentRoot)) components.set(componentRoot, []);
        components.get(componentRoot).push(item);
    });
    return [...components.values()]
        .sort((a, b) => b.length - a.length)
        .slice(0, 4);
}

function createZoneLabelSprite(text) {
    const canvas = document.createElement("canvas");
    canvas.width = 192;
    canvas.height = 96;
    const context = canvas.getContext("2d");
    if (!context) return null;

    context.fillStyle = "rgba(15, 23, 42, 0.9)";
    context.beginPath();
    context.roundRect(14, 12, 164, 72, 18);
    context.fill();
    context.strokeStyle = "rgba(255, 255, 255, 0.9)";
    context.lineWidth = 4;
    context.stroke();
    context.fillStyle = "#ffffff";
    context.font = "700 42px Arial, sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(text, 96, 49);

    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.needsUpdate = true;
    const material = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        depthTest: false,
        depthWrite: false,
        toneMapped: false,
    });
    const sprite = new THREE.Sprite(material);
    sprite.renderOrder = 1000;
    sprite.userData.labelPixelWidth = 54;
    sprite.userData.labelPixelHeight = 27;
    return sprite;
}

function addProductZoneLabels(target, sceneData, dims) {
    const itemsByProduct = new Map();
    (sceneData.items || []).forEach((item) => {
        const productId = String(item.product_id || "");
        if (!productId) return;
        if (!itemsByProduct.has(productId)) itemsByProduct.set(productId, []);
        itemsByProduct.get(productId).push(item);
    });

    const sprites = [];
    itemsByProduct.forEach((items, productId) => {
        significantProductZones(items).forEach((zone) => {
            const minimumX = Math.min(...zone.map((item) => number(item.x)));
            const maximumX = Math.max(...zone.map((item) => number(item.x) + number(item.dx)));
            const minimumY = Math.min(...zone.map((item) => number(item.y)));
            const maximumY = Math.max(...zone.map((item) => number(item.y) + number(item.dy)));
            const maximumZ = Math.max(...zone.map((item) => number(item.z) + number(item.dz)));
            const sprite = createZoneLabelSprite(productId);
            if (!sprite) return;
            sprite.position.copy(mapPosition(
                (minimumX + maximumX) / 2,
                (minimumY + maximumY) / 2,
                maximumZ + Math.max(dims.height * 0.012, 12),
                dims,
            ));
            target.add(sprite);
            sprites.push(sprite);
        });
    });
    return sprites;
}

function stableBoundsCorners(dims) {
    const corners = [];
    [-dims.length / 2, dims.length / 2].forEach((x) => {
        [0, dims.height].forEach((y) => {
            [-dims.width / 2, dims.width / 2].forEach((z) => {
                corners.push(new THREE.Vector3(x, y, z));
            });
        });
    });
    return corners;
}

function fitTransportView(instance, preset, width, height) {
    const { camera, dims } = instance;
    const aspect = Math.max(width, 1) / Math.max(height, 1);
    const right = new THREE.Vector3(1, 0, 0).applyQuaternion(camera.quaternion);
    const up = new THREE.Vector3(0, 1, 0).applyQuaternion(camera.quaternion);
    const target = new THREE.Vector3(0, dims.height / 2, 0);
    let minimumX = Infinity;
    let maximumX = -Infinity;
    let minimumY = Infinity;
    let maximumY = -Infinity;

    stableBoundsCorners(dims).forEach((corner) => {
        const relative = corner.sub(target);
        const projectedX = relative.dot(right);
        const projectedY = relative.dot(up);
        minimumX = Math.min(minimumX, projectedX);
        maximumX = Math.max(maximumX, projectedX);
        minimumY = Math.min(minimumY, projectedY);
        maximumY = Math.max(maximumY, projectedY);
    });

    const projectedWidth = Math.max(maximumX - minimumX, 1);
    const projectedHeight = Math.max(maximumY - minimumY, 1);
    const requiredHeightForWidth = projectedWidth / Math.max(aspect, 0.1);
    const requiredViewHeight = Math.max(requiredHeightForWidth, projectedHeight) * preset.padding;
    camera.aspect = aspect;
    camera.left = -requiredViewHeight * aspect / 2;
    camera.right = requiredViewHeight * aspect / 2;
    camera.top = requiredViewHeight / 2;
    camera.bottom = -requiredViewHeight / 2;
    camera.updateProjectionMatrix();
}

function updateViewButtons(instance) {
    instance.panel.querySelectorAll("[data-transport-threejs-view]").forEach((button) => {
        const active = button.dataset.transportThreejsView === instance.currentViewName;
        button.classList.toggle("active", active);
        button.setAttribute("aria-pressed", active ? "true" : "false");
    });
}

function applyTransportView(instance, viewName, options = {}) {
    const presetName = TRANSPORT_VIEW_PRESETS[viewName] ? viewName : "loading";
    const preset = TRANSPORT_VIEW_PRESETS[presetName];
    const { camera, controls, dims } = instance;
    const width = options.width || instance.renderer.domElement.width || 1;
    const height = options.height || instance.renderer.domElement.height || 1;
    const maxDim = Math.max(dims.length, dims.width, dims.height);
    const target = new THREE.Vector3(0, dims.height / 2, 0);
    const direction = new THREE.Vector3(...preset.direction).normalize();

    camera.rotation.set(0, 0, 0);
    camera.quaternion.identity();
    camera.up.set(...preset.up);
    camera.zoom = 1;
    camera.position.copy(target).addScaledVector(direction, maxDim * 3);
    camera.lookAt(target);
    camera.updateMatrixWorld(true);
    controls.target.copy(target);
    fitTransportView(instance, preset, width, height);
    controls.update();
    instance.currentViewName = presetName;
    if (options.updateButtons !== false) updateViewButtons(instance);
    if (options.render !== false) instance.renderer.render(instance.scene, camera);
}

function updateLabelScales(instance) {
    const canvasHeight = Math.max(
        instance.renderer.domElement.height / instance.renderer.getPixelRatio(),
        1,
    );
    const visibleHeight = (instance.camera.top - instance.camera.bottom) / instance.camera.zoom;
    const worldUnitsPerPixel = visibleHeight / canvasHeight;
    (instance.labelSprites || []).forEach((sprite) => {
        sprite.scale.set(
            sprite.userData.labelPixelWidth * worldUnitsPerPixel,
            sprite.userData.labelPixelHeight * worldUnitsPerPixel,
            1,
        );
    });
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
    const labelSprites = addProductZoneLabels(root, sceneData, dims);
    const panel = el.closest(".transport-threejs-panel") || document;

    const instance = {
        scene,
        camera,
        controls,
        renderer,
        dims,
        panel,
        labelSprites,
        currentViewName: "loading",
    };
    instances.set(el, instance);
    applyTransportView(instance, "loading", {
        width: initialSize.width,
        height: initialSize.height,
    });

    panel.querySelectorAll("[data-transport-threejs-view]").forEach((button) => {
        button.addEventListener("click", () => {
            applyTransportView(instance, button.dataset.transportThreejsView || "loading");
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
        renderer.setSize(next.width, next.height, false);
        camera.aspect = next.width / next.height;
        camera.updateProjectionMatrix();
        applyTransportView(instance, instance.currentViewName, {
            width: next.width,
            height: next.height,
            updateButtons: false,
            render: false,
        });
        controls.update();
        updateLabelScales(instance);
        renderer.render(scene, camera);
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
        updateLabelScales(instance);
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

    const rendererSize = instance.renderer.getSize(new THREE.Vector2());
    const saved = {
        position: instance.camera.position.clone(),
        up: instance.camera.up.clone(),
        quaternion: instance.camera.quaternion.clone(),
        zoom: instance.camera.zoom,
        left: instance.camera.left,
        right: instance.camera.right,
        top: instance.camera.top,
        bottom: instance.camera.bottom,
        aspect: instance.camera.aspect,
        target: instance.controls.target.clone(),
        viewName: instance.currentViewName,
        rendererWidth: rendererSize.x,
        rendererHeight: rendererSize.y,
    };

    const snapshots = {};
    try {
        TRANSPORT_REPORT_VIEWS.forEach((viewName) => {
            const viewport = TRANSPORT_REPORT_VIEWPORTS[viewName];
            instance.renderer.setSize(viewport.width, viewport.height, false);
            instance.camera.aspect = viewport.width / viewport.height;
            instance.camera.updateProjectionMatrix();
            applyTransportView(instance, viewName, {
                width: viewport.width,
                height: viewport.height,
                updateButtons: false,
                render: false,
            });
            instance.controls.update();
            updateLabelScales(instance);
            instance.renderer.render(instance.scene, instance.camera);
            snapshots[viewName] = captureViewer(instance, "image/jpeg", 0.88);
        });
    } finally {
        instance.renderer.setSize(saved.rendererWidth, saved.rendererHeight, false);
        instance.camera.position.copy(saved.position);
        instance.camera.up.copy(saved.up);
        instance.camera.quaternion.copy(saved.quaternion);
        instance.camera.zoom = saved.zoom;
        instance.camera.left = saved.left;
        instance.camera.right = saved.right;
        instance.camera.top = saved.top;
        instance.camera.bottom = saved.bottom;
        instance.camera.aspect = saved.aspect;
        instance.camera.updateProjectionMatrix();
        instance.controls.target.copy(saved.target);
        instance.controls.update();
        instance.currentViewName = saved.viewName;
        updateViewButtons(instance);
        updateLabelScales(instance);
        instance.renderer.render(instance.scene, instance.camera);
    }

    return TRANSPORT_REPORT_VIEWS.every((viewName) => snapshots[viewName])
        ? snapshots
        : null;
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

    ensureHiddenField(form, "transport_threejs_snapshot_loading").value = snapshots.loading;
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
window.KolliTransportThreeJs.applyTransportView = function (viewerId, viewName) {
    const el = typeof viewerId === "string" ? document.getElementById(viewerId) : viewerId;
    const instance = el ? instances.get(el) : null;
    if (!instance) return false;
    applyTransportView(instance, viewName);
    return true;
};
