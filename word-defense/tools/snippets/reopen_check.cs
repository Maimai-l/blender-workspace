// after the restart: is this a fresh editor, is the game scene open and intact, did settings survive?
var sb = new System.Text.StringBuilder();
string marker = System.IO.Path.Combine(System.Environment.GetFolderPath(System.Environment.SpecialFolder.MyDocuments), "WordDefense", "reopen_marker.txt");
sb.AppendLine("before: " + (System.IO.File.Exists(marker) ? System.IO.File.ReadAllText(marker) : "(no marker)"));
sb.AppendLine("now:    " + System.DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " | editor up " + EditorApplication.timeSinceStartup.ToString("0") + " s | compiling=" + EditorApplication.isCompiling + " playing=" + EditorApplication.isPlaying);
var scene = UnityEditor.SceneManagement.EditorSceneManager.GetActiveScene();
sb.AppendLine("active scene: " + scene.path + " loaded=" + scene.isLoaded + " dirty=" + scene.isDirty + " roots=" + scene.rootCount);
int missing = 0, comps = 0;
var names = new System.Collections.Generic.List<string>();
foreach (var root in scene.GetRootGameObjects())
  foreach (var t in root.GetComponentsInChildren<Transform>(true)) {
    missing += GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject);
    foreach (var mb in t.GetComponents<MonoBehaviour>()) if (mb != null && mb.GetType().Namespace == "WordDefense") { comps++; names.Add(t.name + ":" + mb.GetType().Name); }
  }
var gm = UnityEngine.Object.FindAnyObjectByType<WordDefense.GameManager>();
sb.AppendLine("missing scripts=" + missing + " | WordDefense components=" + comps + " | GameManager refs: castle=" + (gm && gm.castle) + " cannon=" + (gm && gm.cannon) + " cam=" + (gm && gm.cam) + " fonts=" + (gm && gm.fontLatin && gm.fontLatinItalic && gm.fontLatinBoldItalic && gm.fontSong && gm.fontSongBold && gm.fontSongBlack) + " halos=" + (gm && gm.fontHalos != null ? gm.fontHalos.Length : 0));
sb.AppendLine("components: " + string.Join(", ", names.ToArray()));
sb.AppendLine("player: product=" + PlayerSettings.productName + " company=" + PlayerSettings.companyName + " " + PlayerSettings.defaultScreenWidth + "x" + PlayerSettings.defaultScreenHeight + " mode=" + PlayerSettings.fullScreenMode + " runInBackground=" + PlayerSettings.runInBackground + " splash=" + PlayerSettings.SplashScreen.show + " colorSpace=" + PlayerSettings.colorSpace);
sb.AppendLine("build scenes: " + string.Join(", ", System.Array.ConvertAll(EditorBuildSettings.scenes, s => s.path + (s.enabled ? "" : " (off)"))));
var models = AssetDatabase.FindAssets("t:Model", new[] { "Assets/WordDefense/Models" });
sb.AppendLine("models: " + string.Join(", ", System.Array.ConvertAll(models, g => System.IO.Path.GetFileNameWithoutExtension(AssetDatabase.GUIDToAssetPath(g)))));
sb.AppendLine("vocabulary copy in StreamingAssets: " + System.IO.File.Exists("Assets/StreamingAssets/vocabulary.db"));
return sb.ToString();
