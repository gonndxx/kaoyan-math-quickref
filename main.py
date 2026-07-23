"""Windows entry point for 研数公式速查 2.1."""

from __future__ import annotations

import ctypes
import json
import os
import sys
import threading
import time
import webbrowser
from ctypes import wintypes
from pathlib import Path
from urllib.parse import urlparse

import pystray
import webview
from PIL import Image, ImageDraw

from formulas import CHAPTER_ORDER, FORMULAS, SOURCES, SUBJECT_ORDER


APP_NAME = "研数公式速查 2.1"
APP_VERSION = "2.1.0"
APP_DIR_NAME = "KaoyanMathQuickRef"
HOTKEY_ID = 0x4D51
HOTKEY_FALLBACK_ID = 0x4D52
WM_HOTKEY = 0x0312
WM_HOTKEY_RELOAD = 0x8001
WM_QUIT = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
PM_NOREMOVE = 0x0000
SW_HIDE = 0
SW_RESTORE = 9
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
DEFAULT_HOTKEY = "Ctrl+Shift+Space"
FALLBACK_HOTKEY = "Ctrl+Alt+M"

NAMED_VIRTUAL_KEYS = {
    "SPACE": ("Space", 0x20),
    **{f"F{index}": (f"F{index}", 0x6F + index) for index in range(1, 13)},
}


def parse_hotkey(shortcut: str) -> dict:
    """Validate and normalize a user-facing global shortcut."""
    if not isinstance(shortcut, str):
        raise ValueError("快捷键格式无效")
    raw_parts = [part.strip() for part in shortcut.split("+") if part.strip()]
    if len(raw_parts) < 2:
        raise ValueError("快捷键必须包含修饰键和一个按键")

    aliases = {
        "CONTROL": "CTRL",
        "CMD": "WIN",
        "META": "WIN",
        "WINDOWS": "WIN",
    }
    modifiers: set[str] = set()
    key_name = ""
    virtual_key = 0

    for raw_part in raw_parts:
        part = aliases.get(raw_part.upper(), raw_part.upper())
        if part in {"CTRL", "ALT", "SHIFT", "WIN"}:
            modifiers.add(part)
            continue
        if key_name:
            raise ValueError("快捷键只能包含一个普通按键")
        if len(part) == 1 and ("A" <= part <= "Z" or "0" <= part <= "9"):
            key_name = part
            virtual_key = ord(part)
        elif part in NAMED_VIRTUAL_KEYS:
            key_name, virtual_key = NAMED_VIRTUAL_KEYS[part]
        else:
            raise ValueError("仅支持字母、数字、Space 和 F1–F12")

    if not key_name:
        raise ValueError("请在修饰键后再按一个普通按键")
    if not modifiers.intersection({"CTRL", "ALT", "WIN"}):
        raise ValueError("至少需要 Ctrl、Alt 或 Win 中的一个")

    modifier_flags = MOD_NOREPEAT
    modifier_labels: list[str] = []
    for name, label, flag in (
        ("CTRL", "Ctrl", MOD_CONTROL),
        ("ALT", "Alt", MOD_ALT),
        ("SHIFT", "Shift", MOD_SHIFT),
        ("WIN", "Win", MOD_WIN),
    ):
        if name in modifiers:
            modifier_flags |= flag
            modifier_labels.append(label)

    return {
        "shortcut": "+".join([*modifier_labels, key_name]),
        "modifiers": modifier_flags,
        "virtualKey": virtual_key,
    }


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def settings_dir() -> Path:
    root = Path(os.environ.get("APPDATA", Path.home()))
    path = root / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


