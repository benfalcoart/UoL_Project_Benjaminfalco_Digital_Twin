### October 3, 2026

Today I continued monitoring the large Scenic Caves reconstruction and examined the mesh that had been generated. The geometry looked promising and suggested that the dataset had produced a much more useful reconstruction than some of the earlier tests.

However, the texturing stage remains extremely demanding on the available hardware. Due to limited computer availability and the amount of processing time still required, I may need to cancel the texturing stage for this dataset, which would be unfortunate given the quality of the generated mesh.

I also continued developing the backend architecture for the web viewer using Python and FastAPI. The planned workflow allows a mesh to be uploaded from the viewer, processed by the existing `VolumeCalculator`, and returned as structured data. I also began planning improvements to the voxelisation system, including BVH-based spatial queries and adaptive subdivision to make analysis of very large meshes more practical.
