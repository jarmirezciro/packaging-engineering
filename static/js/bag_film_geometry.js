const AXES = ["length", "width", "height"];

function bundleDimensions(scene) {
    const dimensions = scene.bag?.film?.bundleDimensions;
    if (dimensions) return dimensions;

    // Saved scenes can predate the film contract. Their product placements
    // still use physical coordinates, even when the old envelope was oversized.
    const bounds = [0, 0, 0];
    for (const product of scene.products || []) {
        for (const [axis, coordinate] of ["x", "y", "z"].entries()) {
            bounds[axis] = Math.max(bounds[axis], product[coordinate] + product["d" + coordinate]);
        }
    }
    return bounds;
}

export function buildBagFilmGeometry(scene) {
    const bag = scene.bag || {};
    const bundle = bundleDimensions(scene);
    if (bundle.length !== 3 || !bundle.every((span) => Number.isFinite(span) && span > 0)) {
        return null;
    }

    // Design retains canonical product coordinates. Selection has already
    // positioned the grid with its chosen insertion depth on scene length.
    const storedAxis = scene.mode === "design" ? bag.insertion?.axis : "length";
    const depthAxis = Math.max(0, AXES.indexOf(bag.film?.depthAxis || storedAxis));
    const [longAxis, shortAxis] = [0, 1, 2]
        .filter((axis) => axis !== depthAxis)
        .sort((a, b) => bundle[b] - bundle[a]);
    const depth = bundle[depthAxis];
    const longSpan = bundle[longAxis];
    const shortSpan = bundle[shortAxis];
    const tolerance = Math.max(0, bag.fitTolerance || 0);
    const seal = Math.max(0, bag.sealingAllowance || 0);
    const widthSlack = Math.max(0, bag.flatWidth - longSpan - shortSpan);
    const pad = Math.min(tolerance, widthSlack) / 4;

    const a = longSpan / 2 + pad;
    const b = shortSpan / 2 + pad;

    // Budget the film on a longitudinal panel centerline. A rear taper of
    // axial reach r develops to hypot(r, b). Keep at least the same budget
    // at the open end so each face can travel b inward before sealing.
    // Loose stock beyond the fitted envelope remains unmodelled.
    const availableEndFilm = Math.min(bag.flatLength - depth - seal, shortSpan + tolerance);
    // Flat length and bundle spans are serialized to six decimal places.
    // Allow their accumulated rounding error at the exact-fit boundary.
    const roundingSlack = 1.5e-6 + 4 * Number.EPSILON * Math.max(bag.flatLength, depth, seal, shortSpan);
    if (!(availableEndFilm >= 2 * b - roundingSlack)) return null;
    const endFilm = Math.max(availableEndFilm, 2 * b);
    const rearBudget = endFilm / 2;
    const rearFold = Math.min(shortSpan / 2, Math.sqrt((rearBudget - b) * (rearBudget + b)));
    const openingRun = endFilm - Math.hypot(rearFold, b);
    const collarStart = depth + openingRun;
    const mouthDepth = collarStart + seal;

    function point(d, across, rise) {
        const position = [0, 0, 0];
        position[depthAxis] = d;
        position[longAxis] = across;
        position[shortAxis] = rise;
        return position;
    }

    function ring(d, halfShort) {
        return [
            point(d, -pad, shortSpan / 2 - halfShort),
            point(d, longSpan + pad, shortSpan / 2 - halfShort),
            point(d, longSpan + pad, shortSpan / 2 + halfShort),
            point(d, -pad, shortSpan / 2 + halfShort),
        ];
    }

    const arrowLength = Math.min(shortSpan * 0.5, Math.max(...bundle) * 0.16);
    return {
        rearSeam: ring(-rearFold, 0),
        shoulder: ring(0, b),
        collar: ring(collarStart, b),
        mouth: ring(mouthDepth, b),
        openingPerimeter: 4 * (a + b),
        insertionDirection: point(-1, 0, 0),
        arrowTail: point(mouthDepth + arrowLength * 1.25, longSpan / 2, shortSpan / 2),
        arrowLength,
    };
}
