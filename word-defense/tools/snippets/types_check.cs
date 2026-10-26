var t1 = System.Type.GetType("WordDefense.GameManager, Assembly-CSharp");
var t2 = System.Type.GetType("WordDefense.EditorTools.WDSetup, Assembly-CSharp-Editor");
var t3 = System.Type.GetType("WordDefense.UIRoot, Assembly-CSharp");
return "GameManager=" + (t1 != null) + " WDSetup=" + (t2 != null) + " UIRoot=" + (t3 != null) + " compiling=" + EditorApplication.isCompiling;
