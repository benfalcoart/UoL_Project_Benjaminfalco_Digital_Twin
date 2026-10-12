# BEHOLDER — Development Diary
**Date:** Saturday, 10 October 2026  

## Overview

Today was primarily about **bringing all of BEHOLDER together**. I had spent much of the previous day and late evening working on the UV classification pipeline. The challenge today was to make its outputs usable in the rest of the application, resolve inconsistencies between several independently developed layers, and reduce the amount of experimental or obsolete code in the version I intend to submit.

BEHOLDER now spans a Raspberry Pi multi-camera image capture system, COLMAP/OpenMVS photogrammetry, Blender-based UV preparation, a Python multi-model material classifier, topology refinement, a voxel-analysis service and a Three.js web viewer. The individual parts had been developed and tested at different times. Much of today's effort involved the less visible but essential work of agreeing on file formats, naming, paths, API endpoints and UI behaviour so a reconstruction could move coherently from processed files to an interactive visualisation.

## 1. Stabilising the UV classification pipeline

I continued work on the classification pipeline that consumes the baked atlas PNGs and UV metadata produced by the reconstruction-preparation stage. I revisited the island/superpixel handling, prediction reuse and the distinction between the different material-ID outputs. The classifier has to preserve the UV layout when replacing diffuse texture colours with a discrete material palette; otherwise the viewer may load a perfectly valid PNG that is visually mapped to the wrong parts of the mesh.

I worked with the set of outputs used during debugging and refinement: `material_id_superpixel_raw.png`, `material_id_tie_preview_raw.png`, `material_id_superpixel_merged.png` and `material_id_topology_refined.png`. These represent different stages and purposes. The raw map shows initial assignments, the tie preview helps diagnose disagreement, the merged map gives a more usable region-level result, and the topology-refined map is intended to improve consistency using actual mesh connectivity. Retaining these intermediate artifacts is useful for evaluation, even though I do not want to expose every one of them in the final viewer dropdown.

I also continued narrowing the batch runner to the four main configurations—**MINC**, **MatSynth**, **DMS** and **DMS + MatSynth + MINC with soft voting**—rather than run pairwise and hard-voting variants. I wanted the three-model ensemble to run first because it is one of the key results for the dissertation. The batch runner uses the reconstruction CSV and can process the exported chunks, produce separate output directories and invoke topology refinement. Its workflow and arguments were reviewed for unattended operation; actual full-batch completion remains a separate verification step.

## 2. Making reconstruction and classification results available to the viewer

A major part of the day was improving how the Three.js viewer discovers the available models. I moved away from manually selecting local output folders and towards a **generated reconstruction catalog** (`D:\BEHOLDER\reconstructions.json`). The catalog generator, `generate_catalog.py`, scans reconstruction directories for `chunk_*.glb` files and matches those chunks with the available ML maps under the separate `superpixel` output tree.

This required agreeing on a predictable directory structure and publishing URLs for each chunk and result. The catalog records reconstruction names, chunk filenames and the corresponding material-map paths, rather than embedding the data itself. The Python ML API serves the actual GLBs and PNGs, while the JavaScript reconstruction library reads the manifest and populates the viewer dropdowns.

On the viewer side I worked with `ReconstructionLibrary.js` and `MLControls.js` so the user can choose a reconstruction, load its GLB chunks and switch between the original diffuse textures and classified overlays. The loader needs to keep chunk transforms in their shared coordinate space; automatically recentering each separate GLB would destroy the reconstruction's spatial assembly. The material maps must also use the correct glTF UV orientation, sRGB handling and texture overlay behaviour. I reviewed those details as part of making the output useful for actual visual comparison rather than just opening files.

I also worked on the viewer's model-selection and scene-management behaviour, including keeping reconstruction groups and meshes locked against unintended manipulation and maintaining useful visibility/selection controls. These usability fixes matter because the viewer is intended to demonstrate and inspect scientific results, not accidentally alter the scene while I am navigating it.

## 3. Diagnosing the HTML-instead-of-JSON failure

One particularly clear integration bug appeared when the viewer reported:

```text
Cannot load reconstruction catalog: Unexpected token '<', "<!doctype "... is not valid JSON
```

This was not a JSON formatting problem. The first character was from an HTML page returned by Vite instead of a JSON response from FastAPI. I traced the problem through the browser request, Vite's proxy configuration, the URL constructed by `ReconstructionLibrary.js`, and the route decorators in the ML `server.py` file.

