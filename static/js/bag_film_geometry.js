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

    // Use only the fit allowance at the mouth. Extra stock on oversized bags
    // can fold or wrinkle, so the preview leaves it unmodelled.
    const lengthSlack = Math.max(0, bag.flatLength - depth - seal - tolerance);
    const rearFold = Math.min(shortSpan / 2, lengthSlack);
    const collarStart = depth + tolerance;
    const mouthDepth = collarStart + seal;
    const a = longSpan / 2 + pad;
    const b = shortSpan / 2 + pad;

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
