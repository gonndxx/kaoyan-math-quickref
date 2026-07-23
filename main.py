"""Windows entry point for 研数公式速查 2.0."""

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


APP_NAME = "研数公式速查 2.0"
APP_VERSION = "2.0.0"
APP_DIR_NAME = "KaoyanMathQuickRef"
HOTKEY_ID = 0x4D51
HOTKEY_FALLBACK_ID = 0x4D52
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
SW_HIDE = 0
SW_RESTORE = 9
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002


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
        self.registered_hotkeys: set[int] = set()
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

    def hotkey_loop(self) -> None:
        if sys.platform != "win32":
            return
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self.hotkey_thread_id = kernel32.GetCurrentThreadId()
        hotkeys = (
            (HOTKEY_ID, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord("M")),
            (HOTKEY_FALLBACK_ID, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, 0x20),
        )
        for hotkey_id, modifiers, virtual_key in hotkeys:
            if user32.RegisterHotKey(None, hotkey_id, modifiers, virtual_key):
                self.registered_hotkeys.add(hotkey_id)
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            if message.message == WM_HOTKEY and message.wParam in self.registered_hotkeys:
                self.toggle_visibility()
        for hotkey_id in self.registered_hotkeys:
            user32.UnregisterHotKey(None, hotkey_id)

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
        return {
            "appVersion": APP_VERSION,
            "formulas": FORMULAS,
            "subjectOrder": SUBJECT_ORDER,
            "chapterOrder": CHAPTER_ORDER,
            "sources": SOURCES,
            "settings": APP.settings.data,
            "hotkeys": {
                "primary": HOTKEY_ID in APP.registered_hotkeys,
                "fallback": HOTKEY_FALLBACK_ID in APP.registered_hotkeys,
            },
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
