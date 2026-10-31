// Dump FalloutNV .text after SteamStub decrypts (Frida spawn/attach).
'use strict';

const OUT = 'D:/backup/github/ThaiFNV/Tools/FalloutNV_text.bin';
const META = 'D:/backup/github/ThaiFNV/Tools/FalloutNV_text_meta.json';

function dumpText() {
  const mod = Process.findModuleByName('FalloutNV.exe');
  if (!mod) {
    send({ ok: false, err: 'module not found' });
    return false;
  }
  // Preferred ImageBase 0x400000, .text VA 0x1000, raw size 0xBDD600
  const textRva = 0x1000;
  const textSize = 0xBDD600;
  const text = mod.base.add(textRva);
  const sample = text.readByteArray(64);
  const u8 = new Uint8Array(sample);
  let ent = 0;
  const counts = {};
  for (let i = 0; i < u8.length; i++) {
    counts[u8[i]] = (counts[u8[i]] || 0) + 1;
  }
  const n = u8.length;
  for (const k in counts) {
    const p = counts[k] / n;
    ent -= p * Math.log2(p);
  }
  // Heuristic: encrypted ~7.9+, decrypted code often lower / has recognizable prologues
  const bytes = text.readByteArray(textSize);
  const f = new File(OUT, 'wb');
  f.write(bytes);
  f.close();
  const meta = {
    ok: true,
    base: mod.base.toString(),
    text_va: text.toString(),
    size: textSize,
    sample_entropy: ent,
    sample_hex: Array.from(u8).map(b => ('0' + b.toString(16)).slice(-2)).join(''),
  };
  const mf = new File(META, 'w');
  mf.write(JSON.stringify(meta, null, 2));
  mf.close();
  send(meta);
  return true;
}

// SteamStub runs first; poll until .text looks less than fully random or timeout.
let tries = 0;
const timer = setInterval(function () {
  tries += 1;
  const mod = Process.findModuleByName('FalloutNV.exe');
  if (!mod) {
    if (tries > 40) {
      clearInterval(timer);
      send({ ok: false, err: 'timeout no module' });
    }
    return;
  }
  const text = mod.base.add(0x1000);
  let looksCode = false;
  try {
    // Common MSVC prologues / INT3 / NOP pads after decrypt
    const b = new Uint8Array(text.readByteArray(16));
    // After decrypt, early .text often starts with valid instructions (not pure high-entropy AES)
    // Also check a known absolute code site used by NVSE: SetFloatValue @ 0xA012D0 -> RVA 0x6012D0
    const probe = mod.base.add(0x6012D0);
    const pb = new Uint8Array(probe.readByteArray(8));
    // Expect function-ish bytes (55 8B EC / 8B FF / E9 ...)
    if (pb[0] === 0x55 || pb[0] === 0x8B || pb[0] === 0xE9 || pb[0] === 0x56 || pb[0] === 0x53) {
      looksCode = true;
    }
  } catch (e) {
    send({ ok: false, err: String(e), tries: tries });
  }
  if (looksCode || tries >= 25) {
    clearInterval(timer);
    dumpText();
  }
}, 1000);