The code had accumulated different conventions, including `/api/reconstructions`, `/api/machineLearning/reconstructions` and `/api/ml/reconstructions`. The voxel service already had a distinct prefix, and I decided the cleanest solution was to give machine learning its own equally explicit namespace.

The intended final routing became:

- **Voxel API:** `/api/volume...` forwarded by Vite to port **8000**.
- **Machine-learning API:** `/api/ml/...` forwarded by Vite to port **8001**.
- **ML catalog:** `/api/ml/reconstructions`.
- **GLB and PNG content:** `/api/ml/model-files/...` and `/api/ml/material-maps/...`.

I aligned the FastAPI routes, Vite proxy, reconstruction-loader request, ML controls and catalog-generated URLs around the same convention. This also highlighted an important lesson: changing a proxy path alone is insufficient if the frontend requests and URLs embedded in the manifest still point to old routes. The server and the Vite development process have to be restarted after appropriate changes, and the manifest regenerated when URL prefixes change.

I reviewed the updated implementation and test methods for checking the ML endpoint both directly and through Vite. The routing mismatch was identified and corresponding fixes were prepared; I still need to distinguish those code-level checks from a documented full-browser verification on the final machine.

## 4. Clarifying what a public ML service should allow

I had considered letting the viewer launch classification jobs through an API. The job-running code can queue a fixed four-configuration batch, log subprocess output and expose job progress. However, I do not want a public viewer or a dissertation marker to be able to start a potentially hours-long GPU processing job.

I experimented with an administrator-token approach, then decided to remove that UI and configuration complexity for the submission. The final intended behaviour is that **reading the catalog, GLB models and material-ID maps is available**, while `POST /api/ml/run` and the job-status endpoint deliberately return **HTTP 403**. The execution implementation remains in the Python code as future functionality, but the public application should be a read-only demonstration with respect to launching ML jobs.

This decision simplifies deployment and reduces the risk of an accidental request consuming the machine's computational resources. It also separates the dissertation's requirement to *display and evaluate results* from the optional convenience of remotely triggering the processing pipeline.

## 5. Consolidating the shared material palette

Another integration issue was colour consistency. The Python classifier originally contained a hard-coded dictionary of RGB values, while the viewer used `shared/material_colors.json`. If either copy changed independently, a material-ID PNG could show one colour while the viewer's legend or per-material statistics interpreted a different one.

I worked on centralising the palette so both Python and JavaScript obtain material colours from **the same JSON file**. The Python-side helper, `machine-learning/material_colors.py`, loads the shared file and converts the JSON RGB arrays into tuples compatible with the existing `MATERIAL_COLORS` lookups. The classifier and topology-refinement code can import that dictionary rather than maintaining their own copies. The viewer imports the JSON and uses it to identify colours when estimating material proportions from the output textures.

The viewer's percentages are based on **UV texture pixels**, not measured physical 3D surface area. I need to preserve that distinction when describing the visualisation in the dissertation. I also need to remember that changing the palette does not retroactively recolour PNGs already generated under an earlier palette.

## 6. Simplifying the published material-map choices

With raw, tie, merged and topology-refined maps available for every classifier configuration, the demonstration interface had become crowded. I decided that the final viewer should show **one processed map for each model or model combination**, in addition to the original texture.

I reviewed `generate_catalog.py` and adjusted the intended publication logic to prefer the **topology-refined map when a full configuration has been produced**, and otherwise fall back to the **merged material-ID map**. This choice is made for the configuration as a whole, rather than mixing map stages arbitrarily between chunks. It keeps all chunks of a displayed configuration at the same processing stage, which is easier to interpret and explain.

I also considered filtering the available configuration directories down to the final four experimental cases. The full intermediate artifacts can remain on disk for investigation, but the published manifest does not need to expose them all. This is an important separation between *data generated for debugging/evaluation* and *results selected for presentation*.

## 7. Cleaning and documenting the COLMAP/OpenMVS code

I examined the collection of photogrammetry automation tools accumulated while developing the project. Many files represent successive attempts at solving the same problem: original automated processing, masked variants, path/SUBST adjustments, different blur-ranking methods and sliding-window mask generation.

