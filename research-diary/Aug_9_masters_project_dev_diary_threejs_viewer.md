# Development Diary – August 9, 2026

While waiting for the Raspberry Pi hardware required for the image-acquisition portion of the project, the development shifted temporarily to the front-end visualization system.

The repository was organized conceptually into separate stages:

``` text
Digital Twin Project
├── viewer/
├── drone/
├── machine-learning/
├── reconstruction/
└── shared/
```

The intended overall pipeline is:

``` text
Drone / Pi or Manual Capture Rig
        ↓
Image Dataset
        ↓
COLMAP / OpenMVS Reconstruction
        ↓
Machine Learning Material Classification
        ↓
Voxelization Measurements
        ↓
Three.js Digital Twin Viewer
```

The viewer is deliberately independent of the image-capture platform and
offline processing pipeline. Its responsibility is to display processed
reconstruction data and visualize it interactively.

The viewer will use Javascript and be delivered with the Vite Package.

------------------------------------------------------------------------

## 4. Initial Three.js Scene

The first viewer prototype consisted of:

-   A Three.js scene
-   Perspective camera
-   WebGL renderer
-   OrbitControls
-   Ambient lighting
-   Directional lighting
-   Ground grid
-   Test cube
-   Responsive resizing

A test cube and grid were used to verify rendering and camera controls.

------------------------------------------------------------------------

## 5. Loading Meshes From the Local Computer

A **Load Mesh** button was added to the page. The browser file input is
hidden and triggered by the button:

The initial loader supported GLB/GLTF using `GLTFLoader`.

Support was subsequently expanded to include:

-   `.glb`
-   `.gltf`
-   `.obj`
-   `.ply`


The selected file extension determines which loader is used.

For PLY files, the geometry is manually wrapped in a Three.js mesh.
Vertex colours are preserved where available.

This is useful because PLY is likely to be relevant to the
reconstruction pipeline and may contain reconstructed geometry or
point/vertex colour information.

------------------------------------------------------------------------

## 6. Viewer Interface

A simple toolbar was created on the left side of the viewer.

It contains:

-   Load Mesh button
-   Minimum voxel-size slider
-   Maximum voxel-size slider

A Scene Explorer was placed separately on the right side.

An HTML nesting problem temporarily caused the Scene Explorer to appear
on the left. It was accidentally contained inside the toolbar:

------------------------------------------------------------------------

## 7. Voxel Resolution Controls

Two voxel-resolution parameters were added:

-   **Minimum Voxel Size**
-   **Maximum Voxel Size**

The intention is to support adaptive voxelization.

Large, relatively simple regions can eventually use coarse voxels, while
areas near edges or geometric detail can recursively use smaller voxels.

Conceptually:

``` text
Maximum voxel size
        ↓
┌─────────────────┐
│                 │
│   coarse area   │
│           ┌─────┤
│           │fine │ ← Minimum voxel size
└───────────┴─────┘
```

The minimum voxel size is clamped so that it cannot exceed the maximum
voxel size.

Both sliders update the voxel-grid visualization dynamically.

------------------------------------------------------------------------

## 8. Custom Voxel Grid Generation

A reusable function was created to generate rectangular grid geometry in
any of the three primary planes.

The function builds the grid manually using pairs of vertices.

Passing the color into the function allows the same grid-generation
logic to be reused for multiple voxel resolutions.

------------------------------------------------------------------------

## 9. Grid Bounds

The loaded meshes are traversed and combined into a single Three.js
bounding box.

This allows the voxel visualization to automatically resize around the
geometry rather than requiring fixed dimensions.

------------------------------------------------------------------------

## 10. Minimum and Maximum Voxel Grid Overlays

The grid system was expanded to visualize both ends of the adaptive
voxel-resolution range simultaneously.

Both grids were adjusted to use the **same padding**, ensuring that they
represent different resolutions over the same spatial region.

The minimum value was also clamped against the maximum value so an
invalid state such as:

``` text
Min voxel size = 0.20
Max voxel size = 0.10
```

cannot occur.

------------------------------------------------------------------------

## 11. Current Viewer State

At the end of this development session, the viewer supports:

