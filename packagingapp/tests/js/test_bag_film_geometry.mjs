import assert from "node:assert/strict";
import test from "node:test";
import { buildBagFilmGeometry } from "../../../static/js/bag_film_geometry.js";

const bundle = [90, 60, 25];
const cases = [
    { axis: "length", index: 0, width: 87, length: 127, depth: 90, mouthSpans: [0, 61, 26], run: 13.5, axialSpan: 117.140054945 },
    { axis: "width", index: 1, width: 117, length: 97, depth: 60, mouthSpans: [91, 0, 26], run: 13.5, axialSpan: 87.140054945 },
    { axis: "height", index: 2, width: 152, length: 97, depth: 25, mouthSpans: [91, 61, 0], run: 31, axialSpan: 71.545268253 },
];

function span(points, axis) {
    const coordinates = points.map((point) => point[axis]);
    return Math.max(...coordinates) - Math.min(...coordinates);
}

function distance(start, end) {
    return Math.hypot(...start.map((coordinate, axis) => end[axis] - coordinate));
}

function perimeter(ring) {
    return ring.reduce((length, point, index) => length + distance(point, ring[(index + 1) % ring.length]), 0);
}

function assertNear(actual, expected) {
    assert.ok(Math.abs(actual - expected) < 1e-8, `Expected ${actual} to be near ${expected}`);
}

function assertEndBudget(film, depthAxis, depth, developedLength, allowance = 10) {
    const crossAxes = [0, 1, 2].filter((axis) => axis !== depthAxis);
    const halfShort = Math.min(...crossAxes.map((axis) => span(film.mouth, axis))) / 2;
    const panelCenter = (ring) => ring[0].map((coordinate, axis) => (coordinate + ring[1][axis]) / 2);
    const rearRun = distance(panelCenter(film.rearSeam), panelCenter(film.shoulder));
    const openingRun = film.collar[0][depthAxis] - depth;
    const sealingStrip = distance(film.collar[0], film.mouth[0]);
    const developedBody = distance(film.shoulder[0], film.collar[0]);
    assertNear(sealingStrip, allowance);
    assertNear(rearRun + developedBody + sealingStrip, developedLength);
    assert.ok(openingRun + 1e-8 >= halfShort, "Both faces can reach the center plane before sealing");
    assert.ok(rearRun <= openingRun + 1e-8);
    assert.ok(film.mouth[0][depthAxis] - film.rearSeam[0][depthAxis] < developedLength);
}

for (const example of cases) {
    test(`bag mouth and seal are perpendicular to scene ${example.axis}`, () => {
        const scene = {
            mode: "design",
            bag: {
                film: { depthAxis: example.axis, bundleDimensions: bundle },
                flatWidth: example.width,
                flatLength: example.length,
                fitTolerance: 2,
                sealingAllowance: 10,
            },
        };
        const film = buildBagFilmGeometry(scene);
        // Even an envelope field in a saved Design scene cannot change its film.
        scene.bag.film.envelopeDimensions = [400, 300, 100];
        assert.deepEqual(buildBagFilmGeometry(scene), film);
        assert.deepEqual([0, 1, 2].map((axis) => span(film.mouth, axis)), example.mouthSpans);
        assert.equal(film.openingPerimeter, 2 * example.width);
        assertNear(perimeter(film.mouth), 2 * example.width);
        const d = example.index;
        assert.equal(film.insertionDirection[d], -1);
        assertNear(film.collar[0][d] - example.depth, example.run);
        assertNear(film.mouth[0][d] - film.rearSeam[0][d], example.axialSpan);
        assertEndBudget(film, d, example.depth, example.length);
        assert.ok(film.rearSeam.every((point) => point[d] < 0));
        assert.equal(new Set(film.rearSeam.map((point) => point.join(","))).size, 2);
        assert.ok(film.arrowTail[d] - film.arrowLength > film.mouth[0][d]);
    });
}

function stockScene(mode, length, width, bundle, envelope, tolerance = 2, seal = 10) {
    return {
        mode,
        bag: {
            insertion: { axis: "height" },
            film: { depthAxis: "length", bundleDimensions: bundle, envelopeDimensions: envelope },
            flatWidth: width,
            flatLength: length,
            fitTolerance: tolerance,
            sealingAllowance: seal,
        },
    };
}

test("oversized catalogue stock does not stretch into a rigid envelope", () => {
    const scene = stockScene("optimal", 400, 300, [25, 90, 60], [328, 238, 60]);
    const film = buildBagFilmGeometry(scene);
    assertNear(film.openingPerimeter, 600);
    assertNear(perimeter(film.shoulder), 600);
    assertNear(perimeter(film.mouth), 600);
    assertNear(span(film.rearSeam, 1), 300);
    assertNear(span(film.rearSeam, 2), 0);
    assert.ok(film.rearSeam.every((point) => point[0] < 0));
    assert.deepEqual(film.insertionDirection, [-1, 0, 0]);
    assert.ok(film.mouth.every((point) => point[0] === 369));
    assertEndBudget(film, 0, 25, 400);
    assert.deepEqual(film.envelopeOutline, [[0, -74, 60], [328, -74, 60], [328, 164, 60], [0, 164, 60]]);
});

