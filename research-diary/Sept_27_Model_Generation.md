# Development Log — 27 September 2026

## Focus

Today I concentrated on turning BEHOLDER image captures into usable 3D models. I tested COLMAP and OpenMVS on the Niagara Railway Museum and basement datasets, investigated weak reconstructions, refined image masking, and assembled an automated queue to process several projects while I collect more field data.

## COLMAP and OpenMVS experiments

The first rail-car reconstruction established that the complete workflow could produce a textured model. COLMAP registered **1,507 of 3,294** selected images and generated **80,199 sparse points**. The recovered rail-car shape was coherent enough to continue into OpenMVS. An OpenMVS develop build produced a textured GLB that opened in Blender. Its appearance was only moderately successful, but this capture was among the poorer image sets, so it served as a useful proof of the processing path rather than a final quality benchmark.

Other attempts showed how variable the results can be. Increasing sequential matching overlap to 100 did not rescue the Rail Car 4 dataset: its largest sparse component registered **220 of 4,513** selected images (about **4.9%**) across 15 models. An earlier masked basement attempt was also highly fragmented, with a largest component of **49 of 5,509** images. The pipeline's sparse-model check correctly stopped these weak reconstructions before the much more expensive OpenMVS stages. These failures reinforced that image count alone does not guarantee enough sharp, overlapping observations for a connected model.

## Mesh detail and decimation

I discovered that I had misunderstood the `TextureMesh --decimate` value. I had treated **0.25** as a modest 25% reduction; in this workflow it retains approximately **25%** of the mesh and removes roughly **75%**. One run reduced about **2.03 million** eligible faces to roughly **508,000** before further cleanup. This helps explain why its textured model looked softer and less detailed than I expected.

I revised the automation to attempt texturing at **1.00** first, retaining the full available mesh, and to retry at **0.90, 0.80,** and lower values down to **0.10** if an attempt fails. I am hopeful that a higher retained fraction will improve geometric detail in the final GLB. That remains a hypothesis until the new outputs are finished and compared; image quality, registration, and texture projection will also affect the result.

## Masking and automated processing

The preprocessing workflow now uses sliding-window Laplacian analysis to generate a separate feature mask for each photograph. White regions remain available to COLMAP; black regions are excluded. Images classified as `KEEP` or `REVIEW` can enter reconstruction, while completely black `SKIP` images are omitted. The originals are preserved.

For the **7,425-image basement-dark dataset**, the run at a sharpness threshold of **40** generated all masks: **3,414 KEEP**, **1,708 REVIEW**, and **2,303 SKIP**. Mask analysis found **5,122 images** with at least some usable area, while only about **28% of pixels** across the masks remained white. After inspecting the strictness of the masks, I chose to lower the local sharpness threshold to **30** for the next pass. The resulting mask distribution and reconstruction quality have not yet been measured.

I also built a sequential project queue that runs both a masked and an unmasked-but-filtered reconstruction for each scan. It records per-stage logs and resume state, attempts the full mesh before reducing detail, and places the large COLMAP/OpenMVS workspaces under **`D:\BEHOLDER_Processing`** to relieve pressure on the source drive. Both variants retain the same selected image set so their outputs can be compared.

The first automated basement run completed mask generation and statistics but both variants stopped before COLMAP because Python 3.14 rejected an unescaped percent sign in a command-line help string. I corrected the help text and prepared a revised bundle. This was a script startup error, not a failed COLMAP reconstruction; no model result should be inferred from that run.

## Status and next steps

I have left the corrected processing queue running overnight. Its high-detail texturing attempts and masked-versus-unmasked outputs remain **pending**, so I will check the logs, successful decimation values, registration counts, and visual quality before drawing conclusions. I will also monitor disk space as the workspaces accumulate.

On **28 September**, I plan to scan at **Scenic Caves Nature Adventures** while the existing datasets process. The reconstruction setbacks have shifted my capture priorities toward steadier images, usable lighting, and dependable overlap rather than simply collecting the largest possible number of photographs. The new field data will provide another test of whether those changes improve registration and final model quality.
