"""Autonomous VM Agent - Claude controls a Debian VM."""
import argparse
import base64
import json
import os
import sys
import time
from anthropic import Anthropic
from vm import VM, VMError

# Tool definitions for Claude
TOOLS = [
    {
        "name": "screenshot",
        "description": "Take a screenshot of the VM desktop (includes cursor). Use frequently to verify actions.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "move_mouse",
        "description": "Move mouse cursor to absolute screen coordinates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate (pixels from left)"},
                "y": {"type": "integer", "description": "Y coordinate (pixels from top)"}
            },
            "required": ["x", "y"]
        }
    },
    {
        "name": "click",
        "description": "Click mouse at current position.",
        "input_schema": {
            "type": "object",
            "properties": {
                "button": {"type": "string", "enum": ["left", "right"], "default": "left"},
                "clicks": {"type": "integer", "default": 1, "description": "1=single, 2=double"}
            },
            "required": []
        }
    },
    {
        "name": "type_text",
        "description": "Type text at cursor. For Enter/Tab/etc, use press_key.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"]
        }
    },
    {
        "name": "press_key",
        "description": "Press key or combo. Examples: Return, Tab, Escape, ctrl+a, alt+F4, Page_Down",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"]
        }
    },
    {
        "name": "ask_user",
        "description": "Pause and ask user a question (for CAPTCHAs, credentials, decisions).",
        "input_schema": {
            "type": "object",
            "properties": {"question": {"type": "string"}},
            "required": ["question"]
        }
    },
    {
        "name": "wait",
        "description": "Wait for page loads or animations. Max 30 seconds.",
        "input_schema": {
            "type": "object",
            "properties": {"seconds": {"type": "number"}},
            "required": ["seconds"]
        }
    }
]

MAX_ITERATIONS = 100


def execute_tool(vm: VM, name: str, args: dict) -> dict:
    """Execute a tool, return result dict."""
    try:
        if name == "screenshot":
            png = vm.screenshot()
            return {"success": True, "image": base64.b64encode(png).decode()}
        elif name == "move_mouse":
            vm.move_mouse(args["x"], args["y"])
            return {"success": True, "moved_to": [args["x"], args["y"]]}
        elif name == "click":
            vm.click(args.get("button", "left"), args.get("clicks", 1))
            return {"success": True}
        elif name == "type_text":
            vm.type_text(args["text"])
            return {"success": True, "chars": len(args["text"])}
        elif name == "press_key":
            vm.press_key(args["key"])
            return {"success": True, "key": args["key"]}
        elif name == "ask_user":
            print(f"\n>>> CLAUDE ASKS: {args['question']}")
            response = input(">>> YOUR RESPONSE: ")
            return {"success": True, "user_said": response}
        elif name == "wait":
            secs = max(0, min(args.get("seconds", 1), 30))
            time.sleep(secs)
            return {"success": True, "waited": secs}
        else:
            return {"success": False, "error": f"Unknown tool: {name}"}
    except VMError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {e}"}


def run_agent(vm: VM, task: str):
    """Run the agent loop until task complete or max iterations."""
    client = Anthropic()

    # Take initial screenshot
    print("Taking initial screenshot...")
    try:
        initial_screenshot = vm.screenshot()
    except VMError as e:
        print(f"Error: Could not take screenshot: {e}")
        return

    messages = [{
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.b64encode(initial_screenshot).decode()
                }
            },
            {
                "type": "text",
                "text": f"""You are an autonomous agent controlling a Debian Linux desktop.

YOUR TASK: {task}

GUIDELINES:
- Take screenshots frequently to verify your actions worked
- Move mouse to target BEFORE clicking
- Use wait after clicks that trigger page loads
- If you encounter CAPTCHAs, login prompts, or are stuck, use ask_user
- Be methodical: screenshot -> think -> act -> screenshot to verify

The screenshot above shows the current desktop. Begin working on the task."""
            }
        ]
    }]

    for iteration in range(MAX_ITERATIONS):
        print(f"\n[Iteration {iteration + 1}/{MAX_ITERATIONS}]")

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            tools=TOOLS,
            messages=messages
        )

        # Check if Claude is done
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    print(f"\n=== TASK COMPLETE ===\n{block.text}")
            return

        # Process tool calls
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            print("No tool calls and not end_turn - stopping.")
            return

        # Add assistant message
        messages.append({"role": "assistant", "content": response.content})

        # Execute each tool
        tool_results = []
        for tool in tool_uses:
            print(f"  -> {tool.name}({json.dumps(tool.input)})")
            result = execute_tool(vm, tool.name, tool.input)

            # Format result for Claude
            if tool.name == "screenshot" and result.get("success"):
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool.id,
                    "content": [{
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": result["image"]
                        }
                    }]
                })
            else:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool.id,
                    "content": json.dumps(result)
                })

        messages.append({"role": "user", "content": tool_results})

    print(f"\n=== MAX ITERATIONS ({MAX_ITERATIONS}) REACHED ===")


def main():
    parser = argparse.ArgumentParser(description="Autonomous VM Agent")
    parser.add_argument("--vm", default=os.environ.get("VM_NAME", "Debian-Claude"),
                        help="UTM VM name")
    parser.add_argument("--ssh-host", default=os.environ.get("VM_SSH_HOST"),
                        help="VM SSH host/IP (auto-detected if not set)")
    parser.add_argument("--ssh-user", default=os.environ.get("VM_SSH_USER", "user"),
                        help="VM SSH username")
    parser.add_argument("--ssh-key", default=os.environ.get("VM_SSH_KEY", "~/.ssh/id_rsa"),
                        help="SSH private key path")
    args = parser.parse_args()

    # Get VM IP if not provided
    ssh_host = args.ssh_host
    if not ssh_host:
        print(f"Getting IP for VM '{args.vm}'...")
        try:
            ssh_host = VM.get_ip(args.vm)
            print(f"  -> {ssh_host}")
        except VMError as e:
            print(f"Error: {e}")
            print("Is the VM running? Try: utmctl start " + args.vm)
            sys.exit(1)

    # Connect to VM
    vm = VM(args.vm, ssh_host, args.ssh_user, args.ssh_key)
    print(f"Connecting to {args.ssh_user}@{ssh_host}...")
    try:
        vm.connect()
        print("  -> Connected!")
    except Exception as e:
        print(f"Error connecting: {e}")
        sys.exit(1)

    print("\n" + "="*50)
    print("AUTONOMOUS VM AGENT")
    print("Claude controls a Debian VM to complete tasks.")
    print("Type a task and press Enter. Ctrl+C to quit.")
    print("="*50)

    try:
        while True:
            task = input("\nEnter task: ").strip()
            if not task:
                continue
            print()
            run_agent(vm, task)
    except KeyboardInterrupt:
        print("\nGoodbye!")
    finally:
        vm.disconnect()


if __name__ == "__main__":
    main()
