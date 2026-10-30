"""Reads the HubSpot export (only the columns it needs) and checks it: steps 0 and 1."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .context import Context
from .settings import (
    BACKFILL_STAMP,
    BAND_COLORS,
    CUSTOMER,
    DETAIL_LINES,
    LABELS,
    LEAD,
    LOGO_URL_COLUMN,
    MQL,
    OPP,
    PRE_BUCKET_MIN_STAGE,
    SQL,
    SUBSCRIBER,
)

# The five standard HubSpot columns the script cannot work without.
REQUIRED = ["Record ID", "Company name", "Company Domain Name", "Create Date", "Lifecycle Stage"]
# HubSpot names the stage-entry columns like:  Date entered "Lead (Lifecycle Stage Pipeline)"
STAGE_DATE_COLUMN = re.compile(r'^Date entered "(.+) \([^()]*\)"$')


def columns_to_read(header: list[str]) -> list[str]:
    """Pick the export columns the run really needs, in file order.

    A HubSpot export can have 170+ columns, but the page only uses the five required ones, every
    ``Date entered "<stage> (...)"`` column, "Date entered current stage", the DETAIL_LINES fields and the logo
    column. Reading just those is several times faster and needs about a quarter of the memory. Names are
    matched the same way the details are later (capitals and surrounding spaces ignored).

    Args:
        header: The column names of the export (its first line).

    Returns:
        The names to pass to ``pandas.read_csv(usecols=...)``.
    """
    lookup = {str(c).strip().lower(): c for c in header}      # lower-case name -> real name (the last one wins)
    wanted = set(REQUIRED) | {"Date entered current stage"}
    wanted |= {c for c in header if STAGE_DATE_COLUMN.match(c)}
    names = [name for line in DETAIL_LINES for name in line]
    if LOGO_URL_COLUMN.strip():
        names.append(LOGO_URL_COLUMN)
    wanted |= {lookup[n.strip().lower()] for n in names if n.strip().lower() in lookup}
    return [c for c in header if c in wanted]


def step0_prepare_settings(ctx: Context) -> None:
    """Validate the bucket settings and build the stage-name lookup.

    Checks that LABELS, BAND_COLORS and the six stage buckets are consistent (stopping with a clear
    message if not) and turns the bucket text into LV: lower-case HubSpot stage name -> level
    (0 = bottom bucket). Also works out PRE_MIN and SQL_LEVEL, the two levels later steps compare against.

    Args:
        ctx: The shared Context (see context.py). The step reads what earlier steps stored in it and
            adds its own results.
    """
    # --- Turn the bucket text above into a lookup: stage name -> level (0 = bottom) -------
    # The six bucket keys, bottom to top. A stage's "level" is its position in this list
    # (SUBSCRIBER = 0 ... CUSTOMER = 5). Levels are what the rest of the program works with.
    BUCKET_KEYS = ["SUBSCRIBER", "LEAD", "MQL", "SQL", "OPP", "CUSTOMER"]
    # The bucket texts in the same order, so BUCKET_TEXT[level] is the text for that level.
    BUCKET_TEXT = [SUBSCRIBER, LEAD, MQL, SQL, OPP, CUSTOMER]
    # Fail early with a clear message if the lists have the wrong length.
    if len(LABELS) != 6 or len(BAND_COLORS) != 6:
        raise SystemExit("LABELS and BAND_COLORS must each have exactly 6 entries (one per bucket).")
    # LV maps each lower-case HubSpot stage name to its level, e.g. {"subscriber": 0, "partner": 0,
    # "lead": 1, "marketing qualified lead": 2, ...}.
    LV = {}
    for _lvl, _text in enumerate(BUCKET_TEXT):          # _lvl = 0..5, _text = that bucket's text
        for _name in _text.split(","):                  # "SUBSCRIBER, OTHER" -> ["SUBSCRIBER", " OTHER"]
            _name = _name.strip().lower()               # remove spaces, ignore capitals
            if not _name:
                continue                                # skip empty pieces (an empty bucket "")
            if _name in LV and LV[_name] != _lvl:
                # the same stage listed in two different buckets is ambiguous: stop.
                raise SystemExit(f'The stage "{_name}" is in two buckets. A stage can only be in one.')
            LV[_name] = _lvl
    # PRE_BUCKET_MIN_STAGE must be one of the five upper bucket keys (a company can never
    # qualify by reaching the bottom bucket).
    if PRE_BUCKET_MIN_STAGE.strip().upper() not in BUCKET_KEYS[1:]:
        raise SystemExit("PRE_BUCKET_MIN_STAGE must be one of: LEAD, MQL, SQL, OPP, CUSTOMER")
    # PRE_MIN: the level number of that stage (for MQL this is 2).
    PRE_MIN = BUCKET_KEYS.index(PRE_BUCKET_MIN_STAGE.strip().upper())
    # SQL_LEVEL: level of the SQL bucket (3). Used by a safety filter in step 2.
    SQL_LEVEL = BUCKET_KEYS.index("SQL")

    # --- values handed to the later steps ---
    ctx.update(
        BUCKET_KEYS=BUCKET_KEYS, LV=LV, PRE_MIN=PRE_MIN,
        SQL_LEVEL=SQL_LEVEL,
    )


def step1_load_and_check_export(ctx: Context) -> None:
    """STEP 1: LOAD AND CHECK THE EXPORT.

    Goal of this step: read the CSV, make sure it has the columns we need, turn the bucket
    text into a stage lookup, find which "Date entered ..." columns exist, work out the
    start date and detect the HubSpot backfill stamp.

    Args:
        ctx: The shared Context (see context.py). The step reads what earlier steps stored in it and
            adds its own results.
    """
    # --- values produced by earlier steps ---
    cfg = ctx.cfg
    BUCKET_KEYS, LV, start = ctx.BUCKET_KEYS, ctx.LV, ctx.start

    print(f"[1/7] Loading {cfg.csv} ...")
    # Only the columns the page really uses are read (about a third of a typical export): several times faster
    # and a fraction of the memory. low_memory=False makes pandas read each column whole before guessing its
    # type, which avoids "mixed type" surprises in a file with 170+ columns.
    header = pd.read_csv(cfg.csv, nrows=0).columns.tolist()          # just the first line of the file
    wanted = columns_to_read(header)
    df = pd.read_csv(cfg.csv, usecols=wanted, low_memory=False)
    print(f"      Loaded {len(df):,} companies ({len(wanted)} of {len(header)} columns)")

    # The script cannot work without these five standard HubSpot columns.
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise SystemExit(f"The CSV is missing these HubSpot columns: {missing}")

    # Print the buckets exactly as the script understood them. This is the quickest way to
    # spot a typo in a stage name when you set the script up for a new client.
    print("      Buckets (bottom to top):")
    for _lvl, _key in enumerate(BUCKET_KEYS):
        _names = [n for n, level in LV.items() if level == _lvl]           # all stage names in this bucket
        print(f"        {LABELS[_lvl]:<12} <- {', '.join(_names) if _names else '(none)'}")

    # the "Date entered <stage> (<pipeline>)" columns, matched without caring about capitals
    # HubSpot names these columns like:  Date entered "Lead (Lifecycle Stage Pipeline)"
    # STAGE_COL maps the lower-case stage name ("lead") to the real column name in the CSV.
    STAGE_COL = {}
    for _c in df.columns:
        # The regex captures the text between the first quote and the " (" that starts the
        # pipeline name: group(1) = the stage name, e.g. "Marketing Qualified Lead".
        _m = STAGE_DATE_COLUMN.match(_c)
        if _m:
            STAGE_COL[_m.group(1).strip().lower()] = _c

    # The text of each company's CURRENT lifecycle stage, cleaned: blanks for missing values,
    # surrounding spaces removed, all lower case (so it can be compared with the LV keys).
    stage_text_norm = df["Lifecycle Stage"].fillna("").astype(str).str.strip().str.lower()
    # Stages that appear in the export (as date columns or as a company's current stage) but
    # are not in any bucket: the script cannot place them, so it warns instead of guessing.
    not_mapped = sorted({n for n in STAGE_COL if n not in LV} |
                        set(stage_text_norm[(stage_text_norm != "") & ~stage_text_norm.isin(LV)]))
    if not_mapped:
        print(f"      WARNING: these stages are in the export but in no bucket, so they are ignored: "
              f"{not_mapped}")
    # Stages that ARE in a bucket but whose "Date entered" column is missing from the export.
    # Without the date a company's journey cannot be reconstructed, only its current stage.
    no_column = [n for n in LV if n not in STAGE_COL]
    if no_column:
        print(f"      WARNING: no 'Date entered' column in the export for: {no_column}")
        print("               Without those a company can only be drawn in the stage it is in now.")
        print('               Add the "Date entered <stage> (Lifecycle Stage Pipeline)" properties to the')
        print("               HubSpot export for the full journey of each company.")
    # stage_dates[stage name] = a Python list with one date (or NaT = "no date") per CSV row.
    # Lists (not pandas Series) are used because the loops below index them very often and
    # list indexing is much faster than Series.iat.
    stage_dates = {
        name: pd.to_datetime(df[STAGE_COL[name]], errors="coerce").tolist()
        for name in LV if name in STAGE_COL
    }
    # Same stages, but mapped to their level: {"lead": 1, "marketing qualified lead": 2, ...}
    # Only stages that really have a date column are included.
    STAGE_LEVEL = {name: LV[name] for name in stage_dates}
    # One Create Date per row (parsed to Timestamps).
    created_list = pd.to_datetime(df["Create Date"]).tolist()
    # The level of each company's CURRENT stage; -1 means "unknown / not in any bucket".
    cur_list = stage_text_norm.map(LV).fillna(-1).astype(int).tolist()

    # --- start date ---
    start = cfg.start                                     # the chart's first date (auto-detect may replace it)
    if cfg.autodetect:
        # Use the first day of the month of the oldest company, so nothing is older than START.
        _first = pd.Series(created_list).min()
        start = pd.Timestamp(_first.year, _first.month, 1)
        print(f"      Start date auto-detected: {start:%Y-%m-%d} (earliest Create Date is {_first:%Y-%m-%d})")
    else:
        print(f"      Start date: {start:%Y-%m-%d} (companies created earlier go in {cfg.pre_name})")


    # --- backfill stamp ---
    def detect_backfill() -> pd.Timestamp | None:
        """Find the HubSpot "backfill" minute, if the export has one.

        Some HubSpot portals have one single minute in which hundreds or thousands of OLD
        companies were given a stage-entry date (HubSpot filling in history when a lifecycle
        pipeline was created or changed). Those dates are not real moves and would look like a
        giant wave of companies changing stage at once.

        How it is detected: for every stage-entry date that is more than 7 days AFTER the
        company's Create Date, count how often each exact timestamp occurs. If the most common
        timestamp occurs at least 300 times AND at least 3 times more often than the runner-up,
        it is the backfill stamp.

        Returns:
            The backfill ``pandas.Timestamp``, or ``None`` when no clear stamp exists.
        """
        created = pd.DatetimeIndex(created_list).to_numpy()   # one Create Date per row (NaT = none)
        late = []                                             # every stage-entry date stamped long after creation
        for dates in stage_dates.values():                    # one list of dates per stage
            entered = pd.DatetimeIndex(dates).to_numpy()
            counted = ~np.isnat(entered) & ~np.isnat(created) & (entered - created > np.timedelta64(7, "D"))
            late.append(entered[counted])
        if not late:
            return None
        stamps, counts = np.unique(np.concatenate(late), return_counts=True)   # each exact timestamp and how often it occurs
        top = np.argsort(-counts, kind="stable")[:2]          # the most common timestamp and its runner-up
        if len(top) and counts[top[0]] >= 300 and (len(top) < 2 or counts[top[0]] >= 3 * counts[top[1]]):
            return pd.Timestamp(stamps[top[0]])  # pyright: ignore[reportArgumentType]
        return None


    # BACKFILL_STAMP may be "AUTO", "" (none) or an explicit date/time string.
    _bf = BACKFILL_STAMP.strip()
    if _bf.upper() == "AUTO":
        BACKFILL = detect_backfill()                      # look for it in the data
    elif _bf == "":
        BACKFILL = None                                   # the user says there is none
    else:
        BACKFILL = pd.Timestamp(_bf)                      # the user gave the exact stamp
    print(f"      Backfill stamp: {BACKFILL if BACKFILL is not None else 'none'}")

    # --- values handed to the later steps ---
    ctx.update(
        BACKFILL=BACKFILL, STAGE_COL=STAGE_COL, STAGE_LEVEL=STAGE_LEVEL,
        created_list=created_list, cur_list=cur_list, df=df,
        stage_dates=stage_dates, stage_text_norm=stage_text_norm, start=start,
    )

