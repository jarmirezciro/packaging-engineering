from collections import Counter, defaultdict

from packagingapp.utils.container_tool.engine import TOLERANCE, allowed_orientations


def _subtract_rectangle(rectangle, blocker):
    x0, y0, length, width = rectangle
    bx0, by0, blocker_length, blocker_width = blocker
    x1, y1 = x0 + length, y0 + width
    bx1, by1 = bx0 + blocker_length, by0 + blocker_width
    ix0, iy0 = max(x0, bx0), max(y0, by0)
    ix1, iy1 = min(x1, bx1), min(y1, by1)
    if ix1 <= ix0 + TOLERANCE or iy1 <= iy0 + TOLERANCE:
        return [rectangle]

    pieces = []
    if ix0 > x0 + TOLERANCE:
        pieces.append((x0, y0, ix0 - x0, width))
    if x1 > ix1 + TOLERANCE:
        pieces.append((ix1, y0, x1 - ix1, width))
    middle_length = ix1 - ix0
    if iy0 > y0 + TOLERANCE:
        pieces.append((ix0, y0, middle_length, iy0 - y0))
    if y1 > iy1 + TOLERANCE:
        pieces.append((ix0, iy1, middle_length, y1 - iy1))
    return pieces


def _positive_overlap(first, second):
    return (
        min(first.x + first.l, second.x + second.l)
        > max(first.x, second.x) + TOLERANCE
        and min(first.y + first.w, second.y + second.w)
        > max(first.y, second.y) + TOLERANCE
        and min(first.z + first.h, second.z + second.h)
        > max(first.z, second.z) + TOLERANCE
    )


def assert_transport_result_physical(test_case, result, container, products):
    """Validate one engine result with a bounded X sweep for overlap checks."""
    placements = result["placements"]
    permitted_by_row = {}
    for row_index, source in enumerate(products):
        permitted_by_row[row_index] = {
            tuple(round(value, 9) for value in orientation)
            for orientation in allowed_orientations(
                (source["length"], source["width"], source["height"]),
                source.get("r1", False),
                source.get("r2", False),
                source.get("r3", False),
            )
        }

    indices_by_row = defaultdict(list)
    for placement in placements:
        test_case.assertGreater(placement.l, 0)
        test_case.assertGreater(placement.w, 0)
        test_case.assertGreater(placement.h, 0)
        test_case.assertGreaterEqual(placement.x, -TOLERANCE)
        test_case.assertGreaterEqual(placement.y, -TOLERANCE)
        test_case.assertGreaterEqual(placement.z, -TOLERANCE)
        test_case.assertLessEqual(placement.x + placement.l, container["L"] + TOLERANCE)
        test_case.assertLessEqual(placement.y + placement.w, container["W"] + TOLERANCE)
        test_case.assertLessEqual(placement.z + placement.h, container["H"] + TOLERANCE)
        test_case.assertIn(
            tuple(
                round(value, 9)
                for value in (placement.l, placement.w, placement.h)
            ),
            permitted_by_row[placement.row_index],
        )
        indices_by_row[placement.row_index].append(placement.item_index)

    # The active set contains only cuboids whose X interval can overlap the
    # next cuboid, avoiding the benchmark suite's former all-pairs scan.
    active = []
    for placement in sorted(placements, key=lambda item: (item.x, item.y, item.z)):
        active = [
            other
            for other in active
            if other.x + other.l > placement.x + TOLERANCE
        ]
        for other in active:
            test_case.assertFalse(
                _positive_overlap(other, placement),
                (other, placement),
            )
        active.append(placement)

    supports_by_top = defaultdict(list)
    for placement in placements:
        supports_by_top[round(placement.z + placement.h, 7)].append(placement)
    for placement in placements:
        if placement.z <= TOLERANCE:
            continue
        unsupported = [(placement.x, placement.y, placement.l, placement.w)]
        possible_supports = supports_by_top.get(round(placement.z, 7), [])
        for support in possible_supports:
            overlap_x = min(
                placement.x + placement.l,
                support.x + support.l,
            ) - max(placement.x, support.x)
            overlap_y = min(
                placement.y + placement.w,
                support.y + support.w,
            ) - max(placement.y, support.y)
            if overlap_x <= TOLERANCE or overlap_y <= TOLERANCE:
                continue
            test_case.assertTrue(support.stackable, (support, placement))
            updated = []
            blocker = (support.x, support.y, support.l, support.w)
            for rectangle in unsupported:
                updated.extend(_subtract_rectangle(rectangle, blocker))
            unsupported = [
                rectangle
                for rectangle in updated
                if rectangle[2] > TOLERANCE and rectangle[3] > TOLERANCE
            ]
            if not unsupported:
                break
        test_case.assertFalse(unsupported, placement)

    packed_by_row = Counter(item.row_index for item in placements)
    unplaced_by_row = Counter(item["row_index"] for item in result["unplaced"])
    for row_index, source in enumerate(products):
        test_case.assertEqual(
            packed_by_row[row_index] + unplaced_by_row[row_index],
            source["qty"],
        )
        item_indices = sorted(indices_by_row[row_index])
        test_case.assertEqual(item_indices, list(range(len(item_indices))))

    expected_weight = sum(item.weight for item in placements)
    test_case.assertAlmostEqual(result["loaded_weight"], expected_weight)
    if container.get("max_weight"):
        test_case.assertLessEqual(
            expected_weight,
            float(container["max_weight"]) + TOLERANCE,
        )

    placement_volume = sum(item.l * item.w * item.h for item in placements)
    count_volume = sum(
        packed_by_row[row_index]
        * float(source["length"])
        * float(source["width"])
        * float(source["height"])
        for row_index, source in enumerate(products)
    )
    test_case.assertAlmostEqual(
        placement_volume,
        count_volume,
        delta=max(1e-3, count_volume * 1e-12),
    )

    if str(result.get("packing_mode", "")).startswith("space_evenly"):
        test_case.assertTrue(all(item.sequence == 1 for item in placements))
    else:
        test_case.assertTrue(
            all(
                item.sequence == int(products[item.row_index].get("sequence", 1))
                for item in placements
            )
        )

    return {
        "packed_by_row": dict(sorted(packed_by_row.items())),
        "unplaced_by_row": dict(sorted(unplaced_by_row.items())),
        "placement_volume": placement_volume,
    }
