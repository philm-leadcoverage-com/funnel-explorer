"""Which companies are charted, each company's journey through the stages, and the month-end snapshots: steps 2 to 4."""
from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence

import numpy as np
import pandas as pd

from .context import Context
from .settings import (
    COUNT_BACKFILL_AS_MOVE,
)


def step2_filter_companies(ctx: Context) -> None:
    """STEP 2: FILTER.

    Goal of this step: decide WHICH companies appear on the chart.
    keep      -> created on/after START (the normal case).
    pre_keep  -> created BEFORE START but moved up to PRE_BUCKET_MIN_STAGE or higher only
    on/after START. They are drawn in the extra "Pre" box on the far left.
    everything else is left out, and skip_reason remembers WHY so the search box can
    explain it ("Not in the chart: ...").

    Args:
        ctx: The shared Context (see context.py). The step reads what earlier steps stored in it and
            adds its own results.
    """
    # --- values produced by earlier steps ---
    cfg = ctx.cfg
    (
        BACKFILL, PRE_MIN, SQL_LEVEL, STAGE_LEVEL, created_list, df, labels, stage_dates, start,
    ) = (
        ctx.BACKFILL, ctx.PRE_MIN, ctx.SQL_LEVEL, ctx.STAGE_LEVEL, ctx.created_list, ctx.df,
        ctx.labels, ctx.stage_dates, ctx.start,
    )

    print(f"[2/7] Filtering (created before {start:%Y-%m-%d}, or {labels[SQL_LEVEL]}+ before that date) ...")
    keep = []          # created on/after START
    pre_keep = []      # the Pre bucket
    skip_reason = {}   # row index -> why a company is not in the chart
    n_old = n_sql_early = 0                                   # counters for the printed summary
    for i in range(len(df)):                                  # i = row number in the CSV
        c0 = pd.Timestamp(created_list[i])                    # this company's Create Date
        if c0 < start:
            # --- an OLD company: does it belong in the Pre bucket? ---------------------
            hi_before = hi_after = False    # reached the minimum stage BEFORE / AFTER the start?
            for s_, lvl in STAGE_LEVEL.items():
                if lvl < PRE_MIN:
                    continue                                  # a lower stage cannot qualify
                v = stage_dates[s_][i]
                if pd.isna(v):
                    continue                                  # the company never entered this stage
                t = pd.Timestamp(v)
                if t < start:
                    hi_before = True                          # already that high before the chart began
                elif COUNT_BACKFILL_AS_MOVE or BACKFILL is None or t != BACKFILL:
                    hi_after = True                           # a REAL move after START (not the backfill stamp)
            if hi_after and not hi_before:
                pre_keep.append(i)                            # qualifies for the Pre bucket
            else:
                n_old += 1
                skip_reason[i] = (f"Not in the chart: reached {labels[PRE_MIN]} or above before {start:%b %Y}"
                                  if hi_before else
                                  f"Not in the chart: created before {start:%b %Y} with no move to "
                                  f"{labels[PRE_MIN]} or above after that date")
            continue                                          # old companies never go in "keep"
        # --- a company created on/after START ------------------------------------------
        # Safety filter: a company that reached SQL or above BEFORE the start date (possible
        # only when a stage date is earlier than its Create Date) is left out.
        # True when any stage at SQL level or above has a date before the start date.
        early_sql = any(
            lvl >= SQL_LEVEL and not pd.isna(stage_dates[s_][i]) and pd.Timestamp(stage_dates[s_][i]) < start
            for s_, lvl in STAGE_LEVEL.items()
        )
        if early_sql:
            n_sql_early += 1
            skip_reason[i] = f"Not in the chart: reached {labels[SQL_LEVEL]} or above before {start:%b %Y}"
            continue
        keep.append(i)
    # Two summary lines: how the companies created before the start were handled, and what was removed after it.
    print(f"      Created before start: {n_old + len(pre_keep):,}, of which "
          f"{len(pre_keep):,} moved to {labels[PRE_MIN]}+ only after start ({cfg.pre_name}) and "
          f"{n_old:,} are left out")
    print(f"      Created on/after start: {len(keep):,}; {n_sql_early:,} more removed "
          f"({labels[SQL_LEVEL]}+ before start)")
    # all_idx = the CSV row numbers that will be charted. Order matters: first all the normal
    # companies, then the Pre-bucket companies. pre_mask (step 3) relies on this order.
    all_idx = keep + pre_keep
    n_pre = len(pre_keep)                                     # how many companies are in the Pre bucket
    n_excluded = len(df) - len(all_idx)                       # in HubSpot but not on the chart
    print(f"      {n_excluded:,} companies in the export are excluded from the chart")
    print(f"      Charting {len(all_idx):,} companies ({n_pre:,} in {cfg.pre_name})")

    # --- values handed to the later steps ---
    ctx.update(
        all_idx=all_idx, keep=keep, n_excluded=n_excluded,
        n_pre=n_pre, pre_keep=pre_keep, skip_reason=skip_reason,
    )


