# EmotionSense - Simple HTTP Server (PowerShell)
# Serves the index/ folder on http://localhost:8000
# VS Code auto-runs this before Chrome launches via tasks.json

param([int]$Port = 8000)

$rootPath = Join-Path $PSScriptRoot "index"

$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$Port/")

try {
    $listener.Start()
} catch {
    Write-Host "ERROR: Could not start server on port $Port. Is another instance already running?" -ForegroundColor Red
    Write-Host "Try closing any other terminal windows running this script, then retry." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# These exact strings are matched by .vscode/tasks.json problemMatcher
Write-Host ""
Write-Host "EmotionSense HTTP Server is starting..." -ForegroundColor Cyan
Start-Sleep -Milliseconds 300
Write-Host "Server is live at http://localhost:$Port" -ForegroundColor Green
Write-Host ""
Write-Host "  App URL   : http://localhost:$Port/index.html" -ForegroundColor White
Write-Host "  Root Dir  : $rootPath" -ForegroundColor White
Write-Host ""
Write-Host "  Press CTRL+C to stop." -ForegroundColor DarkGray
Write-Host ""

$mimeTypes = @{
    ".html"  = "text/html; charset=utf-8"
    ".css"   = "text/css"
    ".js"    = "application/javascript"
    ".json"  = "application/json"
    ".png"   = "image/png"
    ".jpg"   = "image/jpeg"
    ".jpeg"  = "image/jpeg"
    ".svg"   = "image/svg+xml"
    ".ico"   = "image/x-icon"
    ".woff2" = "font/woff2"
    ".woff"  = "font/woff"
    ".ttf"   = "font/ttf"
}

while ($listener.IsListening) {
    try {
        $context  = $listener.GetContext()
        $request  = $context.Request
        $response = $context.Response

        # Add CORS headers so API calls work from localhost
        $response.Headers.Add("Access-Control-Allow-Origin", "*")
        $response.Headers.Add("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

        $urlPath = $request.Url.LocalPath
        if ($urlPath -eq "/" -or $urlPath -eq "") { $urlPath = "/index.html" }

        $filePath = Join-Path $rootPath ($urlPath.TrimStart("/") -replace "/", "\")

        if (Test-Path $filePath -PathType Leaf) {
            $ext         = [System.IO.Path]::GetExtension($filePath).ToLower()
            $contentType = if ($mimeTypes.ContainsKey($ext)) { $mimeTypes[$ext] } else { "application/octet-stream" }

            $content = [System.IO.File]::ReadAllBytes($filePath)
            $response.StatusCode     = 200
            $response.ContentType    = $contentType
            $response.ContentLength64 = $content.Length
            $response.OutputStream.Write($content, 0, $content.Length)

            Write-Host "  [200] $urlPath" -ForegroundColor Green
        } else {
            $body    = [System.Text.Encoding]::UTF8.GetBytes("<h2>404 - Not Found: $urlPath</h2>")
            $response.StatusCode     = 404
            $response.ContentType    = "text/html"
            $response.ContentLength64 = $body.Length
            $response.OutputStream.Write($body, 0, $body.Length)

            Write-Host "  [404] $urlPath" -ForegroundColor Red
        }
    } catch [System.Net.HttpListenerException] {
        break   # Listener was stopped (CTRL+C)
    } catch {
        # Silently ignore other transient errors
    } finally {
        try { $response.OutputStream.Close() } catch {}
    }
}

$listener.Stop()
Write-Host "Server stopped." -ForegroundColor Yellow
