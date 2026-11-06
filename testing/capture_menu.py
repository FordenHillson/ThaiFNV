# -*- coding: utf-8 -*-
"""Launch FNV via NVSE, restore the window, capture the main menu at 2560x1440."""
import ctypes
import os
import subprocess
import sys
import time

from PIL import ImageGrab

GAME = r"D:\SteamLibrary\steamapps\common\Fallout New Vegas"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shot_v7.png")

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
    # kill leftovers
    subprocess.run(["taskkill", "/F", "/IM", "FalloutNV.exe"],
                   capture_output=True)

    exe = os.path.join(GAME, "nvse_loader.exe")
    proc = subprocess.Popen([exe], cwd=GAME,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    print("launched pid", proc.pid, flush=True)

    main_hwnd = None
    deadline = time.time() + 90
    while time.time() < deadline:
        wins = windows()
        for hwnd, pid, name, title, w, h in wins:
            if w >= 1000 and h >= 700:
                print("found", name, pid, repr(title), w, h, flush=True)
                main_hwnd = hwnd
                break
        if main_hwnd:
            break
        time.sleep(2)

    if main_hwnd is None:
        print("main window not found", flush=True)
        subprocess.run(["taskkill", "/F", "/IM", "FalloutNV.exe"],
                       capture_output=True)
        sys.exit(1)

    user32.ShowWindow(main_hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(main_hwnd)

    rect = RECT()
    for i in range(6):
        time.sleep(10)
        # keep the game in front: the shell window steals focus between grabs
        user32.BringWindowToTop(main_hwnd)
        user32.SetForegroundWindow(main_hwnd)
        time.sleep(1.5)
        GetWindowRect(main_hwnd, ctypes.byref(rect))
        img = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom),
                             all_screens=False)
        path = OUT if i == 0 else OUT.replace(".png", "_%d.png" % i)
        img.save(path)
        print("saved", path, img.size, flush=True)

    time.sleep(1)
    subprocess.run(["taskkill", "/F", "/IM", "FalloutNV.exe"],
                   capture_output=True)
    print("terminated", flush=True)


if __name__ == "__main__":
    main()
