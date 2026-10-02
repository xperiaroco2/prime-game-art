"""The command line: finds every command module in runner.commands and dispatches to it."""

from __future__ import annotations

import argparse
import importlib
import pkgutil
import sys
from types import ModuleType

from . import commands, pins
from .common import Failure, say


def discover() -> dict[str, ModuleType]:
    """Every module in runner.commands that defines NAME, HELP, add_arguments and run, by NAME."""
    found: dict[str, ModuleType] = {}
    for info in pkgutil.iter_modules(commands.__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{commands.__name__}.{info.name}")
        if not all(hasattr(module, attr) for attr in ("NAME", "HELP", "add_arguments", "run")):
            raise SystemExit(f"runner.commands.{info.name} lacks NAME, HELP, add_arguments or run")
        if module.NAME in found:
            raise SystemExit(f"two command modules are named {module.NAME!r}")
        found[module.NAME] = module
    return found


def main(argv: list[str]) -> int:
    if sys.version_info < pins.PYTHON_MIN:
        say(f"Python {'.'.join(map(str, pins.PYTHON_MIN))} or newer is needed, this is {sys.version.split()[0]}")
        return 1
    modules = discover()
    parser = argparse.ArgumentParser(prog="tools/run.py", description="prime-game-art task runner")
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    for name in sorted(modules):
        modules[name].add_arguments(sub.add_parser(name, help=modules[name].HELP))
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2
    try:
        return int(modules[args.command].run(args) or 0)
    except Failure as failure:
        say(f"{args.command}: {failure}")
        return 1
    except KeyboardInterrupt:
        return 130
