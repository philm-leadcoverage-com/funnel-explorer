"""The final HTML page: fills the template, encrypts it with the password and writes index.html."""
from __future__ import annotations

import base64
import hashlib
import html
import importlib
import os
import pathlib
import re
import secrets
import webbrowser
from datetime import datetime
from typing import Any

from .assets import ASSETS_FOLDER, minify_embedded, web_file
from .context import Context
from .settings import (
    CREATED_BY_EMAIL,
    CREATED_BY_NAME,
    PBKDF2_ITERATIONS,
    PICTURE_CREATED_BY,
)


def load_aesgcm() -> Any:
    """Load the AES-GCM encryption class from the ``cryptography`` package.

    The package is imported *by name* (``importlib.import_module``) instead of with a normal
    ``import`` line for two reasons: a missing package then produces a clear, friendly
    message with the exact command to run, and code editors do not underline a normal
    import in red when VS Code is pointed at a different Python than the one you run.

    Returns:
        The ``AESGCM`` class (``cryptography.hazmat.primitives.ciphers.aead.AESGCM``).

    Raises:
        SystemExit: if ``cryptography`` is not installed. The message says how to fix it.
    """
    try:
        return importlib.import_module("cryptography.hazmat.primitives.ciphers.aead").AESGCM
    except ImportError:
        raise SystemExit("The password feature needs the cryptography package. Run:  "
                         "python -m pip install cryptography   (then run this script again)") from None



