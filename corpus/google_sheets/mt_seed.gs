/**
 * ThaiFNV — MT Seed Script for Google Sheets
 * ============================================
 * วิธีติดตั้ง (ทำครั้งเดียวต่อ Sheet):
 *  1. Extensions > Apps Script → วางไฟล์นี้เป็น Code.gs แล้ว Save
 *  2. Project Settings (⚙️) → เปิด "Show appsscript.json manifest file in editor"
 *  3. วางเนื้อหาจาก appsscript.json ใน repo (ต้องมี script.external_request)
 *  4. เลือกฟังก์ชัน authorizeExternalFetch → Run → กด Review permissions
 *     → บัญชี Google ของคุณ → Advanced → Go to ThaiFNV MT (unsafe) → Allow
 *  5. กลับมาที่ Sheet รีเฟรช → เมนู 🇹🇭 ThaiFNV
 *     → Import หมวดที่เหลือจาก GitHub
 *
 * ถ้าไม่อยากใช้ UrlFetch: File > Import > Upload CSV จาก extracted\sheets\
 *   (Insert new sheet / Comma) แล้วตั้งชื่อแท็บให้ตรงชื่อไฟล์
 *
 * สถานะ: mt | ok | fix | ว่าง
 */

var MT_TARGET_LANG = 'th';

/** raw CSV บน GitHub (repo สาธารณะ) — อัปเดต branch ถ้าเปลี่ยน */
var GITHUB_RAW_BASE =
  'https://raw.githubusercontent.com/FordenHillson/ThaiFNV/main/extracted/sheets/';

/** CSV ที่แปลแล้ว (gist) — อัปเดตเมื่อมีไฟล์ใหม่จาก mt_seed_local */
var TRANSLATED_URLS = {
  FNV_BookDesc:
    'https://gist.githubusercontent.com/FordenHillson/5427d98171691a67af3aebea70f9e05c/raw/FNV_BookDesc.csv',
  FNV_SystemStr:
    'https://gist.githubusercontent.com/FordenHillson/4d33f15ea488cabbe43a6f1f21e159d2/raw/FNV_SystemStr.csv',
  FNV_Other:
    'https://gist.githubusercontent.com/FordenHillson/bc52f8d85266490aad521fed6b4b32cc/raw/FNV_Other.csv',
  FNV_Notes:
    'https://gist.githubusercontent.com/FordenHillson/b852b6d5f1d5a31e4f4c55493a53355d/raw/FNV_Notes.csv',
};

/** หมวดที่ยังไม่มีในชีต (ข้าม Messages ที่แปลแล้ว) */
var IMPORT_TABS = [
  'FNV_SystemStr',
  'FNV_Other',
  'FNV_BookDesc',
  'FNV_Notes',
  'FNV_Quests',
  'FNV_Terminals',
  'FNV_Names',
  'FNV_TopicNames',
  'FNV_Dialogue',
];

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('🇹🇭 ThaiFNV')
    .addItem('0) Authorize UrlFetch (รันครั้งแรก)', 'authorizeExternalFetch')
    .addItem('Import คำแปลที่พร้อมแล้ว (gist)', 'importTranslatedNow')
    .addItem('Import หมวดที่เหลือจาก GitHub', 'importRemainingFromGithub')
    .addItem('Import แท็บที่เลือกชื่อ…', 'importOneFromGithubPrompt')
    .addSeparator()
    .addItem('MT Seed (แถวที่เลือกไว้ในคอลัมน์ EN)', 'mtSeedSelection')
    .addItem('MT Seed (คอลัมน์ EN ทั้ง sheet, เติมเฉพาะที่ TH ว่าง)', 'mtSeedSheet')
    .addSeparator()
    .addItem('นับสถานะทั้ง sheet', 'reportStatus')
    .addToUi();
}

/** รันครั้งแรกเพื่อขึ้นหน้าต่างอนุญาต script.external_request */
function authorizeExternalFetch() {
  UrlFetchApp.fetch('https://www.google.com', { muteHttpExceptions: true });
  SpreadsheetApp.getUi().alert(
    'Authorize สำเร็จ — กลับไปรัน Import หมวดที่เหลือจาก GitHub ได้'
  );
}

