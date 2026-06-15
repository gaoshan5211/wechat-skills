from __future__ import annotations

import re
import subprocess
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable

import AppKit
from ApplicationServices import (
    AXUIElementCopyAttributeValue,
    AXUIElementCreateApplication,
    AXUIElementPerformAction,
    AXUIElementSetAttributeValue,
    AXValueGetType,
    AXValueGetValue,
    kAXChildrenAttribute,
    kAXIdentifierAttribute,
    kAXListRole,
    kAXPositionAttribute,
    kAXRaiseAction,
    kAXRoleAttribute,
    kAXSizeAttribute,
    kAXStaticTextRole,
    kAXTextAreaRole,
    kAXTitleAttribute,
    kAXValueAttribute,
    kAXValueCGPointType,
    kAXValueCGSizeType,
    kAXWindowRole,
)
from Quartz import (
    CGEventCreateKeyboardEvent,
    CGEventCreateMouseEvent,
    CGEventCreateScrollWheelEvent,
    CGEventPost,
    CGEventSetFlags,
    CGEventSetLocation,
    CGPoint,
    kCGEventFlagMaskCommand,
    kCGEventLeftMouseDown,
    kCGEventLeftMouseUp,
    kCGHIDEventTap,
    kCGScrollEventUnitLine,
)


WECHAT_BUNDLE_ID = "com.tencent.xinWeChat"


class WeChatAutomationError(RuntimeError):
    pass


@dataclass
class SearchEntry:
    element: Any
    text: str
    y: float


@dataclass
class OpenChatResult:
    opened: bool
    chat_name: str
    method: str
    current_chat: str | None = None
    candidates: dict[str, list[str]] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {key: value for key, value in data.items() if value is not None}


def ax_get(element: Any, attribute: str) -> Any:
    err, value = AXUIElementCopyAttributeValue(element, attribute, None)
    if err != 0:
        return None
    return value


def dfs(element: Any, predicate: Callable[[Any, Any, Any, Any], bool]) -> Any | None:
    if element is None:
        return None

    role = ax_get(element, kAXRoleAttribute)
    title = ax_get(element, kAXTitleAttribute)
    identifier = ax_get(element, kAXIdentifierAttribute)

    if predicate(element, role, title, identifier):
        return element

    for child in ax_get(element, kAXChildrenAttribute) or []:
        found = dfs(child, predicate)
        if found is not None:
            return found
    return None


def _walk(element: Any, visit: Callable[[Any, Any, Any, Any], None]) -> None:
    role = ax_get(element, kAXRoleAttribute)
    title = ax_get(element, kAXTitleAttribute)
    identifier = ax_get(element, kAXIdentifierAttribute)
    visit(element, role, title, identifier)
    for child in ax_get(element, kAXChildrenAttribute) or []:
        _walk(child, visit)


def _running_wechat() -> Any | None:
    apps = AppKit.NSRunningApplication.runningApplicationsWithBundleIdentifier_(
        WECHAT_BUNDLE_ID
    )
    return apps[0] if apps else None


def launch_wechat(timeout: float = 8.0) -> Any:
    app = _running_wechat()
    if app is not None:
        return app

    subprocess.run(
        ["open", "-b", WECHAT_BUNDLE_ID],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    end = time.time() + timeout
    while time.time() < end:
        app = _running_wechat()
        if app is not None:
            return app
        time.sleep(0.2)
    raise WeChatAutomationError("WeChat is not running and could not be launched")


def get_wechat_ax_app(open_if_needed: bool = True) -> Any:
    app = launch_wechat() if open_if_needed else _running_wechat()
    if app is None:
        raise WeChatAutomationError("WeChat is not running")

    app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps)
    time.sleep(0.2)
    return AXUIElementCreateApplication(app.processIdentifier())


def _normalize_chat_name(name: str) -> str:
    name = name.strip()
    return re.sub(r"\(\d+\)$", "", name).strip()


def _text_value(element: Any) -> str | None:
    for attribute in (kAXValueAttribute, kAXTitleAttribute):
        value = ax_get(element, attribute)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def get_current_chat_name(ax_app: Any | None = None) -> str | None:
    ax_app = ax_app or get_wechat_ax_app()

    def is_chat_title(_el: Any, role: Any, _title: Any, identifier: Any) -> bool:
        return role == kAXStaticTextRole and identifier == "big_title_line_h_view"

    element = dfs(ax_app, is_chat_title)
    value = _text_value(element) if element is not None else None
    return _normalize_chat_name(value) if value else None


