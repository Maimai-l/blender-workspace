$c = New-Object System.Net.Sockets.TcpClient
$c.ReceiveTimeout = 8000
$c.Connect("127.0.0.1", 9876)
$s = $c.GetStream()
$msg = [System.Text.Encoding]::UTF8.GetBytes('{"type": "get_scene_info", "params": {}}')
$s.Write($msg, 0, $msg.Length)
$buf = New-Object byte[] 65536
try { $n = $s.Read($buf, 0, $buf.Length); [System.Text.Encoding]::UTF8.GetString($buf, 0, $n).Substring(0, [Math]::Min($n, 400)) } catch { "read failed: $_" }
$c.Close()
