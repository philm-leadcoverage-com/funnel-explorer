"""Reads the HubSpot export (only the columns it needs) and checks it: steps 0 and 1."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .clients import stage_label_overrides
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
    OTHER,
    PRE_BUCKET_MIN_STAGE,
    SQL,
    SUBSCRIBER,
)
from .stages import build_vocabulary, classify_names, normalize, own_first_name

# The five standard HubSpot columns the script cannot work without.
REQUIRED = ["Record ID", "Company name", "Company Domain Name", "Create Date", "Lifecycle Stage"]
# HubSpot names the stage-entry columns like:  Date entered "Lead (Lifecycle Stage Pipeline)"
STAGE_DATE_COLUMN = re.compile(r'^Date entered "(.+) \([^()]*\)"$')
# The names the "Copy funnel" button writes for each bucket ("" = the bucket is not part of the copied funnel).
COPY_FULL_NAMES = {"SUBSCRIBER": "Subscriber", "LEAD": "Lead", "MQL": "MQL", "SQL": "SQL", "OPP": "Opp", "CUSTOMER": "Customer"}


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
    """Validate the bucket settings and build the stage-name vocabulary.

    Checks that LABELS, BAND_COLORS and the seven stage buckets are consistent (stopping with a clear
    message if not) and turns the bucket text into VOCAB: each listed stage name -> level (0 = the OTHER bucket at
    the bottom, 1 = SUBSCRIBER ... 6 = CUSTOMER). Also works out PRE_MIN, SQL_LEVEL, OTHER_LEVEL and SUB_LEVEL, the
    levels later steps compare against. The names of one export are placed in buckets in step 1.

    Args:
        ctx: The shared Context (see context.py). The step reads what earlier steps stored in it and
            adds its own results.
    """
    # The seven bucket keys, bottom to top. A stage's "level" is its position in this list
    # (OTHER = 0, SUBSCRIBER = 1 ... CUSTOMER = 6). Levels are what the rest of the program works with.
    BUCKET_KEYS = ["OTHER", "SUBSCRIBER", "LEAD", "MQL", "SQL", "OPP", "CUSTOMER"]
    # The bucket texts in the same order, so BUCKET_TEXT[level] is the text for that level.
    BUCKET_TEXT = [OTHER, SUBSCRIBER, LEAD, MQL, SQL, OPP, CUSTOMER]
    # Fail early with a clear message if the lists have the wrong length.
    if len(LABELS) != len(BUCKET_KEYS) or len(BAND_COLORS) != len(BUCKET_KEYS):
        raise SystemExit(f"LABELS and BAND_COLORS must each have exactly {len(BUCKET_KEYS)} entries (one per bucket).")
    # VOCAB maps each listed stage name to its level, e.g. {"prospect": 1, "marketing qualified lead": 3, ...}.
    VOCAB = build_vocabulary(BUCKET_TEXT)
    # PRE_BUCKET_MIN_STAGE must be one of the five upper bucket keys (a company can never
    # qualify by reaching the OTHER or SUBSCRIBER bucket).
    if PRE_BUCKET_MIN_STAGE.strip().upper() not in BUCKET_KEYS[2:]:
        raise SystemExit("PRE_BUCKET_MIN_STAGE must be one of: LEAD, MQL, SQL, OPP, CUSTOMER")
    # PRE_MIN: the level number of that stage (for MQL this is 3).
    PRE_MIN = BUCKET_KEYS.index(PRE_BUCKET_MIN_STAGE.strip().upper())
    # SQL_LEVEL: level of the SQL bucket (4). Used by a safety filter in step 2.
    SQL_LEVEL = BUCKET_KEYS.index("SQL")
    OTHER_LEVEL = BUCKET_KEYS.index("OTHER")                  # the bottom box: unqualified, internal, partners ...
    SUB_LEVEL = BUCKET_KEYS.index("SUBSCRIBER")               # where a company created above the bottom starts its climb

    # --- values handed to the later steps ---
    ctx.update(
        BUCKET_KEYS=BUCKET_KEYS, VOCAB=VOCAB, PRE_MIN=PRE_MIN,
        SQL_LEVEL=SQL_LEVEL, OTHER_LEVEL=OTHER_LEVEL, SUB_LEVEL=SUB_LEVEL,
    )


def step1_load_and_check_export(ctx: Context) -> None:
    """STEP 1: LOAD AND CHECK THE EXPORT.

    Goal of this step: read the CSV, make sure it has the columns we need, place every stage name of the
    export in a bucket (see stages.py), find which "Date entered ..." columns exist, choose the names printed
    on the chart, work out the start date and detect the HubSpot backfill stamp.

    Args:
        ctx: The shared Context (see context.py). The step reads what earlier steps stored in it and
            adds its own results.
    """
    # --- values produced by earlier steps ---
    cfg = ctx.cfg
    BUCKET_KEYS, VOCAB, OTHER_LEVEL, SUB_LEVEL, start = (
        ctx.BUCKET_KEYS, ctx.VOCAB, ctx.OTHER_LEVEL, ctx.SUB_LEVEL, ctx.start)

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

    # the "Date entered <stage> (<pipeline>)" columns, matched without caring about capitals
    # HubSpot names these columns like:  Date entered "Lead (Lifecycle Stage Pipeline)"
    # STAGE_COL maps the lower-case stage name ("lead") to the real column name in the CSV.
    # display maps the same lower-case name to how the export writes it ("Lead"), for the messages and the chart.
    STAGE_COL = {}
    display = {}
    for _c in df.columns:
        # The regex captures the text between the first quote and the " (" that starts the
        # pipeline name: group(1) = the stage name, e.g. "Marketing Qualified Lead".
        _m = STAGE_DATE_COLUMN.match(_c)
        if _m:
            STAGE_COL[_m.group(1).strip().lower()] = _c
            display.setdefault(_m.group(1).strip().lower(), _m.group(1).strip())

    # The text of each company's CURRENT lifecycle stage, cleaned: blanks for missing values,
    # surrounding spaces removed, all lower case (so it can be compared with the stage names).
    raw_stage = df["Lifecycle Stage"].fillna("").astype(str).str.strip()
    stage_text_norm = raw_stage.str.lower()
    for _text in raw_stage[raw_stage != ""].unique():
        display.setdefault(_text.lower(), _text)

    # Place EVERY stage name of the export (a "Date entered" column or a company's current stage) in a bucket.
    # LV maps each lower-case stage name to its level, e.g. {"subscriber": 1, "partner": 0, "lead": 2, ...}.
    LV, typos, unmatched = classify_names(display, VOCAB, OTHER_LEVEL)
    for _name, _how in typos.items():
        print(f'      Note: the stage "{display[_name]}" was read as a typo ({_how}).')
    if unmatched:
        print(f"      WARNING: these stages matched no known name, so they were put in Other: "
              f"{[display[n] for n in unmatched]}")
        print("               If one belongs in another bucket, add its name to that bucket in settings.py.")
    # Stages that exist in the export but have no "Date entered" column.
    # Without the date a company's journey cannot be reconstructed, only its current stage.
    no_column = [display[n] for n in LV if n not in STAGE_COL]
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
    # Same stages, but mapped to their level: {"lead": 2, "marketing qualified lead": 3, ...}
    # Only stages that really have a date column are included.
    STAGE_LEVEL = {name: LV[name] for name in stage_dates}
    # One Create Date per row (parsed to Timestamps).
    created_list = pd.to_datetime(df["Create Date"]).tolist()
    # The level of each company's CURRENT stage. A company with no stage at all counts as Other.
    cur_list = stage_text_norm.map(LV).fillna(OTHER_LEVEL).astype(int).tolist()

    # --- the names printed on the chart ---
    # The Subscriber box uses the name THIS account gives that stage (Subscriber, Prospect, Target ...); an account
    # whose stage is the standard "Subscriber" keeps the short label from LABELS. ACCOUNT_STAGE_LABELS (clients.py) can
    # force a name for one account. copy_names are the names the "Copy funnel" button writes ("" = not copied).
    labels = list(LABELS)
    copy_names = [COPY_FULL_NAMES.get(_key, "") for _key in BUCKET_KEYS]
    _current = stage_text_norm.value_counts()
    counts = {n: sum(1 for v in stage_dates.get(n, []) if not pd.isna(v)) + int(_current.get(n, 0)) for n in LV}
    _own = own_first_name(SUB_LEVEL, LV, display, typos, counts)
    if _own and normalize(_own) != "subscriber":
        labels[SUB_LEVEL] = copy_names[SUB_LEVEL] = _own
    for _key, _name in stage_label_overrides(cfg.portal_id).items():     # a name forced for this account
        if _key in BUCKET_KEYS:
            labels[BUCKET_KEYS.index(_key)] = _name
            if copy_names[BUCKET_KEYS.index(_key)]:
                copy_names[BUCKET_KEYS.index(_key)] = _name

    # A bucket that no stage of this export belongs to (an account that starts at Lead has no Subscriber stage) is not
    # part of the copied funnel.
    for _lvl in range(len(BUCKET_KEYS)):
        if copy_names[_lvl] and _lvl not in LV.values():
            copy_names[_lvl] = ""

    # Print the buckets exactly as the script understood them. This is the quickest way to
    # spot a mistake when you set the script up for a new client.
    print("      Buckets (bottom to top):")
    for _lvl, _key in enumerate(BUCKET_KEYS):
        _names = [display[n] for n, level in LV.items() if level == _lvl]            # all stage names in this bucket
        print(f"        {labels[_lvl]:<12} <- {', '.join(_names) if _names else '(none)'}")

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
        BACKFILL=BACKFILL, LV=LV, STAGE_COL=STAGE_COL, STAGE_LEVEL=STAGE_LEVEL,
        copy_names=copy_names, created_list=created_list, cur_list=cur_list, df=df, labels=labels,
        stage_dates=stage_dates, stage_text_norm=stage_text_norm, start=start,
    )

