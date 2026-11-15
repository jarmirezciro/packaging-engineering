# Evidence and review notes

## Source and scope

The attached brief supplies the editorial direction and the three screenshots supply case evidence. The article targets the informational query “why empty container space can be unusable”. It uses occupancy and carton fulfillment to explain the booking decision. The existing mixed-cargo delivery-sequence draft focuses on orientation and stops, and the 40-foot EasyCargo draft focuses on reproducing a vendor example. This deep dive uses a different 20-foot manifest to explain fragmented space.

EasyCargo’s Swedish-language URL for the [container-volume article](https://www.easycargo3d.com/sv/blog/container-volume-calculator/) displays English copy dated 15 May 2025. The matching [Fully loaded container figure](https://www.easycargo3d.com/wp-content/uploads/2025/05/How-to-calculate-container-volume_loaded-cargo.jpg) was visually checked against the supplied third screenshot on 15 November 2026. Its visible rows give 116 of 121 placed, including 10 of 15 Item I cartons. The panel rounds loaded volume to 21.99 m³ and shows 1,160 kg. The [SME logistics article](https://www.easycargo3d.com/sv/blog/ssme-logistics-optimize-cargo-transport/) dated 3 February 2026 displays three different figures, including a 48-ft semitrailer. Cite the directly verified May 2025 figure for the nine-carton exercise. The case owner confirmed that all nine EasyCargo carton types were stackable and could rotate on their base while staying upright, equivalent to R3 only in KolliPack. This confirmation comes from the owner. The source figure shows the manifest and result. EasyCargo version, licence plan and other advanced settings are unspecified. The article links to the source and reports the observed count to establish the shared Item I shortfall. The explanation centers on how mixed carton dimensions and loading sequence shape usable space. The plans do not establish that a complete arrangement is impossible. Vendor imagery was inspected for verification and is linked by URL only. No rights clearance is asserted.

Background research includes Martello, Pisinger and Vigo on three-dimensional bin packing and Lodi, Martello and Vigo on packing heuristics. Those links were moved out of the reader-facing article. The case source and practical securing reference remain in the draft. The physical execution section cites the IMO page for the joint IMO/ILO/UNECE CTU Code. The worked example represents calculated geometry and planning inputs. The study has no physical loading or shipment observations.

## Backend reproduction

Working tree on production, base commit 3d18f4a. Ran one direct call using the already-present 20-ft preset manifest with R1 and R2 disabled for all rows. R3 and stackability remained enabled. Progressive Fill – Mixed Cargo Infill preserves the three groups. The case uses millimetres and kilograms with no unit conversion at input. Container dimensions are 5,758 × 2,352 × 2,385 mm with a 28,200 kg payload. The article includes all nine rows.

- Entrypoint chain is get_transport_container_case_preset → _prepare_transport_analysis → engine.pack_container → engine.summarize.
- 121 requested, 119 placed. Item I is the sole shortfall at 13 of 15.
- 32.29961616 m³ internal, 22.640 m³ loaded, 70.093712% utilization.
- 1,190 kg loaded, 4.219858% utilization. Occupied height 2,300 mm and residual height 85 mm.
- Unused volume is 9.65961616 m³ by subtraction. Two 600 mm cubes total 0.432 m³.
- The visible KolliPack counts and percentages agree with the backend. No coordinate-level comparison with the supplied screenshot was performed.
- The unplaced reason string mentions Balanced Spread even though the selected mode and result are Progressive Fill – Mixed Cargo Infill. The string is omitted from editorial claims. The run supports the observed shortfall, with no proof of a global optimum or exhaustive residual-space analysis.

The original named preset enables all three rotation families. The article links to the upright-only variant at `/free-container-loading-calculator/?case=20ft-upright-mixed-cartons`, which reuses the existing manifest and disables R1 and R2. The focused public-calculator test verifies the three groups and the 119 placed, two unplaced result, with Item I as the sole shortfall.

## Title laboratory

Scores out of five based on clarity, fidelity, reader decision and search fit.

| Angle | Candidate | Score |
| --- | --- | --- |
| Problem | Why Empty Container Space Doesn’t Always Mean More Cargo Will Fit | 5 |
| Search | Why Empty Container Space Can Be Unusable | 5 |
| Result | Why Two Cartons Stayed Behind in a 20-Foot Container | 4 |
| Business | When Is There Room for One More Carton? | 4 |
| Curiosity | Where Did the Last 9.66 Cubic Metres Go? | 3 |
| Mechanism | How Gap Shape Limits Container Loading | 4 |

The visible title retains the brief’s question. The search title uses the shorter informational formulation. The thumbnail reads “Gaps / Cargo left out”.

## Figure and editorial review

Figure 1 compares two schematic carton-stack positions directly. It is a conceptual cross-section. The physical scenario modeled is mixed cartons → 20-foot container, with no pallet stage. The case manifest and Figure 2 show the actual scenario. Figure 2 is a lossless crop of the supplied KolliPack view. The article table carries exact quantities and links the P9 label to Item I.

The Fresh-Eyes Business Reader self-review used a logistics manager deciding whether to revisit the load plan or book more capacity. The revision aligned the mode name with the calculator, added manual reproduction instructions, connected the gap concept to measured headroom and preserved the article’s focus on a planning decision. The software-trial questions ask for measurable evidence from a recurring shipment.

Thumbnail candidate is retained beside its validation and provenance. It passed renderer hard checks. The generated scene represents the concept. Owner review of the actual thumbnail is pending before staging the referenced static file. Publication remains on hold.

## Verification results

- The Django detail template rendered through the real article loader and view using a local preview request. The public listing and detail lookup exclude this draft.
- Visual self-review passed for the gap figure, its reflowed mobile version and the supplied-result crop. The final detail preview was inspected at 1,280 px and 390 px. Both figures decode correctly, the expected desktop/mobile gap asset is selected, and the document and all three tables fit their available widths. The thumbnail was inspected at full size and at the 360 × 203 card size. Independent review and thumbnail owner approval remain pending.
- The article schema passed. The editorial audit passed caption numbering and reported the expected missing production thumbnail and Open Graph asset while the candidate awaits approval. It also flags external source archiving as unverified. The candidate itself passed the thumbnail renderer's hard checks. The repository-wide internal-link check flagged six existing related-article references in four unrelated articles. All three body images and the calculator route were verified for this article.
- Regenerated the article registry and checked the change against its pre-task contents. The generated difference adds one draft row. No commit, push, merge, publication or deployment action was taken.

## Editorial rework after owner feedback

The original Fresh-Eyes pass was a self-review and missed two substantive issues. The case arrived after a generic definitions table, and the invitation asked readers to change the loading strategy without showing how that change affected this manifest. The revised draft follows the two cartons through the fit check, the comparison, and the booking decision. It retains the manifest restrictions, P-labels, exact color squares and the runnable preset.

The shared backend ran both modes with the same upright-only preset, via _prepare_transport_analysis, engine.pack_container and engine.summarize. Progressive Fill placed 96, leaving 14 G and 11 I (18.946 m³ placed). Progressive Fill with Mixed Cargo Infill placed 119, leaving two I (22.640 m³ placed). The 23 additional placements are calculated for this manifest.

In the second reader-only pass, the logistics-manager decision was whether to try a different placement strategy before reserving another shipment. The schematic explains why changing positions can create usable space. The authentic result identifies I/P9 and the table makes the restrictions and labels verifiable. The CTA offers the same case and an immediate test. The decision section separates what to inspect in the warehouse from what to measure during a software trial. This remains an editorial self-review. Owner review is pending.

The earlier Fresh-Eyes review failed to apply its jargon check to table headers and conflated engineering source traceability with useful reader-facing links. The revised draft uses 'Upright only' in the manifest and describes the rotation in ordinary language. It reports the observed three-carton difference in one sentence.

## Eight-section rewrite and approval record

The owner supplied an education-first outline and approved the existing thumbnail. The candidate WebP was copied byte-for-byte to the existing static path. SHA-256 B06A0D065233B453DCED30C5725D26B8645866E89E385EC2776AB7D40C6E1BD7. The existing draft URL and preset key were retained so the private preview and calculator link stay stable. The search title and primary keyword follow the outline.

- Section sequence follows the outline from the planning question through capacity measures, practical constraints, how software searches, the 20-foot case, warehouse validation, a purchasing trial and the conclusion.
- Figure 1 is the existing conceptual cross-section. Figure 2 is the data-backed setup table derived from the approved manifest table. It retains all nine color squares, P-labels, dimensions and handling rules, and shows requested quantities as inputs. Figure 3 is the existing authentic loading-view crop, with Item I placement in the caption. The original assets were reused.
- The visible case comparison reports 119 and 116 once and scopes the three-carton difference to those arrangements. Owner-confirmed upright rotation and stackability agree. Detailed vendor group-handling and other solver settings remain unspecified. The EasyCargo image is linked by source URL. No vendor image is reproduced.
- The [2021 research on practical container-loading constraints](https://doi.org/10.1016/j.cor.2020.105186) supports the discussion of group ordering, orientation, load-bearing and multiple destinations. It is retained in this record. The original load-plan figure and the CTU Code are the reader-facing sources.

Fresh-Eyes reader-only self-review used the logistics-manager persona. Opening-only check identifies the decision to rework the load or book capacity before detailed numbers appear. Scan-only check covers heading order, table headers, figure captions and CTA. Plain-language check finds no rotation codes or unexplained mathematical labels. Setup-to-results check places the exact manifest ahead of the calculated layout. Purchasing check identifies the trial baseline, what to measure and which floor checks matter. A separate independent editorial reviewer did not participate.

Rewrite verification passed the article schema, figure-number and named-case checks, and the focused public-calculator Django test. Desktop (1280 px) and mobile (390 px) visual self-review found excess line wrapping in the manifest. The correction keeps each dimension on one line and lets the table scroll within the page on mobile. The loading-view caption links to the full-size image. The authenticated local preview and draft index returned 200, and the public article route returned 404. The editorial audit still reports that external source archiving was not verified.

## Figure 1 revision after owner feedback

The replacement is an original conceptual two-row container cutaway. The rear cargo stays fixed, foreground cartons differ in height, and each panel uses the same carton geometry. The dashed blue outline shows one blocked attempt, and the solid blue carton shows the opening created by moving the front stacks. The figure emphasizes surrounding cargo, available depth and the approach to the position. Dimensions remain in the source specification and worked-example text. The diagram does not depict the verified KolliPack layout.

Source and reproducibility files are in artifacts/container-space-draft/mixed-carton-gap-fit.json and draw_mixed_carton_gaps.py. Visual self-review passed for figure fidelity and clarity in the desktop and reflowed mobile versions. Django preview rendering at 1,280 px and 390 px selected the intended assets, and both WebPs returned HTTP 200 from the private preview server. Schema, figure numbering and preset checks passed. The approved thumbnail hash still matches. The draft remains unpublished.

## Publication record · 2026-11-16

The owner authorized publication of the current preview. The article body and figure order match the approved draft. Release metadata sets published status and the publication and update dates. Production receives the prepopulated upright-only case with the exact verified rows and configuration. The article links to EasyCargo’s public source figure and reproduces no EasyCargo images.

- `mixed-carton-gap-fit.webp` SHA-256 `1954863a3131976e88e3656a52f4370a4d4f765afc31128022cf6c337dc4b857`
- `mixed-carton-gap-fit-mobile.webp` SHA-256 `05c44bdb1b3dd7af6317ba67c29b84f4e6786f313d10cd45c50a976b4fca31f7`
- `kollipack-loading-view.webp` SHA-256 `60d64f45d98b6efc90901700454b5acbe7e75b1c7c7dc786621aeb9b05fad9e8`
- `thumbnail-v1.webp` SHA-256 `b06a0d065233b453dced30c5725d26b8645866e89e385ec2776ab7d40c6e1bd7`
