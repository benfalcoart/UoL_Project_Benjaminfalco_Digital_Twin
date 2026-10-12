# Dev Diary --- August 26, 2026

## MINC Training and UV Material Classification Pipeline

Today I focused primarily on developing and testing the Machine Learning
material classification component of the project. The goal was to
determine whether training a material classifier using the MINC dataset
was practical on my available hardware and, if successful, begin
integrating the classifier into the 3D reconstruction workflow.

I began by setting up the MINC 2500 dataset for use with PyTorch and
confirmed that CUDA acceleration was available using my NVIDIA RTX 2070
SUPER. I initially created a benchmark to determine whether training
times would be practical within the remaining project schedule. The
benchmark showed that training was substantially faster than I had
anticipated, eliminating one of my major concerns about the feasibility
of this part of the project.

I then trained a ResNet18 based classifier using transfer learning on
the MINC dataset. Initial training produced moderate results, after
which I adjusted the training approach to allow greater fine tuning of
the pretrained network. The resulting model achieved a best validation
accuracy of **74.37%**. I subsequently evaluated the saved model against
the held out test set of 5,750 images, where it achieved **75.41%
accuracy**. This provided a useful baseline measurement for the material
classification component.

I created a separate classification script and tested the trained model
against external images that were not part of the MINC dataset. The
classifier successfully identified several obvious materials, including
stone, water, ceramic, glass, brick and plastic. Other materials,
particularly wood, metal and painted surfaces, demonstrated that the
classifier still has limitations when applied to images outside the
training distribution.

I then began adapting the classifier specifically for the project's UV
texture workflow. Rather than classifying an entire UV texture atlas as
a single image, I experimented with dividing the atlas spatially and
classifying individual regions. This led to the development of a UV
aware classification pipeline using a separately generated UV mask.

An important problem discovered during testing was that baked UV
textures frequently contain stretched or dilated texture information
outside the actual UV islands. These pixels significantly affected
classification results even though they are not actually mapped onto the
model. Initial experiments masking these areas with white or black
backgrounds also influenced the classifier and were therefore
unsuitable.

I subsequently changed the approach so that the UV mask is used to
identify individual UV islands and isolate valid texture regions. The
classifier now searches for clean rectangular regions contained within
the valid UV area rather than replacing invalid pixels with an
artificial colour. I also added rotation based preprocessing using the
geometry of the UV island. This allows irregular or diagonal UV islands
to be rotated when doing so produces a larger clean classification
sample. Rotation is only accepted when it provides a meaningful
improvement, and it does not modify the original UV coordinates.

The pipeline now performs the following process:

**Diffuse UV texture → UV mask → UV island detection → geometry aware
cropping → optional rotation → ResNet18 material classification →
Material ID texture generation**

I successfully tested the complete pipeline on a sofa model. Eight UV
islands were detected and classified independently. Several
classifications were particularly strong, including separate wooden
regions classified as wood with **99.06%** and **99.54% confidence**.
Other regions demonstrated limitations of the current classifier, with
some upholstery being classified as painted, wallpaper or carpet. These
results suggest that the UV segmentation and mapping process is
functioning correctly, while semantic material classification remains an
area that could potentially be improved.

Finally, I generated a colour coded Material ID texture from the
classification results and applied it back onto the original 3D sofa
model. The generated texture correctly follows the UV islands and
therefore maps the predicted material regions back onto the
corresponding portions of the 3D geometry. This represents the first
successful end to end test of the planned ML material classification
workflow.

The current implementation will now be preserved as a working baseline.
My next development step will be to clean and document the classifier
code before conducting further tests against additional artificial
environments and, eventually, reconstructed photogrammetry data.

In addition to the technical work today, I also heard back from
**Dr. Martin Harris regarding the insurance requirement for field data
collection**. The insurance requirement had arisen while arranging
potential research access to Bruce's Caves Conservation Area. I will
continue addressing the administrative requirements for field testing
alongside development of the capture and analysis pipeline.

Overall, today's work substantially reduced the technical risk
surrounding the Machine Learning portion of the project. Training the
classifier is computationally practical on my available hardware, the
model can classify external material samples, and the complete UV based
workflow can now generate a Material ID map and project the
classifications back onto a 3D model.
