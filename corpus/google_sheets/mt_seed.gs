/**
 * ThaiFNV — MT Seed Script for Google Sheets
 * ============================================
 * วิธีติดตั้ง (ทำครั้งเดียวต่อ Sheet):
 *  1. สร้าง Google Sheet ใหม่ → เปิด Extensions > Apps Script
 *  2. วางโค้ดทั้งหมดนี้ → Save (ตั้งชื่อ "ThaiFNV MT")
 *  3. กลับมาที่ Sheet — จะมีเมนู "🇹🇭 ThaiFNV" ปรากฏขึ้น (อาจต้องรีเฟรชหน้า)
 *  4. Import CSV: File > Import > Upload > เลือกไฟล์ CSV จาก extracted\sheets\
 *     - Import location: "Insert new sheet(s)" ต่อไฟล์
 *     - Separator: Comma
 *  5. เลือกคอลัมน์ EN ที่จะแปล → เมนู ThaiFNV > MT Seed
 *
 * การให้คะแนนสถานะ (คอลัมน์ สถานะ):
 *  - mt  = แปลโดย Google MT ยังไม่ตรวจ
 *  - ok  = คนตรวจแก้แล้วจบ ไม่ต้องแตะอีก
 *  - fix = ต้องกลับมาแก้ (คน mark ไว้)
 *  - ว่าง = ยังไม่แปล
 *
 * หมายเหตุ:
 *  - LanguageApp.translate() ฟรี แต่มี quota จึงต้องประมวลอย่างระวัง
 *  - ปุ่ม MT Seed จะข้ามแถวที่ TH มีค่าอยู่แล้ว + ข้ามสถานะ ok/fix เสมอ (ปลอดภัยต่องานแก้มือ)
 *  - เขียนเป็น批次 4 แถว/ครั้ง เพื่อกัน rate limit; เจอ limit จะหยุดแล้วบอกให้รันต่อใหม่ภายหลัง
 */

var MT_TARGET_LANG = 'th';

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('🇹🇭 ThaiFNV')
    .addItem('MT Seed (แถวที่เลือกไว้ในคอลัมน์ EN)', 'mtSeedSelection')
    .addItem('MT Seed (คอลัมน์ EN ทั้ง sheet, เติมเฉพาะที่ TH ว่าง)', 'mtSeedSheet')
    .addSeparator()
    .addItem('นับสถานะทั้ง sheet', 'reportStatus')
    .addToUi();
}

/** คืน "EN" ตอนแปล เอา newline รักษาด้วย */
function translateBatch(texts) {
  var out = [];
  for (var i = 0; i < texts.length; i++) {
    var s = texts[i];
    if (!s || !s.trim()) { out.push(s); continue; }
    try {
      out.push(LanguageApp.translate(s, 'en', MT_TARGET_LANG));
    } catch (e) {
      out.push('');
      throw e; // หยุดทั้ง batch เมื่อเจอ rate limit — ให้ user รันต่อทีหลัง
    }
  }
  return out;
}

function mtRange(range, onlyEmpty) {
  var sheet = range.getSheet();
  var startRow = range.getRow();
  var numRows = range.getNumRows();
  var colEs = findColumn_(sheet, 'EN');
  var colTh = findColumn_(sheet, 'TH');
  var colSt = findColumn_(sheet, 'สถานะ');
  if (colEs < 0 || colTh < 0 || colSt < 0) {
    throw 'ไม่เจอคอลัมน์ EN / TH / สถานะ ใน sheet นี้ (ต้องมาจาก CSV ของ pipeline)';
  }
  var es = sheet.getRange(startRow, colEs, numRows, 1).getValues();
  var th = sheet.getRange(startRow, colTh, numRows, 1).getValues();
  var st = sheet.getRange(startRow, colSt, numRows, 1).getValues();

  var indexQueue = [];
  for (var i = 0; i < numRows; i++) {
    var hasTh = th[i][0] && String(th[i][0]).trim() !== '';
    var locked = st[i][0] === 'ok' || st[i][0] === 'fix';
    if (!locked && (!hasTh || !onlyEmpty)) {
      if (es[i][0] && String(es[i][0]).trim() !== '') indexQueue.push(i);
    }
  }

  var done = 0;
  var BATCH = 4;
  for (var j = 0; j < indexQueue.length; j += BATCH) {
    var slice = indexQueue.slice(j, j + BATCH);
    var texts = slice.map(function (i) { return es[i][0]; });
    var translated = translateBatch(texts);
    for (var k = 0; k < slice.length; k++) {
      var r = slice[k];
      if (translated[k]) {
        th[r][0] = translated[k];
        st[r][0] = 'mt';
        done++;
      }
    }
    sheet.getRange(startRow, colTh, numRows, 1).setValues(th);
    sheet.getRange(startRow, colSt, numRows, 1).setValues(st);
    if (j % 400 === 0) SpreadsheetApp.flush(); // กัน timeout ยาว
  }
  sheet.getRange(startRow, colTh, numRows, 1).setValues(th);
  sheet.getRange(startRow, colSt, numRows, 1).setValues(st);
  SpreadsheetApp.getUi().alert('MT เสร็จ ' + done + ' แถว (จากที่มีคิว ' + indexQueue.length + ')');
}

function findColumn_(sheet, heading) {
  var headers = sheet.getRange(1, 1, 1, Math.max(sheet.getLastColumn(), 1)).getValues()[0];
  for (var i = 0; i < headers.length; i++) {
    if (String(headers[i]).trim() === heading) return i + 1;
  }
  return -1;
}

function mtSeedSelection() {
  mtRange(SpreadsheetApp.getActiveRange(), false);
}

function mtSeedSheet() {
  var sheet = SpreadsheetApp.getActiveSheet();
  var last = sheet.getLastRow();
  if (last < 2) { SpreadsheetApp.getUi().alert('ไม่มีข้อมูล'); return; }
  mtRange(sheet.getRange(2, 1, last - 1, 1), true);
}

function reportStatus() {
  var sheet = SpreadsheetApp.getActiveSheet();
  var last = sheet.getLastRow();
  if (last < 2) return;
  var colSt = findColumn_(sheet, 'สถานะ');
  var vals = sheet.getRange(2, colSt, last - 1, 1).getValues();
  var counts = {};
  for (var i = 0; i < vals.length; i++) {
    var v = String(vals[i][0]).trim() || '(ว่าง)';
    counts[v] = (counts[v] || 0) + 1;
  }
  var msg = '';
  for (var k in counts) msg += k + ': ' + counts[k] + '\n';
  SpreadsheetApp.getUi().alert('สถานะของ "' + sheet.getName() + '":\n\n' + msg);
}
