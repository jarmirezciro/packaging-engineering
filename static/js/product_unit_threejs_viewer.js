import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import {
    createApprovedProductMaterials,
    createApprovedProductVisual,
    normalizeProductShape,
    orientationQuaternion,
} from "./product_shape_factory.js?v=20260731-product-shapes";

const initializedViewers = new WeakSet();
const viewerInstances = new WeakMap();

// The orientation index is the shared L × W × H axis order after rotation.
// Its third dimension is vertical in the packing contract; Three.js maps that
// vertical dimension onto world Y through orientationQuaternion().
export const PRODUCT_UNIT_ORIENTATION_PRESETS = Object.freeze({
    R1: Object.freeze({ verticalDimension: "length", orientationIndex: 3 }),
    R2: Object.freeze({ verticalDimension: "width", orientationIndex: 5 }),
    R3: Object.freeze({ verticalDimension: "height", orientationIndex: 0 }),
});

function finitePositive(value) {
    const number = Number(value);
    return Number.isFinite(number) && number > 0 ? number : null;
}

function normalizeProductData(value) {
    if (!value) return null;
    const definition = value.productDefinition || value;
    const length = finitePositive(definition.length);
    const width = finitePositive(definition.width);
    const height = finitePositive(definition.height);
    if (!length || !width || !height) return null;

    const productShape = normalizeProductShape(value.productShape || value.shape);
    return {
        productShape,
        productDefinition: { length, width, height },
        unit: String(value.unit || "mm"),
        showBoundingBox: value.showBoundingBox === undefined
            ? productShape !== "cuboid"
            : Boolean(value.showBoundingBox),
    };
}

function readScene(element) {
    const scriptId = element.dataset.sceneScript;
    const script = scriptId ? document.getElementById(scriptId) : null;
    if (!script) return null;

    try {
        return normalizeProductData(JSON.parse(script.textContent || "{}"));
    } catch (error) {
        return null;
    }
}

function findNamedControl(scope, name) {
    if (!name) return null;
    return Array.from(scope.querySelectorAll("[name]")).find(
        (control) => control.name === name,
    ) || null;
}

function liveProductControls(element) {
    if (!element.hasAttribute("data-product-unit-live")) return null;
    const scope = element.closest("[data-container-tool-root], [data-bag-tool-root]")
        || element.closest("form")
        || document;
    return {
        length: findNamedControl(scope, element.dataset.productUnitLengthInput),
        width: findNamedControl(scope, element.dataset.productUnitWidthInput),
        height: findNamedControl(scope, element.dataset.productUnitHeightInput),
        shape: findNamedControl(scope, element.dataset.productUnitShapeInput),
    };
}

function readLiveProduct(controls) {
    if (!controls || !controls.length || !controls.width || !controls.height) return null;
    return normalizeProductData({
        length: controls.length.value,
        width: controls.width.value,
        height: controls.height.value,
        shape: controls.shape ? controls.shape.value : "cuboid",
        unit: "mm",
    });
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
    const boxGeometry = new THREE.BoxGeometry(
        definition.length,
        definition.height,
        definition.width,
    );
    const geometry = new THREE.EdgesGeometry(boxGeometry);
    boxGeometry.dispose();
    const material = new THREE.LineBasicMaterial({
        color: 0x334155,
        transparent: opacity < 1,
        opacity,
    });
    group.add(new THREE.LineSegments(geometry, material));
}

function disposeObjectTree(group, preservedMaterials = new Set()) {
    const geometries = new Set();
    const materials = new Set();
    const textures = new Set();

    group.traverse((object) => {
        if (object.geometry) geometries.add(object.geometry);
        const objectMaterials = Array.isArray(object.material)
            ? object.material
            : [object.material];
        objectMaterials.filter(Boolean).forEach((material) => {
            if (preservedMaterials.has(material)) return;
            materials.add(material);
            Object.values(material).forEach((property) => {
                if (property && property.isTexture) textures.add(property);
            });
        });
    });

    geometries.forEach((geometry) => geometry.dispose());
    textures.forEach((texture) => texture.dispose());
    materials.forEach((material) => material.dispose());
    group.clear();
}

