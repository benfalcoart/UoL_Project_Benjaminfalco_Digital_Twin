# Development Diary — 19 September 2026

I started work this morning after getting only a few hours of sleep following the previous night's development session. Despite being tired, the main goal for the day was to move BEHOLDER away from individually tested components and toward a complete field-ready capture system. A major focus was therefore on defining how projects, cameras, the physical clicker, the API, and the future phone application should interact without allowing the codebase to become overly coupled.

## Project Management and Recovery

A significant amount of work was completed on the **project management system**. The `ProjectManager` was tested on the Raspberry Pi using a dedicated test project. The tests confirmed:

- Project creation.
- Directory and metadata generation.
- Persistence of capture IDs across a simulated reboot.
- Project listing.
- Project statistics.
- Project deletion.
- Recovery from an interrupted capture.

In particular, the recovery logic successfully detected image files whose capture ID was newer than the value stored in `project.json` and repaired the stored counter. This provides useful fault tolerance if BEHOLDER loses power during fieldwork.

The intended recovery behaviour is that the filesystem is treated as evidence of what was actually written, while the metadata counter is never reduced. This means that if image files exist with a higher capture ID than the metadata, the project can recover forward, while a previously reserved capture ID will not be reused if power is lost before the corresponding images are completed.

## Capture Controller and Clicker Integration

Attention then moved to the **actual image capture workflow**. Rather than allowing the API, clicker, and cameras to each contain their own capture logic, I introduced a `CaptureController`. This acts as the central coordinator between the `ProjectManager` and `CameraManager`.

The controller supports two capture modes:

- **Single Shot** — each clicker press triggers one complete capture across all active cameras.
- **Automatic** — the first clicker press starts continuous rapid-fire capture and the next press stops it.

The existing USB presenter/clicker was integrated using `evdev`. The Page Up and Page Down buttons are treated as equivalent physical trigger buttons. Only key-down events are processed, preventing key release and repeat events from accidentally causing additional captures.

Concurrency protection was also added using a lock so that the phone, clicker, and automatic capture thread cannot command the camera array simultaneously. The `CameraManager` continues to handle the lower-level camera work, including concurrent `v4l2-ctl` captures, retries, timeouts, and individual camera failure results.

Automatic capture was also designed to use more aggressive timeout/retry behaviour than single-shot capture. The reasoning is that a single missed frame during rapid-fire capture is preferable to freezing the entire capture sequence for a long retry period.

## End-to-End Capture Test

An end-to-end hardware test was performed on BEHOLDER.

Five cameras were detected and active. A single clicker press successfully produced five images:

```text
000001_CAM01.jpg
000001_CAM02.jpg
000001_CAM03.jpg
000001_CAM04.jpg
000001_CAM05.jpg
```

Automatic mode was then started and stopped using the physical clicker. Seven additional capture events were produced, resulting in eight total capture sets.

Every capture contained images from all five cameras, giving a **5/5 success rate for every capture during the test**.

This successfully demonstrated the complete physical workflow:

```text
Clicker
  ↓
CaptureController
  ↓
ProjectManager
  ↓
CameraManager
  ↓
Five concurrent camera captures
  ↓
Numbered JPG files saved to the active project
```

This is an important milestone because the physical clicker is intended to be the main field controller for BEHOLDER.

## Application State Architecture

The software architecture was reorganized around a shared `app_state.py`.

This ensures that the API, system monitor, clicker, and capture system all reference the same:

- `CameraManager`
- `ProjectManager`
- `CaptureController`
- Clicker controller

This avoids accidentally creating independent copies of system state in different modules.

The intended architecture is now:

```text
Physical Clicker ──┐
                   │
Phone / API ───────┼──► CaptureController
                   │
                   └──► Shared Application State
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
              ProjectManager       CameraManager
```

## FastAPI and Postman Testing

Work then moved to the **FastAPI interface**.

FastAPI and Uvicorn were installed inside a Python virtual environment on the Raspberry Pi. The server was successfully exposed across the local network and tested from my computer using Postman.

API calls were tested for:

- System status.
- Camera information.
- Enabling and disabling cameras.
- Project creation.
- Capture mode.
- Capture interval.
- Capture triggering.
- WebSocket connectivity.

Duplicate project creation initially generated an HTTP 500 because the existing `ValueError` was not being handled by the API layer. This was identified and changed so that the API can return a more appropriate conflict response.

The API is intended to use REST primarily for commands sent **to** BEHOLDER.

Examples include:

```text
Create/open project
Set capture mode
Set automatic capture interval
Enable/disable cameras
Trigger capture
```

## WebSocket Status System

