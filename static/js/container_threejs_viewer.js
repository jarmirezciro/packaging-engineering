import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { buildBagFilmGeometry } from "./bag_film_geometry.js?v=20261125";
import {
    createApprovedProductMaterials,
    createApprovedProductVisual,
    normalizeProductShape,
} from "./product_shape_factory.js?v=20260731-product-shapes";

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

function hasValidProductDefinition(productDefinition) {
    if (!productDefinition) return false;
    return ["length", "width", "height"].every((key) => {
        const value = Number(productDefinition[key]);
        return Number.isFinite(value) && value > 0;
    });
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

function addEdges(mesh, target, edgeColor = 0x111827, opacity = 0.65) {
    // Draw only the 12 real cuboid edges. Do not use WireframeGeometry or
    // generic triangle edges here, because that exposes the internal diagonal
    // used when rectangular faces are triangulated by WebGL/Three.js.
    const size = geometrySize(mesh.geometry);
    const edges = externalCuboidEdgeGeometry(size.width, size.height, size.depth);
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

function addBagFilm(target, dims, sceneData) {
    const film = buildBagFilmGeometry(sceneData);
    if (!film) return false;
    const stock = Boolean(film.envelopeOutline);

    function mapped(point) {
        return mapPosition(...point, dims);
    }

    function addFilmPanels(rings, color, opacity, collapsedRear = false) {
        const positions = rings.flatMap((ring) => ring.flatMap((point) => mapped(point).toArray()));
        const indices = [];
        for (let row = 1; row < rings.length; row += 1) {
            for (let i = 0; i < 4; i += 1) {
                const a = (row - 1) * 4 + i;
                const b = (row - 1) * 4 + (i + 1) % 4;
                if (!(collapsedRear && row === 1 && i % 2 === 1)) indices.push(a, b, b + 4);
                indices.push(a, b + 4, a + 4);
            }
        }
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
        geometry.setIndex(indices);
        geometry.computeVertexNormals();
        target.add(new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({
            color, transparent: true, opacity, side: THREE.DoubleSide,
            depthWrite: false, roughness: 0.55, flatShading: true,
        })));
    }

    addFilmPanels([film.rearSeam, film.shoulder, film.collar], 0x56c6d2, 0.23, stock);
    const showCollar = !stock || sceneData.bag.sealingAllowance > 0;
    if (showCollar) addFilmPanels([film.collar, film.mouth], 0x0b8ba1, 0.38);
    const seamMaterial = new THREE.LineBasicMaterial({ color: 0x14748a });
    const seam = new THREE.BufferGeometry().setFromPoints(film.rearSeam.slice(0, 2).map(mapped));
    target.add(new THREE.Line(seam, seamMaterial));
    for (const ring of showCollar ? [film.collar, film.mouth] : [film.mouth]) {
        target.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(ring.map(mapped)), seamMaterial));
    }
    const [x, y, z] = film.insertionDirection;
    target.add(new THREE.ArrowHelper(
        new THREE.Vector3(x, z, y), mapped(film.arrowTail), film.arrowLength, 0x126f83,
        film.arrowLength * 0.38, film.arrowLength * 0.32,
    ));

    if (stock) {
        const outline = [...film.envelopeOutline, film.envelopeOutline[0]];
        const dashSize = Math.max(dims.length, dims.width) / 48;
        const guide = new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(outline.map(mapped)),
            new THREE.LineDashedMaterial({
                color: 0x164e63, transparent: true, opacity: 0.9, depthWrite: false,
                dashSize, gapSize: dashSize * 0.7,
            }),
        );
        guide.computeLineDistances();
        guide.renderOrder = 1;
        target.add(guide);
    }
    return stock;
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

    const edgeVertices = [];
    [0, 1, 1, 2, 2, 3, 3, 0].forEach((idx) => {
        const p = points[idx];
        const mapped = mapPosition(p[0], p[1], p[2], dims);
        edgeVertices.push(mapped.x, mapped.y, mapped.z);
    });
    const edgeGeometry = new THREE.BufferGeometry();
    edgeGeometry.setAttribute("position", new THREE.Float32BufferAttribute(edgeVertices, 3));
    const lines = new THREE.LineSegments(
        edgeGeometry,
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
    const target = dims.target || new THREE.Vector3(0, dims.height * 0.45, 0);
    const distance = maxDim * 2.0;

    const views = {
        reset: new THREE.Vector3(distance * 0.85, distance * 0.55, distance * 0.85),
        top: new THREE.Vector3(0.001, distance * 1.1, 0.001),
        front: new THREE.Vector3(0, distance * 0.35, distance),
        side: new THREE.Vector3(distance, distance * 0.35, 0),
    };

    camera.position.copy(views[viewName] || views.reset);
    if (dims.target) camera.position.add(target);
    camera.up.set(0, 1, 0);
    camera.lookAt(target);
    controls.target.copy(target);
    controls.update();
}

