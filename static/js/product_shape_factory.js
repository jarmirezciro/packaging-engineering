import * as THREE from "three";

/**
 * Approved KolliPack product-shape geometry.
 *
 * Canonical local axes:
 *   local X = original product length
 *   local Y = original product height / longitudinal axis
 *   local Z = original product width
 */

export const PRODUCT_SHAPE_VALUES = Object.freeze([
    "cuboid",
    "cylinder",
    "bottle",
    "pillow_bag",
]);

export function normalizeProductShape(value) {
    const normalized = String(value || "").trim().toLowerCase();
    return PRODUCT_SHAPE_VALUES.includes(normalized) ? normalized : "cuboid";
}

export function createApprovedProductMaterials(color = "#f59e0b") {
    const main = new THREE.MeshStandardMaterial({
        color: new THREE.Color(color),
        roughness: 0.46,
        metalness: 0.02,
    });

    const film = new THREE.MeshPhysicalMaterial({
        color: new THREE.Color(color),
        roughness: 0.30,
        metalness: 0.02,
        clearcoat: 0.35,
        clearcoatRoughness: 0.38,
        side: THREE.DoubleSide,
    });

    const detail = new THREE.MeshStandardMaterial({
        color: new THREE.Color(color),
        roughness: 0.64,
        metalness: 0.01,
    });

    return { main, film, detail };
}

function positiveDimension(value, fallback = 1) {
    const numeric = Number(value);
    return Number.isFinite(numeric) && numeric > 0 ? numeric : fallback;
}

/**
 * Authoritative visual orientation mapping.
 *
 * orientationIndex follows the current Python order:
 *   0: L × W × H
 *   1: L × H × W
 *   2: W × L × H
 *   3: W × H × L
 *   4: H × W × L
 *   5: H × L × W
 */
export function orientationQuaternion(orientationIndex) {
    const index = Number.isInteger(Number(orientationIndex))
        ? Math.max(0, Math.min(5, Number(orientationIndex)))
        : 0;

    const basis = [
        [new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, 1)],
        [new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, -1, 0)],
        [new THREE.Vector3(0, 0, -1), new THREE.Vector3(0, 1, 0), new THREE.Vector3(1, 0, 0)],
        [new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, 1), new THREE.Vector3(1, 0, 0)],
        [new THREE.Vector3(0, -1, 0), new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 0, 1)],
        [new THREE.Vector3(0, 0, 1), new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 1, 0)],
    ][index];

    const matrix = new THREE.Matrix4().makeBasis(basis[0], basis[1], basis[2]);
    return new THREE.Quaternion().setFromRotationMatrix(matrix);
}

function createCanonicalCuboid(length, width, height, material) {
    const group = new THREE.Group();
    group.add(new THREE.Mesh(
        new THREE.BoxGeometry(length, height, width),
        material,
    ));
    return group;
}

function createCanonicalCylinder(length, width, height, material) {
    const group = new THREE.Group();
    const geometry = new THREE.CylinderGeometry(0.5, 0.5, 1, 28, 1, false);
    const mesh = new THREE.Mesh(geometry, material);
    mesh.scale.set(length, height, width);
    group.add(mesh);
    return group;
}

function createCanonicalBottle(length, width, height, materials) {
    const group = new THREE.Group();
    const profile = [
        new THREE.Vector2(0.43, -0.50),
        new THREE.Vector2(0.48, -0.46),
        new THREE.Vector2(0.50, -0.39),
        new THREE.Vector2(0.50, 0.20),
        new THREE.Vector2(0.47, 0.26),
        new THREE.Vector2(0.36, 0.34),
        new THREE.Vector2(0.24, 0.39),
        new THREE.Vector2(0.145, 0.405),
        new THREE.Vector2(0.145, 0.47),
    ];

    const body = new THREE.Mesh(
        new THREE.LatheGeometry(profile, 28),
        materials.main,
    );
    body.scale.set(length, height, width);
    group.add(body);

    const cap = new THREE.Mesh(
        new THREE.CylinderGeometry(0.16, 0.16, 0.065, 24),
        materials.detail,
    );
    cap.scale.set(length, height, width);
    cap.position.y = height * 0.468;
    group.add(cap);

    return group;
}