-   Interactive Three.js 3D rendering
-   Orbit, pan and zoom controls
-   Local model selection
-   GLB loading
-   GLTF loading
-   OBJ loading
-   PLY loading
-   PLY vertex-colour support
-   Scene Explorer
-   Automatic mesh bounding-box calculation
-   Dynamic voxel-grid sizing
-   Minimum voxel-resolution control
-   Maximum voxel-resolution control
-   Minimum/maximum value clamping
-   Overlayed minimum and maximum voxel grids
-   Separate grid colours
-   Shared voxel-grid spatial bounds/padding
-   Floor, back and side voxel-grid visualization

------------------------------------------------------------------------

## 12. Adaptive Voxelization --- Planned Work

The current grids visualize the **upper and lower voxel-size limits**
only. They do not yet perform adaptive voxelization.

The planned system will begin with the maximum voxel size and subdivide
regions requiring additional geometric accuracy.

Conceptually:

``` text
                 Coarse voxel
                      │
              Geometry complex?
                /           \
              No             Yes
              │               │
            Keep          Subdivide
                           / | | \
                          ■  ■ ■  ■
                              │
                        Test further
```

Potential subdivision criteria include:

-   Proximity to mesh edges
-   Surface-normal variation
-   Curvature
-   Geometric occupancy
-   Material boundaries
-   Classification boundaries

Subdivision will stop when either:

1.  sufficient geometric accuracy has been reached, or...
2.  the minimum voxel size has been reached.

------------------------------------------------------------------------

## 13. Offline Processing Architecture

The machine-learning and reconstruction stages will operate offline
rather than through the web application.

The intended separation is:

``` text
OFFLINE PROCESSING

Captured Images
      ↓
COLMAP / OpenMVS
      ↓
Reconstructed Geometry
      ↓
ML Material Classification
      ↓
Adaptive Voxelization
      ↓
Processed Output Files


VIEWER

Processed Output Files
      ↓
Three.js
      ↓
Interactive Digital Twin
```

This prevents reconstruction and machine-learning runtime from affecting
viewer responsiveness.

------------------------------------------------------------------------

## 14. Planned Synthetic ML Testing

Before sufficient real-world image data is available, game environments or assets
can be used as controlled synthetic test scenes.

These environments can provide known materials and known geometry,
allowing the ML and processing pipeline to be developed independently of
the Raspberry Pi acquisition system.

Initial test materials may include:

``` text
Stone
Wood
Metal
Concrete
Vegetation
```

Testing can progressively introduce more difficult conditions:

``` text
Clean textures / strong lighting
            ↓
Similar-looking materials
            ↓
Shadows
            ↓
Low illumination
            ↓
Noisy or irregular textures
            ↓
Cave-like surfaces
```

Useful performance measurements include:

``` text
Input image count
Image resolution
Mesh / point count
Inference time
Memory usage
Number of classified regions
Classification accuracy
Voxelization time
Output size
```

The immediate goal is not necessarily high classification accuracy, but
to establish an end-to-end pipeline whose individual components can
subsequently be improved.

------------------------------------------------------------------------

## 15. Capture Platform Contingency

The original acquisition design uses a Raspberry Pi-based multi-camera
system mounted to a drone.

Because the intended cave field sites may prohibit UAV operation, the
proposal includes a contingency in which the same imaging payload can be
mounted on a telescopic pole.

This preserves the core processing pipeline:

``` text
Capture Platform
      ↓
Pi + Cameras
      ↓
Images
      ↓
Reconstruction
      ↓
ML
      ↓
Voxelization
      ↓
Viewer
```

Only the mechanism used to position the imaging payload changes.

Permission will still be requested from the relevant park authorities
for UAV-based research. Any correspondence can be retained as evidence
of the regulatory/site constraints and included in the dissertation
appendix if appropriate.

------------------------------------------------------------------------

## 16. Next Development Steps

Immediate planned work is:

1.  Configure the Raspberry Pi and camera hardware.
2.  Verify multi-camera image acquisition and local storage.
3.  Establish a repeatable image-transfer workflow.
4.  Capture an initial controlled dataset.
5.  Test reconstruction using COLMAP/OpenMVS.
6.  Create synthetic game-environment datasets for ML pipeline testing.
7.  Establish the material-classification output format.
8.  Implement adaptive voxel subdivision.
9.  Connect processed voxel/material data to the Three.js viewer.
10. Conduct field tests using the drone where permitted, otherwise the
    telescopic-pole capture platform.

The viewer is now sufficiently developed to act as an independent
visualization component while the acquisition and offline processing
stages are developed in parallel.
