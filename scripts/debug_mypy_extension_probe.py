"""Probe why Cursor mypy extension fails on load. Writes NDJSON to debug-6f3231.log."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

SESSION = "6f3231"
LOG = Path(__file__).resolve().parents[1] / "debug-6f3231.log"
EXT = Path.home() / ".cursor" / "extensions" / "ms-python.mypy-type-checker-2026.6.0"
LIBS = EXT / "bundled" / "libs"
TOOL = EXT / "bundled" / "tool" / "lsp_server.py"
VENV_PY = Path(__file__).resolve().parents[1] / ".venv" / "Scripts" / "python.exe"


def log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    entry = {
        "sessionId": SESSION,
        "runId": "pre-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> int:
    # H1: shared package absent from bundled/libs
    names = sorted(p.name for p in LIBS.iterdir()) if LIBS.is_dir() else []
    has_shared = any("vscode_common_python_lsp" in n for n in names)
    log(
        "H1",
        "debug_mypy_extension_probe.py:H1",
        "bundled libs inventory",
        {"libs_dir": str(LIBS), "exists": LIBS.is_dir(), "has_shared_pkg": has_shared, "names": names},
    )

    # H2: same launch command as extension fails with ModuleNotFoundError
    py = str(VENV_PY if VENV_PY.is_file() else sys.executable)
    cmd = [py, str(TOOL)]
    env = os.environ.copy()
    env["LS_IMPORT_STRATEGY"] = "useBundled"
    proc = subprocess.run(
        cmd,
        cwd=str(Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=8,
        env=env,
        input="",
    )
    err = (proc.stderr or "") + (proc.stdout or "")
    log(
        "H2",
        "debug_mypy_extension_probe.py:H2",
        "lsp_server launch result",
        {
            "cmd": cmd,
            "returncode": proc.returncode,
            "stderr_tail": err[-1200:],
            "missing_module": "vscode_common_python_lsp" in err,
        },
    )

    # H3: package importable if installed into libs
    probe = (
        "import sys; "
        f"sys.path.insert(0, r'{LIBS}'); "
        "sys.path.insert(0, r'{TOOL.parent}'); "
        "import importlib.util as u; "
        "print('spec', u.find_spec('vscode_common_python_lsp')); "
        "print('ok')"
    ).replace("{TOOL.parent}", str(TOOL.parent))
    proc3 = subprocess.run([py, "-c", probe], capture_output=True, text=True, timeout=8)
    log(
        "H3",
        "debug_mypy_extension_probe.py:H3",
        "find_spec for shared package on libs path",
        {"stdout": (proc3.stdout or "").strip(), "stderr": (proc3.stderr or "").strip()[:500]},
    )

    # H4: historical Cursor Mypy.log pattern still present in latest non-empty log
    logs_root = Path(os.environ.get("APPDATA", "")) / "Cursor" / "logs"
    latest = None
    for p in sorted(logs_root.rglob("Mypy.log"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.stat().st_size > 0:
            latest = p
            break
    snippet = ""
    if latest:
        snippet = latest.read_text(encoding="utf-8", errors="replace")[-800:]
    log(
        "H4",
        "debug_mypy_extension_probe.py:H4",
        "latest non-empty Mypy.log",
        {
            "path": str(latest) if latest else None,
            "has_missing_module": "vscode_common_python_lsp" in snippet,
            "has_connection_error": "couldn't create connection" in snippet,
            "snippet_tail": snippet,
        },
    )

    # H5: toast source = LSP client error after crash loop (inferred from log markers)
    log(
        "H5",
        "debug_mypy_extension_probe.py:H5",
        "notification markers in latest log",
        {
            "server_init_failed": "Server initialization failed" in (snippet or ""),
            "restart_failed": "Restarting server failed" in (snippet or ""),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
