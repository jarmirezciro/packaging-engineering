# Corrugated material reference database

## Purpose and boundary

`CorrugatedBoardConstruction` stores a complete construction and its optional
supplier/measured values. `CorrugatedECTReferenceGrade` stores a reference
performance category separately. Reference grades are screening classes; they
do not claim that every paper construction in a flute family achieves the
listed ECT.

This work supports single-wall A, B, C, E, F and N families and double-wall EB
and BC families. It does not add SCT, STC, RCT, grammage-based ECT inference,
new FEFCO styles, external-dimension logic, Packaging Flow integration, cost,
humidity, creep, vibration or finite-element analysis.

## Flute profiles

The A/B/C/E profiles remain unchanged. F and N are representative KolliPack
selections within the FEFCO-published F/G/N indicative range (0.5-0.8 mm
profile height, 400-550 flutes/m, 1.15-1.25 take-up, and 9.0-11.0 g/m² glue
per glue layer). Their values are:

| Flute | Height, facings excluded | Flutes/m | Take-up | Glue/layer |
| --- | ---: | ---: | ---: | ---: |
| F | 0.8 mm | 420 | 1.20 | 10.0 g/m² |
| N | 0.5 mm | 550 | 1.20 | 10.0 g/m² |

Nominal profile height is not finished-board caliper. Finished-board reference
caliper is stored on each reference-grade record.

## Generic construction seeds

The reference database migration adds:

- `GEN_F_125_90_125` - generic F flute, 125/90/125;
- `GEN_N_125_90_125` - generic N flute, 125/90/125.

For both constructions:

```text
G = 125 + 90 x 1.20 + 125 + 2 x 10.0
  = 378.00 g/m²
```

The total generic construction seed count is 11. All 11 retain null actual
ECT, null supplier/finished caliper and null measured BCT. Reference values
belong only to `CorrugatedECTReferenceGrade`.

## Reference-grade data model

Each active reference grade has a stable code, flute family, wall type, ECT in
lb/in and calculated ECT in kN/m, required finished-board caliper, caliper
basis, separate ECT and caliper source labels/URLs, access date, source notes,
calculation notes, status and ordering metadata. The metric field is readonly
and recalculated on save.

The conversion is:

```text
ECT_kN/m = ECT_lb/in x 0.175126835
```

The conversion constant is `ECT_LB_IN_TO_KN_M = Decimal("0.175126835")`.
Metric values are stored to greater precision and rounded only in display.

## Seed matrix

Single-wall categories are 32, 40, 44 and 55 ECT for each of A, B, C, E, F
and N (24 records). Double-wall categories are 42, 48, 51, 61, 71 and 82
ECT for EB and BC (12 records). Total: 36 reference-grade records.

| Family | Reference calipers, in ECT order |
| --- | --- |
| A | 5.15, 5.31, 5.46, 5.72 mm |
| B | 3.10, 3.26, 3.41, 3.67 mm |
| C | 4.08, 4.23, 4.38, 4.64 mm |
| E | 1.60, 1.60, 1.60, 1.60 mm |
| F | 0.80, 0.80, 0.80, 0.80 mm |
| N | 0.50, 0.50, 0.50, 0.50 mm |
| EB | 4.90, 4.90, 4.90, 4.90, 4.90, 4.90 mm |
| BC | 6.62, 6.77, 7.03, 7.20, 7.54, 7.90 mm |

A/B/C and most BC values are grade-specific target values. E/F/N values are
flute-family references. EB uses the midpoint of the published 4.8-5.0 mm
BE/EB range:

```text
(4.8 + 5.0) / 2 = 4.90 mm
```

BC 61 ECT is explicitly a linear interpolation between 350# -> 7.03 mm and
500# -> 7.54 mm:

```text
7.03 + (400 - 350) / (500 - 350) x (7.54 - 7.03) = 7.20 mm
```

## Resolution and priority

The selected board resolves to A/B/C/E/F/N for single wall, or EB/BC for the
supported double-wall pairs E+B and B+C. Compatibility is validated in the
form and again in the service; browser filtering is only an interaction aid.

Strength input priority is:

1. one-time measured BCT override;
2. measured BCT on the construction;
3. complete one-time ECT and caliper pair;
4. complete construction ECT and caliper pair;
5. selected reference ECT and reference caliper;
6. unavailable.

Reference data is never presented as measured or supplier-documented.

## Source register

| Source | Used for | Classification |
| --- | --- | --- |
| [FBA-hosted Corrugated Board Specifications](https://www.fibrebox.org/assets/2025/09/Walmart_Corrugated-Board_Specifications_Automation_Packaging_Standards.pdf) | ECT classes and A/B/C/BC target-caliper rows | Direct industry reference |
| [FEFCO European Database for Corrugated Board Life Cycle Studies 2023](https://www.fefco.org/download/file/fid/3353) | F/G/N profile ranges, take-up and glue context | Industry reference |
| [Netpak E/F/N Micro-Flute Guide](https://www.netpak.com/en/packaging-resources/industry-articles/micro-flute-packaging-e-f-n-flute/) | E/F/N family-level thickness | Manufacturer family reference |
| [Unico BE/EE Flute Reference](https://unicopacking.com/en/new/EE-flute-corrugated-box.html) | EB finished-thickness range | Manufacturer range |
| [Esko Cape Pack Corrugated Compression Strength](https://docs.esko.com/docs/en-us/cape/18/userguide/en-us/common/cape/concept/co_cape_18_CorrugatedCompressionStrength.html) | Metric McKee formula and units | Primary software methodology |
| [ISO 3037:2022](https://www.iso.org/standard/80310.html) | ECT test-method context | Standard |

Source values, unit conversions, family-level references, range midpoints,
interpolation and KolliPack screening calculations are recorded separately in
the grade metadata.