def build_page_and_write_files(ctx: Context) -> None:
    """Fill in the page template, build the password screen, encrypt and write index.html.

    Replaces the placeholders in the HTML template, then (when PASSWORD is set) encrypts the whole
    page with AES-256-GCM and hides it inside the lock page, writes index.html into this run's folder (made by
    the previous step), optionally writes the PNG there too, and opens the result in the browser unless
    --no-open was given.

    Args:
        ctx: The shared Context (see context.py). The step reads what earlier steps stored in it and
            adds its own results.
    """
    # --- values produced by earlier steps ---
    cfg = ctx.cfg
    (
        CHART_W, banner_text, css_v, data_json, fig, js_v, n_excluded, out_dir, plot_html, plotly_v,
    ) = (
        ctx.CHART_W, ctx.banner_text, ctx.css_v, ctx.data_json, ctx.fig, ctx.js_v, ctx.n_excluded,
        ctx.out_dir, ctx.plot_html, ctx.plotly_v,
    )

    # wrap_style: a very wide chart gets a fixed pixel width, otherwise it fills the window.
    wrap_style = "width:100%" if CHART_W is None else f"width:{CHART_W}px"
    # The note under the credit line (empty when nothing is excluded, so the line disappears).
    excluded_text = f"{n_excluded:,} more in HubSpot excluded from this graph" if n_excluded else ""
    # The moment this script ran, in the computer's own time zone.
    _now = datetime.now().astimezone()
    _tz = _now.tzname() or ""
    if " " in _tz:
        _tz = "".join(w[0] for w in _tz.split())      # "Eastern Daylight Time" -> "EDT"
    created_at_text = f"{_now:%Y-%m-%d %H:%M} {_tz}".strip()
    # The HTML comments in the template are for you, not for the visitor: they are removed.
    page_template = re.sub(r"<!--.*?-->", "", web_file("page.html"), flags=re.DOTALL)
    # Replace every placeholder in the template. html.escape() makes the text safe inside HTML
    # (for example & < > and quotes), so a heading like  A & B  cannot break the page.
    inner_html = (page_template.replace("__HEADING__", html.escape(cfg.heading))          # page title and h1
                  .replace("__EMAIL__", html.escape(CREATED_BY_EMAIL, quote=True))         # mailto address in the credit line
                  .replace("__CREATED_BY__", html.escape(CREATED_BY_NAME))                 # name shown in the credit line
                  .replace("__CREATED_AT__", html.escape(created_at_text))                 # when this run happened
                  .replace("__PICTURE_CREDIT__",                                           # credit line inside saved pictures
                           html.escape(f"Created by {PICTURE_CREATED_BY} on {created_at_text}", quote=True))
                  .replace("__EXCLUDED__", html.escape(excluded_text))                     # "N more in HubSpot excluded ..." note
                  .replace("__CSS_V__", css_v).replace("__JS_V__", js_v).replace("__PLOTLY_V__", plotly_v)   # cache-busting codes
                  .replace("__WRAPSTYLE__", wrap_style).replace("__PLOT__", plot_html)     # chart width and the chart itself
                  .replace("__DATA__", data_json))                                         # the data, replaced last (it is big)

    # The password screen is public (anyone can open index.html), so its explanatory comments are
    # removed and its code and styles are minified (level 1 only: no renaming), and it gets the same
    # notice and robots directive as the other public files.
    lock_template = minify_embedded(
        web_file("lock.html").replace('content="noindex, nofollow, noarchive, nosnippet">',
                          'content="noindex, nofollow, noarchive, nosnippet, noai, noimageai">'),
        banner_text)

    # -----------------------------------------------------------------------------
    # ENCRYPT (when a password is set) AND WRITE THE FILE
    # -----------------------------------------------------------------------------
    if cfg.password:
        # The AES-GCM class from the "cryptography" package (the check at the top of the file
        # already made sure it is installed).
        AESGCM = load_aesgcm()
        # salt: random bytes mixed into the key derivation (so equal passwords give different keys).
        # iv: the "nonce" AES-GCM needs; must be 12 random bytes and never reused with the same key.
        salt, iv = secrets.token_bytes(16), secrets.token_bytes(12)
        # Password -> 32-byte key (PBKDF2-HMAC-SHA256, PBKDF2_ITERATIONS rounds).
        key = hashlib.pbkdf2_hmac("sha256", cfg.password.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=32)
        # blob = salt + iv + encrypted page (AES-GCM appends its authentication tag to the end).
        blob = salt + iv + AESGCM(key).encrypt(iv, inner_html.encode("utf-8"), None)
        # Put the Base64 text of the blob into the lock page.
        final_html = (lock_template.replace("__PAYLOAD__", base64.b64encode(blob).decode("ascii"))
                      .replace("__ITER__", str(PBKDF2_ITERATIONS)))
        print("      Page is password protected and encrypted")
    else:
        # No password: publish the page as it is (anyone with the file can read everything).
        final_html = inner_html
        print("      WARNING: no password set, the page is readable by anyone with the file")

    # Write index.html into this run's folder, next to its assets folder (utf-8 so accents in company names survive).
    out_html = os.path.join(out_dir, "index.html")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(final_html)
    print(f"      Saved {out_html}")
    print(f"      UPLOAD BOTH: index.html and the {ASSETS_FOLDER} folder from {out_dir} (the page shows a message if the folder is missing)")
    # Optional picture of the chart (needs the kaleido package; see the pip install guide).
    if cfg.save_png:
        try:
            out_png = os.path.join(out_dir, "company_lifecycle_sankey.png")
            # no box outlines in the PNG: the invisible helper boxes would otherwise show theirs
            fig.update_traces(node=dict(line=dict(width=0, color="rgba(0,0,0,0)")))
            fig.write_image(out_png, width=2400, height=1100, scale=1)
            print(f"      Saved {out_png} (not password protected)")
        except Exception as e:  # noqa: BLE001 - the optional PNG must never stop the run
            # Missing kaleido (or its browser) must not stop the run: the HTML is already saved.
            print(f"      PNG skipped ({type(e).__name__}); install it with: pip install kaleido")
    # Open the finished page in the default browser (unless --no-open was given).
    if cfg.open_browser:
        print("Opening in your browser ...")
        webbrowser.open(pathlib.Path(out_html).as_uri())
    print("Done.")

