# Development Diary — 25–26 September 2026

## Final Field Preparation

Development over the last two days focused on getting BEHOLDER from a functional prototype into a physically assembled field system that can be taken to the Niagara Railway Museum.

This period involved a mixture of camera-control work, MAUI interface development, physical assembly, optical testing, Android deployment, networking tests, and last-minute debugging of the mobile status system.

By the end of the session, BEHOLDER was fully assembled and the Android application could reliably communicate with it in the field using HTTP requests over the dedicated BEHOLDER Wi-Fi network.

---

## Camera Control Integration

I expanded the Raspberry Pi camera system so that the USB cameras can be configured through the existing FastAPI and MAUI architecture rather than relying entirely on their automatic defaults.

The cameras expose a useful set of V4L2 controls, including:

```text
Brightness
Contrast
Saturation
Hue
Automatic white balance
White balance temperature
Gamma
Gain
Power-line frequency
Sharpness
Backlight compensation
Automatic exposure
Exposure time
Dynamic frame rate
```

The `CameraManager` was extended with functions for reading and writing these controls using `v4l2-ctl`.

The implementation supports both individual-camera access and applying the same setting across all cameras. Since BEHOLDER currently operates the five cameras as a coordinated capture system, the application uses the global configuration approach.

A bug was encountered when reading controls such as `auto_exposure` because V4L2 returns additional descriptive text:

```text
auto_exposure: 3 (Aperture Priority Mode)
```

The parser was corrected so that only the numeric portion is converted to an integer.

Hardware testing confirmed that camera settings could be read, modified, and restored successfully.

## Camera Profiles

A camera-profile system was added so that groups of settings can be stored and quickly restored in the field.

Profiles are stored as JSON on the Raspberry Pi and contain values for all supported camera controls.

Example structure:

```json
{
    "name": "Bright Interior",
    "description": "",
    "settings": {
        "brightness": 0,
        "contrast": 32,
        "saturation": 64,
        "hue": 0,
        "white_balance_automatic": 0,
        "white_balance_temperature": 4600,
        "gamma": 100,
        "gain": 5,
        "power_line_frequency": 2,
        "sharpness": 3,
        "backlight_compensation": 12,
        "auto_exposure": 1,
        "exposure_time_absolute": 157,
        "exposure_dynamic_framerate": 0
    }
}
```

The profile manager can list, load, apply, save, and delete profiles.

The application order matters because some settings depend on others. Automatic white balance must be disabled before a manual white-balance temperature can be applied, and automatic exposure must be disabled before manual exposure time can be changed. The profile system therefore applies the automatic controls before the dependent manual controls.

## MAUI Camera Settings Interface

The Cameras page was expanded with a new camera-settings section containing profile selection, profile application, expandable manual settings, exposure controls, white-balance controls, image controls, lighting controls, and an apply-settings action.

The controls map directly to the V4L2 ranges reported by the cameras. The manual settings area is intentionally collapsible so that the camera page remains practical on a phone.

A XAML layout issue was identified where the expandable camera-settings content had accidentally been placed outside the surrounding `Border`. The XAML itself was valid, but the visual nesting was wrong. The header and expandable content were moved into the same `VerticalStackLayout` inside the `Border`.

The application can also prompt after manual settings are applied and allow the current configuration to be saved as a reusable profile.

## Exposure, White Balance and Polarizer Testing

I tested the cameras with the circular polarizing filters mounted in front of the lenses. The filters successfully reduced reflections when rotated to the appropriate angle, although they also reduce the amount of light reaching the camera.

This led to experimentation with exposure time, gain, gamma, and white balance. For photogrammetry, the priority is preserving sharp detail. A slightly dark but sharp frame is preferable to a bright image with motion blur.

The working approach is therefore:

```text
Increase lighting where possible
Increase exposure moderately
Increase gain only as required
Use modest gamma adjustments if necessary
Avoid excessive brightness adjustment
```

Manual white balance produced a slightly yellow-green appearance under some indoor lighting, while automatic white balance produced more visually neutral images. For the material-classification work, fixed white balance remains attractive because it provides greater consistency across images, but this will be evaluated from actual field data rather than treated as a fixed assumption.

A small amount of the polarizer holder also appeared at the extreme edge of one test image. The obstruction is minor enough that it should not prevent photogrammetry and could be cropped or masked later if necessary.

## Physical Assembly

BEHOLDER was finally assembled into its complete field configuration.

All five USB camera boards and lens assemblies are now mounted on the enclosure. This was a significant milestone because the system had previously existed primarily as a collection of tested subsystems. It is now a complete physical device that can be carried and operated as intended.

The final assembly revealed an issue that was difficult to appreciate during CAD design: cable volume. The USB camera cables are considerably longer than required and create a large bundle inside the enclosure. Fortunately, enough internal space was included in the shell that the cables still fit.

For the current field version, the priorities are to prevent strain on USB ports, keep cables clear of the cooling fan, avoid pinching cables when closing the shell, and maintain enough slack for strain relief.

Future enclosure revisions could add dedicated cable channels, tie-down locations, shorter USB leads, or internal cable sleeving. I had also considered adding two additional cameras, but the current camera boards and cable volume suggest that five cameras may be a practical limit for this enclosure revision.

## Camera Hot-Plug Limitation

