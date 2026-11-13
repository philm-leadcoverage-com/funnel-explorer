"""The settings you edit, and RunSettings: the values of one run.

Nothing here does any work. The constants are the defaults; the command line and the setup window may replace
some of them for ONE run (see RunSettings at the bottom), and the constants themselves are never changed.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

## ## ## ## ## ## ## ## USER DEFINED CONSTANTS  ## ## ## ## ## ## ## ##
# #############################################################################
# THIS IS THE ONLY BLOCK YOU NORMALLY EDIT (for example, when switching client).
# Everything below the closing line of this block is the program itself.
# #############################################################################

# --- Access ------------------------------------------------------------------
# PASSWORD: the text visitors must type before the page opens. The whole page (chart and
# company data) is encrypted with it. Examples: "two-random-words-and-a-number".
# Use "" (empty) to publish WITHOUT a password (the script then prints a warning).
PASSWORD = "password"

# --- Page text ---------------------------------------------------------------
# PAGE_HEADING: the big H1 title at the top of the page and the browser tab title.
PAGE_HEADING = "Funnel Tracking"
# CREATED_BY_NAME / CREATED_BY_EMAIL: the credit line "Created by <name> on <date and time>".
# The name becomes a mailto: link to the e-mail address.
CREATED_BY_NAME = "Phil Mann at LeadCoverage"
CREATED_BY_EMAIL = "phil.m@leadcoverage.com"

# --- HubSpot links -----------------------------------------------------------
# The number after /contacts/ in any HubSpot URL. Company names become links to the record.
# Use "" for no links. Change the app address if the portal is in the EU data center.
#   Example URL:  https://app.hubspot.com/contacts/48053876/record/0-2/12345
#                                                    ^^^^^^^^ this number
#   EU data center example for HUBSPOT_APP_URL: "https://app-eu1.hubspot.com"
# (The setup window sets this for you: it has a drop-down of the accounts in HUBSPOT_ACCOUNTS below.)
HUBSPOT_PORTAL_ID = "48053876"
HUBSPOT_APP_URL = "https://app.hubspot.com"


# --- Extra company details -----------------------------------------------------
# When a company is selected the page lists these HubSpot columns under its journey, but only the ones
# that are not blank. They all run on together in ONE block, so a line only breaks where the next item no
# longer fits. Each inner list below is a GROUP: the groups only decide the ORDER (related fields stay next
# to each other), they never start a new line. All the "First ..." fields are together and all the
# "Last ..." fields are together. The names must match the column headers of the export (capitals and
# spaces around the name do not matter). A column the export does not have is skipped, and the script
# prints which ones were skipped. Edit, add or remove names freely; use [] for no details.
# A value of ZERO (0, 0.0, 0.00) counts as blank and is never shown or stored.
DETAIL_LINES = [
    # Who owns the company, what it does and what kind of company it is.
    ["Company owner", "Industry", "Type"],
    # How many contacts and deals are associated with the company.
    ["Number of Associated Contacts", "Number of Associated Deals"],
    # ALL THE FIRSTS: the first conversion, deal, sales activity and touch, and the first time seen / first session.
    ["First Conversion", "First Conversion Date", "First Deal Created Date",
     "First Sales Activity Date", "First Touch Converting Campaign",
     "Time First Seen", "Time of First Session"],
    # ALL THE LASTS: the most recent activity (meetings, contacts, engagement, calls, e-mails), the last converting
    # campaign, the last website visit and session, and the last meeting booking.
    ["Last Activity Date", "Last Booked Meeting Date", "Last Contacted", "Last Engagement Date",
     "Last Logged Call Date", "Last Logged Outgoing Email Date", "Last Touch Converting Campaign",
     "Last Tracked Visit Time", "Time Last Seen", "Time of Last Session",
     "Campaign of last booking in meetings tool", "Source of last booking in meetings tool"],
    # Where the most recent visit came from, and the lead status.
    ["Latest Traffic Source", "Latest Traffic Source Data 1", "Latest Traffic Source Data 2",
     "Latest Traffic Source Timestamp", "Lead Status"],
    # The most recent form conversion and the most recent deal.
    ["Recent Conversion", "Recent Conversion Date", "Recent Deal Amount", "Recent Deal Close Date"],
    # Website usage, how often the company was contacted, and where it first came from.
    ["Number of Pageviews", "Number of Sessions", "Number of times contacted",
     "Original Traffic Source", "Original Traffic Source Drill-Down 1",
     "Original Traffic Source Drill-Down 2"],
    # How the company record was created in HubSpot.
    ["Record source", "Record source detail 1", "Record source detail 2", "Record source detail 3"],
]
# LOGO_URL_COLUMN: the export column that holds a company's logo web address. The logo is shown
# next to the company's details when it is selected. "" = no logos.
LOGO_URL_COLUMN = "Logo URL"

# --- Agency logo ---------------------------------------------------------------
# The agency's own logo is shown UNDER the selected company's logo, and links to AGENCY_SITE_URL
# in a new window. When the script runs it downloads the logo once from AGENCY_LOGO_URL and builds
# it into the page (a few KB), so it always displays, works offline and can be included in the
# saved picture. If the download fails the page loads it from the web instead.
# "" for AGENCY_LOGO_URL = no agency logo. "" for AGENCY_SITE_URL = the logo is not a link.
AGENCY_LOGO_URL = "https://f.hubspotusercontent30.net/hubfs/612489/__hs-marketplace__/LeadCoverageIconWEB.jpeg"
AGENCY_SITE_URL = "https://leadcoverage.com"

# --- Saved picture (camera button) ----------------------------------------------
# PICTURE_SCALE: 1 = the picture is as many pixels wide as the chart is on the screen (about 2,000
#                for a typical window). 2 = twice as many pixels in each direction (4 times the
#                pixels and roughly 4 times the file size). 0.5 = half in each direction.
# PICTURE_CREATED_BY: the credit line INSIDE the picture reads "Created by <this> on <date and time>".
#                The credit line on the page itself keeps CREATED_BY_NAME and the e-mail link.
PICTURE_SCALE = 1
PICTURE_CREATED_BY = "LeadCoverage"

# --- Month header word -----------------------------------------------------------
# The header above each month reads "+428 new / 57 <this word> / 485 total". The middle number
# is the companies that were already in the chart in the previous month, carried over.
CARRIED_LABEL = "carried-over"

# --- Output files and source protection --------------------------------------------
# Every run writes into its own NEW folder, <client-name>/<yyyy-mm-dd-hh-mm-ss>/ (see OUTPUT_ROOT in the
# settings below), so an older run is never overwritten. In it the script writes index.html (the password
# screen with the whole page encrypted inside it) and, next to it, a folder called "assets" with the page's
# code and styles (funnel.js, funnel.css) and the Plotly library. The assets files hold NO company data,
# but they are NOT password protected: anyone who knows their address can read them.
# Upload index.html AND the assets folder together.
# MINIFY: True  = shrink the files. Level 1 removes comments and spacing (needs: pip install rjsmin rcssmin).
#                 Level 2 also renames local variable and function names to short letters; it
#                 runs automatically when Node's "terser" is installed (npm install -g terser).
#         False = leave them readable (useful when debugging the page code).
MINIFY = True
# SOURCE_NOTICE_OWNER: the owner named in the copyright notices that are written into the
# public files (assets and password screen). "" = no notices. See the "notices" comments below.
SOURCE_NOTICE_OWNER = "LeadCoverage"

# --- Start date --------------------------------------------------------------
# True : ignore START and begin the chart at the earliest Create Date in the export.
# False: use START. Companies created before START go in the "Pre" bucket below
#        (only the ones that reached PRE_BUCKET_MIN_STAGE or higher on/after START).
# AUTODETECT_DATE: True = start at the first day of the month of the oldest company.
#                  False = start exactly at START. Everything older goes into the Pre
#                  bucket (or is left out, see PRE_BUCKET_MIN_STAGE).
AUTODETECT_DATE = False
# START: the first date shown on the chart (only used when AUTODETECT_DATE is False).
START = pd.Timestamp("2025-01-01")
# PRE_BUCKET_NAME: the label of the extra box on the far left (companies older than START).
# The setup window asks for it too and starts with the text below. This text is used as written
# when SHOW_DIALOG is False, and when the window's "Pre-bucket name" box is left blank.
PRE_BUCKET_NAME = "Pre-LeadCoverage"      # the text shown for the bucket before START
# PRE_BUCKET_MIN_STAGE: an older company only enters the Pre bucket if, on or after START, it
# reached this stage or higher. Allowed: LEAD, MQL, SQL, OPP, CUSTOMER (never SUBSCRIBER or OTHER).
PRE_BUCKET_MIN_STAGE = "MQL"              # LEAD, MQL, SQL, OPP or CUSTOMER

# --- Lifecycle stage buckets (bottom of the chart to the top) -----------------
# The chart stacks seven buckets: OTHER at the very bottom (unqualified, internal, partners and so on), then
# SUBSCRIBER, LEAD, MQL, SQL and OPP, with CUSTOMER at the top. Each one is a comma separated list of stage names, not
# case sensitive. It is ONE list for every account: the script reads the stage names it finds in each export and puts
# every one in a bucket, so a new account normally needs no change here. How a name is matched (see stages.py):
#   * a name is matched against the lists as whole words, and the longest listed name wins
#     ("Marketing Qualified Lead" is MQL, not Lead; "Not Right for Circle" is Other because NOT RIGHT FOR is listed);
#   * a hint in brackets is read first: "Awareness (MQL)" is MQL, "Development (Customer)" is Customer;
#   * a small typo is forgiven ("Propsect" is read as PROSPECT, "Unqualifed" as UNQUALIFIED);
#   * a name that matches nothing goes to OTHER, with a warning, so every company is still counted.
# Two names in one bucket ("Marketing Qualified Lead" and "MQL") are combined. A name listed in two buckets stops the
# script. Leave a bucket as "" if nobody uses it (an account with no Subscriber stage just has an empty bottom box).
OTHER = "OTHER, UNQUALIFIED, DISQUALIFIED, NOT RIGHT FOR, INTERNAL, AGENT, PARTNER, SUPPLY CHAIN PARTNER"
SUBSCRIBER = "SUBSCRIBER, TARGET, PROSPECT"
LEAD = "LEAD, IQL, MARKETING ENROLLED"
MQL = "MARKETING QUALIFIED LEAD, MARKETING ACCEPTED LEAD, MQL, MAL"
SQL = "SALES QUALIFIED LEAD, SALES ACCEPTED LEAD, SALES LEAD, SQL, SAL, PROSPECTING, APPLICANT SCREENING"
OPP = "OPPORTUNITY, OPP, DEAL, OFFER, HIRED"
CUSTOMER = "CUSTOMER, EVANGELIST, PROMOTER, FORMER CUSTOMER, TRANSACTIONAL"
# LABELS: the seven names printed on the chart, in the same order as the buckets above (bottom to top). The Subscriber
# box does not use its entry here when the export has its own name for that stage: it then shows that name (Prospect,
# Target ...). ACCOUNT_STAGE_LABELS in clients.py can force a different name for one account.
LABELS = ["Other", "Sub", "Lead", "MQL", "SQL", "Opp", "Cust"]   # names shown on the chart

# --- Colors -------------------------------------------------------------------
# Any CSS color works: "#rrggbb" hex or "rgba(r,g,b,alpha)" where alpha is 0 (clear) to 1.
# BAND_COLORS: the box color of each bucket, bottom to top (same order as LABELS).
BAND_COLORS = ["#b9c0c9", "#7f8c9a", "#2f80ed", "#8e44ad", "#f39c12", "#884c3c", "#16a34a"]  # one per bucket, same order as LABELS
PRE_BUCKET_COLOR = "#34495e"                  # the Pre bucket box
STAYED_COLOR = "rgba(180,180,180,0.33)"       # ribbons for companies that stayed in the same bucket
MOVED_DOWN_COLOR = "rgba(50,50,50,0.66)"      # ribbons for companies that moved down a bucket
HIGHLIGHT_COLOR = "#ff0099"                   # the line drawn for a searched company
# (Ribbons for companies that moved UP take the color of the bucket they moved into.)

# MARKED_DATES: optional notes flagged under the month they fall in (for example a bulk import or a bulk stage change,
# so nobody reads that month's jump as growth). Each entry is (date, short text), for example
#   MARKED_DATES = [(pd.Timestamp("2025-03-04"), "Contacts import")]
# The text is written in red-orange under the month name at the bottom of the chart. Empty by default: no change.
MARKED_DATES: list = []
# STAGE_HOVER: optional text shown when you hover a stage box, one entry per LABELS entry (same order, so the first is for Other).
# Empty by default.
STAGE_HOVER: list = []

# --- HubSpot backfill ---------------------------------------------------------
# Some portals have one minute where thousands of old companies were stamped with a stage
# date. That is not a real move. "AUTO" finds it, "" means none, or type a date and time
# such as "2026-02-12 00:27".
# Why it matters: such a stamp would look like a huge wave of companies "moving" on one
# day. Stage dates equal to this stamp are not counted as real moves when deciding who
# belongs in the Pre bucket or the "Random success" list.
BACKFILL_STAMP = "AUTO"

# --- Launch window -------------------------------------------------------------
# True : a setup window opens first. What you choose there REPLACES, for that run only, the
#        constants PASSWORD, PAGE_HEADING, HUBSPOT_PORTAL_ID, AUTODETECT_DATE, START,
#        SAVE_PNG, SCALE, RANDOM_CREATED_BEFORE, PRE_BUCKET_NAME and the CSV file. (So the values typed for
#        those constants above are only used when this is False or the window cannot open.)
# False: no window; the script uses the constants exactly as written above (handy for
#        scheduled or unattended runs).
SHOW_DIALOG = True
 ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ##
# ----------------------- END OF USER DEFINED CONSTANTS -----------------------

# =============================================================================
# SETTINGS
# =============================================================================
# Less common knobs. The defaults are fine for normal use.

# The folder that holds lcs-graph.py (this file sits in its "funnel" folder, one level down).
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The CSV to read when none is chosen: all-companies.csv in the script folder. The run replaces it with
# the file given on the command line (python lcs-graph.py "D:\exports\acme.csv") or picked in the setup window.
CSV = os.path.join(HERE, "all-companies.csv")

# OUTPUT_ROOT: the folder in which the output of every run is stored. Each run gets its OWN new folder,
#     <OUTPUT_ROOT>/<client-name>/<yyyy-mm-dd-hh-mm-ss>/
# holding index.html and the assets folder (and the PNG when SAVE_PNG is on), so an older run is never
# overwritten. The client name is found from HUBSPOT_PORTAL_ID in the HUBSPOT_ACCOUNTS list (so it is the name
# picked in the setup window's drop-down), written in lower case with every run of spaces and special
# characters turned into one hyphen. See client_folder_name() and make_output_folder().
OUTPUT_ROOT = HERE
# --- Access ------------------------------------------------------------------
# Visitors must type the PASSWORD to see anything. The whole page (chart and company
# data) is encrypted with it, so it cannot be read from the page source. Use a long one.
# Set to "" for no password. The page always tells search engines not to index it.

# PBKDF2_ITERATIONS: how many times the password is "stretched" into the key. More rounds
# make guessing the password slower for an attacker (and decrypting a hair slower for
# visitors). The browser uses the same number, so it is written into the page.
PBKDF2_ITERATIONS = 250_000
# SAVE_PNG: True also writes company_lifecycle_sankey.png (needs the optional kaleido
# package). The PNG is a plain picture, so it is NOT password protected.
SAVE_PNG = False            # the PNG is NOT password protected, do not share it by accident
# --- Ribbon width scaling ----------------------------------------------------
# The ribbon's drawn width is a transformed version of the real company count, so huge
# flows shrink and tiny flows stay visible. Hover text always shows the REAL count.
#   "log"  : width ~ log(1 + count)   strongest compression (default)
#   "sqrt" : width ~ sqrt(count)      gentler compression
#   "none" : width ~ count            true proportions
# Example: 28,000 companies and 1 company differ 28,000x in reality but only about 15x
# on screen with "log", so the single company is still visible.
SCALE = "log"
# MIN_WIDTH_SHARE: no ribbon is drawn thinner than this fraction of the widest ribbon.
MIN_WIDTH_SHARE = 0.02    # no ribbon is drawn thinner than this share of the widest ribbon

# Stage dates stamped exactly at the backfill minute are not real moves, so by default they
# do not qualify a company for the Pre bucket. Set True to count them anyway.
COUNT_BACKFILL_AS_MOVE = False

# The Random success button picks a charted company that
#   * is NOW in the OPP or CUSTOMER bucket,
#   * was not always there: it STARTED below MQL (as a Subscriber or Lead, not created at MQL or SQL),
#   * PASSED THROUGH BOTH MQL AND SQL without skipping a step: its journey has MQL followed directly by SQL,
#     each with its own date, and
#   * was created BEFORE the date RANDOM_CREATED_BEFORE below (YYYY-MM-DD).
# The company's JOURNEY is used (see is_success_journey), not the month-end snapshots, so a company that went
# Lead, MQL, SQL and Opp inside ONE month qualifies. Stages stamped at the same minute are one point of the
# journey, so they count as skipped; a date at the HubSpot backfill minute is not a real move (unless
# COUNT_BACKFILL_AS_MOVE is True). (Created recently = probably still a plain Subscriber, which makes a dull
# example.) The plain Random button is NOT limited by any of this: it can pick any charted company.
RANDOM_CREATED_BEFORE = "2026-09-01"

# MIN_COL_PX: every month gets at least this many pixels of width. If the months do not
# fit on a normal screen the chart becomes wider than the window and scrolls sideways.
MIN_COL_PX = 150          # each month gets at least this many pixels, so labels never touch; wide charts scroll sideways

# Every stage gets its own horizontal band so a box never sits at the same height as a
# different stage in another month. The tallest box of a stage sets the height of its band,
# every box of that stage shares the band's bottom edge, and each band starts BAND_GAP_PX
# below the band above it. The chart grows taller to fit (the chart box scrolls up and down).
# BOX_MAX_PX: pixel height of the single tallest box on the whole chart. Everything else
# is scaled from it. Bigger = a taller chart with bigger boxes.
BOX_MAX_PX = 300          # height in pixels of the tallest box
# BAND_GAP_PX: empty pixels between one stage band and the next.
BAND_GAP_PX = 1           # empty space between one stage band and the next
# BOX_WIDTH_PX: width in pixels of every stage box (the coloured rectangles).
BOX_WIDTH_PX = 32         # width in pixels of each stage box


# The page heading the window starts with. Choosing a client puts the client's name in front of it.
DEFAULT_HEADING = "Funnel Tracking"


# =============================================================================
# THE SETTINGS OF ONE RUN
# =============================================================================
@dataclass
class RunSettings:
    """The settings of ONE run.

    Every field starts as the constant of the same meaning above. The command line (CSV file, --no-dialog,
    --no-open) and the setup window replace some of them for this run only, by making a changed copy, so the
    constants are never overwritten and running twice in one Python session starts from the same settings.
    The field names are the keys the setup window returns.
    """

    password: str = PASSWORD                      # blank = no password
    heading: str = PAGE_HEADING                   # the H1 and the browser tab title
    portal_id: str = HUBSPOT_PORTAL_ID            # blank = company names are not links
    autodetect: bool = AUTODETECT_DATE            # start at the oldest company?
    start: pd.Timestamp = START                   # first date on the chart (ignored when autodetect is on)  # pyright: ignore[reportAssignmentType]
    save_png: bool = SAVE_PNG                     # also write the (unprotected) PNG?
    scale: str = SCALE                            # ribbon width scale: log, sqrt or none
    random_before: str = RANDOM_CREATED_BEFORE    # "Random success" picks companies created before this (YYYY-MM-DD)
    pre_name: str = PRE_BUCKET_NAME               # label of the box for companies created before the start
    csv: str = CSV                                # the HubSpot export to read
    show_dialog: bool = SHOW_DIALOG               # open the setup window first?
    open_browser: bool = True                     # open the finished page in the browser?
    # The moment that names the run's output folder (the setup window replaces it with the Run click time).
    run_time: datetime = field(default_factory=datetime.now)
    # Today at midnight: the right edge of the chart and the base of "3 months ago". Fresh for every run.
    # Set the FUNNEL_ASOF environment variable (for example 2026-10-31) to pin the date, so a rebuild of an older export
    # does not add an empty current month.
    today: pd.Timestamp = field(default_factory=lambda: pd.Timestamp(os.environ.get("FUNNEL_ASOF") or pd.Timestamp.today()).normalize())  # pyright: ignore[reportAssignmentType, reportAttributeAccessIssue]
