"""Boxes, ribbons and the Plotly figure: steps 5 and 6."""
from __future__ import annotations

from bisect import bisect_left
from collections import Counter, defaultdict
from collections.abc import Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .context import Context
from .settings import (
    BAND_COLORS,
    BAND_GAP_PX,
    BOX_MAX_PX,
    BOX_WIDTH_PX,
    CARRIED_LABEL,
    LABELS,
    MIN_COL_PX,
    MIN_WIDTH_SHARE,
    MARKED_DATES,
    MOVED_DOWN_COLOR,
    PRE_BUCKET_COLOR,
    STAYED_COLOR,
)


def hex_to_rgba(h: str, a: float) -> str:
    """Convert a ``#rrggbb`` hex color plus an opacity into a CSS ``rgba(...)`` string.

    Plotly lets ribbons be semi-transparent only through ``rgba`` colors, so the bucket
    colors (written as hex above) are converted when ribbons are colored.

    Args:
        h: Hex color such as ``"#2f80ed"`` (the leading ``#`` is optional).
        a: Opacity from 0 (invisible) to 1 (solid).

    Returns:
        A string such as ``"rgba(47,128,237,0.55)"``.
    """
    h = h.lstrip("#")                                     # remove the leading '#'
    # int(x, 16) reads a two-digit hexadecimal number: "2f" -> 47
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def ribbon_widths(counts: Sequence[float], mode: str) -> np.ndarray:
    """Turn real company counts into ribbon widths (see the SCALE setting and ``MIN_WIDTH_SHARE``).

    The transform compresses the range so one giant flow (tens of thousands of companies)
    does not dwarf the small ones. Every width is then lifted to at least
    ``MIN_WIDTH_SHARE`` times the widest width so tiny ribbons stay visible.

    Args:
        counts: Sequence of real company counts, one per ribbon.
        mode: ``"log"``, ``"sqrt"`` or ``"none"`` (the SCALE setting).

    Returns:
        A numpy array of widths (arbitrary units; plotly rescales them to pixels).
    """
    c = np.asarray(counts, dtype=float)                   # make sure we have a float array
    if mode == "log":
        w = np.log1p(c)                                   # log(1 + count): safe for count = 0
    elif mode == "sqrt":
        w = np.sqrt(c)
    else:
        w = c.copy()                                      # "none": true proportions
    # np.maximum keeps each element at least MIN_WIDTH_SHARE of the biggest one.
    return np.maximum(w, MIN_WIDTH_SHARE * w.max())


