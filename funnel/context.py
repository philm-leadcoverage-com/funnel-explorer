"""The values the steps hand to each other."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .settings import RunSettings


@dataclass
class Context:
    """The shared values of one run.

    ``cfg`` holds the settings of the run. Every other field starts empty and is filled in by the step named in
    the comment above it; a later step reads it. ``update`` refuses a name that is not a field, so a typo in a step
    fails at once instead of quietly creating a new value.
    """

    cfg: RunSettings

    # produced by write_assets_folder
    banner_text: Any = None
    css_v: Any = None
    js_v: Any = None
    out_dir: Any = None
    plotly_v: Any = None

    # produced by step2_filter_companies
    all_idx: Any = None
    keep: Any = None
    n_excluded: Any = None
    n_pre: Any = None
    pre_keep: Any = None
    skip_reason: Any = None

    # produced by step3_build_stage_paths
    paths: Any = None
    pre_mask: Any = None

    # produced by step4_snapshot_each_month
    K: Any = None
    NONE: Any = None
    col_labels: Any = None
    month_ends: Any = None
    snap: Any = None

    # produced by step0_prepare_settings
    BUCKET_KEYS: Any = None
    OTHER_LEVEL: Any = None
    PRE_MIN: Any = None
    SQL_LEVEL: Any = None
    SUB_LEVEL: Any = None
    VOCAB: Any = None

    # produced by step1_load_and_check_export
    BACKFILL: Any = None
    LV: Any = None
    STAGE_COL: Any = None
    STAGE_LEVEL: Any = None
    copy_names: Any = None
    created_list: Any = None
    cur_list: Any = None
    df: Any = None
    labels: Any = None
    stage_dates: Any = None
    stage_text_norm: Any = None
    start: Any = None

    # produced by step5_build_nodes_and_links
    CHART_H: Any = None
    CHART_W: Any = None
    DOMAIN_TOP: Any = None
    MARGIN_B: Any = None
    MARGIN_T: Any = None
    OFF: Any = None
    PAD_PX: Any = None
    colors: Any = None
    dst: Any = None
    entry_days: Any = None
    ever_first: Any = None
    hover: Any = None
    month_end_days: Any = None
    month_start_days: Any = None
    n_real_links: Any = None
    n_real_nodes: Any = None
    node_colors: Any = None
    node_id: Any = None
    node_labels: Any = None
    node_x: Any = None
    node_y: Any = None
    src: Any = None
    use_dummy: Any = None
    via: Any = None
    widths: Any = None
    xs_col: Any = None

    # produced by step6_draw_chart
    fig: Any = None

    # produced by step7_build_search_index_and_page_data
    data_json: Any = None
    plot_html: Any = None

    def update(self, **values: Any) -> None:
        """Store several values at once (each name must be a field above)."""
        for name, value in values.items():
            if not hasattr(self, name):
                raise AttributeError(f"Context has no field {name!r}")
            setattr(self, name, value)
