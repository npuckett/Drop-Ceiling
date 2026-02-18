# Drop Ceiling — Hardware

Physical build details, wiring, and network topology for the Drop Ceiling installation.

---

## Overview

The installation consists of four lighting units suspended in a street-level window, two PoE security cameras mounted above, and a single Linux computer running the tracking and behavior software. All components communicate over a local 10.42.0.x Ethernet network.

---

## Lighting Units

### Physical Layout

Four identical units hang side-by-side, spanning approximately 260 cm:

```
     Unit 0        Unit 1        Unit 2        Unit 3
     X = −30       X = −110      X = −190      X = −270
    ┌───────┐     ┌───────┐     ┌───────┐     ┌───────┐
    │ P1    │     │ P1    │     │ P1    │     │ P1    │   ← top panel (Y=90, faces down)
    ├───┬───┤     ├───┬───┤     ├───┬───┤     ├───┬───┤
    │P2 │P3 │     │P2 │P3 │     │P2 │P3 │     │P2 │P3 │   ← lower panels (Y=30, angled ±22.5°)
    └───┴───┘     └───┴───┘     └───┴───┘     └───┴───┘
```

Each unit contains **3 panels** (2 ft × 2 ft LED ceiling light panels):

| Panel | Position | Orientation |
|-------|----------|-------------|
| P1 (top) | Y = 90 cm, Z = 0 | Faces straight down |
| P2 (lower-left) | Y = 30 cm, Z = +12 cm | Angled 22.5° outward |
| P3 (lower-right) | Y = 30 cm, Z = −12 cm | Angled −22.5° outward |

### 3D-Printed Connectors

Panels within each unit are joined by custom 3D-printed connectors. Print files are in the [`3dprintFiles/`](../3dprintFiles/) directory:

| Directory | Contents |
|-----------|----------|
| `STL Files/` | Print-ready STL files (left and right middle connectors) |
| `Fusion Files/` | Editable Fusion 360 source files |
| `3MF and GCode/` | Pre-sliced print files |

### Panel Specifications

- **Type**: Standard 2 ft × 2 ft LED flat panel ceiling light
- **Dimming**: 0–10V analog input (controlled by DMX decoder)
- **DMX range**: 1–255 per channel (1 = minimum glow, never fully off)
- **Maximum DMX**: 212 (corresponds to 10V output from 12V decoder; prevents over-driving)

---

## DMX Control Chain

```
lightController_osc.py
        │
        │  Art-Net UDP packets
        │  Universe 0, 12 channels
        │  30 FPS
        ▼
DMX Decoder (10.42.0.200)
        │
        │  12x 0-10V analog signals
        │  (DMX 1-255 → 0-10V)
        ▼
LED Panel Dimming Inputs
        │
        │  Panels 1-12
        ▼
Physical Light Output
```

### DMX Channel Map

| Channel | Unit | Panel | Position |
|---------|------|-------|----------|
| CH 1 | Unit 0 | P1 (top) | X = −30 |
| CH 2 | Unit 0 | P2 (lower-left) | X = −30 |
| CH 3 | Unit 0 | P3 (lower-right) | X = −30 |
| CH 4 | Unit 1 | P1 (top) | X = −110 |
| CH 5 | Unit 1 | P2 (lower-left) | X = −110 |
| CH 6 | Unit 1 | P3 (lower-right) | X = −110 |
| CH 7 | Unit 2 | P1 (top) | X = −190 |
| CH 8 | Unit 2 | P2 (lower-left) | X = −190 |
| CH 9 | Unit 2 | P3 (lower-right) | X = −190 |
| CH 10 | Unit 3 | P1 (top) | X = −270 |
| CH 11 | Unit 3 | P2 (lower-left) | X = −270 |
| CH 12 | Unit 3 | P3 (lower-right) | X = −270 |

### DMX Decoder Configuration

- **IP Address**: 10.42.0.200 (static, on the local PoE network)
- **Protocol**: Art-Net (UDP port 6454)
- **Universe**: 0
- **Channels**: 12
- **Output**: 0–10V analog per channel
- **Supply voltage**: 12V DC (output maxes at 10V via DMX value 212)

---

## Cameras

### Specifications

| Property | Value |
|----------|-------|
| **Model** | Reolink RLC-520A |
| **Quantity** | 2 |
| **Resolution** | 2048 × 1536 |
| **Connection** | Power over Ethernet (PoE) |
| **Protocol** | RTSP on port 555 |
| **Detection model** | YOLO 11n (416px input resize) |

### Camera Positions

| Camera | IP Address | World Position | Field of View |
|--------|-----------|----------------|---------------|
| Camera 1 (Right) | 10.42.0.75 | X = −30, Z = 78 cm | Covers right side of panel array |
| Camera 2 (Left) | 10.42.0.172 | X = −270, Z = 78 cm | Covers left side of panel array |

Cameras are mounted above the panel units, angled down toward the sidewalk. Their overlapping fields of view enable cross-camera fusion for more accurate tracking.

### Calibration

