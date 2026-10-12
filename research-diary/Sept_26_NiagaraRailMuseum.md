# Development Diary — 26 September 2026

## Niagara Railway Museum Fieldwork

Today was the first major public field deployment of **BEHOLDER**. I took the completed five-camera Raspberry Pi photogrammetry rig to the **Niagara Railway Museum** and spent approximately **four hours scanning museum objects and rolling stock**.

The visit acted both as genuine data collection for the MSc project and as a practical stress test of the complete system outside the controlled home environment. I captured multiple rail cars and other museum objects, including a tank and railway signal equipment.

Across the museum projects, BEHOLDER captured more than **21,000 images**, representing roughly **4,000+ five-camera capture events**. This was the first time the system had been used for an extended real-world capture session at this scale.

The field session confirmed that the physical rig was usable for sustained scanning. The Raspberry Pi, five cameras, battery system, physical clicker, hotspot, and MAUI control application all remained usable throughout the visit.

## MAUI Application Observations

Using the MAUI application extensively in the field exposed several **quality-of-life improvements** that I would like to make before future scanning sessions. These are not major architectural problems, but small usability issues became more obvious when operating the system repeatedly while moving around a real site.

The previously observed Android connection/disconnection issue **still occurred in the field**. However, the contingency work completed before the visit proved effective:

- REST/HTTP communication remained available even when the persistent WebSocket connection became unreliable.
- The dashboard continued to receive BEHOLDER status information using periodic HTTP polling.
- Reconnecting the application restored the connection when necessary.
- The connection issue did not prevent the fieldwork from continuing.

This was an important result because it showed that the fallback design was sufficient for real field use. The WebSocket issue still warrants investigation, but it is no longer a critical blocker for data collection.

## Initial Image Review

After returning from the museum, I began reviewing the captured photographs.

The dataset contains a mixture of good and poor images. Some photographs show noticeable motion blur, while others appear sharp and usable. The volume of imagery also makes manual inspection impractical, so an automated preprocessing step is necessary before reconstruction.

Rather than deleting any original captures, I decided to preserve the complete raw dataset and generate a filtered list of images to use during reconstruction.

## Blur Detection and Dataset Filtering

I used a Python preprocessing tool based on **variance of the Laplacian** to calculate a sharpness score for each image.

The script records the result for every photograph in a CSV file. Images below a selected sharpness threshold can then be excluded from reconstruction without altering or deleting the original data.

For the first reconstruction test I focused on the **rail car 3** dataset:

- Original images: **5,385**
- Images retained after blur filtering: **3,294**
- Selected sharpness threshold: approximately **44.95**

The threshold was chosen through visual inspection of ranked images. This is being treated as a screening metric rather than an absolute definition of image quality, because high-contrast or overexposed images can sometimes receive deceptively high Laplacian scores.

The retained image list was then sorted back into capture order and split into separate files for **CAM01–CAM05**.

## COLMAP Setup and Feature Extraction

I installed and began testing **COLMAP 4.2.0** using the filtered rail car dataset.

Because BEHOLDER contains five physically separate cameras, I did not want COLMAP to incorrectly treat every image as coming from a single camera. The accepted images were therefore divided by camera, and feature extraction was performed separately for each camera while writing into the same COLMAP database.

The five physical cameras were configured using the `SIMPLE_RADIAL` camera model.

The Windows CUDA build of COLMAP initially failed to detect the RTX 2070 SUPER even though the GPU was visible to Windows and `nvidia-smi`. To avoid blocking the reconstruction work, SIFT feature extraction and matching were switched to CPU processing.

CPU feature extraction worked successfully. For example, CAM01 processed all **687 accepted images** in approximately two minutes and produced thousands of SIFT features for most photographs.

## Feature Matching and Sparse Reconstruction

After feature extraction was completed for the camera groups, I ran COLMAP's **sequential matcher**.

Sequential matching is appropriate for the BEHOLDER dataset because the image filenames preserve the capture sequence. The matcher compares images against nearby photographs in the sequence instead of exhaustively comparing every possible pair.

Once matching completed, I started the COLMAP **mapper** to construct the sparse Structure-from-Motion reconstruction.

The mapper was still running at the end of the day and was left processing overnight. The final reconstruction results will therefore be evaluated in the next diary entry.

## End-of-Day Status

By the end of 26 September:

- BEHOLDER had completed its first major public field session.
- Approximately four hours of scanning were completed at the Niagara Railway Museum.
- More than 21,000 museum images were collected.
- The Android WebSocket disconnection issue still occurred, but the HTTP polling/reconnection fallback worked successfully in real field conditions.
- Several MAUI quality-of-life improvements were identified for future development.
- The raw imagery was preserved while a reproducible blur-filtering workflow was introduced.
- The first major dataset was reduced from 5,385 to 3,294 candidate images for reconstruction.
- COLMAP feature extraction and feature matching were completed.
- Sparse reconstruction mapping was started and left running overnight.

The day was an important transition from system development into genuine field data collection. The hardware and software were sufficiently reliable to complete the museum scan, and the focus can now begin shifting toward reconstruction quality, processing automation, and refinement of the field workflow.
