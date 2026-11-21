import assert from "node:assert/strict";
import test from "node:test";
import { buildBagFilmGeometry } from "../../../static/js/bag_film_geometry.js";

const bundle = [90, 60, 25];
const cases = [
    { axis: "length", index: 0, width: 87, length: 127, depth: 90, mouthSpans: [0, 61, 26] },
    { axis: "width", index: 1, width: 117, length: 97, depth: 60, mouthSpans: [91, 0, 26] },
    { axis: "height", index: 2, width: 152, length: 97, depth: 25, mouthSpans: [91, 61, 0] },
];

function span(points, axis) {
    const coordinates = points.map((point) => point[axis]);
    return Math.max(...coordinates) - Math.min(...coordinates);
}

for (const example of cases) {
    test(`bag mouth and seal are perpendicular to scene ${example.axis}`, () => {
        const film = buildBagFilmGeometry({
            mode: "design",
            bag: {
                film: { depthAxis: example.axis, bundleDimensions: bundle },
                flatWidth: example.width,
                flatLength: example.length,
                fitTolerance: 2,
                sealingAllowance: 10,
            },
        });
        assert.deepEqual([0, 1, 2].map((axis) => span(film.mouth, axis)), example.mouthSpans);
        assert.equal(film.openingPerimeter, 2 * example.width);
        const d = example.index;
        assert.equal(film.insertionDirection[d], -1);
        assert.equal(film.collar[0][d], example.depth + 2);
        assert.equal(film.mouth[0][d] - film.collar[0][d], 10);
        assert.ok(film.rearSeam.every((point) => point[d] < 0));
        assert.equal(new Set(film.rearSeam.map((point) => point.join(","))).size, 2);
        assert.ok(film.arrowTail[d] - film.arrowLength > film.mouth[0][d]);
    });
}

test("oversized catalogue stock does not stretch into a rigid envelope", () => {
    const film = buildBagFilmGeometry({
        mode: "single",
        bag: {
            insertion: { axis: "height" },
            film: { depthAxis: "length", bundleDimensions: [25, 90, 60] },
            flatWidth: 300,
            flatLength: 400,
            fitTolerance: 2,
            sealingAllowance: 10,
        },
    });
    assert.equal(film.openingPerimeter, 304);
    assert.deepEqual(film.insertionDirection, [-1, 0, 0]);
    assert.ok(film.mouth.every((point) => point[0] === 37));
});

test("saved Design scenes can recover the mouth from insertion and product placement", () => {
    const film = buildBagFilmGeometry({
        mode: "design",
        bag: { insertion: { axis: "height" }, flatWidth: 152, flatLength: 97, fitTolerance: 2, sealingAllowance: 10 },
        products: [{ x: 0, y: 0, z: 0, dx: 90, dy: 60, dz: 25 }],
    });
    assert.deepEqual(film.insertionDirection, [0, 0, -1]);
    assert.equal(film.openingPerimeter, 304);
    assert.ok(film.mouth.every((point) => point[2] === 37));
});
