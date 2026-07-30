import * as THREE from "three";

function number(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
}

export function getPalletizedLoadDimensions(sceneData, explicitBounds = null) {
    if (explicitBounds) {
        return {
            length: Math.max(number(explicitBounds.length), 1),
            width: Math.max(number(explicitBounds.width), 1),
            height: Math.max(number(explicitBounds.height), 1),
        };
    }

    const pallet = sceneData.pallet || {};
    const allowed = sceneData.allowed_footprint || {};
    const metadata = sceneData.metadata || {};
    return {
        length: Math.max(number(allowed.length, pallet.length), number(pallet.length, 1), 1),
        width: Math.max(number(allowed.width, pallet.width), number(pallet.width, 1), 1),
        height: Math.max(
            number(metadata.total_render_height_mm),
            number(pallet.height) + number(metadata.stack_height_mm),
            1,
        ),
    };
}

function localCenter(cuboid, bounds) {
<<<<<<< HEAD
    // Scene data is Python X=length, Y=width, Z=height. The local Three.js
    // assembly is centered so a transport placement can rotate it as one unit.
=======
>>>>>>> pre-production
    return new THREE.Vector3(
        number(cuboid.x) + number(cuboid.dx) / 2 - bounds.length / 2,
        number(cuboid.z) + number(cuboid.dz) / 2 - bounds.height / 2,
        number(cuboid.y) + number(cuboid.dy) / 2 - bounds.width / 2,
    );
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
<<<<<<< HEAD
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

    addBox(target, {
        x: 0,
        y: 0,
        z: runnerHeight,
        dx: length,
        dy: width,
        dz: deckThickness,
=======
    const wood = new THREE.MeshStandardMaterial({ color: 0xc69a62, roughness: 0.88, metalness: 0 });
    const runnerWood = new THREE.MeshStandardMaterial({ color: 0xa97842, roughness: 0.92, metalness: 0 });

    addBox(target, {
        x: 0, y: 0, z: runnerHeight,
        dx: length, dy: width, dz: deckThickness,
>>>>>>> pre-production
    }, bounds, wood, { color: 0x6b4423, opacity: 0.55 });

    const runnerWidth = Math.max(Math.min(width / 6, 100), 24);
    [0, (width - runnerWidth) / 2, width - runnerWidth].forEach((y) => {
        addBox(target, {
<<<<<<< HEAD
            x: 0,
            y,
            z: 0,
            dx: length,
            dy: runnerWidth,
            dz: runnerHeight,
=======
            x: 0, y, z: 0,
            dx: length, dy: runnerWidth, dz: runnerHeight,
>>>>>>> pre-production
        }, bounds, runnerWood, { color: 0x5b3b22, opacity: 0.5 });
    });
}

function addAllowedFootprint(target, sceneData, bounds) {
    const pallet = sceneData.pallet || {};
    const allowed = sceneData.allowed_footprint || {};
    if (number(allowed.length_overhang) <= 0 && number(allowed.width_overhang) <= 0) return;

    const length = Math.max(number(allowed.length), number(pallet.length), 1);
    const width = Math.max(number(allowed.width), number(pallet.width), 1);
    const geometry = new THREE.BoxGeometry(length, 1, width);
    const outline = new THREE.LineSegments(
        new THREE.EdgesGeometry(geometry),
        new THREE.LineBasicMaterial({ color: 0xf97316, transparent: true, opacity: 0.8 }),
    );
    outline.position.copy(localCenter({
<<<<<<< HEAD
        x: 0,
        y: 0,
        z: number(pallet.height) + 1.5,
        dx: length,
        dy: width,
        dz: 1,
=======
        x: 0, y: 0, z: number(pallet.height) + 1.5,
        dx: length, dy: width, dz: 1,
>>>>>>> pre-production
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
    placementsByColor.forEach((placements, color) => {
<<<<<<< HEAD
        const material = new THREE.MeshStandardMaterial({
            color,
            roughness: 0.66,
            metalness: 0.01,
        });
=======
        const material = new THREE.MeshStandardMaterial({ color, roughness: 0.66, metalness: 0.01 });
>>>>>>> pre-production
        const cases = new THREE.InstancedMesh(unitGeometry, material, placements.length);
        const outlines = new THREE.InstancedMesh(
            unitGeometry,
            new THREE.MeshBasicMaterial({ color: 0x0f172a, wireframe: true }),
            placements.length,
        );
        const matrix = new THREE.Matrix4();
        const quaternion = new THREE.Quaternion();
        const scale = new THREE.Vector3();
        placements.forEach((placement, index) => {
            scale.set(
                Math.max(number(placement.dx), 0.001),
                Math.max(number(placement.dz), 0.001),
                Math.max(number(placement.dy), 0.001),
            );
            matrix.compose(localCenter(placement, bounds), quaternion, scale);
            cases.setMatrixAt(index, matrix);
            outlines.setMatrixAt(index, matrix);
        });
        cases.instanceMatrix.needsUpdate = true;
        outlines.instanceMatrix.needsUpdate = true;
        target.add(cases);
        target.add(outlines);
    });
}

export function buildPalletizedLoadGroup(sceneData, options = {}) {
    const bounds = getPalletizedLoadDimensions(sceneData, options.bounds || null);
    const group = new THREE.Group();
    group.userData.palletizedLoadBounds = bounds;
    addPallet(group, sceneData, bounds);
<<<<<<< HEAD
    if (options.showAllowedFootprint !== false) {
        addAllowedFootprint(group, sceneData, bounds);
    }
=======
    if (options.showAllowedFootprint !== false) addAllowedFootprint(group, sceneData, bounds);
>>>>>>> pre-production
    addCases(group, sceneData, bounds);
    return group;
}
