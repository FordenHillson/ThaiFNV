# Helper: list remaining arg indices for agent MCP write_range loop.
# Agent: for each index, run: node pipeline/push_jsonl_index.cjs $i
# Then CallDynamicTool write_range with JSON line 2 from output.
$dir = "C:\Users\saetanpee\AppData\Local\Cursor\AgentStores\cursor_agent_stores\f277bb1f-18c1-446d-97ec-8f94cb76d6fd\files\push_items"
$done = @("F0002","F0042","F0082","F0122","F0162","F0202")
for ($i = 0; $i -le 21; $i++) {
  $p = Join-Path $dir "arg_$i.json"
  if (-not (Test-Path $p)) { continue }
  $cells = (Get-Content $p -Raw | ConvertFrom-Json).cells
  $batch = "F$($cells.Substring(1))"
  if ($done -contains $batch) { continue }
  Write-Output $i
}
