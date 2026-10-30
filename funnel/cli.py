"""The command line and the order in which the steps run."""
from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from dataclasses import replace

from . import __version__
from .assets import write_assets_folder
from .context import Context
from .dialog import choose_run_settings
from .journeys import (
    step2_filter_companies,
    step3_build_stage_paths,
    step4_snapshot_each_month,
)
from .loader import step0_prepare_settings, step1_load_and_check_export
from .page import build_page_and_write_files, load_aesgcm
from .sankey import step5_build_nodes_and_links, step6_draw_chart
from .search_index import step7_build_search_index_and_page_data
from .settings import (
    HERE,
    RunSettings,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Read the command line.

    Nothing is read from disk and no window is opened here, so ``--help`` and ``--version`` work
    on any computer.

    Args:
        argv: The arguments (without the program name). ``None`` means "use sys.argv", which is what
            happens when the script is run. A list is used by tests.

    Returns:
        The parsed options: ``csv`` (a path or None), ``no_dialog`` and ``no_open`` (booleans).
    """
    # The parser describes the options; argparse builds --help from these texts and rejects unknown options.
    parser = argparse.ArgumentParser(
        prog="lcs-graph.py",
        description="Build the Funnel Tracking dashboard (a password-protected Sankey page) from a "
                    "HubSpot companies export.",
        epilog='examples:\n'
               '  python lcs-graph.py\n'
               '  python lcs-graph.py "D:\\exports\\acme.csv"\n'
               '  python lcs-graph.py acme.csv --no-dialog --no-open',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    # The optional positional argument: the path of the export.
    parser.add_argument("csv", nargs="?", metavar="CSV",
                        help="the HubSpot companies export (default: all-companies.csv next to this script). "
                             "A relative path is taken from the folder you run the command in")
    # Two on/off switches (store_true: False unless the flag is given) and --version.
    parser.add_argument("--no-dialog", action="store_true",
                        help="do not open the setup window; use the constants as written "
                             "(the same as SHOW_DIALOG = False)")
    parser.add_argument("--no-open", action="store_true",
                        help="do not open the finished page in the browser (handy for scheduled runs)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)



def main(argv: Sequence[str] | None = None) -> int:
    """Run the whole program: read the options, then run the steps in order.

    The settings of the run live in one ``RunSettings`` object that is passed along; nothing global is changed,
    so calling main() twice in one Python session starts from the same settings both times. Only the working
    folder is changed while it runs, and it is put back at the end.

    Args:
        argv: The command line arguments (without the program name); ``None`` = ``sys.argv``.

    Returns:
        The exit code: 0 when the page was written, 1 when the CSV could not be found, 130 when stopped
        with Ctrl+C. Problems with the settings or the export stop the program with a clear message
        (``SystemExit``), which Python turns into exit code 1.
    """
    args = parse_args(argv)
    saved_folder = os.getcwd()
    # A relative CSV path from the command line means "relative to where YOU ran the command", so it
    # is made absolute BEFORE the working folder changes below.
    csv_from_command_line = os.path.abspath(args.csv) if args.csv else None
    try:
        # Make the script's folder the "current directory" so relative file names (all-companies.csv)
        # always refer to the script's own folder, wherever you launched it from. (The output goes to
        # OUTPUT_ROOT, which is the script's folder too, in a new folder per run.)
        os.chdir(HERE)
        cfg = RunSettings(open_browser=not args.no_open)      # the constants, with today's date and the start time
        if csv_from_command_line:
            cfg = replace(cfg, csv=csv_from_command_line)
        if args.no_dialog:
            cfg = replace(cfg, show_dialog=False)
        ctx = Context(cfg=cfg)                               # the values the steps hand to each other
        # The pipeline. Each call reads what earlier steps left in ctx and adds its own results.
        step0_prepare_settings(ctx)              # validate the settings first, before any window opens
        ctx.cfg = choose_run_settings(ctx.cfg)   # the setup window (may replace some settings)
        if ctx.cfg.password:
            # Check now, before the slow processing starts, so a missing package does not waste time.
            load_aesgcm()          # stop right away if the package is missing
        step1_load_and_check_export(ctx)                 # read the CSV, check it, find the stage columns
        step2_filter_companies(ctx)                      # decide which companies are charted
        step3_build_stage_paths(ctx)                     # each company's journey through the stages
        step4_snapshot_each_month(ctx)                   # its stage at the end of every month
        step5_build_nodes_and_links(ctx)                 # boxes and ribbons, with their positions
        step6_draw_chart(ctx)                            # the Plotly figure
        step7_build_search_index_and_page_data(ctx)      # per-company data for the page, plus the chart HTML
        write_assets_folder(ctx)                         # assets/: code, styles and Plotly
        build_page_and_write_files(ctx)                  # index.html (encrypted when a password is set)
        return 0                                         # success
    except FileNotFoundError as err:
        print(f"File not found: {err.filename or err}")
        print("Give the path of the HubSpot export (python lcs-graph.py \"D:\\exports\\acme.csv\") or put "
              "all-companies.csv next to the script.")
        return 1
    except KeyboardInterrupt:
        print("\nStopped.")
        return 130
    finally:
        os.chdir(saved_folder)                  # put the working folder back
