# Development Diary — August 20, 2026

Today was a lighter development day focused primarily on hardware preparation and safety.

I 3D printed a protective cover for the Raspberry Pi's GPIO pins. Since the pins are exposed in the current BEHOLDER assembly, the cover will help protect both the pins themselves and anyone handling the device during assembly and field use.

I also charged all four sets of lithium-ion batteries in preparation for testing the BEHOLDER's power system.

Finally, I began considering the overall design of the BEHOLDER's outer shell. Current possibilities include a square enclosure, a spherical design, or a polygonal enclosure. The final geometry will largely depend on the angles and positions selected for the cameras, since the shell will need to provide appropriate mounting surfaces while maintaining the desired overlapping fields of view.

**Next Steps**
- Determine the desired camera positions and viewing angles.
- Select an enclosure geometry based on the camera arrangement.
- Begin measuring the hardware and modelling the BEHOLDER shell.
- Test the Raspberry Pi and UPS system using the charged batteries.

# BEHOLDER API Development

Later, I began development of the API that will be used to communicate with the BEHOLDER system while operating it in the field. The goal is to create an Android application for my phone that can connect directly to the Raspberry Pi and provide a simple interface for controlling and monitoring the system.

I created the initial API using FastAPI. The API currently includes a status endpoint that can report information about the Raspberry Pi, including CPU temperature, remaining storage space, detected camera devices, battery status, and a timestamp. Some of the hardware monitoring functionality, particularly the battery information from the UPS HAT, still needs to be implemented and tested on the Raspberry Pi.

I also created a capture endpoint. The endpoint currently starts an asynchronous simulated capture operation rather than communicating with the cameras directly. This allows me to develop and test the API communication and application architecture before integrating the actual multi-camera capture system.

WebSocket support was also added so that BEHOLDER can send real-time events back to connected clients. The current simulated capture process broadcasts events when a capture begins, when individual cameras complete their captures, and when the overall capture operation is complete. This will eventually allow the Android application to provide immediate feedback while I am operating the system.

The purpose of the Android application is to avoid needing to directly interact with the Raspberry Pi while collecting data. In the field, particularly when the camera system is mounted on the telescopic pole, I should be able to use my phone to check the state of the system, monitor important hardware information, initiate captures, and receive confirmation that the cameras successfully completed the capture.

The API is currently an early prototype, but the basic REST and WebSocket communication architecture is now in place. The next stage will be integrating the endpoints with the actual camera capture code and UPS HAT telemetry, followed by development of the Android client.