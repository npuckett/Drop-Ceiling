![Drop Ceiling Front View](images/dropCeiling-frontView.jpg)

## [View Live Installation → thedropceiling.com](https://thedropceiling.com)

# Drop Ceiling

**Drop Ceiling** is an open-source interactive light installation that transforms standard office ceiling panels into a responsive, learning artwork. Four lighting units — each built from three 2 ft × 2 ft LED ceiling lights joined by 3D-printed connectors — hang in a street-level window. A pair of security cameras watch the sidewalk below, and a real-time computer vision system translates pedestrian movement into animated light behavior using only open data protocols.

The light has a personality. When no one is around it wanders gently, pulsing and drifting. When someone stops beneath the panels it locks on, brightens, and begins to breathe in rhythm with them. Over days and weeks an auto-tuning system adjusts the light's character to match the patterns of the site — learning when people are likely to stop, which attraction strategies work, and how energetic to be at different times of day.

No images of people are stored or transmitted. The vision system outputs only anonymous floor-plane coordinates.

---

## Documentation

| Document | Description |
|----------|-------------|
| **[How It Works](docs/HOW_IT_WORKS.md)** | Accessible overview of the installation — what visitors experience, the four behavior modes, and how the light learns over time |
| **[Behavior System](docs/BEHAVIOR_SYSTEM.md)** | Complete technical reference for modes, gestures, dwell phases, personality sliders, trend analysis, and feedback learning |
| **[Behavior Diagrams](docs/BEHAVIOR_DIAGRAMS.md)** | Visual architecture walkthrough — 8 Mermaid diagrams covering the full pipeline from camera to DMX |
| **[Software Guide](docs/SOFTWARE_GUIDE.md)** | Application reference — hotkeys, slider parameters, OSC messages, database schema, and configuration files |
| **[Hardware](docs/HARDWARE.md)** | Physical build details — panel units, wiring, DMX decoder, cameras, and network topology |
| **[Production Setup](docs/PRODUCTION_SETUP.md)** | Deployment guide — systemd services, Tailscale Funnel, monitoring, and maintenance |

### Additional Resources

| Resource | Description |
|----------|-------------|
| [Public Viewer README](public-viewer/README.md) | Three.js real-time 3D viewer — deployment, WebSocket protocol, Tailscale configuration |
| [Calibration Guide](calibration/CALIBRATION_GUIDE.md) | ArUco marker placement and multi-camera calibration process |

---

## Quick Start

```bash
# 1. Clone and set up
git clone https://github.com/your-username/Drop-Ceiling.git
cd Drop-Ceiling
python3 -m venv .venv && source .venv/bin/activate
pip install torch ultralytics opencv-python-headless python-osc pygame PyOpenGL stupidArtnet websockets numpy

# 2. Calibrate cameras (one-time, on-site)
cd calibration
python camera_calibration.py    # Press C → A for auto-calibration

# 3. Run the system (two terminals)
cd IO
python camera_tracker_osc.py    # Terminal 1: tracks people, sends OSC
python lightController_osc.py   # Terminal 2: receives OSC, outputs Art-Net + WebSocket
```

See [Production Setup](docs/PRODUCTION_SETUP.md) for 24/7 deployment with systemd.

---

## Architecture

