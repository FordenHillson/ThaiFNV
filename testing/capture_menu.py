# -*- coding: utf-8 -*-
"""Launch FNV via NVSE, restore the window, capture the main menu."""
import ctypes
import os
import subprocess
import sys
import time

from PIL import ImageGrab

GAME = r"D:\SteamLibrary\steamapps\common\Fallout New Vegas"
TESTING_DIR = r"D:\backup\github\ThaiFNV\testing"
OUT = os.path.join(TESTING_DIR, "main_menu_ingame.png")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
IsWindowVisible = user32.IsWindowVisible
GetWindowRect = user32.GetWindowRect
GetWindowTextW = user32.GetWindowTextW
OpenProcess = kernel32.OpenProcess
QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
CloseHandle = kernel32.CloseHandle


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def process_name(pid):
    h = OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    buf = ctypes.create_unicode_buffer(1024)
    size = ctypes.c_ulong(1024)
    ok = QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
    CloseHandle(h)
    if not ok:
        return ""
    return os.path.basename(buf.value).lower()


def windows():
    found = []

    def cb(hwnd, _):
        if not IsWindowVisible(hwnd):
            return True
        pid = ctypes.c_ulong()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        name = process_name(pid.value)
        if name not in ("falloutnv.exe", "nvse_loader.exe"):
            return True
        r = RECT()
        GetWindowRect(hwnd, ctypes.byref(r))
        buf = ctypes.create_unicode_buffer(256)
        GetWindowTextW(hwnd, buf, 256)
        found.append((hwnd, pid.value, name, buf.value,
                      r.right - r.left, r.bottom - r.top))
        return True

    EnumWindows(EnumWindowsProc(cb), 0)
    return found


def main():
    # ปิด process ค้างถ้ามี
    subprocess.run(["taskkill", "/F", "/IM", "FalloutNV.exe"], capture_output=True)

    exe = os.path.join(GAME, "nvse_loader.exe")
    print("Launching FNV via", exe, flush=True)
    proc = subprocess.Popen([exe], cwd=GAME,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    print("Launched pid:", proc.pid, flush=True)

    main_hwnd = None
    deadline = time.time() + 60
    while time.time() < deadline:
        wins = windows()
        for hwnd, pid, name, title, w, h in wins:
            if w >= 800 and h >= 600:
                print(f"Found game window: {name} pid={pid} title={title!r} size=({w}x{h})", flush=True)
                main_hwnd = hwnd
                break
        if main_hwnd:
            break
        time.sleep(2)

    if main_hwnd is None:
        print("Error: Main game window not found within timeout", flush=True)
        subprocess.run(["taskkill", "/F", "/IM", "FalloutNV.exe"], capture_output=True)
        sys.exit(1)

    user32.ShowWindow(main_hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(main_hwnd)

    print("Waiting for main menu to load...", flush=True)
    # รอโลโก้และ intro ผ่านไป
    time.sleep(14)

    rect = RECT()
    for i in range(2):
        user32.BringWindowToTop(main_hwnd)
        user32.SetForegroundWindow(main_hwnd)
        time.sleep(2.0)
        GetWindowRect(main_hwnd, ctypes.byref(rect))
        img = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=False)
        path = OUT if i == 0 else OUT.replace(".png", f"_{i}.png")
        img.save(path)
        print("Captured screenshot:", path, img.size, flush=True)
        time.sleep(4)

    time.sleep(1)
    subprocess.run(["taskkill", "/F", "/IM", "FalloutNV.exe"], capture_output=True)
    print("Test run completed and closed cleanly.", flush=True)


if __name__ == "__main__":
    main()
