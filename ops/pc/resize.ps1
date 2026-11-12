param([string]$Src, [string]$Out, [int]$Max = 1600)
Add-Type -AssemblyName System.Drawing
$img = [System.Drawing.Image]::FromFile($Src)
if ($img.PropertyIdList -contains 274) {
  $o = $img.GetPropertyItem(274).Value[0]
  if ($o -eq 3) { $img.RotateFlip([System.Drawing.RotateFlipType]::Rotate180FlipNone) }
  elseif ($o -eq 6) { $img.RotateFlip([System.Drawing.RotateFlipType]::Rotate90FlipNone) }
  elseif ($o -eq 8) { $img.RotateFlip([System.Drawing.RotateFlipType]::Rotate270FlipNone) }
}
$s = [math]::Min(1.0, $Max / [math]::Max($img.Width, $img.Height))
$w = [int]($img.Width * $s); $h = [int]($img.Height * $s)
$bmp = New-Object System.Drawing.Bitmap $w, $h
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$g.DrawImage($img, 0, 0, $w, $h)
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Jpeg)
$g.Dispose(); $bmp.Dispose(); $img.Dispose()
Write-Output ('{0}x{1} -> {2}' -f $w, $h, $Out)
