"""The setup window: asks for the main settings of one run (tkinter ships with Python, imported only when it opens)."""
from __future__ import annotations

import calendar
import importlib
import os
from dataclasses import replace
from datetime import date, datetime
from typing import Any

import pandas as pd

from .clients import (
    OTHER_PORTAL_LABEL,
    heading_for_client,
    password_for_client,
    portal_choices,
    start_date_for_portal,
)
from .settings import (
    DEFAULT_HEADING,
    HERE,
    PRE_BUCKET_NAME,
    RunSettings,
)


def default_setup_values(cfg: RunSettings) -> dict[str, Any]:
    """Work out the starting values shown in the launch window.

    The defaults are:
        password            blank (= no password)
        page heading        "Funnel Tracking"
        HubSpot portal ID   nothing selected (= company names are not links)
        auto-detect date    off
        start date          the first day of the PREVIOUS calendar quarter, so the chart
                            covers the previous quarter and the current one
        save PNG            off
        scale               "log"
        random-before date  exactly 3 months before today (for the Random success button)
        pre-bucket name     the text of PRE_BUCKET_NAME in the constants block
        file                the CSV given on the command line, otherwise all-companies.csv
                            next to this script if it exists, otherwise blank

    Args:
        cfg: The settings of this run so far (today's date, the command-line CSV and the Pre bucket name).

    Returns:
        A dictionary the SetupWindow reads. Dates are ``datetime.date`` objects.
    """
    today = date(cfg.today.year, cfg.today.month, cfg.today.day)          # today as a plain date
    # Start of the previous quarter: quarters begin in January, April, July and October.
    quarter = (today.month - 1) // 3                          # 0, 1, 2 or 3 for the current quarter
    prev_quarter, prev_year = quarter - 1, today.year
    if prev_quarter < 0:                                      # current quarter is Q1: go back to last year's Q4
        prev_quarter, prev_year = 3, today.year - 1
    start_default = date(prev_year, prev_quarter * 3 + 1, 1)
    # Exactly 3 months before today; if that month is shorter (31 May -> 28/29 Feb) use its last day.
    month, year = today.month - 3, today.year           # subtract 3 months ...
    if month < 1:                                       # ... and wrap into the previous year if needed
        month, year = month + 12, year - 1
    three_months_ago = date(year, month, min(today.day, calendar.monthrange(year, month)[1]))
    # One entry per field of the window; SetupWindow reads these keys.
    return {
        "password": "",                                 # blank = no password
        "heading": DEFAULT_HEADING,                     # page title
        "portal_id": "",                                # blank = nothing selected = company names are not HubSpot links
        "autodetect": False,                            # start at the oldest company?
        "start": start_default,                         # start of the previous quarter
        "save_png": False,                              # also write the unprotected PNG?
        "scale": "log",                                 # ribbon width scale
        "random_before": three_months_ago,              # the Random success button picks companies created before this
        "pre_name": cfg.pre_name,                    # label of the box for companies created before the start date
        "csv": cfg.csv if os.path.isfile(cfg.csv) else "",      # pre-select the default export when it exists
    }