Cameras are calibrated using ArUco markers placed at known positions on the floor. The calibration process computes a ray-plane intersection matrix that maps pixel coordinates to world floor coordinates (Y = −66 cm plane). See [Calibration Guide](../calibration/CALIBRATION_GUIDE.md) for the full process.

---

## Tracking Zones

Two zones are defined in `world_coordinates.json`:

```
                    ← 260 cm →
    ┌──────────────────────────────────────┐
    │          ACTIVE ZONE (~2m deep)      │  ← directly under panels
    │  People here trigger ENGAGED mode    │
    ├──────────────────────────────────────┤
    │         PASSIVE ZONE (~2.7m deep)    │  ← sidewalk traffic area
    │  Pedestrians here influence FLOW     │
    └──────────────────────────────────────┘
              (street / sidewalk)
```

| Zone | Depth | Effect |
|------|-------|--------|
| Active | ~2 m | People treated as engaging with the installation; triggers ENGAGED or CROWD mode |
| Passive | ~2.7 m | Pedestrian traffic contributes to flow tracking and trend analysis without direct engagement |

---

## Network Topology

```
                    Internet
                       │
                       │ Tailscale (remote SSH + Funnel)
                       ▼
               ┌───────────────┐
               │    cvtower     │
               │  (Linux PC)    │
               │  GPU: NVIDIA   │
               │  10.42.0.1     │
               │                │
               │  Runs:         │
               │  • camera_     │
               │    tracker_osc │
               │  • light       │
               │    Controller  │
               │    _osc        │
               └───────┬───────┘
                       │
                       │  Ethernet (macOS Internet Sharing / PoE switch)
                       │
            ┌──────────┼──────────┐
            │          │          │
            ▼          ▼          ▼
     ┌───────────┐ ┌───────┐ ┌───────────┐
     │ Camera 1  │ │ Camera│ │DMX Decoder│
     │ 10.42.0.75│ │   2   │ │10.42.0.200│
     │ RTSP:555  │ │10.42  │ │ Art-Net   │
     │           │ │.0.172 │ │ UDP:6454  │
     └───────────┘ └───────┘ └───────────┘
                                  │
                                  │ 12x 0-10V
                                  ▼
                           ┌────────────┐
                           │ LED Panels │
                           │ 4 units    │
                           │ × 3 panels │
                           └────────────┘
```

### Network Ports

| Port | Protocol | Direction | Purpose |
|------|----------|-----------|---------|
| 555 | RTSP | Camera → cvtower | Video stream from each camera |
| 7000 | OSC/UDP | tracker → controller | Person positions (internal, localhost) |
| 6454 | Art-Net/UDP | cvtower → decoder | DMX light values |
| 8765 | WebSocket | cvtower → internet | Real-time state for public viewer |

### IP Address Summary

| Device | IP Address | Notes |
|--------|-----------|-------|
| cvtower (production PC) | 10.42.0.1 | Static, runs all software |
| Camera 1 (Right) | 10.42.0.75 | PoE, RTSP |
| Camera 2 (Left) | 10.42.0.172 | PoE, RTSP |
| DMX Decoder | 10.42.0.200 | Art-Net receiver |

---

## Computer (cvtower)

### Minimum Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | NVIDIA with CUDA | Modern NVIDIA (for YOLO 11n at 25 Hz) |
| RAM | 8 GB | 16 GB |
| Storage | 20 GB | 50 GB (for extended database history) |
| Network | Gigabit Ethernet | Gigabit Ethernet |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

### Software Stack

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.10+ | Runtime |
| PyTorch | CUDA build | GPU inference for YOLO |
| Ultralytics | Latest | YOLO 11n model |
| OpenCV | With CUDA | Video capture and processing |
| python-osc | — | OSC messaging (tracker → controller) |
| PyOpenGL | — | 3D visualization |
| Pygame | — | Window management |
| stupidArtnet | — | Art-Net DMX output |
| websockets | — | Real-time public viewer feed |
| Tailscale | — | Remote access and Funnel |

---

## Bill of Materials

| Item | Qty | Purpose |
|------|-----|---------|
| 2 ft × 2 ft LED flat panel ceiling light (0–10V dimmable) | 12 | Light panels (3 per unit) |
| 3D-printed connectors (see `3dprintFiles/`) | 8 | Join panels within each unit |
| Art-Net to 0–10V DMX decoder (12 channel) | 1 | Convert network data to analog dimming |
| Reolink RLC-520A PoE camera | 2 | Person tracking |
| PoE switch or PoE injectors | 1 | Power cameras over Ethernet |
| Linux PC with NVIDIA GPU | 1 | Runs all software |
| Ethernet cables (Cat5e or better) | 4+ | Network connections |
| Ceiling suspension hardware | — | Hooks, cables, or T-bar clips |
| 12V DC power supply | 1 | Powers DMX decoder |

---

See also: [Production Setup](PRODUCTION_SETUP.md) for deployment and service management, [Software Guide](SOFTWARE_GUIDE.md) for application reference, [How It Works](HOW_IT_WORKS.md) for an accessible system overview.
