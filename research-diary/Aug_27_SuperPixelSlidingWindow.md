# Development Diary: 27 August 2026

## Material Classification: Superpixel Segmentation and Sliding Window Verification

Today I continued development of the material classification pipeline,
building upon the UV island based classification system developed
previously. The previous implementation was able to isolate individual
UV islands, remove texture padding outside the valid UV geometry, rotate
islands to improve their crop efficiency, classify the resulting regions
using the trained MINC material classifier, and reconstruct the
classifications into a material ID texture.

While this produced significantly cleaner results than classifying the
complete diffuse texture, it introduced another limitation. A single UV
island does not necessarily correspond to a single physical material. In
more complex reconstructed environments, an individual UV island could
potentially contain multiple materials, such as wood adjacent to stone.
Classifying the entire island as one region could therefore cause
smaller material regions to be lost.

## Superpixel Based Segmentation

To investigate this problem, I created a new experimental classifier,
`classify-UV-Crop-SuperPixel.py`, using the existing UV crop classifier
as its starting point.

The new version introduces superpixel segmentation within the valid UV
regions. Rather than assuming that every UV island contains a single
material, the texture inside each island is divided into smaller regions
based on local visual similarity.

Several iterations were tested. The initial implementation produced a
large number of fragmented classifications, particularly across the
large fabric regions of the test sofa. Although this demonstrated that
the segmentation was capable of detecting local differences within an
island, many of these differences appeared to represent variations in
texture, lighting or noise rather than genuine changes in material.

The segmentation and merging behaviour was subsequently adjusted to
reduce these isolated false positive regions. This produced a noticeably
cleaner material ID map while retaining the ability to identify
potentially different materials within the same UV island.

## Sliding Window Verification

I then investigated using a sliding window technique as an additional
classification stage.

The purpose of this stage is to provide additional context for the
classifications generated from the superpixels. Individual superpixels
can contain relatively little visual information and may therefore
produce unstable material predictions. Sliding windows examine larger
overlapping portions of the surrounding texture and provide additional
evidence that can be used to verify or reclassify the smaller regions.

This produced another significant improvement in the test output. Many
of the isolated false classifications within the large upholstery
regions were removed, while some distinct regions remained.

The resulting pipeline is now approximately:

1.  Load the diffuse texture and UV mask.
2.  Identify valid UV islands.
3.  Remove texture padding outside the valid UV geometry.
4.  Rotate and crop regions where appropriate.
5.  Generate superpixels within valid texture regions.
6.  Classify the generated regions using the MINC based classifier.
7.  Use overlapping sliding window classifications to provide additional
    contextual evidence.
8.  Verify or reclassify questionable local predictions.
9.  Apply neighbouring region processing and merge compatible
    classifications.
10. Reconstruct the results into a material ID texture.

The latest sofa test produced a considerably cleaner result than the
initial superpixel implementation. The large upholstery regions were
classified much more consistently, while smaller differing regions were
still preserved where sufficient evidence existed.

## Parameter Tuning

The current results also identified several parameters that should
eventually be exposed for experimentation rather than being permanently
hard coded.

In particular, the target superpixel size controls how finely the
texture is initially segmented. Increasing the sensitivity could allow
smaller material boundaries to be discovered, but would also introduce
additional false positive regions.

The sliding window system provides a possible counterbalance to this. A
more sensitive superpixel stage could deliberately over segment the
texture, while the contextual sliding window stage could reject
unsupported classifications.

Future experiments will therefore investigate the relationship between
superpixel resolution and sliding window parameters such as window size,
stride, sampling density and reclassification thresholds.

## Configurable Material Classes

I also identified another potential improvement to the classifier. The
current MINC classifier considers the complete set of supported material
categories regardless of the environment being analysed.

For many environments, a large number of these classes are not
realistically possible. For example, an indoor architectural scan may
not need classes such as sky, foliage, food, hair or skin.

A future version of the web interface could therefore allow the user to
select which material classes should be considered during
classification. Presets could also be provided for different
environments, such as indoor architecture, geological or cave
environments, furniture and outdoor environments.

Rather than simply discarding unwanted classifications after inference,
the intention is to investigate restricting the probability calculation
to the selected candidate materials. The original unrestricted
predictions should still be retained for diagnostic purposes so that the
effect of this constraint can be evaluated.

## Web Interface Integration

The longer term intention is for the material classification pipeline to
run locally on my computer and be launched through the project's web
interface.

The experimental parameters currently being adjusted directly within the
Python scripts should eventually be exposed through this interface. This
would allow superpixel segmentation, sliding window behaviour,
confidence thresholds, material selection and other processing options
to be changed without modifying the classifier source code.

This would also make systematic comparison between configurations
significantly easier.

## Current Status

The UV based material classification pipeline has now progressed from
classifying entire UV islands to performing local segmentation and
contextual verification within those islands.

The current results are not yet considered final, but the combination of
UV masking, superpixel segmentation and sliding window verification
appears promising. In particular, today's experiments demonstrated that
additional segmentation sensitivity can potentially be introduced
without necessarily accepting every resulting false positive, as the
later contextual stages can remove unsupported classifications.

Further parameter tuning and testing against additional textures will be
performed later. For now, development on the classifier has been paused
with the current implementation functioning successfully and producing
useful experimental results.

## BEHOLDER Case Design and Physical Prototyping

Today I also worked on the design and early physical prototyping of the BEHOLDER enclosure. I continued developing the 3D model of the main shell in Blender, with particular attention given to how the internal electronics, cameras, lighting, and pole attachment will fit within the final assembly.

I completed several small test prints rather than printing the entire enclosure. One test was designed specifically to evaluate the attachment between BEHOLDER and the telescopic pole. This allowed me to check the physical dimensions and fit of the mounting mechanism before incorporating it into the larger shell design.

A second test print was produced to evaluate the internal compartment intended to house the Raspberry Pi and associated electronics. The purpose of this test was to verify the available space and determine how the components could be securely positioned within the enclosure. I also investigated using an accurate Raspberry Pi 5 reference model within Blender so that mounting points, screw holes, connector locations, and component clearances can be considered directly during the enclosure design.

A significant part of today's work involved considering how the BEHOLDER shell should be assembled and opened. Rather than permanently fixing the cameras and lighting into a single configuration, I want the enclosure to support interchangeable camera and light modules. The current design direction therefore uses removable panels or mounting sections that can be repositioned around the shell.

This modular approach should make it possible to experiment with different camera orientations, overlap between camera views, lighting positions, and polarization configurations without redesigning or reprinting the entire enclosure for each experiment. It also allows individual components to be removed or replaced more easily if the hardware configuration changes.

The enclosure design is therefore being treated not only as a protective housing for the electronics, but as an experimental platform that can support multiple capture configurations. The results of the initial test prints will be used to refine the dimensions and mounting mechanisms before producing larger sections of the final BEHOLDER shell.

# Bruce Caves Insurance Enquiries

I also continued preparations for potentially conducting a field capture at Bruce Caves Conservation Area. The research agreement for this location requires general liability insurance, so today I sent enquiries to three insurance providers to investigate the cost and availability of suitable coverage.

At this stage, these were enquiries only and no insurance policy has been purchased. Once I receive quotes and further information from the providers, I will assess whether the required coverage is financially reasonable. If an appropriate and affordable policy is available, I intend to purchase the necessary insurance at a future date so that the Bruce Caves fieldwork can proceed.