"""One data row per company for the page's search box, popups and buttons: the first part of step 7."""
from __future__ import annotations

import base64
import json
import re
import urllib.request
from collections import Counter

import numpy as np
import pandas as pd

from .context import Context
from .journeys import is_success_journey
from .settings import (
    AGENCY_LOGO_URL,
    AGENCY_SITE_URL,
    COUNT_BACKFILL_AS_MOVE,
    DETAIL_LINES,
    HIGHLIGHT_COLOR,
    HUBSPOT_APP_URL,
    LABELS,
    LOGO_URL_COLUMN,
    PICTURE_SCALE,
)

# "0", "0.0", "0.00", "-0" ... : a number that is zero
_ZERO_TEXT = re.compile(r"[+-]?0+(?:[.,]0*)?")


def _format_number(value: float) -> str:
    """One number as display text: "" when zero, no trailing ".0", thousands separators."""
    if float(value) == 0:
        return ""                                       # zero: blank
    if float(value).is_integer():
        return f"{int(value):,}"
    text = f"{value:,.2f}"
    return "" if _ZERO_TEXT.fullmatch(text) else text   # 0.001 would print as 0.00: blank too


def _format_text(value: object) -> str:
    """One text value as display text: "" when empty, "nan", "null" or a number that is zero."""
    text = str(value).strip()
    blank = text.lower() in ("", "nan", "null") or _ZERO_TEXT.fullmatch(text) is not None
    return "" if blank else text                        # a number stored as text gets the same zero rule


def clean_detail_column(series: pd.Series) -> list[str]:
    """Turn one export column into display text, with "" for every blank value.

    Blank means empty, only spaces, missing, the text "null" / "nan", or the number ZERO
    (0, 0.0, 0.00): zero is treated as blank for every number property and is removed from the
    data. Numbers are written without a trailing ".0" and with thousands separators (2500.0 ->
    "2,500", 26.0 -> "26", 1234.5 -> "1,234.50"). Text and dates are kept exactly as they appear
    in the export.

    Most columns repeat the same few values thousands of times (an owner, an industry, a source), so each
    DISTINCT value is cleaned once and the answer is looked up for every row.

    Args:
        series: One column of the export (a pandas Series).

    Returns:
        A list of strings, one per row, "" where the value is blank.
    """
    clean = _format_number if pd.api.types.is_numeric_dtype(series) else _format_text
    codes, uniques = pd.factorize(series)                 # a number per row; -1 = missing
    shown = [clean(v) for v in uniques.tolist()] + [""]   # the last entry is what code -1 (missing) picks
    return [shown[code] for code in codes.tolist()]


def load_agency_logo(url: str) -> str:
    """Download the agency logo once and return it as a data address the page can show.

    A data address (``data:image/png;base64,...``) carries the picture inside the page itself, so
    it displays without internet, and the browser may copy it into the saved picture (a logo
    loaded from another website cannot be copied). If the download fails for any reason the
    plain web address is returned instead, and the page loads the logo from the web.

    Args:
        url: The address of the logo image ("" for none).

    Returns:
        A data address, the original web address (download failed), or "" (no logo wanted).
    """
    if not url.strip():
        return ""                                         # no logo wanted
    try:
        # Some servers refuse the default Python user agent, so present a normal browser name.
        request = urllib.request.Request(url.strip(), headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=15) as response:
            kind = response.headers.get_content_type()    # e.g. "image/png"
            body = response.read(2_000_001)               # read one byte more than the limit so "too big" can be detected
        # Accept only a real image of a sensible size (2 MB at most).
        if not kind.startswith("image/") or len(body) > 2_000_000:
            raise ValueError(f"not a usable image ({kind}, {len(body):,} bytes)")
        print(f"      Agency logo: downloaded and built into the page ({len(body) // 1024:,} KB)")
        return f"data:{kind};base64," + base64.b64encode(body).decode("ascii")
    except Exception as err:  # noqa: BLE001 - offline, blocked, bad certificate ... any failure means "load it from the web"
        print(f"      Agency logo: could not download it ({type(err).__name__}: {err}).")
        print("      The page will load it from the web instead; the saved picture will leave it out.")
        return url.strip()



