import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import {
    createApprovedProductMaterials,
    createApprovedProductVisual,
    normalizeProductShape,
} from "./product_shape_factory.js?v=20260731-product-shapes";

const initializedViewers = new WeakSet();

function finitePositive(value) {
    const number = Number(value);
    return Number.isFinite(number) && number > 0 ? number : null;
}

function readScene(element) {
    const scriptId = element.dataset.sceneScript;
    const script = scriptId ? document.getElementById(scriptId) : null;
    if (!script) return null;

    try {
        const scene = JSON.parse(script.textContent || "{}");
        const definition = scene.productDefinition || {};
        const length = finitePositive(definition.length);
        const width = finitePositive(definition.width);
        const height = finitePositive(definition.height);
        if (!length || !width || !height) return null;
        return {
            productShape: normalizeProductShape(scene.productShape),
            productDefinition: { length, width, height },
            orientationIndex: 0,
            unit: String(scene.unit || "mm"),
            showBoundingBox: Boolean(scene.showBoundingBox),
        };
    } catch (error) {
        return null;
    }
}

function viewerSize(element) {
    const rect = element.getBoundingClientRect();
    return {
        width: Math.max(Math.round(rect.width || element.clientWidth || 640), 1),
        height: Math.max(Math.round(rect.height || element.clientHeight || 320), 1),
    };
}

function formatDimension(value) {
    return new Intl.NumberFormat(undefined, {
        maximumFractionDigits: 3,
        useGrouping: false,
    }).format(value);
}

function roundedRect(context, x, y, width, height, radius) {
    const safeRadius = Math.min(radius, width / 2, height / 2);
    context.beginPath();
    context.roundRect(x, y, width, height, safeRadius);
    context.closePath();
}

function createLabelSprite(text, sceneScale) {
    const canvas = document.createElement("canvas");
    canvas.width = 1024;
    canvas.height = 256;
    const context = canvas.getContext("2d");
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = "rgba(255, 255, 255, 0.96)";
    context.strokeStyle = "rgba(15, 23, 42, 0.22)";
    context.lineWidth = 5;
    roundedRect(context, 10, 10, canvas.width - 20, canvas.height - 20, 36);
    context.fill();
    context.stroke();
    context.fillStyle = "#172033";
    context.font = "700 104px system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(text, canvas.width / 2, canvas.height / 2 + 2, canvas.width - 70);

    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.minFilter = THREE.LinearFilter;
    const material = new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        depthTest: false,
        depthWrite: false,
    });
    const sprite = new THREE.Sprite(material);
    const height = sceneScale * 0.12;
    sprite.scale.set(height * 4, height, 1);
    sprite.userData.dimensionLabelAspect = 4;
    sprite.renderOrder = 10;
    return sprite;
}

