# take_screenshots.ps1 — Capture landing page & Swagger UI screenshots using Edge
# Usage: powershell -ExecutionPolicy Bypass -File scripts/take_screenshots.ps1

$BASE_URL = "https://india-prevalidate-api-production.up.railway.app"
$OUT_DIR = Join-Path $PSScriptRoot "..\static\img\screenshots"

# Ensure output directory exists
if (!(Test-Path $OUT_DIR)) { New-Item -ItemType Directory -Path $OUT_DIR -Force }

$EDGE = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if (!(Test-Path $EDGE)) {
    $EDGE = "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
}
if (!(Test-Path $EDGE)) {
    $EDGE = "C:\Program Files\Google\Chrome\Application\chrome.exe"
}

Write-Host "Using browser: $EDGE"
Write-Host "Saving screenshots to: $OUT_DIR"

# Screenshot 1: Landing page (1280x800)
Write-Host "`nCapturing landing page..."
& $EDGE --headless --disable-gpu --screenshot="$OUT_DIR\landing-page.png" --window-size=1280,900 "$BASE_URL/" 2>$null
Start-Sleep -Seconds 3

# Screenshot 2: Swagger UI (1280x800)
Write-Host "Capturing Swagger UI..."
& $EDGE --headless --disable-gpu --screenshot="$OUT_DIR\swagger-ui.png" --window-size=1280,900 "$BASE_URL/docs" 2>$null
Start-Sleep -Seconds 3

# Screenshot 3: Live demo section (scroll down)
Write-Host "Capturing live demo section..."
& $EDGE --headless --disable-gpu --screenshot="$OUT_DIR\live-demo.png" --window-size=1280,900 "$BASE_URL/#demo" 2>$null
Start-Sleep -Seconds 3

# Screenshot 4: Bulk validation section
Write-Host "Capturing bulk validation section..."
& $EDGE --headless --disable-gpu --screenshot="$OUT_DIR\bulk-validation.png" --window-size=1280,900 "$BASE_URL/#bulk" 2>$null
Start-Sleep -Seconds 3

Write-Host "`nDone! Screenshots saved to:"
Get-ChildItem $OUT_DIR -Filter "*.png" | ForEach-Object { Write-Host "  $_" }
Write-Host "`nThese are now served at:"
Write-Host "  $BASE_URL/static/img/screenshots/landing-page.png"
Write-Host "  $BASE_URL/static/img/screenshots/swagger-ui.png"
Write-Host "  $BASE_URL/static/img/screenshots/live-demo.png"
Write-Host "  $BASE_URL/static/img/screenshots/bulk-validation.png"
