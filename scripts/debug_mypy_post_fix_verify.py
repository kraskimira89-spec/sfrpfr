import json, os, subprocess, sys, time
from pathlib import Path

LOG = Path(r"c:\Users\user\Documents\Cursor\SFRFR\debug-6f3231.log")
LIBS = Path(os.path.expandvars(r"%USERPROFILE%\.cursor\extensions\ms-python.mypy-type-checker-2026.6.0\bundled\libs"))
TOOL = LIBS.parent / "tool" / "lsp_server.py"
PY = r"c:\Users\user\Documents\Cursor\SFRFR\.venv\Scripts\python.exe"

def log(hid, msg, data):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "sessionId": "6f3231",
            "runId": "post-fix",
            "hypothesisId": hid,
            "location": "post_fix_verify",
            "message": msg,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }, ensure_ascii=False) + "\n")

has = (LIBS / "vscode_common_python_lsp").is_dir()
log("H1", "shared pkg present after install", {"has_shared_pkg": has, "libs": str(LIBS)})

probe = (
    "import sys, pathlib;"
    f"B=pathlib.Path(r'{TOOL}').parent.parent;"
    "sys.path.insert(0, str(B/'tool'));"
    "sys.path.insert(0, str(B/'libs'));"
    "import vscode_common_python_lsp;"
    "import lsp_utils;"
    "print('IMPORT_OK', vscode_common_python_lsp.__file__)"
)
p = subprocess.run([PY, "-c", probe], capture_output=True, text=True, timeout=15)
out = (p.stdout or "") + (p.stderr or "")
log("H2", "import lsp_utils after fix", {"returncode": p.returncode, "ok": "IMPORT_OK" in out, "out_tail": out[-800:]})

env = os.environ.copy()
env["LS_IMPORT_STRATEGY"] = "useBundled"
try:
    p2 = subprocess.run([PY, str(TOOL)], capture_output=True, text=True, timeout=2, cwd=r"c:\Users\user\Documents\Cursor\SFRFR", env=env, input="")
    err = (p2.stderr or "") + (p2.stdout or "")
    log("H2b", "lsp_server short launch", {"returncode": p2.returncode, "missing_module": "vscode_common_python_lsp" in err, "err_tail": err[-800:]})
except subprocess.TimeoutExpired as e:
    err = ""
    if e.stderr:
        err += e.stderr.decode("utf-8", "replace") if isinstance(e.stderr, (bytes, bytearray)) else e.stderr
    if e.stdout:
        err += e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, (bytes, bytearray)) else e.stdout
    log("H2b", "lsp_server short launch timeout (expected if server waits stdio)", {"missing_module": "vscode_common_python_lsp" in err, "err_tail": err[-800:], "timed_out": True})

print("done")