class SetupWindow:
    """The launch window: one small form that collects the settings for a single run.

    Fields (top to bottom): start date picker (the only bold label), auto-detect-start-date
    checkbox, password, page heading, HubSpot portal drop-down (with an "Other - Type ID" box),
    save-PNG checkbox, scale drop-down, the CSV file picker, the "Random Success picks
    companies created before" date picker (the only italic label) and the pre-bucket name box,
    then Run and Cancel.

    Choosing a client in the portal drop-down fills in the start date (from ACCOUNT_START_DATES), and
    the page heading and the password, but only while those two are still at their defaults (see
    ``_on_portal_selected``).

    Date pickers: if the optional ``tkcalendar`` package is installed a real calendar pop-up
    is used; otherwise three simple drop-downs (year, month, day) take its place.

    Attributes:
        result: ``None`` until the user presses Run. Afterwards a dictionary with the keys
            password, heading, portal_id (digits, or "" for no links), autodetect, start (a
            ``pandas.Timestamp``), save_png, scale, random_before (text ``YYYY-MM-DD``, used by the
            Random success button), pre_name (the Pre bucket label), csv (the file path) and run_time (a
            ``datetime``: the moment Run was clicked, which names the output folder).
            It stays ``None`` if the window is cancelled or closed.
    """

    SCALE_CHOICES = ("log", "sqrt", "none")
    MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

    def __init__(self, defaults: dict[str, Any]) -> None:
        """Build the window (it is not shown on screen until ``show()`` is called).

        Args:
            defaults: The dictionary returned by ``default_setup_values()``.

        Raises:
            ImportError: tkinter is not installed.
            tkinter.TclError: there is no screen to draw on (for example a server).
        """
        # tkinter is imported here, not at the top of the file, so the rest of the script
        # does not need it.
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
        from tkinter import font as tkfont
        self.tk, self.ttk = tk, ttk
        self.filedialog, self.messagebox = filedialog, messagebox
        self.result = None
        # The last page heading and password that choosing a client filled in (None = nothing yet).
        # A field that still holds that text counts as "not typed by the user", so choosing a
        # different client may replace it; anything the user typed is never touched.
        self._auto_heading: str | None = None
        self._auto_password: str | None = None

        self.root = tk.Tk()
        self.root.title("Funnel Tracking - setup")
        self.root.resizable(False, False)
        # Closing the window with the X counts as Cancel.
        self.root.protocol("WM_DELETE_WINDOW", self._on_cancel)
        frame = ttk.Frame(self.root, padding=16)
        frame.grid(row=0, column=0)

        ttk.Label(frame, text="Funnel Tracking setup",
                  font=("TkDefaultFont", 13, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(frame, text="These choices apply to this run only.",
                  foreground="#555").grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self.form = frame                       # kept so the layout can be inspected (tests, debugging)
        # Two variants of the normal label font: bold (for "Start date") and italic (for the Random date).
        base_font = tkfont.nametofont("TkDefaultFont")
        self._bold_font = base_font.copy()
        self._bold_font.configure(weight="bold")
        self._italic_font = base_font.copy()
        self._italic_font.configure(slant="italic")

        # Each field is one grid row: label (column 0), the control (column 1), a hint (column 2).
        def label(row: int, text: str, font: Any = None) -> None:
            """Put the field's name in column 0 of the given row (``font`` None = the normal font)."""
            ttk.Label(frame, text=text, font=font).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 12))

        def hint(row: int, text: str) -> None:
            """Put the small gray explanation in column 2 of the given row."""
            ttk.Label(frame, text=text, foreground="#666").grid(row=row, column=2, sticky="w", padx=(12, 0))

        # --- START date picker (first row, bold) --------------------------------------
        label(2, "Start date", self._bold_font)
        (self._start_widget, self._get_start, self._enable_start,
         self._set_start) = self._date_picker(frame, defaults["start"])
        self._start_widget.grid(row=2, column=1, sticky="w")
        hint(2, "Ignored when auto-detect is on")

        # --- AUTODETECT_DATE checkbox (turns the start date picker off) --------------
        # It stays right under the start date it controls.
        label(3, "Auto-detect start date")
        self.autodetect = tk.BooleanVar(value=defaults["autodetect"])
        ttk.Checkbutton(frame, variable=self.autodetect,
                        command=self._toggle_start).grid(row=3, column=1, sticky="w")
        hint(3, "Start at the oldest company")
        self._toggle_start()                    # grey the start date out if auto-detect starts ticked

        # --- PASSWORD: hidden characters, with a "Show" box -------------------------
        label(4, "Password")
        self.password = tk.StringVar(value=defaults["password"])         # the typed text lives in this variable
        pw_row = ttk.Frame(frame)                                        # holds the entry and the "Show" box side by side
        pw_row.grid(row=4, column=1, sticky="w")
        self.password_entry = ttk.Entry(pw_row, textvariable=self.password, width=40, show="*")   # "*" hides the characters
        self.password_entry.pack(side="left")
        self.show_password = tk.BooleanVar(value=False)                  # ticked = show the characters
        ttk.Checkbutton(pw_row, text="Show", variable=self.show_password,
                        command=self._toggle_password).pack(side="left", padx=(8, 0))
        hint(4, "Blank = no password")

        # --- PAGE_HEADING ---------------------------------------------------------------
        label(5, "Page heading")
        self.heading = tk.StringVar(value=defaults["heading"])
        ttk.Entry(frame, textvariable=self.heading, width=40).grid(row=5, column=1, sticky="w")

        # --- HubSpot portal: a drop-down of the known accounts, nothing selected at first ---------
        label(6, "HubSpot portal ID")
        # Shown text -> (company name, portal ID), already sorted by name (see portal_choices).
        self._accounts = {text: (name, portal_id) for text, name, portal_id in portal_choices()}
        self.portal_choice = tk.StringVar()      # the drop-down's text; "" = nothing selected
        self.portal_other = tk.StringVar()       # the ID typed after choosing "Other - Type ID"
        # If the defaults already carry a portal ID, pre-select it (the normal default is blank = nothing).
        preset = str(defaults.get("portal_id", "")).strip()
        for text, (_name, portal_id) in self._accounts.items():
            if portal_id == preset:
                self.portal_choice.set(text)
        if preset and not self.portal_choice.get():
            self.portal_choice.set(OTHER_PORTAL_LABEL)
            self.portal_other.set(preset)
        portal_row = ttk.Frame(frame)            # holds the drop-down and, when needed, the typing box
        portal_row.grid(row=6, column=1, sticky="w")
        # state="readonly": only entries from the list can be chosen. "Other - Type ID" is always first.
        self._portal_box = ttk.Combobox(portal_row, textvariable=self.portal_choice, state="readonly", width=44,
                                        values=[OTHER_PORTAL_LABEL, *self._accounts])
        self._portal_box.pack(side="left")
        self._portal_box.bind("<<ComboboxSelected>>", self._on_portal_selected)
        # The typing box is only shown while "Other - Type ID" is chosen (see _show_portal_entry).
        self._portal_entry = ttk.Entry(portal_row, textvariable=self.portal_other, width=14)
        hint(6, "Pick the client, or Other to type an ID. Nothing picked = no links")
        self._show_portal_entry()

        # --- SAVE_PNG checkbox ---------------------------------------------------------
        label(7, "Save PNG")
        self.save_png = tk.BooleanVar(value=defaults["save_png"])
        ttk.Checkbutton(frame, variable=self.save_png).grid(row=7, column=1, sticky="w")
        hint(7, "Also saves a picture. It is NOT password protected")

        # --- SCALE drop-down ---------------------------------------------------------
        label(8, "Ribbon scale")
        self.scale = tk.StringVar(value=defaults["scale"])
        ttk.Combobox(frame, textvariable=self.scale, values=self.SCALE_CHOICES, state="readonly",
                     width=10).grid(row=8, column=1, sticky="w")
        hint(8, "log = strongest compression, sqrt = gentler, none = true size")

        # --- CSV file picker ------------------------------------------------------------
        label(9, "HubSpot export (CSV)")
        self.csv = tk.StringVar(value=defaults["csv"])
        file_row = ttk.Frame(frame)
        file_row.grid(row=9, column=1, columnspan=2, sticky="w")
        ttk.Entry(file_row, textvariable=self.csv, width=58).pack(side="left")
        ttk.Button(file_row, text="Browse...", command=self._browse).pack(side="left", padx=(8, 0))

        # --- RANDOM_CREATED_BEFORE date picker (italic) ---------------------------------
        label(10, "Random Success picks companies created before", self._italic_font)
        self._random_widget, self._get_random, _unused, _unused2 = self._date_picker(frame, defaults["random_before"])
        self._random_widget.grid(row=10, column=1, sticky="w")
        hint(10, "Only the Random success button uses it; Random can pick any company")

        # --- PRE_BUCKET_NAME: the label of the box for companies older than the start date ----------
        label(11, "Pre-bucket name")
        self.pre_name = tk.StringVar(value=defaults["pre_name"])
        ttk.Entry(frame, textvariable=self.pre_name, width=40).grid(row=11, column=1, sticky="w")
        hint(11, "Label of the box for companies created before the start date")

        ttk.Label(frame, text="Stage buckets, labels, colors and the other settings are still set in the "
                              "constants block at the top of the script.",
                  foreground="#666").grid(row=12, column=0, columnspan=3, sticky="w", pady=(12, 0))

        # --- buttons -------------------------------------------------------------------
        buttons = ttk.Frame(frame)
        buttons.grid(row=13, column=0, columnspan=3, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Cancel", command=self._on_cancel).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Run", command=self._on_run).pack(side="right")
        self.root.bind("<Return>", lambda _event: self._on_run())
        self.root.bind("<Escape>", lambda _event: self._on_cancel())

    # ---------------------------------------------------------------- date picker widgets
    def _date_picker(self, parent: Any, initial: date) -> tuple[Any, Any, Any, Any]:
        """Create a date picker and return ``(widget, get_date, set_enabled, set_date)``.

        Args:
            parent: The tkinter frame to place the picker in.
            initial: A ``datetime.date`` to show first.

        Returns:
            widget: the picker (call ``.grid(...)`` on it).
            get_date: function returning the chosen ``datetime.date``.
            set_enabled: function taking True/False to switch the picker on or off.
            set_date: function taking a ``datetime.date`` and showing it in the picker (it works
                even while the picker is greyed out).
        """
        ttk, tk = self.ttk, self.tk
        try:
            # Best case: the optional tkcalendar package gives a real calendar pop-up.
            date_entry = importlib.import_module("tkcalendar").DateEntry
            picker = date_entry(parent, width=12, date_pattern="yyyy-mm-dd",
                                year=initial.year, month=initial.month, day=initial.day)
            def set_date_entry(value: date) -> None:
                """Show ``value`` in the calendar box, also when it is greyed out."""
                state = str(picker.cget("state"))
                picker.configure(state="normal")          # a disabled box would ignore the new text
                picker.set_date(value)
                picker.configure(state=state)

            return (picker, picker.get_date,
                    lambda on: picker.configure(state="normal" if on else "disabled"),
                    set_date_entry)
        except ImportError:
            pass
        # Fallback with no extra package: three drop-downs (year, month, day).
        box = ttk.Frame(parent)                                          # one frame holding the three drop-downs
        year_var = tk.StringVar(value=str(initial.year))                 # each drop-down keeps its choice in a variable
        month_var = tk.StringVar(value=self.MONTH_NAMES[initial.month - 1])
        day_var = tk.StringVar(value=str(initial.day))
        years = [str(y) for y in range(initial.year - 8, initial.year + 3)]   # 8 years back to 2 years ahead
        # state="readonly": the user can only pick from the list, never type something invalid.
        year_box = ttk.Combobox(box, textvariable=year_var, values=years, width=6, state="readonly")
        month_box = ttk.Combobox(box, textvariable=month_var, values=self.MONTH_NAMES, width=5, state="readonly")
        day_box = ttk.Combobox(box, textvariable=day_var, values=[str(d) for d in range(1, 32)],
                               width=4, state="readonly")
        for part in (year_box, month_box, day_box):                      # place them left to right
            part.pack(side="left", padx=(0, 4))

        def get_date() -> date:
            """Read the three drop-downs and return the chosen date."""
            year = int(year_var.get())
            month = self.MONTH_NAMES.index(month_var.get()) + 1
            # "31 Feb" becomes the last real day of that month.
            return date(year, month, min(int(day_var.get()), calendar.monthrange(year, month)[1]))

        def set_enabled(on: bool) -> None:
            """Switch the three drop-downs on (True) or grey them out (False)."""
            for part in (year_box, month_box, day_box):
                part.configure(state="readonly" if on else "disabled")

        def set_date(value: date) -> None:
            """Show ``value`` in the three drop-downs (the year list grows if it is missing)."""
            if str(value.year) not in year_box.cget("values"):
                year_box.configure(values=[str(y) for y in range(min(value.year, initial.year - 8),
                                                                  max(value.year, initial.year + 2) + 1)])
            year_var.set(str(value.year))
            month_var.set(self.MONTH_NAMES[value.month - 1])
            day_var.set(str(value.day))

        return box, get_date, set_enabled, set_date

    # ---------------------------------------------------------------- small event handlers
    def _toggle_password(self) -> None:
        """Show or hide the typed password characters."""
        self.password_entry.configure(show="" if self.show_password.get() else "*")

    def _show_portal_entry(self) -> None:
        """Show the typing box next to the drop-down only while "Other - Type ID" is chosen."""
        if self.portal_choice.get() == OTHER_PORTAL_LABEL:
            self._portal_entry.pack(side="left", padx=(8, 0))
        else:
            self._portal_entry.pack_forget()

    def _on_portal_selected(self, _event: Any = None) -> None:
        """React to a choice in the portal drop-down.

        * "Other - Type ID": show the typing box and put the cursor in it. Nothing else changes.
        * A client: if the page heading is still the default ("Funnel Tracking", or blank), put the
          client's name in front of it. If the password is blank, make it from the client's name
          (lower case, hyphens, ``-funnel``) and tick "Show" so it can be read. The Start date box is
          set to the client's date from ACCOUNT_START_DATES (every time, even if it was changed by
          hand; a client with no entry leaves it alone).

        A heading or password the user typed is left alone. One that an earlier choice filled in
        counts as untouched, so choosing a different client updates it instead of leaving the
        first client's name behind.
        """
        self._show_portal_entry()
        choice = self.portal_choice.get()
        if choice == OTHER_PORTAL_LABEL:
            self._portal_entry.focus_set()
            return                                   # no client name to use: heading and password stay as they are
        found = self._accounts.get(choice)
        if found is None:
            return
        name = found[0]
        # Page heading: replace it only while it is the default or the text this method put there before.
        heading = self.heading.get().strip()
        if heading in ("", DEFAULT_HEADING) or heading == self._auto_heading:
            self._auto_heading = heading_for_client(name)
            self.heading.set(self._auto_heading)
        # Password: fill it only while it is blank or the one this method made before, then show it.
        password = self.password.get()
        if not password.strip() or password == self._auto_password:
            self._auto_password = password_for_client(name)
            self.password.set(self._auto_password)
            self.show_password.set(True)
            self._toggle_password()
        # Start date: always filled from ACCOUNT_START_DATES (a client without an entry leaves the box alone).
        start = start_date_for_portal(found[1])
        if start is not None:
            self._set_start(start)

    def _toggle_start(self) -> None:
        """Grey out the start date picker while auto-detect is ticked (it would be ignored)."""
        self._enable_start(not self.autodetect.get())

    def _browse(self) -> None:
        """Open the file chooser and put the picked CSV path in the file field."""
        current = self.csv.get().strip()
        start_dir = os.path.dirname(current) if current and os.path.dirname(current) else HERE
        picked = self.filedialog.askopenfilename(
            parent=self.root, title="Choose the HubSpot companies export", initialdir=start_dir,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if picked:
            self.csv.set(os.path.normpath(picked))

    def _on_cancel(self) -> None:
        """Close the window without running anything (``result`` stays None)."""
        self.result = None
        self.root.destroy()

    def _on_run(self) -> None:
        """Check the entries; if they are fine store them in ``result`` and close the window.

        A problem (missing file, "Other - Type ID" without a numeric ID) shows a message and leaves
        the window open. A blank password asks for confirmation first, because the page is
        then readable by anyone who gets the file.
        """
        # 1) The export file must be chosen and must exist (surrounding spaces and quotes are removed).
        csv_path = self.csv.get().strip().strip('"')
        if not csv_path or not os.path.isfile(csv_path):
            self.messagebox.showerror("File not found", "Choose the HubSpot export (a CSV file) first.",
                                      parent=self.root)
            return
        # 2) The portal: a client from the list gives its ID; "Other - Type ID" needs a number typed in
        #    (it goes into the HubSpot links); nothing selected means no links.
        choice = self.portal_choice.get()
        if choice == OTHER_PORTAL_LABEL:
            portal = self.portal_other.get().strip()
            if not portal.isdigit():
                self.messagebox.showerror("HubSpot portal ID",
                                          "Type the portal ID (a number, for example 20889631),\n"
                                          "or choose a client from the list.", parent=self.root)
                return
        elif choice in self._accounts:
            portal = self._accounts[choice][1]
        else:
            portal = ""
        # 3) A blank password publishes the page unprotected, so it needs an explicit "Yes".
        password = self.password.get()
        if not password.strip():
            password = ""
            if not self.messagebox.askyesno(
                    "No password",
                    "No password is set.\n\nAnyone who gets the page can read every company name, "
                    "domain and Record ID in it.\n\nContinue without a password?", parent=self.root):
                return
        # 4) Everything is fine: store the choices (this is what ask_settings() returns) and close the window.
        self.result = {
            "password": password,
            "heading": self.heading.get().strip() or DEFAULT_HEADING,
            "portal_id": portal,
            "autodetect": bool(self.autodetect.get()),
            "start": pd.Timestamp(self._get_start()),
            "save_png": bool(self.save_png.get()),
            "scale": self.scale.get(),
            "random_before": self._get_random().strftime("%Y-%m-%d"),
            "pre_name": self.pre_name.get().strip() or PRE_BUCKET_NAME,
            "csv": csv_path,
            "run_time": datetime.now(),                      # the moment Run was clicked: names the output folder
        }
        self.root.destroy()

    def show(self) -> dict[str, Any] | None:
        """Put the window in front of everything, wait until it is closed and return ``result``."""
        self.root.update_idletasks()
        # Centre on the screen.
        width, height = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        x = max((self.root.winfo_screenwidth() - width) // 2, 0)
        y = max((self.root.winfo_screenheight() - height) // 3, 0)
        self.root.geometry(f"+{x}+{y}")
        # Bring it to the front (it can open behind the editor), then let it behave normally.
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.after(300, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()
        self.root.mainloop()
        return self.result



def ask_settings(defaults: dict[str, Any]) -> dict[str, Any] | None:
    """Open the launch window and return the chosen settings.

    Args:
        defaults: Starting values, normally ``default_setup_values()``.

    Returns:
        The settings dictionary (see ``SetupWindow``), or ``None`` if the user cancelled.
    """
    return SetupWindow(defaults).show()


def choose_run_settings(cfg: RunSettings) -> RunSettings:
    """Open the setup window (when ``cfg.show_dialog`` is True) and return the settings of this run.

    What the user chooses replaces the matching fields of ``cfg``, in a changed COPY: ``cfg`` itself and the
    constants in settings.py are never touched. The moment Run was clicked becomes ``run_time``, which names
    the output folder. If the window cannot be opened (no tkinter, or no screen) the settings are returned as
    they are. Pressing Cancel stops the program.

    Args:
        cfg: The settings so far (the constants, the command line).

    Returns:
        The settings to use for this run.

    Raises:
        SystemExit: when the window is cancelled.
    """
    if not cfg.show_dialog:
        return cfg
    try:
        choice = ask_settings(default_setup_values(cfg))
    except Exception as err:  # noqa: BLE001 - any failure to open the window (no tkinter, no screen) means "use the constants"
        choice = {}
        print(f"Setup window unavailable ({type(err).__name__}: {err}).")
        print("Using the values in the constants block instead.")
    if choice is None:
        raise SystemExit("Setup cancelled. Nothing was generated.")
    if not choice:
        return cfg
    # The window's result uses the same names as the RunSettings fields.
    names = ("password", "heading", "portal_id", "autodetect", "start", "save_png", "scale",
             "random_before", "pre_name", "csv")
    cfg = replace(cfg, **{name: choice[name] for name in names}, run_time=choice.get("run_time", cfg.run_time))
    # Echo the choices to the console (the password itself is never printed, only "set" or "none").
    print("Settings chosen in the setup window:")
    print(f"      file: {cfg.csv}")
    print(f"      heading: {cfg.heading!r} | password: {'set' if cfg.password else 'none'} | "
          f"portal ID: {cfg.portal_id or 'none'}")
    print(f"      start date: {'auto-detect' if cfg.autodetect else f'{cfg.start:%Y-%m-%d}'} | "
          f"scale: {cfg.scale} | save PNG: {cfg.save_png} | Random success before: {cfg.random_before}")
    print(f"      pre-bucket name: {cfg.pre_name!r}")
    print(f"      run started: {cfg.run_time:%Y-%m-%d %H:%M:%S}")
    return cfg
