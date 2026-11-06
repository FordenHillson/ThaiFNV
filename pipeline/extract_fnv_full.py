#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_fnv_full.py — Comprehensive extractor for Fallout: New Vegas + all DLCs
Extracts all text into categorized files with DLC and Speaker metadata.
Exports both by_category/ and by_dlc/ views.
"""
from __future__ import annotations
import csv
import json
import os
import struct
import sys
import time
import zlib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = r"D:\SteamLibrary\steamapps\common\Fallout New Vegas\Data"
OUTPUT_DIR = r"D:\backup\github\ThaiFNV\extracted"

PLUGINS = [
    ("FalloutNV.esm", "Base Game", "Base_Game"),
    ("DeadMoney.esm", "Dead Money", "Dead_Money"),
    ("HonestHearts.esm", "Honest Hearts", "Honest_Hearts"),
    ("OldWorldBlues.esm", "Old World Blues", "Old_World_Blues"),
    ("LonesomeRoad.esm", "Lonesome Road", "Lonesome_Road"),
    ("GunRunnersArsenal.esm", "Gun Runners' Arsenal", "Gun_Runners_Arsenal"),
    ("ClassicPack.esm", "Classic Pack", "Courier_Stash"),
    ("CaravanPack.esm", "Caravan Pack", "Courier_Stash"),
    ("MercenaryPack.esm", "Mercenary Pack", "Courier_Stash"),
    ("TribalPack.esm", "Tribal Pack", "Courier_Stash"),
]

EMOTIONS = {
    0: "Neutral",
    1: "Anger",
    2: "Disgust",
    3: "Fear",
    4: "Sad",
    5: "Happy",
    6: "Surprise",
    7: "Pained",
}


def decode_str(b: bytes) -> str:
    return b.split(b"\x00")[0].decode("cp1252", "replace").strip()


def is_extractable(text: str) -> bool:
    if not text:
        return False
    for c in text:
        if c in "\r\n\t":
            continue
        if not c.isprintable():
            return False
    return True


def decompress(payload: bytes) -> bytes:
    try:
        return zlib.decompress(payload[4:])
    except Exception:
        try:
            return zlib.decompress(payload)
        except Exception:
            return b""


class FNVExtractor:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        # plugin_name -> dict of formid -> (name, edid)
        self.actors = {}
        self.actors_tplt = {}
        self.lvlc_targets = {}
        self.factions = {}
        self.voice_types = {}
        self.quests = {}
        self.dials = {}

    def resolve_ref(self, caller_plugin: str, target_fid: int, ref_dict: dict) -> tuple[str, str] | None:
        high = (target_fid >> 24)
        if high == 0:
            res = ref_dict.get("FalloutNV.esm", {}).get(target_fid)
            if res:
                return res
        elif high == 1:
            res = ref_dict.get(caller_plugin, {}).get(target_fid)
            if res:
                return res
        # Global fallback search across all plugins
        for p in PLUGINS:
            res = ref_dict.get(p[0], {}).get(target_fid)
            if res:
                return res
        return None

    def run_pass1(self):
        """Pass 1: Collect reference tables (Actors, Factions, Voice Types, Quests, DIALs)"""
        print("=== PASS 1: Indexing References & Templates across All Plugins ===")
        for fname, dlc_title, _ in PLUGINS:
            fpath = os.path.join(self.data_dir, fname)
            if not os.path.exists(fpath):
                print(f"Warning: {fpath} not found!")
                continue

            self.actors[fname] = {}
            self.actors_tplt[fname] = {}
            self.lvlc_targets[fname] = {}
            self.factions[fname] = {}
            self.voice_types[fname] = {}
            self.quests[fname] = {}
            self.dials[fname] = {}

            with open(fpath, "rb") as f:
                data = f.read()

            n = len(data)
            tes4_size = struct.unpack_from("<I", data, 4)[0]

            def walk(pos, end):
                while pos < end:
                    if pos + 24 > end:
                        break
                    sig = data[pos:pos + 4]
                    size = struct.unpack_from("<I", data, pos + 4)[0]
                    if size <= 0:
                        break
                    if sig == b"GRUP":
                        if pos + size > end:
                            break
                        walk(pos + 24, pos + size)
                        pos += size
                    else:
                        if pos + 24 + size > end:
                            break
                        flags = struct.unpack_from("<I", data, pos + 8)[0]
                        fid = struct.unpack_from("<I", data, pos + 12)[0]
                        if sig in (b"NPC_", b"CREA", b"TACT", b"FACT", b"VTYP", b"QUST", b"DIAL", b"LVLC", b"LVLN"):
                            payload = data[pos + 24:pos + 24 + size]
                            if flags & 0x00040000:
                                payload = decompress(payload)
                            edid = ""
                            full = ""
                            tplt = None
                            lvlo_list = []
                            ip = 0
                            while ip + 6 <= len(payload):
                                ssig = payload[ip:ip + 4].decode("ascii", "replace")
                                ssz = struct.unpack_from("<H", payload, ip + 4)[0]
                                sval = payload[ip + 6:ip + 6 + ssz]
                                if ssig == "EDID":
                                    edid = decode_str(sval)
                                elif ssig == "FULL":
                                    full = decode_str(sval)
                                elif ssig == "TPLT" and len(sval) >= 4:
                                    tplt = struct.unpack_from("<I", sval, 0)[0]
                                elif ssig == "LVLO" and len(sval) >= 8:
                                    tfid = struct.unpack_from("<I", sval, 4)[0]
                                    lvlo_list.append(tfid)
                                ip += 6 + ssz

                            if sig in (b"NPC_", b"CREA", b"TACT"):
                                self.actors[fname][fid] = [full, edid]
                                if tplt:
                                    self.actors_tplt[fname][fid] = tplt
                            elif sig in (b"LVLC", b"LVLN"):
                                self.lvlc_targets[fname][fid] = lvlo_list
                            elif sig == b"FACT":
                                self.factions[fname][fid] = (full if full else edid, edid)
                            elif sig == b"VTYP":
                                self.voice_types[fname][fid] = (edid, edid)
                            elif sig == b"QUST":
                                self.quests[fname][fid] = (full if full else edid, edid)
                            elif sig == b"DIAL":
                                self.dials[fname][fid] = (full if full else edid, edid)

                        pos += 24 + size

            walk(24 + tes4_size, n)

        # Resolve Actor templates (TPLT -> Leveled list or base NPC)
        for fname in self.actors:
            for fid, (full, edid) in list(self.actors[fname].items()):
                if not full:
                    tplt = self.actors_tplt[fname].get(fid)
                    if tplt:
                        # Direct template
                        tres = self.resolve_ref(fname, tplt, self.actors)
                        if tres and tres[0]:
                            self.actors[fname][fid][0] = tres[0]
                        else:
                            # Leveled list template
                            for p in PLUGINS:
                                ltargets = self.lvlc_targets.get(p[0], {}).get(tplt)
                                if ltargets:
                                    for target_fid in ltargets:
                                        res2 = self.resolve_ref(fname, target_fid, self.actors)
                                        if res2 and res2[0]:
                                            self.actors[fname][fid][0] = res2[0]
                                            break
                                    if self.actors[fname][fid][0]:
                                        break
                # Convert back to tuple (display_name, edid)
                curr_full = self.actors[fname][fid][0]
                self.actors[fname][fid] = (curr_full if curr_full else edid, edid)

            dlc_name = [p[1] for p in PLUGINS if p[0] == fname][0]
            print(f"  [{dlc_name}] Indexed: {len(self.actors[fname])} Actors, "
                  f"{len(self.factions[fname])} Factions, {len(self.quests[fname])} Quests, "
                  f"{len(self.dials[fname])} Topics")

    def run_pass2(self):
        """Pass 2: Extract all strings and categorize them"""
        print("\n=== PASS 2: Extracting Text & Categorizing ===")

        dialogue_rows = []
        topic_rows = []
        quest_rows = []
        message_rows = []
        terminal_rows = []
        note_rows = []
        book_rows = []
        item_rows = []
        perk_rows = []
        world_rows = []
        loadscreen_rows = []
        gamestring_rows = []
        other_rows = []

        total_records_processed = 0

        for fname, dlc_title, dlc_folder in PLUGINS:
            fpath = os.path.join(self.data_dir, fname)
            if not os.path.exists(fpath):
                continue

            with open(fpath, "rb") as f:
                data = f.read()

            n = len(data)
            tes4_size = struct.unpack_from("<I", data, 4)[0]

            def walk_records(pos, end, current_dial_fid=None):
                nonlocal total_records_processed
                while pos < end:
                    if pos + 24 > end:
                        break
                    sig = data[pos:pos + 4]
                    size = struct.unpack_from("<I", data, pos + 4)[0]
                    if size <= 0:
                        break
                    if sig == b"GRUP":
                        if pos + size > end:
                            break
                        glabel = data[pos + 8:pos + 12]
                        gtype = struct.unpack_from("<i", data, pos + 12)[0]
                        next_dial = struct.unpack("<I", glabel)[0] if gtype == 7 else current_dial_fid
                        walk_records(pos + 24, pos + size, next_dial)
                        pos += size
                    else:
                        if pos + 24 + size > end:
                            break
                        total_records_processed += 1
                        flags = struct.unpack_from("<I", data, pos + 8)[0]
                        fid = struct.unpack_from("<I", data, pos + 12)[0]
                        rtype = sig.decode("ascii", "replace")
                        payload = data[pos + 24:pos + 24 + size]
                        if flags & 0x00040000:
                            payload = decompress(payload)

                        self.process_record(
                            fname, dlc_title, dlc_folder, rtype, fid, payload, current_dial_fid,
                            dialogue_rows, topic_rows, quest_rows, message_rows,
                            terminal_rows, note_rows, book_rows, item_rows,
                            perk_rows, world_rows, loadscreen_rows, gamestring_rows,
                            other_rows
                        )
                        pos += 24 + size

            walk_records(24 + tes4_size, n)

        print(f"\nExtraction complete! Total records scanned: {total_records_processed:,}")
        return {
            "FNV_Dialogue": dialogue_rows,
            "FNV_TopicNames": topic_rows,
            "FNV_Quests": quest_rows,
            "FNV_Messages": message_rows,
            "FNV_Terminals": terminal_rows,
            "FNV_Notes": note_rows,
            "FNV_Books": book_rows,
            "FNV_Items": item_rows,
            "FNV_Perks_Skills": perk_rows,
            "FNV_World_Objects": world_rows,
            "FNV_LoadScreens": loadscreen_rows,
            "FNV_GameSettings": gamestring_rows,
            "FNV_Other": other_rows,
        }

    def process_record(self, fname, dlc_title, dlc_folder, rtype, fid, payload, parent_dial_fid,
                       dialogue_rows, topic_rows, quest_rows, message_rows,
                       terminal_rows, note_rows, book_rows, item_rows,
                       perk_rows, world_rows, loadscreen_rows, gamestring_rows,
                       other_rows):
        fid_hex = f"{fid:08X}"

        # 1. DIALOGUE (INFO)
        if rtype == "INFO":
            self.process_info(fname, dlc_title, dlc_folder, fid, fid_hex, payload, parent_dial_fid, dialogue_rows)
            return

        edid = ""
        full = ""
        desc = ""
        other_subs = []
        ip = 0
        n = len(payload)
        while ip + 6 <= n:
            ssig = payload[ip:ip + 4].decode("ascii", "replace")
            ssz = struct.unpack_from("<H", payload, ip + 4)[0]
            sval = payload[ip + 6:ip + 6 + ssz]
            if ssig == "EDID":
                edid = decode_str(sval)
            elif ssig == "FULL":
                full = decode_str(sval)
            elif ssig == "DESC":
                desc = decode_str(sval)
            else:
                other_subs.append((ssig, sval))
            ip += 6 + ssz

        base_meta = {
            "DLC": dlc_title,
            "DLC_Folder": dlc_folder,
            "Plugin": fname,
            "RecordType": rtype,
            "FormID": fid_hex,
            "EditorID": edid,
            "TH": "",
            "Status": "",
            "Notes": "",
        }

        # 2. TOPIC NAMES (DIAL)
        if rtype == "DIAL":
            if full and is_extractable(full):
                row = dict(base_meta)
                row.update({
                    "Subrecord": "FULL",
                    "ParentContext": "",
                    "EN": full,
                })
                topic_rows.append(row)
            return

        # 3. QUESTS (QUST)
        if rtype == "QUST":
            quest_name = full if full else edid
            if full and is_extractable(full):
                row = dict(base_meta)
                row.update({
                    "Subrecord": "FULL",
                    "ParentContext": "Quest Title",
                    "EN": full,
                })
                quest_rows.append(row)
            for ssig, sval in other_subs:
                if ssig == "NNAM":
                    nnam = decode_str(sval)
                    if nnam and is_extractable(nnam):
                        row = dict(base_meta)
                        row.update({
                            "Subrecord": "NNAM",
                            "ParentContext": f"Objective: {quest_name}",
                            "EN": nnam,
                        })
                        quest_rows.append(row)
            return

        # 4. MESSAGES (MESG)
        if rtype == "MESG":
            mesg_title = full if full else edid
            if full and is_extractable(full):
                row = dict(base_meta)
                row.update({
                    "Subrecord": "FULL",
                    "ParentContext": "Message Title",
                    "EN": full,
                })
                message_rows.append(row)
            if desc and is_extractable(desc):
                row = dict(base_meta)
                row.update({
                    "Subrecord": "DESC",
                    "ParentContext": mesg_title,
                    "EN": desc,
                })
                message_rows.append(row)
            for ssig, sval in other_subs:
                if ssig == "ITXT":
                    itxt = decode_str(sval)
                    if itxt and is_extractable(itxt):
                        row = dict(base_meta)
                        row.update({
                            "Subrecord": "ITXT",
                            "ParentContext": f"Button: {mesg_title}",
                            "EN": itxt,
                        })
                        message_rows.append(row)
            return

        # 5. TERMINALS (TERM)
        if rtype == "TERM":
            term_title = full if full else edid
            if full and is_extractable(full):
                row = dict(base_meta)
                row.update({
                    "Subrecord": "FULL",
                    "ParentContext": "Terminal Title",
                    "EN": full,
                })
                terminal_rows.append(row)
            if desc and is_extractable(desc):
                row = dict(base_meta)
                row.update({
                    "Subrecord": "DESC",
                    "ParentContext": term_title,
                    "EN": desc,
                })
                terminal_rows.append(row)
            for ssig, sval in other_subs:
                if ssig == "ITXT":
                    itxt = decode_str(sval)
                    if itxt and is_extractable(itxt):
                        row = dict(base_meta)
                        row.update({
                            "Subrecord": "ITXT",
                            "ParentContext": f"Menu Item: {term_title}",
                            "EN": itxt,
                        })
                        terminal_rows.append(row)
                elif ssig == "RNAM":
                    rnam = decode_str(sval)
                    if rnam and is_extractable(rnam):
                        row = dict(base_meta)
                        row.update({
                            "Subrecord": "RNAM",
                            "ParentContext": f"Response: {term_title}",
                            "EN": rnam,
                        })
                        terminal_rows.append(row)
            return

        # 6. NOTES (NOTE)
        if rtype == "NOTE":
            note_title = full if full else edid
            if full and is_extractable(full):
                row = dict(base_meta)
                row.update({
                    "Subrecord": "FULL",
                    "ParentContext": "Note Title",
                    "EN": full,
                })
                note_rows.append(row)
            for ssig, sval in other_subs:
                if ssig == "TNAM":
                    tnam = decode_str(sval)
                    if tnam and is_extractable(tnam):
                        row = dict(base_meta)
                        row.update({
                            "Subrecord": "TNAM",
                            "ParentContext": note_title,
                            "EN": tnam,
                        })
                        note_rows.append(row)
            return

        # 7. BOOKS (BOOK)
        if rtype == "BOOK":
            book_title = full if full else edid
            if full and is_extractable(full):
                row = dict(base_meta)
                row.update({
                    "Subrecord": "FULL",
                    "ParentContext": "Book Title",
                    "EN": full,
                })
                book_rows.append(row)
            if desc and is_extractable(desc):
                row = dict(base_meta)
                row.update({
                    "Subrecord": "DESC",
                    "ParentContext": book_title,
                    "EN": desc,
                })
                book_rows.append(row)
            return

        # 8. LOADING SCREENS (LSCR)
        if rtype == "LSCR":
            if desc and is_extractable(desc):
                row = dict(base_meta)
                row.update({
                    "Subrecord": "DESC",
                    "ParentContext": "Loading Screen",
                    "EN": desc,
                })
                loadscreen_rows.append(row)
            return

        # 9. GAME SETTINGS (GMST)
        if rtype == "GMST":
            if edid.startswith("s"):
                for ssig, sval in other_subs:
                    if ssig == "DATA":
                        s_text = decode_str(sval)
                        if s_text and is_extractable(s_text):
                            row = dict(base_meta)
                            row.update({
                                "Subrecord": "DATA",
                                "ParentContext": "Game Setting UI String",
                                "EN": s_text,
                            })
                            gamestring_rows.append(row)
            return

        # 10. ITEMS & EQUIPMENT
        item_types = {
            "WEAP": "Weapon",
            "ARMO": "Armor/Clothing",
            "AMMO": "Ammunition",
            "ALCH": "Ingestible/Chem/Food",
            "MISC": "Misc Item",
            "KEYM": "Key",
            "IMOD": "Weapon Mod",
            "CHIP": "Casino Chip",
            "CCRD": "Caravan Card",
            "RCPE": "Recipe",
        }
        if rtype in item_types:
            itype = item_types[rtype]
            if full and is_extractable(full):
                row = dict(base_meta)
                row.update({
                    "Subrecord": "FULL",
                    "ItemType": itype,
                    "EN": full,
                })
                item_rows.append(row)
            if desc and is_extractable(desc):
                row = dict(base_meta)
                row.update({
                    "Subrecord": "DESC",
                    "ItemType": f"{itype} Description",
                    "EN": desc,
                })
                item_rows.append(row)
            return

        # 11. PERKS, STATS & SPELLS
        perk_types = {
            "PERK": "Perk/Trait",
            "AVIF": "SPECIAL/Skill/ActorValue",
            "SPEL": "Spell/Ability",
            "MGEF": "Magic Effect",
            "ENCH": "Object Effect/Enchantment",
            "CHAL": "Challenge",
        }
        if rtype in perk_types:
            ptype = perk_types[rtype]
            if full and is_extractable(full):
                row = dict(base_meta)
                row.update({
                    "Subrecord": "FULL",
                    "Category": ptype,
                    "EN": full,
                })
                perk_rows.append(row)
            if desc and is_extractable(desc):
                row = dict(base_meta)
                row.update({
                    "Subrecord": "DESC",
                    "Category": f"{ptype} Description",
                    "EN": desc,
                })
                perk_rows.append(row)
            return

        # 12. WORLD OBJECTS & ACTORS
        world_types = {
            "NPC_": "NPC Name",
            "CREA": "Creature Name",
            "FACT": "Faction Name",
            "WRLD": "Worldspace",
            "CELL": "Location/Interior Cell",
            "ACTI": "Activator",
            "TACT": "Talking Activator",
            "CONT": "Container",
            "DOOR": "Door",
            "FURN": "Furniture",
        }
        if rtype in world_types:
            wtype = world_types[rtype]
            if full and is_extractable(full):
                row = dict(base_meta)
                row.update({
                    "Subrecord": "FULL",
                    "ObjectType": wtype,
                    "EN": full,
                })
                world_rows.append(row)
            if rtype == "FACT":
                for ssig, sval in other_subs:
                    if ssig == "RNAM":
                        rnam = decode_str(sval)
                        if rnam and is_extractable(rnam):
                            row = dict(base_meta)
                            row.update({
                                "Subrecord": "RNAM",
                                "ObjectType": f"Faction Rank ({full or edid})",
                                "EN": rnam,
                            })
                            world_rows.append(row)
            return

        # 13. OTHER
        if full and is_extractable(full):
            row = dict(base_meta)
            row.update({
                "Subrecord": "FULL",
                "ParentContext": "",
                "EN": full,
            })
            other_rows.append(row)
        if desc and is_extractable(desc):
            row = dict(base_meta)
            row.update({
                "Subrecord": "DESC",
                "ParentContext": full or edid,
                "EN": desc,
            })
            other_rows.append(row)

    def process_info(self, fname, dlc_title, dlc_folder, fid, fid_hex, payload, parent_dial_fid, dialogue_rows):
        """Extract INFO dialogue responses, speaker, emotions, and actor notes"""
        ip = 0
        n = len(payload)

        qsti = None
        anam_fid = None
        ctda_conditions = []
        rnam_prompt = ""
        responses = []
        
        current_emotion_type = 0
        current_emotion_val = 50
        current_notes = ""

        while ip + 6 <= n:
            ssig = payload[ip:ip + 4].decode("ascii", "replace")
            ssz = struct.unpack_from("<H", payload, ip + 4)[0]
            sval = payload[ip + 6:ip + 6 + ssz]

            if ssig == "QSTI" and len(sval) >= 4:
                qsti = struct.unpack_from("<I", sval, 0)[0]
            elif ssig == "ANAM" and len(sval) >= 4:
                anam_fid = struct.unpack_from("<I", sval, 0)[0]
            elif ssig == "RNAM":
                rnam_prompt = decode_str(sval)
            elif ssig == "TRDT" and len(sval) >= 8:
                current_emotion_type, current_emotion_val = struct.unpack_from("<II", sval, 0)
            elif ssig == "NAM2":
                current_notes = decode_str(sval)
            elif ssig == "NAM1":
                line_text = decode_str(sval)
                if line_text and is_extractable(line_text):
                    responses.append({
                        "text": line_text,
                        "emotion_type": current_emotion_type,
                        "emotion_val": current_emotion_val,
                        "notes": current_notes,
                    })
                current_notes = ""
            elif ssig == "CTDA" and len(sval) >= 20:
                fn = struct.unpack_from("<H", sval, 8)[0]
                p1 = struct.unpack_from("<I", sval, 12)[0]
                run_on = struct.unpack_from("<I", sval, 20)[0] if len(sval) >= 24 else 0
                ctda_conditions.append((fn, p1, run_on))

            ip += 6 + ssz

        topic_name = ""
        topic_edid = ""
        if parent_dial_fid:
            res = self.resolve_ref(fname, parent_dial_fid, self.dials)
            if res:
                topic_name, topic_edid = res

        quest_name = ""
        quest_edid = ""
        if qsti:
            res = self.resolve_ref(fname, qsti, self.quests)
            if res:
                quest_name, quest_edid = res

        speaker = ""
        speaker_id = ""
        speaker_type = ""

        # Priority 1: ANAM (Direct Actor FormID)
        if anam_fid:
            res = self.resolve_ref(fname, anam_fid, self.actors)
            if res:
                speaker, speaker_id = res
                speaker_type = "Actor (ANAM)"

        # Priority 2: CTDA GetIsID (fn 72)
        if not speaker:
            for fn, p1, run_on in ctda_conditions:
                if fn == 72 and run_on == 0:
                    res = self.resolve_ref(fname, p1, self.actors)
                    if res:
                        speaker, speaker_id = res
                        speaker_type = "Actor (Condition)"
                        break
            if not speaker:
                for fn, p1, run_on in ctda_conditions:
                    if fn == 72:
                        res = self.resolve_ref(fname, p1, self.actors)
                        if res:
                            speaker, speaker_id = res
                            speaker_type = "Actor (Condition)"
                            break

        # Priority 3: CTDA GetInFaction (fn 71)
        if not speaker:
            for fn, p1, run_on in ctda_conditions:
                if fn == 71 and run_on == 0:
                    res = self.resolve_ref(fname, p1, self.factions)
                    if res:
                        speaker = f"[Faction: {res[0]}]"
                        speaker_id = res[1]
                        speaker_type = "Faction"
                        break

        # Priority 4: CTDA GetIsVoiceType (fn 74)
        if not speaker:
            for fn, p1, run_on in ctda_conditions:
                if fn == 74 and run_on == 0:
                    res = self.resolve_ref(fname, p1, self.voice_types)
                    if res:
                        speaker = f"[Voice: {res[0]}]"
                        speaker_id = res[1]
                        speaker_type = "VoiceType"
                        break

        # Priority 5: Fallback to Topic / Quest context
        if not speaker:
            if topic_edid and any(c.isupper() for c in topic_edid):
                speaker = f"[Context: {topic_edid}]"
                speaker_type = "TopicContext"
            elif quest_name:
                speaker = f"[Context: {quest_name}]"
                speaker_type = "QuestContext"

        for resp_idx, resp in enumerate(responses, 1):
            ename = EMOTIONS.get(resp["emotion_type"], f"Type {resp['emotion_type']}")
            emotion_str = f"{ename} ({resp['emotion_val']})"

            text = resp["text"]
            combined_notes = resp["notes"]
            if text.startswith("{") and "}" in text:
                closing = text.index("}")
                inline_dir = text[1:closing]
                combined_notes = f"[{inline_dir}] {combined_notes}".strip()

            dialogue_rows.append({
                "DLC": dlc_title,
                "DLC_Folder": dlc_folder,
                "Plugin": fname,
                "Category": "Dialogue",
                "FormID": fid_hex,
                "Subrecord": "NAM1",
                "ResponseIndex": resp_idx,
                "Speaker": speaker,
                "Speaker_ID": speaker_id,
                "Speaker_Type": speaker_type,
                "Emotion": emotion_str,
                "ActorNotes": combined_notes,
                "Topic_Name": topic_name,
                "Topic_EDID": topic_edid,
                "Quest_Name": quest_name,
                "Quest_EDID": quest_edid,
                "EN": text,
                "TH": "",
                "Status": "",
                "Notes": "",
            })

        if rnam_prompt and is_extractable(rnam_prompt):
            dialogue_rows.append({
                "DLC": dlc_title,
                "DLC_Folder": dlc_folder,
                "Plugin": fname,
                "Category": "Dialogue Prompt",
                "FormID": fid_hex,
                "Subrecord": "RNAM",
                "ResponseIndex": 0,
                "Speaker": "Player / Courier",
                "Speaker_ID": "Player",
                "Speaker_Type": "Player",
                "Emotion": "",
                "ActorNotes": "Player Choice Prompt",
                "Topic_Name": topic_name,
                "Topic_EDID": topic_edid,
                "Quest_Name": quest_name,
                "Quest_EDID": quest_edid,
                "EN": rnam_prompt,
                "TH": "",
                "Status": "",
                "Notes": "",
            })


def save_csv(path: str, rows: list[dict], fieldnames: list[str]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        all_fields = ["ID"] + [f for f in fieldnames if f != "DLC_Folder"]
        writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()
        for idx, r in enumerate(rows, 1):
            r["ID"] = idx
            writer.writerow(r)


def main():
    t0 = time.time()
    extractor = FNVExtractor(DATA_DIR)
    extractor.run_pass1()
    results = extractor.run_pass2()

    by_category_dir = os.path.join(OUTPUT_DIR, "by_category")
    by_dlc_dir = os.path.join(OUTPUT_DIR, "by_dlc")
    sheets_dir = os.path.join(OUTPUT_DIR, "sheets")

    dialogue_fields = [
        "DLC", "Plugin", "Category", "FormID", "Subrecord", "ResponseIndex",
        "Speaker", "Speaker_ID", "Speaker_Type", "Emotion", "ActorNotes",
        "Topic_Name", "Topic_EDID", "Quest_Name", "Quest_EDID",
        "EN", "TH", "Status", "Notes"
    ]

    standard_fields = [
        "DLC", "Plugin", "RecordType", "Subrecord", "FormID", "EditorID",
        "ParentContext", "EN", "TH", "Status", "Notes"
    ]

    item_fields = [
        "DLC", "Plugin", "RecordType", "Subrecord", "FormID", "EditorID",
        "ItemType", "EN", "TH", "Status", "Notes"
    ]

    perk_fields = [
        "DLC", "Plugin", "RecordType", "Subrecord", "FormID", "EditorID",
        "Category", "EN", "TH", "Status", "Notes"
    ]

    world_fields = [
        "DLC", "Plugin", "RecordType", "Subrecord", "FormID", "EditorID",
        "ObjectType", "EN", "TH", "Status", "Notes"
    ]

    field_map = {
        "FNV_Dialogue": dialogue_fields,
        "FNV_Items": item_fields,
        "FNV_Perks_Skills": perk_fields,
        "FNV_World_Objects": world_fields,
    }

    print("\n=== Saving CSV Files: by_category/ & sheets/ ===")
    summary_stats = {}
    dlc_breakdown = {}

    for cat_name, rows in results.items():
        fields = field_map.get(cat_name, standard_fields)
        
        # 1. Save to by_category
        cat_path = os.path.join(by_category_dir, f"{cat_name}.csv")
        save_csv(cat_path, rows, fields)

        # 2. Save to sheets for pipeline integration
        sheet_path = os.path.join(sheets_dir, f"{cat_name}.csv")
        save_csv(sheet_path, rows, fields)

        summary_stats[cat_name] = len(rows)
        print(f"  {cat_name:<20}: {len(rows):>6,} rows")

        for r in rows:
            dlc = r["DLC"]
            dlc_breakdown[dlc] = dlc_breakdown.get(dlc, 0) + 1

    print("\n=== Saving CSV Files: by_dlc/ ===")
    dlc_groups = {}
    for cat_name, rows in results.items():
        fields = field_map.get(cat_name, standard_fields)
        for r in rows:
            folder = r.get("DLC_Folder", "Other")
            dlc_groups.setdefault(folder, {}).setdefault(cat_name, []).append(r)

    for folder, cats in sorted(dlc_groups.items()):
        folder_path = os.path.join(by_dlc_dir, folder)
        folder_rows = sum(len(x) for x in cats.values())
        print(f"  [{folder}] -> {folder_rows:,} rows across {len(cats)} categories")
        for cat_name, c_rows in cats.items():
            fields = field_map.get(cat_name, standard_fields)
            csv_path = os.path.join(folder_path, f"{cat_name}.csv")
            save_csv(csv_path, c_rows, fields)

    total_all = sum(summary_stats.values())

    diag_rows = results["FNV_Dialogue"]
    resolved_diag = sum(1 for r in diag_rows if r["Speaker"] and not r["Speaker"].startswith("[Context"))
    diag_pct = (resolved_diag / max(1, len(diag_rows))) * 100

    print(f"\n==========================================")
    print(f"TOTAL TEXT EXTRACTED: {total_all:,} rows across Base Game + all DLCs!")
    print(f"Dialogue speaker resolution: {resolved_diag:,} / {len(diag_rows):,} ({diag_pct:.1f}%)")
    print(f"Execution time: {time.time() - t0:.2f} seconds")
    print(f"==========================================")

    # Save summary manifest
    summary_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_rows": total_all,
        "categories": summary_stats,
        "dlc_breakdown": dlc_breakdown,
        "dialogue_speaker_resolution": {
            "total_dialogue_lines": len(diag_rows),
            "speaker_identified": resolved_diag,
            "percentage": f"{diag_pct:.1f}%",
        }
    }
    with open(os.path.join(OUTPUT_DIR, "extraction_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)

    # Generate Markdown Report in extracted/README.md
    md_report = f"""# ThaiFNV — ข้อมูลการแกะข้อความเกม (Game Text Extraction Manifest)