def step3_build_stage_paths(ctx: Context) -> None:
    """STEP 3: BUILD EACH COMPANY'S STAGE PATH (same rules as the line chart).

    Goal of this step: for every charted company build its JOURNEY, a short list of
    (moment, stage level) points, for example:
    [(2025-06-26, 1), (2025-12-02, 2), (2026-08-17, 4)]
    = Subscriber from creation, Lead from 2 Dec, SQL from 17 Aug.
    (Levels: 0 Other, 1 Subscriber, 2 Lead, 3 MQL, 4 SQL, 5 Opp, 6 Customer.)
    Rules:
    * every stage-entry date is an "event";
    * events on the same day as creation count as "at creation";
    * events at exactly the same instant are collapsed into one point (the company's
    current stage if it is among them, otherwise the highest stage), because HubSpot
    stamps all skipped stages with the same minute when a record jumps ahead;
    * a company created ABOVE Subscriber first appears in Subscriber and "rises" at once, so the chart shows it
    arriving from below (a company created in Other starts in Other: it was never a Subscriber).

    Args:
        ctx: The shared Context (see context.py). The step reads what earlier steps stored in it and
            adds its own results.
    """
    # --- values produced by earlier steps ---
    (
        OTHER_LEVEL, STAGE_LEVEL, SUB_LEVEL, all_idx, created_list, cur_list, keep, n_pre, stage_dates,
    ) = (
        ctx.OTHER_LEVEL, ctx.STAGE_LEVEL, ctx.SUB_LEVEL, ctx.all_idx, ctx.created_list, ctx.cur_list, ctx.keep,
        ctx.n_pre, ctx.stage_dates,
    )

    print("[3/7] Building stage journeys ...")
    paths = []                                                # one tuple per charted company (same order as all_idx)
    for i in all_idx:
        c0 = pd.Timestamp(created_list[i])
        cur_i = cur_list[i]                                   # level of the CURRENT stage
        events = []                                           # list of (moment, level)
        for s, lvl in STAGE_LEVEL.items():
            v = stage_dates[s][i]
            if not pd.isna(v):
                t = pd.Timestamp(v)
                if t.normalize() <= c0.normalize():  # pyright: ignore[reportAttributeAccessIssue]  (neither is ever NaT here)
                    t = c0                                    # same day (or earlier) as creation = "at creation"
                events.append((t, lvl))
        if not events:
            # No stage dates at all: the only thing known is the current stage, assumed to hold
            # from the day the company was created.
            events = [(c0, max(cur_i, 0))]
        # Collapse events that share an exact timestamp into ONE level per moment.
        groups = {}                                           # moment -> list of levels at that moment
        for t, lvl in events:
            groups.setdefault(t, []).append(lvl)
        pts = []                                              # chronological (moment, level) points
        for t in sorted(groups):
            lvls = groups[t]
            # if the company's current stage is one of the tied stages use it, otherwise the highest
            lvl = cur_i if cur_i in lvls else max(lvls)
            if not pts or pts[-1][1] != lvl:                  # skip a point that repeats the previous level
                pts.append((t, lvl))
        first_t, first_l = pts[0]
        if first_t == c0 and first_l == OTHER_LEVEL:
            path = [(c0, first_l)] + pts[1:]                  # created in Other: it starts there, it was never a Subscriber
        elif first_t == c0:
            path = [(c0, SUB_LEVEL)]                          # start in Subscriber ...
            if first_l > SUB_LEVEL:
                path.append((c0, first_l))                    # ... and rise immediately if it started higher
            path += pts[1:]
        else:
            path = [(c0, first_l)] + pts[1:]                  # first stage date is later than creation: start there
        # Store: creation date, list of moments, list of levels. (Two parallel lists make the
        # binary search in step 4 simple.)
        paths.append((c0, [p[0] for p in path], [p[1] for p in path]))
    print(f"      {len(paths):,} journeys built")
    # pre_mask[r] is True when charted company number r belongs to the Pre bucket. It works
    # because all_idx = keep + pre_keep (normal companies first, Pre companies last).
    pre_mask = np.array([False] * len(keep) + [True] * n_pre)

    # --- values handed to the later steps ---
    ctx.update(
        paths=paths, pre_mask=pre_mask,
    )


