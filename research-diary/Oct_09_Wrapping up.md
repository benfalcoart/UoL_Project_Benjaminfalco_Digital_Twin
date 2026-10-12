# BEHOLDER — Development Diary
**Date:** Friday, 9 October 2026  
**Project:** University of London MSc Computer Science — BEHOLDER Digital Twin  
**Primary focus:** Bringing the UV texture-classification pipeline together; multi-model evaluation, automation and debugging  
**Work period:** Daytime and evening, continuing into a late-night development session

## Overview

Today became a substantial implementation and integration day rather than the short testing-and-writing session I had originally envisaged. My main objective was to turn the individual parts of the material-classification research into a practical pipeline that I could run against complete photogrammetry reconstructions. I spent much of the day, and continued working late into the night, dealing with the transition from trained image classifiers to material-ID textures that can be applied back onto reconstructed 3D geometry.

The earlier reconstruction and UV preparation work had already produced chunked mesh exports, baked diffuse texture atlases and geometry/UV metadata. The problem now was getting these products through the machine-learning stages consistently, comparing the models fairly, and producing outputs that would eventually be usable inside the Three.js viewer. This was one of the final major pieces required to connect capture, reconstruction, material classification and visualisation into a single system.

## 1. Preparing the three-model material-classification comparison

I worked on the evaluation setup for the three separately trained ResNet18 material classifiers: **MINC**, **MatSynth** and **DMS**. The MatSynth data preparation had involved a troublesome Hugging Face download, including unavailable Parquet shards; by this stage I had progressed to training and using the MatSynth model rather than spending more time collecting data. I wanted the classifiers to remain independent so that I could compare what each learned from its source dataset.

The important design decision was **not to retrain a new combined neural network**. Instead, I investigated combining the predictions of the three existing models. In soft voting, their class probabilities can be mapped into a common output space and averaged to determine the final material label. This approach preserves each model as an independent experiment and allows a direct comparison of single-model results against the ensemble.

During the initial evaluation planning I considered the three single models, three pairwise combinations and an all-three ensemble. I also explored soft voting, hard voting and ways of showing classifier disagreement. As the implementation developed, it became clear that running every variation over every UV chunk would be computationally expensive and would generate an unnecessarily large collection of nearly identical results. I began narrowing the final demonstrable comparison to **four configurations: MINC, MatSynth, DMS and the three-model soft-voting ensemble**. I also chose to prioritise the combined ensemble rather than spend limited processing time on all pairwise variants.

Because these are reconstructions of real environments and I do not have authoritative per-surface ground-truth annotations, the planned evaluation relies principally on visual inspection of the generated material-ID maps, comparisons with the original diffuse textures, and examination of the maps on the reconstructed meshes. I need to be careful in the dissertation not to describe model confidence as proof of correct classification.

## 2. Integrating UV atlases with classification

A major part of the work was refining the route from the exported UV information to actual classifier inputs. A photogrammetry texture atlas contains many disconnected UV islands, blank regions and sometimes unrelated pieces of the scene close together in image space. Passing an entire atlas directly to an ordinary image classifier would make it difficult to associate predictions with physical surfaces.

I worked through the existing classifier, `classify-UV-crop-superpixel-sliding-window.py`, and the metadata exported by the Blender preparation stage. The workflow needs to identify which parts of the atlas correspond to valid UV coverage, isolate useful image patches, classify the visual content and convert the results back into a material-ID texture aligned with the original UV layout. It must avoid treating blank atlas background as a material and must keep the atlas pixel coordinates consistent with the geometry that uses them.

I brought together the UV-island and masking logic, geometry-aware patch extraction and superpixel/region processing so that predictions could be assigned to local areas rather than one label for an entire object or atlas. Sliding windows and superpixels were particularly useful here: material changes do not necessarily coincide with UV island boundaries, and a single island can contain more than one visible material. I also revisited crop orientation and the relationship between UV coordinates, texture pixels and reconstructed mesh faces.

The target outputs were not merely numerical class predictions. I needed **material-ID PNGs** whose pixels retain their exact positions in the atlas, together with metadata describing the classified regions and labels. Those maps would subsequently be used as overlays in the viewer, allowing the same piece of geometry to be viewed with the original photographed texture or an ML-generated material classification.

## 3. Prediction caching and repeatable experiments

Running three ResNet18 models repeatedly over the same texture crops is wasteful when the objective is to compare different ensemble strategies. I therefore worked on prediction reuse and the SQLite-backed cache used by the classification workflow (`machine-learning/outputs/prediction_cache.sqlite`). The intent is to perform the expensive underlying inference once for a given model and input, and then reuse those outputs while constructing alternative material maps or voting combinations.