function createViewerEnvironment(element) {
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
    scene.add(keyLight);

    const root = new THREE.Group();
    scene.add(root);
    const productMaterials = createApprovedProductMaterials("#f59e0b");
    const preservedMaterials = new Set(Object.values(productMaterials));
    const defaultViewDirection = new THREE.Vector3(1.35, 0.95, 1.45).normalize();
    const centre = new THREE.Vector3();
    let sceneScale = 1;
    let radius = 1;
    let currentOrientationIndex = 0;
    let hasProduct = false;
    let contextAvailable = true;

    const camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.01, 30);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = false;
    controls.enablePan = false;
    controls.minZoom = 0.55;
    controls.maxZoom = 4;

    let lastWidth = size.width;
    let lastHeight = size.height;

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
        if (!contextAvailable) return;
        updateLabelScales();
        renderer.render(scene, camera);
    }

    function fitCurrentProduct(viewDirection = null) {
        if (!hasProduct) return;
        root.updateMatrixWorld(true);
        const bounds = new THREE.Box3().setFromObject(root);
        bounds.getCenter(centre);
        radius = Math.max(
            bounds.getBoundingSphere(new THREE.Sphere()).radius,
            sceneScale,
        );
        const currentOffset = camera.position.clone().sub(controls.target);
        const direction = viewDirection
            || (currentOffset.lengthSq() > 1e-9
                ? currentOffset.normalize()
                : defaultViewDirection);

        keyLight.position.set(sceneScale, sceneScale * 1.5, sceneScale * 1.2);
        camera.far = radius * 30;
        controls.target.copy(centre);
        camera.position.copy(centre).addScaledVector(direction, radius * 3.2);
        camera.up.set(0, 1, 0);
        camera.lookAt(centre);
        updateFrustum(lastWidth, lastHeight);
        controls.update();
        camera.updateProjectionMatrix();
        render();
    }

    function updateProduct(value) {
        const productData = normalizeProductData(value);
        if (!productData || !contextAvailable) return false;

        disposeObjectTree(root, preservedMaterials);
        const { productDefinition } = productData;
        sceneScale = Math.max(
            productDefinition.length,
            productDefinition.width,
            productDefinition.height,
        );
        const product = createApprovedProductVisual({
            shapeType: productData.productShape,
            productDefinition,
            orientationIndex: 0,
            materials: productMaterials,
        });
        root.add(product);
        if (productData.productShape === "cuboid") {
            addProductEdges(root, productDefinition, 0.8);
        } else if (productData.showBoundingBox) {
            addProductEdges(root, productDefinition, 0.24);
        }
        addDimensionGuides(root, productDefinition, productData.unit);
        root.quaternion.copy(orientationQuaternion(currentOrientationIndex));
        hasProduct = true;
        fitCurrentProduct();
        return true;
    }

    function setOrientationView(name) {
        const preset = PRODUCT_UNIT_ORIENTATION_PRESETS[name];
        if (!preset || !hasProduct || !contextAvailable) return false;
        currentOrientationIndex = preset.orientationIndex;
        root.quaternion.copy(orientationQuaternion(currentOrientationIndex));
        fitCurrentProduct();
        return true;
    }

    function resetView() {
        if (!hasProduct || !contextAvailable) return false;
        currentOrientationIndex = 0;
        root.quaternion.identity();
        camera.zoom = 1;
        fitCurrentProduct(defaultViewDirection);
        return true;
    }

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
        observer.observe(element.closest(".product-unit-threejs-panel") || element);
    }
    window.addEventListener("resize", requestResize);
    controls.addEventListener("change", render);
    renderer.domElement.addEventListener("webglcontextlost", (event) => {
        event.preventDefault();
        contextAvailable = false;
        element.innerHTML = '<div class="product-unit-threejs-fallback">The interactive 3D view lost its graphics context. Reload the page to restore it.</div>';
    }, { once: true });

    return { resetView, setOrientationView, updateProduct };
}

function initViewer(element) {
    if (initializedViewers.has(element)) return;
    initializedViewers.add(element);

    const productControls = liveProductControls(element);
    let environment = null;
    let renderingUnavailable = false;

    function updateProduct(value) {
        const productData = normalizeProductData(value);
        if (!productData || renderingUnavailable) return false;
        if (!environment) {
            environment = createViewerEnvironment(element);
            if (!environment) {
                renderingUnavailable = true;
                return false;
            }
        }
        return environment.updateProduct(productData);
    }

    const controller = {
        resetView: () => environment ? environment.resetView() : false,
        setOrientationView: (name) => environment
            ? environment.setOrientationView(name)
            : false,
        updateProduct,
    };
    viewerInstances.set(element, controller);

    const panel = element.closest(".product-unit-threejs-panel");
    const resetButton = panel
        ? panel.querySelector("[data-product-unit-threejs-reset]")
        : null;
    if (resetButton) {
        resetButton.addEventListener("click", controller.resetView);
    }
    const orientationButtons = panel
        ? panel.querySelectorAll("[data-product-unit-threejs-orientation]")
        : [];
    orientationButtons.forEach((button) => {
        button.addEventListener("click", () => {
            controller.setOrientationView(
                button.dataset.productUnitThreejsOrientation,
            );
        });
    });

    if (productControls) {
        const refreshFromInputs = () => {
            controller.updateProduct(readLiveProduct(productControls));
        };
        new Set(Object.values(productControls).filter(Boolean)).forEach((control) => {
            control.addEventListener("input", refreshFromInputs);
            control.addEventListener("change", refreshFromInputs);
        });
        const initialProduct = readLiveProduct(productControls) || readScene(element);
        if (initialProduct) {
            controller.updateProduct(initialProduct);
        } else {
            element.innerHTML = '<div class="product-unit-threejs-fallback">Enter valid product dimensions to preview.</div>';
        }
    } else {
        const initialProduct = readScene(element);
        if (initialProduct) {
            controller.updateProduct(initialProduct);
        } else {
            element.innerHTML = '<div class="product-unit-threejs-fallback">Base product dimensions are unavailable.</div>';
        }
    }
}

export function updateProductUnitViewer(element, productDefinition) {
    const controller = viewerInstances.get(element);
    return controller ? controller.updateProduct(productDefinition) : false;
}

function initAll() {
    document.querySelectorAll("[data-product-unit-threejs-viewer]").forEach(initViewer);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAll);
} else {
    initAll();
}
