// schedules the Windows build on the next editor update and writes the summary to Temp/wd_build.txt
System.IO.File.WriteAllText(System.IO.Path.GetFullPath("Temp/wd_build.txt"), "");
EditorApplication.CallbackFunction cb = null;
cb = () => {
  EditorApplication.update -= cb;
  string msg;
  try { msg = WordDefense.EditorTools.WDBuild.BuildWindows(); }
  catch (System.Exception e) { msg = "[WD] build exception " + e; }
  System.IO.File.WriteAllText(System.IO.Path.GetFullPath("Temp/wd_build.txt"), msg);
};
EditorApplication.update += cb;
return "build scheduled";
