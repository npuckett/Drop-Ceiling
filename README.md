# Drop Ceiling

**Drop Ceiling** is an interactive light installation that responds to human presence and movement. This repository contains the public viewer — a mobile-first Three.js web application that displays the real-time state of the installation.

## What Is Included

### `/public-viewer`
A browser-based 3D visualization that connects to the installation WebSocket server:
- Real-time rendering of 12 LED light panels
- Tracked person positions shown as 3D avatars
- Light point position and falloff visualization
- Behavior mode display (Idle, Engaged, Crowd, Flow)

## Live Demo

Visit: **https://yourusername.github.io/Drop-Ceiling/public-viewer/**

*(Replace `yourusername` with your GitHub username after deploying)*

---

## Deployment

### Option 1: GitHub Pages (Recommended)

1. **Push this repository to GitHub**
   ```bash
   git add .
   git commit -m "Add public viewer"
   git push origin main
   ```

2. **Enable GitHub Pages**
   - Go to your repository Settings → Pages
   - Under "Source", select **Deploy from a branch**
   - Choose `main` branch and `/ (root)` folder
   - Click Save

3. **Access your viewer**
   - GitHub will deploy to: `https://<username>.github.io/Drop-Ceiling/public-viewer/`
   - First deployment takes 1-2 minutes

### Option 2: Local Development

Serve the files locally:
```bash
cd public-viewer
python3 -m http.server 8080
```

Then open `http://localhost:8080` in your browser.

---

## Connecting to the Installation

The viewer connects to a WebSocket server that broadcasts the installation real-time state.

### Connection Methods

1. **URL Parameter** (highest priority)
   ```
   https://yoursite.github.io/Drop-Ceiling/public-viewer/?ws=wss://your-server.ts.net/
   ```

2. **Saved Connection** - Enter the WebSocket URL in the connection dialog; the viewer remembers your last connection

3. **Default** - Falls back to the production Tailscale Funnel URL

### WebSocket Requirements

For GitHub Pages (HTTPS), you need a secure WebSocket (`wss://`):

- **Tailscale Funnel** — Expose your local server via `tailscale funnel 8765`
- **Cloudflare Tunnel** — Alternative tunnel service
- **Any WSS endpoint** — Any server with SSL/TLS

---

## Features

- **Real-time sync** — 60 FPS state updates via WebSocket
- **Mobile-first** — Optimized for portrait viewing on phones
- **Minimal aesthetic** — Clean dark design matching the installation
- **Status display** — Shows connection state, behavior mode, tracked people
- **No dependencies** — Pure vanilla JavaScript with Three.js via CDN

---

## Customization

### Modify WebSocket URL
Edit `public-viewer/viewer.js` and update the `WS_URL` in the CONFIG object.

### Adjust Panel Layout
The panel configuration in `viewer.js` matches the physical installation:
- 4 units × 3 panels each = 12 panels total
- Configurable spacing, angles, and positions

---

## License

MIT License