function createPillowBody(length, width, bodyHeight, material) {
    const segmentsAcross = 28;
    const segmentsAlong = 36;
    const positions = [];
    const indices = [];

    function appendSurface(front) {
        const baseIndex = positions.length / 3;
        const sign = front ? 1 : -1;

        for (let row = 0; row <= segmentsAlong; row += 1) {
            const v = -1 + (2 * row / segmentsAlong);
            const halfLength = length * 0.5 * (
                0.79 + 0.17 * Math.pow(Math.abs(v), 1.65)
            );
            const endFactor = Math.pow(Math.max(0, 1 - v * v), 0.54);
            const centreFullness = 0.88 + 0.12 * Math.cos(v * Math.PI * 0.5);

            for (let column = 0; column <= segmentsAcross; column += 1) {
                const u = -1 + (2 * column / segmentsAcross);
                const sideFactor = Math.pow(Math.max(0, 1 - u * u), 0.46);
                const x = u * halfLength;
                const y = v * bodyHeight * 0.5;
                const z = sign * width * 0.5 * endFactor * sideFactor * centreFullness;
                positions.push(x, y, z);
            }
        }

        for (let row = 0; row < segmentsAlong; row += 1) {
            for (let column = 0; column < segmentsAcross; column += 1) {
                const a = baseIndex + row * (segmentsAcross + 1) + column;
                const b = a + 1;
                const c = a + segmentsAcross + 1;
                const d = c + 1;

                if (front) {
                    indices.push(a, c, b, b, c, d);
                } else {
                    indices.push(a, b, c, b, d, c);
                }
            }
        }
    }

    appendSurface(true);
    appendSurface(false);

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geometry.setIndex(indices);
    geometry.computeVertexNormals();
    geometry.computeBoundingBox();
    geometry.computeBoundingSphere();

    return new THREE.Mesh(geometry, material);
}

function addSealRibs(group, length, width, sealHeight, centreY, material) {
    const ribCount = 5;
    const ribSpacing = sealHeight * 0.13;
    const ribHeight = sealHeight * 0.055;
    const ribDepth = Math.max(width * 0.14, 0.001);

    for (let index = 0; index < ribCount; index += 1) {
        const offset = (index - (ribCount - 1) / 2) * ribSpacing;
        const rib = new THREE.Mesh(
            new THREE.BoxGeometry(length * 0.96, ribHeight, ribDepth),
            material,
        );
        rib.position.y = centreY + offset;
        group.add(rib);
    }
}

function createCanonicalPillowBag(length, width, height, materials) {
    const group = new THREE.Group();
    const sealHeight = height * 0.115;
    const bodyHeight = Math.max(height - 2 * sealHeight, height * 0.5);
    const sealDepth = Math.max(width * 0.11, Math.min(length, width, height) * 0.015);

    group.add(createPillowBody(length, width, bodyHeight, materials.film));

    const sealGeometry = new THREE.BoxGeometry(length, sealHeight, sealDepth);
    const topY = height * 0.5 - sealHeight * 0.5;
    const bottomY = -topY;

    const topSeal = new THREE.Mesh(sealGeometry, materials.detail);
    topSeal.position.y = topY;
    group.add(topSeal);

    const bottomSeal = new THREE.Mesh(sealGeometry, materials.detail);
    bottomSeal.position.y = bottomY;
    group.add(bottomSeal);

    addSealRibs(group, length, width, sealHeight, topY, materials.detail);
    addSealRibs(group, length, width, sealHeight, bottomY, materials.detail);

    return group;
}

export function createApprovedProductVisual({
    shapeType,
    productDefinition,
    orientationIndex = 0,
    materials,
}) {
    const normalizedShape = normalizeProductShape(shapeType);
    const definition = productDefinition || {};
    const length = positiveDimension(definition.length);
    const width = positiveDimension(definition.width);
    const height = positiveDimension(definition.height);
    const visualMaterials = materials || createApprovedProductMaterials();

    let group;
    if (normalizedShape === "cylinder") {
        group = createCanonicalCylinder(length, width, height, visualMaterials.main);
    } else if (normalizedShape === "bottle") {
        group = createCanonicalBottle(length, width, height, visualMaterials);
    } else if (normalizedShape === "pillow_bag") {
        group = createCanonicalPillowBag(length, width, height, visualMaterials);
    } else {
        group = createCanonicalCuboid(length, width, height, visualMaterials.main);
    }

    group.quaternion.copy(orientationQuaternion(orientationIndex));
    group.userData.productShape = normalizedShape;
    group.userData.orientationIndex = Number(orientationIndex) || 0;
    return group;
}
