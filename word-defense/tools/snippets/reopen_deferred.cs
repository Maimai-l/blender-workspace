// saves everything, records a marker, then reopens the project (the editor closes and restarts)
UnityEditor.SceneManagement.EditorSceneManager.SaveOpenScenes();
AssetDatabase.SaveAssets();
string dir = System.IO.Path.Combine(System.Environment.GetFolderPath(System.Environment.SpecialFolder.MyDocuments), "WordDefense");
System.IO.Directory.CreateDirectory(dir);
var scene = UnityEditor.SceneManagement.EditorSceneManager.GetActiveScene();
string info = "saved " + System.DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " | editor up " + EditorApplication.timeSinceStartup.ToString("0") + " s | scene " + scene.path + " dirty=" + scene.isDirty;
System.IO.File.WriteAllText(System.IO.Path.Combine(dir, "reopen_marker.txt"), info);
string proj = System.IO.Path.GetFullPath(".");
EditorApplication.CallbackFunction cb = null;
cb = () => { EditorApplication.update -= cb; EditorApplication.OpenProject(proj); };
EditorApplication.update += cb;
return "reopen scheduled for " + proj + " | " + info;
