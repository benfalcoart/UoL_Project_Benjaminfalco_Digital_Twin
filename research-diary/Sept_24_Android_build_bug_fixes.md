# Development Diary — 24 September 2026

## Preparing BEHOLDER for Field Use

Today’s development work focused on moving BEHOLDER from a system that works reliably on my home network toward one that can be used independently in the field. The main areas of work were field networking, further refinement of the MAUI configuration application, Android deployment, and testing the mobile capture and data-transfer workflow.

At this stage, the core Raspberry Pi capture system is substantially complete. The priority is now ensuring that the phone and laptop can reliably communicate with BEHOLDER without depending on an external Wi-Fi network.

## Field Network Configuration

I configured BEHOLDER with a dedicated Wi-Fi hotspot for use in the field.

The NetworkManager connection is configured as:

```text
Connection: Photogrammetry-Hotspot
SSID: Photogrammetry-Device
```

The hotspot uses a fixed Raspberry Pi address of:

```text
192.168.50.1
```

with the FastAPI service available at:

```text
192.168.50.1:8000
```

This will allow the phone to connect directly to BEHOLDER without requiring a router or Internet connection.

I also configured the Raspberry Pi’s Ethernet interface for a separate direct connection to the laptop. The Pi uses:

```text
192.168.60.1
```

while the laptop can be manually configured as:

```text
192.168.60.2
Subnet mask: 255.255.255.0
```

No gateway or DNS server is required because this connection is intended only for communication between the laptop and BEHOLDER.

Testing confirmed that the laptop could successfully communicate with the FastAPI service over the direct Ethernet connection.

The intended field network arrangement is therefore:

```text
                  BEHOLDER
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
    Wi-Fi Hotspot          Direct Ethernet
    192.168.50.1           192.168.60.1
          │                     │
          ▼                     ▼
        Phone                 Laptop
```

The Wi-Fi connection will primarily support the mobile control application, while Ethernet provides a faster and more reliable option for transferring captured datasets to the laptop.

At home, BEHOLDER can still connect to the normal wireless network, although the current address of `192.168.0.130` is assigned dynamically and may change.

## Unified Application Connection Settings

I also refactored the MAUI application so that the REST API and WebSocket systems use the same connection configuration.

Previously, different parts of the application could independently construct their own addresses. This created a risk that the command API and live status connection could point at different IP addresses.

A shared `BeholderConnectionSettings` service now maintains:

```text
Address
Port
HTTP base address
WebSocket address
```

Both the REST and WebSocket services reference this shared state.

This means that changing the BEHOLDER address in the application automatically changes the destination used by both communication systems.

The application can therefore be switched between environments such as:

```text
Home Wi-Fi:
192.168.0.130:8000

Field Wi-Fi:
192.168.50.1:8000

Direct Ethernet:
192.168.60.1:8000
```

without changing source code.

## Camera Interface Refinement

Further work was completed on the Cameras page of the MAUI application.

Camera controls are generated dynamically from the cameras reported by BEHOLDER, while the physical layout displays the possible mounting positions on the enclosure:

```text
T1

U1 U2 U3 U4 U5

M1 M2 M3 M4 M5 M6 M7 M8 M9

L1 L2 L3 L4 L5

B1
```

The camera cards are retained rather than recreated every time a WebSocket status update arrives. This prevents controls such as the slot-selection pickers from closing or resetting while the Raspberry Pi sends its regular status broadcasts.

The camera page can now perform the major operations required for field configuration, including:

- Enabling and disabling cameras.
- Assigning cameras to physical BEHOLDER slots.
- Identifying an individual camera by requesting a temporary JPEG image.
- Displaying camera assignments visually on the physical layout.

I also continued refining the use of colours to visually distinguish camera assignments within the interface.

## Android Release Build

The next major task was producing a proper Android build of the application for my Samsung Galaxy S10.

A Release APK was generated using:

```text
dotnet publish -f net9.0-android -c Release -p:AndroidPackageFormat=apk
```

The application was then installed directly using ADB.

The Android build completed successfully. The remaining compiler messages were limited to several XAML compiled-binding warnings and did not prevent the application from running.

I also began replacing the default MAUI application identity and icon with the BEHOLDER branding so that the installed field application is visually distinguishable from a generic development build.

## Android Startup Crash Investigation

An early Android build installed correctly but immediately crashed during startup.

Using Android `logcat`, I traced the failure to:

```text
DeviceDisplay.Current.KeepScreenOn
```

The setting was being applied inside the Settings page constructor while dependency injection was constructing the application. At that point, Android had not yet provided a valid Activity, resulting in a `NullReferenceException` indicating that the current Activity could not be detected.

I changed the initialization behaviour so that `LoadPreferences()` only reads stored settings and updates the interface.