```mermaid
flowchart TB
    CAM["<b>Camera + YOLO + Fusion</b><br/>───────────────<br/>Cameras: 2x Reolink RLC-520A<br/>Capture: threaded RTSP, 2048x1536<br/>Detection: YOLO 11n (416px resize)<br/>Calibration: ray-plane to floor<br/>Fusion: cross-camera merge (150cm)<br/>Tracking: EMA smooth, velocity pred<br/>Output: OSC /tracker/person/id x z"] -->|"OSC x,z<br/>25 Hz UDP"| TRACKER["<b>Person Manager</b><br/>───────────────<br/>Zone: active / passive classify<br/>Tracking: velocity, dwell time"]

    TRACKER -->|"active/passive counts<br/>person positions"| BEHAVIOR["<b>Behavior System</b><br/>───────────────<br/>Mode: state machine<br/>Dwell: phase tracking<br/>Gestures: event + interaction"]

    TRACKER -->|"zone crossings<br/>per timescale"| TRENDS["<b>Trend Analysis</b><br/>───────────────<br/>Windows: 1m / 5m / 30m / 1h<br/>Output: activity weights"]

    TRACKER -->|"velocity vectors"| FLOWTRACK["<b>Flow Tracking</b><br/>───────────────<br/>Direction: -1 to +1<br/>Strength: 0 to 1<br/>Window: 30s, update 1.5s"]

    TRENDS -->|"activity weights<br/>anticipation, energy"| BEHAVIOR
    FLOWTRACK -->|"flow direction"| BEHAVIOR

    TRENDS -->|"short_activity<br/>medium, long"| AUTOTUNE["<b>AutoTuning Manager</b><br/>───────────────<br/>Cycle: every 5 seconds<br/>Params: 12 (6 sliders + 6 globals)<br/>Method: adaptive target + deltas"]

    BEHAVIOR -->|"aggression state"| AUTOTUNE

    AUTOTUNE -->|"adjusted values"| META["<b>MetaParameters</b><br/>───────────────<br/>Personality: 6 sliders (0-1)<br/>Globals: 6 multipliers"]

    META -->|"personality +<br/>global multipliers"| BEHAVIOR

    BEHAVIOR -->|"behavior_params<br/>7 output values"| POINTLIGHT["<b>Point Light</b><br/>───────────────<br/>Position: x, y, z<br/>Brightness: min/max<br/>Falloff: radius<br/>Pulse: phase"]

    BEHAVIOR -->|"wander_box bounds"| WANDERBOX["<b>Wander Box</b><br/>───────────────<br/>Spatial constraint for position<br/>Shape: mode + flow + aggression<br/>Animation: exponential lerp"]

    WANDERBOX -->|"position target"| POINTLIGHT

    POINTLIGHT -->|"light state"| PANELSYS["<b>Panel System</b><br/>───────────────<br/>Panels: 12 (4 units x 3)<br/>Calc: distance to DMX"]

    PANELSYS -->|"12 DMX channels"| ARTNET["<b>Art-Net Output</b><br/>───────────────<br/>Target: 10.42.0.200<br/>Universe: 0 / Rate: 30 FPS"]

    POINTLIGHT -->|"state snapshot"| WEBSOCKET["<b>WebSocket Broadcast</b><br/>───────────────<br/>Server: port 8765<br/>Protocol: WSS via Tailscale Funnel<br/>Payload: JSON (light pos,<br/>brightness, panels, people, mode)<br/>Rate: ~15 FPS"]

    WEBSOCKET -->|"JSON state updates<br/>auto-reconnect 3s"| VIEWER["<b>Public 3D Viewer</b><br/>───────────────<br/>Engine: Three.js + OrbitControls<br/>Renders: light sphere, 12 panels,<br/>tracked people, wander box,<br/>trackzone boundaries<br/>Hosting: GitHub Pages<br/>Access: mobile-first web app<br/>Source: public-viewer/"]

    BEHAVIOR -->|"engagement context<br/>snapshots"| FEEDBACK["<b>Feedback Learning</b><br/>───────────────<br/>Buffer: 50 contexts<br/>Dims: position x time x flow<br/>Rate: +/-0.02 per event"]

    FEEDBACK -->|"learned weights"| BEHAVIOR

    AUTOTUNE -->|"parameter journey<br/>end-of-day"| DAILY["<b>Daily Learning</b><br/>───────────────<br/>Compute: optimal starts<br/>Granularity: per time-of-day"]

    DAILY -->|"learned home values<br/>30% blend on startup"| AUTOTUNE

    DAILY -->|"daily report"| DB[("<b>Tracking Database</b><br/>───────────────<br/>Hourly stats, learnings,<br/>engagement history")]

    TRENDS -->|"raw events"| DB
    DB -->|"historical patterns"| TRENDS
    DB -->|"7-day weighted avg"| DAILY

    TOD["<b>Time of Day</b><br/>───────────────<br/>Maps: hour to period<br/>Scales: brightness, pulse,<br/>wander Y, aggression cap"] -->|"modifiers"| BEHAVIOR

    style CAM fill:#e94560,stroke:#fff,color:#fff
    style ARTNET fill:#e94560,stroke:#fff,color:#fff
    style WEBSOCKET fill:#533483,stroke:#e94560,color:#fff
    style VIEWER fill:#16213e,stroke:#0f3460,color:#e0e1dd
    style META fill:#e94560,stroke:#fff,color:#fff
    style DB fill:#0d1b2a,stroke:#415a77,color:#e0e1dd
    style AUTOTUNE fill:#533483,stroke:#e94560,color:#fff
    style DAILY fill:#1b263b,stroke:#415a77,color:#e0e1dd
    style FEEDBACK fill:#1b263b,stroke:#415a77,color:#e0e1dd
```

### Network Ports

| Port | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| 7000 | OSC/UDP | Tracker → Controller | Person positions (x, z) at 25 Hz |
| 6454 | Art-Net/UDP | Controller → DMX Decoder | 12 panel brightness values at 30 FPS |
| 8765 | WebSocket/TCP | Controller → Public Viewer | JSON state updates at ~15 FPS |
| 555 | RTSP/TCP | Cameras → Tracker | H.264 video streams |

### Protocols

**Input — RTSP Camera Feeds**: The system uses standard PoE security cameras broadcasting via [RTSP](https://en.wikipedia.org/wiki/Real_Time_Streaming_Protocol). Drop Ceiling uses two [Reolink RLC-520A](https://reolink.com/product/rlc-520a/) cameras chosen for low-light performance and wide field of view. Feeds are processed with [YOLO v11](https://docs.ultralytics.com/) for person detection. [ArUco markers](https://docs.opencv.org/4.x/d5/dae/tutorial_aruco_detection.html) placed at known floor positions provide the calibration transform from pixel coordinates to real-world centimeters. Cross-camera fusion merges overlapping detections into a unified coordinate stream at ~15–20 Hz.

**Output — DMX over Art-Net**: Panel brightness values are sent as [Art-Net](https://art-net.org.uk/) DMX data. A standard DMX decoder receives the signals and a voltage divider circuit converts the 0–12V PWM output to the 0–10V dimming protocol used by LED ceiling panels.

---

## Repository Structure

| Directory | Contents |
|-----------|----------|
| [`IO/`](IO/) | Core runtime — light controller, camera tracker, behavior system, tracking database, pedestrian simulator, systemd services |
| [`calibration/`](calibration/) | ArUco marker images, calibration guide, camera calibration data, CUDA-optimized tracker variant |
| [`public-viewer/`](public-viewer/) | Three.js web app — real-time 3D visualization of panels, light, and tracked people via WebSocket |
| [`3dprintFiles/`](3dprintFiles/) | Panel connector designs — Fusion 360 source, STL exports, ready-to-print 3MF/GCode |
| [`DMXtest/`](DMXtest/) | Art-Net diagnostic utility for validating panel addressing |
| [`docs/`](docs/) | Project documentation — behavior reference, diagrams, software guide, hardware, deployment |

---

## License

MIT License
