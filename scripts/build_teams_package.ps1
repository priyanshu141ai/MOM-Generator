param(
    [Parameter(Mandatory = $true)]
    [string]$PublicUrl,

    [string]$AppId = [guid]::NewGuid().ToString()
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$TemplatePath = Join-Path $ProjectRoot "teams\manifest.template.json"
$BuildRoot = Join-Path $ProjectRoot "teams\build"
$PackageFolder = Join-Path $BuildRoot "package"
$ZipPath = Join-Path $BuildRoot "meetwise-teams.zip"

$uri = [uri]$PublicUrl
if ($uri.Scheme -ne "https" -or [string]::IsNullOrWhiteSpace($uri.Host)) {
    throw "PublicUrl must be a public HTTPS address."
}

if (Test-Path -LiteralPath $PackageFolder) {
    Remove-Item -LiteralPath $PackageFolder -Recurse -Force
}
New-Item -ItemType Directory -Path $PackageFolder -Force | Out-Null

$cleanUrl = $PublicUrl.TrimEnd("/")
$manifest = Get-Content -LiteralPath $TemplatePath -Raw
$manifest = $manifest.Replace("{{APP_ID}}", $AppId)
$manifest = $manifest.Replace("{{PUBLIC_APP_URL}}", $cleanUrl)
$manifest = $manifest.Replace("{{PUBLIC_DOMAIN}}", $uri.Host)
$manifest | ConvertFrom-Json | Out-Null
$manifest | Set-Content -LiteralPath (Join-Path $PackageFolder "manifest.json") -Encoding UTF8

Add-Type -AssemblyName System.Drawing

function New-ColorIcon {
    param([string]$Path)
    $bitmap = New-Object System.Drawing.Bitmap 192, 192
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.Clear([System.Drawing.Color]::FromArgb(91, 95, 199))
    $font = New-Object System.Drawing.Font("Segoe UI", 92, [System.Drawing.FontStyle]::Bold)
    $brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
    $format = New-Object System.Drawing.StringFormat
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $format.LineAlignment = [System.Drawing.StringAlignment]::Center
    $graphics.DrawString("M", $font, $brush, (New-Object System.Drawing.RectangleF 0, 0, 192, 184), $format)
    $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $format.Dispose(); $brush.Dispose(); $font.Dispose(); $graphics.Dispose(); $bitmap.Dispose()
}

function New-OutlineIcon {
    param([string]$Path)
    $bitmap = New-Object System.Drawing.Bitmap 32, 32
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.Clear([System.Drawing.Color]::Transparent)
    $font = New-Object System.Drawing.Font("Segoe UI", 17, [System.Drawing.FontStyle]::Bold)
    $brush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
    $format = New-Object System.Drawing.StringFormat
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $format.LineAlignment = [System.Drawing.StringAlignment]::Center
    $graphics.DrawString("M", $font, $brush, (New-Object System.Drawing.RectangleF 0, 0, 32, 30), $format)
    $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $format.Dispose(); $brush.Dispose(); $font.Dispose(); $graphics.Dispose(); $bitmap.Dispose()
}

New-ColorIcon (Join-Path $PackageFolder "color.png")
New-OutlineIcon (Join-Path $PackageFolder "outline.png")

if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path (Join-Path $PackageFolder "*") -DestinationPath $ZipPath

Write-Host "Teams package created: $ZipPath"
Write-Host "App ID: $AppId"
