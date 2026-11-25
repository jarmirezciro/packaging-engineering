const AXES = ["length", "width", "height"];

function positiveDimensions(dimensions) {
    return Array.isArray(dimensions) && dimensions.length === 3
        && dimensions.every((span) => Number.isFinite(span) && span > 0);
}

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
    if (!positiveDimensions(bundle)) return null;

    const envelope = scene.mode === "single" || scene.mode === "optimal"
        ? bag.film?.envelopeDimensions
        : undefined;
    const stock = envelope !== undefined;
    if (stock) {
        const { flatLength, flatWidth, fitTolerance, sealingAllowance } = bag;
        if (!positiveDimensions(envelope) || bag.film.depthAxis !== "length"
            || ![flatLength, flatWidth, fitTolerance, sealingAllowance].every(Number.isFinite)
            || fitTolerance < 0 || sealingAllowance < 0) return null;

        const [length, width, height] = envelope;
        // Flat stock, envelope and bundle spans are serialized to six decimals.
        const slack = 1.5e-6 + 4 * Number.EPSILON * Math.max(flatLength, flatWidth);
        if (length + slack < bundle[0] || width + slack < bundle[1] || height !== bundle[2]
            || Math.abs(length + height + fitTolerance + sealingAllowance - flatLength) > slack
            || Math.abs(width + height + fitTolerance - flatWidth) > slack) return null;
    }

    // Design retains canonical product coordinates. Selection has already
    // positioned the grid with its chosen insertion depth on scene length.
    const storedAxis = scene.mode === "design" ? bag.insertion?.axis : "length";
    const depthAxis = Math.max(0, AXES.indexOf(bag.film?.depthAxis || storedAxis));
    const [longAxis, shortAxis] = stock ? [1, 2] : [0, 1, 2]
        .filter((axis) => axis !== depthAxis)
        .sort((a, b) => bundle[b] - bundle[a]);
    const depth = bundle[depthAxis];
    const longSpan = bundle[longAxis];
    const shortSpan = bundle[shortAxis];
    const tolerance = Math.max(0, bag.fitTolerance || 0);
    const seal = Math.max(0, bag.sealingAllowance || 0);
    const widthSlack = Math.max(0, bag.flatWidth - longSpan - shortSpan);
    const pad = (stock ? tolerance : Math.min(tolerance, widthSlack)) / 4;

    const a = (stock ? envelope[1] : longSpan) / 2 + pad;
    const b = shortSpan / 2 + pad;
    const left = stock ? longSpan / 2 - a : -pad;
    const right = stock ? longSpan / 2 + a : longSpan + pad;

    // Budget the film on a longitudinal panel centerline. A rear taper of
    // axial reach r develops to hypot(r, b). Keep at least the same budget
    // at the open end so each face can travel b inward before sealing.
    // Stock bags show all remaining length. Keep the fitted rear fold so
    // surplus length extends towards the opening. Design and saved scenes
    // without an envelope retain their fitted film budget.
    const remainingLength = bag.flatLength - depth - seal;
    const fittedEndFilm = shortSpan + tolerance;
    const availableEndFilm = stock ? remainingLength : Math.min(remainingLength, fittedEndFilm);
    // Flat length and bundle spans are serialized to six decimal places.
    // Allow their accumulated rounding error at the exact-fit boundary.
    const roundingSlack = 1.5e-6 + 4 * Number.EPSILON * Math.max(bag.flatLength, depth, seal, shortSpan);
    if (!(availableEndFilm >= 2 * b - roundingSlack)) return null;
    const endFilm = Math.max(availableEndFilm, 2 * b);
    const rearBudget = (stock ? fittedEndFilm : endFilm) / 2;
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

    function ring(d, halfShort, extraWidth = 0) {
        return [
            point(d, left - extraWidth, shortSpan / 2 - halfShort),
            point(d, right + extraWidth, shortSpan / 2 - halfShort),
            point(d, right + extraWidth, shortSpan / 2 + halfShort),
            point(d, left - extraWidth, shortSpan / 2 + halfShort),
        ];
    }

    const arrowLength = Math.min(shortSpan * 0.5, Math.max(...bundle) * 0.16);
    const film = {
        // Flatten the opening perimeter into a full-width two-wall seam.
        rearSeam: ring(-rearFold, 0, stock ? b : 0),
        shoulder: ring(0, b),
        collar: ring(collarStart, b),
        mouth: ring(mouthDepth, b),
        openingPerimeter: 4 * (a + b),
        insertionDirection: point(-1, 0, 0),
        arrowTail: point(mouthDepth + arrowLength * 1.25, longSpan / 2, shortSpan / 2),
        arrowLength,
    };
    if (stock) {
        const [length, width, height] = envelope;
        const minWidth = (bundle[1] - width) / 2;
        const maxWidth = minWidth + width;
        film.envelopeOutline = [
            [0, minWidth, height], [length, minWidth, height],
            [length, maxWidth, height], [0, maxWidth, height],
        ];
    }
    return film;
}
