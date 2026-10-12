# Development Diary – August 21, 2026

Today I focused on designing and prototyping the **camera lens/polarizer mount** for BEHOLDER. **Blender was used as the 3D modelling tool**, with the resulting models exported for slicing and 3D printing.

I initially modelled and printed a threaded lens holder intended to mount onto the camera. The first print revealed two tolerance issues. The threaded section was too large because I had created it using a Boolean operation without accounting for the clearance required for an FDM-printed thread. The opening for the polarizing lens was also slightly too tight, so I widened it to provide additional clearance for the lens.

A second version was modelled in Blender with the threaded section reduced in size. After printing and testing it, however, the fit was still too tight. Reducing the dimensions had also made the surrounding wall too thin, making further reductions to the threaded design impractical.

Rather than continuing to modify the thread, I redesigned the mounting mechanism in Blender using **two separate cylindrical components with square mounting bases**. The smaller cylinder holds the **1-inch (25.4 mm) polarizing lens** and slides inside the larger cylinder. The two square bases contain mounting holes so that they can be fastened together using screws. The lens holder also includes additional clearance above the polarizer and a retaining lip to prevent the lens from moving out of position.

To accurately position the mounting holes so that they aligned with the screw holes on the camera's PCB, I took a photograph of the camera board and **UV mapped the photograph onto the model of the camera cylinder's base in Blender**. This provided a visual reference for the physical PCB geometry. I then positioned the geometry used for the Boolean operations over the screw-hole locations visible in the mapped image and used these to cut the mounting holes into the base. This method worked very well: when the component was printed and test-fitted against the camera PCB, **the mounting holes aligned correctly with the physical screw holes**.

This approach avoids relying on a difficult-to-tune 3D-printed thread while producing a mechanically removable polarizer assembly. It should also make future adjustments, maintenance, or replacement of the polarizing lens considerably easier.

A total of **four prototype attempts** were made today, with the results of each print informing subsequent dimensional and design changes. After testing the different approaches and adjusting the tolerances, **Version 2 of the double-cylinder design was selected as the final design to move forward with**. This was based on its simplicity and to save printing material on prototyping.

## Next Steps

- Print and test the finalized V2 polarizer mount.
- Confirm the fit and retention of the polarizing lens.
- Confirm the fit of the mount against the camera.
- Test the screw-mounted two-piece assembly.
- Incorporate the completed camera/polarizer assembly into the larger BEHOLDER shell design.

## Location Research and Permission Requests

Alongside the continued development of the BEHOLDER hardware and software, I began investigating potential locations that could be used for real-world data collection and validation of the system.

I contacted the **Grey Sauble Conservation Authority (GSCA)** regarding the possibility of conducting photogrammetry at **Bruce's Caves Conservation Area**. I explained the purpose of my MSc research, the general operation of the BEHOLDER capture system, and that the equipment would be carried on a telescopic pole rather than flown using a drone as the conservation area prohibits drones. I also explained that nothing would be attached to or removed from the cave and asked whether there were particular times when the site would be less busy or any additional precautions they would recommend.

As part of the request, I offered to provide GSCA with the resulting 3D model, imagery, and approximate measurements, including estimates such as the cave's volume and dimensions, if the capture is successful. I also offered to assist with making an interactive version of the resulting 3D model available through their website if this would be useful to them.

I also researched a number of alternative field sites that could provide different environments for testing BEHOLDER. These included:

- **Queenston Quarry/Caves, Niagara-on-the-Lake** – historic cement/mining workings beneath the Niagara Escarpment. Historical sources indicate substantial underground excavation, although portions of the surviving workings are flooded. Current ownership, access permissions, historical mine plans, and the extent of the surviving workings require further investigation.
- **Flett Tunnel, Thunder Bay** – an approximately 192 m abandoned railway tunnel. Research indicated that the property is managed by Wagner Forest Management and that a permit system exists for recreational access, making this a potentially viable controlled underground test site.
- **Torrance Gypsum Mine, Brant County** – historic gypsum workings with documented flooding and instability around the entrances. Current ownership and permission requirements still need to be established.
- **Rat's Nest Cave, Alberta** – a substantial natural cave that could provide an excellent dataset but would require controlled access and considerable travel and tour expenses.
- **Troy W.I. Hall / Old Troy School** – an 1878 schoolhouse that could provide a useful historic-building dataset if permission can be obtained from the Troy Women's Institute.

I expanded this research to include additional historic buildings around Niagara that could potentially be documented with BEHOLDER. Candidate sites now include **The Brown Homestead, Nelles Manor Museum, McFarland House, Laura Secord Homestead, Mackenzie Printery, Salem Chapel BME Church, Fry Family House, Old Fort Erie, Fort George National Historic Site, and Butler's Barracks National Historic Site**.

Historic buildings are particularly interesting as additional validation environments because they present different reconstruction challenges from both a controlled modern interior and a natural cave. They can contain complex geometry, furniture, narrow spaces, windows, reflective surfaces, machinery, stairs, and other features that may affect photogrammetric reconstruction.

One potential difficulty identified with museums and public historic sites is visitor traffic. Moving people and obstructed surfaces could negatively affect image capture and reconstruction. When approaching these organizations, I therefore plan to ask whether data collection could be scheduled during quieter periods or, where appropriate, outside normal public hours.

A **BEHOLDER Field Sites spreadsheet** was created to track candidate locations, environment type, access and permission status, expected logistical difficulties, research priority, and additional notes. This will be maintained as potential sites are investigated and organizations are contacted.

The emerging validation strategy is to test BEHOLDER progressively across substantially different environments rather than relying on a single dataset. Initial testing can be performed in a controlled indoor environment, followed by natural caves, historic interiors, tunnels, or other underground environments where appropriate permissions and safe access can be obtained.