def step4_snapshot_each_month(ctx: Context) -> None:
    """STEP 4: SNAPSHOT EVERY COMPANY'S STAGE AT THE END OF EACH MONTH.

    Goal of this step: build a table "snap" with one row per charted company and one column
    per month. Each cell is the company's stage LEVEL (0..6) at the end of that month, or
    NONE (-1) if the company did not exist yet. The Sankey ribbons are made by comparing
    two neighbouring columns of this table.

    Args:
        ctx: The shared Context (see context.py). The step reads what earlier steps stored in it and
            adds its own results.
    """
    # --- values produced by earlier steps ---
    cfg = ctx.cfg
    paths, start = ctx.paths, ctx.start

    print("[4/7] Taking month-end snapshots ...")
    month_ends = []                                           # the moment each month's snapshot is taken
    m = start                                                 # m walks forward one month at a time
    while m <= cfg.today:
        # the last minute of m's month (23:59 on the last day)
        end_of_month = (m + pd.offsets.MonthEnd(0)).replace(hour=23, minute=59)
        # the current (unfinished) month is cut off at "now", so the last column means "to date"
        month_ends.append(min(end_of_month, cfg.today + pd.Timedelta(hours=23, minutes=59)))
        m = m + pd.offsets.MonthBegin(1)                      # jump to the first day of the next month
    # Column labels such as "Dec 2025". The unfinished last month (the month so far) is labelled like any other.
    col_labels = [f"{t:%b %Y}" for t in month_ends]
    K = len(month_ends)                                       # number of month columns

    NONE = -1   # company does not exist yet at that snapshot
    # Start with "does not exist" everywhere, then fill in the stage where the company exists.
    snap = np.full((len(paths), K), NONE, dtype=int)
    for r, (c0, times, lvls) in enumerate(paths):             # r = row in snap, one per company
        for k, me in enumerate(month_ends):                   # k = month column, me = month end moment
            if c0 > me:
                continue                                      # not created yet by the end of this month
            # bisect_right(times, me) - 1 = index of the LAST journey point at or before month end
            idx = bisect_right(times, me) - 1
            snap[r, k] = lvls[max(idx, 0)]                    # max(...,0) guards the (rare) idx = -1
    # Drop empty months at the very start (e.g. a start date before the first company was
    # created). An empty column would have no boxes to link to and would only add blank space.
    first_k = next((k for k in range(K) if (snap[:, k] != NONE).any()), 0)
    if first_k:                               # months before the first company exists are left out
        print(f"      Skipping {first_k} empty month(s) at the start: {', '.join(col_labels[:first_k])}")
        # Cut the same number of months off all three month lists, so they stay in step with each other.
        month_ends = month_ends[first_k:]
        col_labels = col_labels[first_k:]
        snap = snap[:, first_k:]
        K = len(month_ends)                               # the new number of months
    print(f"      {K} snapshots: {col_labels[0]} to {col_labels[-1]}")
    for k in range(K):                                    # one console line per month: how many companies exist then
        print(f"      {col_labels[k]:>22}: {int((snap[:, k] != NONE).sum()):>7,} companies")

    # --- values handed to the later steps ---
    ctx.update(
        K=K, NONE=NONE, col_labels=col_labels,
        month_ends=month_ends, snap=snap,
    )