I traced the final linked chain in `automation_pipeline`: `process_scan_queue.py`, `process_scan_dual.py`, `process_scan_variant.py`, `beholder_blur_ranker_sliding_masks.py` and `analyze_beholder_masks.py`, along with the launcher scripts, queue template and README. The older `preparation_tools` implementations are valuable development history but would make a submission confusing if presented as equally current. I therefore prepared a cleaner source-only submission structure, leaving generated score CSVs, batch logs, run-specific image lists and other experimental output outside the active source tree.

I also reviewed local paths and instructions that would not transfer cleanly to another computer. A repository intended for examiners should make the **final entry points and dependencies** obvious, even if a full photogrammetry reconstruction cannot be reproduced without the external Windows tools and datasets.

## 8. Sharing the remaining ML work across two computers

To make use of remaining processing time, I began setting up the ML pipeline on Alyssa's computer. The intended division is straightforward: my computer reads the reconstruction CSV from the top, while hers reads a **reversed copy** from the bottom. This lets us process different reconstructions in parallel without retraining the models or deliberately duplicating work.

I identified the files needed by the remote worker: the batch runner, classifier, model loader, topology refiner, shared palette, CSV queue, three `.pth` checkpoints, and each selected reconstruction's baked diffuse textures, `_ml_uv.npz` metadata and `global_mesh_topology.npz`. The original camera photos, COLMAP databases and full viewer are not required for this classification stage.

Setup exposed several ordinary but time-consuming environment problems. On the secondary Windows machine, Python **3.14** initially lacked Pillow (`No module named 'PIL'`). Installing the imaging and scientific Python packages resolved that import issue. Another attempt exposed a missing **PyTorch** installation; the batch launcher reported that the classifier did not support certain CLI arguments because the classifier crashed while importing `torch` before it could print its help text. We also checked the difference between the scan-root path on my original workstation and the location used on the second computer.

The setup and parallel processing plan were substantial progress, but I am **not claiming that the secondary computer completed its overnight classification queue**. Its PyTorch/GPU environment and successful end-to-end execution still needed confirmation at the point these notes were written.

## 9. Preparing final unit tests and closing development

Having spent so much time making the layers work together, I turned back to a weakness in my evidence: much of the system has been verified by manual use, image inspection, field captures, REST/API checks and troubleshooting rather than a well-documented formal unit-test suite.

I prepared a deliberately small **five-test Vitest suite** for the web viewer. It covers transform-history behaviour, undo, redo, voxel-grid world positioning, and reconstruction-catalog loading. These are suitable unit tests because they can exercise important logic without requiring the browser to render WebGL or the actual backend services to be running. I also intend to write several tests in the other implementation layers rather than attempt an exhaustive suite this late in the project.

The five viewer tests were **prepared, not yet confirmed as passing in the final project environment**. I plan to finish the evening running and recording tests across the viewer, ML and API/voxel layers, dealing with any small failures that arise. Formal execution results and screenshots will then support the testing section of my report.

## Reflection and project status

Today was the clearest example of the difference between having individually working modules and having a usable application. Most of the problems were not new research questions; they were integration details: mismatched REST paths, inconsistent directory names, duplicated material palettes, output-file conventions, viewer controls, overcomplicated result selections and dependencies missing from a second computer.

After the work across 9 and 10 October, I feel that **the principal coding phase is substantially complete**. The viewer, material-classification pipeline, reconstruction automation and voxel-analysis layer have defined responsibilities, and the remaining issues are mainly verification, results generation and presentation rather than major new features. This is my assessment of development maturity, **not a claim that every reconstruction has finished processing or that all tests have passed**.

My priority now is to stop expanding scope. I intend to finish the evening with focused tests across the different layers, then use the rest of tonight and tomorrow for the approximately **7,000-word dissertation report**, final evaluation evidence and demonstration video. I need to document the completed system faithfully, including the computational limitations, the unfinished or unsuccessful runs and the distinction between model confidence, UV-pixel statistics and validated material accuracy.

## Immediate next steps

1. Install and verify a suitable PyTorch build on the secondary worker; confirm GPU use and that a first classification chunk actually completes.
2. Run the prepared Vitest viewer tests and targeted tests in the Python services; capture the command output and failures as evidence.
3. Verify the final viewer against its hosted catalog and material-map URLs after restarting the services and regenerating `reconstructions.json`.
4. Inspect available individual-model and ensemble maps, including topology-refined output where complete, and collect representative comparison screenshots.
5. Concentrate on the dissertation writing, limitations, evaluation and short demonstration rather than adding further major capabilities.
