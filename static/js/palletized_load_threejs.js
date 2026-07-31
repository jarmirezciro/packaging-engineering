import * as THREE from "three";

function number(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
}

function getAllowedFootprint(sceneData) {
    const pallet = sceneData.pallet || {};
    const allowed = sceneData.allowed_footprint || {};
    const palletLength = Math.max(number(pallet.length), 1);
    const palletWidth = Math.max(number(pallet.width), 1);
    const lengthOverhang = number(allowed.length_overhang);
    const widthOverhang = number(allowed.width_overhang);
    const length = Math.max(number(allowed.length, palletLength + lengthOverhang), palletLength, 1);
    const width = Math.max(number(allowed.width, palletWidth + widthOverhang), palletWidth, 1);

    return {
        x: number(allowed.x, -lengthOverhang / 2),
        y: number(allowed.y, -widthOverhang / 2),
        length,
        width,
        lengthOverhang,
        widthOverhang,
    };
}

export function getPalletizedLoadDimensions(sceneData, explicitBounds = null) {
    if (explicitBounds) {
        const length = Math.max(number(explicitBounds.length), 1);
        const width = Math.max(number(explicitBounds.width), 1);
        const height = Math.max(number(explicitBounds.height), 1);
        return {
            length,
            width,
            height,
            centerX: number(explicitBounds.center_x, length / 2),
            centerY: number(explicitBounds.center_y, width / 2),
        };
    }

    const pallet = sceneData.pallet || {};
    const metadata = sceneData.metadata || {};
    const footprint = getAllowedFootprint(sceneData);
    const palletLength = Math.max(number(pallet.length), 1);
    const palletWidth = Math.max(number(pallet.width), 1);
    const xValues = [0, palletLength, footprint.x, footprint.x + footprint.length];
    const yValues = [0, palletWidth, footprint.y, footprint.y + footprint.width];

    (sceneData.placements || []).forEach((placement) => {
        xValues.push(number(placement.x), number(placement.x) + number(placement.dx));
        yValues.push(number(placement.y), number(placement.y) + number(placement.dy));
    });

    const minX = Math.min(...xValues);
    const maxX = Math.max(...xValues);
    const minY = Math.min(...yValues);
    const maxY = Math.max(...yValues);
    const length = Math.max(maxX - minX, palletLength, 1);
    const width = Math.max(maxY - minY, palletWidth, 1);
    return {
        length,
        width,
        height: Math.max(
            number(metadata.total_render_height_mm),
            number(pallet.height) + number(metadata.stack_height_mm),
            1,
        ),
        minX,
        maxX,
        minY,
        maxY,
        centerX: (minX + maxX) / 2,
        centerY: (minY + maxY) / 2,
    };
}

function localCenter(cuboid, bounds) {
    return new THREE.Vector3(
        number(cuboid.x) + number(cuboid.dx) / 2 - number(bounds.centerX, bounds.length / 2),
        number(cuboid.z) + number(cuboid.dz) / 2 - bounds.height / 2,
        number(cuboid.y) + number(cuboid.dy) / 2 - number(bounds.centerY, bounds.width / 2),
    );
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
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(vertices, 3));
    return geometry;
}

function edgeGeometryKey(dx, dy, dz) {
    return [
        Math.round(dx * 1000) / 1000,
        Math.round(dy * 1000) / 1000,
        Math.round(dz * 1000) / 1000,
    ].join("x");
}

function getExternalEdgeGeometry(cache, dx, dy, dz) {
    const key = edgeGeometryKey(dx, dy, dz);
    if (!cache.has(key)) {
        cache.set(key, externalCuboidEdgeGeometry(dx, dz, dy));
    }
    return cache.get(key);
}

function addBox(target, cuboid, bounds, material, edgeOptions = {}) {
    const geometry = new THREE.BoxGeometry(
        Math.max(number(cuboid.dx), 0.001),
        Math.max(number(cuboid.dz), 0.001),
        Math.max(number(cuboid.dy), 0.001),
    );
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.copy(localCenter(cuboid, bounds));
    target.add(mesh);

    const edges = new THREE.LineSegments(
        new THREE.EdgesGeometry(geometry),
        new THREE.LineBasicMaterial({
            color: edgeOptions.color ?? 0x0f172a,
            transparent: (edgeOptions.opacity ?? 0.62) < 1,
            opacity: edgeOptions.opacity ?? 0.62,
        }),
    );
    edges.position.copy(mesh.position);
    target.add(edges);
}

