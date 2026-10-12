# Development Diary — 22 September 2026

## Continuing After Midnight

This entry covers work that continued past midnight following the 21 September development session. By then, the basic BEHOLDER workflow was functioning: the MAUI application could communicate with the Raspberry Pi, control capture, display live status, and offload project files. The focus shifted to refactoring the API and its client contract, then checking how the assembled system behaved during sustained automatic capture.

## Python API Refactor

I worked through the Python `server.py` API to make the available operations more complete and consistent. The refactor addressed missing project, camera, and transfer endpoints and moved the relevant commands toward requests that carry their parameters in the request body. This gives the MAUI client a clearer contract for operations that need a project name, camera identifier, slot assignment, or transfer path.

Project handling gained lookup and close operations in the project manager, along with routes for retrieving the current project and working with existing projects. Camera handling gained lookup, slot assignment, and an identification operation that can return a temporary JPEG from the selected camera. The slot assignment logic is intended to prevent two cameras from occupying the same logical slot.

I also brought the transfer manifest and individual-file routes into the refactored API. A requested file path is checked against the project directory so the file endpoint cannot be used to escape the intended transfer area. Error handling and the status update loop were strengthened so an individual failure is less likely to disrupt ongoing status reporting.

This work was primarily about making the backend easier to maintain and ensuring that the API exposes the functions the application already needs. The camera identification and persistence behaviour still require further device testing.

## MAUI API Contract

I updated the MAUI endpoint definitions to match the backend changes. The endpoint enum and JSON configuration now account for operations such as retrieving or closing the current project, assigning a camera slot, identifying a camera, and requesting transfer manifests or files. Capture mode changes use the shared capture-mode route.

The all-project offload flow can first retrieve the project list, then reuse the existing per-project transfer service for each project. This keeps the transfer logic in one place rather than creating a second implementation for bulk offloading. Updated Python API files were copied to `/home/bfalco/beholder/API` on the Pi with SCP for testing against the running device.

Some integration work remains in the MAUI interface. In particular, the diagnostic Console navigation should be made a top-level tab, and the transfer and camera flows need broader testing on an Android device.

## Automatic Capture Endurance Test

I continued the automatic capture battery test with all five cameras active. After approximately **42 minutes**, BEHOLDER had completed **1,970 five-camera capture cycles**, or roughly **9,850 individual images**. The battery indicator showed about **84%** at that point. I stopped the test close to the one-hour mark, when the reported charge was approximately **80%**.

The early battery readings moved around enough that a short sample was misleading. Across the longer run, the displayed charge dropped by roughly 20 percentage points in about an hour. That suggests a *rough* five-hour runtime per battery set under this capture pattern, but it is an extrapolation, not a measured full-discharge result. Battery percentage, workload, and the lower end of the discharge curve could all change the actual field runtime.

The Raspberry Pi temperature remained around **45 °C** during sustained capture. This is a useful early sign that the active cooler and enclosure are handling the present workload. With four complete battery sets available, the initial runtime result is encouraging for the planned field sessions, provided battery swapping is practical.

The 18650 cells were difficult to remove from the UPS holder and required some prying. I plan to place a short length of non-conductive nylon ribbon beneath the cells when reinstalling them, allowing the ribbon to act as a pull tab during field swaps.

## End-of-Day State and Next Steps

The core capture-to-offload workflow now works as an integrated system, and today's work made the API contract more complete. The endurance run produced useful real-world numbers: nearly 10,000 images in about 42 minutes, approximately 80% battery remaining near one hour, and a Pi temperature around 45 °C.

The next development session should focus on cleaning up the MAUI Console navigation, validating the application and transfers on Android, testing a larger all-project offload, checking whether camera settings persist as intended, and rehearsing the complete field workflow. The battery estimate should also be treated as provisional until a longer discharge test is completed.
