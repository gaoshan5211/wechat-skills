---
name: WeChat
description: Control the macOS WeChat desktop client through Accessibility APIs. Use when the user asks to check WeChat status, open a contact or group chat, type text, or send a text message from the local WeChat app.
---

# WeChat

Use this skill to operate the local macOS WeChat desktop app with bundled Python scripts. The scripts use macOS Accessibility APIs and Quartz input events, not image recognition.

## Requirements

- macOS with WeChat desktop installed and logged in
- Python 3.10+
- Dependencies:

```bash
python3 -m pip install pyobjc-framework-Cocoa pyobjc-framework-ApplicationServices pyobjc-framework-Quartz
```

- Accessibility permission for the app running Codex or the terminal:
  System Settings > Privacy & Security > Accessibility

## Commands

Run commands from this skill directory or pass the absolute script path.

```bash
# Check whether WeChat is running and whether AX can see chats.
python3 scripts/wechat_cli.py status

# Open an exact contact or group chat.
python3 scripts/wechat_cli.py open-chat --name "Contact Name"

# Fill the current chat input box without sending.
python3 scripts/wechat_cli.py input --message "Message content"

# Open a chat and send a text message.
python3 scripts/wechat_cli.py send --name "Contact Name" --message "Message content"

# Compatibility wrapper for older usage.
python3 scripts/wechat_send.py --name "Contact Name" --message "Message content"
```

## Workflow

1. For any WeChat operation, first run `status` unless the user explicitly asks to send immediately.
2. To send text, use `send --name ... --message ...`.
3. If `send` returns `opened: false`, report the candidates from the JSON output and ask the user for a more exact chat name.
4. If the script reports that WeChat is not running, rerun the requested command; it will try to launch WeChat by bundle id.
5. If AX fields cannot be found, tell the user to grant Accessibility permission to Codex/Terminal and confirm WeChat is logged in.

## Notes

- Contact and group names should match the visible WeChat name exactly.
- The current implementation supports status, opening chats, typing text, and sending text.
- Image sending is intentionally not supported by the Accessibility implementation yet.
- Do not use the mouse or keyboard while a command is running.