สกัดข้อความทั้งหมดจาก **Fallout: New Vegas** ตัวเต็ม พร้อม DLC ครบทั้ง 9 ตัว  
วันที่แกะข้อมูล: `{summary_data['timestamp']}`  
จำนวนข้อความทั้งหมด: **{total_all:,} รายการ**  
การระบุชื่อตัวละครในบทสนทนา (Dialogue Speaker Resolution): **{resolved_diag:,} / {len(diag_rows):,} ({diag_pct:.1f}%)**

---

## 1. ข้อมูลแยกตามหมวดหมู่ (By Category)

ไฟล์ทั้งหมดเก็บอยู่ที่: `extracted/by_category/` และ `extracted/sheets/`

| ชื่อไฟล์ | หมวดหมู่ | ชนิด Record ในเกม | จำนวนแถว |
|---|---|---|---:|
| `FNV_Dialogue.csv` | บทสนทนา (Dialogue) | `INFO` (NAM1 คำพูด, RNAM ช้อยส์) | {summary_stats.get('FNV_Dialogue', 0):,} |
| `FNV_TopicNames.csv` | หัวข้อบทพูดในเมนู | `DIAL` (FULL) | {summary_stats.get('FNV_TopicNames', 0):,} |
| `FNV_Quests.csv` | เควสและเป้าหมาย | `QUST` (FULL ชื่อเควส, NNAM เป้าหมาย) | {summary_stats.get('FNV_Quests', 0):,} |
| `FNV_Messages.csv` | ป๊อปอัป, กล่องข้อความ, ปุ่มกดยืนยัน | `MESG` (FULL, DESC, ITXT) | {summary_stats.get('FNV_Messages', 0):,} |
| `FNV_Terminals.csv` | จอคอมพิวเตอร์เทอร์มินัล | `TERM` (FULL, DESC, ITXT, RNAM) | {summary_stats.get('FNV_Terminals', 0):,} |
| `FNV_Notes.csv` | บันทึก, จดหมาย, ข้อความเทป | `NOTE` (FULL, TNAM) | {summary_stats.get('FNV_Notes', 0):,} |
| `FNV_Books.csv` | หนังสือ และนิตยสารสกิล | `BOOK` (FULL, DESC) | {summary_stats.get('FNV_Books', 0):,} |
| `FNV_Items.csv` | อาวุธ, ชุดเกราะ, ยา, กระสุน, ขยะ, กุญแจ | `WEAP`, `ARMO`, `ALCH`, `AMMO`, `MISC` ฯลฯ | {summary_stats.get('FNV_Items', 0):,} |
| `FNV_Perks_Skills.csv` | Perks, Traits, SPECIAL, เวทมนตร์, ชาเลนจ์ | `PERK`, `AVIF`, `SPEL`, `MGEF`, `CHAL` ฯลฯ | {summary_stats.get('FNV_Perks_Skills', 0):,} |
| `FNV_World_Objects.csv` | ชื่อ NPC, มอนสเตอร์, ฝ่าย, สถานที่, ประตู, กล่อง | `NPC_`, `CREA`, `FACT`, `CELL`, `WRLD` ฯลฯ | {summary_stats.get('FNV_World_Objects', 0):,} |
| `FNV_LoadScreens.csv` | ข้อความ Lore หน้าโหลดเกม | `LSCR` (DESC) | {summary_stats.get('FNV_LoadScreens', 0):,} |
| `FNV_GameSettings.csv` | ข้อความระบบ UI ฮาร์ดโค้ด (Yes, No, Take All...) | `GMST` (DATA) | {summary_stats.get('FNV_GameSettings', 0):,} |
| `FNV_Other.csv` | ข้อความอื่น ๆ | เผ่าพันธุ์, คลาส ฯลฯ | {summary_stats.get('FNV_Other', 0):,} |
| **รวมทั้งหมด** | | | **{total_all:,}** |

