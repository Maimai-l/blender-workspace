var p = System.IO.Path.GetFullPath("Temp/SmokeTest/capture_test.png");
System.IO.Directory.CreateDirectory(System.IO.Path.GetDirectoryName(p));
WordDefense.AutoPilot.CaptureOffscreen(p);
return "captured " + p + " " + new System.IO.FileInfo(p).Length;
