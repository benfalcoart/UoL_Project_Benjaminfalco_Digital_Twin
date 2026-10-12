## 18 September 2026

Today was primarily focused on the administrative and logistical
preparation required for the upcoming fieldwork, particularly arranging
the required insurance and coordinating potential research dates.

I followed up with Mark Gora at Fena Insurance regarding the commercial
general liability insurance required for the proposed fieldwork at
Bruce's Caves. I confirmed that the likely fieldwork dates would now be
**27--29 September**, depending on weather and other practical
considerations. Mark advised that the request is somewhat unusual for
insurers because the research is non-commercial, short-term, and does
not generate revenue. Several underwriters have been approached, but a
suitable policy has not yet been confirmed.

I also indicated that I would consider an annual insurance policy if a
short-term policy cannot be arranged and if doing so would make
obtaining coverage easier. However, the potential cost of an annual
policy is a concern given the limited duration of the fieldwork and the
remaining project timeline. I also asked whether an intermediate option,
such as a two- or three-month policy, might be possible.

Further communication was undertaken regarding alternative fieldwork
locations and scheduling. This is becoming increasingly important
because the remaining project timeline is relatively short, and
sufficient time needs to remain after data collection for
reconstruction, material-classification experiments, comparison of the
different processing pipelines, and evaluation of the results.

The remainder of today's development work focused on the **BEHOLDER
capture system**. The immediate goal remains to have the system
substantially completed and ready for use **by the end of this
weekend**. This will allow field testing to begin at the locations where
permission has already been obtained rather than waiting for the
outstanding Bruce's Caves insurance arrangements to be resolved.

Development continued late into the evening of 18 September and into the
early morning of 19 September. The first objective was to validate the
five-camera USB capture hardware and begin implementing a reliable
software abstraction for controlling it.

All five Innomaker USB cameras were connected to the Raspberry Pi 5 and
inspected using V4L2. Each physical camera was found to expose multiple
`/dev/video*` interfaces. The usable image-capture interfaces were
identified as `/dev/video0`, `/dev/video2`, `/dev/video4`,
`/dev/video6`, and `/dev/video8`. Testing confirmed support for
**1920×1080 MJPEG capture at 30 FPS**.

Initial captures were performed directly using `v4l2-ctl`. All five
cameras successfully produced 1080p JPEG images. During one test, a
camera initially returned a `VIDIOC_STREAMON` protocol error, but a
subsequent retry succeeded. This provided useful evidence that the
production capture system should include retry handling rather than
assuming that every hardware capture request will succeed on its first
attempt.

A new `CameraManager` Python component was implemented. Rather than
hard-coding the five current cameras, the manager automatically searches
the available `/dev/video*` devices and identifies usable cameras by
checking their V4L2 capabilities. Devices are accepted when they provide
MJPEG and 1920×1080 capture. This allows BEHOLDER to scale to different
numbers of connected cameras without changing the capture code. Testing
correctly discovered all five current cameras while excluding their
secondary video interfaces and the Raspberry Pi's internal video
devices.

Individual camera capture was implemented with configurable retry and
timeout behaviour. Each capture records a history of its attempts,
including whether the attempt succeeded, the process return code, and
any reported error. This preserves information from multiple failed
attempts instead of retaining only the final error and should make field
failures considerably easier to diagnose. Timeouts were also added so
that an unresponsive camera cannot indefinitely freeze the capture
process.

Concurrent multi-camera capture was then implemented using Python's
`ThreadPoolExecutor`. Each detected camera is assigned its own capture
task, allowing the cameras to begin capturing at approximately the same
time instead of being triggered sequentially. A hardware test
successfully produced images from all five cameras concurrently. The
resulting files were:

-   Camera 1: 224 KB
-   Camera 2: 101 KB
-   Camera 3: 208 KB
-   Camera 4: 148 KB
-   Camera 5: 141 KB

All five images were successfully written. Dedicated validation scripts
are now being maintained in a `Tests` directory within the Raspberry Pi
project so that tests can be reproduced and referenced during the final
evaluation and report. Planned testing includes camera discovery,
concurrent capture, repeated stress testing, and power-consumption
measurements.

Work also began on integrating the Waveshare UPS HAT into BEHOLDER's
monitoring system. The Raspberry Pi's I²C interface was enabled and an
I²C scan detected devices at addresses `0x40` and `0x42`. Waveshare's
reference INA219 software was downloaded and tested against the
installed UPS HAT. The manufacturer's script successfully reported
approximately **7.86 V**, **−0.41 A**, **3.2 W**, and **77.5% estimated
battery charge**.

The Waveshare implementation was inspected to determine the INA219
register configuration, calibration constants, and battery-percentage
calculation. The reported percentage is a linear estimate based on
battery voltage between 6.0 V and 8.4 V and should therefore be
considered an approximate state-of-charge indicator rather than a
precise measurement of remaining capacity.

A custom INA219 driver was subsequently implemented under
`API/hardware/ina219.py`. This provides a clean hardware abstraction for
BEHOLDER rather than depending directly on Waveshare's demonstration
script. The driver communicates with the UPS HAT over I²C and returns a
structured `BatteryReading` containing voltage, current, power, and
estimated battery percentage.

A dedicated `battery_monitor_test.py` validation script was added to the
repository and successfully tested on BEHOLDER. The custom
implementation reported:

``` text
Voltage:    7.768 V
Current:    -0.5093 A
Power:      3.958 W
Percentage: 73.7%
```

These results are consistent with the earlier readings obtained using
Waveshare's reference implementation, validating communication between
the custom BEHOLDER software and the UPS hardware.

At the end of the development session, BEHOLDER can automatically
discover compatible connected cameras, capture 1920×1080 images from all
five cameras concurrently, retry failed captures, prevent camera
operations from hanging indefinitely, and directly obtain battery
voltage, current, power, and estimated charge information from the UPS
HAT.

The next development work will integrate the new battery driver into
`system_monitor.py`, develop repeatable camera stress tests to quantify
reliability over hundreds of captures, and measure capture timing and
power consumption. These components can then be integrated with the main
BEHOLDER API and user interface.

Overall, the day began primarily with work intended to remove logistical
risks surrounding fieldwork but concluded with substantial progress on
the capture hardware and software itself. Insurance remains the largest
outstanding external dependency, but BEHOLDER's core capture and
battery-monitoring systems are now operational. Completing and
validating the remaining software over the weekend should allow field
testing to proceed at already-approved locations while the Bruce's Caves
arrangements continue independently.
