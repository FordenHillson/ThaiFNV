# -*- coding: utf-8 -*-
"""Load a save, open the Pip-Boy and capture STATS / ITEMS / DATA tabs."""
import ctypes
import os
import subprocess
import sys
import time

from PIL import ImageGrab

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
mouse_event = user32.mouse_event
SetCursorPos = user32.SetCursorPos

VK = {"enter": 0x0D, "tab": 0x09, "esc": 0x1B, "down": 0x28, "up": 0x26}
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


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


def press(hwnd, key, wait=0.35):
    focus(hwnd)
    vk = VK[key]
    keybd_event(vk, 0, 0, 0)
    time.sleep(0.06)
    keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(wait)


def click(hwnd, x, y, wait=1.0):
    focus(hwnd)
    r = rect_of(hwnd)
    SetCursorPos(r.left + x, r.top + y)
    time.sleep(0.15)
    mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.08)
    mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    time.sleep(wait)


def grab(hwnd, name):
    focus(hwnd)
    time.sleep(0.3)
    r = rect_of(hwnd)
    img = ImageGrab.grab(bbox=(r.left, r.top, r.right, r.bottom), all_screens=False)
    img.save(os.path.join(HERE, name))
    print("saved", name, img.size, flush=True)


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
    print("continue", flush=True)
    press(hwnd, "enter", 1.0)
    time.sleep(32)

    # clear any pause menu / dialog restored by the save (even count ends in-game)
    press(hwnd, "esc", 1.2)
    press(hwnd, "esc", 1.2)
    press(hwnd, "esc", 1.2)
    press(hwnd, "esc", 1.2)
    grab(hwnd, "pb_hud.png")

    press(hwnd, "tab", 2.5)
    grab(hwnd, "pb_items.png")

    # tab buttons sit at y~992 in a 2560x1440 frame
    click(hwnd, 985, 992, 1.2)
    grab(hwnd, "pb_stats.png")
    click(hwnd, 1160, 992, 1.2)
    grab(hwnd, "pb_data.png")
    click(hwnd, 845, 992, 1.2)
    grab(hwnd, "pb_items2.png")

    time.sleep(1)
    subprocess.run(["taskkill", "/F", "/IM", "FalloutNV.exe"], capture_output=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
