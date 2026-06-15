from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

def _emit(data: dict, as_json: bool = True) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if data.get("error"):
        print(f"ERROR: {data['error']}")
        return
    print(json.dumps(data, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Control macOS WeChat through Accessibility APIs"
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="print compact plain output instead of pretty JSON",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="inspect WeChat running state")

    open_parser = subparsers.add_parser("open-chat", help="open a contact or group chat")
    open_parser.add_argument("--name", required=True, help="exact contact or group name")

    input_parser = subparsers.add_parser(
        "input", help="type text into the current chat input box"
    )
    input_parser.add_argument("--message", required=True, help="text to input")
    input_parser.add_argument(
        "--submit", action="store_true", help="press Return after filling the input"
    )

    send_parser = subparsers.add_parser("send", help="open a chat and send text")
    send_parser.add_argument("--name", required=True, help="exact contact or group name")
    send_parser.add_argument("--message", required=True, help="text message to send")
    send_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="open the chat but do not fill or send the message",
    )

    args = parser.parse_args()
    as_json = not args.plain

    try:
        from wechat_ax import (
            WeChatAutomationError,
            input_text,
            open_chat,
            send_message,
            status,
        )

        if args.command == "status":
            _emit(status(), as_json=as_json)
            return 0
        if args.command == "open-chat":
            result = open_chat(args.name).to_dict()
            _emit(result, as_json=as_json)
            return 0 if result.get("opened") else 2
        if args.command == "input":
            input_text(args.message, submit=args.submit)
            _emit({"input": True, "submitted": args.submit}, as_json=as_json)
            return 0
        if args.command == "send":
            result = send_message(args.name, args.message, dry_run=args.dry_run)
            _emit(result, as_json=as_json)
            return 0 if result.get("sent") or result.get("dry_run") else 2
    except ImportError as exc:
        _emit(
            {
                "error": (
                    f"{exc}. Install dependencies with: "
                    "python3 -m pip install pyobjc-framework-Cocoa "
                    "pyobjc-framework-ApplicationServices pyobjc-framework-Quartz"
                )
            },
            as_json=as_json,
        )
        return 1
    except WeChatAutomationError as exc:
        _emit({"error": str(exc)}, as_json=as_json)
        return 1
    except Exception as exc:
        _emit({"error": f"{type(exc).__name__}: {exc}"}, as_json=as_json)
        return 1

    parser.error(f"unsupported command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