---

## 2. ข้อมูลแยกตาม DLC (By DLC)

นอกจากระบุคอลัมน์ `DLC` และ `Plugin` ในทุกบรรทัดของไฟล์หมวดหมู่แล้ว ยังแยกโฟลเดอร์ให้อยู่ใน `extracted/by_dlc/` ดังนี้:

| โฟลเดอร์ใน `extracted/by_dlc/` | DLC | ไฟล์ Plugin | จำนวนข้อความ |
|---|---|---|---:|
| `Base_Game/` | Fallout: New Vegas (ตัวหลัก) | `FalloutNV.esm` | {dlc_breakdown.get('Base Game', 0):,} |
| `Dead_Money/` | Dead Money (DLC 1) | `DeadMoney.esm` | {dlc_breakdown.get('Dead Money', 0):,} |
| `Honest_Hearts/` | Honest Hearts (DLC 2) | `HonestHearts.esm` | {dlc_breakdown.get('Honest Hearts', 0):,} |
| `Old_World_Blues/` | Old World Blues (DLC 3) | `OldWorldBlues.esm` | {dlc_breakdown.get('Old World Blues', 0):,} |
| `Lonesome_Road/` | Lonesome Road (DLC 4) | `LonesomeRoad.esm` | {dlc_breakdown.get('Lonesome Road', 0):,} |
| `Gun_Runners_Arsenal/` | Gun Runners' Arsenal | `GunRunnersArsenal.esm` | {dlc_breakdown.get("Gun Runners' Arsenal", 0):,} |
| `Courier_Stash/` | Classic / Caravan / Mercenary / Tribal Packs | `*.esm` | {dlc_breakdown.get('Classic Pack', 0) + dlc_breakdown.get('Caravan Pack', 0) + dlc_breakdown.get('Mercenary Pack', 0) + dlc_breakdown.get('Tribal Pack', 0):,} |

