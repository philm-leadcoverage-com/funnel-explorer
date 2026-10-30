#!/usr/bin/env python3
"""Funnel Tracking: a HubSpot lifecycle Sankey dashboard generator.

By Phil Mann at LeadCoverage, phil.m@leadcoverage.com

Reads a HubSpot companies export (CSV) and writes one password-protected web page. Run it with

    python lcs-graph.py [CSV] [--no-dialog] [--no-open] [--version] [--help]

This file only checks that Python and the packages are new enough, then starts the program in the
``funnel`` folder next to it (keep the two together). The settings you edit are in funnel/settings.py and
funnel/clients.py. The full guide is in README.md.
"""
from __future__ import annotations

import importlib
import sys

# The script uses f-strings, pandas 2+/3 and numpy 2: Python 3.9 is the practical floor.
if sys.version_info < (3, 9):  # noqa: UP036 - kept on purpose: it gives a friendly message on an old Python
    raise SystemExit(
        f"This script needs Python 3.9 or newer, but you are running "
        f"{sys.version_info.major}.{sys.version_info.minor}. Install a newer Python and try again."
    )

# A clear message (with the exact command to run) instead of a raw "ModuleNotFoundError" traceback.
try:
    import numpy  # noqa: F401  (only checked here; the real imports are in the funnel package)
    import pandas  # noqa: F401
    import plotly.graph_objects  # noqa: F401
except ImportError as _import_error:
    # Work out which of the three are missing, so the message can list them all at once.
    _missing_packages = []
    for _package in ("numpy", "pandas", "plotly"):
        try:
            importlib.import_module(_package)  # just try to load it; we only care if it fails
        except ImportError:
            _missing_packages.append(_package)
    if not _missing_packages:
        raise  # some other import problem: show the real error
    # sys.executable is the exact python.exe running this script, so the printed command
    # installs into the right Python even when several are installed.
    _message = (
        "Missing Python package(s): " + ", ".join(_missing_packages) + "\n"
        "Install them with this command, then run the script again:\n"
        f'    "{sys.executable}" -m pip install {" ".join(_missing_packages)}'
    )
    if __name__ == "__main__":
        raise SystemExit(_message) from None  # run as a program: just the friendly message
    raise ImportError(_message) from _import_error  # imported by other code: a normal, catchable error

from funnel import __version__  # noqa: E402
from funnel.cli import main, parse_args  # noqa: E402

__all__ = ["__version__", "main", "parse_args"]

# The standard guard: run main() only when this file is executed as a program (python lcs-graph.py),
# never when it is imported. SystemExit passes main()'s exit code to the operating system.
if __name__ == "__main__":
    raise SystemExit(main())
