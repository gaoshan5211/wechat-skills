from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compatibility wrapper for sending WeChat text messages"
    )
    parser.add_argument("--name", required=True, help="exact contact or group name")
    parser.add_argument("--message", required=True, help="text message to send")
    parser.add_argument(
        "--image_path",
        required=False,
        help="deprecated: image sending is not supported by the AX wrapper",
    )
    args = parser.parse_args()

    if args.image_path:
        parser.error(
            "--image_path is not supported by the Accessibility implementation; "
            "use --message only"
        )

    try:
        from wechat_ax import send_message
    except ImportError as exc:
        print(
            f"{exc}. Install dependencies with: "
            "python3 -m pip install pyobjc-framework-Cocoa "
            "pyobjc-framework-ApplicationServices pyobjc-framework-Quartz"
        )
        return 1

    result = send_message(args.name, args.message)
    if not result.get("sent"):
        print(result)
        return 2
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