The WebSocket connection was also successfully tested.

The intention is to use REST requests primarily for **commands sent to BEHOLDER**, while the WebSocket provides continuous **state updates from BEHOLDER back to the client**.

This is especially useful because the physical clicker is intended to remain the primary field controller. If automatic capture is started using the clicker, the phone application should immediately update its interface without having initiated the action itself.

The planned WebSocket status data includes:

- Current project.
- Current or most recent capture ID.
- Single/automatic mode.
- Whether automatic capture is currently running.
- Whether a capture is currently in progress.
- Automatic capture interval.
- Number of detected cameras.
- Number of active cameras.
- Camera slot assignments.
- Battery percentage.
- Battery voltage.
- Current draw.
- Power draw.
- Raspberry Pi temperature.
- Free storage.
- Connection state.
- Timestamp.

The plan is for BEHOLDER to send a complete status snapshot approximately once per second, while immediate events such as capture start, capture completion, camera failure, automatic capture start, and automatic capture stop can later be pushed instantly.

This should provide the future client application with a reliable live representation of BEHOLDER's state.

## Automatic Startup

BEHOLDER was configured to start automatically after boot.

A Bash launcher and `systemd` service were created so that the FastAPI server and clicker listener start automatically when the Raspberry Pi powers on.

The service is also configured to restart if it fails.

The deployment files were copied back to the Windows development repository so that the Raspberry Pi startup configuration is version controlled alongside the rest of the research project.

The intended field startup process is therefore:

```text
Power on BEHOLDER
       ↓
Raspberry Pi boots
       ↓
systemd starts BEHOLDER
       ↓
FastAPI starts
       ↓
Clicker listener starts
       ↓
Phone/laptop connects
       ↓
Project is selected
       ↓
Capture begins
```

## Mobile/Desktop Client Planning

I also spent some time considering the approach for the **mobile/desktop control application**.

I initially expected to build a Java Android Studio application, partly because I wanted additional practice with Java. However, I am now leaning toward using **.NET MAUI** instead.

I am significantly more familiar with C# because of both my career in game development and my current teaching work. MAUI would still give me an opportunity to learn a new technology stack without simultaneously having to become comfortable with a new application language and mobile framework.

MAUI also has the additional advantage of allowing the same application to target both Android and Windows, which would allow BEHOLDER to be controlled from either my phone in the field or my Windows laptop.

I plan to begin development of the MAUI client tomorrow. Today's work remained focused primarily on the BEHOLDER hardware, Raspberry Pi capture software, API, and system integration.

## 3D Printing and Phone Mount Development

In parallel with the software work, I spent much of the day **3D printing and iterating on the physical phone mounting system for BEHOLDER**.

The goal is to mount my phone securely to the telescopic pole that will be used during field capture, allowing the phone to function as the live control and status interface while BEHOLDER is operating.

I went through three physical design iterations during the day.

### Version 1

The first design had sizing issues and did not fit the pole correctly.

This print was useful for identifying dimensional problems and determining how much clearance would be required around the pole.

### Version 2

The second design fit the pole very well, confirming that the basic clamp dimensions were now correct.

However, the printed part snapped during testing. Although this version failed mechanically, the successful pole fit provided a useful basis for the next design.

### Version 3

Based on what I learned from the first two prototypes, I created a third design consisting of **three separate interlocking pieces**.

The pieces are intended to lock together around the pole while also supporting the phone and its case.

This should distribute the forces more effectively than the earlier approach and provide a stronger connection without requiring the mount to be permanently screwed into a fixed angle.

The third version is currently printing overnight.

I have high hopes for this iteration because it combines the correct pole fit achieved in the second prototype with a more robust multi-piece clamping structure.

If successful, it should become the basis for the final phone mount used during BEHOLDER field testing.

## Summary

Overall, today moved BEHOLDER substantially closer to a usable field instrument.

The following major components were demonstrated or established:

- Persistent project management.
- Power-loss capture recovery.
- Physical clicker control.
- Single-shot capture mode.
- Automatic rapid-fire capture mode.
- Five-camera concurrent capture.
- Capture locking and state management.
- Shared application state.
- FastAPI network control.
- Postman API testing.
- WebSocket connectivity.
- Automatic Raspberry Pi startup using `systemd`.
- Selection of .NET MAUI as the likely approach for the Android/Windows control application.
- Three iterations of the physical phone/pole mounting system.

At the same time, the physical phone mount progressed through three rapid 3D-printed design iterations, with the latest three-piece version printing overnight.

The next major phase is to begin development of the MAUI client tomorrow, while continuing to refine the physical mount and prepare BEHOLDER for field deployment.