test("legacy selection scenes without an envelope retain their fitted film", () => {
    const scene = stockScene("single", 400, 300, [25, 90, 60]);
    delete scene.bag.film.envelopeDimensions;
    const film = buildBagFilmGeometry(scene);
    assert.equal(film.openingPerimeter, 304);
    assert.deepEqual(film.insertionDirection, [-1, 0, 0]);
    assert.ok(film.mouth.every((point) => point[0] === 66));
    assertEndBudget(film, 0, 25, 97);
    assert.equal(film.envelopeOutline, undefined);

    delete scene.bag.film;
    scene.products = [{ x: 0, y: 0, z: 0, dx: 25, dy: 90, dz: 60 }];
    assert.deepEqual(buildBagFilmGeometry(scene), film);
});

for (const mode of ["single", "optimal"]) {
    test(`${mode} shows the cereal bar envelope and keeps film clear of the authoritative grid`, () => {
        const scene = stockScene(mode, 300, 200, [216, 130, 50], [238, 148, 50]);
        scene.products = Array.from({ length: 12 }, (_, index) => ({
            x: 18 * index, y: 0, z: 0, dx: 18, dy: 130, dz: 50,
        }));
        const before = structuredClone(scene);
        const film = buildBagFilmGeometry(scene);
        assert.deepEqual(scene, before);
        assert.deepEqual(film.envelopeOutline, [[0, -9, 50], [238, -9, 50], [238, 139, 50], [0, 139, 50]]);
        assertEndBudget(film, 0, 216, 300);
        assertNear(perimeter(film.mouth), 400);
        assertNear(span(film.rearSeam, 1), 200);
        assert.ok([film.rearSeam, film.shoulder, film.collar, film.mouth].flat(2).every(Number.isFinite));
        assert.ok(film.rearSeam.every(([x]) => x <= 0));
        for (const { x, y, z, dx, dy, dz } of scene.products) {
            assert.ok(x >= film.shoulder[0][0] && x + dx < film.collar[0][0]);
            assert.ok(y > film.shoulder[0][1] && y + dy < film.shoulder[1][1]);
            assert.ok(z > film.shoulder[0][2] && z + dz < film.shoulder[2][2]);
        }

        const larger = stockScene(mode, 307, 205, [216, 130, 50], [245, 153, 50]);
        larger.products = scene.products;
        const largerFilm = buildBagFilmGeometry(larger);
        assertNear(largerFilm.mouth[0][0] - film.mouth[0][0], 7);
        assertNear(span(largerFilm.mouth, 1) - span(film.mouth, 1), 5);
        assertNear(largerFilm.rearSeam[0][0], film.rearSeam[0][0]);
        assertNear(span(largerFilm.mouth, 2), span(film.mouth, 2));
    });
}

test("stock film rejects an undersized or inconsistent envelope", () => {
    for (const [length, width, envelope] of [
        [277, 200, [215, 148, 50]], [300, 181, [238, 129, 50]],
        [300, 200, [238, 148, 49]], [300, 200, [238, 148, 0]],
        [300, 200, [238, 148, NaN]], [300, 200, [239, 148, 50]],
    ]) {
        assert.equal(buildBagFilmGeometry(stockScene("single", length, width, [216, 130, 50], envelope)), null);
    }
});

test("stock exact fit handles zero or fractional allowances without inventing a seal", () => {
    for (const [tolerance, seal] of [[0, 0], [0, 15.1], [4.25, 0], [4.25, 13.5]]) {
        const length = 115 + tolerance + seal;
        const width = 85 + tolerance;
        const film = buildBagFilmGeometry(stockScene("single", length, width, bundle, bundle, tolerance, seal));
        assert.ok(film);
        assert.ok([film.rearSeam, film.shoulder, film.collar, film.mouth].flat(2).every(Number.isFinite));
        assertNear(perimeter(film.mouth), 2 * width);
        assertEndBudget(film, 0, 90, length, seal);
        if (seal === 0) assert.deepEqual(film.collar, film.mouth);
    }
});

test("saved Design scenes can recover the mouth from insertion and product placement", () => {
    const film = buildBagFilmGeometry({
        mode: "design",
        bag: { insertion: { axis: "height" }, flatWidth: 152, flatLength: 97, fitTolerance: 2, sealingAllowance: 10 },
        products: [{ x: 0, y: 0, z: 0, dx: 90, dy: 60, dz: 25 }],
    });
    assert.deepEqual(film.insertionDirection, [0, 0, -1]);
    assert.equal(film.openingPerimeter, 304);
    assert.ok(film.mouth.every((point) => point[2] === 66));
    assertEndBudget(film, 2, 25, 97);
});

