#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vigor_tester_tool.py — เครื่องมือจัดการและพรีวิว Texture ตู้ Vit-o-matic Vigor Tester สำหรับ Fallout: New Vegas

ความสามารถ:
  1. แปลงไฟล์ภาพ .PNG ภาษาไทยเป็น .DDS (DXT1/RGBA) และติดตั้งลงโฟลเดอร์เกมทันที
  2. เปิด Web 3D Studio สำหรับหมุนดูโมเดล 3D และพรีวิว Material Texture แบบเรียลไทม์
  3. ตรวจสอบไฟล์ Texture ของตู้ Vit-o-matic ทั้ง 7 หน้าสเตตัส (S-P-E-C-I-A-L)
"""
from __future__ import annotations

import argparse
import http.server
import os
import socketserver
import sys
import webbrowser
from pathlib import Path

from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
GAME_DIR = Path(r"d:\SteamLibrary\steamapps\common\Fallout New Vegas\Data")
EXTRACTED_DIR = ROOT / "extracted_assets" / "vigortester" / "textures" / "terminals" / "english"
TARGET_GAME_TEX = GAME_DIR / "Textures" / "terminals" / "english"

PAGE_NAMES = {
    0: ("vitomatic_page_0.dds", "STRENGTH (ความแข็งแรง)"),
    1: ("vitomatic_page_1.dds", "PERCEPTION (การรับรู้)"),
    2: ("vitomatic_page_2.dds", "ENDURANCE (ความทนทาน)"),
    3: ("vitomatic_page_3.dds", "CHARISMA (เสน่ห์)"),
    4: ("vitomatic_page_4.dds", "INTELLIGENCE (สติปัญญา)"),
    5: ("vitomatic_special-values1.dds", "AGILITY & SPECIAL VALUES 1 (ความว่องไว)"),
    6: ("vitomatic_special-values2.dds", "LUCK & SPECIAL VALUES 2 (โชคชะตา)"),
}


def encode_dxt1_level(img_np):
    """เข้ารหัส 4x4 blocks เป็น DXT1 พร้อม color palette 4 สีแบบเวกเตอร์ความเร็วสูง"""
    import numpy as np

    h, w, _ = img_np.shape
    bh, bw = max(1, h // 4), max(1, w // 4)
    if h < 4 or w < 4:
        pad_img = np.zeros((max(4, h), max(4, w), 3), dtype=np.uint8)
        pad_img[:h, :w] = img_np
        blocks = pad_img.reshape(1, 4, 1, 4, 3).swapaxes(1, 2).reshape(-1, 16, 3)
    else:
        blocks = img_np.reshape(bh, 4, bw, 4, 3).swapaxes(1, 2).reshape(-1, 16, 3)

    c_min = blocks.min(axis=1)
    c_max = blocks.max(axis=1)

    r_max = (c_max[:, 0] >> 3).astype(np.uint16)
    g_max = (c_max[:, 1] >> 2).astype(np.uint16)
    b_max = (c_max[:, 2] >> 3).astype(np.uint16)
    c0_16 = (r_max << 11) | (g_max << 5) | b_max

    r_min = (c_min[:, 0] >> 3).astype(np.uint16)
    g_min = (c_min[:, 1] >> 2).astype(np.uint16)
    b_min = (c_min[:, 2] >> 3).astype(np.uint16)
    c1_16 = (r_min << 11) | (g_min << 5) | b_min

    same = c0_16 <= c1_16
    c0_16[same] = np.maximum(c1_16[same] + 1, 1)

    def c565_to_rgb(c):
        r = (((c >> 11) & 0x1F) * 527 + 23) >> 6
        g = (((c >> 5) & 0x3F) * 259 + 33) >> 6
        b = ((c & 0x1F) * 527 + 23) >> 6
        return np.stack([r, g, b], axis=-1).astype(np.uint8)

    p0 = c565_to_rgb(c0_16)[:, None, :]
    p1 = c565_to_rgb(c1_16)[:, None, :]
    p2 = ((2 * p0.astype(np.int32) + p1.astype(np.int32)) // 3).astype(np.uint8)
    p3 = ((p0.astype(np.int32) + 2 * p1.astype(np.int32)) // 3).astype(np.uint8)

    palette = np.stack([p0, p1, p2, p3], axis=2)
    diff = blocks[:, :, None, :].astype(np.int32) - palette.astype(np.int32)
    dist = np.sum(diff ** 2, axis=-1)
    indices = np.argmin(dist, axis=-1).astype(np.uint32)

    shifts = (np.arange(16, dtype=np.uint32) * 2)[None, :]
    packed_idx = np.bitwise_or.reduce(indices << shifts, axis=1)

    block_data = np.empty((len(blocks),), dtype=[('c0', '<u2'), ('c1', '<u2'), ('idx', '<u4')])
    block_data['c0'] = c0_16
    block_data['c1'] = c1_16
    block_data['idx'] = packed_idx
    return block_data.tobytes()


def save_dxt1_dds(image: Image.Image, out_path: str):
    """บันทึกไฟล์ภาพเป็น DirectDraw Surface (DDS) แบบ DXT1 พร้อม 11 Mipmaps มาตรฐาน Bethesda"""
    import numpy as np
    import struct

    image = image.convert('RGB')
    w, h = image.size

    mip_data = []
    cur_img = image
    cur_w, cur_h = w, h
    num_mips = 0
    while True:
        num_mips += 1
        arr = np.array(cur_img)
        mip_data.append(encode_dxt1_level(arr))
        if cur_w == 1 and cur_h == 1:
            break
        cur_w = max(1, cur_w // 2)
        cur_h = max(1, cur_h // 2)
        cur_img = cur_img.resize((cur_w, cur_h), Image.Resampling.LANCZOS)

    header = bytearray(128)
    header[0:4] = b'DDS '
    struct.pack_into('<I', header, 4, 124)  # size
    struct.pack_into('<I', header, 8, 0x000A1007)  # flags
    struct.pack_into('<I', header, 12, h)
    struct.pack_into('<I', header, 16, w)
    struct.pack_into('<I', header, 20, (w * h) // 2)  # pitchOrLinearSize
    struct.pack_into('<I', header, 24, 0)  # depth
    struct.pack_into('<I', header, 28, num_mips)  # mipmaps
    struct.pack_into('<I', header, 76, 32)  # pf size
    struct.pack_into('<I', header, 80, 0x00000004)  # pf flags (FourCC)
    header[84:88] = b'DXT1'
    struct.pack_into('<I', header, 108, 0x00401008)  # caps

    all_bytes = bytes(header) + b''.join(mip_data)
    with open(out_path, 'wb') as f:
        f.write(all_bytes)
    return len(all_bytes)


def convert_and_install(png_path: str, page_num: int = 0, target_dds: str | None = None):
    """แปลง PNG เป็น DDS (DXT1 with Mipmaps) และติดตั้งเข้าเกมหรือบันทึกตาม path ที่ระบุ"""
    if not os.path.exists(png_path):
        print(f"Error: ไม่พบไฟล์ภาพต้นฉบับ: {png_path}")
        return False

    im = Image.open(png_path)
    print(f"กำลังเปิดภาพ: {png_path} ({im.size[0]}x{im.size[1]}, Mode: {im.mode})")

    # ปรับขนาดเป็น 1024x1024 ถ้าจำเป็น
    if im.size != (1024, 1024):
        print(f"แจ้งเตือน: ปรับขนาดภาพจาก {im.size} เป็น 1024x1024 ตามมาตรฐานเกม")
        im = im.resize((1024, 1024), Image.Resampling.LANCZOS)

    if target_dds is None:
        filename, label = PAGE_NAMES.get(page_num, (f"vitomatic_page_{page_num}.dds", f"Page {page_num}"))
        target_dds = str(TARGET_GAME_TEX / filename)
        print(f"เป้าหมายหน้า: {label}")

    os.makedirs(os.path.dirname(target_dds), exist_ok=True)
    size = save_dxt1_dds(im, target_dds)
    print(f"สำเร็จ: บันทึกไฟล์ DXT1 DDS (Mipmaps 11) -> {target_dds} ({size} bytes)")
    print("คุณสามารถเข้าเกมเพื่อดูผลลัพธ์บนตู้ Vit-o-matic ในบ้าน Doc Mitchell ได้ทันที!")
    return True


def launch_preview_server(port: int = 8085):
    """เปิด Local Web Server และเปิดเบราว์เซอร์ไปที่ 3D Studio"""
    os.chdir(str(ROOT))
    handler = http.server.SimpleHTTPRequestHandler
    
    # อนุญาตให้ reuse port
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), handler) as httpd:
        url = f"http://localhost:{port}/tools/vigor_tester_viewer.html"
        print("=" * 70)
        print("  Vit-o-matic Vigor Tester — 3D & Texture Preview Studio")
        print("=" * 70)
        print(f"Web Server กำลังทำงานที่: {url}")
        print("กำลังเปิดเบราว์เซอร์อัตโนมัติ... (กด Ctrl+C เพื่อหยุดการทำงาน)")
        print("=" * 70)
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nปิด Server เรียบร้อยแล้ว")


def list_pages():
    """แสดงรายชื่อ Texture ทั้งหมดของตู้ Vit-o-matic"""
    print("=" * 70)
    print("  รายชื่อไฟล์ Texture ของตู้ Vit-o-matic Vigor Tester")
    print("=" * 70)
    for p_id, (fname, label) in PAGE_NAMES.items():
        extracted_p = EXTRACTED_DIR / fname.replace(".dds", ".png")
        game_p = TARGET_GAME_TEX / fname
        extracted_status = "OK (PNG พร้อมแต่ง)" if extracted_p.exists() else "Missing"
        game_status = "Custom Installed" if game_p.exists() else "Vanilla BSA"
        print(f"[{p_id}] {label:<40}")
        print(f"    ไฟล์ DDS: {fname}")
        print(f"    ไฟล์ PNG ต้นฉบับ: {extracted_status}")
        print(f"    สถานะในเกม:      {game_status}")
        print()


def main():
    parser = argparse.ArgumentParser(description="เครื่องมือจัดการและพรีวิว Texture ตู้ Vit-o-matic Vigor Tester")
    parser.add_argument("--preview", action="store_true", help="เปิด 3D & Texture Preview Studio ในเบราว์เซอร์")
    parser.add_argument("--convert", type=str, help="แปลงไฟล์ PNG เป็น DDS และติดตั้งเข้าเกม")
    parser.add_argument("--page", type=int, default=0, help="เลขหน้าสเตตัส (0=STR, 1=PER, 2=END, 3=CHA, 4=INT, 5=AGI, 6=LCK)")
    parser.add_argument("--out", type=str, help="ตำแหน่งบันทึกไฟล์ DDS ปลายทาง (ถ้าไม่ระบุจะลงโฟลเดอร์เกม Data/ ทันที)")
    parser.add_argument("--list", action="store_true", help="แสดงรายชื่อหน้า Texture ทั้งหมด")
    parser.add_argument("--port", type=int, default=8085, help="Port สำหรับ Web Preview Server (ค่าเริ่มต้น 8085)")

    args = parser.parse_args()

    if args.list:
        list_pages()
    elif args.convert:
        convert_and_install(args.convert, page_num=args.page, target_dds=args.out)
    elif args.preview:
        launch_preview_server(port=args.port)
    else:
        # ค่าเริ่มต้นถ้าไม่ระบุ argument ให้แสดง list และแนะนำวิธีใช้งาน
        list_pages()
        print("คำสั่งแนะนำ:")
        print("  เปิด 3D Preview Studio:   python pipeline/vigor_tester_tool.py --preview")
        print("  แปลงรูปและลงม็อดเข้าเกม: python pipeline/vigor_tester_tool.py --convert my_thai_str.png --page 0")


if __name__ == "__main__":
    main()
