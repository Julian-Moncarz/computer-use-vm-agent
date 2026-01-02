# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

An autonomous agent that controls a Debian Linux VM through screenshots and xdotool commands. Claude receives screenshots, decides actions (mouse/keyboard), and executes them via SSH until a task is complete.

## Running the Agent

```bash
# Install dependencies
pip install -r requirements.txt

# Run (requires VM running + .env configured)
python3 main.py                        # Interactive mode
python3 main.py --task "Open Firefox"  # Single task, then exit
python3 main.py --keep-screenshots     # Don't delete screenshots/ on exit
```

## Architecture

```
main.py  →  Claude API (tool use loop)
   ↓
vm.py    →  SSH + xdotool/scrot to VM
   ↓
Debian VM (UTM or Xvfb in cloud)
```

**main.py**: Agent loop - sends screenshots to Claude, receives tool calls, executes them via VM class, repeats until `stop_reason == "end_turn"`. Tools: `screenshot`, `move_mouse`, `click`, `type_text`, `press_key`, `ask_user`, `wait`.

**vm.py**: `VM` class wraps SSH connection. All commands run with `DISPLAY=:0` (local) or `DISPLAY=:99` (cloud/Xvfb). Uses `xdotool` for mouse/keyboard, `scrot` for screenshots.

## Key Implementation Details

**Screenshot reliability**: Uses unique timestamp filenames + `xdotool sync` + small delay before capture. Static filenames cause caching bugs (see POST_MORTEM.md).

**Model**: Currently uses `claude-sonnet-4-5-20250929` in main.py.

**Environment variables** (loaded from `.env`):
- `ANTHROPIC_API_KEY` - required
- `VM_NAME` - UTM VM name (default: "Debian-Claude")
- `VM_SSH_HOST` - IP/hostname (auto-detected via utmctl if not set)
- `VM_SSH_USER` - SSH username (default: "user")
- `VM_SSH_KEY` - SSH key path (default: ~/.ssh/vm_agent_key)

## Cloud Deployment

See CLOUD_DEPLOYMENT.md. Key difference: use `DISPLAY=:99` with Xvfb instead of `:0`. The xdotool/scrot commands are identical.