---

## 3. รายละเอียดคอลัมน์ของไฟล์บทพูด (`FNV_Dialogue.csv`)

โครงสร้างข้อมูลถูกออกแบบมาเพื่อให้นักแปลเข้าใจบริบท น้ำเสียง และสไตล์การพูดของแต่ละตัวละครได้อย่างแม่นยำ:

- **`DLC`**: ระบุ DLC ชัดเจน (เช่น `Dead Money`, `Honest Hearts`, `Base Game`)
- **`Plugin`**: ชื่อไฟล์ `.esm` ต้นฉบับ
- **`FormID`**: FormID ในเกม สำหรับใช้อ้างอิงและอิมพอร์ตกลับเข้า mod
- **`ResponseIndex`**: ลำดับประโยคพูดในเหตุการณ์นั้น (1, 2, 3...)
- **`Speaker`**: **ชื่อตัวละครที่พูด** (เช่น `Doc Mitchell`, `Father Elijah`, `Joshua Graham`, `Craig Boone`, `Veronica`, `Ulysses`, `Doctor Dala` หรือกลุ่มฝ่ายเช่น `[Faction: Boulder City Great Khans]`)
- **`Speaker_ID`**: FormID / EditorID ของตัวละคร
- **`Speaker_Type`**: แหล่งที่มาของการระบุ (`Actor (ANAM)`, `Actor (Condition)`, `Faction`, `VoiceType`, `Player`)
- **`Emotion`**: อารมณ์และระดับความรู้สึกของตัวละครที่เกมตั้งไว้ เช่น `Anger (50)`, `Disgust (20)`, `Happy (50)`, `Sad (50)`, `Surprise (50)`, `Fear (50)`, `Neutral (50)`
- **`ActorNotes`**: โน้ตกำกับเสียงพากย์ของทีมเขียนบท Obsidian (เช่น `[Whispering]`, `[Sarcastic]`, `[Angry] Slower at the end...`)
- **`Topic_Name` & `Topic_EDID`**: ชื่อหัวข้อบทสนทนา
- **`Quest_Name` & `Quest_EDID`**: ชื่อเควสที่เป็นเจ้าของบทสนทนานี้
- **`EN`**: ข้อความภาษาอังกฤษต้นฉบับ
- **`TH`**: ช่องสำหรับแปลภาษาไทย (เว้นว่างไว้ตามคำขอ)
- **`Status`**: สถานะการแปล
- **`Notes`**: หมายเหตุเพิ่มเติมของนักแปล
"""
    with open(os.path.join(OUTPUT_DIR, "README.md"), "w", encoding="utf-8") as f:
        f.write(md_report)

    print("\nGenerated extraction report in extracted/README.md")


if __name__ == "__main__":
    main()