function setupCamera(width, height, dims, fitNarrow = false) {
    const aspect = Math.max(width, 1) / Math.max(height, 1);
    const maxDim = Math.max(dims.length, dims.width, dims.height);
    // Slightly wider orthographic frame so the container, flaps and edges fit comfortably.
    const getViewSize = (aspect) => maxDim * 2.05 / (fitNarrow ? Math.min(1, aspect) : 1);
    const viewSize = getViewSize(aspect);

    const camera = new THREE.OrthographicCamera(
        -viewSize * aspect / 2,
        viewSize * aspect / 2,
        viewSize / 2,
        -viewSize / 2,
        -maxDim * 10,
        maxDim * 10,
    );
    return { camera, getViewSize };
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

    const isBag = sceneData.packageType === "bag";
    const hasStockEnvelope = isBag && addBagFilm(containerGroup, dims, sceneData);
    if (!isBag) {
        addContainerBody(containerGroup, dims);
        addRscFlaps(containerGroup, dims, sceneData);
    }

    (sceneData.subboxes || []).forEach((box) => {
        addCuboid(subboxGroup, box, dims, {
            color: box.color || "#2563eb",
            opacity: number(box.opacity, 0.1),
            edgeColor: 0x111827,
            edgeOpacity: 0.22,
        });
    });

    const productShape = normalizeProductShape(sceneData.productShape);
    const useApprovedProductShape = (
        productShape !== "cuboid"
        && hasValidProductDefinition(sceneData.productDefinition)
    );
    const productMaterial = useApprovedProductShape ? null : new THREE.MeshStandardMaterial({
        color: 0xf59e0b,
        roughness: 0.64,
        metalness: 0.02,
    });
    const approvedProductMaterials = useApprovedProductShape
        ? createApprovedProductMaterials("#f59e0b")
        : null;

    (sceneData.products || []).forEach((item) => {
        if (useApprovedProductShape) {
            const visual = createApprovedProductVisual({
                shapeType: productShape,
                productDefinition: sceneData.productDefinition,
                orientationIndex: item.orientationIndex,
                materials: approvedProductMaterials,
            });
            visual.position.copy(centerPosition(item, dims));
            productGroup.add(visual);
        } else {
            addCuboid(productGroup, item, dims, {
                material: productMaterial,
                edgeColor: 0x1e40af,
                edgeOpacity: 0.75,
            });
        }
    });

    let viewDims = dims;
    if (isBag) {
        const bounds = new THREE.Box3().setFromObject(root);
        const size = bounds.getSize(new THREE.Vector3());
        viewDims = {
            length: size.x, width: size.z, height: size.y,
            target: bounds.getCenter(new THREE.Vector3()),
        };
    }
    const { camera, getViewSize } = setupCamera(width, height, viewDims, hasStockEnvelope);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.screenSpacePanning = true;

    let currentViewName = "reset";
    setCameraView(camera, controls, viewDims, currentViewName);

    const panel = el.closest(".container-threejs-panel") || document;
    panel.querySelectorAll("[data-container-threejs-view]").forEach((button) => {
        button.addEventListener("click", () => {
            currentViewName = button.dataset.containerThreejsView || "reset";
            setCameraView(camera, controls, viewDims, currentViewName);
        });
    });

    let envelopeLegend;
    if (hasStockEnvelope) {
        envelopeLegend = document.createElement("p");
        envelopeLegend.className = "small text-muted mt-2 mb-0";
        envelopeLegend.textContent = "Dashed outline shows the idealized usable bag footprint at the bundle height.";
        el.after(envelopeLegend);
    }

    const bagToggle = isBag && panel.querySelector('[data-container-threejs-toggle="container"]');
    if (bagToggle) {
        function syncBagVisibility() {
            containerGroup.visible = bagToggle.checked;
            if (envelopeLegend) envelopeLegend.hidden = !bagToggle.checked;
        }
        bagToggle.addEventListener("change", syncBagVisibility);
        syncBagVisibility();
    }

    const toggle = panel.querySelector('[data-container-threejs-toggle="subboxes"]');
    if (toggle) {
        toggle.addEventListener("change", () => {
            subboxGroup.visible = Boolean(toggle.checked);
        });
        subboxGroup.visible = Boolean(toggle.checked);
    } else {
        subboxGroup.visible = false;
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
        const viewSize = getViewSize(aspect);
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
