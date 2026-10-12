# Development Diary — 21 September 2026

Development continued directly from the previous day's work and extended through the night into the early morning. By approximately **5:30 AM**, I had reached another useful milestone with both the BEHOLDER software and physical hardware.

## MAUI Interface Refinement

I continued developing the .NET MAUI configuration application and focused primarily on refining the overall navigation and visual design.

The application now uses a Shell-based tab structure to separate the major areas of BEHOLDER:

```text
Dashboard
Projects
Cameras
Connection
Settings
```

I initially experimented with showing both icons and text labels in the navigation bar. However, when resizing the Windows application, MAUI's native Shell tab bar did not consistently update the tab labels. Some tabs would switch to icon-only while others retained their text, resulting in inconsistent spacing.

Rather than continuing to work around platform-specific Shell rendering behaviour, I decided that **icon-only navigation** is simpler and better suited to the application. I selected a set of royalty-free **Lucide SVG icons** for the navigation tabs.

MAUI automatically processes SVG image resources into platform-specific assets, although the resources are referenced using generated `.png` names inside XAML. I also encountered MAUI's strict resource naming requirements: filenames cannot contain hyphens and must use lowercase alphanumeric characters or underscores. Renaming the downloaded Lucide assets resolved the build errors.

The resulting navigation is compact and works much better across different window sizes.

## Application Theme

While testing the Settings page, I noticed that several controls, particularly `Entry` fields and other input controls, were using dark text despite being placed on BEHOLDER's dark interface.

The cause was the default MAUI styles, which were still using `AppThemeBinding` and therefore following the Windows system theme. Because Windows was using a light theme, some MAUI controls were selecting their light-theme colours even though the application itself had been designed as dark-only.

I decided that BEHOLDER does not require a light theme and forced the application to use:

```csharp
UserAppTheme = AppTheme.Dark;
```

This allows the existing MAUI control styles to consistently use their dark-theme colours throughout the application rather than individually overriding text colours on every page.

This also fits the intended BEHOLDER visual design, which is deliberately styled as a dark technical field interface.

## Additional Application Pages

I fleshed out the visual structure of the remaining major pages.

The **Projects page** is designed around the current active project and the projects stored on BEHOLDER. It will eventually support creating new projects, opening existing projects, viewing image counts and storage usage, and later offloading or deleting completed datasets.

The **Cameras page** includes a visual representation of the 21 possible camera mounting positions:

```text
T1

U1 U2 U3 U4 U5

M1 M2 M3 M4 M5 M6 M7 M8 M9

L1 L2 L3 L4 L5

B1
```

Each connected camera will eventually be assigned to one of these physical positions using Row and Slot selectors. The page will also provide controls for identifying, enabling, and disabling cameras.

The **Settings page** now contains planned sections for:

- Field behaviour.
- Automatic capture interval.
- Data transfer.
- Diagnostics.
- Security.
- Advanced application settings.

A dedicated **Connection page** was also moved into the main tab navigation. I found this simpler than treating connection configuration as a separate modal workflow. The page currently accepts the BEHOLDER address, API port, and a password field reserved for the authentication system that will be implemented later.

## First Android Deployment

I began testing the MAUI application on my **Samsung Galaxy S10**.

Visual Studio initially reported that the Android SDK licences had not been accepted. While investigating the installed Android SDK and JDK paths, Visual Studio unexpectedly completed the deployment and the application appeared on the phone.

This marked the first successful Android deployment of the BEHOLDER configuration application.

The same MAUI project is now running on both:

```text
Windows
Android
```

This validates one of the main reasons I selected MAUI: the same C# and XAML application can be used both as a desktop configuration tool and as the mobile field interface mounted directly on the BEHOLDER pole.

Further Android testing will be required, particularly for the WebSocket connection to the Raspberry Pi and the final phone-sized layout, but the basic deployment pipeline is now working.

## Additional 3D Printing

While continuing the software work, I also prepared additional components for 3D printing.

Several unused openings remain in the BEHOLDER enclosure because the physical shell supports more camera positions than are currently populated. I modelled **small removable hole covers with ventilation openings** for these unused slots.

The covers should serve two purposes:

- Close unused openings in the enclosure and improve the finished appearance.
- Preserve airflow through the shell rather than completely sealing those areas.

These parts were started on the printer before going to sleep and will print while I rest.

This continues the rapid physical iteration process used throughout the BEHOLDER build: software development and physical fabrication are progressing in parallel, allowing enclosure changes and interface improvements to be tested almost immediately.

## Current State

At approximately **5:30 AM**, the current development session concluded with several useful milestones completed.

The BEHOLDER configuration application now has a much more complete multi-page structure, consistent dark styling, icon-based navigation, and an initial Android deployment running successfully on the Galaxy S10.

