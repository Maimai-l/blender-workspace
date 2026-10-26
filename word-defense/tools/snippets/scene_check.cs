WordDefense.EditorTools.WDSetup.BuildScene();
var scene = UnityEditor.SceneManagement.EditorSceneManager.OpenScene(WordDefense.EditorTools.WDSetup.ScenePath, UnityEditor.SceneManagement.OpenSceneMode.Single);
var sb = new System.Text.StringBuilder();
int missing = 0, comps = 0;
foreach (var root in scene.GetRootGameObjects())
  foreach (var t in root.GetComponentsInChildren<Transform>(true)) {
    missing += GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(t.gameObject);
    foreach (var mb in t.GetComponents<MonoBehaviour>()) if (mb != null && mb.GetType().Namespace == "WordDefense") { comps++; sb.Append(t.name + ":" + mb.GetType().Name + " "); }
  }
var gm = UnityEngine.Object.FindAnyObjectByType<WordDefense.GameManager>();
return "missing=" + missing + " wd components=" + comps + " | castle=" + (gm && gm.castle) + " cannon=" + (gm && gm.cannon) + " | " + sb;
