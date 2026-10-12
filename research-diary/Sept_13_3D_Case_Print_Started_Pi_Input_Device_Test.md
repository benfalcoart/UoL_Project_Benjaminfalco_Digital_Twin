# Beholder Dev Diary — September 13, 2026

## Summary

Today focused on completing the Beholder enclosure model, validating its mechanical layout, troubleshooting the main enclosure print, configuring a USB remote trigger on the Raspberry Pi, and planning the next round of field-site outreach. The main printing failure was ultimately traced to a non-flat underside rather than ordinary build-plate adhesion.

## 3D model and mechanical validation

- Finished positioning the camera openings and screw holes on the Beholder enclosure.
- Printed smaller test sections to verify the placement of the camera and screw openings.
- Confirmed that the test pieces aligned correctly.
- Imported the Raspberry Pi STEP model into a separate Blender file because the complex STEP import was slow and caused the main project to become unresponsive.
- Planned to convert the imported board model to OBJ for easier use in the enclosure scene.

## Main enclosure print preparation

- Prepared the large enclosure base in Bambu Studio for the Bambu Lab A1.
- Used a 45° support threshold as a conservative starting point.
- Reduced initial-layer speeds to improve adhesion:
  - Initial layer: 20 mm/s
  - Initial-layer infill: 25 mm/s, later reduced to approximately 15 mm/s while diagnosing the failure
- Discovered that the filament profile was set to Generic PLA rather than the matching Bambu PLA profile.
- Switching to the Bambu PLA profile reduced the estimated print time by approximately 2.5 hours because the tuned profile permits higher normal-layer flow and speed.
- The sliced print was estimated at approximately 231 g including supports.
- The black spool appeared to have only approximately 200 g remaining, so a mid-print spool change may be required. White and blue PLA were identified as possible continuation colours, potentially producing an intentional accent band or blue racing stripe.

## First-layer failure investigation

### Initial symptoms

- Tree-support bases adhered to the textured PEI plate successfully.
- The enclosure outline repeatedly lifted when the printer began filling the base.
- Black PLA appeared less consistent than the blue PLA used for the smaller successful test pieces.
- Retesting with blue improved the result but did not eliminate the lifting, indicating that filament behaviour was not the primary cause.
- Considered cleaning the plate, increasing initial nozzle or bed temperature, adding a zero-gap brim, lowering the initial-layer speed, and testing the Concentric bottom-surface pattern.

### Root cause

- Inspected Layer 1 in Bambu Studio instead of judging the model only from the Prepare view.
- Layer 1 contained only the dark circular tree-support bases; the enclosure itself did not have meaningful contact with the build plate.
- The bottom of the source mesh was not flat. The enclosure outline and vent region began on later layers, after Bambu Studio had already switched to normal-layer speeds and the normal-layer bed temperature.
- This explained why changing first-layer settings initially appeared to have no effect on the vents or enclosure floor.
- The printer was effectively attempting to establish a wide portion of the enclosure above the build plate, allowing fill lines to catch and pull up the weak outline.

### Attempted and final solutions

- Tried Bambu Studio's Lay on Face operation, but the first-layer preview still showed the enclosure suspended above the plate.
- Considered flattening the lower vertices in Blender using `S Z 0`.
- Attempted a Boolean cut in Blender, but the model was too complex and the Boolean produced only an unwanted intersection edge.
- Flipping the enclosure upside down greatly increased the required supports and material waste, so that orientation was rejected.
- Moved the mesh slightly below the Bambu Studio build plate. The slicer clipped the uneven lower geometry at Z = 0 and generated a flat printable cross-section.
- Verified that Layer 1 now contained the complete enclosure base rather than only the tree-support footprints.
- Restarted the print in black PLA. The corrected version printed substantially better, although the complete first layer moved slowly as intended.

## Raspberry Pi remote trigger

- Connected a HAS HS304 USB input device to the Raspberry Pi host `BEHOLDER`.
- Used `evtest` to identify its Linux input devices:
  - `/dev/input/event5`: HAS HAS HS304 Keyboard
  - `/dev/input/event6`: HAS HAS HS304 mouse/interface device
- Confirmed the keyboard interface reported USB vendor `0x2571` and product `0x4101`.
- Tested a Python input-monitoring script successfully.
- Verified that the remote produces distinct events for UP pressed, UP released, DOWN pressed, and DOWN released.
- Confirmed the stable device link: `/dev/input/by-id/usb-HAS_HAS_HS304-event-kbd -> ../event5`.
- The stable `/dev/input/by-id/` path should be used by the capture software instead of relying on an event number that may change after rebooting or reconnecting hardware.
- Next step: copy the Python script from the Pi to the Windows development machine over SCP/SSH and integrate the input events with the capture workflow.

## Ethernet transfer dock

### Completed physical preparation

- Purchased a male-to-female Ethernet extension cable.
- Cut an access opening in the Beholder's rear door for the cable.

### Ideas

- The current idea is to expose the Raspberry Pi's Ethernet connection through the rear door so the enclosure does not need to be opened for routine data access.
- The connection could become a quick docking option for transferring captured photographs to a laptop and eventually clearing local storage between capture sessions.
- Direct Pi-to-laptop networking has not yet been configured or tested.
- The cable has not yet been documented as mounted, strain-relieved, or validated for rear-door clearance.
- Transfer speed, reliability, copy verification, and any automated storage-clearing procedure remain future work.

## Fieldwork planning

- Goal: complete printing and assemble the full Beholder by tomorrow.
- Plan to send follow-up emails to potential field locations tonight and begin booking concrete capture dates.
- Hold off on scheduling Scenic Caves until the insurance situation is clearer.
- Bruce's Caves remains dependent on obtaining $5 million commercial general liability coverage naming GSCA as an additional insured on a primary basis.
- Give the insurance contact through Monday to respond, follow up again if necessary, and make a go/no-go decision by Wednesday.
- If Bruce's Caves cannot be confirmed, redirect the remaining project time toward available locations and controlled baseline captures rather than allowing one site to block the project.
- Relevant outreach targets include Morningstar Mill, Niagara Railway Museum, The Brown Homestead, and Tintern Church of Christ.

## Next steps

- Monitor the corrected black enclosure print through the first several layers.
- Replace the filament mid-print if the remaining black PLA runs out.
- Complete the remaining enclosure components and assemble the Beholder.
- Verify camera fit, screw alignment, airflow, Raspberry Pi clearance, lighting, power, and cable routing.
- Integrate the HAS HS304 remote events into the capture program.
- Install and secure the Ethernet extension in the rear-door opening.
- Configure and test direct Ethernet photo transfer between the Beholder and the Windows laptop.
- Run a complete local capture test before travelling to a field location.
- Send field-site follow-ups and establish a firm schedule for the remaining September capture window.