def collect_recent_chats(ax_app: Any | None = None) -> dict[str, Any]:
    ax_app = ax_app or get_wechat_ax_app()
    results: dict[str, Any] = {}

    def visit(element: Any, role: Any, _title: Any, identifier: Any) -> None:
        if role != kAXStaticTextRole:
            return
        if not isinstance(identifier, str):
            return
        if identifier.startswith("session_item_"):
            name = identifier.removeprefix("session_item_").strip()
            if name:
                results[name] = element

    _walk(ax_app, visit)
    return results


def find_recent_chat_element(ax_app: Any, chat_name: str) -> Any | None:
    chats = collect_recent_chats(ax_app)
    if chat_name in chats:
        return chats[chat_name]

    target = chat_name.casefold()
    for name, element in chats.items():
        if name.casefold() == target:
            return element
    return None


def axvalue_to_point(ax_value: Any) -> tuple[float, float] | None:
    if ax_value is None or AXValueGetType(ax_value) != kAXValueCGPointType:
        return None
    ok, point = AXValueGetValue(ax_value, kAXValueCGPointType, None)
    if not ok:
        return None
    return float(point.x), float(point.y)


def axvalue_to_size(ax_value: Any) -> tuple[float, float] | None:
    if ax_value is None or AXValueGetType(ax_value) != kAXValueCGSizeType:
        return None
    ok, size = AXValueGetValue(ax_value, kAXValueCGSizeType, None)
    if not ok:
        return None
    return float(size.width), float(size.height)


def click_element_center(element: Any) -> None:
    origin = axvalue_to_point(ax_get(element, kAXPositionAttribute))
    size = axvalue_to_size(ax_get(element, kAXSizeAttribute))
    if origin is None or size is None:
        raise WeChatAutomationError("Failed to read target element bounds")

    x, y = origin
    w, h = size
    point = CGPoint(x + w / 2.0, y + h / 2.0)
    down = CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, point, 0)
    up = CGEventCreateMouseEvent(None, kCGEventLeftMouseUp, point, 0)
    CGEventPost(kCGHIDEventTap, down)
    CGEventPost(kCGHIDEventTap, up)


def _send_key(keycode: int, flags: int = 0) -> None:
    down = CGEventCreateKeyboardEvent(None, keycode, True)
    CGEventSetFlags(down, flags)
    up = CGEventCreateKeyboardEvent(None, keycode, False)
    CGEventSetFlags(up, flags)
    CGEventPost(kCGHIDEventTap, down)
    CGEventPost(kCGHIDEventTap, up)


def press_return() -> None:
    _send_key(36)


def command_a() -> None:
    _send_key(0, kCGEventFlagMaskCommand)


def command_v() -> None:
    _send_key(9, kCGEventFlagMaskCommand)


def paste_text(text: str) -> None:
    pasteboard = AppKit.NSPasteboard.generalPasteboard()
    pasteboard.clearContents()
    pasteboard.setString_forType_(text, AppKit.NSPasteboardTypeString)
    command_v()


def post_scroll(center: tuple[float, float], delta_lines: int) -> None:
    cx, cy = center
    event = CGEventCreateScrollWheelEvent(None, kCGScrollEventUnitLine, 1, delta_lines)
    CGEventSetLocation(event, CGPoint(cx, cy))
    CGEventPost(kCGHIDEventTap, event)


def element_center(element: Any) -> tuple[float, float]:
    origin = axvalue_to_point(ax_get(element, kAXPositionAttribute))
    size = axvalue_to_size(ax_get(element, kAXSizeAttribute))
    if origin is None or size is None:
        raise WeChatAutomationError("Failed to read element bounds")
    x, y = origin
    w, h = size
    return x + w / 2.0, y + h / 2.0


def find_search_field(ax_app: Any) -> Any:
    def is_search(_el: Any, role: Any, title: Any, identifier: Any) -> bool:
        if role != kAXTextAreaRole:
            return False
        return title == "Search" or identifier in {
            "search_text_field",
            "search_field",
        }

    search = dfs(ax_app, is_search)
    if search is None:
        raise WeChatAutomationError("Could not find WeChat search field")
    return search


