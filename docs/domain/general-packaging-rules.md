# General packaging-engineering rules

## Deterministic geometry

All dimensional feasibility must be based on explicit usable dimensions and allowed orientations. Never infer fit from volume alone.

## Units

- Default dimensions: mm.
- Transport/result volumes may be displayed in m³, but conversions must be explicit and tested.
- Weights must state the unit and whether tare is included.
- Reports and visualizations must match input labels.

## Feasibility layers

A result can be geometrically feasible but operationally infeasible. Keep constraints separate:

1. geometry;
2. orientation restrictions;
3. requested quantity;
4. packaging/pallet/transport payload;
5. stack-height limit;
6. bottom-box compression/load limit;
7. overhang/tolerance;
8. catalogue or business restrictions.

Do not collapse these into one opaque score.

## Ranking

Ranking should be traceable. Typical priorities may include:

- meets requested quantity;
- all mandatory constraints pass;
- maximum quantity;
- minimum packaging size/material;
- highest footprint/volume/payload utilization;
- least excess capacity;
- operational preference.

The exact order is tool-specific and must be documented and tested.

## Visualization is explanatory, not proof

A render must correspond to engine placements, but a visually plausible render is not evidence that the algorithm is correct. Validate coordinates, overlap, bounds, counts, and constraints independently.

## Real-world disclaimer

KolliPack calculations are engineering decision support. Unless implemented and validated, they do not automatically account for:

- product fragility;
- friction and load shift;
- packaging compression strength;
- humidity and storage duration;
- axle loads;
- dangerous goods segregation;
- door clearance and loading equipment;
- irregular/non-rectangular shapes;
- local transport regulation.

UI and reports should expose relevant omitted assumptions rather than imply universal physical safety.
