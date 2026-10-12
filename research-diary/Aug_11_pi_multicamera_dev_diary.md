# Development Diary – August 11, 2026
## Raspberry Pi 5 Multi-Camera Capture Hardware Bring-Up

## Session Objective

The goal of this session was to assemble and validate the Raspberry Pi 5
image-capture hardware, specifically:

-   Raspberry Pi 5
-   Waveshare PCIe to USB 3.2 Gen1 HAT+
-   PCIe FFC/ribbon cable
-   Five Innomaker U20CAM-1080P-S1 USB cameras
-   Ethernet/SSH access to the Raspberry Pi

The immediate objective was to confirm that the PCIe expansion board
could be detected by the Raspberry Pi and that images could successfully
be captured from the USB cameras.

------------------------------------------------------------------------

## 1. Hardware Assembly

The Waveshare PCIe to USB 3.2 Gen1 HAT+ was mounted above the Raspberry
Pi 5 using the supplied brass standoffs.

The HAT uses both the physical HAT/GPIO mounting arrangement and a
separate 16-pin PCIe ribbon cable. The ribbon cable connects the
Raspberry Pi 5 external PCIe interface to the PCIe connector on the
Waveshare board.

Initially, the expansion board was assembled and the Raspberry Pi booted
successfully, but the expansion board was not detected.

------------------------------------------------------------------------

## 2. Initial PCIe Detection Test

After connecting to the Raspberry Pi over SSH, PCI devices were
inspected with:

``` bash
lspci
```

At this stage only the Raspberry Pi's existing USB root hubs were
visible.

------------------------------------------------------------------------

## 3. Enabling the Raspberry Pi 5 External PCIe Interface

The Raspberry Pi boot configuration was checked for an external PCIe
configuration:

``` bash
grep -i pcie /boot/firmware/config.txt
```

No PCIe configuration was returned.

The configuration file was opened:

``` bash
sudo nano /boot/firmware/config.txt
```

The following line was added:

``` ini
dtparam=pciex1
```

The file was saved and the Raspberry Pi rebooted:

``` bash
sudo reboot
```

After reconnecting through SSH, the configuration was verified:

``` bash
grep -i pcie /boot/firmware/config.txt
```

Output:

``` text
dtparam=pciex1
```

However, `lspci` still did not show the expansion board.

------------------------------------------------------------------------

## 4. Diagnosing the PCIe Link

Kernel messages relating to PCIe were inspected:

``` bash
dmesg | grep -i pcie
```

The important result was:

``` text
brcm-pcie 1000110000.pcie: link down
```

The Raspberry Pi was attempting to initialize its external
PCIe interface, but no PCIe link was being established.

The internal PCIe interface showed:

``` text
brcm-pcie 1000120000.pcie: link up, 5.0 GT/s PCIe x4 (!SSC)
```

This confirmed to me that the Raspberry Pi itself was functioning normally and
narrowed the problem to the external PCIe connection between the Pi and the Waveshare HAT.

------------------------------------------------------------------------

## 5. PCIe Ribbon Cable Orientation

I inspected the PCIe ribbon cable more closely.

A black marking containing a small white arrow was present on the
ribbon. A corresponding white arrow was discovered on the expansion
board.

The ribbon cable was powered down, disconnected/reoriented, and
reinstalled so that the markings correctly aligned.

After powering the Raspberry Pi back on, the red power/status LED on the
Waveshare expansion board illuminated.

The PCIe devices were checked again:

``` bash
lspci
```

This time the output included:

``` text
0001:00:00.0 PCI bridge: Broadcom Inc. and subsidiaries BCM2712 PCIe Bridge (rev 30)
0001:01:00.0 USB controller: VIA Technologies, Inc. VL805/806 xHCI USB 3.0 Controller (rev 01)
0002:00:00.0 PCI bridge: Broadcom Inc. and subsidiaries BCM2712 PCIe Bridge (rev 30)
0002:01:00.0 Ethernet controller: Raspberry Pi Ltd RP1 PCIe 2.0 South Bridge
```

The important new device was:

``` text
VIA Technologies, Inc. VL805/806 xHCI USB 3.0 Controller
```

This confirmed that the Waveshare expansion board was successfully
communicating with the Raspberry Pi over PCIe! Yay.

The USB topology was checked:

``` bash
lsusb -t
```

The expansion controller exposed USB connectivity including a 5000M USB
3.x root hub.

------------------------------------------------------------------------

## 6. First Camera Detection

An Innomaker U20CAM-1080P-S1 camera was connected to the expansion
board.

The USB devices were inspected:

``` bash
lsusb
```

Relevant output:

``` text
Bus 001 Device 002: ID 2109:3431 VIA Labs, Inc. Hub
Bus 001 Device 003: ID 0c45:6366 Microdia Webcam Vitade AF
```

This demonstrated to me that the USB hub and camera were both visible to
Linux. 

Video devices were inspected:

``` bash
ls /dev/video*
```

The V4L2 device mapping was then examined:

``` bash
v4l2-ctl --list-devices
```

The first camera appeared as:

``` text
Innomaker-U20CAM-1080p-S1: Inno (usb-0001:01:00.0-1.2):
        /dev/video0
        /dev/video1
        /dev/media3
```

Additionally this also confirmed that the camera was connected through the new PCIe
USB controller.

------------------------------------------------------------------------

## 7. Five-Camera Enumeration Test

All five Innomaker cameras were connected.

The following command was used:

``` bash
v4l2-ctl --list-devices
```

All five cameras successfully enumerated:

