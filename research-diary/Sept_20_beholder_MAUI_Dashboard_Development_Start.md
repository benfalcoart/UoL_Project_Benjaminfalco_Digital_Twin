# Development Diary — 20 September 2026

I started the day by finishing the cleanup and organization of the machine-learning experiments I had originally developed during July and August. Much of this code had remained local while I was experimenting with different approaches, so I spent the morning refactoring it, improving naming and structure, adding documentation where appropriate, and committing the individual scripts to the project repository.

I deliberately committed the experiments separately so that the development history is easier to follow and so that it is clear that these are cleaned and consolidated versions of work completed earlier in the project rather than newly introduced code.

With the older machine-learning work now organized and under version control, I moved on to beginning development of the **BEHOLDER configuration and control application**.

## Beginning the .NET MAUI Application

I decided to proceed with **.NET MAUI** rather than creating a native Java Android application.

I found MAUI surprisingly easy to get up and running. Its general application structure and, particularly, its use of **XAML** are very similar to WPF, which I already use and teach at Niagara College. Because of this familiarity, I was able to understand the page structure, controls, layout system, and C# code-behind almost immediately.

This made MAUI feel like a good compromise for the project: it introduces me to a new application framework while allowing me to continue working in C# and XAML, technologies that are already closely related to my professional and teaching experience.

Another advantage is that the same application can target both **Windows and Android**. This is useful for BEHOLDER because I want the phone to act as the primary field interface while still having the option to run the same control application on my laptop.

I began development using the Windows target because my phone was charging and I plan to deploy and test the Android version later.

## WebSocket Client

The first development goal was intentionally small: establish communication between the MAUI application and BEHOLDER's existing WebSocket server.

I created a `BeholderWebSocketService` using .NET's `ClientWebSocket`. The service maintains the connection to BEHOLDER and exposes events for connection-state changes and incoming messages.

The WebSocket service is registered as a **singleton** with MAUI's dependency injection system. This is important because the finished application will contain multiple pages, but they should all share the same BEHOLDER connection rather than creating independent WebSocket connections.

The intended structure is:

```text
BEHOLDER
    ↓
WebSocket
    ↓
BeholderWebSocketService
    ↓
Shared application state
    ↓
Dashboard / Projects / Cameras / Settings
```

I initially ran into a connection-refused error when attempting to connect to BEHOLDER at:

```text
ws://192.168.0.130:8000/ws
```

This was useful because it confirmed that the MAUI application was attempting the network connection correctly and allowed me to verify the Raspberry Pi service and network configuration.

Once the server was available, the connection succeeded.

## Debugging the Receive Loop

After establishing the WebSocket connection, I found that the application was not receiving any status updates.

The cause was straightforward: although I had written the asynchronous receive-loop function, I had forgotten to actually start it after the WebSocket connected.

After correcting this, the application began receiving messages from BEHOLDER.

The resulting flow is now:

```text
ConnectAsync()
    ↓
WebSocket connects
    ↓
ReceiveLoopAsync() starts
    ↓
BEHOLDER sends status
    ↓
MessageReceived event
    ↓
MAUI user interface
```

I also adjusted the receive logic to properly account for WebSocket messages that may be split across multiple receive operations by waiting until `EndOfMessage` is reached before treating the data as a complete message.

Debugging confirmed that a complete BEHOLDER status message was successfully reaching the C# application.

An example contained live values for system temperature, free storage, battery percentage and electrical data, capture mode, capture state, and information for all five connected cameras.

## BEHOLDER Status Model

I created a C# status model matching the structure of the JSON being transmitted by BEHOLDER.

The model represents several parts of system state, including:

- System status and temperature.
- Free storage.
- Battery percentage, voltage, current, and power.
- Current project.
- Capture mode and automatic-capture state.
- Camera count, active state, and physical slot assignment.

Nullable fields are used where appropriate. For example, BEHOLDER can legitimately report that no project is currently selected, so the project object may be `null`.

I also added a custom `ToString()` implementation that produces a human-readable diagnostic representation of the status rather than simply outputting raw JSON.

This proved useful while validating that the C# representation contained the expected values.

## MAUI Multiline Display Issue

While displaying the incoming status, I encountered an unexpected UI issue where the MAUI `Editor` control would display only the first line of multiline text.

Initially this looked like either a WebSocket fragmentation problem or an issue with JSON serialization. Breakpoint inspection confirmed, however, that the complete message was reaching the application correctly.

Even a simple multiline test would display only the first line in the `Editor`.

I replaced the read-only `Editor` with a `Label` contained inside a `ScrollView`. This immediately displayed the complete multiline diagnostic status correctly.

