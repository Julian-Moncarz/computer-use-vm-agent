"""VM interaction via SSH and xdotool."""
import base64
import paramiko
import shlex
import subprocess
from pathlib import Path


class VMError(Exception):
    """Base exception for VM errors."""
    pass


class VM:
    """Controls a UTM VM via SSH."""

    def __init__(self, name: str, ssh_host: str, ssh_user: str, ssh_key: str):
        self.name = name
        self.ssh_host = ssh_host
        self.ssh_user = ssh_user
        self.ssh_key = Path(ssh_key).expanduser()
        self.ssh: paramiko.SSHClient | None = None

    def connect(self):
        """Establish SSH connection to VM."""
        self.ssh = paramiko.SSHClient()
        # Load system known_hosts for security
        self.ssh.load_system_host_keys()
        # For first connection, auto-add the key (user can tighten later)
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(
            hostname=self.ssh_host,
            username=self.ssh_user,
            key_filename=str(self.ssh_key),
            timeout=10
        )

    def disconnect(self):
        """Close SSH connection."""
        if self.ssh:
            self.ssh.close()
            self.ssh = None

    def _run(self, cmd: str, timeout: float = 10) -> str:
        """Run command via SSH, return stdout. Raises on failure."""
        if not self.ssh:
            raise VMError("Not connected")

        stdin, stdout, stderr = self.ssh.exec_command(cmd, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()

        if exit_code != 0:
            err = stderr.read().decode().strip()
            raise VMError(f"Command failed (exit {exit_code}): {err}")

        return stdout.read().decode()

    def screenshot(self) -> bytes:
        """Take screenshot with cursor visible, return PNG bytes."""
        # Use unique filename, force overwrite, sync display first
        import time
        ts = int(time.time() * 1000)
        cmd = f"""
            rm -f /tmp/shot_{ts}.png
            DISPLAY=:0 xdotool sync
            sleep 0.1
            DISPLAY=:0 scrot -o /tmp/shot_{ts}.png
            base64 /tmp/shot_{ts}.png
            rm -f /tmp/shot_{ts}.png
        """
        b64 = self._run(cmd, timeout=15)
        return base64.b64decode(b64.strip())

    def move_mouse(self, x: int, y: int):
        """Move mouse to absolute coordinates."""
        self._run(f"DISPLAY=:0 xdotool mousemove {x} {y}")

    def click(self, button: str = "left", clicks: int = 1):
        """Click mouse button."""
        btn = {"left": "1", "right": "3", "middle": "2"}.get(button, "1")
        for _ in range(clicks):
            self._run(f"DISPLAY=:0 xdotool click {btn}")

    def type_text(self, text: str):
        """Type text. For special keys, use press_key instead."""
        # Use xdotool type with proper escaping
        escaped = shlex.quote(text)
        self._run(f"DISPLAY=:0 xdotool type --clearmodifiers {escaped}")

    def press_key(self, key: str):
        """Press key or combo. Examples: Return, Tab, ctrl+a, alt+F4"""
        escaped = shlex.quote(key)
        self._run(f"DISPLAY=:0 xdotool key {escaped}")

    @staticmethod
    def get_ip(vm_name: str) -> str:
        """Get VM IP via utmctl."""
        result = subprocess.run(
            ["utmctl", "ip-address", vm_name],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode != 0:
            raise VMError(f"Failed to get VM IP: {result.stderr}")
        return result.stdout.strip()

    @staticmethod
    def start(vm_name: str):
        """Start VM via utmctl."""
        subprocess.run(["utmctl", "start", vm_name], check=True, timeout=30)

    @staticmethod
    def is_running(vm_name: str) -> bool:
        """Check if VM is running."""
        result = subprocess.run(
            ["utmctl", "status", vm_name],
            capture_output=True, text=True, timeout=10
        )
        return "started" in result.stdout.lower()
