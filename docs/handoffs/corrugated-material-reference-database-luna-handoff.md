# Corrugated reference database and compression-capacity handoff

## Delivered scope

The current `pre-production` branch now contains the complete reference-grade
slice for Corrugated Material & Strength. Migration `0013_corrugated_reference_database`
adds F/N construction choices, two generic construction seeds, the new source
and derivation metadata, and updates the reference-grade seeds with complete
calipers. It uses `update_or_create()` with stable codes and does not delete
admin-created rows.

Counts after migration:

- generic board constructions: 11;
- reference ECT grades: 36;
- single wall: A/B/C/E/F/N x 32/40/44/55 ECT;
- double wall: EB/BC x 42/48/51/61/71/82 ECT.

Every reference grade has a positive caliper and source URL. Every generic
construction retains null actual ECT, caliper and measured BCT.

## Compression capacity

The authoritative calculation is `calculate_compression_capacity()` in
`packagingapp/tools/corrugated_material_strength/strength.py`. It uses the
available measured or predicted BCT, distribution factor, gross packed-box
mass, and pallet-service current load values. It returns JSON-safe primitives
after service serialization and supports partial results.

```text
F_allowable = BCT_available / distribution_factor
m_allowable = F_allowable / 9.80665
N_above_max = floor(m_allowable / gross_box_mass)
N_column_max = N_above_max + 1
m_current = current_boxes_above x gross_box_mass
usage = current_force / F_allowable x 100
F_remaining = max(0, F_allowable - current_force)
m_remaining = F_remaining / 9.80665
N_remaining = floor(m_remaining / gross_box_mass)
```

Overload force is current force minus allowable force when positive. Overload
mass uses gravity conversion and overload equivalent boxes remain decimal
information. Stacked pallets preserve the existing pallet service's complete
supported mass and static force; the equivalent supported-box load may be
decimal because it can include an upper pallet mass.

Results are always labelled preliminary screening values and include the
warning that equivalent capacity is for one vertical load column, not a
recommended physical stack height. Height, stability, moisture, storage,
pallet deflection, vibration, uneven distribution, cutouts and manufacturing
variation can govern first.

## Verification and follow-up

Focused pure-Python checks can run without Django:

```powershell
python -m py_compile packagingapp\tools\corrugated_material_strength\strength.py
node --check static\js\corrugated_material_strength.js
```

The desktop bundled Django runtime was unavailable in this workspace during
the handoff: its temporary Django package was incomplete, and the repository
`.venv` points to a removed Spyder interpreter. Run the focused Django suite
after restoring the project environment:

```powershell
python manage.py test packagingapp.tests.test_corrugated_material_strength
python manage.py check
```

No production branch, deployment, migration execution against production data,
Packaging Flow, SCT/STC, or external-dimension implementation was changed by
this task.
