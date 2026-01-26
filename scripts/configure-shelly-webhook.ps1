$ShellyIP = "192.168.1.201"
$MyIP = "192.168.1.100"
$Port = "1488"
$WebhookUrl = "http://${MyIP}:${Port}/api/sensors/shellyhtg3-b08184ee93a8/readings"

Write-Host "Waiting for Shelly to wake up..." -ForegroundColor Cyan

$maxAttempts = 120  # 10 minutes at 5 second intervals
$attempts = 0

while ($attempts -lt $maxAttempts) {
    try {
        $response = Invoke-RestMethod -Uri "http://$ShellyIP/shelly" -TimeoutSec 2 -ErrorAction Stop
        Write-Host "`nShelly is ONLINE!" -ForegroundColor Green
        Write-Host "Device: $($response.id)"
        break
    }
    catch {
        $attempts++
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 5
    }
}

if ($attempts -ge $maxAttempts) {
    Write-Host "`nTimeout waiting for Shelly" -ForegroundColor Red
    exit 1
}

# Create temperature webhook
Write-Host "`nCreating temperature webhook..." -ForegroundColor Yellow
$tempWebhookBody = @{
    id = 1
    method = "Webhook.Create"
    params = @{
        cid = 0
        enable = $true
        event = "temperature.change"
        urls = @("${WebhookUrl}?tC=`${ev.tC}&rh=`${status[`"humidity:0`"].rh}")
    }
} | ConvertTo-Json -Depth 3

try {
    $result = Invoke-RestMethod -Uri "http://$ShellyIP/rpc" -Method Post -Body $tempWebhookBody -ContentType "application/json" -TimeoutSec 5
    Write-Host "Temperature webhook created: $($result | ConvertTo-Json)" -ForegroundColor Green
}
catch {
    Write-Host "Failed to create temperature webhook: $_" -ForegroundColor Red
}

Write-Host "`nDone! Webhook configured to send data to: $WebhookUrl" -ForegroundColor Cyan
Write-Host "Test command from another PC: curl http://${MyIP}:${Port}/api/sensors/test/readings?tC=21.5" -ForegroundColor Gray
