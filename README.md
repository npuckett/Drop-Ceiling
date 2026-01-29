## [View Live Installation → www.thedropceiling.com](https://www.thedropceiling.com)

# Drop Ceiling
'Drop Ceiling' implements an open-source hardware and software system to transform ubiquitous office lighting into an interactive installation. It responds to the movement and position of people on the sidewalk using a Computer Vision system created from an array of standard security cameras. The installation showcases new methods of playful re-use via open data protocols.

Each lighting unit is constructed from three 2 ft × 2ft LED ceiling lights that are connected via 3D printed connectors. A custom hardware controller dynamically adjusts the brightness of each panel by interfacing with its standard 0 – 10V dimming protocol. All four of the units are networked together to allow them to uniformly respond to the position information from the Computer Vision system. The vision system utilizes the standard Real Time Streaming Protocol (RTSP) available in security cameras to create a custom tracking model that is focused on data privacy. Over time, the panels will develop an animated language to communicate with passers-by throughout the day and night.


## Protocols

### Input

#### RTSP Camera Feeds
The system uses standard PoE security cameras. While these are often designed to work with proprietary NVRs, many also have the ability to broadcast using the standard [Real Time Streaming Protocol (RTSP)](https://en.wikipedia.org/wiki/Real_Time_Streaming_Protocol). This open protocol can be read by most any programming language. Drop Ceiling uses 2 [Reolink RLC-520A](https://reolink.com/product/rlc-520a/) cameras. These were chosen for their good low-light performance, wide field of view, and decent framerate. Others have higher resolution, but this isn't useful for tracking.

#### Synthesis and Calibration
The feeds are processed first using [YOLOv11](https://docs.ultralytics.com/), a real-time object detection model optimized for identifying people in the frame. Each camera produces independent 2D detections with bounding boxes and confidence scores.

To translate these 2D pixel coordinates into a shared 3D world coordinate system, the installation uses [ArUco markers](https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html)—square fiducial markers from the OpenCV library that encode unique IDs in their black and white patterns. Four markers are placed at known positions in the physical space, typically on the floor at measured distances. During calibration, each camera detects these markers and computes a homography matrix that maps its 2D image plane to the real-world ground plane.

Because the two cameras have overlapping fields of view, their detections must be reconciled. The system uses spatial proximity matching: when two cameras detect people in the same region, detections within a configurable distance threshold are merged into a single tracked individual. Each camera's contribution is weighted by detection confidence and viewing angle. The result is a unified coordinate stream with X/Z positions in centimeters, updated at approximately 15–20Hz depending on network conditions and processing load.

### Output

#### DMX over Art-Net
The brightness of each LED panel is sent in real-time as DMX data over the [Art-Net protocol](https://art-net.org.uk/). A standard DMX decoder receives the signals and a voltage divider circuit converts the 0–12V PWM signal into the standard 0–10V dimming protocol used by most LED ceiling panels.

## Operating Software
This repo contains all source code for Drop Ceiling. This includes: Calibration software and methods, Computer Vision tracking system, Lighting control software, and 3D printing files. 

### `/IO`
Core runtime software for the installation. The **Light Controller** (`lightController_osc.py`) serves as the central nervous system — receiving tracked positions via OSC, computing panel brightness using a virtual point light model, and outputting DMX values via Art-Net. It includes a sophisticated **Behavior System** (`light_behavior.py`) that transitions between personality modes (Idle, Engaged, Crowd, Flow) based on pedestrian activity, creating an animated language that evolves throughout the day. The **Camera Tracker** (`camera_tracker_osc.py`) performs real-time person detection from RTSP camera feeds using CUDA-accelerated YOLO inference, broadcasting positions via OSC. A **Tracking Database** (`tracking_database.py`) logs movement patterns for behavioral analysis, while a **Pedestrian Simulator** (`pedestrian_simulator.py`) enables testing without live camera feeds. Includes production utilities for 24/7 operation via systemd.

### `/calibration`
Tools and assets for calibrating the Computer Vision system. Contains ArUco marker images placed at known physical positions within the tracking zone, along with camera calibration data. The **Calibration Guide** documents the multi-camera setup process, including homography transforms that map pixel coordinates to real-world centimeters. Includes a CUDA-optimized tracker variant and the YOLO model weights used for person detection.

### `/public-viewer`
A Three.js web application that displays the real-time state of the installation via WebSocket. Renders the 12 LED panels as 3D boxes with dynamic brightness, visualizes tracked people as avatars, and shows the virtual point light with its falloff radius. Connects to the installation via Tailscale Funnel for secure public access. Features orbit controls for camera navigation and displays the current behavior mode and status text.

### `/3dprintFiles`
Design files for the physical panel connectors. Includes Fusion 360 source files for parametric editing, STL exports for slicing, and ready-to-print 3MF/GCode files. These 3D printed parts connect standard 2ft × 2ft LED ceiling panels into the angled three-panel units that comprise the installation.

### `/DMXtest`
Diagnostic utility for testing Art-Net communication with the DMX lighting controllers. The `artnetTest.py` script validates network connectivity and panel addressing before full system deployment.

## License

MIT License
