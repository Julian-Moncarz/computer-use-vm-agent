# Cloud Deployment Guide

How to run the Autonomous VM Agent in the cloud instead of locally.

## Overview

The agent can run on any Linux server with a virtual framebuffer (Xvfb) instead of a physical display. This guide covers deployment options and costs.

## Recommended: Hetzner VPS ($4-9/month)

### Setup Script

Run on a fresh Debian 12 VPS:

```bash
#!/bin/bash
# Install X11 and desktop
apt update
apt install -y xvfb xfce4 xfce4-goodies dbus-x11 \
    xdotool scrot firefox-esr \
    tigervnc-standalone-server \
    openssh-server python3-pip python3-venv

# Create agent user
useradd -m -s /bin/bash agent
echo 'agent:agent' | chpasswd

# Create virtual display service
cat > /etc/systemd/system/xvfb.service << 'EOF'
[Unit]
Description=X Virtual Frame Buffer
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/Xvfb :99 -screen 0 1280x800x24
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Create desktop session service
cat > /etc/systemd/system/xfce-session.service << 'EOF'
[Unit]
Description=XFCE Desktop Session
After=xvfb.service
Requires=xvfb.service

[Service]
Type=simple
Environment=DISPLAY=:99
User=agent
ExecStart=/usr/bin/startxfce4
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# VNC for debugging (optional)
cat > /etc/systemd/system/vnc.service << 'EOF'
[Unit]
Description=VNC Server
After=xvfb.service

[Service]
Type=simple
Environment=DISPLAY=:99
User=agent
ExecStart=/usr/bin/x0vncserver -display :99 -SecurityTypes=None
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable services
systemctl daemon-reload
systemctl enable xvfb xfce-session vnc
systemctl start xvfb xfce-session vnc
```

### Code Change Required

Update `vm.py` to use `DISPLAY=:99` instead of `DISPLAY=:0`:

```python
# In vm.py, change the display variable
DISPLAY = ":99"  # or make it configurable via env var
```

### Deploy the Agent

```bash
# On the VPS
cd /opt
git clone <your-repo> vm-agent
cd vm-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env
cat > .env << 'EOF'
ANTHROPIC_API_KEY=your_key
VM_SSH_HOST=localhost
VM_SSH_USER=agent
VM_SSH_KEY=/root/.ssh/id_rsa
EOF

# Run
python3 main.py
```

### Debugging via VNC

```bash
# From your local machine, create SSH tunnel
ssh -L 5901:localhost:5901 root@your-server-ip

# Then connect VNC client to localhost:5901
```

## Cost Comparison

| Provider | Config | Monthly Cost |
|----------|--------|--------------|
| **Hetzner CX22** | 2 vCPU, 4GB RAM | **$4.35** |
| **Hetzner CX32** | 4 vCPU, 8GB RAM | **$8.69** |
| DigitalOcean | 2 vCPU, 4GB RAM | $24 |
| AWS t3.medium | 2 vCPU, 4GB RAM | ~$30 |
| Paperspace Core | 2 vCPU, 4GB RAM | $8+ |

**Recommendation: Hetzner CX22 or CX32** - Best price/performance.

## Alternative: Docker

Run the entire desktop in a Docker container:

```yaml
# docker-compose.yml
version: '3'
services:
  desktop:
    image: kasmweb/debian-bullseye-desktop:1.14.0
    ports:
      - "6901:6901"
      - "2222:22"
    environment:
      - VNC_PW=agent123
```

## Architecture Comparison

### Local (Current)
```
Mac → SSH → UTM VM (Debian)
```

### Cloud
```
Cloud VPS:
  main.py → SSH localhost → Xvfb + XFCE

  VNC tunnel for debugging
```

### All-in-One (Best Performance)
```
Single VPS running both:
  - Agent (main.py)
  - Virtual desktop (Xvfb + XFCE)
  - No SSH needed, direct subprocess calls
```

## What Changes for Cloud

| Component | Local | Cloud |
|-----------|-------|-------|
| Display | `:0` (UTM/SPICE) | `:99` (Xvfb) |
| VM management | utmctl | Not needed |
| SSH target | VM IP | localhost or VPS IP |
| Debugging | UTM window | VNC tunnel |

Core logic (xdotool, scrot, Claude API) stays exactly the same.
