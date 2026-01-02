# Post-Mortem: Screenshot Bug

Analysis of the screenshot bug encountered during development.

## The Bug

When the agent ran, screenshots showed different content than what was actually on screen. The user saw Firefox with Google results, but Claude's screenshots showed a terminal.

## Root Cause

**File caching + race conditions** in the screenshot pipeline:

1. **Static filename** (`/tmp/s.png`) - filesystem could return cached content
2. **No X synchronization** - screenshots captured before display updated
3. **Missing `-o` flag** - scrot may silently fail to overwrite

## The Fix

```python
# Before (buggy)
b64 = self._run("DISPLAY=:0 scrot -p /tmp/s.png && base64 /tmp/s.png")

# After (working)
ts = int(time.time() * 1000)
cmd = f"""
    rm -f /tmp/shot_{ts}.png
    DISPLAY=:0 xdotool sync
    sleep 0.1
    DISPLAY=:0 scrot -o /tmp/shot_{ts}.png
    base64 /tmp/shot_{ts}.png
    rm -f /tmp/shot_{ts}.png
"""
```

Key changes:
- Unique filename (timestamp)
- `xdotool sync` to wait for X events
- Small delay for display refresh
- `-o` flag to force overwrite
- Cleanup of temp files

## Red Herrings Chased

| Red Herring | Why It Wasn't The Issue |
|-------------|------------------------|
| Multiple displays | Only `:0` existed |
| SPICE vs X11 mismatch | Same X server for both |
| Permission issues | Agent had correct access |

## How to Diagnose Faster

The key test that revealed the bug:

```bash
# Take screenshots, check if they're different
for i in 1 2 3; do
    DISPLAY=:0 scrot /tmp/test_$i.png
done
md5sum /tmp/test_*.png  # All same hash = caching bug
```

**Ask early**: "If I take two screenshots with the same command, are the files byte-identical?"

## Lessons Learned

1. **Never use static filenames** in automation - use timestamps/UUIDs
2. **X11 is async** - always use `xdotool sync` before screenshots
3. **Use file hashes to debug** - reveals caching immediately
4. **Test primitives in isolation** before building the full system

## Reliable Screenshot Template

```python
def reliable_screenshot(display=":0") -> bytes:
    ts = int(time.time() * 1000_000)
    cmd = f"""
        export DISPLAY={display}
        xdotool sync 2>/dev/null || sleep 0.1
        F=/tmp/s_{ts}.png
        scrot -o "$F" && base64 "$F" && rm -f "$F"
    """
    return run(cmd)
```

## Key Insight

What appeared to be a complex display/protocol issue was actually a simple file caching bug. We wasted time investigating complex hypotheses (SPICE, multiple displays) instead of testing the basic assumption: "Is scrot writing new data each time?"

**Always test the simplest possible explanation first.**
