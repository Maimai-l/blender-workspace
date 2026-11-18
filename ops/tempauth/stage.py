"""把临时授权的安装包需要的文件整理到一个暂存目录，并把 SHA256 填进 install.ps1。
    python3 ops/tempauth/stage.py <暂存目录>
然后把暂存目录整个传到电脑的 D:\\Projects\\mcp-console-stage\\tempauth\\。"""
import hashlib
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OPS = HERE.parent
FILES = {
    "helper/AitempHelper.cs": HERE / "helper/AitempHelper.cs",
    "helper/wfp.cs": HERE / "helper/wfp.cs",
    "gateway/gateway.py": HERE / "gateway/gateway.py",
    "denywrite.ps1": HERE / "test/denywrite.ps1",
    "console/console.py": OPS / "console/console.py",
    "console/agent.py": OPS / "console/agent.py",
    "console/static/index.html": OPS / "console/static/index.html",
    "console/static/app.js": OPS / "console/static/app.js",
    "console/static/app.css": OPS / "console/static/app.css",
    "console/static/grants.js": OPS / "console/static/grants.js",
}

out = Path(sys.argv[1])
if out.exists():
    shutil.rmtree(out)
ps = (HERE / "install.ps1").read_text(encoding="utf-8")
for rel, src in FILES.items():
    dst = out / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    ps = ps.replace("@@" + rel, hashlib.sha256(src.read_bytes()).hexdigest().upper())
assert "@@" not in ps, "manifest entry without a file"
# Windows PowerShell 读没有 BOM 的 UTF-8 会按系统代码页解码：加 BOM
(out / "install.ps1").write_bytes(b"\xef\xbb\xbf" + ps.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
print("staged", len(FILES) + 1, "files in", out)
