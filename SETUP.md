# Setup Guide

Complete guide to setting up the Autonomous VM Agent from scratch.

## Prerequisites

- macOS (Apple Silicon or Intel)
- Python 3.9+
- Anthropic API key

## Step 1: Install UTM

```bash
brew install --cask utm
```

Or download from [mac.getutm.app](https://mac.getutm.app)

## Step 2: Get a Debian VM

### Option A: Download Pre-built (Fastest)

Download a Debian ARM64 VM from the [UTM Gallery](https://mac.getutm.app/gallery/) and double-click to import.

### Option B: Install from ISO

1. Download [Debian 12 ARM64 ISO](https://cdimage.debian.org/debian-cd/current/arm64/iso-cd/) (or AMD64 for Intel Macs)

2. Create VM in UTM:
   - Click "Create a New Virtual Machine"
   - Choose "Virtualize" → "Linux"
   - Select the Debian ISO
   - Settings: 4GB RAM, 2 CPU cores, 32GB disk
   - Name it `Debian-Claude`

3. Install Debian:
   - Boot the VM and select "Graphical Install"
   - Choose **Xfce** desktop environment
   - Enable **SSH server**
   - Create user `claude` with password `claude`

4. After install, eject the ISO and reboot

## Step 3: Configure the VM

Boot into Debian and open a terminal. Run:

```bash
# Install required packages
sudo apt update
sudo apt install -y xdotool scrot spice-vdagent

# Set password (if not already set)
sudo passwd claude
```

Get the VM's IP address:

```bash
ip addr | grep 192
```

Note the IP (e.g., `192.168.64.2`)

## Step 4: Set Up SSH Key

On your Mac:

```bash
# Create a dedicated key (no passphrase)
ssh-keygen -t ed25519 -f ~/.ssh/vm_agent_key -N "" -C "vm-agent"

# Copy to VM (enter password when prompted)
ssh-copy-id -i ~/.ssh/vm_agent_key.pub claude@192.168.64.2

# Test it works
ssh -i ~/.ssh/vm_agent_key claude@192.168.64.2 "echo 'SSH works!'"
```

## Step 5: Install Python Dependencies

```bash
cd autonomous-vm-agent
pip install -r requirements.txt
```

## Step 6: Configure Environment

Create `.env` file:

```bash
cat > .env << 'EOF'
ANTHROPIC_API_KEY=your_api_key_here
VM_NAME=Debian-Claude
VM_SSH_HOST=192.168.64.2
VM_SSH_USER=claude
VM_SSH_KEY=~/.ssh/vm_agent_key
EOF
```

Replace `your_api_key_here` with your actual Anthropic API key.

## Step 7: Run the Agent

```bash
python3 main.py
```

Enter a task like "Open Firefox and go to google.com"

### Options

```bash
python3 main.py                        # Interactive mode
python3 main.py --task "Open Firefox"  # Single task mode
python3 main.py --keep-screenshots     # Keep screenshots after exit
```

## Troubleshooting

### "Permission denied" SSH error

```bash
# Re-copy SSH key
ssh-copy-id -i ~/.ssh/vm_agent_key.pub -o PubkeyAuthentication=no claude@192.168.64.2
```

### Screenshots show wrong content

The VM display must be active. Make sure:
- VM is running and logged in
- Desktop is visible (not screen locked)
- Only one X session is active

### Can't find VM IP

```bash
# From Mac
utmctl ip-address "Debian-Claude"

# Or from inside VM
ip addr | grep inet
```

### xdotool commands fail

Ensure DISPLAY is correct:

```bash
ssh -i ~/.ssh/vm_agent_key claude@192.168.64.2 "DISPLAY=:0 xdotool getmouselocation"
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│                    Mac Host                      │
│                                                  │
│  main.py ─── Claude API ─── Tool Calls          │
│      │                                           │
│      └──── vm.py ─── SSH ────────────┐          │
└──────────────────────────────────────┼──────────┘
                                       │
                                       ▼
┌──────────────────────────────────────────────────┐
│              Debian VM (UTM)                     │
│                                                  │
│  xdotool ─── mouse/keyboard control             │
│  scrot ───── screenshots                        │
│  XFCE ────── desktop environment                │
└──────────────────────────────────────────────────┘
```

## How It Works

1. Agent takes screenshot of VM desktop
2. Screenshot sent to Claude API
3. Claude analyzes screen and decides action
4. Action executed via SSH (xdotool/scrot)
5. New screenshot taken
6. Repeat until task complete
