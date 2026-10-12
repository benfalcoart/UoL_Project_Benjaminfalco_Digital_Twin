# Development Diary — September 29, 2026

Today was primarily focused on refining the automated photogrammetry processing pipeline and preparing to process the large amount of data collected during the Scenic Caves fieldwork.

I made several tweaks to the automated COLMAP/OpenMVS workflow to make it easier to process collections with less manual intervention. The goal is increasingly to be able to provide the pipeline with a collection of images and allow it to work through feature extraction, matching, reconstruction, dense processing, meshing, texturing, and export automatically. I also continued refining how different processing options are handled so that failed stages can be retried with more conservative settings rather than requiring the entire process to be restarted manually.

One significant improvement was gaining access to a second, more powerful computer that I can use alongside my primary workstation. I transferred the processing scripts, COLMAP, OpenMVS, and the Scenic Caves image collections to this system and configured it to use GPU acceleration where possible. With several large Scenic Caves collections still needing reconstruction, having a second machine available should substantially increase the amount of processing I can complete in parallel.

I also spent some time examining the models that had completed processing from my earlier basement scans and the Niagara Railway Museum fieldwork. Unfortunately, the initial results were not particularly encouraging. Several of the reconstructed models showed poor geometry, missing areas, distortion, or generally lower visual quality than I had hoped for.

This was disappointing, particularly given the amount of effort that has gone into designing and building the BEHOLDER capture system and collecting the datasets. However, these results are also useful evidence. They are highlighting weaknesses in the current capture methodology, reconstruction settings, and environmental conditions that need to be examined rather than hidden.

The automated workflow itself is becoming substantially more capable, which means I can now iterate on reconstruction parameters much more quickly than when I was manually running each stage. The additional processing computer should also allow me to test more of the Scenic Caves datasets without tying up a single workstation for days at a time.

At this stage, the priority is to process the Scenic Caves collections and determine whether the more structured field captures produce stronger reconstructions. Regardless of the final visual quality, the differences between successful and unsuccessful captures should provide useful material for evaluating the limitations of the system and identifying improvements for future versions of the BEHOLDER platform.
