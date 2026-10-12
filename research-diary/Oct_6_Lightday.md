# October 6, 2026

Today was a relatively light project day because of work obligations, but I still made useful progress diagnosing the remaining problems in the automated UV-processing workflow.

I started the day by checking the overnight UV-unwrapping batch and quickly realized that several of my own reconstructed photogrammetry models were not processing fast enough. The downloaded reference models had completed in a reasonable amount of time, while some of my generated meshes were taking hours or appearing likely to run for days. I investigated the geometry and found that the main difference was polygon count: several of my reconstructions were still extremely high-poly.

I manually cleaned the affected meshes in Blender, merging loose or duplicate vertices where appropriate and applying controlled Collapse decimation to reduce the triangle counts while visually checking that the models retained acceptable reconstruction quality. I then restarted the established automated chunking, xatlas, UVPackmaster, baking, and ML-topology pipeline using the reduced meshes.

The Birch Log model completed successfully through the entire pipeline in roughly two hours, confirming that the workflow itself was still functional when the source geometry was kept to a manageable size. However, the Blue Car and Rail Car models failed during UVPackmaster processing. Reviewing the logs showed that both exported meshes were still much larger than intended: Blue Car contained roughly 7.2 million triangles and Rail Car roughly 6.85 million. This suggested that I had either not applied the decimation modifier correctly, had not exported the reduced result, or had simply underestimated how large the meshes still were. I plan to reduce both further before trying them again.

The Tree model also completed successfully, but inspection of its generated UV textures revealed another problem. Although the unwrap technically succeeded, the result was heavily fragmented into very small UV islands. The mesh statistics strongly suggest that the photogrammetry GLB is effectively being exported as disconnected or nearly disconnected triangle geometry. The Tree model contained approximately 1.72 million vertices for 574,598 triangles, which is very close to three unique vertices per triangle, and the topology export found only a handful of shared-edge adjacency links. Several chunks also produced almost one UV island per face.

This likely explains both the poor UV layouts and some of the performance issues seen with my generated scans. The geometry appears visually continuous, but much of it is not topologically connected by shared vertex IDs. The next step will be to test a very small Merge by Distance / weld operation before xatlas so that coincident vertices can be reconnected without materially altering the reconstructed surface. If successful, this should reduce UV fragmentation and make the exported topology much more useful for the later ML material-classification stage.

Overall, today was primarily a troubleshooting and cleanup day. I did not complete as much implementation work as on previous days because of teaching/work commitments, but I was able to identify two important bottlenecks: excessive polygon counts in several reconstructed meshes and disconnected triangle topology in the exported photogrammetry geometry.

## Next Steps

- Correctly decimate Blue Car and Rail Car to a more manageable triangle count and verify the exported GLBs before rerunning them.
- Test a very small Merge by Distance / weld threshold on one photogrammetry model.
- Compare UV chart/island counts before and after welding.
- Rerun the UV pipeline on the cleaned meshes once topology is improved.
- Continue validating the generated topology data before moving on to the ML material-classification stage.