class SettingsStore:
    DEFAULTS = {
        "favorites": [],
        "recent": [],
        "theme": "light",
        "pinned": False,
        "quickMode": False,
        "sidebarCollapsed": False,
        "hotkey": DEFAULT_HOTKEY,
        "width": 1180,
        "height": 780,
    }

    def __init__(self) -> None:
        self.path = settings_dir() / "settings.json"
        self.lock = threading.RLock()
        self.data = dict(self.DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except (OSError, ValueError, TypeError):
            pass
        valid_ids = {card["id"] for card in FORMULAS}
        self.data["favorites"] = [x for x in self.data.get("favorites", []) if x in valid_ids]
        self.data["recent"] = [x for x in self.data.get("recent", []) if x in valid_ids][:30]
        self.data["theme"] = self.data.get("theme") if self.data.get("theme") in {"light", "dark"} else "light"
        self.data["pinned"] = bool(self.data.get("pinned", False))
        self.data["quickMode"] = bool(self.data.get("quickMode", False))
        self.data["sidebarCollapsed"] = bool(self.data.get("sidebarCollapsed", False))
        try:
            self.data["hotkey"] = parse_hotkey(
                self.data.get("hotkey", DEFAULT_HOTKEY)
            )["shortcut"]
        except ValueError:
            self.data["hotkey"] = DEFAULT_HOTKEY

    def save(self) -> None:
        with self.lock:
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(self.path)

    def set(self, key: str, value) -> None:
        with self.lock:
            self.data[key] = value
            self.save()

    def update(self, values: dict) -> None:
        with self.lock:
            self.data.update(values)
            self.save()


class Application:
    def __init__(self) -> None:
        self.settings = SettingsStore()
        self.window: webview.Window | None = None
        self.tray: pystray.Icon | None = None
        self.visible = True
        self.exiting = False
        self.hotkey_thread_id = 0
        self.registered_hotkeys: dict[int, dict] = {}
        self.hotkey_ready = threading.Event()
        self.hotkey_change_done = threading.Event()
        self.hotkey_change_request: dict | None = None
        self.hotkey_change_result: dict | None = None
        self.hotkey_lock = threading.RLock()
        self.state_lock = threading.RLock()
        self.resize_timer: threading.Timer | None = None
        self.allowed_hosts = {
            urlparse(source["url"]).netloc.lower()
            for source in SOURCES
        }

    def _native_window_handle(self):
        if sys.platform != "win32":
            return None
        user32 = ctypes.windll.user32
        user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
        user32.FindWindowW.restype = wintypes.HWND
        return user32.FindWindowW(None, APP_NAME)

    def show(self) -> None:
        with self.state_lock:
            if self.window is None or self.exiting:
                return
            try:
                hwnd = self._native_window_handle()
                if hwnd:
                    user32 = ctypes.windll.user32
                    user32.ShowWindow(hwnd, SW_RESTORE)
                    user32.SetForegroundWindow(hwnd)
                else:
                    self.window.show()
                    self.window.restore()
                self.visible = True
                try:
                    self.window.evaluate_js("window.onQuickShow && window.onQuickShow()")
                except Exception:
                    pass
            except Exception:
                pass

    def hide(self) -> None:
        with self.state_lock:
            if self.window is None or self.exiting:
                return
            try:
                hwnd = self._native_window_handle()
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)
                else:
                    self.window.hide()
                self.visible = False
            except Exception:
                pass

    def toggle_visibility(self) -> None:
        if self.visible:
            self.hide()
        else:
            self.show()

    def toggle_pin(self) -> bool:
        with self.state_lock:
            pinned = not bool(self.settings.data.get("pinned"))
            self.settings.set("pinned", pinned)
            if self.window is not None:
                self.window.on_top = pinned
            if self.tray is not None:
                self.tray.update_menu()
            return pinned

    def request_exit(self) -> None:
        with self.state_lock:
            if self.exiting:
                return
            self.exiting = True
        if self.tray is not None:
            try:
                self.tray.stop()
            except Exception:
                pass
        if self.hotkey_thread_id and sys.platform == "win32":
            ctypes.windll.user32.PostThreadMessageW(self.hotkey_thread_id, WM_QUIT, 0, 0)
        if self.resize_timer is not None:
            self.resize_timer.cancel()
        if self.window is not None:
            try:
                self.window.destroy()
            except Exception:
                pass

    def on_closing(self) -> bool | None:
        if self.exiting:
            return None
        self.hide()
        return False

    def on_resized(self, width: int, height: int) -> None:
        if width < 880 or height < 620 or self.exiting:
            return
        if self.resize_timer is not None:
            self.resize_timer.cancel()

        def persist_size() -> None:
            self.settings.update({
                "width": max(880, min(int(width), 2400)),
                "height": max(620, min(int(height), 1600)),
            })

        self.resize_timer = threading.Timer(0.45, persist_size)
        self.resize_timer.daemon = True
        self.resize_timer.start()

    def _tray_image(self) -> Image.Image:
        size = 64
        image = Image.new("RGBA", (size, size), (25, 79, 180, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((2, 2, 61, 61), radius=15, fill=(39, 103, 232, 255))
        points = [(44, 15), (20, 15), (34, 31), (20, 49), (45, 49)]
        draw.line(points, fill=(255, 255, 255, 255), width=7, joint="curve")
        return image

    def start_tray(self) -> None:
        if self.tray is not None:
            return

        def show_hide(icon, item):
            self.toggle_visibility()

        def pin(icon, item):
            self.toggle_pin()

        def quit_app(icon, item):
            self.request_exit()

        menu = pystray.Menu(
            pystray.MenuItem("显示 / 隐藏", show_hide, default=True),
            pystray.MenuItem(
                "窗口置顶",
                pin,
                checked=lambda item: bool(self.settings.data.get("pinned")),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", quit_app),
        )
        self.tray = pystray.Icon(APP_DIR_NAME, self._tray_image(), APP_NAME, menu)
        threading.Thread(target=self.tray.run, name="formula-tray", daemon=True).start()

    def _register_hotkey(self, user32, hotkey_id: int, spec: dict) -> bool:
        registered = user32.RegisterHotKey(
            None,
            hotkey_id,
            spec["modifiers"],
            spec["virtualKey"],
        )
        if registered:
            self.registered_hotkeys[hotkey_id] = dict(spec)
        return bool(registered)

    def _unregister_all_hotkeys(self, user32) -> None:
        for hotkey_id in tuple(self.registered_hotkeys):
            user32.UnregisterHotKey(None, hotkey_id)
        self.registered_hotkeys.clear()

    def _register_with_fallback(self, user32, preferred: dict) -> None:
        if self._register_hotkey(user32, HOTKEY_ID, preferred):
            return
        fallback = parse_hotkey(FALLBACK_HOTKEY)
        if fallback["shortcut"] != preferred["shortcut"]:
            self._register_hotkey(user32, HOTKEY_FALLBACK_ID, fallback)

    def _apply_hotkey_change(self, user32, requested: dict | None) -> dict:
        previous_id, previous = next(
            iter(self.registered_hotkeys.items()),
            (None, None),
        )
        self._unregister_all_hotkeys(user32)
        if requested and self._register_hotkey(user32, HOTKEY_ID, requested):
            return {
                "ok": True,
                "message": f"{requested['shortcut']} 已立即生效",
            }

        if previous and previous_id is not None:
            self._register_hotkey(user32, previous_id, previous)
        if not self.registered_hotkeys:
            self._register_hotkey(
                user32,
                HOTKEY_FALLBACK_ID,
                parse_hotkey(FALLBACK_HOTKEY),
            )
        return {
            "ok": False,
            "error": "in_use",
            "message": "该组合键已被其他程序占用，原快捷键仍然有效",
        }

    def hotkey_status(self) -> dict:
        with self.hotkey_lock:
            active_id = next(iter(self.registered_hotkeys), None)
            active = self.registered_hotkeys.get(active_id, {})
            return {
                "configured": self.settings.data.get("hotkey", DEFAULT_HOTKEY),
                "active": active.get("shortcut"),
                "registered": active_id is not None,
                "usingFallback": active_id == HOTKEY_FALLBACK_ID,
            }

    def update_hotkey(self, shortcut: str) -> dict:
        try:
            requested = parse_hotkey(shortcut)
        except ValueError as error:
            return {
                "ok": False,
                "error": "invalid",
                "message": str(error),
                **self.hotkey_status(),
            }
        if sys.platform != "win32":
            return {
                "ok": False,
                "error": "unsupported",
                "message": "当前系统不支持 Windows 全局快捷键",
                **self.hotkey_status(),
            }
        if not self.hotkey_ready.wait(timeout=1.5):
            return {
                "ok": False,
                "error": "not_ready",
                "message": "快捷键服务尚未就绪，请稍后重试",
                **self.hotkey_status(),
            }

        status = self.hotkey_status()
        if (
            status["registered"]
            and not status["usingFallback"]
            and status["active"] == requested["shortcut"]
        ):
            self.settings.set("hotkey", requested["shortcut"])
            return {"ok": True, "message": "快捷键已启用", **self.hotkey_status()}

        with self.hotkey_lock:
            self.hotkey_change_request = requested
            self.hotkey_change_result = None
            self.hotkey_change_done.clear()
        if not ctypes.windll.user32.PostThreadMessageW(
            self.hotkey_thread_id,
            WM_HOTKEY_RELOAD,
            0,
            0,
        ):
            return {
                "ok": False,
                "error": "service_error",
                "message": "无法通知快捷键服务",
                **self.hotkey_status(),
            }
        if not self.hotkey_change_done.wait(timeout=2.0):
            return {
                "ok": False,
                "error": "timeout",
                "message": "快捷键注册超时，请重试",
                **self.hotkey_status(),
            }

        with self.hotkey_lock:
            result = dict(self.hotkey_change_result or {})
        if result.get("ok"):
            self.settings.set("hotkey", requested["shortcut"])
        return {**result, **self.hotkey_status()}

    def hotkey_loop(self) -> None:
        if sys.platform != "win32":
            self.hotkey_ready.set()
            return
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self.hotkey_thread_id = kernel32.GetCurrentThreadId()
        message = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_NOREMOVE)
        with self.hotkey_lock:
            self._register_with_fallback(
                user32,
                parse_hotkey(self.settings.data.get("hotkey", DEFAULT_HOTKEY)),
            )
        self.hotkey_ready.set()

        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            if message.message == WM_HOTKEY and message.wParam in self.registered_hotkeys:
                self.toggle_visibility()
            elif message.message == WM_HOTKEY_RELOAD:
                with self.hotkey_lock:
                    requested = self.hotkey_change_request
                    self.hotkey_change_result = self._apply_hotkey_change(
                        user32,
                        requested,
                    )
                    self.hotkey_change_request = None
                    self.hotkey_change_done.set()
        with self.hotkey_lock:
            self._unregister_all_hotkeys(user32)

    def start_hotkey(self) -> None:
        threading.Thread(target=self.hotkey_loop, name="formula-hotkey", daemon=True).start()


APP = Application()


def set_windows_clipboard(text: str) -> bool:
    if sys.platform != "win32":
        return False
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
    kernel32.GlobalFree.argtypes = (wintypes.HGLOBAL,)
    user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
    user32.SetClipboardData.restype = wintypes.HANDLE
    encoded = (text + "\0").encode("utf-16-le")
    handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
    if not handle:
        return False
    pointer = kernel32.GlobalLock(handle)
    if not pointer:
        kernel32.GlobalFree(handle)
        return False
    ctypes.memmove(pointer, encoded, len(encoded))
    kernel32.GlobalUnlock(handle)
    opened = False
    for _ in range(6):
        if user32.OpenClipboard(None):
            opened = True
            break
        time.sleep(0.03)
    if not opened:
        kernel32.GlobalFree(handle)
        return False
    success = False
    try:
        user32.EmptyClipboard()
        success = bool(user32.SetClipboardData(CF_UNICODETEXT, handle))
        if success:
            handle = None
    finally:
        user32.CloseClipboard()
        if handle:
            kernel32.GlobalFree(handle)
    return success


class Api:
    def get_bootstrap(self):
        APP.hotkey_ready.wait(timeout=0.8)
        return {
            "appVersion": APP_VERSION,
            "formulas": FORMULAS,
            "subjectOrder": SUBJECT_ORDER,
            "chapterOrder": CHAPTER_ORDER,
            "sources": SOURCES,
            "settings": APP.settings.data,
            "hotkeys": APP.hotkey_status(),
        }

    def set_favorite(self, card_id: str, enabled: bool) -> bool:
        valid_ids = {card["id"] for card in FORMULAS}
        if card_id not in valid_ids:
            return False
        favorites = list(APP.settings.data.get("favorites", []))
        if enabled and card_id not in favorites:
            favorites.append(card_id)
        elif not enabled:
            favorites = [value for value in favorites if value != card_id]
        APP.settings.set("favorites", favorites)
        return True

    def record_recent(self, card_id: str) -> bool:
        if not any(card["id"] == card_id for card in FORMULAS):
            return False
        recent = [card_id] + [x for x in APP.settings.data.get("recent", []) if x != card_id]
        APP.settings.set("recent", recent[:30])
        return True

    def save_setting(self, key: str, value) -> bool:
        if key not in {"theme", "quickMode", "sidebarCollapsed"}:
            return False
        if key == "theme" and value not in {"light", "dark"}:
            return False
        if key in {"quickMode", "sidebarCollapsed"}:
            value = bool(value)
        APP.settings.set(key, value)
        return True

    def set_hotkey(self, shortcut: str) -> dict:
        return APP.update_hotkey(str(shortcut))

    def copy_text(self, text: str) -> bool:
        return set_windows_clipboard(str(text))

    def hide_app(self) -> bool:
        APP.hide()
        return True

    def toggle_pin(self) -> bool:
        return APP.toggle_pin()

    def open_url(self, url: str) -> bool:
        parsed = urlparse(str(url))
        if parsed.scheme != "https" or parsed.netloc.lower() not in APP.allowed_hosts:
            return False
        webbrowser.open(url)
        return True


def main() -> None:
    width = max(940, min(int(APP.settings.data.get("width", 1180)), 1800))
    height = max(650, min(int(APP.settings.data.get("height", 780)), 1200))
    index_url = resource_path("web/index.html").resolve().as_uri()
    APP.window = webview.create_window(
        APP_NAME,
        index_url,
        js_api=Api(),
        width=width,
        height=height,
        min_size=(880, 620),
        background_color="#132239",
        on_top=bool(APP.settings.data.get("pinned")),
        text_select=True,
    )
    APP.window.events.closing += APP.on_closing
    APP.window.events.resized += APP.on_resized
    APP.window.events.loaded += APP.start_tray
    APP.start_hotkey()
    webview.start(
        gui="edgechromium",
        debug=False,
        private_mode=False,
        # Versioned storage prevents Edge WebView2 from reusing cached HTML,
        # CSS or JavaScript from an older single-file build.
        storage_path=str(settings_dir() / f"webview-v{APP_VERSION.split('.')[0]}"),
    )
    APP.request_exit()


if __name__ == "__main__":
    main()
