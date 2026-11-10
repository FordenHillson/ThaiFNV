# ThaiFNV Local LoRA Notes

ใช้เมื่อ Phase A (prompt / Modelfile / QA) **ยังไม่ผ่าน** `pipeline/eval_local_mt.py`  
หรือเมื่อต้องการดันคุณภาพโทนผู้พูดให้นิ่งขึ้นหลังรอบแปลจริง

## สถานะปัจจุบัน

- โมเดล inference หลัก: `thaifnv-typhoon` (จาก `pipeline/ollama/Modelfile.thaifnv-typhoon`)
- ชุดทอง eval: `corpus/gold/fnv_gold_eval.jsonl` (~52 คู่)
- เมล็ด SFT: `corpus/gold/fnv_sft_train.jsonl` (สร้างจากชุดทองแล้ว)
- เป้าขยาย SFT ก่อนเทรนจริง: **200–500** คู่คุณภาพสูง (เน้น doctor / military / raider / robot)

## เตรียมข้อมูลเพิ่ม

1. คัดบรรทัดจาก `extracted/by_category/FNV_Dialogue.csv` ตาม `Speaker`
2. แปล/แก้ด้วยมือให้ยึด `pipeline/fnv_glossary.py` (ทับศัพท์ + register)
3. แปลงเป็น chat JSONL รูปแบบเดียวกับ `fnv_sft_train.jsonl`:
   - `system` = `SYSTEM_PROMPT`
   - `user` = batch prompt จาก `_build_user_prompt`
   - `assistant` = `{"results":[{"id":1,"th":"..."}]}`
4. **ห้าม**เทรนจาก `corpus/sheets_backup` ทั้งก้อนที่ยังมั่ว

## เทรน (Unsloth ตัวอย่าง)

```bash
# ตัวอย่างแนวทาง — ปรับตาม GPU จริง
# base: scb10x/typhoon2.1-gemma3-12b (HF) หรือ GGUF ที่เทียบเท่า
# data: corpus/gold/fnv_sft_train.jsonl (+ ไฟล์ที่ขยายแล้ว)
# LoRA rank 8–16, lr ~1e-4, 1–2 epoch
```

หลังเทรน:

1. Export GGUF (Q4_K_M / Q5_K_M)
2. สร้างโมเดล Ollama ใหม่ เช่น `thaifnv-typhoon-lora`
3. รัน:

```bash
python pipeline/eval_local_mt.py --model thaifnv-typhoon-lora
```

4. ผ่านเกณฑ์เดิมก่อนเปิดแปลเต็ม

## เกณฑ์ผ่าน (ล็อก)

- glossary miss &lt; 10%
- QA fail &lt; 15%
- corruption = 0
- doctor / professional register fail = 0