The physical system is also continuing to evolve, with additional enclosure components currently printing overnight.

The next development work will include testing live BEHOLDER communication from the Android version, connecting the new Projects and Cameras interfaces to the FastAPI endpoints, and continuing to refine both the field interface and the physical enclosure.

---

# Later Development Session — API Integration, Data Offload and System Testing

After returning to the project later on 21 September, development shifted away from the visual shell of the MAUI application and toward connecting the interface to the live BEHOLDER system. This became a substantial integration session covering the Raspberry Pi FastAPI backend, MAUI REST communication, project management, camera configuration, data offloading, diagnostics, and initial endurance testing.

## FastAPI Backend Expansion and Refactoring

I continued restructuring the Raspberry Pi backend so that the system has a clear division of responsibility.

The central application state now uses shared instances of the major BEHOLDER subsystems:

```text
CameraManager
ProjectManager
CaptureController
Clicker
```

This ensures that the REST API, WebSocket status updates, and physical clicker all operate on the same live system state rather than creating independent instances.

The FastAPI server was expanded to provide the endpoints required by the MAUI application. These now cover:

- System status.
- Project creation, opening, closing, deletion, and listing.
- Current project information.
- Camera listing, enabling, disabling, physical slot assignment, and identification.
- Capture mode selection.
- Automatic capture interval configuration.
- Capture status and triggering.
- Project transfer manifests.
- Individual file transfer.

The request models used by the server were also moved into a dedicated models module to reduce clutter in `server.py` and make the API definitions easier to maintain.

Additional exception handling was added at the API boundary so that expected problems can return meaningful HTTP responses while unexpected failures can be logged and returned as server errors.

## Camera Identification and Configuration

Camera management was expanded beyond simple detection and enable/disable support.

Each camera can now be assigned to one of BEHOLDER's physical mounting positions, such as:

```text
T1
U1-U5
M1-M9
L1-L5
B1
```

Duplicate slot assignments are rejected so that two cameras cannot accidentally be configured for the same physical location.

An identification feature was also added. The API can capture a temporary image from a requested camera and return the JPEG directly to the MAUI application. This can be used while configuring the rig to determine which physical camera corresponds to each `/dev/video` device.

The identification image is treated as temporary diagnostic data and does not increase the project's capture counter or become part of the dataset.

## MAUI REST API Service

The MAUI application's `BeholderAPIService` was developed into a generic REST client.

Rather than hard-coding individual URLs throughout the application, endpoint information is stored in `APIEndPoints.json`. Each API operation is represented by an `APIEndpoint` enum value, and the service resolves the HTTP method and route at runtime.

The endpoint set now covers the major project, camera, capture, transfer, and system operations.

The service also supports `HttpCompletionOption`, which is important for project offloading because large image files can be streamed directly rather than requiring the entire HTTP response to be loaded into memory first.

Connection information remains configurable so that the Raspberry Pi address and port can ultimately come from the application's Connection page rather than being hard-coded.

## Application Diagnostics and Logging

A centralized application logging service was added to the MAUI application.

The logger supports informational, warning, and error messages and exposes them to a dedicated diagnostic console page. This provides a useful field-debugging tool without requiring Visual Studio to be connected.

The console is intentionally separate from the main tab navigation and is accessed through the Settings page.

This became especially useful while testing API operations, transfers, and connection state because errors can now be surfaced inside the application instead of silently failing.

## Dashboard and Capture Controls

The Dashboard was connected to the live BEHOLDER backend.

The application can now:

- Switch between single and automatic capture modes.
- Configure the automatic capture interval.
- Trigger a single capture.
- Start or stop automatic capture.

The WebSocket remains the authoritative source for displaying live state. REST calls issue commands, while status updates from the Pi determine what the interface displays.

A problem was identified where the automatic interval text field could be continually overwritten by the once-per-second WebSocket update while the user was attempting to edit it. A local dirty-state flag was introduced so that the server value only replaces the field when the user is not actively changing it.

This preserves the principle that the Pi owns the actual capture state without making the interface frustrating to use.

## Project Management

The Projects page was connected to the project API.

The application can now work with the projects stored on the Raspberry Pi, including:

- Listing projects.
- Creating a new project.
- Opening a project.
- Closing the current project.
- Deleting projects.
- Displaying the currently selected project.

Project information includes capture counts, image counts, creation information, and storage usage.

The current project is also communicated through the live WebSocket status so that other parts of the MAUI application can remain synchronized with the project selected on the Raspberry Pi.

## Late-Night Continuation

Work continued into the early hours of **22 September 2026**.

At this point I decided to stop for the night rather than continue making changes while tired. The plan is to take a break, return to the project tomorrow, and continue the ongoing refactor and system testing with a fresh head.

