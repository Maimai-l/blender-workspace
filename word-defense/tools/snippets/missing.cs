var sb = new System.Text.StringBuilder();
foreach (var go in Resources.FindObjectsOfTypeAll<GameObject>()) {
  if (go.hideFlags != HideFlags.None) continue;
  int n = GameObjectUtility.GetMonoBehavioursWithMissingScriptCount(go);
  if (n > 0) sb.AppendLine(go.name + " scene=" + go.scene.name + " missing=" + n + " path=" + AssetDatabase.GetAssetPath(go));
}
return sb.Length == 0 ? "none" : sb.ToString();
