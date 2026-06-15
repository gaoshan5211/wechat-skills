# WeChat Skill

Agent Skill for controlling the macOS WeChat desktop app through Accessibility APIs.

This fork focuses on deterministic local CLI actions that Codex or another skills-compatible agent can call:

- check WeChat status
- open an exact contact or group chat
- type text into the current chat input
- send a text message

It does not use YOLO, OCR, or Computer Use. It reads the macOS Accessibility tree and posts native Quartz input events.

## Installation

Copy the `skills/wechat` directory into your Codex skills path, usually `~/.codex/skills/wechat`.

Install Python dependencies:

```bash
python3 -m pip install pyobjc-framework-Cocoa pyobjc-framework-ApplicationServices pyobjc-framework-Quartz
```

Grant Accessibility permission to the app that runs the scripts:

1. Open System Settings > Privacy & Security > Accessibility.
2. Add Terminal, iTerm2, VS Code, Codex, or the relevant Python host app.
3. Enable the toggle.

## Usage

```bash
cd skills/wechat

python3 scripts/wechat_cli.py status
python3 scripts/wechat_cli.py open-chat --name "Contact Name"
python3 scripts/wechat_cli.py input --message "Message content"
python3 scripts/wechat_cli.py send --name "Contact Name" --message "Message content"
```

The legacy text-send command still works:

```bash
python3 scripts/wechat_send.py --name "Contact Name" --message "Message content"
```

## Behavior

The automation tries to open WeChat by bundle id `com.tencent.xinWeChat` when it is not running. It prefers exact matches from the recent chat list, then searches contacts and group chats through WeChat's search results. If no exact match is found, it returns candidate names in JSON instead of clicking an ambiguous result.

## Limitations

- WeChat must be logged in.
- Contact and group names should match visible WeChat names exactly.
- Text sending is supported. Image sending is not implemented in this Accessibility path.
- The UI is operated in the foreground, so avoid using the mouse or keyboard during a command.

## Attribution

The Accessibility approach is adapted from the MIT-licensed ideas in `BiboyQG/WeChat-MCP`, with this repository kept as a Skill-style CLI package rather than an MCP server.
