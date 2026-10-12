# Development Diary — September 14, 2026

## Beholder Enclosure — Top Shell and Rear Door

Today I continued fabrication and assembly testing of the Beholder capture system. The main focus was printing the **top shell and rear door** of the enclosure and beginning a proper test fit with the previously completed components.

The printed parts fit together reasonably well overall. There is a small issue with the **slots and tabs designed to align the upper and lower shells**. When the two halves are assembled, something in this interface appears to prevent them from sitting completely flush, leaving a small gap between the shells. The issue is minor and does not currently appear to compromise the overall design, but the slot/tab geometry will need to be inspected before deciding whether it warrants a revision.

Several important mechanical aspects of the enclosure were successfully validated:

- The **Raspberry Pi 5 fits correctly inside the enclosure**.
- The Pi's mounting holes align correctly and it can be screwed securely into place.
- The **carriage bolts used to join the upper and lower shells work as intended**.
- The rear door was successfully printed and test fitted with the enclosure.

One practical assembly issue became apparent during testing. Some of the carriage bolts are embedded deeply enough within the enclosure that they are difficult or impossible to reach comfortably by hand. I will therefore need to design and print a **small tightening tool** that can reach into these recessed areas and allow the bolts/nuts to be tightened properly.

Overall, the physical design appears to be approaching a functional assembled state. The remaining issues discovered today are relatively minor compared with validating that the major components, mounting points, and shell-fastening system actually fit.

## Material Classification Experiment Design

A significant portion of today was also spent developing the experimental methodology for the MSc project, particularly how the existing material-classification pipeline could be expanded into a more rigorous comparison of different ways of obtaining material evidence.

The existing **traditional photogrammetry pipeline will remain the baseline**. This is important because it provides a complete and already-established route from captured photographs through reconstructed geometry and texture to machine-learning material classification.

The current experimental concept is to hold as much of the reconstruction and evaluation environment constant as possible — including the original photographs, COLMAP camera solution, final mesh, UV layout and resolution, material classifier, material classes, evaluation regions, and ground truth — while changing the method used to obtain the visual evidence supplied to the classifier.

Three independent material-identification approaches are currently envisioned:

**Method A — Traditional Photogrammetric Texture**

The conventional photogrammetry workflow produces a textured mesh. The texture/UV regions are processed by the existing material-classification system to produce **Material ID Map A**.

This serves as the experimental baseline.

**Method B — Gaussian-Splat-Derived Appearance**

A Gaussian Splat representation would be generated from the same capture data. The appearance represented by the splats would then be rendered or baked back onto the same UV-mapped evaluation mesh.

This produces **Material ID Map B** and creates a way to investigate whether Gaussian Splatting preserves material appearance differently or more effectively than the conventional photogrammetric texture-generation process.

**Method C — Direct Multi-View Image Classification**

Rather than relying on a reconstructed texture, overlapping regions from the original source photographs would be classified directly using the existing **ResNet18 classifier and its 23-class probability output**.

Using the COLMAP camera poses, these classifications could then be projected onto the mesh. Occluded or invalid observations would be rejected, while classifications from multiple valid camera views would be aggregated.

This would produce **Material ID Map C** without requiring either the conventional photogrammetric texture or a Gaussian-derived texture as the primary ML input.

A later **Method D** may investigate probability-level fusion between approaches, initially using something simple such as 50/50 probability averaging. However, fusion should only be investigated after the independent methods are functioning and can be evaluated separately.

## Comparison and Agreement Mapping

Because each method ultimately produces a material classification aligned with the same mesh and UV space, their outputs can be compared spatially.

The intended output is therefore not simply a collection of classification accuracy numbers. Each reconstruction can potentially provide several aligned material maps:

- Traditional photogrammetry material ID map
- Gaussian-derived material ID map
- Direct multi-view material ID map
- Optional fused material ID map
- Ground-truth material map
- Agreement heatmap
- Confidence and spatial-error information

The **agreement heatmap** is particularly promising as a visualization tool. Rather than attempting to create an awkward four-dimensional comparison, each point or texel can be assigned an agreement score based on how many methods produce the same material label.

A simple discrete visualization could represent complete agreement as white and progressively lower agreement as darker values, down to black for complete disagreement.

Importantly, **agreement is not the same thing as accuracy**. Several classifiers can agree and still be wrong. Ground-truth labels therefore remain necessary so that agreement between methods and actual classification accuracy can both be measured independently.

This should make it possible to answer more interesting questions than simply asking which method has the highest overall classification accuracy. The experiments may reveal *where* different reconstruction techniques succeed or fail, whether particular material types benefit from one representation, and whether combining multiple evidence pathways improves classification reliability.

## Current Direction

Today's work helped bring both halves of the project closer together.

On the hardware side, the Beholder enclosure is now reaching the point where the Raspberry Pi and major shell components can be physically assembled and secured. The remaining fit issue with the shell tabs appears minor, and the need for a specialized tightening tool is straightforward to address.

On the research side, the material-identification component is developing from a single classification pipeline into a controlled comparative experiment. The existing photogrammetric classifier remains the required baseline, while Gaussian-derived appearance and direct multi-view classification can be introduced as experimental extensions.

The next major software priority is to establish the **shared geometry, UV layout, ground truth, evaluation system, and baseline Method A output** before introducing additional methods.

For Gaussian Splatting specifically, the immediate goal should be a small feasibility prototype: determine whether Gaussian-derived appearance can be reliably rendered or baked onto the shared evaluation mesh. If that works, it becomes a viable second experimental pathway rather than simply an interesting visualization technique.

Overall, September 14 represented progress in both the **physical construction of the Beholder** and the **experimental design that will determine how its captured data is ultimately evaluated**.