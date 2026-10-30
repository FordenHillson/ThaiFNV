# UTF-8 row text patches for th_*.json
$base = 'D:\backup\github\ThaiFNV\extracted\sheets\from_google\_ai_notes'
$textDir = Join-Path $base '_text'
New-Item -ItemType Directory -Force -Path $textDir | Out-Null

$rows = @{
'725' = @'
ฉันชื่อ Carrie Delaney สอนชั้นป.4 ที่โรงเรียน Early Dawn Elementary ใน Washington, D.C. เมื่อวาน 23 ตุลาคม 2077 ครึ่งโรงเรียนไปทัศนศึกษaที่ Lamplight Caverns กำลังจะเก็บของกลับ แล้vทุกอย่างก็บ้aไป ถ้ำสั่n ไฟดับ เด็kกรีดร้อง พระเจ้า... คุณ Pollack ออกไปดู กลับมaบอกว่าเห็nเมฆ เมฆรูปเห็d ในที่สุdมaันเกิดขึ้nจริw สิwสุdของโloก
'@
}

foreach ($k in $rows.Keys) {
  $path = Join-Path $textDir "row_$k.txt"
  [System.IO.File]::WriteAllText($path, $rows[$k].Trim(), [System.Text.UTF8Encoding]::new($false))
}