At this point the full communication pipeline had been demonstrated successfully:

```text
Raspberry Pi
    ↓
FastAPI WebSocket
    ↓
Local network
    ↓
MAUI ClientWebSocket
    ↓
C# BeholderStatus
    ↓
Windows MAUI interface
```

This was the first point at which live BEHOLDER telemetry was visibly displayed inside the new application.

## Dashboard Development

With the communication layer working, I began replacing the temporary diagnostic interface with the actual BEHOLDER dashboard.

The interface uses the same general visual style as the digital-twin viewer: a dark background, charcoal panels, white text, subtle borders, blue interaction elements, and green/red status indicators.

The dashboard is being designed to display the most important information needed while operating BEHOLDER in the field, including the current project and capture ID, capture mode, automatic-capture state, camera count, battery level, Raspberry Pi temperature, available storage, and individual camera status.

The main capture controls will support both **Single** and **Automatic** modes. In automatic mode, the primary action button will change between starting and stopping automatic capture.

The interface is designed so that the WebSocket is responsible for displaying the real system state. This is important because BEHOLDER can also be controlled using the physical clicker. If a capture mode or state changes through the clicker, the MAUI application should reflect that change rather than assuming that all actions originate from the application itself.

## Application Navigation

I revisited the earlier application design and retained the planned bottom navigation structure.

The final application is intended to have four major areas:

```text
Dashboard | Projects | Cameras | Settings
```

The Dashboard is the live capture-control interface.

The Projects page will handle project creation, selection, and project information.

The Cameras page will handle enabling/disabling cameras, camera identification, and assignment of cameras to the 21 physical BEHOLDER camera positions.

The Settings page will eventually contain connection settings, diagnostics, data transfer, and other system configuration.

MAUI's existing `AppShell` will be retained and used to provide this navigation rather than manually recreating navigation controls on each page.

## BEHOLDER Connection Screen

I also began implementing a dedicated **Connection** screen.

Rather than automatically connecting to a hardcoded Raspberry Pi address, the Dashboard will have a `CONNECT` button near the top of the interface.

Selecting this opens a connection page containing fields for:

```text
Address
Port
Password
```

The address and port are currently used to construct the WebSocket address dynamically rather than relying on the previously hardcoded `192.168.0.130:8000`.

A password field has also been included in preparation for the authentication system I intend to add later. Password authentication itself has not yet been implemented.

The eventual connection process is intended to be:

```text
Open application
    ↓
Dashboard
    ↓
CONNECT
    ↓
Enter BEHOLDER address / port / password
    ↓
Authenticate and connect
    ↓
Return to Dashboard
    ↓
Live telemetry begins
```

After a successful connection, the Connection page now returns to the existing Dashboard rather than creating another instance of it. This is handled through the Shell navigation stack.

## Physical Hardware and Phone Mount Testing

The three-piece phone mount that I left printing overnight from the previous development session was completed and tested today.

The design worked extremely well on the shorter handheld pole. The three interlocking printed pieces fit together securely, held the phone and case in place, and clamped effectively around the pole. This was a significant improvement over the earlier prototypes, particularly the second version that fit correctly but snapped during testing.

The successful print gives me confidence in the overall mounting approach. I still need to produce a second version sized for the larger **25-foot telescopic pole**, but the shorter handheld configuration is now working well and provides a proven design to adapt from.

While testing the assembled BEHOLDER hardware, the overall appearance of the two pole configurations has also earned me the nickname **“The Wizard”** from friends and family. The shorter handheld pole resembles a wand, while the long telescopic pole resembles a staff once the BEHOLDER hardware is mounted to it.

Although this is mostly an amusing side effect of the physical design, it does highlight how distinctive the final capture rig has become as it transitions from individual components into a recognizable field instrument.

## Current State

By the end of the session, the MAUI application could successfully establish a WebSocket connection to BEHOLDER and receive real-time status information from the Raspberry Pi.

The most important software milestone today was proving the complete communication path between the physical BEHOLDER system and a separate graphical client application.

The physical side of the system also progressed, with the overnight three-piece phone mount proving successful on the shorter handheld pole. A second version still needs to be produced for the 25-foot pole, but the mounting concept is now validated.

The application is still in the early stages visually, but the underlying communication architecture is now functioning. The next work will focus on completing the dashboard controls, setting up the full Shell navigation structure, creating the Projects and Cameras interfaces, and connecting the application's buttons to the existing FastAPI REST endpoints.

Android deployment also remains to be tested once my phone is available, but because MAUI supports the same C# and XAML application across Windows and Android, the Windows version has provided a convenient environment for getting the initial application architecture working first.