A small camera-management limitation was discovered. `CameraManager` currently performs camera discovery when BEHOLDER starts. If a camera is plugged in after the Raspberry Pi is already running, it is not added to the active camera list automatically.

A future improvement could monitor `/dev/video*` devices and trigger rediscovery when the device list changes.

For the current field session, the simpler and safer workaround is:

```text
Connect all cameras
Restart BEHOLDER
Allow CameraManager to rediscover the devices
Verify that all five cameras are present
```

This avoids introducing a new hot-plug system immediately before fieldwork.

## Windows and Android Builds

The MAUI application was built for both Windows and Android.

The Android application can be published as an APK with:

```powershell
dotnet publish -f net9.0-android -c Release -p:AndroidPackageFormats=apk
```

The APK was installed directly on the Galaxy S10 using ADB:

```powershell
adb install -r "com.benfalcoUoL.BEHOLDER-Signed.apk"
```

The `-r` option allows updated builds to replace the existing application without clearing its stored preferences. This made rapid rebuild-and-reinstall testing practical while debugging the field-network behaviour.

## Off-Network Field Test

I drove away from the house with BEHOLDER and tested the device from the car to confirm that it could operate independently of the home network.

The Android application successfully connected to:

```text
192.168.50.1:8000
```

over the dedicated:

```text
Photogrammetry-Device
```

Wi-Fi network.

During this test the application successfully connected to BEHOLDER, loaded API endpoints, applied a camera profile, identified cameras, opened a project, and triggered captures.

This confirmed that the REST API and dedicated Wi-Fi network can operate without the home router or Internet access.

The plan is to make the BEHOLDER hotspot the default wireless connection at startup, while keeping the home Wi-Fi profile available for development when needed.

## Android WebSocket Investigation

The main problem uncovered during the field-network test was that the Android WebSocket connection was unreliable.

The Windows version of the MAUI application could maintain the WebSocket connection normally, while Android repeatedly lost it. The failure appeared as:

```text
WebSocketException
Connection reset by peer
```

Several possible causes were investigated.

First, the Raspberry Pi service was checked with:

```bash
sudo systemctl status beholder
sudo journalctl -fu beholder
```

The FastAPI / Uvicorn service remained active and continued responding to REST requests. The server also continued accepting new WebSocket connections whenever Android reconnected.

Android was then tested in airplane mode with Wi-Fi manually re-enabled. This ruled out switching to cellular data as the primary explanation.

ADB `logcat` was used to inspect Android networking and lifecycle behaviour. The phone remained connected to `Photogrammetry-Device` even while the WebSocket failed. A full system log also showed that Android still considered the phone connected to the BEHOLDER Wi-Fi network, although the network had no Internet connectivity.

This suggested that the problem was specific to the persistent Android WebSocket connection rather than the underlying BEHOLDER Wi-Fi or FastAPI service.

## HTTP Status Polling Fallback

Because normal HTTP requests were consistently reliable on Android, I decided not to make the field system depend on the unstable WebSocket implementation.

BEHOLDER already exposes:

```text
GET /api/status
```

and the MAUI application already contains the `SystemGetStatus` API endpoint definition.

The Android application was therefore changed to request the BEHOLDER status once per second using HTTP.

The new architecture is:

```text
Android
   ↓
GET /api/status every second
   ↓
BeholderStatus
   ↓
Existing dashboard update logic
```

The polling loop waits for each request to complete before delaying for one second, which prevents multiple status requests from overlapping.

The existing `BeholderStatus` model and `UpdateDashboard()` method are reused, so the status transport changed without requiring the dashboard logic to be rewritten.

Two small integration mistakes were corrected while implementing the fallback:

1. `StartStatusPollingAsync()` had accidentally been placed outside the `MainPage` class because of an extra closing brace.
2. The polling code called a non-existent `UpdateStatusDisplay()` method instead of the existing `UpdateDashboard()` method.

After correcting these issues, the HTTP polling system worked successfully on Android.

For the immediate field deployment, the architecture is therefore:

```text
Windows
    WebSocket status

Android
    HTTP status polling at approximately 1 Hz

Both platforms
    REST API commands
```

This is less elegant than using the same live WebSocket transport everywhere, but it is much more important that the mobile interface be reliable during field capture.

A one-second status delay is acceptable for battery level, temperature, storage, current project, capture ID, capture mode, capture state, and camera state.

## Current State

At approximately 5:30 AM on 26 September, BEHOLDER had reached its first complete field-ready state.

The system now consists of:

```text
Fully assembled five-camera capture rig
Raspberry Pi 5 capture controller
Dedicated field Wi-Fi hotspot
Direct Ethernet option for the laptop
Physical clicker control
Windows MAUI application
Android MAUI application
Camera profiles and manual camera controls
Project management
Capture control
Data offloading
Android HTTP status polling
```

There is still substantial work remaining, particularly in photogrammetry processing, dataset evaluation, machine-learning integration, voxel analysis, and refinement of the hardware and software.

However, the most important milestone has now been reached:

**BEHOLDER exists as a complete physical system and is ready to be used for real-world data collection.**

The next step is to perform a basement dry run if time allows and then use the Niagara Railway Museum visit as the first full external field test. The museum session will provide both research data and practical information about exposure, handling, camera overlap, cable management, battery use, and the overall capture workflow.
