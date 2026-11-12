param([string]$Src, [string]$Out, [string]$Filter = '*.jpg', [int]$Cols = 4, [int]$TW = 640, [int]$TH = 480)
Add-Type -AssemblyName System.Drawing
$files = Get-ChildItem -LiteralPath $Src -Filter $Filter | Sort-Object Name
$lab = 26
$rows = [math]::Ceiling($files.Count / $Cols)
$sheet = New-Object System.Drawing.Bitmap ($Cols * $TW), ($rows * ($TH + $lab))
$g = [System.Drawing.Graphics]::FromImage($sheet)
$g.Clear([System.Drawing.Color]::White)
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$font = New-Object System.Drawing.Font 'Arial', 12
$k = 0
foreach ($f in $files) {
  $img = [System.Drawing.Image]::FromFile($f.FullName)
  $s = [math]::Min($TW / $img.Width, $TH / $img.Height)
  $w = [int]($img.Width * $s); $h = [int]($img.Height * $s)
  $cx = ($k % $Cols) * $TW; $cy = [math]::Floor($k / $Cols) * ($TH + $lab)
  $g.DrawImage($img, $cx + [int](($TW - $w) / 2), $cy + $lab, $w, $h)
  $g.DrawString(('{0}: {1}' -f $k, $f.Name), $font, [System.Drawing.Brushes]::Black, $cx + 4, $cy + 4)
  $img.Dispose(); $k++
}
$sheet.Save($Out, [System.Drawing.Imaging.ImageFormat]::Jpeg)
$g.Dispose(); $sheet.Dispose()
Write-Output ('sheet {0} images -> {1}' -f $files.Count, $Out)
