## Development Diary — September 5, 2026

### Research into Alternative 3D Scan Data

Today I focused primarily on researching the Paris Catacombs and investigating whether existing 3D scans could be used as additional test data for the system.

Collection of my own field data is currently dependent on site approvals, insurance arrangements, and scheduling research visits. Rather than allowing these external dependencies to prevent further testing, I investigated publicly available 3D scans that could provide realistic underground environments for testing the processing pipeline.

I located a collection of 3D scans of the Paris Catacombs on Sketchfab. Several potentially suitable models were captured using an iPhone 12 Pro and the Scaniverse application. These provide independently captured examples of confined and irregular underground environments that are relevant to the types of locations I intend to capture during my own fieldwork.

### Suitability for System Testing

The Catacombs models provide potentially useful external test cases for the system. Unlike clean synthetic meshes, the models contain imperfections associated with real-world scanning in difficult environments, including incomplete surfaces, holes, irregular geometry, and areas where portions of the environment were not successfully captured.

This makes the models useful as additional test data while arrangements for my own fieldwork are ongoing. They may also provide a useful opportunity to determine how well the system handles imperfect geometry produced independently of my own capture and reconstruction pipeline.

### Mesh Repair Investigation

Initial inspection of the available models identified a significant problem: many of the meshes are sparse or contain substantial holes. This could interfere with later stages of the system, particularly voxelisation and volumetric analysis.

Rather than relying entirely on existing mesh-processing software to correct these problems, I began considering an automated mesh-repair stage that could be implemented as part of my own processing pipeline.

A possible approach would involve identifying boundary edges within the triangle mesh, grouping connected boundary edges into individual holes, measuring each opening, and automatically generating replacement geometry for holes that fall within an acceptable threshold. Larger areas of missing geometry could remain unchanged where there is insufficient information to reasonably infer the missing surface.

This would address a practical problem with the external scan data while also increasing the amount of original processing functionality implemented within the project.

### Next Steps

The next step will be to download a small selection of suitable Paris Catacombs models and examine their geometry in more detail. I will then experiment with programmatically detecting open mesh boundaries and developing a basic automatic hole-filling method.

If successful, the repaired meshes can then be passed through the existing voxelisation and analysis pipeline. This will allow development and testing of the system to continue while approvals, insurance, and scheduling for original on-site data collection are finalized.

### Odesa Catacombs Research and Outreach

I also expanded my search for external underground datasets beyond the Paris Catacombs and investigated available 3D reconstructions of the Odesa Catacombs in Ukraine.

I located a downloadable scan of part of the Odesa Catacombs on Sketchfab and downloaded it as an additional potential test dataset. Like the Paris Catacombs scans identified earlier today, this provides another independently captured underground environment that may be useful for evaluating the processing pipeline against data produced outside of my own capture and reconstruction workflow.

During this research, I also discovered a substantially larger and higher-quality reconstruction of the Odesa Catacombs published on Sketchfab by the Scientific and Research Lab "Archaic". The reconstruction was produced as part of the Ukrainian Heritage Digitisation and Dissemination Initiative and appeared to represent a professional digitisation of the site.

Unlike the other Odesa model, the Archaic reconstruction was not publicly available for download. Because of its apparent quality and strong relevance to the research, I contacted Archaic directly to ask whether they would consider providing access to the 3D model or an associated research-quality dataset for use in my MSc project.

In the enquiry, I provided an overview of the project and explained that I am developing and evaluating a system for processing 3D reconstructions of underground and interior environments, including mesh processing, machine-learning-based material classification, voxelisation, volumetric analysis, and WebGL visualisation. I explained that the model would be used solely for academic research and evaluation, would not be redistributed, and that I would comply with any attribution or usage requirements.

The work being undertaken through the Ukrainian Heritage Digitisation and Dissemination Initiative is also particularly interesting from the perspective of digital heritage preservation. The preservation and documentation of cultural heritage through high-quality digital reconstruction closely relates to some of the broader motivations behind this project and provides an interesting real-world application for the technologies being investigated.

At this stage, I do not know whether access to the Archaic dataset will be possible, but I have submitted the enquiry and will continue working with the publicly available external datasets in the meantime.
