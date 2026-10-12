# Development Diary — October 1, 2026

Today I continued working on both the photogrammetry processing pipeline and the Three.js Digital Twin viewer.

## Additional Processing Capacity and Pipeline Automation

I set up an older computer as a **third machine for processing COLMAP/OpenMVS reconstructions**. Since this system has older and weaker hardware than the other machines I am currently using, I assigned it some of the smaller scan datasets rather than the larger collections.

I also modified the **photogrammetry pipeline automation code to be machine-agnostic**. The processing scripts are no longer tied as closely to the configuration or paths of a specific computer, making it much easier to move unfinished or queued reconstruction work between systems.

This is particularly important because I will lose access to the more powerful processing computer on Sunday. With the updated automation, I should be able to transfer its remaining workload to one of the other machines with significantly less setup and continue processing without having to rebuild the workflow for each computer.

This gives me three systems that can currently process different captures in parallel, while also making the overall reconstruction pipeline more portable and resilient to changes in available hardware.

## Digital Twin Viewer — Object Selection and Transformation

I returned to development of the Three.js Digital Twin viewer and began adding more editor-like functionality.

The first major addition was **object selection**. Objects in the Scene Explorer can now be selected, establishing a selected object that other editing tools can operate on.

I also integrated Three.js `TransformControls`, providing familiar 3D manipulation gizmos. Selected objects can now be:

- moved
- rotated
- scaled

Keyboard shortcuts were also introduced to make switching between these tools quicker:

- `W` — Move
- `E` — Rotate
- `R` — Scale
- `Esc` — Deselect

This functionality is an important prerequisite for the planned voxel bounding-region system, since those regions will need to be positioned, rotated and resized interactively within the scene.

## Voxel Grid Bounds Fix

Adding the transform gizmo exposed an issue with the existing voxel grid visualization.

Because the TransformControls helper is itself added to the Three.js scene, the voxel bounding calculation began detecting geometry belonging to the gizmo. This resulted in extremely large bounding dimensions and caused the voxel grid to extend effectively indefinitely, eventually overwhelming the browser.

I modified the voxel-bound calculation so that editor/helper geometry is excluded.

The bounds are now intended to be calculated from the actual visible mesh geometry in the scene rather than every renderable object indiscriminately. This also lays useful groundwork for future editor objects such as voxel bounding regions, which should influence voxelization deliberately rather than accidentally being treated as scanned geometry.

## Undo / Redo System

I also began adding an **undo/redo history system** for object transformations.

The current design stores the object's transform before a gizmo operation begins. When the user finishes moving, rotating or scaling the object, the previous transform is added to an undo history.

The intended controls are:

- `Ctrl + Z` — Undo
- `Ctrl + Y` — Redo
- `Ctrl + Shift + Z` — Redo

Importantly, an entire gizmo drag is treated as a single operation rather than recording every tiny movement while the mouse is being dragged.

This history system can later be extended beyond transforms to support actions such as creating, deleting and duplicating voxel regions.

## Next Steps

The viewer is gradually changing from a passive model viewer into a small interactive scene editor.

The next major feature will be the **Voxel Region** system. These regions will be independently positioned and transformed bounding volumes that define where voxel generation is allowed to occur. Multiple regions will be permitted and may overlap.

The intended voxelization process will begin near the centre of each region and expand toward its boundaries, stopping where expansion encounters mesh geometry. The transform and selection tools developed today provide the foundation needed to begin implementing that system.
