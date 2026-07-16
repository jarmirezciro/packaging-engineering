# Packaging terminology

Use these terms consistently in UI, reports, code comments, and documentation.

## General

- **Product / base unit:** the physical item being packed.
- **Packaging:** bag, carton, box, crate, tray, pallet, transport container, or other enclosing/handling unit.
- **Candidate:** a catalogue or generated option being evaluated.
- **Selected result:** the option explicitly chosen by the user and propagated downstream.
- **Pending result:** a newly calculated result that may be displayed before explicit selection.
- **Utilization / fill:** occupied usable volume or area divided by the applicable usable capacity. Always state whether it is volume, footprint, pallet area, or payload utilization.
- **Tare:** empty packaging or transport-unit weight.
- **Payload:** maximum allowed cargo weight, excluding tare where the model defines it that way.

## Dimensions

Default tool convention is millimetres unless a field explicitly states another unit.

- **L / Length:** X direction.
- **W / Width:** Y direction.
- **H / Height:** Z direction.

Do not silently swap labels in renders or reports. A rotated placement may map product dimensions to different axes, but the product detail must still show the original user-entered L/W/H.

## Container selection

- **Orientation:** one of the six orthogonal permutations of a rectangular product.
- **R1/R2/R3:** project rotation controls. Verify exact UI meaning in the current repository; restrictions must apply globally to all main and leftover subboxes.
- **Main subbox:** the dominant rectangular region filled using one selected orientation/grid.
- **Leftover subbox:** residual region along length, width, or height after the main region is allocated.
- **Single mode:** analyse a chosen packaging unit and return maximum feasible quantity.
- **Optimal mode:** rank candidate packaging options, commonly showing a Top 5.

## Bag selection

- **Sealing space / sealing margin:** additional length reserved for closure. It belongs to the bag-length direction and is not product volume.
- **Tolerance:** non-sealing allowance for fit and handling; do not merge it with sealing margin.
- **Lay-flat dimensions:** bag dimensions measured flat. A 3D product consumes lay-flat width/length according to the current bag-fit equations.

## Palletization

- **Layer / mosaic:** the 2D top-view arrangement of cartons on one pallet layer.
- **P1/P2:** the two principal carton footprint orientations on the pallet.
- **Column view:** identical layer mosaic repeated vertically.
- **Interlock view:** alternate layer orientation/arrangement intended to improve interlocking.
- **Interlock possible:** flag indicating a valid alternate-layer construction exists; it is not a guarantee of real-world stability.
- **Main block, secondary block, filler block, filler line, sparse filler line, edge-balanced filler:** established pattern-development terms.
- **Overhang / stickout:** permitted extension beyond pallet footprint. Use “overhang” in user-facing copy.
- **Bottom-box load:** cargo load transmitted from boxes above, excluding the bottom box’s own product weight unless the engine explicitly defines otherwise.

## Transport loading

- **Transport unit:** container, trailer, reefer, box trailer, or other load space.
- **Usable internal dimensions:** the dimensions available for loading, not external dimensions.
- **Door end:** the end from which loading/access occurs and which should be visually recognizable in renders.
- **Main/Opposite/Top/Side:** approved multi-view result labels.
