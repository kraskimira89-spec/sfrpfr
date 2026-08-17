"""Probe: почему падает расширение ms-python.mypy-type-checker при старте."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time

LOG_PATH = pathlib.Path(__file__).resolve().parents[1] / "debug-6f3231.log"
SESSION_ID = "6f3231"
EXT = (
    pathlib.Path.home()
    / ".cursor"
    / "extensions"
    / "ms-python.mypy-type-checker-2026.6.0"
)
LIBS = EXT / "bundled" / "libs"
SERVER = EXT / "bundled" / "tool" / "lsp_server.py"


def log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    # #region agent log
    payload = {
        "sessionId": SESSION_ID,
        "runId": "pre-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    # #endregion


def main() -> int:
    py = sys.executable
    log(
        "H1",
        "debug_mypy_ext_probe.py:ext",
        "extension paths",
        {
            "ext_exists": EXT.is_dir(),
            "libs_exists": LIBS.is_dir(),
            "server_exists": SERVER.is_file(),
            "python": py,
        },
    )

    names = sorted(p.name for p in LIBS.iterdir()) if LIBS.is_dir() else []
    has_common = any("vscode_common_python_lsp" in n for n in names)
    log(
        "H1",
        "debug_mypy_ext_probe.py:libs",
        "bundled libs listing",
        {"has_vscode_common_python_lsp": has_common, "lib_count": len(names), "sample": names[:25]},
    )

    # H2: import fails when launching like the extension does
    env = os.environ.copy()
    env["LS_IMPORT_STRATEGY"] = "useBundled"
    proc = subprocess.run(
        [py, str(SERVER)],
        cwd=str(pathlib.Path(__file__).resolve().parents[1]),
        capture_output=True,
        text=True,
        timeout=8,
        env=env,
        input="",
    )
    err = (proc.stderr or "") + (proc.stdout or "")
    log(
        "H2",
        "debug_mypy_ext_probe.py:launch",
        "lsp_server launch result",
        {
            "returncode": proc.returncode,
            "stderr_tail": err[-800:],
            "missing_module": "vscode_common_python_lsp" in err,
        },
    )

    # H3: venv mypy itself works (CLI), so toast is extension-only
    cli = subprocess.run(
        [py, "-m", "mypy", "--version"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    log(
        "H3",
        "debug_mypy_ext_probe.py:cli",
        "venv mypy CLI",
        {"returncode": cli.returncode, "out": (cli.stdout or cli.stderr or "").strip()[:200]},
    )

    # H4: installing into bundled/libs would resolve import
    probe_code = (
        "import sys; sys.path.insert(0, r'%s'); "
        "import importlib.util as u; "
        "print('found' if u.find_spec('vscode_common_python_lsp') else 'missing')"
    ) % str(LIBS).replace("\\", "\\\\")
    spec = subprocess.run([py, "-c", probe_code], capture_output=True, text=True, timeout=10)
    log(
        "H4",
        "debug_mypy_ext_probe.py:find_spec",
        "find_spec against bundled/libs",
        {"out": (spec.stdout or "").strip(), "err": (spec.stderr or "").strip()[:200]},
    )

    print(f"Wrote {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
