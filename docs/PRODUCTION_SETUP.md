# Drop Ceiling — Production Setup

Complete guide for deploying the Drop Ceiling installation on a Linux production machine.

**Deployment method**: SSH into the production machine via Tailscale, pull from the repository, and manage services with systemd.

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Remote Access](#remote-access)
3. [Initial Setup](#initial-setup)
4. [Python Environment](#python-environment)
5. [Camera Calibration](#camera-calibration)
6. [Network Configuration](#network-configuration)
7. [Service Installation](#service-installation)
8. [Tailscale Funnel Setup](#tailscale-funnel-setup)
9. [Testing & Verification](#testing--verification)
10. [Monitoring & Logs](#monitoring--logs)
11. [Troubleshooting](#troubleshooting)
12. [Maintenance](#maintenance)
13. [Quick Reference](#quick-reference)

---

## System Requirements

### Hardware

- **GPU**: NVIDIA with CUDA support (for YOLO tracking at 25 Hz)
- **RAM**: 8 GB minimum, 16 GB recommended
- **Storage**: 20 GB for OS + application + logs
- **Network**: Ethernet to PoE switch for cameras

See [Hardware](HARDWARE.md) for full physical build details.

### Software

- Ubuntu 22.04 LTS (or similar Linux distribution)
- Python 3.10+
- NVIDIA drivers + CUDA toolkit
- Tailscale (for remote access and Funnel)

### Network

| Device | IP Address | Purpose |
|--------|-----------|---------|
| Production machine | 10.42.0.1 | Runs all software |
| Camera 1 (Right) | 10.42.0.75 | RTSP video stream |
| Camera 2 (Left) | 10.42.0.172 | RTSP video stream |
| DMX Decoder | 10.42.0.200 | Art-Net → 0–10V |

---

## Remote Access

### SSH via Tailscale

```bash
# Connect using Tailscale IP or hostname
ssh dc@100.x.x.x
ssh dc@cvtower
```

### Verify Connection

```bash
hostname        # Should show production machine name
nvidia-smi      # Should show GPU and driver version
```

---

## Initial Setup

### 1. Update Repository

```bash
cd /home/nick/Documents/Github/dc-dev
git pull origin main
```

### 2. Verify NVIDIA GPU

```bash
nvidia-smi
# Should show GPU model and driver version
```

### 3. BIOS Configuration

Ensure these are set (one-time):
- **Power Recovery**: Always On (auto-start after power loss)
- **Wake on LAN**: Disabled (unless needed)

---

## Python Environment

### 1. Create Virtual Environment

```bash
cd /home/nick/Documents/Github/dc-dev
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install --upgrade pip

# Core dependencies
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install ultralytics
pip install opencv-python-headless
pip install python-osc
pip install numpy

# Light controller dependencies
pip install pygame PyOpenGL PyOpenGL_accelerate
pip install stupidArtnet
pip install websockets

# Verify CUDA
python -c "import torch; print('CUDA:', torch.cuda.is_available())"
```

### 3. Download YOLO Model

```bash
cd IO
python -c "from ultralytics import YOLO; YOLO('yolo11n.pt')"
```

---

## Camera Calibration

Calibration must be done on-site with the physical cameras. See the [Calibration Guide](../calibration/CALIBRATION_GUIDE.md) for full details.

### Quick Steps

1. **Print markers** — ArUco markers 0–6, 15 cm size (files in `calibration/`)
2. **Place markers** on the floor at known positions
3. **Run calibration**:
   ```bash
   source .venv/bin/activate
   cd calibration
   python camera_tracker_cuda.py
   ```
4. Press `C` for calibration mode, then `A` for auto-calibration
5. **Verify** the output file: `calibration/camera_calibration.json`

---

## Network Configuration

### Static IP for Production Machine

Edit `/etc/netplan/01-network.yaml`:

```yaml
network:
  version: 2
  ethernets:
    eth0:
      addresses:
        - 10.42.0.1/24
      routes:
        - to: default
          via: 10.42.0.254
      nameservers:
        addresses: [8.8.8.8, 8.8.4.4]
```

Apply:

```bash
sudo netplan apply
```

### Verify Devices

```bash
# Camera RTSP streams
ffprobe rtsp://admin:password@10.42.0.75:555/h264Preview_01_main
ffprobe rtsp://admin:password@10.42.0.172:555/h264Preview_01_main

# DMX decoder
ping 10.42.0.200
```

---

## Service Installation

### 1. Review Service Files

Verify paths in the service configuration:

```bash
cat IO/systemd/camera-tracker.service
cat IO/systemd/light-controller.service
```

Key settings to check:
- `User` — your Linux username
- `WorkingDirectory` — path to the IO/ directory
- `ExecStart` — path to the Python executable in the venv

### 2. Install Services

```bash
cd /home/nick/Documents/Github/dc-dev/IO/systemd
sudo chmod +x install-services.sh
sudo ./install-services.sh
```

### 3. Start Services

```bash
# Start in order (camera tracker must start first)
sudo systemctl start camera-tracker
sleep 5
sudo systemctl start light-controller
sudo systemctl start tailscale-funnel
```

### 4. Verify

```bash
# Quick status
./status.sh

# Detailed status
sudo systemctl status camera-tracker light-controller
```

---

## Tailscale Funnel Setup

Tailscale Funnel exposes the WebSocket server on port 8765 to the public internet via HTTPS, enabling the [public viewer](../public-viewer/) to receive real-time data.

### 1. Install Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo systemctl enable --now tailscaled
```

### 2. Authenticate

```bash
sudo tailscale up
# Follow the URL to authenticate in your browser
```

### 3. Enable Funnel in Admin Console

1. Navigate to: https://login.tailscale.com/admin/acls
2. Add to your ACL policy:
   ```json
   {
     "nodeAttrs": [
       {"target": ["*"], "attr": ["funnel"]}
     ]
   }
   ```

### 4. Start Funnel

```bash
sudo systemctl start tailscale-funnel
```

### 5. Get Your Public URLs

```bash
tailscale funnel status
```

### Connection Details

Once running, the public WebSocket endpoint is available at:

| Setting | Value |
|---------|-------|
| **Machine Name** | `cvtower` |
| **Tailscale IP** | `100.81.227.53` |
| **Public HTTPS URL** | `https://cvtower.tail830204.ts.net/` |
| **WebSocket URL** | `wss://cvtower.tail830204.ts.net/` |
| **Local Port** | `8765` |

### JavaScript Connection

```javascript
const socket = new WebSocket('wss://cvtower.tail830204.ts.net/');

socket.onopen = () => console.log('Connected to Drop Ceiling');
socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    // data contains: light position, brightness, panels, people, mode
};
```

### Funnel Management

```bash
tailscale funnel status               # Check status
sudo tailscale funnel --https=443 off # Disable
sudo tailscale funnel --bg 8765       # Re-enable
```

---

## Testing & Verification

### 1. Test Camera Tracker

```bash
journalctl -u camera-tracker -f

# Expected output:
# ✅ Model loaded!
# 📹 Connecting to cameras...
# ✓ Camera 1 connected
# 📡 OSC output: 127.0.0.1:7000
```

### 2. Test Light Controller

```bash
journalctl -u light-controller -f

# Expected output:
# 📡 OSC server listening on 0.0.0.0:7000
# 🌐 WebSocket server started on port 8765
# 📥 OSC: messages received
```

### 3. Test WebSocket

```bash
# From another machine (install: cargo install websocat)
websocat wss://cvtower.tail830204.ts.net/
# Should receive continuous JSON state updates
```

### 4. Test Public Viewer

Open in a browser:

```
https://yourusername.github.io/Drop-Ceiling/public-viewer/?ws=wss://cvtower.tail830204.ts.net/
```

---

## Monitoring & Logs

### View Live Logs

```bash
# All services
journalctl -u camera-tracker -u light-controller -f

# Single service
journalctl -u camera-tracker -f
journalctl -u light-controller -f

# Last hour
journalctl -u camera-tracker --since "1 hour ago"
```

### System Resources

```bash
nvidia-smi -l 1    # GPU usage (updates every second)
htop               # CPU and memory
```

### Log Rotation

Configure retention in `/etc/systemd/journald.conf`:

```ini
[Journal]
SystemMaxUse=1G
MaxRetentionSec=7day
```

---

## Troubleshooting

### Service Won't Start

```bash
journalctl -u camera-tracker -n 100 --no-pager
```

Common causes:
- Python path wrong (verify `.venv` location in service file)
- Missing dependencies (re-run `pip install`)
- GPU not available (check `nvidia-smi`)

### Camera Connection Failed

```bash
# Test RTSP directly
ffplay rtsp://admin:password@10.42.0.75:555/h264Preview_01_main

# Check network
ping 10.42.0.75
```

### Art-Net Not Working

```bash
ping 10.42.0.200              # Check decoder reachable
sudo ufw status               # Check firewall
```

### WebSocket Connection Refused

```bash
tailscale funnel status                # Check Funnel
sudo systemctl status light-controller # Check service
ss -tlnp | grep 8765                   # Check port
```

### Service Keeps Restarting

```bash
# Check restart count
systemctl show camera-tracker --property=NRestarts

# Reset and retry
sudo systemctl reset-failed camera-tracker
sudo systemctl start camera-tracker
```

### Display / OpenGL Issues (Headless Server)

```bash
# Option 1: Virtual framebuffer
sudo apt install xvfb
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

# Option 2: Dummy video driver (add to service file)
Environment="SDL_VIDEODRIVER=dummy"
```

---

## Maintenance

### Automatic (Daily)

- Services auto-restart on crash (systemd `Restart=always`)
- Logs rotate via journald
- Database auto-prunes raw data older than 48 hours (aggregated stats kept forever)

### Weekly

```bash
df -h                                                             # Disk space
journalctl --disk-usage                                           # Log size
journalctl -u camera-tracker -u light-controller | grep -i "failed"  # Check for issues
```

### Monthly

```bash
sudo apt update && sudo apt upgrade   # System packages
pip list --outdated                    # Python packages (update carefully)
```

### After Power Outage

Services auto-start. Verify via SSH:

```bash
ssh dc@cvtower
./dc-dev/IO/systemd/status.sh
```

### Updating Code

```bash
# From local machine — stop, pull, restart
ssh dc@cvtower "cd ~/Documents/Github/dc-dev && \
  sudo systemctl stop camera-tracker light-controller && \
  git pull && \
  sudo systemctl start camera-tracker light-controller"
```

---

## Quick Reference

### Service Commands

| Action | Command |
|--------|---------|
| Start all | `sudo systemctl start camera-tracker light-controller tailscale-funnel` |
| Stop all | `sudo systemctl stop camera-tracker light-controller` |
| Restart all | `sudo systemctl restart camera-tracker light-controller` |
| Status | `./IO/systemd/status.sh` |
| Logs | `journalctl -u camera-tracker -u light-controller -f` |
| Disable auto-start | `sudo systemctl disable camera-tracker` |

### Key Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 555 | RTSP/TCP | Camera video streams |
| 7000 | OSC/UDP | Tracker → Controller (localhost) |
| 6454 | Art-Net/UDP | Controller → DMX decoder |
| 8765 | WebSocket/TCP | Controller → Public viewer (via Funnel) |

### Key Files

| File | Purpose |
|------|---------|
| `IO/camera_tracker_osc.py` | Production camera tracker |
| `IO/lightController_osc.py` | Light controller + Art-Net + WebSocket |
| `IO/light_behavior.py` | Behavior system (imported by controller) |
| `IO/tracking_database.py` | Database management (imported by controller) |
| `calibration/camera_calibration.json` | Camera calibration data |
| `IO/systemd/install-services.sh` | Service installer script |

### Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                      PRODUCTION MACHINE (cvtower)                  │
│                                                                    │
│  ┌──────────────────┐    OSC     ┌──────────────────────┐         │
│  │ camera_tracker   │───7000───▶│  lightController     │         │
│  │    _osc.py       │           │     _osc.py          │         │
│  │                  │           │                      │         │
│  │ • YOLO tracking  │           │ • Behavior system    │         │
│  │ • 2× RTSP input  │           │ • Art-Net output     │         │
│  │ • Calibration    │           │ • WebSocket server   │         │
│  └────────┬─────────┘           └──────┬───────┬───────┘         │
│           │                            │       │                  │
│       RTSP:555                   Art-Net:6454  WS:8765           │
│           ▼                            ▼       ▼                  │
│   ┌───────────────┐            ┌──────────┐  ┌──────────────┐    │
│   │   Cameras     │            │   DMX    │  │  Tailscale   │    │
│   │ .75  /  .172  │            │ Decoder  │  │   Funnel     │    │
│   └───────────────┘            └────┬─────┘  └──────┬───────┘    │
└─────────────────────────────────────│───────────────│────────────┘
                                      │               │
                                      ▼            HTTPS ▼
                               ┌──────────┐    ┌───────────────┐
                               │   LED    │    │ GitHub Pages  │
                               │  Panels  │    │ Public Viewer │
                               └──────────┘    └───────────────┘
```

---

See also: [Hardware](HARDWARE.md) for physical build details, [Software Guide](SOFTWARE_GUIDE.md) for application reference, [How It Works](HOW_IT_WORKS.md) for an accessible overview.