def step7_build_search_index_and_page_data(ctx: Context) -> None:
    """STEP 7: SEARCH INDEX, INTERACTIVE PAGE, PASSWORD.

    Goal of this step: (a) build one compact data row per company for the page's search box,
    popups and buttons, (b) put chart + data + JavaScript into one HTML page, (c) encrypt the
    page with the password and (d) write index.html.

    Args:
        ctx: The shared Context (see context.py). The step reads what earlier steps stored in it and
            adds its own results.
    """
    # --- values produced by earlier steps ---
    cfg = ctx.cfg
    (
        BACKFILL, BUCKET_KEYS, NONE, OFF, STAGE_COL, all_idx, col_labels, colors, created_list,
        cur_list, df, ever_first, fig, n_real_links, n_real_nodes, node_id, paths, pre_keep,
        skip_reason, snap, src, stage_text_norm, use_dummy, entry_days, month_end_days,
        month_start_days, via, xs_col,
    ) = (
        ctx.BACKFILL, ctx.BUCKET_KEYS, ctx.NONE, ctx.OFF, ctx.STAGE_COL, ctx.all_idx,
        ctx.col_labels, ctx.colors, ctx.created_list, ctx.cur_list, ctx.df, ctx.ever_first, ctx.fig,
        ctx.n_real_links, ctx.n_real_nodes, ctx.node_id, ctx.paths, ctx.pre_keep, ctx.skip_reason,
        ctx.snap, ctx.src, ctx.stage_text_norm, ctx.use_dummy, ctx.entry_days, ctx.month_end_days,
        ctx.month_start_days, ctx.via, ctx.xs_col,
    )

    print("[7/7] Building the search box and saving the page ...")
    # keep_row maps a CSV row number to its row in the charted table (snap / paths).
    keep_row = {i: r for r, i in enumerate(all_idx)}
    pre_set = set(pre_keep)                                   # CSV rows that belong to the Pre bucket
    # Plain Python lists of the columns shown in the page (fast to index; missing values -> "").
    domains_all = df["Company Domain Name"].fillna("").astype(str).tolist()
    # A company with no name (empty, only spaces, missing, or the text "null" / "nan" / "none")
    # is shown by its DOMAIN name instead, everywhere on the page (search, lists, popups and the
    # info line). A name that is present is kept exactly as it is. If the domain is blank too,
    # the page shows "(no name)".
    names_all = []
    n_name_from_domain = 0                                    # how many companies needed the replacement
    for _name_raw, _domain_raw in zip(df["Company name"].fillna("").astype(str).tolist(), domains_all):
        if _name_raw.strip() and _name_raw.strip().lower() not in ("null", "nan", "none"):
            names_all.append(_name_raw)                       # a real name: keep it unchanged
        else:
            names_all.append(_domain_raw.strip())             # no name: use the domain (may also be blank)
            n_name_from_domain += 1
    if n_name_from_domain:
        print(f"      {n_name_from_domain:,} companies have no name, so their domain name is shown instead")
    ids_all = df["Record ID"].astype(str).tolist()
    stage_all = df["Lifecycle Stage"].fillna("").astype(str).tolist()

    # --- extra details and logos for the selected-company panel ---------------------------
    # Lower-case header -> real header, so DETAIL_LINES works whatever capitals the export uses.
    _header_lookup = {str(_c).strip().lower(): _c for _c in df.columns}
    detail_labels = []      # the label of every detail field the export has (a field's number = its position here)
    detail_columns = []     # the matching column name in the CSV
    detail_groups = []      # one list of field numbers per group of DETAIL_LINES (the groups only set the order)
    detail_missing = []     # names listed in DETAIL_LINES that the export does not have
    for _line in DETAIL_LINES:
        _group = []
        for _wanted in _line:
            _col = _header_lookup.get(_wanted.strip().lower())
            if _col is None:
                detail_missing.append(_wanted)                # not in this export: skip it
                continue
            _group.append(len(detail_labels))
            detail_labels.append(_wanted)
            detail_columns.append(_col)
        if _group:
            detail_groups.append(_group)


    detail_values = [clean_detail_column(df[_c]) for _c in detail_columns]   # one list of display text per field
    # Shared text list: a value that appears 3 or more times (for example "CRM Setting" or
    # "Offline Sources") is written once and each row stores just its position, which keeps the
    # page small. Rarer values (dates, names) are stored as the text itself.
    _value_counts = Counter(v for _vals in detail_values for v in _vals if v)
    detail_strings = [v for v, n in _value_counts.items() if n >= 3]
    _string_index = {v: k for k, v in enumerate(detail_strings)}


    def details_for_row(i: int) -> list:
        """Return one company's non-blank details as a flat list [field number, value, ...].

        A value is either the TEXT itself or, for text that repeats a lot, a NUMBER that is its
        position in the shared text list (the page looks it up).

        Args:
            i: Row number in the CSV.
        """
        flat = []
        for fi, vals in enumerate(detail_values):
            v = vals[i]
            if v:
                flat.append(fi)
                flat.append(_string_index.get(v, v))
        return flat


    # Logos: keep only well-formed web addresses. The start of an address (for example
    # "https://na1.hubspot-logos.com/") is shared, so each row stores [position of that start, the rest].
    _logo_col = _header_lookup.get(LOGO_URL_COLUMN.strip().lower()) if LOGO_URL_COLUMN.strip() else None
    logo_all = df[_logo_col].fillna("").astype(str).tolist() if _logo_col is not None else []
    logo_prefixes = []                                        # the shared address starts
    _logo_prefix_index = {}


    def logo_token(raw: str) -> list | str:
        """Return a company's logo as [prefix number, rest of the address], or "" if it has none.

        Only addresses that start with http:// or https:// are kept.
        """
        url = raw.strip()
        if not url.lower().startswith(("http://", "https://")):
            return ""
        found = re.match(r"^(https?://[^/]+/)(.*)$", url)
        if not found:
            return [-1, url]                                  # unusual shape: keep the whole address
        prefix = found.group(1)
        if prefix not in _logo_prefix_index:
            _logo_prefix_index[prefix] = len(logo_prefixes)
            logo_prefixes.append(prefix)
        return [_logo_prefix_index[prefix], found.group(2)]


    # Tell the user what was found: how many of the wanted detail columns exist, and which do not.
    _n_wanted = sum(len(_l) for _l in DETAIL_LINES)
    print(f"      Details: {len(detail_labels)} of {_n_wanted} wanted columns are in the export")
    if detail_missing:
        print(f"      Not in this export (skipped): {', '.join(detail_missing)}")
    if LOGO_URL_COLUMN.strip():                           # logos were asked for
        if _logo_col is None:
            print(f"      Logos: no '{LOGO_URL_COLUMN}' column in the export, so no logos will be shown")
        else:
            print(f"      Logos: {sum(1 for _u in logo_all if logo_token(_u)):,} companies have a logo address")

    # "Date entered current stage": when each company reached the stage it is in now.
    stage_text_list = stage_text_norm.tolist()
    if "Date entered current stage" in df.columns:
        cur_stage_dates = pd.to_datetime(df["Date entered current stage"], errors="coerce").tolist()
    else:
        # fall back to the date column of each company's own current stage
        cur_stage_dates = []
        for _i in range(len(df)):
            _col = STAGE_COL.get(stage_text_list[_i])
            cur_stage_dates.append(pd.to_datetime(df[_col].iat[_i], errors="coerce") if _col else pd.NaT)

    # Constants for the "Random success" rule (see is_success_journey).
    MQL_LEVEL = BUCKET_KEYS.index("MQL")                      # level of the MQL bucket (2)
    SQL_LEVEL = BUCKET_KEYS.index("SQL")                      # level of the SQL bucket (3)
    OPP_LEVEL = BUCKET_KEYS.index("OPP")                      # level of the Opp bucket (4); Opp and above = "now a success"
    success_cutoff = pd.Timestamp(cfg.random_before)   # "Random success" only picks companies created before this date
    # A stage date at the HubSpot backfill minute is not a real move, unless COUNT_BACKFILL_AS_MOVE says so.
    success_backfill = None if COUNT_BACKFILL_AS_MOVE else BACKFILL
    n_success = 0                                             # how many companies match (printed below)

    # One row per company in the CSV (charted or not, so every company can be searched).
    # Row layout (the JavaScript below reads these by position):
    #   0 name   1 domain   2 Record ID   3 created (YYYY-MM-DD)   4 month-end stage string
    #   5 current stage text   6 "why not in chart" text (empty = charted)   7 1 if Pre bucket
    #   8 current-stage date   9 1 if that date is the backfill stamp   10 1 if "Random success"
    #   11 list of 6 numbers: first month column in which the company was in each stage (-1 = never);
    #      empty for companies that are not on the chart
    #   12 non-blank extra details as a flat list [field number, value, ...] (see details_for_row)
    #   13 the logo as [prefix number, rest of the address], or "" if there is none
    #   14 every stage entry as [stage, day, stage, day, ...] (days since 1970-01-01); empty for
    #      companies that are not on the chart (see entry_days in step 5)
    #   15 the level (0..5) of the stage the company is in NOW, or -1 when that stage is in no bucket
    #      (the popup's "Show only" check boxes: Now Opp, Now Cust ... Now Other)
    #   16 the stages the company only passed THROUGH inside a month, as [month column, stage, ...] in order;
    #      empty for most companies and for companies that are not on the chart (see via in step 5)
    # snap_strings[r]: one character per month for charted company r ("-" = did not exist yet, otherwise the level
    # 0..5), made for all companies at once from a small lookup table.
    snap_strings = ["".join(row) for row in np.array(list("-012345"))[snap - NONE].tolist()]
    rows = []
    for i in range(len(df)):                                  # one row per company, in CSV order
        created = pd.Timestamp(created_list[i])
        _csd = cur_stage_dates[i]                             # when it entered its current stage
        stage_since = "" if pd.isna(_csd) else f"{_csd:%Y-%m-%d}"
        # Flag a "date" that is really the HubSpot backfill stamp, so the page can say so.
        since_is_backfill = 1 if (BACKFILL is not None and not pd.isna(_csd) and _csd == BACKFILL) else 0
        is_success = 0                                        # becomes 1 below when it qualifies for "Random success"
        if i in keep_row:
            snap_str = snap_strings[keep_row[i]]
            status = ""
            # All the conditions: created early enough, NOW Opp or Customer, and a journey that STARTED below MQL and
            # PASSED THROUGH MQL and SQL one step at a time (see is_success_journey).
            _times, _levels = paths[keep_row[i]][1], paths[keep_row[i]][2]
            if (created < success_cutoff and cur_list[i] >= OPP_LEVEL
                    and is_success_journey(_times, _levels, MQL_LEVEL, SQL_LEVEL, success_backfill)):
                is_success = 1
                n_success += 1
        else:
            snap_str = ""                                     # not charted: no month-end path
            status = skip_reason.get(i, "Not in the chart")   # the reason shown in the page
        # Append the row in exactly the field order documented above (the page reads the fields by position).
        rows.append([names_all[i], domains_all[i], ids_all[i], f"{created:%Y-%m-%d}",
                     snap_str, stage_all[i], status, 1 if i in pre_set else 0,
                     stage_since, since_is_backfill, is_success,
                     ever_first[keep_row[i]] if i in keep_row else [],
                     details_for_row(i), logo_token(logo_all[i]) if logo_all else "",
                     entry_days[keep_row[i]] if i in keep_row else [], cur_list[i],
                     via[keep_row[i]] if i in keep_row else []])
    print(f"      {n_success:,} companies match the Random success button "
          f"(created before {cfg.random_before}, now {LABELS[OPP_LEVEL]} or {LABELS[OPP_LEVEL + 1]}, started below "
          f"{LABELS[MQL_LEVEL]}, and went {LABELS[MQL_LEVEL]} then {LABELS[SQL_LEVEL]} without skipping a step)")

    # Base address of a company record in HubSpot (the Record ID is appended in the page).
    # Empty string = names are not turned into links.
    _hs_base = (f"{HUBSPOT_APP_URL.rstrip('/')}/contacts/{cfg.portal_id.strip()}/record/0-2/"
                if cfg.portal_id.strip() else "")


    agency_logo_src = load_agency_logo(AGENCY_LOGO_URL)

    # Everything the page's JavaScript needs, packed into one dictionary (sent as JSON).
    page_data = {
        "months": list(col_labels),                                    # month names for the path text
        # the column names of the frozen row above the counts (the Pre bucket first), each with its place across the chart (0 to 1)
        "columns": ([[cfg.pre_name, float(xs_col[0])]] if OFF else [])
                   + [[col_labels[k], float(xs_col[k + OFF])] for k in range(len(col_labels))],
        "stages": LABELS,                                              # stage names for the path text and popups
        "preName": cfg.pre_name,
        "highlight": HIGHLIGHT_COLOR,
        # "<month>_<level>" -> Plotly box number: lets the page find a company's boxes
        "nodes": {f"{key[0]}_{key[1]}": idx for key, idx in node_id.items() if len(key) == 2},
        "linkColors": colors,                                          # original ribbon colors (restored on Clear)
        "pre": node_id[("pre",)] if OFF else -1,                       # box number of the Pre box (-1 = none)
        "hubspotBase": _hs_base,
        # first and last day of each month column (days since 1970-01-01), for the popup's "new this month" mark
        "monthStartDays": month_start_days,
        "monthEndDays": month_end_days,
        # the agency logo (a data address when it was downloaded), its link, and the picture size
        "agencyLogo": agency_logo_src,
        "agencyLogoEmbedded": agency_logo_src.startswith("data:"),
        "agencyLink": AGENCY_SITE_URL.strip(),
        "pictureScale": PICTURE_SCALE,
        # extra details: labels, which fields form a group (the groups only set the order), and the shared text list
        "detailLabels": detail_labels,
        "detailGroups": detail_groups,
        "strs": detail_strings,
        "logoPrefixes": logo_prefixes,
        # numbers of the invisible helper boxes / ribbons, which the page hides
        "dummyNodes": [n_real_nodes, n_real_nodes + 1] if use_dummy else [],
        "dummyLinks": list(range(n_real_links, len(src))) if use_dummy else [],
        "rows": rows,
    }
    # json.dumps writes the data as text. "</" is escaped so the text can never accidentally
    # close the <script> tag it is placed in.
    data_json = json.dumps(page_data).replace("</", "<\\/")

    # The chart itself as an HTML fragment: full_html=False (we supply the page around it),
    # include_plotlyjs=False because the Plotly library is written to assets/plotly.min.js and loaded by
    # the page (it is public code, so it does not need to be inside the encrypted blob).
    # config: "responsive" lets the chart resize with the window; "displayModeBar": False hides
    # Plotly's row of small tool icons (camera, link, selection, comment, home, logo) that would
    # otherwise float in the top right corner of the chart. Set it to True to bring them back.
    plot_html = fig.to_html(full_html=False, include_plotlyjs=False, div_id="sankey-plot",
                            config={"responsive": True, "displayModeBar": False})

    # --- values handed to the later steps ---
    ctx.update(
        data_json=data_json, plot_html=plot_html,
    )