/** แปลทีละข้อความ + retry เมื่อโดน rate limit */
function translateOne_(s) {
  if (!s || !String(s).trim()) return s;
  var tries = 0;
  while (tries < 6) {
    try {
      return LanguageApp.translate(s, 'en', MT_TARGET_LANG);
    } catch (e) {
      var msg = String(e);
      if (msg.indexOf('เกินไป') >= 0 || msg.indexOf('too many') >= 0 ||
          msg.indexOf('Service invoked too many') >= 0) {
        tries++;
        Utilities.sleep(1500 * tries); // 1.5s, 3s, 4.5s...
        continue;
      }
      throw e;
    }
  }
  throw 'rate limit ยังไม่หายหลัง retry — รัน MT ต่อทีหลัง';
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
  // ช้าแต่ไม่โดนโควต้าง่าย: 1 แถว + sleep
  for (var j = 0; j < indexQueue.length; j++) {
    var r = indexQueue[j];
    th[r][0] = translateOne_(es[r][0]);
    st[r][0] = 'mt';
    done++;
    Utilities.sleep(1200);
    if (done % 20 === 0) {
      sheet.getRange(startRow, colTh, numRows, 1).setValues(th);
      sheet.getRange(startRow, colSt, numRows, 1).setValues(st);
      SpreadsheetApp.flush();
    }
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

/**
 * ดึง CSV จาก GitHub แล้วสร้าง/แทนที่แท็บ — รันครั้งเดียวหลังวางสคริปต์นี้
 * หมายเหตุ: ไฟล์ใหญ่ (Dialogue ~30k) อาจใกล้ลิมิต 6 นาที; ถ้าระหว่างทางหลุด ให้รันซ้ำ
 * (แท็บที่มีอยู่แล้วจะถูกข้าม เว้นแต่ forceReplace=true)
 */
function importRemainingFromGithub() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var report = [];
  for (var i = 0; i < IMPORT_TABS.length; i++) {
    var name = IMPORT_TABS[i];
    try {
      var n = importCsvTab_(ss, name, false);
      report.push(name + ': OK ' + n + ' แถว');
    } catch (e) {
      report.push(name + ': FAIL ' + e);
      SpreadsheetApp.getUi().alert(
        'หยุดที่ ' + name + '\n\n' + e + '\n\nความคืบหน้า:\n' + report.join('\n')
      );
      return;
    }
    SpreadsheetApp.flush();
  }
  SpreadsheetApp.getUi().alert('Import เสร็จ:\n\n' + report.join('\n'));
}

function importOneFromGithubPrompt() {
  var ui = SpreadsheetApp.getUi();
  var r = ui.prompt(
    'Import จาก GitHub',
    'ชื่อแท็บ/ไฟล์ (เช่น FNV_Names):',
    ui.ButtonSet.OK_CANCEL
  );
  if (r.getSelectedButton() !== ui.Button.OK) return;
  var name = String(r.getResponseText() || '').trim();
  if (!name) return;
  if (name.indexOf('FNV_') !== 0) name = 'FNV_' + name;
  try {
    var n = importCsvTab_(SpreadsheetApp.getActiveSpreadsheet(), name, true);
    ui.alert(name + ': นำเข้า ' + n + ' แถว');
  } catch (e) {
    ui.alert('ล้มเหลว: ' + e);
  }
}

function importTranslatedNow() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var report = [];
  var names = Object.keys(TRANSLATED_URLS);
  for (var i = 0; i < names.length; i++) {
    var name = names[i];
    try {
      var n = importCsvFromUrl_(ss, name, TRANSLATED_URLS[name], true);
      report.push(name + ': OK ' + n + ' แถว');
    } catch (e) {
      report.push(name + ': FAIL ' + e);
    }
    SpreadsheetApp.flush();
  }
  SpreadsheetApp.getUi().alert('Import คำแปล:\n\n' + report.join('\n'));
}

function importCsvTab_(ss, tabName, forceReplace) {
  return importCsvFromUrl_(ss, tabName, GITHUB_RAW_BASE + tabName + '.csv', forceReplace);
}

function importCsvFromUrl_(ss, tabName, url, forceReplace) {
  var existing = ss.getSheetByName(tabName);
  if (existing && !forceReplace) {
    return existing.getLastRow() > 0 ? existing.getLastRow() - 1 : 0;
  }
  var resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  var code = resp.getResponseCode();
  if (code !== 200) {
    throw 'HTTP ' + code + ' สำหรับ ' + url;
  }
  var text = resp.getContentText('UTF-8');
  if (text.charCodeAt(0) === 0xfeff) text = text.substring(1);
  var rows = Utilities.parseCsv(text);
  if (!rows || !rows.length) throw 'CSV ว่าง: ' + tabName;

  var sheet = existing;
  if (sheet) {
    sheet.clearContents();
  } else {
    sheet = ss.insertSheet(tabName);
  }
  var CHUNK = 2000;
  var width = rows[0].length;
  for (var start = 0; start < rows.length; start += CHUNK) {
    var end = Math.min(start + CHUNK, rows.length);
    var slice = rows.slice(start, end);
    for (var r = 0; r < slice.length; r++) {
      while (slice[r].length < width) slice[r].push('');
      if (slice[r].length > width) slice[r] = slice[r].slice(0, width);
    }
    sheet.getRange(start + 1, 1, end - start, width).setValues(slice);
    SpreadsheetApp.flush();
  }
  return rows.length - 1;
}