def is_success_journey(times: Sequence[pd.Timestamp], levels: Sequence[int], mql: int, sql: int,
                       backfill: pd.Timestamp | None = None, other: int | None = None) -> bool:
    """Say whether a company's journey is a "success story" for the Random success button.

    The company must also be NOW in the Opp or Customer bucket; the caller checks that, because it comes
    from the export's current stage. This function checks the journey itself, which has to
      * START below MQL (as a Subscriber or Lead, not created at MQL or SQL), and
      * PASS THROUGH BOTH MQL AND SQL without skipping a step: MQL is followed directly by SQL, and
      * NOT END in Other.
    A company that starts below MQL and is now Opp or Customer was by definition not always one.

    Visits to Other are ignored: a company that went to Other and came back is judged on the rest of its journey (so
    MQL, then Other, then SQL still counts). A company that is in Other now never qualifies, because it is not Opp or
    Customer (the caller's check) and its journey ends in Other (the check here).

    The journey is the list built in step 3: one point per stage change, stages stamped at the same instant are
    already collapsed into one point (so a company that jumped over MQL or SQL has no point for it). Step 3 also
    puts a made-up first point in Subscriber for a company created above it, at the same instant as its real
    first point; that point is not a real start and is ignored here.

    Examples (levels: 0 Other, 1 Subscriber, 2 Lead, 3 MQL, 4 SQL, 5 Opp, 6 Customer; ``other`` = 0):
        ``[2, 3, 4, 5]``       -> True   (Lead, MQL, SQL, Opp, each with its own date)
        ``[1, 2, 3, 4, 6]``    -> True   (SQL to Customer is fine)
        ``[2, 3, 0, 4, 5]``    -> True   (MQL, a visit to Other, then SQL: the visit is ignored)
        ``[2, 3, 5]``          -> False  (skipped SQL)
        ``[3, 4, 5]``          -> False  (started at MQL)
        ``[2, 3, 4, 5, 0]``    -> False  (ended in Other)

    Args:
        times: The moment of each point of the journey.
        levels: The stage level of each point (the bottom bucket is Other).
        mql: The level of the MQL bucket.
        sql: The level of the SQL bucket.
        backfill: The HubSpot backfill stamp (or None). A point at that moment is not a real move.
        other: The level of the Other bucket (None = there is none). Points in it are ignored.

    Returns:
        True when the journey started below MQL, went MQL then SQL and did not end in Other.
    """
    if not levels or (other is not None and levels[-1] == other):
        return False                                           # no journey, or it ended in Other
    if other is not None:                                      # leave out the visits to Other
        kept = [k for k, level in enumerate(levels) if level != other]
        times, levels = [times[k] for k in kept], [levels[k] for k in kept]
    start = levels[1] if len(levels) > 1 and times[0] == times[1] else levels[0]
    if start >= mql:
        return False
    for k in range(len(levels) - 1):
        if levels[k] == mql and levels[k + 1] == sql:
            if backfill is None or (times[k] != backfill and times[k + 1] != backfill):
                return True
    return False
