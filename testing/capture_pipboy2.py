# -*- coding: utf-8 -*-
"""Load a save, open the Pip-Boy STATS page and capture it.

Robust against slow loads: waits until the frame is not black before
sending keys.
"""
import ctypes
import os
import subprocess
import sys
import time

from PIL import ImageGrab, ImageStat

GAME = r"D:\SteamLibrary\steamapps\common\Fallout New Vegas"
HERE = os.path.dirname(os.path.abspath(__file__))

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
IsWindowVisible = user32.IsWindowVisible
GetWindowRect = user32.GetWindowRect
OpenProcess = kernel32.OpenProcess
QueryFullProcessImageNameW = kernel32.QueryFullProcessImageNameW
CloseHandle = kernel32.CloseHandle
keybd_event = user32.keybd_event

VK = {"enter": 0x0D, "tab": 0x09, "esc": 0x1B, "down": 0x28, "up": 0x26,
      "left": 0x25, "right": 0x27, "q": 0x51, "e": 0x45}
KEYEVENTF_KEYUP = 0x0002


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def process_name(pid):
    h = OpenProcess(0x1000, False, pid)
    if not h:
        return ""
    buf = ctypes.create_unicode_buffer(1024)
    size = ctypes.c_ulong(1024)
    ok = QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
    CloseHandle(h)
    return os.path.basename(buf.value).lower() if ok else ""


def find_game_window():
    found = []

    def cb(hwnd, _):
        if not IsWindowVisible(hwnd):
            return True
        pid = ctypes.c_ulong()
        GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if process_name(pid.value) != "falloutnv.exe":
            return True
        r = RECT()
        GetWindowRect(hwnd, ctypes.byref(r))
        if r.right - r.left >= 1000 and r.bottom - r.top >= 700:
            found.append(hwnd)
        return True

    EnumWindows(EnumWindowsProc(cb), 0)
    return found[0] if found else None


def rect_of(hwnd):
    r = RECT()
    GetWindowRect(hwnd, ctypes.byref(r))
    return r


def focus(hwnd):
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)


def shot(hwnd):
    focus(hwnd)
    time.sleep(0.3)
    r = rect_of(hwnd)
    return ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom), all_screens=False)


def mean_of(img, box):
    return ImageStat.Stat(img.crop(box).convert("L")).mean[0]


def press(hwnd, key, wait=0.35):
    focus(hwnd)
    vk = VK[key]
    keybd_event(vk, 0, 0, 0)
    time.sleep(0.06)
    keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(wait)


def grab(hwnd, name):
    img = shot(hwnd)
    img.save(os.path.join(HERE, name))
    print("saved", name, "mean=%.1f" % mean_of(img, (600, 200, 2000, 1200)), flush=True)
    return img


def wait_frame(hwnd, what, tries=12, gap=8, box=(600, 200, 2000, 1200)):
    for i in range(tries):
        img = shot(hwnd)
        m = mean_of(img, box)
        print("  probe %s #%d mean=%.1f" % (what, i, m), flush=True)
        if m > 12:
            return img
        time.sleep(gap)
    return None


def main():
    subprocess.run(["taskkill", "/F", "/IM", "FalloutNV.exe"], capture_output=True)
    proc = subprocess.Popen([os.path.join(GAME, "nvse_loader.exe")], cwd=GAME,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("launched", proc.pid, flush=True)

    hwnd = None
    deadline = time.time() + 120
    while time.time() < deadline and not hwnd:
        hwnd = find_game_window()
        if not hwnd:
            time.sleep(2)
    if not hwnd:
        print("no window")
        sys.exit(1)

    user32.ShowWindow(hwnd, 9)
    time.sleep(25)
    wait_frame(hwnd, "main menu")
    print("continue", flush=True)
    press(hwnd, "enter", 1.0)
    time.sleep(20)
    img = wait_frame(hwnd, "loaded", tries=15, gap=8)
    if img is None:
        print("never loaded")
        sys.exit(1)

    for _ in range(4):
        press(hwnd, "esc", 1.2)
    grab(hwnd, "pb_hud.png")

    press(hwnd, "tab", 2.5)
    grab(hwnd, "pb_items.png")
    press(hwnd, "q", 2.0)
    grab(hwnd, "pb_stats.png")
    press(hwnd, "e", 2.0)
    grab(hwnd, "pb_items2.png")

    time.sleep(1)
    subprocess.run(["taskkill", "/F", "/IM", "FalloutNV.exe"], capture_output=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