This required thinking about cache identity and invalidation. Reusing an old prediction is safe only if the model, source texture and relevant crop information still match. I considered the risk of cached results silently becoming stale when the baked texture or processing settings change, and the value of comparing cached and uncached output to catch errors. The late-night work involved refining this inference-to-output pipeline rather than merely adding more models to a loop.

I also worked on handling classification disagreements and uncertain regions. A tie or disagreement preview is useful as diagnostic evidence, but I do not want to mistake such an image for the final presentable classification. I distinguished intermediate **raw** material-ID maps from **merged** maps and the later **topology-refined** output.

## 4. Adding mesh-aware reasoning after image classification

Another important limitation is that a texture atlas is a two-dimensional packing of surfaces that may be neighbours in three-dimensional space but far apart in the atlas. Conversely, two patches adjacent in the PNG may belong to unrelated parts of the scene. Purely image-space smoothing cannot reliably address those relationships.

I examined the possibility of using the exported global mesh topology to refine classifications after the initial superpixel step. The UV processing stage has access to mesh information, including shared edges, face membership and surface normals. A separate topology pass can therefore consider whether regions meet across real mesh edges, rather than treating every contact in texture space as a physical connection. This led to the `mesh_topology_refine.py` workflow and the use of `global_mesh_topology.npz` as supporting data.

The intended sequence is deliberately two-pass: first generate the original per-model and ensemble classifications, then optionally produce a topology-refined map while retaining the original intermediate maps. Preserving the pre-refinement output is important both for troubleshooting and for evaluating how much the geometry-aware correction changes the result. At this point, the implementation and integration work was the achievement; I still needed completed batch runs to judge its effectiveness on all reconstructions.

## 5. Moving from individual experiments to batch automation

I reviewed the CSV-driven batch-processing setup, particularly `batch_classify_uv_chunks.py`, with the goal of processing multiple reconstructions unattended. A single reconstruction may contain numerous UV chunks, each with a baked diffuse PNG and associated `_ml_uv.npz` data. The batch runner must discover the chunks, call the classifier with the selected models and voting method, manage output folders, and optionally run the topology stage afterwards.

I wanted the runs to be restartable because processing complete scene collections will take many hours. Skipping already completed results and sharing cached model predictions are important practical features for this project, particularly given my limited available GPU time. I also needed clear output directories separating reconstructions and classifier configurations so that later visual comparison would not be confused by filenames or overwritten outputs.

I continued reviewing the resource limits exposed by earlier photogrammetry work, including the unsuccessful attempt to run the approximately **17,000-image** COLMAP/OpenMVS dataset on an available workstation. That failure was not a UV-classification result, but it reinforced why automation, partial-result preservation and realistic experimental scope matter. I distinguished the older Ivy workstation from the other machines when reviewing that processing history.

## 6. Integration issues, decisions and remaining verification

This was a day of repeated small adjustments: getting the Python command-line interfaces to agree, checking file naming and folder conventions, aligning UV data with material textures, managing alternate prediction outputs and ensuring the individual models and combined ensemble followed the same pipeline. Much of the effort went into making previously separate components behave as **one reproducible workflow**, rather than developing a completely new classifier from scratch.

By the end of the session, I had a much clearer final architecture for the ML layer:

1. Load the baked diffuse atlas and UV/mesh metadata for each reconstruction chunk.
2. Identify valid textured regions and create image patches/superpixels.
3. Obtain predictions from the trained MINC, MatSynth and DMS models, reusing cached inference where possible.
4. Generate individual material-ID maps and a three-model soft-voting map.
5. Optionally perform mesh-topology refinement on those outputs.
6. Publish the chosen maps for inspection against the original textures in the viewer.

I regard this as significant progress towards completing the code, but **I am not recording unexecuted overnight batches or proposed topology improvements as validated experimental results**. Those still require actual processing output, inspection and test evidence.

## Reflection

The main difficulty was not training one more network; it was building the bridge between photographic textures, machine-learning predictions, mesh geometry and visual interpretation. I spent far longer on the UV pipeline and integration than originally planned, but this work is essential to the dissertation's contribution. Without it, I would have three classification models and a set of reconstructed meshes, but no practical way to associate predictions with the surface of a digital twin.

The workload also forced a useful prioritisation decision. Rather than expand into every possible ensemble combination, I will focus on the three individual classifiers and their combined soft ensemble, explain the method clearly, and evaluate the results I can actually produce.

## Next steps

- Continue testing the atlas/superpixel/cache/refinement path on complete reconstruction chunks and investigate any failures.
- Connect the processed GLBs and material-ID maps to the web viewer, with reliable loading and clear configuration names.
- Obtain full processing results where time and hardware permit; do not report incomplete runs as finished.
- Add targeted unit tests for the ML and viewer layers and preserve command output as evidence.
- Finish the dissertation report and short demonstration video before submission.
