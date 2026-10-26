var gm = WordDefense.GameManager.Instance;
if (gm == null) return "no gm";
gm.StartGame();
return "started: " + gm.State;
