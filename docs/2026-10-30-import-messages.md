# Import FNV_Messages จาก Google Sheets — 2026-10-30

## แหล่ง
https://docs.google.com/spreadsheets/d/1kJf1JjuN_CDdh7660LuVYHax0Z9cuB5NETtt1_LrEOE

แท็บเดียว: `FNV_Messages` (~1958 แถว, สถานะ `mt`)

## Pipeline
```text
curl export CSV → extracted/sheets/from_google/FNV_Messages.csv
python pipeline/import_csv_to_esp.py ... --out release/ThaiFNV_Messages.esp
```
- ดึง MESG จาก `FalloutNV.esm` ตาม FormID
- แทน FULL/DESC/ITXT เป็นไทย
- encode CP874 + sparse wordbreak + precompose

## ผล
- `release/ThaiFNV_Messages.esp` — 1121 records, 1957 string patches
- Deploy: `Data\ThaiFNV_Messages.esp` (โหลดหลัง `ThaiFNV_Test.esp`)

## เทสคอนโซล
```
ShowMessage 1717D3
ShowMessage 186
ShowMessage 17BA3C
ShowMessage 190
```
