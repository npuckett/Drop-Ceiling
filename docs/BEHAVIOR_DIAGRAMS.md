# Drop Ceiling — Behavior System Diagrams

A visual walkthrough of how the Drop Ceiling light thinks, moves, and learns — from camera input to physical light output.

Each diagram builds on the previous one. If you're new to the project, read them in order. If a section feels abstract, use the **Wander Box** diagram as the anchor: it connects behavior decisions to spatial motion and ultimately to DMX output.

> All diagrams use [Mermaid](https://mermaid.js.org/) syntax and render natively on GitHub.

---

## 1. System Overview

The Drop Ceiling installation is a single simulated point light that moves above a grid of LED panels. Two cameras watch pedestrians below, and the light responds in real-time.

Data flows through six stages: two RTSP cameras capture video, YOLO detects people, calibration projects detections to real-world floor coordinates, cross-camera fusion and temporal tracking produce stable positions, the behavior system decides what the light should do, and Art-Net sends DMX values to the physical panels.

```mermaid
flowchart LR
    subgraph INPUT["Camera Input"]
        direction TB
        CAM1["<b>Camera 1 (Right)</b>
        ───────────────
        Model: Reolink RLC-520A
        Position: X=-30, Z=78
        IP: 10.42.0.75
        RTSP port 555
        Resolution: 2048 x 1536"]

        CAM2["<b>Camera 2 (Left)</b>
        ───────────────
        Model: Reolink RLC-520A
        Position: X=-270, Z=78
        IP: 10.42.0.172
        RTSP port 555
        Resolution: 2048 x 1536"]
    end

    subgraph DETECT["Detection and Calibration"]
        direction TB
        ROBUST["<b>RobustCamera</b>
        ───────────────
        Threads: 1 daemon per camera
        Buffer flush: grab() x3
        Reconnect: auto on failure"]

        YOLO["<b>YOLO 11n</b>
        ───────────────
        Input: 416px resize
        Class: person only
        Confidence: 0.10 - 0.80
        Output: bounding boxes"]

        CAL["<b>Calibration</b>
        ───────────────
        Method: ray-plane intersect
        Floor: Y = -66 cm
        Pre-computed: R_T, K_inv
        Output: world (X, Z) cm"]

        ROBUST --> YOLO --> CAL
    end

    subgraph TRACKING["Fusion and Tracking"]
        direction TB
        FUSE["<b>Cross-Camera Fusion</b>
        ───────────────
        Merge: different cameras only
        Threshold: 50 - 300 cm
        Method: greedy nearest-neighbor"]

        SMOOTH["<b>Temporal Tracking</b>
        ───────────────
        Velocity: prediction + correct
        EMA alpha: 0.01 - 0.20
        Prune: 60 frames lost"]

        FUSE --> SMOOTH
    end

    subgraph TRANSPORT["OSC Transport"]
        OSC["<b>OSC Output</b>
        ───────────────
        /tracker/count n
        /tracker/person/id x z
        Target: 127.0.0.1:7000
        Protocol: UDP, 25 Hz"]
    end

    subgraph BRAIN["Behavior Engine"]
        direction TB
        TRACK["<b>Person Manager</b>
        ───────────────
        Zone: active / passive classify
        Velocity: per-person tracking
        Dwell: time in zone
        Callbacks: enter / exit / move"]
        BEH["<b>Behavior System</b>
        ───────────────
        Mode: IDLE / ENGAGED / CROWD / FLOW
        Gestures: 16 types, phase-gated
        Personality: 6 meta sliders
        Learning: feedback + daily"]
        TRACK --> BEH
    end

    subgraph CONTROLLER["Light Controller"]
        direction TB
        LIGHT["<b>Point Light</b>
        ───────────────
        Position: x, y, z (cm)
        Constrained by: wander box
        Brightness: min / max range
        Falloff: radius (cm)
        Pulse: sine wave phase"]
        PANELS["<b>Panel System</b>
        ───────────────
        Layout: 4 units x 3 panels
        Calc: distance-based falloff
        Output: 12 DMX values (1-255)"]
        LIGHT --> PANELS
    end

    subgraph OUTPUT["Physical Output"]
        ARTNET["<b>Art-Net</b>
        ───────────────
        Protocol: Art-Net UDP
        Channels: 12 (Universe 0)
        Target: 10.42.0.200
        Rate: 30 FPS"]
        LEDS["<b>LED Panels</b>
        ───────────────
        Units: 4 ceiling-mounted
        Panels per unit: 3
        Control: single DMX ch each"]
        ARTNET --> LEDS
    end

    CAM1 --> ROBUST
    CAM2 --> ROBUST
    CAL -->|"world detections"| FUSE
    SMOOTH -->|"tracked (id, x, z)"| OSC
    OSC -->|"x, z per person"| TRACK
    BEH -->|"behavior_params dict
    brightness, speed, falloff,
    pulse, smoothing, wander_box"| LIGHT
    PANELS -->|"12 DMX values
    (1-255 per panel)"| ARTNET

    style INPUT fill:#1a1a2e,stroke:#e94560,color:#fff
    style DETECT fill:#16213e,stroke:#0f3460,color:#e0e1dd
    style TRACKING fill:#0f3460,stroke:#e94560,color:#fff
    style TRANSPORT fill:#1a1a2e,stroke:#0f3460,color:#fff
    style BRAIN fill:#1a1a2e,stroke:#16213e,color:#fff
    style CONTROLLER fill:#1a1a2e,stroke:#533483,color:#fff
    style OUTPUT fill:#1a1a2e,stroke:#e94560,color:#fff
```

Three Python files implement the system:

| File | Responsibility |
|---|---|
| `camera_tracker_osc.py` | Camera capture, YOLO detection, calibration, fusion, temporal tracking, OSC output |
| `light_behavior.py` | State machine, gestures, trend analysis, feedback learning |
| `lightController_osc.py` | Main loop, OSC input, point light, panel math, Art-Net output, auto-tuning |

---

## 2. Behavior Mode State Machine

The light is always in one of four modes. Mode determines the base personality — how fast it moves, how bright it shines, and whether it follows someone or wanders on its own.

Transitions are **not instantaneous**. Conditions must persist for a minimum duration (stickiness) before the mode switches, and parameters interpolate smoothly over a transition period.

```mermaid
flowchart LR
    START(( )) --> IDLE

    IDLE["**IDLE**
    ───────────────
    Trigger: no one in active zone
    Behavior: gentle wandering
    ───────────────
    Speed: 20 cm/s
    Brightness: 3-15
    Pulse: 4000 ms
    Falloff: 80 cm
    Smoothing: 0
    Wander box: full width (260cm)"]

    ENGAGED["**ENGAGED**
    ───────────────
    Trigger: 1-2 in active zone
    Behavior: follows nearest person
    ───────────────
    Speed: 25 cm/s
    Brightness: 8-30
    Pulse: 2500 ms
    Falloff: 50 cm
    Smoothing: 0.03
    Wander box: tight around person"]

    CROWD["**CROWD**
    ───────────────
    Trigger: 3+ in active zone
    Behavior: follows centroid
    ───────────────
    Speed: 60 cm/s
    Brightness: 12-45
    Pulse: 1500 ms
    Falloff: 40 cm
    Smoothing: 0.03
    Wander box: around group centroid"]

    FLOW["**FLOW**
    ───────────────
    Trigger: heavy passive traffic
    Behavior: drifts with crowd flow
    ───────────────
    Speed: 25 cm/s
    Brightness: 5-20
    Pulse: 3000 ms
    Falloff: 70 cm
    Smoothing: 0
    Wander box: shifted with traffic"]

    IDLE -->|"person enters active zone
    stickiness: 0s (immediate)
    transition: 0.8s"| ENGAGED

    IDLE -->|"15s sustained passive traffic
    transition: 2.0s"| FLOW

    ENGAGED -->|"5s after last person leaves
    transition: 3.0s (slow goodbye)"| IDLE

    ENGAGED -->|"3s with 3+ people
    transition: 0.5s (quick)"| CROWD

    CROWD -->|"5s after crowd thins
    transition: 2.0s"| ENGAGED

    CROWD -->|"5s after everyone leaves
    transition: 4.0s"| IDLE

    FLOW -->|"10s of low traffic
    transition: 3.0s"| IDLE

    FLOW -->|"person enters active zone
    stickiness: 0s (immediate)
    transition: 0.8s"| ENGAGED

    GUARD["**Mode Guard**
    ───────────────
    Min duration: 8 seconds
    prevents rapid flip-flopping"]

    GUARD -.-> IDLE
    GUARD -.-> ENGAGED
    GUARD -.-> CROWD
    GUARD -.-> FLOW

    style START fill:#e94560,stroke:#e94560,color:#fff
    style IDLE fill:#0d1b2a,stroke:#415a77,color:#e0e1dd
    style ENGAGED fill:#0f3460,stroke:#e94560,color:#fff
    style CROWD fill:#533483,stroke:#e94560,color:#fff
    style FLOW fill:#1b263b,stroke:#778da9,color:#e0e1dd
    style GUARD fill:#1a1a2e,stroke:#778da9,color:#e0e1dd
```

**Key design choice**: Engaging is fast (0.5–0.8s), disengaging is slow (2.0–4.0s). The light is eager to connect and reluctant to let go.

---

## 3. MetaParameters → Actual Light Values

The personality system consists of **6 sliders** (0.0–1.0) that define the light's character and **6 global multipliers** that scale the output. Together they transform the mode base values into the light's actual behavior.

```mermaid
flowchart LR
    subgraph SLIDERS["Personality Sliders (0.0 - 1.0)"]
        RESP["<b>responsiveness</b><br/>───────────<br/>Low: contemplative, slow<br/>High: reactive, quick"]
        ENER["<b>energy</b><br/>───────────<br/>Low: calm, gentle<br/>High: lively, dynamic"]
        ATTN["<b>attention_span</b><br/>───────────<br/>Low: easily distracted<br/>High: focused, loyal"]
        SOCI["<b>sociability</b><br/>───────────<br/>Low: reserved, withdrawn<br/>High: eager to engage"]
        EXPL["<b>exploration</b><br/>───────────<br/>Low: stays in place<br/>High: wanders widely"]
        MEMO["<b>memory</b><br/>───────────<br/>Low: forgets quickly<br/>High: avoids repetition"]
    end

    subgraph OUTPUTS["Output Parameters"]
        SPEED["<b>move_speed</b><br/>───────────<br/>Range: x0.6 - x1.4<br/>Unit: cm/s"]
        FOLLOW["<b>follow_smoothing</b><br/>───────────<br/>Range: 0.03 - 0.20<br/>0 = no follow"]
        PULSE["<b>pulse_speed</b><br/>───────────<br/>Range: x1.3 - x0.7<br/>Unit: ms period"]
        BRIGHT["<b>brightness</b><br/>───────────<br/>Range: x0.7 - x1.3<br/>Unit: DMX (1-255)"]
        WANDER["<b>wander_interval</b><br/>───────────<br/>Range: x1.5 - x0.5<br/>Unit: seconds"]
        GESTURE["<b>gesture frequency</b><br/>───────────<br/>Range: x1.5 - x0.5<br/>Unit: interval (s)"]
        ANTIREP["<b>anti-repetition</b><br/>───────────<br/>Strength: 0.0 - 1.0<br/>Suppresses repeats"]
    end

    RESP -->|"lerp"| SPEED
    RESP -->|"lerp"| FOLLOW
    ENER -->|"lerp"| PULSE
    ENER -->|"lerp"| BRIGHT
    EXPL -->|"lerp"| WANDER
    SOCI -->|"lerp"| GESTURE
    ATTN -->|"weight"| GESTURE
    MEMO -->|"scale"| ANTIREP

    subgraph MULTIPLIERS["Global Multipliers (default 1.0)"]
        BG["<b>brightness_global</b><br/>range: 0.2 - 5.0"]
        SG["<b>speed_global</b><br/>range: 0.2 - 2.0"]
        PG["<b>pulse_global</b><br/>range: 0.3 - 3.0"]
        FG["<b>follow_speed_global</b><br/>range: 0.5 - 3.0"]
        DI["<b>dwell_influence</b><br/>range: 0.0 - 2.0"]
        TW["<b>trend_weight</b><br/>range: 0.0 - 2.0"]
    end

    BG -->|"x"| BRIGHT
    SG -->|"x"| SPEED
    PG -->|"x"| PULSE
    FG -->|"x"| FOLLOW
    DI -.->|"scales dwell<br/>bonus layer"| BRIGHT
    TW -.->|"scales trend<br/>response layer"| SPEED

    style SLIDERS fill:#16213e,stroke:#0f3460,color:#e0e1dd
    style OUTPUTS fill:#1a1a2e,stroke:#e94560,color:#fff
    style MULTIPLIERS fill:#533483,stroke:#0f3460,color:#e0e1dd
```

**Example**: With `responsiveness = 0.8` and `speed_global = 1.2`:
- Base mode speed is 20 cm/s (IDLE)
- Responsiveness maps to ×1.24 (lerp between 0.6 and 1.4 at 0.8)
- Global multiplier applies: 20 × 1.24 × 1.2 = **29.8 cm/s**

---

## 4. AutoTuning Feedback Loop

The `AutoTuningManager` runs every 5 seconds and continuously adjusts the personality parameters based on observed activity. The key insight is **asymmetric adjustment**: personality sliders are only pushed *up* when activity is high — they're never pushed down. Only mean reversion gently brings them back toward home values.

```mermaid
flowchart TB
    subgraph SENSE["Sense (every 5s)"]
        ACT["<b>Read Activity Levels</b><br/>───────────────<br/>short_activity: 5 min window<br/>medium_activity: 30 min window<br/>long_activity: 1 hour window"]
        AGG["<b>Read Aggression State</b><br/>───────────────<br/>level: 0-1 (EMA smoothed)<br/>seconds_since_engagement: int"]
    end

    subgraph COMPUTE["Compute"]
        TARGET["<b>Adaptive Target</b><br/>───────────────<br/>Method: rolling median<br/>Samples: ~500 (~42 min)<br/>Clamp: 0.03 - 0.40<br/>Purpose: relative busy/quiet"]
        EXCESS["<b>Activity Excess</b><br/>───────────────<br/>Formula: short_activity<br/>minus adaptive_target<br/>Positive = busier than normal<br/>Negative = quieter than normal"]
        ACT --> TARGET --> EXCESS
        AGG --> EXCESS
    end

    subgraph DELTAS["Calculate Deltas"]
        PERS_UP["<b>Personality (up only)</b><br/>───────────────<br/>Params: responsiveness, energy, sociability<br/>When busy: pushed UP<br/>When quiet: NOT pushed down<br/>Max step: 0.03 per cycle"]
        DISP_INV["<b>Display (inverse)</b><br/>───────────────<br/>Params: brightness, speed, pulse globals<br/>When busy: decrease (personality handles it)<br/>When quiet: increase (compensates)<br/>Max step: 0.08 per cycle"]
        EXPL_Q["<b>Exploration</b><br/>───────────────<br/>When quiet: increase (search more)<br/>When busy: decrease (stay focused)<br/>Max step: 0.03 per cycle"]
        EXCESS --> PERS_UP
        EXCESS --> DISP_INV
        EXCESS --> EXPL_Q
    end

    subgraph ADJUST["Adjust and Constrain"]
        REVERT["<b>Mean Reversion</b><br/>───────────────<br/>Target: home values (defaults)<br/>Strength: 0.02 + 0.06 x distance<br/>Type: progressive (stronger when far)<br/>Always active"]
        CURIOSITY["<b>Curiosity Perturbation</b><br/>───────────────<br/>Interval: every 30 seconds<br/>Strength: 0.015<br/>Bias: 60% toward home values<br/>Purpose: explore parameter space"]
        BUDGET["<b>Budget Gate</b><br/>───────────────<br/>Cost: sum(abs(deltas)) x 60<br/>Restore: over ~300 seconds<br/>Effect: scales down changes when depleted<br/>Purpose: prevents runaway drift"]
        CLAMP["<b>Clamp</b><br/>───────────────<br/>Safe floors: prevent zombie light<br/>Soft caps: prevent obnoxious behavior<br/>Hard range: per-parameter min/max<br/>Min step: 0.002 (below = zeroed)"]
        PERS_UP --> REVERT
        DISP_INV --> REVERT
        EXPL_Q --> REVERT
        REVERT --> CURIOSITY --> BUDGET --> CLAMP
    end

    CLAMP --> APPLY["<b>Apply</b><br/>───────────────<br/>Target: MetaParameters<br/>Also: sync slider UI positions"]

    APPLY --> META["<b>MetaParameters</b><br/>───────────────<br/>6 personality sliders<br/>6 global multipliers<br/>Updated for next frame"]

    META -.->|"personality shapes<br/>behavior output"| SENSE

    subgraph DAILY["Daily Learning (midnight)"]
        direction LR
        SNAP["<b>End-of-Day Snapshot</b><br/>───────────────<br/>60% final value<br/>40% midpoint of range"]
        DB["<b>Persist</b><br/>───────────────<br/>Stored per time-of-day<br/>period in database"]
        LOAD["<b>Next Startup</b><br/>───────────────<br/>Load learned values<br/>Blend: 30% toward learned"]
        SNAP --> DB --> LOAD
    end

    CLAMP -.->|"parameter journeys<br/>logged all day"| SNAP
    LOAD -.->|"learned home values"| TARGET

    style SENSE fill:#0d1b2a,stroke:#1b263b,color:#e0e1dd
    style COMPUTE fill:#1b263b,stroke:#415a77,color:#e0e1dd
    style DELTAS fill:#415a77,stroke:#778da9,color:#e0e1dd
    style ADJUST fill:#778da9,stroke:#e0e1dd,color:#0d1b2a
    style DAILY fill:#533483,stroke:#e94560,color:#fff
    style META fill:#e94560,stroke:#fff,color:#fff
```

**Tuned parameters and their constraints:**

| Parameter | Min | Max | Safe Floor | Soft Cap | Home |
|---|---|---|---|---|---|
| responsiveness | 0.0 | 1.0 | 0.30 | 0.90 | 0.50 |
| energy | 0.0 | 1.0 | 0.25 | 0.85 | 0.45 |
| attention_span | 0.0 | 1.0 | 0.10 | — | 0.50 |
| sociability | 0.0 | 1.0 | 0.20 | — | 0.45 |
| exploration | 0.0 | 1.0 | 0.15 | — | 0.40 |
| memory | 0.0 | 1.0 | — | — | 0.30 |
| brightness_global | 0.2 | 5.0 | 0.60 | 3.0 | 1.20 |
| speed_global | 0.2 | 2.0 | 0.35 | 1.6 | 0.70 |
| pulse_global | 0.3 | 3.0 | 0.35 | 2.0 | 0.80 |
| follow_speed_global | 0.5 | 3.0 | 0.60 | — | 1.00 |
| dwell_influence | 0.0 | 2.0 | — | — | 0.50 |
| idle_trend_weight | 0.0 | 2.0 | 0.10 | — | 0.40 |

---

## 5. Light Position → Panel DMX Output

The final stage converts the virtual point light into 12 physical DMX values. The `PanelSystem` models the exact physical layout: 4 lighting units at different X positions, each containing 3 LED panels at different angles.

```mermaid
flowchart TB
    subgraph LIGHT["Virtual Point Light"]
        POS["Position (x, y, z)<br/>constrained by wander box"]
        PULSE["Pulse Phase<br/>sin(phase) oscillation<br/>period = pulse_speed"]
        BRANGE["Brightness Range<br/>brightness_min → brightness_max"]
        FALLOFF["Falloff Radius<br/>40 – 80 cm"]
    end

    subgraph LAYOUT["Physical Panel Layout (top view)"]
        direction LR
        U0["Unit 0<br/>X = −30"]
        U1["Unit 1<br/>X = −110"]
        U2["Unit 2<br/>X = −190"]
        U3["Unit 3<br/>X = −270"]
    end

    subgraph UNIT_DETAIL["Each Unit: 3 Panels"]
        P1["Panel 1 (top)<br/>Y=90, Z=0<br/>faces down"]
        P2["Panel 2 (lower-left)<br/>Y=30, Z=12<br/>angled 22.5°"]
        P3["Panel 3 (lower-right)<br/>Y=30, Z=−12<br/>angled −22.5°"]
    end

    subgraph CALC["Per-Panel Calculation (×12)"]
        DIST["distance = ‖panel_center − light.position‖"]
        CHECK{"distance ><br/>falloff_radius?"}
        OFF["Panel OFF<br/>DMX = 1"]
        FALL["falloff = 1.0 − distance / falloff_radius"]
        INTENSITY["intensity = (sin(phase) + 1) / 2<br/>oscillates 0.0 – 1.0"]
        COMBINE["final = falloff × intensity"]
        DMX["dmx = brightness_min +<br/>final × (brightness_max − brightness_min)<br/>clamped 1 – 255"]
    end

    POS --> DIST
    FALLOFF --> CHECK
    DIST --> CHECK
    CHECK -->|"Yes"| OFF
    CHECK -->|"No"| FALL
    PULSE --> INTENSITY
    FALL --> COMBINE
    INTENSITY --> COMBINE
    BRANGE --> DMX
    COMBINE --> DMX

    subgraph OUTPUT["Art-Net Output"]
        direction LR
        CHANNELS["Channel Map:<br/>CH1: U0-P1 · CH2: U0-P2 · CH3: U0-P3<br/>CH4: U1-P1 · CH5: U1-P2 · CH6: U1-P3<br/>CH7: U2-P1 · CH8: U2-P2 · CH9: U2-P3<br/>CH10: U3-P1 · CH11: U3-P2 · CH12: U3-P3"]
        SEND["Art-Net UDP → 10.42.0.200<br/>Universe 0 · 30 FPS"]
    end

    DMX --> CHANNELS --> SEND

    style LIGHT fill:#533483,stroke:#e94560,color:#fff
    style LAYOUT fill:#1b263b,stroke:#415a77,color:#e0e1dd
    style UNIT_DETAIL fill:#16213e,stroke:#0f3460,color:#e0e1dd
    style CALC fill:#415a77,stroke:#778da9,color:#e0e1dd
    style OUTPUT fill:#e94560,stroke:#fff,color:#fff
```

**The brightness equation in plain language:**

1. Measure the distance from the light to each panel's center point
2. If the panel is outside the falloff radius, it's off (DMX = 1)
3. Otherwise, compute a falloff factor: closer panels are brighter (linear decay)
4. Multiply the falloff by the current pulse intensity (a sine wave that breathes between 0 and 1)
5. Map the result into the brightness range and convert to a DMX byte (1–255)

---

## 6. Wander Box: Behavior Inputs to Spatial Motion

The wander box is a 3D bounding volume that constrains where the virtual point light can move. Every behavior modifier — flow direction, aggression, engagement contraction — works by reshaping this box, not by steering the light directly.

The box uses a three-layer animation system: `current_wander_box` reflects the raw mode and modifier state, `animated_wander_box` smooths that with an exponential lerp (~95% converged in one second), and `WanderBehavior` picks random points inside the animated box at timed intervals.

```mermaid
flowchart TB
    subgraph BASE ["Base Wander Box (IDLE Default)"]
        BASEBOX["**Default Dimensions**
        ───────────────
        X: -290 to -30 cm
        Y: 0 to 150 cm
        Z: -32 to 28 cm
        Source: light_behavior.py
        Covers: full panel array width"]
    end

    subgraph MODIFIERS ["Behavior Modifiers to Target Box"]
        FLOW["**Flow Positioning**
        ───────────────
        Mode: IDLE only
        Effect: shift X +/-60 cm
        Source: flow_balance trend
        Direction: follows crowd flow"]

        AGG["**Aggression**
        ───────────────
        Mode: IDLE only
        Z expand: +40 cm
        Y expand: +30 cm
        Wander interval: faster
        Trigger: high aggression param"]

        ENGAGE["**Engagement Contraction**
        ───────────────
        Mode: ENGAGED
        Method: contract around people
        1 person: +/-15cm X, +/-35cm Y,
        +/-15cm Z centered on them
        2 people: 70/30 weighted center
        3+: centroid of all positions
        Y offset: +100 cm"]

        MOMENTUM["**Flow Momentum**
        ───────────────
        Mode: FLOW
        Effect: shift X up to +/-40 cm
        Source: flow velocity
        Applied to: current box"]

        DRIFT["**Almost-Engaged Drift**
        ───────────────
        Phase: engagement candidate
        Effect: shift X +/-50 cm
        Direction: toward candidate
        Blended with: engagement timer"]
    end

    subgraph LERP ["Three-Layer Animation"]
        CURRENT["**current_wander_box**
        ───────────────
        Role: base + mode modifiers
        Updates: per calculate_parameters
        Reflects: mode and trend state"]

        ANIMATED["**animated_wander_box**
        ───────────────
        Role: smoothed version of current
        Lerp speed: 3.0 (exponential)
        Convergence: ~95% in 1 second
        Method: per-axis exponential lerp
        dt-scaled for frame rate"]

        CURRENT -->|"exponential lerp"| ANIMATED
    end

    subgraph WANDER ["WanderBehavior Output"]
        PICK["**Random Target Selection**
        ───────────────
        Trigger: wander_interval timer
        Base interval: 2.0 - 5.0s
        Exploration scale: x0.5 to x1.5
        Target: random point inside
        animated_wander_box bounds"]

        MOVE["**Position Lerp**
        ───────────────
        Method: 3% per-frame lerp
        Smoothing: continuous motion
        Override: gesture targets
        Output: smooth (x, y, z)"]

        PICK --> MOVE
    end

    subgraph LIGHTOUT ["To Light System (see Diagram 5)"]
        POINTLIGHT["**PointLight.update()**
        ───────────────
        Input: wander position
        Speed: move_speed param
        Effect: virtual light moves
        through 3D panel space"]

        PANEL["**PanelSystem**
        ───────────────
        Distance: light to each panel
        Falloff: linear within radius
        Result: 12 DMX brightness values"]

        POINTLIGHT --> PANEL
    end

    BASE --> CURRENT
    FLOW --> CURRENT
    AGG --> CURRENT
    ENGAGE --> CURRENT
    MOMENTUM --> CURRENT
    DRIFT --> CURRENT
    ANIMATED --> PICK
    MOVE --> POINTLIGHT

    style BASE fill:#1b263b,stroke:#415a77,color:#e0e1dd
    style MODIFIERS fill:#533483,stroke:#e94560,color:#fff
    style LERP fill:#16213e,stroke:#0f3460,color:#e0e1dd
    style WANDER fill:#0f3460,stroke:#e94560,color:#fff
    style LIGHTOUT fill:#0d1b2a,stroke:#415a77,color:#e0e1dd
    style BASEBOX fill:#1b263b,stroke:#415a77,color:#e0e1dd
    style FLOW fill:#533483,stroke:#e94560,color:#fff
    style AGG fill:#533483,stroke:#e94560,color:#fff
    style ENGAGE fill:#533483,stroke:#e94560,color:#fff
    style MOMENTUM fill:#533483,stroke:#e94560,color:#fff
    style DRIFT fill:#533483,stroke:#e94560,color:#fff
    style CURRENT fill:#16213e,stroke:#0f3460,color:#e0e1dd
    style ANIMATED fill:#16213e,stroke:#0f3460,color:#e0e1dd
    style PICK fill:#0f3460,stroke:#e94560,color:#fff
    style MOVE fill:#0f3460,stroke:#e94560,color:#fff
    style POINTLIGHT fill:#0d1b2a,stroke:#415a77,color:#e0e1dd
    style PANEL fill:#0d1b2a,stroke:#415a77,color:#e0e1dd
```

### Worked Example: IDLE vs ENGAGED

| Stage | IDLE (no active person) | ENGAGED (1 active person) |
|---|---|---|
| Mode baseline | `move_speed=20`, `wander_interval=5.0`, `falloff=80` | `move_speed=25`, `wander_interval=4.0`, `falloff=50`, `follow_smoothing=0.03` |
| Wander box behavior | Uses broader base box, chooses exploratory targets | Contracts and anchors around person; target updates stay close |
| Position path | Slower, wider drift across full panel span | Tighter, more deliberate tracking near person position |
| DMX result | Wider illumination spread, gentler panel transitions | More localized hotspots, stronger panel contrast, faster local changes |

### Mini Scenario: Passive Flow Shifts Panel Emphasis (10–20s)

A common street condition: people move through the passive zone mostly left-to-right while nobody is actively engaged. The behavior system treats that as directional flow pressure and shifts wander preference toward the incoming side.

```mermaid
flowchart LR
    T0["t=0s<br/>No active person<br/>Mode: IDLE or FLOW candidate"] --> T1["t=0..10s<br/>Passive detections accumulate<br/>flow tracker updates (~1.5s)"]
    T1 --> T2["t~10..15s<br/>Sustained direction signal<br/>(passive_rate + flow_direction)"]
    T2 --> T3["Wander box: nudge center<br/>in flow direction"]
    T3 --> T4["Target picks bias<br/>toward shifted side"]
    T4 --> T5["Light path drifts to flow side<br/>over multiple updates"]
    T5 --> T6["Nearest panels on that side<br/>brighten more often"]
    T6 --> T7["Observed output: directional<br/>DMX emphasis without hard switch"]

    style T0 fill:#0d1b2a,stroke:#415a77,color:#e0e1dd
    style T1 fill:#1b263b,stroke:#415a77,color:#e0e1dd
    style T2 fill:#415a77,stroke:#778da9,color:#e0e1dd
    style T3 fill:#0f3460,stroke:#e94560,color:#fff
    style T4 fill:#0f3460,stroke:#e94560,color:#fff
    style T5 fill:#533483,stroke:#e94560,color:#fff
    style T6 fill:#533483,stroke:#e94560,color:#fff
    style T7 fill:#e94560,stroke:#fff,color:#fff
```

---

## 7. Engagement Lifecycle

A complete person interaction from arrival to departure, showing which systems activate at each stage.

```mermaid
sequenceDiagram
    participant P as Person
    participant Z as Zone Classification
    participant B as Behavior System
    participant G as Gesture System
    participant L as Light Output

    Note over P,L: ── Person Approaches ──

    P->>Z: Enters passive zone
    Z->>B: passive_count += 1
    B->>G: Trigger ACKNOWLEDGE
    G->>L: Brief move toward passerby

    Note over P,L: ── Person Enters Active Zone ──

    P->>Z: Crosses into active zone
    Z->>B: active_count += 1
    B->>B: Mode: IDLE → ENGAGED (immediate)
    Note over B: Wander box contracts around person
    B->>G: Trigger WELCOME
    G->>L: Entry pulse: +25 brightness flash
    B->>L: Transition interpolation (0.8s)

    rect rgb(30, 40, 70)
        Note over B,L: NOTICE PHASE (0–3s)
        B->>L: Light turns toward person
        B->>L: Brightness ramping up
        Note right of G: No positional gestures yet
    end

    rect rgb(40, 50, 90)
        Note over B,L: GREET PHASE (3–10s)
        B->>L: Brightness increase settled
        B->>L: Breathing overlay begins ramping in (8s ramp)
        loop Every 8–15s
            G->>L: NOD (1.2s, most common)
            G->>L: LEAN (1.5s, leaning in)
            G->>L: BREATHE (4.0s, shared rhythm)
        end
    end

    rect rgb(50, 60, 110)
        Note over B,L: ENGAGE PHASE (10–30s)
        B->>L: Breathing at full depth (±12% brightness, ±6% radius)
        B->>L: Tighter tracking, brighter output
        loop Every 10–20s
            G->>L: SWAY (3.0s, lateral oscillation)
            G->>L: ORBIT (4.0s, lazy circle)
            G->>L: BREATHE (5.0s, deeper)
            G->>L: NOD / LEAN (carried forward)
        end
    end

    rect rgb(60, 70, 130)
        Note over B,L: BOND PHASE (30s+)
        B->>L: Maximum intimacy
        B->>L: Very settled, infrequent gestures
        loop Every 15–30s
            G->>L: SWAY (4.0s)
            G->>L: ORBIT (5.0s)
            G->>L: SETTLE (3.0s, tighten in closer)
            G->>L: BREATHE (6.0s)
        end
    end

    Note over P,L: ── Person Leaves ──

    P->>Z: Exits active zone
    Z->>B: active_count = 0
    B->>B: Start 5s stickiness timer

    alt Dwell was > 5s and no one remains
        B->>G: Trigger FAREWELL
        G->>L: Reluctant move toward last position
    end

    Note over B: 5s passes with no one...
    B->>B: Mode: ENGAGED → IDLE
    Note over B: Wander box expands to full 260cm width
    B->>L: Transition interpolation (3.0s slow goodbye)
    B->>L: Breathing overlay ramps out
    B->>L: Return to gentle wandering within full wander box
```

**What the person experiences:**

1. Walking past, the light briefly acknowledges them — a subtle flicker of awareness
2. Stepping under the panels, the light immediately locks on with a welcoming pulse
3. Standing still, they notice the light beginning to breathe — a slow shared rhythm
4. After 10 seconds, the light starts to sway and orbit gently, as if comfortable in their presence
5. After 30 seconds, the light settles in close — maximum intimacy, minimal movement
6. Walking away, the light lingers, reluctantly following their last position before slowly fading back to its wandering state

---

## 8. How Everything Connects

The complete system with all feedback loops visible at once — inputs, processing layers, adaptation loops, and outputs.

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

---

## Terms

| Term | Definition |
|---|---|
| **Active zone** | The area directly under the panels (~2m deep) where people are treated as engaging with the installation. |
| **Passive zone** | The sidewalk traffic area beyond the active zone (~2.7m deep) that can influence behavior without direct engagement. |
| **Wander box** | The current allowed movement boundary for the light target (`min/max x,y,z`), continuously updated by behavior context. |
| **Meta parameters** | Personality sliders (0–1) and global multipliers that reshape mode defaults. |
| **Auto-tuning** | The 5-second adjustment loop that updates meta parameters based on observed activity. |
| **Falloff radius** | How far from the virtual light position panels still receive illumination. The single most impactful parameter on visual output. |
| **Dwell phase** | One of four progressive engagement stages (Notice → Greet → Engage → Bond) based on how long a person remains in the active zone. |
| **Aggression** | A 0–1 value that rises when the light has not engaged anyone for a while. Causes wider, more active wandering to attract attention. |
| **Flow tracking** | The 1.5-second loop that measures pedestrian direction and speed through the passive zone, expressed as direction (-1 to +1) and strength (0–1). |

---

*This is a condensed version of the full 19-diagram set in the development repository. For the complete set including the 17-layer parameter pipeline, multi-timescale adaptation, and detailed camera tracking diagrams, see the development repository.*

---

See also: [Behavior System Reference](BEHAVIOR_SYSTEM.md) for full prose documentation, [How It Works](HOW_IT_WORKS.md) for an accessible overview.