The actual Android screen-awake setting is now applied after the main page becomes visible, when a valid Activity exists.

The settings toggle can still change the value immediately once the application is running.

After this change, the application launched successfully on Android.

## Android Networking

Once the application launched, the next problem was communication with the Raspberry Pi.

The BEHOLDER API currently uses ordinary HTTP rather than HTTPS. Modern Android applications block cleartext HTTP traffic by default, so the Android application manifest was updated to explicitly permit cleartext communication.

The required Internet permission was also confirmed.

After these changes, the Android version successfully connected to BEHOLDER and the same application services used by the Windows build began functioning on the phone.

Testing confirmed:

```text
WebSocket connection        ✓
REST API requests           ✓
Project operations          ✓
Single capture              ✓
Automatic capture           ✓
Camera identification       ✓
Five-camera communication   ✓
```

This is an important milestone because the phone is intended to be the main visual configuration and monitoring interface while BEHOLDER is being used in the field.

## Android Project Offloading

I then began testing the project offload system on Android.

The existing transfer architecture downloads a project manifest from BEHOLDER and streams each file individually rather than building a large archive on the Raspberry Pi.

This remains desirable because it avoids requiring enough free space on BEHOLDER to temporarily store both the original photographs and a second compressed copy.

The basic workflow remains:

```text
Request project manifest
        ↓
Receive list of files and sizes
        ↓
Request each file individually
        ↓
Stream file to destination
        ↓
Update progress
        ↓
Original remains on BEHOLDER
```

Android initially exposed a threading problem while the HTTP response stream was being closed. The Android HTTP implementation attempted network work on the UI thread and raised a `NetworkOnMainThreadException`.

The transfer service was adjusted so that its network and file operations do not resume unnecessarily on the UI synchronization context. The user-interface event handler remains on the UI thread, while the transfer service performs its I/O asynchronously.

After resolving this issue, the transfer progressed far enough to expose a second Android-specific problem: storage access.

## Android Scoped Storage

The folder picker allowed me to choose a directory such as:

```text
/storage/emulated/0/offload test
```

but Android then rejected the attempt to create files there using ordinary `System.IO.File.Create()`.

This is a consequence of Android’s scoped-storage model. Selecting a folder through the Android storage interface does not necessarily provide a normal filesystem path that can be accessed using the same APIs as Windows.

As a diagnostic test, I redirected project offloads to the application’s private data directory:

```text
/data/user/0/com.benfalcoUoL.BEHOLDER/files/Offloads
```

The transfer succeeded there, confirming that:

- The BEHOLDER transfer API works.
- Manifest retrieval works.
- File streaming works.
- Android can receive and write the captured files.
- The remaining issue is specifically how the destination is represented and accessed on Android.

Private application storage is not suitable as the final field workflow because the files cannot easily be browsed using the normal Android file manager.

I therefore began adapting the Android implementation to use Android’s `MediaStore` system instead.

The intended Android output structure is:

```text
Downloads
└── BEHOLDER
    └── Project_Name
        ├── project.json
        └── captured files...
```

On Windows, the existing folder-picker and ordinary filesystem implementation will remain unchanged.

The platform-specific transfer behaviour is therefore becoming:

```text
                 ProjectTransferService
                         │
             ┌───────────┴───────────┐
             │                       │
             ▼                       ▼
          Windows                  Android
             │                       │
        System.IO                 MediaStore
             │                       │
      User-selected folder      Downloads/BEHOLDER
```

The network transfer logic remains shared between both platforms; only the method used to create the destination file needs to differ.

## End-of-Day State

By the end of the session, BEHOLDER had made substantial progress toward being genuinely field-ready.

The networking architecture now supports both a direct phone hotspot connection and a dedicated Ethernet laptop connection. The MAUI client uses a shared connection configuration for REST and WebSocket communication, reducing the chance of inconsistent connection state.

The Android application can now launch reliably, connect to BEHOLDER, receive live WebSocket telemetry, issue REST commands, control capture, and identify individual cameras.

Android project offloading has also been proven to work at the network and streaming level. The remaining work is primarily adapting the final output stage to Android’s scoped-storage system so that transferred projects appear in a normal user-accessible `Downloads/BEHOLDER` directory.

The overall system is now approaching the point where the full workflow can be rehearsed away from the home network:

```text
Power on BEHOLDER
        ↓
Connect phone to BEHOLDER hotspot
        ↓
Open/create project
        ↓
Verify cameras and slots
        ↓
Capture photographs
        ↓
Connect laptop or use phone fallback
        ↓
Offload project
```

The next development session should finish the Android `MediaStore` download implementation, verify that complete projects appear correctly in the phone’s Downloads folder, test repeat transfers and larger datasets, and then perform a complete field-style capture rehearsal before the first real scanning session.
