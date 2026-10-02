"""Runs a Python script inside headless Blender, never with a window:
`blender -b --factory-startup --python-exit-code 1 --python <script> -- <args>`.

Scripts live in tools/blender/ and read their own arguments after `--` (sys.argv[sys.argv.index("--") + 1:]).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from . import common

SCRIPTS = common.ROOT / "tools" / "blender"


def run_script(script: Path | str, args: list[str], timeout: float = 600) -> subprocess.CompletedProcess[str]:
    """Runs script (a path, or a file name in tools/blender/) in background Blender; a Python error inside it, a
    non-zero exit or a timeout raises common.Failure with the end of Blender's output."""
    path = Path(script)
    if not path.is_absolute():
        path = SCRIPTS / path
    if not path.is_file():
        raise common.Failure(f"no Blender script {path}")
    cmd = [common.blender_bin(), "-b", "--factory-startup", "--python-exit-code", "1", "--python", path, "--", *args]
    result = common.run(cmd, timeout)
    if result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        tail = "\n".join(output.splitlines()[-40:])
        raise common.Failure(f"Blender script {path.name} failed with exit code {result.returncode}:\n{tail}")
    return result