def step5_build_nodes_and_links(ctx: Context) -> None:
    """STEP 5: BUILD NODES AND LINKS.

    Sankey vocabulary used from here on:
    node = a coloured BOX (for example "Lead, Jan 2026, 285 companies")
    link = a RIBBON between two boxes (for example "Lead in Jan -> Lead in Feb, 90 companies")
    This step (1) creates the boxes, (2) creates the ribbons from the snapshot table,
    (3) lays the boxes out in horizontal stage bands, and (4) adds a few invisible helper
    items that make Plotly behave (explained where they are created).

    Args:
        ctx: The shared Context (see context.py). The step reads what earlier steps stored in it and
            adds its own results.
    """
    # --- values produced by earlier steps ---
    cfg = ctx.cfg
    (
        K, NONE, month_ends, n_pre, paths, pre_mask, snap,
    ) = (
        ctx.K, ctx.NONE, ctx.month_ends, ctx.n_pre, ctx.paths, ctx.pre_mask, ctx.snap,
    )

    # Sankey vocabulary used from here on:
    #   node = a coloured BOX (for example "Lead, Jan 2026, 285 companies")
    #   link = a RIBBON between two boxes (for example "Lead in Jan -> Lead in Feb, 90 companies")
    # This step (1) creates the boxes, (2) creates the ribbons from the snapshot table,
    # (3) lays the boxes out in horizontal stage bands, and (4) adds a few invisible helper
    # items that make Plotly behave (explained where they are created).
    print(f"[5/7] Building Sankey (width scaling = {cfg.scale}) ...")
    MARGIN_T, MARGIN_B = 170, 45   # pixels of blank space above the chart (month headers live here) / below it (month names live here)
    if MARKED_DATES:
        MARGIN_B = 120             # room for the notes written under the month names
    HEADER_GAP_PX = 60          # space between the month headers and the top of the chart
    EDGE_PAD_PX = 12            # space above the top band and below the bottom band
    PAD_PX = 14                 # plotly's own spacing between boxes (needed for its size math)

    OFF = 1 if n_pre else 0     # one extra column on the left for the Pre bucket
    # NCOLS = number of real columns: [the Pre column, if any] + one per month.
    NCOLS = K + OFF
    NTOT = NCOLS + 1            # plus an empty spacer column on the right, so the last labels have room
    # If the columns would be narrower than MIN_COL_PX the chart gets a fixed pixel width
    # (and scrolls sideways); otherwise it stretches to the window (CHART_W = None).
    CHART_W = None if NTOT * MIN_COL_PX <= 1500 else NTOT * MIN_COL_PX
    # Horizontal position of each column as a fraction (0 = far left, 1 = far right).
    xs_col = np.linspace(0.02, 0.98, NTOT)

    # node ids: one node per (month column k, stage band lvl)
    # Bookkeeping for the boxes. All lists are indexed by the box number (0, 1, 2 ...):
    #   node_id[key]      key -> box number. key is (month k, level) or ("pre",) / ("dummyA",) ...
    #   node_labels[n]    the text printed next to the box
    #   node_colors[n]    the box color
    #   node_col[n]       which column the box is in (0 = leftmost)
    #   node_order[n]     legacy sort key (kept for reference; the band layout does not use it)
    node_id, node_labels, node_colors, node_col, node_order = {}, [], [], [], []


    def add_node(key: tuple, label: str, color: str, col: int, order: int) -> None:
        """Register one Sankey box and return nothing (it is stored in the lists above).

        Args:
            key: Lookup key used later, e.g. ``(k, lvl)`` for "month k, stage level lvl",
                or a string tuple such as ``("pre",)`` for the special boxes.
            label: Text shown next to the box (may be empty).
            color: Box color (hex or rgba string).
            col: Column number the box belongs to (0 = leftmost column).
            order: Sort key kept for reference; the band layout does not use it.
        """
        node_id[key] = len(node_labels)       # the new box gets the next free number
        node_labels.append(label)
        node_colors.append(color)
        node_col.append(col)
        node_order.append(order)


    # --- "ever been in this stage" counts -------------------------------------------------
    # Every box label shows two numbers:  "Lead 287" = companies IN the stage at that month end,
    # and, on the next line, "(300)" = companies that have EVER been in that stage up to and
    # including that month (so it never goes down from one month to the next, and it is never
    # smaller than the first number). It counts a company even if it only passed through the
    # stage between two month ends, because it is based on each company's journey (step 3),
    # not on the month-end snapshots.
    #   ever_diff[k, lvl]  = number of companies whose FIRST visit to stage lvl happens in month k
    #   ever_in[k, lvl]    = running total of ever_diff up to month k = the number in brackets
    # ever_first[r] = for company number r, a list of 6 numbers: the first month column in which
    # it was in each stage (-1 = never). The popup uses it to list the companies that have "ever
    # been in" a stage: a company counts for (stage S, month k) when ever_first[r][S] is between
    # 0 and k.
    ever_first = []
    ever_diff = np.zeros((K + 1, 6), dtype=int)
    # entry_days[r] = for company number r, every moment it ENTERED a stage, as whole days since
    # 1970-01-01: [stage, day, stage, day, ...]. The popup uses it for the red "new this month"
    # asterisk and for sorting by "Date entered stage".
    entry_days = []
    _epoch = pd.Timestamp("1970-01-01")                       # day 0 for those day numbers
    # via[r] = for company number r, the stages it only passed THROUGH inside a month (it entered the stage and moved
    # on again before that month ended), as [month column, stage, month column, stage, ...] in order. The month-end
    # snapshots never show them, so a company that went Lead, MQL, SQL and Opp inside one month would look as if it
    # jumped from Lead to Opp. The page adds these stages to the highlight and to the path text.
    via = []
    _chart_start = month_ends[0].replace(day=1).normalize()   # the first day of the first month; earlier stages belong to the Pre bucket
    for _c0, _times, _lvls in paths:
        first_seen = {}                                       # level -> earliest moment this company was in it
        for _t, _lv in zip(_times, _lvls):
            if _lv not in first_seen or _t < first_seen[_lv]:
                first_seen[_lv] = _t
        _first_k = [-1] * 6                                   # first month column per stage (-1 = never)
        for _lv, _t in first_seen.items():
            _k0 = bisect_left(month_ends, _t)                 # first month whose end is on/after that moment
            if _k0 < K:
                ever_diff[_k0, _lv] += 1
                _first_k[_lv] = _k0
        ever_first.append(_first_k)
        # A company ENTERS a stage each time its path moves to a different stage. Its first stage
        # counts as entered on the day the company was created.
        _entries = []
        _previous = None
        for _t, _lv in zip(_times, _lvls):
            if _lv != _previous:
                _entries += [_lv, (_t.normalize() - _epoch).days]
            _previous = _lv
        entry_days.append(_entries)
        # The stages this company passed through: every point of its journey that is followed by another point in the
        # SAME month column. (The last point of a month is the month-end stage itself.) The made-up first point of a
        # company created above the bottom stage is not a real stage and is left out, and so is anything from before
        # the chart began.
        _cols = [bisect_left(month_ends, _t) for _t in _times]     # the month column of each point
        _stops = []
        for _p in range(len(_times) - 1):
            if _p == 0 and _times[0] == _times[1]:
                continue                                        # the made-up first point
            if _times[_p] >= _chart_start and _cols[_p] < K and _cols[_p] == _cols[_p + 1]:
                _stops += [_cols[_p], _lvls[_p]]
        via.append(_stops)
    # The first and last day of every month column, as days since 1970-01-01. The popup needs them
    # to tell whether a company entered a stage DURING that month.
    month_end_days = [(t.normalize() - _epoch).days for t in month_ends]
    month_start_days = [(t.replace(day=1).normalize() - _epoch).days for t in month_ends]
    ever_in = np.cumsum(ever_diff[:K], axis=0)                # add up month by month (the extra last row is unused)

    # The Pre bucket box (far left column) - only when there are Pre companies.
    if OFF:
        add_node(("pre",), f"{cfg.pre_name}  {n_pre:,}", PRE_BUCKET_COLOR, 0, 5)
    # One box per (month, stage) that has at least one company in it.
    for k in range(K):
        for lvl in range(6):
            n_here = int((snap[:, k] == lvl).sum())           # how many companies are in this stage this month
            if n_here == 0:
                continue                       # no box at all for an empty stage
            # label: "Lead  287" on the first line, "(300)" = ever been in this stage on the second
            add_node((k, lvl), f"{LABELS[lvl]}  {n_here:,}<br>({int(ever_in[k, lvl]):,})",
                     BAND_COLORS[lvl], k + OFF, 10 - lvl)          # order: Customer top ... Subscriber bottom

    # --- the ribbons ---------------------------------------------------------------------
    # Parallel lists describing every ribbon: where it starts (src), where it ends (dst), the
    # REAL number of companies (real), its color and a short kind ("stayed", "moved up" ...).
    src, dst, real, colors, link_kind = [], [], [], [], []
    if OFF:
        # Ribbons from the Pre box into the stage each Pre company held at the end of the first month.
        pre_levels, pre_counts = np.unique(snap[pre_mask, 0], return_counts=True)
        for lvl, cnt in zip(pre_levels.tolist(), pre_counts.tolist()):
            src.append(node_id[("pre",)])
            dst.append(node_id[(0, lvl)])
            real.append(cnt)
            colors.append("rgba(52,73,94,0.35)")
            link_kind.append(f"from {cfg.pre_name}")
    # Ribbons between each pair of neighbouring months.
    for k in range(K - 1):
        # companies that exist in BOTH month k and month k+1
        both = (snap[:, k] != NONE) & (snap[:, k + 1] != NONE)
        # count companies per (stage in month k, stage in month k+1) pair
        pair_counts = Counter(zip(snap[both, k].tolist(), snap[both, k + 1].tolist()))
        # biggest flows first (ties broken by the stage pair) so the output is deterministic
        for (a_, b_), cnt in sorted(pair_counts.items(), key=lambda kv: (-kv[1], kv[0])):
            src.append(node_id[(k, a_)])
            dst.append(node_id[(k + 1, b_)])
            real.append(cnt)
            if a_ == b_:
                colors.append(STAYED_COLOR)
                link_kind.append("stayed")
            elif b_ > a_:
                # moved UP: tinted with the color of the stage it moved into
                colors.append(hex_to_rgba(BAND_COLORS[b_], 0.55))
                link_kind.append("moved up")
            else:
                colors.append(MOVED_DOWN_COLOR)
                link_kind.append("moved down")

    # widths[j] = the drawn width of ribbon j (log/sqrt-compressed real count).
    widths = ribbon_widths(real, cfg.scale)

    # Plotly decides each node's column from the links, so a box with no incoming ribbon would
    # drift left. Invisible hair-thin links keep every box in its own month column.
    # (Plotly places a box in column "number of ribbons you must follow from the left". A box
    # nobody flows into would count as column 0. The 1e-4 wide transparent ribbon below gives
    # it an incoming link from the previous month so it stays in the right column.)
    has_incoming = set(dst)                                   # boxes that already have a real incoming ribbon
    for k in range(0 if OFF else 1, K):
        # boxes in the previous column (the Pre box when k == 0 and there is a Pre column)
        prev = ([node_id[("pre",)]] if k == 0
                else [node_id[(k - 1, lvl)] for lvl in range(6) if (k - 1, lvl) in node_id])
        if not prev:                          # nothing in the month before: this is the first column
            continue
        for lvl in range(6):
            if (k, lvl) in node_id and node_id[(k, lvl)] not in has_incoming:
                src.append(prev[0])
                dst.append(node_id[(k, lvl)])
                real.append(0)
                colors.append("rgba(0,0,0,0)")
                link_kind.append("placeholder")
                widths = np.append(widths, 1e-4)

    # --- layout: one horizontal band per stage, the same band in every month ---------------
    # THE IDEA: every stage (Subscriber, Lead, ...) owns one horizontal band across all months.
    # Inside a band all boxes of that stage sit on the same bottom edge. The tallest box of a
    # stage sets the band height, and the bands are stacked with BAND_GAP_PX between them.
    # So a Lead box can never be level with a Subscriber box of another month.
    n_nodes = len(node_labels)                                # number of boxes so far (before helper boxes)
    # inflow / outflow = total ribbon width entering / leaving each box.
    inflow = np.zeros(n_nodes)
    outflow = np.zeros(n_nodes)
    for j in range(len(src)):
        outflow[src[j]] += widths[j]
        inflow[dst[j]] += widths[j]
    # Plotly draws a box as tall as the larger of its inflow and outflow.
    val = np.maximum(inflow, outflow)
    node_level = {idx: key[1] for key, idx in node_id.items() if len(key) == 2}   # month boxes only

    # ky_t = pixels per unit of value, chosen so the single tallest month box is BOX_MAX_PX tall.
    ky_t = BOX_MAX_PX / max(float(val[x]) for x in node_level)      # pixels per unit of value
    # band_h[level] = height of that stage's band = height of its tallest box.
    band_h = {}
    for x, lvl in node_level.items():
        band_h[lvl] = max(band_h.get(lvl, 0.0), float(val[x]) * ky_t)
    # Stack the bands from the top (highest stage) to the bottom (Subscriber).
    band_top, band_bottom = {}, {}
    cursor = float(EDGE_PAD_PX)                               # y position (pixels from the top) of the next band
    for lvl in sorted(band_h, reverse=True):                         # top band first
        band_top[lvl] = cursor
        band_bottom[lvl] = cursor + band_h[lvl]
        cursor += band_h[lvl] + BAND_GAP_PX
    H_s = cursor - BAND_GAP_PX + EDGE_PAD_PX                         # height of the sankey in pixels

    # col_n[c] = number of boxes in column c; col_S[c] = sum of their values.
    col_n = Counter(node_col)
    col_S = defaultdict(float)
    for x in range(n_nodes):
        col_S[node_col[x]] += float(val[x])
    # plotly shrinks the boxes until its tallest month fills the chart. Our bands need more room
    # than that, so two invisible boxes (first column and the spacer column) make plotly use our pixel scale.
    #
    # BACKGROUND: Plotly sizes the boxes itself: it finds the column with the largest total
    # value and scales EVERYTHING so that column exactly fills the chart height:
    #       plotly_scale = min over columns of (height - 14 * (boxes_in_column - 1)) / column_total
    # Our banded layout needs more total height than that, so left alone Plotly would draw the
    # boxes too big and they would overlap. The trick: make a column look bigger to Plotly by
    # adding an INVISIBLE box with a carefully chosen value D. Then Plotly's scale becomes
    # exactly ky_t pixels per unit and every box has the planned height.
    # First make sure the chart is tall enough for every real column at our scale.
    H_s = max(H_s, max(ky_t * col_S[c] + PAD_PX * col_n[c] for c in col_n) + 1)
    use_dummy = NCOLS >= 2                                    # (a single column needs no trick)
    D = 0.0
    if use_dummy:
        # D = the value the invisible box needs so that Plotly's scale equals ky_t exactly.
        D = max(0.0, min((H_s - PAD_PX * col_n[0]) / ky_t - col_S[0], H_s / ky_t))
        n_real_nodes, n_real_links = n_nodes, len(src)        # remember how many are REAL (before helpers)
        add_node(("dummyA",), "", "rgba(0,0,0,0)", 0, 0)
        add_node(("dummyB",), "", "rgba(0,0,0,0)", NCOLS, 0)         # the spacer column
        # An invisible ribbon of width D from helper A (first column) to helper B (spacer column).
        src.append(node_id[("dummyA",)])
        dst.append(node_id[("dummyB",)])
        real.append(0)
        colors.append("rgba(0,0,0,0)")
        link_kind.append("placeholder")
        widths = np.append(widths, D)
        # a hair-thin link from each box in the last month keeps it out of the spacer column
        # (Plotly would otherwise push every box with NO outgoing ribbon - all the boxes of the
        # last month - into the rightmost column, which would then be the spacer column.)
        for x in range(n_real_nodes):
            if node_col[x] == NCOLS - 1:
                src.append(x)
                dst.append(node_id[("dummyB",)])
                real.append(0)
                colors.append("rgba(0,0,0,0)")
                link_kind.append("placeholder")
                widths = np.append(widths, 1e-4)
        n_nodes = len(node_labels)                            # now includes the two helper boxes
    else:
        n_real_nodes, n_real_links = n_nodes, len(src)

    # Overall figure geometry (pixels). P_H = the plot area height, CHART_H adds the margins.
    P_H = int(np.ceil(H_s + HEADER_GAP_PX))                          # plot area height
    CHART_H = P_H + MARGIN_T + MARGIN_B
    # Plotly wants the sankey's height as a FRACTION of the plot area (0..1).
    DOMAIN_TOP = H_s / P_H                                           # sankey fills the lower part

    # Horizontal position of every box = the position of its column.
    node_x = [float(xs_col[node_col[x]]) for x in range(n_nodes)]
    # Vertical position: Plotly wants the CENTER of each box (pixels from the top). The
    # default centre is the middle of the chart (used by the invisible helper boxes).
    center_px = [H_s / 2] * n_nodes
    for x, lvl in node_level.items():                        # every box sits on the bottom edge of its band
        # centre = bottom edge of the band minus half the box's own height
        center_px[x] = band_bottom[lvl] - float(val[x]) * ky_t / 2
    if OFF:                                  # the Pre box may overlap: center it on where its ribbons go
        pre_i = node_id[("pre",)]
        w_sum = c_sum = 0.0                  # weighted average of the target bands' middles
        for j in range(n_real_links):
            if src[j] == pre_i and dst[j] in node_level:
                _lv = node_level[dst[j]]
                w_sum += float(widths[j])
                c_sum += float(widths[j]) * (band_top[_lv] + band_bottom[_lv]) / 2
        if w_sum:
            center_px[pre_i] = c_sum / w_sum
    # Convert pixels to the 0..1 fractions Plotly expects (clamped just inside the edges).
    node_y = [min(max(c / H_s, 0.001), 0.999) for c in center_px]
    print(f"      Layout: {len(band_h)} stage bands, chart height {CHART_H:,}px (the chart box scrolls up and down)")

    print(f"      {n_nodes:,} nodes, {len(src):,} ribbons; "
          f"real counts {min(r for r in real if r):,} to {max(real):,}")
    # The tooltip text of each ribbon (shown when you hover it). Placeholders get none.
    hover = [f"{link_kind[j]}: {real[j]:,} companies" if link_kind[j] != "placeholder" else ""
             for j in range(len(real))]

    # --- values handed to the later steps ---
    ctx.update(
        CHART_H=CHART_H, CHART_W=CHART_W, DOMAIN_TOP=DOMAIN_TOP,
        MARGIN_B=MARGIN_B, MARGIN_T=MARGIN_T, OFF=OFF,
        PAD_PX=PAD_PX, colors=colors, dst=dst,
        ever_first=ever_first, hover=hover, n_real_links=n_real_links,
        n_real_nodes=n_real_nodes, node_colors=node_colors, node_id=node_id,
        node_labels=node_labels, node_x=node_x, node_y=node_y,
        src=src, use_dummy=use_dummy, widths=widths,
        xs_col=xs_col, entry_days=entry_days, month_end_days=month_end_days, via=via,
        month_start_days=month_start_days,
    )