``` text
Innomaker-U20CAM-1080p-S1: Inno (usb-0001:01:00.0-1.2):
        /dev/video0
        /dev/video1
        /dev/media3

Innomaker-U20CAM-1080p-S1: Inno (usb-0001:01:00.0-1.3):
        /dev/video2
        /dev/video3
        /dev/media4

Innomaker-U20CAM-1080p-S1: Inno (usb-0001:01:00.0-1.4):
        /dev/video4
        /dev/video5
        /dev/media5

Innomaker-U20CAM-1080p-S1: Inno (usb-xhci-hcd.0-2):
        /dev/video8
        /dev/video9
        /dev/media7

Innomaker-U20CAM-1080p-S1: Inno (usb-xhci-hcd.1-1):
        /dev/video6
        /dev/video7
        /dev/media6
```

Three cameras were connected through the Waveshare PCIe controller,
while two were connected through the Raspberry Pi's built-in USB
controllers.

The primary capture nodes were therefore expected to be:

``` text
/dev/video0
/dev/video2
/dev/video4
/dev/video6
/dev/video8
```

------------------------------------------------------------------------

## 8. Camera Format Investigation

An initial FFmpeg capture using automatic/default settings failed with:

``` text
ioctl(VIDIOC_STREAMON): Protocol error
```

The supported formats of `/dev/video0` were then inspected:

``` bash
v4l2-ctl -d /dev/video0 --list-formats-ext
```

The camera supports MJPEG at several resolutions, including:

``` text
MJPG
1920x1080 @ 30 fps
1280x960  @ 30 fps
1280x720  @ 30 fps
1024x576  @ 30 fps
800x600   @ 30 fps
640x480   @ 30 fps
```

It also supports YUYV, but 1920x1080 YUYV is limited to 5 fps. Not potentially ideal for my purposes but good to know.

The full V4L2 camera information was inspected:

``` bash
v4l2-ctl -d /dev/video0 --all
```

The camera was correctly detected using the Linux `uvcvideo` driver:

``` text
Driver name      : uvcvideo
Card type        : Innomaker-U20CAM-1080p-S1: Inno
Bus info         : usb-0001:01:00.0-1.2
Video Capture
Streaming
```

This confirmed to me that the camera and V4L2 driver were operating correctly.

------------------------------------------------------------------------

## 9. Successful 1080p Still Capture

Because the camera advertises native MJPEG at 1920x1080, I used FFmpeg explicitly configured to use that mode:

``` bash
ffmpeg -f v4l2 -input_format mjpeg -video_size 1920x1080 -i /dev/video0 -frames:v 1 camera1.jpg
```

FFmpeg was successful at capturing one frame:

``` text
Input #0, video4linux2,v4l2, from '/dev/video0':
  Stream #0:0: Video: mjpeg ..., 1920x1080, 30 fps

frame=    1
video:224KiB
```

A warning was produced because FFmpeg's `image2` output normally expects
a sequence filename, but the single JPEG was still successfully written.

------------------------------------------------------------------------

## 10. Transferring the Captured Image to the Development PC

The captured image was copied from the Raspberry Pi to the Windows
development computer using SCP.

From Windows PowerShell:

``` powershell
scp bfalco@Photogrammetry-Device.local:/home/bfalco/camera1.jpg .
```

The image was successfully transferred and visually inspected.

The resulting photograph was a valid 1920x1080 image. Amusingly, the
first camera's first successful photograph was pointed directly at one
of the other Innomaker cameras.

The image exhibited noticeable noise under the available indoor
lighting. This is expected to be addressed later through exposure, gain,
focus, lighting, and other camera-control tuning.

------------------------------------------------------------------------

## Session Result

This session successfully demonstrated the complete basic image
acquisition path:

``` text
Raspberry Pi 5
    ↓
External PCIe interface
    ↓
Waveshare PCIe to USB 3.2 Gen1 HAT+
    ↓
VIA VL805/806 xHCI USB controller
    ↓
Innomaker U20CAM-1080P-S1
    ↓
Linux UVC/V4L2
    ↓
FFmpeg
    ↓
1920×1080 MJPEG still image
    ↓
JPEG stored on Raspberry Pi
    ↓
SCP transfer over Ethernet/SSH
    ↓
Windows development computer
```

### Confirmed Working

-   Raspberry Pi 5 boots with the expansion HAT installed.
-   External PCIe interface enabled through `dtparam=pciex1`.
-   Waveshare PCIe-to-USB board detected.
-   VIA VL805/806 USB 3.0 controller detected.
-   USB hub detected.
-   Five Innomaker USB cameras enumerate simultaneously.
-   Cameras expose valid V4L2 capture devices.
-   Camera capabilities and controls can be queried.
-   1920×1080 MJPEG capture succeeds.
-   Captured JPEG can be transferred from the Raspberry Pi to the
    development PC over SCP.

------------------------------------------------------------------------

## Next Steps

For the next development session:

1.  Capture and inspect a still image from each of the five cameras.
2.  Verify reliable repeated capture from all five cameras.
3.  Determine stable camera identification independent of `/dev/videoX`
    numbering.
4.  Develop a script/application to trigger captures from all cameras
    automatically.
5.  Decide whether captures should be sequential or approximately
    simultaneous.
6.  Investigate camera exposure, gain, white balance, focus, and
    lighting configuration for photogrammetry.
7.  Establish a consistent image naming and directory structure for
    capture sessions.
8.  Test storage performance and capture latency.
9.  Later integrate image acquisition with the wider
    drone/photogrammetry pipeline.

------------------------------------------------------------------------

## Milestone

**First successful image captured by the Raspberry Pi 5 multi-camera
photogrammetry system!**

This session established that the core capture hardware is viable and
that the Raspberry Pi can communicate with the PCIe USB expansion
hardware and all five intended USB cameras.