const fitCases = [
    { name: "equal opening spans", bundle: [70, 40, 40], axis: "length", index: 0, width: 82, length: 122, tolerance: 2 },
    { name: "cube", bundle: [30, 30, 30], axis: "width", index: 1, width: 62, length: 72, tolerance: 2 },
    { name: "thin product with large opening", bundle: [180, 120, 4], axis: "height", index: 2, width: 302, length: 136, tolerance: 2 },
    { name: "long product with small opening", bundle: [420, 12, 8], axis: "length", index: 0, width: 22, length: 440, tolerance: 2 },
    { name: "larger fit tolerance", bundle: [55, 35, 15], axis: "length", index: 0, width: 54, length: 84, tolerance: 4 },
    { name: "zero fit tolerance", bundle: [90, 60, 25], axis: "length", index: 0, width: 85, length: 125, tolerance: 0 },
    { name: "submillimetre opening span", bundle: [80, 11, 0.5], axis: "length", index: 0, width: 13.5, length: 92.5, tolerance: 2 },
];

for (const example of fitCases) {
    test(`closure and seal stay within flat stock for ${example.name}`, () => {
        const film = buildBagFilmGeometry({
            mode: "design",
            bag: {
                film: { depthAxis: example.axis, bundleDimensions: example.bundle },
                flatWidth: example.width,
                flatLength: example.length,
                fitTolerance: example.tolerance,
                sealingAllowance: 10,
            },
        });
        assertNear(perimeter(film.mouth), 2 * example.width);
        assertEndBudget(film, example.index, example.bundle[example.index], example.length);
    });
}

test("the 90 mm cube leaves 46 mm of closure film before the 10 mm seal", () => {
    const film = buildBagFilmGeometry({
        mode: "design",
        bag: {
            film: { depthAxis: "length", bundleDimensions: [90, 90, 90] },
            flatWidth: 182, flatLength: 192, fitTolerance: 2, sealingAllowance: 10,
        },
    });
    assertNear(perimeter(film.mouth), 364);
    assertNear(film.collar[0][0], 136);
    assertNear(film.mouth[0][0], 146);
    assertNear(film.rearSeam[0][0], -6.763874629);
    assertEndBudget(film, 0, 90, 192);
});

test("a four-product grid uses the bundle opening and contains every placement", () => {
    const products = [
        { x: 0, y: 0, z: 0, dx: 60, dy: 20, dz: 30 },
        { x: 60, y: 0, z: 0, dx: 60, dy: 20, dz: 30 },
        { x: 0, y: 20, z: 0, dx: 60, dy: 20, dz: 30 },
        { x: 60, y: 20, z: 0, dx: 60, dy: 20, dz: 30 },
    ];
    const film = buildBagFilmGeometry({
        mode: "design",
        products,
        bag: {
            film: { depthAxis: "width", bundleDimensions: [120, 40, 30] },
            flatWidth: 152, flatLength: 82, fitTolerance: 2, sealingAllowance: 10,
        },
    });
    assertNear(perimeter(film.mouth), 304);
    assertEndBudget(film, 1, 40, 82);
    for (const { x, y, z, dx, dy, dz } of products) {
        assert.ok(x >= film.shoulder[0][0] && x + dx <= film.shoulder[1][0]);
        assert.ok(z >= film.shoulder[0][2] && z + dz <= film.shoulder[2][2]);
        assert.ok(y >= film.shoulder[0][1] && y + dy <= film.collar[0][1]);
    }
});

test("the preview does not invent closure stock for an inconsistent saved bag length", () => {
    const scene = {
        mode: "design",
        bag: {
            film: { depthAxis: "length", bundleDimensions: bundle },
            flatWidth: 87, flatLength: 125.5, fitTolerance: 2, sealingAllowance: 10,
        },
    };
    assert.equal(buildBagFilmGeometry(scene), null);
});

for (const [index, width, length] of [[0, 89, 134], [1, 119, 104], [2, 154, 104]]) {
    test(`custom fit and seal keep the film within stock for ${cases[index].axis} insertion`, () => {
        const film = buildBagFilmGeometry({
            mode: "design",
            bag: {
                film: { depthAxis: cases[index].axis, bundleDimensions: bundle },
                flatWidth: width, flatLength: length, fitTolerance: 4, sealingAllowance: 15,
            },
        });
        assertNear(perimeter(film.mouth), 2 * width);
        assertEndBudget(film, index, bundle[index], length, 15);
    });
}

for (const seal of [0, 15.1]) {
    test(`exact fit with zero tolerance and ${seal} mm sealing produces finite film`, () => {
        const film = buildBagFilmGeometry({
            mode: "design",
            bag: {
                film: { depthAxis: "length", bundleDimensions: bundle },
                flatWidth: 85, flatLength: 115 + seal, fitTolerance: 0, sealingAllowance: seal,
            },
        });
        assert.ok(film);
        assert.ok([film.rearSeam, film.shoulder, film.collar, film.mouth].flat(2).every(Number.isFinite));
        assertNear(perimeter(film.mouth), 170);
        assertEndBudget(film, 0, 90, 115 + seal, seal);
        if (seal === 0) assert.deepEqual(film.mouth, film.collar);
    });
}
