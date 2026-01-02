"""Session recorder for saving logs and generating replay videos."""
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Frame:
    """A single frame in the session recording."""
    timestamp: float
    screenshot_path: str
    actions: list[str] = field(default_factory=list)
    reasoning: Optional[str] = None


@dataclass
class SessionRecorder:
    """Records agent sessions to structured logs."""
    task: str = ""
    frames: list[Frame] = field(default_factory=list)
    screenshot_dir: Path = field(default_factory=lambda: Path("screenshots"))
    _current_reasoning: Optional[str] = None
    _pending_actions: list[str] = field(default_factory=list)

    def set_reasoning(self, text: str):
        """Set reasoning text for the next frame."""
        self._current_reasoning = text

    def add_action(self, action: str):
        """Add an action to be shown in the next frame."""
        self._pending_actions.append(action)

    def add_frame(self, screenshot_bytes: bytes) -> str:
        """Add a frame, saving screenshot to disk.

        Returns the screenshot path.
        """
        # Save screenshot
        self.screenshot_dir.mkdir(exist_ok=True)
        timestamp = time.strftime("%H%M%S")
        # Add frame index to avoid collisions
        screenshot_path = self.screenshot_dir / f"{timestamp}_{len(self.frames):03d}.png"
        screenshot_path.write_bytes(screenshot_bytes)

        # Create frame
        self.frames.append(Frame(
            timestamp=time.time(),
            screenshot_path=str(screenshot_path),
            actions=list(self._pending_actions),
            reasoning=self._current_reasoning
        ))

        # Clear pending state
        self._current_reasoning = None
        self._pending_actions = []

        return str(screenshot_path)

    def save_log(self, path: str):
        """Save session log to JSON file."""
        data = {
            "task": self.task,
            "frames": [
                {
                    "timestamp": f.timestamp,
                    "screenshot": f.screenshot_path,
                    "actions": f.actions,
                    "reasoning": f.reasoning
                }
                for f in self.frames
            ]
        }
        Path(path).write_text(json.dumps(data, indent=2))
        print(f"Log saved to {path}")

    @classmethod
    def load_log(cls, path: str) -> "SessionRecorder":
        """Load session log from JSON file."""
        data = json.loads(Path(path).read_text())
        recorder = cls(task=data.get("task", ""))
        for f in data["frames"]:
            recorder.frames.append(Frame(
                timestamp=f["timestamp"],
                screenshot_path=f["screenshot"],
                actions=f.get("actions", []),
                reasoning=f.get("reasoning")
            ))
        return recorder
