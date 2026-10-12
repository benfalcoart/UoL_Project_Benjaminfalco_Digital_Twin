# Development Diary – 7 September 2026

## Odesa Catacombs Research Dataset

Today I received a response from Dr Simon Radchenko, Co-founder and Project Director of the Scientific and Research Lab "Archaic", regarding my request to use their digitisation of the Odesa Catacombs as an external dataset for my MSc research.

Archaic provided access to the research-quality "master" reconstruction of the Odesa Catacombs produced through the Ukrainian Heritage Digitisation and Dissemination Initiative. Permission was granted to use the model for non-commercial purposes, provided that Archaic and the Ukrainian Heritage Digitisation and Dissemination Initiative are appropriately credited.

The dataset was successfully downloaded and archived locally.

The supplied model consists of:

- Wavefront OBJ geometry
- MTL material definition
- Three diffuse texture maps
- Approximately 47.8 million vertices
- Approximately 95.7 million faces
- Approximately 10 GB of model data

The OBJ header identifies the reconstruction as having been generated using RealityScan 2.1.1.

This represents a particularly valuable addition to the research because it provides a large, independently captured and reconstructed dataset against which the processing pipeline can be evaluated. Until now, much of the planned evaluation has centred on datasets captured using the BEHOLDER system. The Odesa dataset provides an opportunity to determine whether the processing pipeline generalises to a reconstruction produced independently using different equipment and workflows.

## Initial Model Evaluation

An initial attempt was made to load the complete model into Blender.

The model could be opened successfully in Object Mode, although system performance was significantly affected. Attempting to enter Edit Mode caused Blender and the wider operating system to become effectively unresponsive due to the size and complexity of the mesh.

This demonstrated that the research-quality model cannot practically be manipulated directly using the normal interactive Blender workflow on the current workstation.

Rather than modifying the original dataset, it was decided that the master model should remain unchanged and act as the high-resolution source from which derived processing and visualisation models can be produced.

## OBJ Structure Investigation

A small Python utility was created to inspect the OBJ without loading the entire file into memory. The program streamed through the file line-by-line and located representative texture-coordinate, group, material and face definitions.

The model was found to contain:

- XYZ vertex positions
- Per-vertex RGB colour information
- UV texture coordinates
- Material assignments
- Triangular faces
- A single default OBJ group

A representative face uses the following indexing structure:

`f 1/1 2/2 3/3`

This indicates separate vertex and texture-coordinate references without explicitly stored normal indices.

The single `g default` group also indicates that the reconstruction was not exported as conveniently separable spatial sections. Consequently, spatial subdivision will need to be performed as part of the preprocessing pipeline.

## Material and Texture Structure

The supplied MTL file was also examined.

Three diffuse materials are defined:

- `catacombs__u1_v1`
- `catacombs__u2_v1`
- `catacombs__u1_v2`

Each references a corresponding diffuse JPEG texture. The structure resembles a tiled/UDIM-style texture arrangement exported through standard OBJ material definitions.

The original photogrammetry UV layout is not particularly suitable for the existing machine-learning material-classification pipeline because photogrammetric reconstruction commonly produces highly fragmented UV islands.

As a result, preserving the original UV topology on the final processing model is not required. Instead, the original textured reconstruction can be retained as a high-resolution source from which appearance information is transferred to a newly generated UV layout.

## Proposed Large-Mesh Processing Pipeline

A revised processing strategy was established for the Odesa dataset.

The original 95.7-million-face model will first be spatially subdivided using a custom streaming Python tool. This avoids requiring Blender to load and manipulate the complete reconstruction interactively.

The intended workflow is:

**Original RealityScan Model → Spatial Chunking → Mesh Simplification → New UV Layout → High-to-Low Texture Baking → Material Classification → Voxelisation → WebGL Visualisation**

The initial spatial subdivision will preserve the original geometry, vertex colours, UV coordinates and material assignments for each high-resolution chunk.

Individual chunks can then be processed independently in Blender. This should allow the original high-resolution chunk to act as the source while a duplicated mesh is simplified to produce a lower-resolution representation.

The lower-resolution mesh can then receive a new UV unwrap. Diffuse appearance from the original RealityScan textures can subsequently be baked from the high-resolution source onto the new UV layout. Normal maps may also be generated to retain small-scale geometric appearance while allowing substantial geometric simplification.

This approach should produce models that are significantly more suitable for both the machine-learning pipeline and WebGL visualisation while retaining the original master reconstruction for research reference.

Full manual retopology is not currently considered necessary. Geometry-preserving decimation followed by UV regeneration and texture baking should be sufficient for the requirements of material classification, voxelisation and browser-based visualisation.

## FAIR Research Data Principles

Archaic also indicated that a complete dataset exceeding 200 GB exists for the Odesa reconstruction and described it as a FAIR dataset.

This prompted an investigation of the FAIR Guiding Principles:

- **Findable**
- **Accessible**
- **Interoperable**
- **Reusable**

The complete Odesa dataset is not required for this project, and no request will be made for its transfer. The research-quality master model already provides the required independent evaluation dataset.

However, the FAIR principles align closely with the data-management approach already planned for this MSc project. As a result, the project's research-data management will be structured with reference to FAIR principles.

In particular, datasets should retain:

- Stable dataset identifiers
- Source and creator information
- Capture metadata
- Processing parameters
- Software and model versions
- Standardized file formats
- Relationships between source and derived artifacts
- Attribution and licensing information
- Machine-readable metadata where practical
- Documentation sufficient to understand and reproduce processing stages

A standardized directory structure will also be considered for datasets, separating raw capture data, reconstruction outputs, mesh processing, classification results, voxelisation outputs and visualisation assets.

For externally sourced datasets such as the Odesa Catacombs, provenance information will clearly distinguish the original dataset creators from derived artifacts produced through this research.

Rather than claiming complete FAIR compliance, the dissertation will describe the project's research-data management as being **informed by the FAIR Guiding Principles**.

## Next Steps

The next technical task is to develop the streaming spatial OBJ subdivision utility.

Before subdivision, the tool will determine the complete spatial bounds of the Odesa reconstruction. Appropriate chunk dimensions can then be selected based on both physical dimensions and approximate face density.

The initial target will be to produce high-resolution chunks small enough to be comfortably manipulated in Blender, potentially containing approximately 1–3 million faces each.

Once spatial subdivision is working, a Blender automation pipeline will be investigated for:

1. Importing individual high-resolution chunks.
2. Generating simplified copies.
3. Creating new UV layouts.
4. Baking diffuse appearance from the high-resolution source.
5. Potentially baking normal maps.
6. Exporting processed GLB models for the WebGL viewer.

The Odesa dataset therefore provides not only an independent evaluation dataset, but also a valuable scalability test for the overall processing architecture.