function addSegments(group, pointPairs, material) {
    const positions = [];
    pointPairs.forEach(([start, end]) => {
        positions.push(start.x, start.y, start.z, end.x, end.y, end.z);
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    const lines = new THREE.LineSegments(geometry, material);
    group.add(lines);
    return lines;
}

function addArrowhead(group, point, direction, length, material) {
    const geometry = new THREE.ConeGeometry(length * 0.34, length, 12);
    const arrow = new THREE.Mesh(geometry, material);
    arrow.position.copy(point).addScaledVector(direction, length * 0.5);
    arrow.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction);
    group.add(arrow);
}

function addDimensionGuide({
    group,
    start,
    end,
    extensionStarts,
    labelPosition,
    label,
    sceneScale,
    lineMaterial,
    arrowMaterial,
}) {
    const direction = new THREE.Vector3().subVectors(end, start).normalize();
    addSegments(group, [[start, end]], lineMaterial);
    addSegments(group, [
        [extensionStarts[0], start],
        [extensionStarts[1], end],
    ], lineMaterial);
    const arrowLength = sceneScale * 0.032;
    addArrowhead(group, start, direction, arrowLength, arrowMaterial);
    addArrowhead(group, end, direction.clone().negate(), arrowLength, arrowMaterial);
    const sprite = createLabelSprite(label, sceneScale);
    sprite.position.copy(labelPosition);
    group.add(sprite);
}

function addDimensionGuides(group, definition, unit) {
    const { length, width, height } = definition;
    const sceneScale = Math.max(length, width, height);
    const offset = sceneScale * 0.18;
    const labelDrop = sceneScale * 0.075;
    const lineMaterial = new THREE.LineBasicMaterial({ color: 0x334155 });
    const arrowMaterial = new THREE.MeshBasicMaterial({ color: 0x334155 });
    const xMin = -length / 2;
    const xMax = length / 2;
    const yMin = -height / 2;
    const yMax = height / 2;
    const zMin = -width / 2;
    const zMax = width / 2;

    const lengthY = yMin - offset;
    const lengthZ = zMax + offset * 0.12;
    addDimensionGuide({
        group,
        start: new THREE.Vector3(xMin, lengthY, lengthZ),
        end: new THREE.Vector3(xMax, lengthY, lengthZ),
        extensionStarts: [
            new THREE.Vector3(xMin, yMin, zMax),
            new THREE.Vector3(xMax, yMin, zMax),
        ],
        labelPosition: new THREE.Vector3(-length * 0.12, lengthY - labelDrop, lengthZ),
        label: `Length — ${formatDimension(length)} ${unit}`,
        sceneScale,
        lineMaterial,
        arrowMaterial,
    });

    const widthX = xMax + offset;
    const widthY = yMin - offset * 0.12;
    addDimensionGuide({
        group,
        start: new THREE.Vector3(widthX, widthY, zMin),
        end: new THREE.Vector3(widthX, widthY, zMax),
        extensionStarts: [
            new THREE.Vector3(xMax, yMin, zMin),
            new THREE.Vector3(xMax, yMin, zMax),
        ],
        labelPosition: new THREE.Vector3(widthX + labelDrop * 0.8, widthY - labelDrop, 0),
        label: `Width — ${formatDimension(width)} ${unit}`,
        sceneScale,
        lineMaterial,
        arrowMaterial,
    });

    const heightX = xMin - offset;
    const heightZ = zMin - offset * 0.12;
    addDimensionGuide({
        group,
        start: new THREE.Vector3(heightX, yMin, heightZ),
        end: new THREE.Vector3(heightX, yMax, heightZ),
        extensionStarts: [
            new THREE.Vector3(xMin, yMin, zMin),
            new THREE.Vector3(xMin, yMax, zMin),
        ],
        labelPosition: new THREE.Vector3(heightX - labelDrop, 0, heightZ),
        label: `Height — ${formatDimension(height)} ${unit}`,
        sceneScale,
        lineMaterial,
        arrowMaterial,
    });
}

function addProductEdges(group, definition, opacity) {
    const geometry = new THREE.EdgesGeometry(new THREE.BoxGeometry(
        definition.length,
        definition.height,
        definition.width,
    ));
    const material = new THREE.LineBasicMaterial({
        color: 0x334155,
        transparent: opacity < 1,
        opacity,
    });
    group.add(new THREE.LineSegments(geometry, material));
}

function initViewer(element) {
    if (initializedViewers.has(element)) return;
    initializedViewers.add(element);

    const sceneData = readScene(element);
    if (!sceneData) {
        element.innerHTML = '<div class="product-unit-threejs-fallback">Base product dimensions are unavailable.</div>';
        return;
    }

    const { productDefinition } = sceneData;
    const sceneScale = Math.max(
        productDefinition.length,
        productDefinition.width,
        productDefinition.height,
    );
    const size = viewerSize(element);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf8fafc);

    let renderer;
    try {
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    } catch (error) {
        element.innerHTML = '<div class="product-unit-threejs-fallback">Interactive 3D is unavailable. Check this browser\'s WebGL settings.</div>';
        return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(size.width, size.height, false);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    element.replaceChildren(renderer.domElement);

    scene.add(new THREE.HemisphereLight(0xffffff, 0xdbe4ee, 1.8));
    const keyLight = new THREE.DirectionalLight(0xffffff, 1.45);
    keyLight.position.set(sceneScale, sceneScale * 1.5, sceneScale * 1.2);
    scene.add(keyLight);

    const root = new THREE.Group();
    const materials = createApprovedProductMaterials("#f59e0b");
    const product = createApprovedProductVisual({
        shapeType: sceneData.productShape,
        productDefinition,
        orientationIndex: 0,
        materials,
    });
    root.add(product);
    if (sceneData.productShape === "cuboid") {
        addProductEdges(root, productDefinition, 0.8);
    } else if (sceneData.showBoundingBox) {
        addProductEdges(root, productDefinition, 0.24);
    }
    addDimensionGuides(root, productDefinition, sceneData.unit);
    scene.add(root);
    root.updateMatrixWorld(true);

    const bounds = new THREE.Box3().setFromObject(root);
    const centre = bounds.getCenter(new THREE.Vector3());
    const radius = Math.max(bounds.getBoundingSphere(new THREE.Sphere()).radius, sceneScale);
    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.01, radius * 30);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = false;
    controls.enablePan = false;
    controls.minZoom = 0.55;
    controls.maxZoom = 4;
    controls.target.copy(centre);

    function updateFrustum(width, height) {
        const aspect = Math.max(width, 1) / Math.max(height, 1);
        const viewSize = radius * 2.28 * Math.max(1, 1 / aspect);
        camera.left = -viewSize * aspect / 2;
        camera.right = viewSize * aspect / 2;
        camera.top = viewSize / 2;
        camera.bottom = -viewSize / 2;
        camera.updateProjectionMatrix();
    }

    function updateLabelScales() {
        const canvasHeight = Math.max(renderer.domElement.clientHeight || size.height, 1);
        const canvasWidth = Math.max(renderer.domElement.clientWidth || size.width, 1);
        const visibleWorldHeight = (camera.top - camera.bottom) / camera.zoom;
        root.traverse((object) => {
            const aspect = object.userData.dimensionLabelAspect;
            if (object.isSprite && aspect) {
                const labelPixelWidth = Math.min(104, Math.max(76, canvasWidth * 0.42));
                const labelPixelHeight = labelPixelWidth / aspect;
                const labelWorldHeight = visibleWorldHeight * labelPixelHeight / canvasHeight;
                object.scale.set(labelWorldHeight * aspect, labelWorldHeight, 1);
            }
        });
    }

    function render() {
        updateLabelScales();
        renderer.render(scene, camera);
    }

    function resetView() {
        camera.position.copy(centre).add(new THREE.Vector3(1.35, 0.95, 1.45).normalize().multiplyScalar(radius * 3.2));
        camera.up.set(0, 1, 0);
        camera.zoom = 1;
        camera.lookAt(centre);
        controls.target.copy(centre);
        controls.update();
        camera.updateProjectionMatrix();
        render();
    }

    updateFrustum(size.width, size.height);
    resetView();
    controls.addEventListener("change", render);

    const panel = element.closest(".product-unit-threejs-panel");
    const resetButton = panel ? panel.querySelector("[data-product-unit-threejs-reset]") : null;
    if (resetButton) resetButton.addEventListener("click", resetView);

    let lastWidth = size.width;
    let lastHeight = size.height;
    let resizePending = false;
    function applyResize() {
        resizePending = false;
        const next = viewerSize(element);
        if (Math.abs(next.width - lastWidth) < 1 && Math.abs(next.height - lastHeight) < 1) return;
        lastWidth = next.width;
        lastHeight = next.height;
        renderer.setSize(next.width, next.height, false);
        updateFrustum(next.width, next.height);
        render();
    }
    function requestResize() {
        if (resizePending) return;
        resizePending = true;
        window.requestAnimationFrame(applyResize);
    }
    if ("ResizeObserver" in window) {
        const observer = new ResizeObserver(requestResize);
        observer.observe(panel || element);
    }
    window.addEventListener("resize", requestResize);
    renderer.domElement.addEventListener("webglcontextlost", (event) => {
        event.preventDefault();
        element.innerHTML = '<div class="product-unit-threejs-fallback">The interactive 3D view lost its graphics context. Reload the page to restore it.</div>';
    }, { once: true });
}

function initAll() {
    document.querySelectorAll("[data-product-unit-threejs-viewer]").forEach(initViewer);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
} else {
    initAll();
}