def focus_search(ax_app: Any, query: str) -> None:
    search = find_search_field(ax_app)
    AXUIElementPerformAction(search, kAXRaiseAction)
    click_element_center(search)
    AXUIElementSetAttributeValue(search, kAXValueAttribute, "")
    time.sleep(0.1)
    command_a()
    time.sleep(0.05)
    paste_text(query)


def get_search_list(ax_app: Any) -> Any:
    def is_search_list(_el: Any, role: Any, _title: Any, identifier: Any) -> bool:
        return role == kAXListRole and identifier == "search_list"

    search_list = dfs(ax_app, is_search_list)
    if search_list is None:
        raise WeChatAutomationError("Could not find WeChat search results list")
    return search_list


SECTION_TITLES = {
    "contacts": {"Contacts", "联系人"},
    "groups": {"Group Chats", "群聊"},
    "ignored": {
        "Chat History",
        "聊天记录",
        "Official Accounts",
        "公众号",
        "Internet search results",
        "网络搜索结果",
        "More",
        "更多",
    },
}


def _section_kind(text: str) -> str | None:
    if text in SECTION_TITLES["contacts"]:
        return "contacts"
    if text in SECTION_TITLES["groups"]:
        return "groups"
    if text in SECTION_TITLES["ignored"]:
        return "ignored"
    return None


def collect_search_entries(search_list: Any) -> list[SearchEntry]:
    entries: list[SearchEntry] = []

    def visit(element: Any, role: Any, _title: Any, _identifier: Any) -> None:
        if role != kAXStaticTextRole:
            return
        text = _text_value(element)
        if not text:
            return
        point = axvalue_to_point(ax_get(element, kAXPositionAttribute))
        entries.append(SearchEntry(element=element, text=text, y=point[1] if point else 0.0))

    _walk(search_list, visit)
    entries.sort(key=lambda entry: entry.y)
    return entries


def _build_headers(entries: list[SearchEntry]) -> list[tuple[str, float]]:
    headers: list[tuple[str, float]] = []
    for entry in entries:
        kind = _section_kind(entry.text)
        if kind:
            headers.append((kind, entry.y))
    headers.sort(key=lambda item: item[1])
    return headers


def _classify_entry(entry: SearchEntry, headers: list[tuple[str, float]]) -> str | None:
    section: str | None = None
    for kind, y in headers:
        if y <= entry.y:
            section = kind
        else:
            break
    return section


def _search_candidates(entries: list[SearchEntry]) -> dict[str, list[str]]:
    headers = _build_headers(entries)
    contacts: list[str] = []
    groups: list[str] = []

    for entry in entries:
        if _section_kind(entry.text):
            continue
        section = _classify_entry(entry, headers)
        if section == "contacts" and entry.text not in contacts:
            contacts.append(entry.text)
        elif section == "groups" and entry.text not in groups:
            groups.append(entry.text)

    return {"contacts": contacts[:15], "group_chats": groups[:15]}


def _find_exact_search_match(entries: list[SearchEntry], chat_name: str) -> Any | None:
    target = chat_name.strip()
    headers = _build_headers(entries)
    fallback = None

    for entry in entries:
        if entry.text != target:
            continue
        section = _classify_entry(entry, headers)
        if section == "contacts":
            return entry.element
        if section == "groups" and fallback is None:
            fallback = entry.element
        if section is None and not headers and fallback is None:
            fallback = entry.element
    return fallback


def _expand_visible_sections(search_list: Any) -> None:
    entries = collect_search_entries(search_list)
    headers = _build_headers(entries)

    for entry in entries:
        text = entry.text
        if not (
            text.startswith("View All")
            or text.startswith("查看全部")
            or text.startswith("显示全部")
        ):
            continue
        section = _classify_entry(entry, headers)
        if section in {"contacts", "groups"}:
            click_element_center(entry.element)
            time.sleep(0.25)


