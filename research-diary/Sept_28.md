# Development Diary — September 28, 2026

Today was primarily a fieldwork and processing day, with the first successful capture of a genuine cave environment using the BEHOLDER system.

I had originally planned to arrive at Scenic Caves Nature Adventures at approximately 9:00 AM, but I overslept and did not arrive until approximately 11:00 AM. Despite the delayed start, I was still able to spend several hours on site collecting data. The staff were accommodating, and I was able to bring the BEHOLDER system into the cave areas and capture several datasets.

Most importantly, I successfully captured an actual cave environment. This represents an important milestone for the project, as much of the development and testing up to this point has used indoor environments, artificial test scenes, the basement, or museum objects. The Scenic Caves dataset provides material that is much closer to the original intended application of the project: reconstructing irregular underground environments.

The fieldwork also provided another opportunity to evaluate the BEHOLDER hardware under real operating conditions. The system continued to hold up well despite transportation, extended use, uneven terrain, and the more difficult lighting conditions found around the caves. The long telescopic pole and handheld configuration both gave me options for capturing viewpoints that would otherwise have been difficult to reach.

There was also a small but memorable moment while I was walking through the forest with BEHOLDER mounted on the telescopic pole. The pole was fully collapsed, but the complete system was still approximately six feet tall. Another visitor walking along the trail called out, “Nice wizard staff!” This made me smile because I had jokingly described the BEHOLDER pole in almost exactly the same way during development a few weeks earlier. It was a minor moment, but it was amusing to see that the improvised appearance of the system was apparently immediately recognizable to someone else as well.

At approximately 2:00 PM, I temporarily stopped fieldwork to attend a remote Niagara College meeting from the parking lot. I was able to connect using the site's Wi-Fi and then continued the fieldwork afterward.

The new datasets have not yet been processed, but they will be added to the automated reconstruction pipeline once the currently queued datasets have completed.

## Reconstruction Pipeline Progress

While I was away conducting fieldwork, the COLMAP/OpenMVS automated processing pipeline continued running at home. This was useful because the computer was able to spend the entire field day performing reconstruction work without requiring much manual intervention.

Both versions of the basement dataset have now progressed through the pipeline:

- the original/unmasked dataset;
- the masked dataset.

The pipeline subsequently began processing the blue car dataset captured at the Niagara Railway Museum.

One useful observation today concerned the difference between the size of the dense reconstruction data and the final GLB output. The GLB files are substantially smaller than the intermediate dense reconstruction files. This initially appeared concerning, but it is consistent with the export and mesh-processing stages, particularly where geometry is decimated before being converted into a format intended for interactive viewing.

Reviewing the previous pipeline configuration also highlighted that a decimation ratio of approximately `0.25` had been used in some processing stages. This retains approximately 25% of the original geometry and therefore represents roughly a 75% reduction in polygon count. This likely explains some of the poorer visual quality I observed in earlier generated models.

This is an important finding because the earlier decimation settings were primarily introduced to prevent memory failures during later processing stages. The next iterations of the pipeline should therefore attempt to preserve substantially more geometry. A better strategy may be to initially attempt processing the full-resolution mesh and only introduce progressive decimation if the operation fails because of memory limitations. For example, the system could retry using increasingly aggressive reductions rather than immediately reducing every model to 25% of its geometry.

Although this will increase processing time, this is acceptable for the project. High-quality reconstruction is more important than quickly generating a model, particularly because processing can occur unattended while I am conducting fieldwork or performing other tasks.

## Human Detection and Privacy Masking

The Scenic Caves fieldwork also revealed another issue that needs to be considered in the preprocessing pipeline. Because Scenic Caves remained open to the public while I was collecting images, people occasionally moved through the capture areas. I attempted to avoid deliberately photographing visitors, but it is possible that individuals appear incidentally in some of the images.

This is especially relevant because the project's ethics documentation states that I would attempt to avoid capturing identifiable members of the public and would remove photographs containing people where necessary.

Rather than manually reviewing several thousand images, I began considering an automated human-detection stage as part of the preprocessing pipeline.

A practical implementation would use an existing pretrained segmentation model to detect people within each captured photograph and generate a corresponding binary person mask. This mask could remain separate from the existing image-quality masks used to remove blurred or otherwise unsuitable regions.

The preprocessing process could therefore maintain several mask types, for example:

- blur or image-quality masks;
- human/privacy masks;
- a final combined reconstruction mask.

The masks could then be combined immediately before the COLMAP/OpenMVS reconstruction stages.

There is also the possibility of modifying the stored image itself so that detected people are permanently removed or obscured while retaining the associated mask as evidence of what was excluded. This could provide a more robust privacy workflow than simply relying on COLMAP to ignore masked image regions.

An automated workflow might therefore operate as follows:

1. Import the original BEHOLDER photographs.
2. Detect people using a pretrained segmentation model.
3. Generate and retain a human segmentation mask.
4. Remove or permanently obscure the corresponding pixels in the working image.
5. Generate the existing blur/image-quality mask.
6. Combine the individual masks into the final reconstruction mask.
7. Submit only the sanitized photographs and combined masks to the reconstruction pipeline.

This would allow privacy protection to become a repeatable preprocessing step rather than relying entirely on manual inspection. It would also make the handling of incidental human subjects more explicit and auditable within the project methodology.

I think this would be a worthwhile addition if it can be implemented without significantly disrupting the existing pipeline. It is not necessary to develop a new machine-learning model for this purpose; an existing pretrained person-segmentation model should be sufficient.

## Reflection

Today represented an important transition from development and controlled testing toward genuine field deployment. The BEHOLDER system has now been used to capture a real cave environment, while the reconstruction pipeline has continued processing previously collected datasets independently.

At the same time, fieldwork is exposing practical problems that were difficult to anticipate during development. Incidental capture of visitors, reconstruction memory requirements, aggressive mesh decimation, difficult lighting, and the sheer quantity of generated data are all influencing how the final system should operate.

These issues are useful rather than purely negative. They demonstrate why testing the complete system outside controlled environments is necessary.

The next major step is to allow the current reconstruction queue to finish and then process the Scenic Caves datasets. Seeing whether COLMAP and OpenMVS can successfully reconstruct the cave imagery will be one of the most important tests of the project so far.
