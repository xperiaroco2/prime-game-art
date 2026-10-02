"""Runner commands, one module per command, found by runner.cli at start.

A command module defines:
- NAME: the command word (`tools/run.py <NAME>`), unique across modules;
- HELP: one line for `tools/run.py --help`;
- add_arguments(parser): adds its arguments to an argparse parser;
- run(args) -> int: does the work and returns the exit code; raise common.Failure with an actionable message to fail.

Modules whose file name starts with `_` are helpers, not commands.
"""