def select_from_search_results(
    ax_app: Any, chat_name: str, max_scrolls: int = 60
) -> tuple[bool, dict[str, list[str]]]:
    search_list = get_search_list(ax_app)
    contacts: set[str] = set()
    groups: set[str] = set()

    def merge_candidates(entries: list[SearchEntry]) -> None:
        candidates = _search_candidates(entries)
        contacts.update(candidates["contacts"])
        groups.update(candidates["group_chats"])

    entries = collect_search_entries(search_list)
    merge_candidates(entries)
    element = _find_exact_search_match(entries, chat_name)
    if element is not None:
        click_element_center(element)
        return True, {
            "contacts": sorted(contacts)[:15],
            "group_chats": sorted(groups)[:15],
        }

    _expand_visible_sections(search_list)
    center = element_center(search_list)
    last_bottom_text = None
    stable_count = 0

    for _ in range(max_scrolls):
        entries = collect_search_entries(search_list)
        merge_candidates(entries)
        element = _find_exact_search_match(entries, chat_name)
        if element is not None:
            click_element_center(element)
            return True, {
                "contacts": sorted(contacts)[:15],
                "group_chats": sorted(groups)[:15],
            }

        if not entries:
            break
        bottom_text = entries[-1].text
        if bottom_text == last_bottom_text:
            stable_count += 1
            if stable_count >= 3:
                break
        else:
            stable_count = 0
            last_bottom_text = bottom_text

        post_scroll(center, -80)
        time.sleep(0.1)

    return False, {
        "contacts": sorted(contacts)[:15],
        "group_chats": sorted(groups)[:15],
    }


def open_chat(chat_name: str) -> OpenChatResult:
    target = chat_name.strip()
    if not target:
        raise WeChatAutomationError("chat name is empty")

    ax_app = get_wechat_ax_app(open_if_needed=True)
    current = get_current_chat_name(ax_app)
    if current == _normalize_chat_name(target):
        return OpenChatResult(True, target, "already_open", current_chat=current)

    recent = find_recent_chat_element(ax_app, target)
    if recent is not None:
        click_element_center(recent)
        time.sleep(0.4)
        return OpenChatResult(
            True,
            target,
            "recent_session",
            current_chat=get_current_chat_name(ax_app),
        )

    focus_search(ax_app, target)
    time.sleep(0.5)
    found, candidates = select_from_search_results(ax_app, target)
    if found:
        time.sleep(0.5)
        return OpenChatResult(
            True,
            target,
            "search",
            current_chat=get_current_chat_name(ax_app),
            candidates=candidates,
        )

    return OpenChatResult(
        False,
        target,
        "search",
        current_chat=get_current_chat_name(ax_app),
        candidates=candidates,
        error="No exact contact or group chat match found in visible WeChat search results",
    )


def find_chat_input(ax_app: Any) -> Any:
    def is_chat_input(_el: Any, role: Any, title: Any, identifier: Any) -> bool:
        if role != kAXTextAreaRole:
            return False
        if identifier == "chat_input_field":
            return True
        return title not in {"Search", "搜索"}

    element = dfs(ax_app, is_chat_input)
    if element is None:
        raise WeChatAutomationError("Could not find WeChat chat input field")
    return element


def input_text(text: str, submit: bool = False) -> None:
    ax_app = get_wechat_ax_app(open_if_needed=True)
    field = find_chat_input(ax_app)
    AXUIElementPerformAction(field, kAXRaiseAction)
    click_element_center(field)

    err = AXUIElementSetAttributeValue(field, kAXValueAttribute, text)
    if err != 0:
        command_a()
        time.sleep(0.05)
        paste_text(text)
    time.sleep(0.1)
    if submit:
        press_return()


def send_message(chat_name: str, message: str, dry_run: bool = False) -> dict[str, Any]:
    result = open_chat(chat_name)
    if not result.opened:
        data = result.to_dict()
        data["sent"] = False
        return data

    if dry_run:
        data = result.to_dict()
        data["sent"] = False
        data["dry_run"] = True
        return data

    input_text(message, submit=True)
    data = result.to_dict()
    data["sent"] = True
    data["message_length"] = len(message)
    return data


def status() -> dict[str, Any]:
    app = _running_wechat()
    if app is None:
        return {"running": False, "bundle_id": WECHAT_BUNDLE_ID}

    ax_app = get_wechat_ax_app(open_if_needed=False)
    recent_chats = collect_recent_chats(ax_app)
    windows = []

    def visit(_element: Any, role: Any, title: Any, _identifier: Any) -> None:
        if role == kAXWindowRole and isinstance(title, str):
            windows.append(title)

    _walk(ax_app, visit)
    return {
        "running": True,
        "bundle_id": WECHAT_BUNDLE_ID,
        "pid": app.processIdentifier(),
        "current_chat": get_current_chat_name(ax_app),
        "recent_chat_count": len(recent_chats),
        "recent_chat_names": sorted(recent_chats)[:20],
        "windows": windows[:10],
    }