function addPallet(target, sceneData, bounds) {
    const pallet = sceneData.pallet || {};
    const length = Math.max(number(pallet.length), 1);
    const width = Math.max(number(pallet.width), 1);
    const height = Math.max(number(pallet.height), 1);
    const deckThickness = Math.min(
        Math.max(number(pallet.deck_thickness, height * 0.17), 1),
        height,
    );
    const runnerHeight = Math.max(height - deckThickness, 0.001);
    const wood = new THREE.MeshStandardMaterial({ color: 0xc69a62, roughness: 0.88, metalness: 0 });
    const runnerWood = new THREE.MeshStandardMaterial({ color: 0xa97842, roughness: 0.92, metalness: 0 });

    addBox(target, {
        x: 0, y: 0, z: runnerHeight,
        dx: length, dy: width, dz: deckThickness,
    }, bounds, wood, { color: 0x6b4423, opacity: 0.55 });

    const runnerWidth = Math.max(Math.min(width / 6, 100), 24);
    [0, (width - runnerWidth) / 2, width - runnerWidth].forEach((y) => {
        addBox(target, {
            x: 0, y, z: 0,
            dx: length, dy: runnerWidth, dz: runnerHeight,
        }, bounds, runnerWood, { color: 0x5b3b22, opacity: 0.5 });
    });
}

function addAllowedFootprint(target, sceneData, bounds) {
    const pallet = sceneData.pallet || {};
    const footprint = getAllowedFootprint(sceneData);
    if (footprint.lengthOverhang <= 0 && footprint.widthOverhang <= 0) return;

    const geometry = new THREE.BoxGeometry(footprint.length, 1, footprint.width);
    const outline = new THREE.LineSegments(
        new THREE.EdgesGeometry(geometry),
        new THREE.LineBasicMaterial({ color: 0xf97316, transparent: true, opacity: 0.8 }),
    );
    outline.position.copy(localCenter({
        x: footprint.x, y: footprint.y, z: number(pallet.height) + 1.5,
        dx: footprint.length, dy: footprint.width, dz: 1,
    }, bounds));
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

function addCases(target, sceneData, bounds) {
    const placementsByColor = new Map();
    (sceneData.placements || []).forEach((placement) => {
        const color = caseColor(placement);
        if (!placementsByColor.has(color)) placementsByColor.set(color, []);
        placementsByColor.get(color).push(placement);
    });

    const unitGeometry = new THREE.BoxGeometry(1, 1, 1);
    const edgeGeometryCache = new Map();
    const edgeMaterial = new THREE.LineBasicMaterial({
        color: 0x0f172a,
        transparent: true,
        opacity: 0.62,
    });

    placementsByColor.forEach((placements, color) => {
        const material = new THREE.MeshStandardMaterial({ color, roughness: 0.66, metalness: 0.01 });
        const cases = new THREE.InstancedMesh(unitGeometry, material, placements.length);
        const matrix = new THREE.Matrix4();
        const quaternion = new THREE.Quaternion();
        const scale = new THREE.Vector3();

        placements.forEach((placement, index) => {
            const dx = Math.max(number(placement.dx), 0.001);
            const dy = Math.max(number(placement.dy), 0.001);
            const dz = Math.max(number(placement.dz), 0.001);
            const center = localCenter(placement, bounds);

            scale.set(dx, dz, dy);
            matrix.compose(center, quaternion, scale);
            cases.setMatrixAt(index, matrix);

            // Draw only the 12 real cuboid edges. The previous instanced
            // wireframe drew the internal triangle split of each rectangular
            // face, which appeared as an unwanted diagonal line on cartons.
            const edges = new THREE.LineSegments(
                getExternalEdgeGeometry(edgeGeometryCache, dx, dy, dz),
                edgeMaterial,
            );
            edges.position.copy(center);
            target.add(edges);
        });

        cases.instanceMatrix.needsUpdate = true;
        target.add(cases);
    });
}

export function buildPalletizedLoadGroup(sceneData, options = {}) {
    const bounds = getPalletizedLoadDimensions(sceneData, options.bounds || null);
    const group = new THREE.Group();
    group.userData.palletizedLoadBounds = bounds;
    addPallet(group, sceneData, bounds);
    if (options.showAllowedFootprint !== false) addAllowedFootprint(group, sceneData, bounds);
    addCases(group, sceneData, bounds);
    return group;
}