def step6_draw_chart(ctx: Context) -> None:
    """STEP 6: DRAW THE CHART.

    Hand everything built in step 5 to Plotly. arrangement="fixed" tells Plotly to use OUR
    x/y positions for the boxes instead of choosing its own.

    Args:
        ctx: The shared Context (see context.py). The step reads what earlier steps stored in it and
            adds its own results.
    """
    # --- values produced by earlier steps ---
    cfg = ctx.cfg
    (
        CHART_H, CHART_W, DOMAIN_TOP, K, MARGIN_B, MARGIN_T, NONE, OFF, PAD_PX, col_labels, colors,
        dst, hover, n_pre, node_colors, node_labels, node_x, node_y, paths, pre_mask, snap, src,
        widths, xs_col, start,
    ) = (
        ctx.CHART_H, ctx.CHART_W, ctx.DOMAIN_TOP, ctx.K, ctx.MARGIN_B, ctx.MARGIN_T, ctx.NONE,
        ctx.OFF, ctx.PAD_PX, ctx.col_labels, ctx.colors, ctx.dst, ctx.hover, ctx.n_pre,
        ctx.node_colors, ctx.node_labels, ctx.node_x, ctx.node_y, ctx.paths, ctx.pre_mask, ctx.snap,
        ctx.src, ctx.widths, ctx.xs_col, ctx.start,
    )

    # Hand everything built in step 5 to Plotly. arrangement="fixed" tells Plotly to use OUR
    # x/y positions for the boxes instead of choosing its own.
    print("[6/7] Drawing ...")
    # Optional hover text for each stage box (STAGE_HOVER in settings.py), wrapped with <br> so Plotly shows several short lines.
    # Boxes that are not month boxes (the Pre box, helper boxes) get no extra text.
    import textwrap
    from .settings import STAGE_HOVER
    node_tip = [""] * len(node_labels)
    for key_, idx_ in ctx.node_id.items():
        if len(key_) == 2 and isinstance(key_[0], int) and 0 <= key_[1] < len(STAGE_HOVER) and idx_ < len(node_tip):
            node_tip[idx_] = "<br>".join(textwrap.wrap(STAGE_HOVER[key_[1]], 55))
    fig = go.Figure(go.Sankey(
        arrangement="fixed",
        # The boxes: label text, fill color and our own x/y position for each one.
        node=dict(label=node_labels, color=node_colors, x=node_x, y=node_y,
                  pad=PAD_PX, thickness=BOX_WIDTH_PX,
                  line=dict(color="#222", width=0.5),
                  customdata=node_tip,
                  hovertemplate="%{label}<br>%{customdata}<extra></extra>" if any(node_tip) else "%{label}<extra></extra>"),
        # The part of the figure the chart may use (the top is left free for the month headers).
        domain=dict(x=[0, 1], y=[0, DOMAIN_TOP]),
        # The ribbons: from box number src to box number dst; the drawn width is the scaled value,
        # and the tooltip text (the real company counts) travels in customdata.
        link=dict(source=src, target=dst, value=[float(w) for w in widths],
                  color=colors, customdata=hover,
                  hovertemplate="%{customdata}<extra></extra>"),
    ))
    # Title, size and margins. The month headers (annotations) are added below and sit in
    # the top margin, above the sankey.
    fig.update_layout(
        title=dict(text=(f"Company lifecycle flow by month ({len(paths):,} companies)"
                         f"<br><sup>Grey = stayed, colored = moved up, dark grey = moved down.</sup>"),
                   x=0.5, xanchor="center", y=0.985, yanchor="top"),
        font=dict(size=11), height=CHART_H, margin=dict(l=20, r=20, t=MARGIN_T, b=MARGIN_B),
        plot_bgcolor="white", width=CHART_W,
    )
    # Every column label below is centred over its column (xanchor="center"). Plotly's default, "auto", would
    # left-align the labels in the left third of the chart and right-align those in the right third, so they sat
    # off their column and off the frozen month names.
    # Header text above the Pre column (company count + "created before <start>"). The bucket's name above it is
    # a frozen row that the page adds, so it is kept in the annotation's "name" (the saved picture puts it back).
    if OFF:
        fig.add_annotation(x=float(xs_col[0]), y=1.0, xref="paper", yref="paper", xanchor="center", yanchor="bottom",
                           showarrow=False, align="center",
                           name=cfg.pre_name,
                           text=f"{n_pre:,} companies<br>created before<br>{start:%b %Y}")
        # the same name again under the chart (name only, no counts)
        fig.add_annotation(x=float(xs_col[0]), y=0, xref="paper", yref="paper", xanchor="center", yanchor="top", yshift=-8,
                           showarrow=False, align="center", text=f"<b>{cfg.pre_name}</b>")
        # a faint dotted vertical guide line through the Pre column
        fig.add_shape(type="line", xref="paper", yref="paper", layer="below",
                      x0=float(xs_col[0]), x1=float(xs_col[0]), y0=0, y1=0.97,
                      line=dict(color="#c9c9c9", width=1, dash="dot"))
    # Header above every month: new companies, carried-over companies, total. The month name above these counts
    # is a frozen row that the page adds (see placeMonthRow in the page code), so it is not part of this text; it
    # is kept in the annotation's "name" so the saved picture can put it back. The month name is also written at
    # the bottom of the chart so it can be read next to the lowest boxes.
    for k in range(K):
        exists_now = snap[:, k] != NONE                       # companies that exist at the end of month k
        # companies that existed the month before (for the first month: the Pre companies)
        existed_before = (snap[:, k - 1] != NONE) if k else pre_mask
        total = int(exists_now.sum())
        n_new = int((exists_now & ~existed_before).sum())     # exist now but did not before = created this month
        fig.add_annotation(x=float(xs_col[k + OFF]), y=1.0, xref="paper", yref="paper", xanchor="center", yanchor="bottom",
                           showarrow=False, align="center",
                           name=col_labels[k],
                           text=f"+{n_new:,} new<br>{total - n_new:,} {CARRIED_LABEL}<br>{total:,} total")
        # the month name again at the bottom of the chart (name only, without the counts above)
        fig.add_annotation(x=float(xs_col[k + OFF]), y=0, xref="paper", yref="paper", xanchor="center", yanchor="top", yshift=-8,
                           showarrow=False, align="center",
                           text=f"<b>{col_labels[k]}</b>" + "".join(
                               f'<br><span style="color:#B5460F">{d.month}/{d.day}: {txt}</span>'
                               for d, txt in MARKED_DATES if d.strftime("%b %Y") == col_labels[k]))
        # dotted vertical guide line through the month column
        fig.add_shape(type="line", xref="paper", yref="paper", layer="below",
                      x0=float(xs_col[k + OFF]), x1=float(xs_col[k + OFF]), y0=0, y1=0.97,
                      line=dict(color="#c9c9c9", width=1, dash="dot"))

    # --- values handed to the later steps ---
    ctx.update(
        fig=fig,
    )

