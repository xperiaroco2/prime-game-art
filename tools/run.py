"""prime-game-art task runner: python tools/run.py <command> [args] (or tools\\run.cmd, tools/run.sh).

Commands live in tools/runner/commands/, one module each, found at start (see that package's docstring), so tasks
running in parallel add commands without touching this file.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from runner.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
