# Funnel Tracking

A HubSpot lifecycle Sankey dashboard generator, by Phil Mann at LeadCoverage (phil.m@leadcoverage.com).

```text
"Funnel Tracking": a HubSpot lifecycle Sankey dashboard generator
By Phil Mann at LeadCoverage phil.m@leadcoverage.com
===============================================================================

PURPOSE
-------
Reads a HubSpot COMPANIES export (a CSV file) and turns it into ONE password-protected web
page (index.html, with a small assets folder next to it). The page shows how every company moved
through the lifecycle funnel (Subscriber -> Lead -> MQL -> SQL -> Opp -> Customer)
month by month, as a Sankey diagram, with a search box, "Random" buttons, clickable
stage boxes and links back to the HubSpot records.

WHAT YOU GET
------------
Every run writes into its OWN new folder, so an older run is never overwritten or deleted:
      <client-name>/<yyyy-mm-dd-hh-mm-ss>/        (created next to this script; see OUTPUT_ROOT)
and that folder holds:
  index.html                        The password screen with the whole dashboard (headings, chart,
                                    ALL the company data) encrypted inside it with PASSWORD
                                    (about 10 MB for 34,000 companies).
  assets/funnel.js, funnel.css      The page's code and styles, minified. They contain NO company
  assets/plotly.min.js              data, the page hands the data to them at run time. They are
                                    NOT password protected. plotly.min.js is the public Plotly library.
                                    UPLOAD index.html AND the assets folder together.
  company_lifecycle_sankey.png      Optional static picture (only if SAVE_PNG = True).
                                    NOT password protected.
How the folder is named:
  * client-name: the client is found from the portal ID (HUBSPOT_PORTAL_ID) in the HUBSPOT_ACCOUNTS list, so it
    is the name picked in the setup window's drop-down, in lower case with every run of spaces and special
    characters turned into ONE hyphen ("Century Supply Chain Solutions" -> century-supply-chain-solutions).
    A portal ID that is typed in ("Other - Type ID") and is not in the list gives portal-<id>; no portal at all
    gives no-client.
  * yyyy-mm-dd-hh-mm-ss: the moment the Run button was clicked in the setup window (without the window: the
    moment the script started), in this computer's time. If that folder already exists, -2, -3 ... is added.
  Example:  unilog/2026-10-29-14-05-32/index.html   and   unilog/2026-10-29-14-05-32/assets/funnel.js

QUICK START
-----------
  1. Install the packages (see the PIP INSTALL GUIDE just below).
  2. Have the HubSpot export ready (a CSV). You pick it in the setup window; if a file named
     all-companies.csv sits next to this script it is pre-selected, and a path given on the
     command line is pre-selected too:  python lcs-graph.py "C:\\path\\to\\export.csv"
  3. One time per client, edit the "USER DEFINED CONSTANTS" block at the top of funnel/settings.py
     (stage buckets, labels, colors ...). The client list and start dates are in funnel/clients.py.
  4. Run it:   python lcs-graph.py        (options: see COMMAND LINE below)
  5. A SETUP WINDOW opens (see THE LAUNCH WINDOW below). Fill it in and press Run.
  6. index.html and the assets folder are written into this run's own folder (<client-name>/<date-time>/ next
     to the script), and index.html opens in your browser. To share it, upload BOTH index.html and the
     assets folder from that folder to the same place on your web host (the page shows a message if the
     folder is missing).

COMMAND LINE
------------
  python lcs-graph.py [CSV] [--no-dialog] [--no-open] [--version] [--help]
      CSV           the HubSpot export (default: all-companies.csv next to this script).
                    A relative path is taken from the folder you run the command in.
      --no-dialog   skip the setup window and use the constants as written (SHOW_DIALOG = False).
      --no-open     do not open the finished page in the browser (handy for scheduled runs).
      --version     print the version and stop.   --help   print this list and stop.
  Exit codes: 0 = the page was written, 1 = a problem (a message says what), 130 = Ctrl+C.

THE LAUNCH WINDOW
-----------------
Every time the script starts (while SHOW_DIALOG = True) a small window asks for:
      Start date               (bold, at the top) calendar picker; default = first day of the
                               PREVIOUS quarter
      Auto-detect start date   tick to start at the oldest company
      Password                 blank = no password (you are asked to confirm)
      Page heading             default "Funnel Tracking"
      HubSpot portal ID        drop-down of the accounts in HUBSPOT_ACCOUNTS, in alphabetical order;
                               nothing selected = company names are not links. The first entry,
                               "Other - Type ID", shows a box where you type any other portal ID
      Save PNG                 tick to also save a picture (NOT password protected)
      Ribbon scale             log, sqrt or none
      HubSpot export (CSV)     file picker
      Random Success picks companies created before
                               (italic) calendar picker; only the Random success
                               button uses it, the Random button can pick any charted company;
                               default = 3 months before today
      Pre-bucket name          (at the bottom) the label of the extra box for companies created before
                               the start date; starts as PRE_BUCKET_NAME
Choosing a client in the portal drop-down also fills in other fields. The Start date box is set to the
client's date from ACCOUNT_START_DATES (the table sits under HUBSPOT_ACCOUNTS; the dates are not shown in
the drop-down, you can change the box afterwards, and it is ignored while auto-detect is ticked). Two
more fields are filled only while they are still at their defaults: a heading of "Funnel Tracking" becomes "<Client> Funnel Tracking", and a
blank password becomes the client name in lower case, with every run of spaces and special
characters turned into one hyphen, plus "-funnel" (Century Supply Chain Solutions ->
century-supply-chain-solutions-funnel); the Show box is then ticked so the password can be read. A
heading or password you typed yourself is never changed. A password made this way can be guessed
by anyone who knows the client's name, so replace it when the data matters.
What you choose REPLACES the matching constants for that run only (PASSWORD, PAGE_HEADING,
HUBSPOT_PORTAL_ID, AUTODETECT_DATE, START, SAVE_PNG, SCALE, RANDOM_CREATED_BEFORE, PRE_BUCKET_NAME
and the CSV file). The moment you press Run is remembered too: it names the run's output folder (see
WHAT YOU GET). Everything else still comes from the constants block. Press Cancel (or close the
window) to stop without generating anything. Set SHOW_DIALOG = False to skip the window and
use the constants as written. If no window can be opened (no tkinter, or a computer with no
screen) the script says so and uses the constants block instead.

PIP INSTALL GUIDE
-----------------
  Step 1. Check your Python version. You need Python 3.9 or newer (built and tested on
          3.12 and 3.14):
              python --version
  Step 2. (Recommended) upgrade pip itself:
              python -m pip install --upgrade pip
  Step 3. Install the four required packages with ONE command:
              python -m pip install pandas numpy plotly cryptography
  Step 4. OPTIONAL. Only needed if you set SAVE_PNG = True (it draws the PNG):
              python -m pip install kaleido
              plotly_get_chrome        <- one-time download of the browser kaleido uses
  Step 5. OPTIONAL, recommended. Gives the setup window real calendar pop-ups for its date
          fields (without it the dates use simple year / month / day drop-downs):
              python -m pip install tkcalendar
  Step 6. OPTIONAL, recommended. Shrinks the page's code and styles (level 1: comments and
          spacing removed):
              python -m pip install rjsmin rcssmin
  Step 7. OPTIONAL. Level 2 also renames local variable and function names to short letters.
          It needs Node.js (nodejs.org) and then, once:
              npm install -g terser
          The script finds it by itself and never downloads it. Without it, level 1 is used.
  Step 8. Check that everything imports:
              python -c "import pandas, numpy, plotly, cryptography; print('all good')"

  What each package is for:
      pandas        reads the CSV and does all the date handling
      numpy         fast number arrays (the month-by-month stage table)
      plotly        draws the Sankey diagram and supplies the JavaScript chart library
                    that is embedded in index.html
      cryptography  AES-GCM encryption for the password lock
      kaleido       (optional) turns the chart into a PNG file
      tkcalendar    (optional) calendar pop-ups in the setup window
      rjsmin, rcssmin  (optional) level 1 minifying of the page code and styles
      terser        (optional, a Node tool, not a Python package) level 2 minifying
      tkinter       draws the setup window. It is part of Python itself (nothing to pip
                    install). On Windows and macOS it is included with the python.org
                    installer. On Linux install it with:  sudo apt install python3-tk

  Tested with: Python 3.12 / 3.14, pandas 3.0, numpy 2.4, plotly 7.1,
               cryptography 46.0, kaleido 1.5.
               Older releases usually work too (pandas 2.x, plotly 5.x/6.x).

  Equivalent requirements.txt  (then run:  python -m pip install -r requirements.txt):
      pandas
      numpy
      plotly
      cryptography
      kaleido        # optional
      tkcalendar     # optional
      rjsmin         # optional
      rcssmin        # optional

  WINDOWS TIPS
      * Always write "python -m pip" instead of plain "pip". That guarantees the packages
        are installed into the SAME Python that runs the script. If you have several
        Pythons, use the full path, for example:
            "C:\\Users\\you\\AppData\\Local\\Python\\pythoncore-3.14-64\\python.exe" -m pip install pandas numpy plotly cryptography
      * "py -m pip install ..." also works if the Python launcher is installed.
      * In VS Code, the interpreter shown in the bottom-right corner must be the same
        Python. Change it with Ctrl+Shift+P -> "Python: Select Interpreter".
      * If the editor underlines an import in red but the script runs, VS Code is simply
        looking at a different Python than the one you install into.
  OPTIONAL: keep this project's packages separate in a virtual environment:
      python -m venv .venv
      .venv\\Scripts\\activate            (macOS/Linux: source .venv/bin/activate)
      python -m pip install pandas numpy plotly cryptography

INPUT FILE REQUIREMENTS
-----------------------
A HubSpot companies export with these columns (exact HubSpot names):
      Record ID, Company name, Company Domain Name, Create Date, Lifecycle Stage
For the journeys you also need, for every stage the client uses:
      Date entered "<stage> (Lifecycle Stage Pipeline)"        e.g. Date entered "Lead (Lifecycle Stage Pipeline)"
      Date entered current stage                                (optional, shown in the lists)
Without the "Date entered" columns a company can only be drawn in the stage it is in
now (the script prints a WARNING in that case).

HOW TO USE IT FOR ANOTHER CLIENT
--------------------------------
  1. Export that client's companies from HubSpot (include the "Date entered" properties).
  2. Save it as all-companies.csv next to the script.
  3. Edit the "USER DEFINED CONSTANTS" block in funnel/settings.py for the things the setup window does not ask
     about: the six stage buckets, LABELS and the colors (and the heading, portal ID, start date,
     password and PRE_BUCKET_NAME too if you run with SHOW_DIALOG = False).
  4. Run the script and read the printed "Buckets" list and any WARNING lines. If a stage
     is reported as "in no bucket", add its name to one of the buckets and run again.
  5. The result is in <client-name>/<yyyy-mm-dd-hh-mm-ss>/ next to the script (the console prints the
     exact folder). Running again never touches that folder: it makes a new one.

HOW IT WORKS (the seven steps, in the order the code runs)
-----------------------------------------------------------
  [0]   The launch window (optional) collects the settings for this run; the moment Run is
        clicked names this run's output folder (<client-name>/<yyyy-mm-dd-hh-mm-ss>/).
        (At the end, step 7 also writes the assets folder: the page code and styles are
        minified, given a copyright notice, and saved as separate public files.)
  [1/7] Load and check the CSV, build the stage lookup, find the start date and the
        HubSpot "backfill" stamp.
  [2/7] Filter: decide which companies are charted (created after the start date, plus
        older companies that moved to MQL or above after it = the "Pre" bucket).
  [3/7] Build each company's journey: a list of (date, stage level) points.
  [4/7] Take a snapshot of every company's stage at the end of every month.
  [5/7] Build the Sankey boxes ("nodes") and ribbons ("links") and lay them out in
        horizontal bands, one band per stage.
  [6/7] Draw the chart with Plotly (the counts of each month on top, the month names at the
        bottom, month lines; the month names on top are a frozen row the page adds, see
        MOVING AROUND THE CHART).
  [7/7] Build the search data, wrap everything in the HTML page, encrypt it with the
        password and write index.html and the assets folder into this run's own folder.

READING THE BOX LABELS
----------------------
Every stage box shows two numbers, for example:
      Lead  287
      (300)
  287  = companies that are IN the stage at the end of that month.
  (300) = companies that have EVER been in that stage up to and including that month
          (always at least the first number, and it never drops from one month to the next).
The second number is based on each company's journey, so a company that passed through a
stage between two month ends still counts. A company created above the bottom stage is
counted as having started in Subscriber (its line rises from the bottom).
Click a box to open a popup that lists its companies. The switch at the top of the popup
chooses the group:
  * "In the stage at month end" (the first number),
  * "Ever been in the stage" (the bracketed number, which also lists companies that have since moved on),
  * "Only in stage for this month": companies that ENTERED the stage during the month shown and LEFT it on
    or before the last day of the NEXT month (for June: entered on or after 1 June, left on or before
    31 July). Each line also shows the day it left. A company that is still in the stage has not left, so it
    is not listed. (A company created above the bottom stage counts as passing through Subscriber on its
    first day, so it appears in that stage's list.)
The Pre box has no such groups, so the switch is hidden there.
Under the filter box, the "Show only" check boxes (Now Opp, Now Cust, Now SQL, Now MQL, Now Lead, Now Sub,
Now Other) limit the list to companies whose CURRENT stage is ticked; tick several to see any of them.
"Now Other" means a current stage that is in no bucket. Select All and Select None tick or untick every box.
Every popup starts with all boxes ticked; they stay as they are while you switch between the three groups.
The popup can be sorted: "Sort by" Lexical (A to Z by name), Created (create date) or Entered Stage (date
entered the stage), and Ascd or Desc (the Pre box has no date entered, so that button is off there). A
company that entered the stage during the month shown gets a red asterisk after its name; the date it
entered the stage is shown on its line.

WHEN YOU SELECT A COMPANY
-------------------------
The panel under the search box shows, from left to right and top to bottom:
  * the company LOGO (if the export has a "Logo URL" column; see LOGO_URL_COLUMN). It links to
    the company's website (its domain) and opens in a new window. UNDER it sits the agency
    logo (AGENCY_LOGO_URL), which links to AGENCY_SITE_URL, also in a new window. When a company
    has no logo (or its logo does not load) a blank 64 pixel place is kept for it, so the agency logo
    never moves. The logos float at the left: the first lines of text run along their right side, and
    below them the text continues all the way to the left margin,
  * the name (a link to its HubSpot record), domain, Record ID, created date and current stage,
  * the month-end path, with the stages it only passed through inside a month marked "passed through"
    (or the reason the company is not on the chart),
  * extra DETAIL lines: the HubSpot columns listed in DETAIL_LINES in the constants block
    (company owner, industry, type, associated contacts and deals, conversions, last activity
    dates, traffic sources, session counts, deal amounts ...). A value of ZERO counts as blank,
    for every number property, and is never shown or stored in the page.
    Only values that are not blank are shown. A column the export does not have is skipped (the
    script prints which ones). ALL the details are in ONE <dl> (a little smaller than the rest of
    the panel); every label (<dt>) and value (<dd>) pair sits in its own <div>. The groups of
    DETAIL_LINES only set the ORDER (all the "First ..." fields together, all the "Last ..." fields
    together) and never start a new line: a line breaks only BETWEEN whole pairs, when the next pair
    no longer fits, and the pairs otherwise run along to the margin; a single pair that is longer
    than a whole line wraps inside itself.
The company logo is loaded from its web address when you look at the page, so the viewer needs
internet for it. If the address does not load, the logo's place simply stays blank. The agency logo is
different: the script downloads it ONCE when it runs and builds it into the page, so it always
shows (if that download fails the page loads it from the web instead and the saved picture
leaves it out).

THE RANDOM BUTTONS AND THE JOURNEY HIGHLIGHT
--------------------------------------------
"Random" selects any charted company. "Random success" selects a company that
  * is NOW an Opportunity or a Customer,
  * was not always one: it STARTED below MQL (as a Subscriber or Lead, not created at MQL or SQL),
  * PASSED THROUGH BOTH MQL AND SQL without skipping a step (MQL followed directly by SQL, each with its own date),
  * and was created before the date asked for in the setup window (RANDOM_CREATED_BEFORE).
The pink highlight follows the selected company's journey box by box. The boxes show where a company is at the
END of each month, so a company that moves through several stages inside one month would look as if it jumped.
The highlight therefore also outlines the stages it only passed THROUGH during a month: a company that was a Lead
at the end of May and went MQL, SQL and Opp in June gets all of them outlined (Lead in May, then MQL, SQL and Opp in
June, joined by a straight line inside June's column). The "Month-end path" text lists them too, for example
"MQL (Jun 2026, passed through)". Stages stamped by HubSpot at the same minute are one step, so a company that
really jumped still shows a jump.

MOVING AROUND THE CHART
-----------------------
The page is exactly as tall as the browser window: the title and the search bar stay at the top and the chart
sits in its own box below them, which takes the rest of the window. That box ALWAYS shows both scroll bars
(sideways along the bottom, up and down along the right edge), even when the whole chart would fit. The chart
starts scrolled as far UP and as far RIGHT as it can go, so the newest months are in view first.
Four round compass arrows float over the bottom right corner of the box. Each one jumps to an edge:
top-most (N, up), left-most (W), bottom-most (S, down) and right-most (E). An arrow only changes its own
direction (N and S move up and down, W and E move sideways) and fades out while you are already at that edge.
The scroll bars are drawn by the page in Chrome, Edge and Safari. Firefox follows the system setting, so on a Mac
that hides scroll bars automatically they may only appear while you scroll.
The month names (and the Pre bucket name) are frozen: they sit in one row just above the counts at the top of
the chart and stay at the top of the chart box while you scroll up and down (they scroll sideways with the
chart). The counts under them (+new, carried-over, total) scroll away as usual. The last month is the month so
far; it is not marked "(to date)".

THE CAMERA BUTTON
-----------------
Once a company is selected a camera button appears next to Clear. It saves ONE PNG picture of
the page: the heading, one line with the note and the credit line, the selected company's panel
(logos, details, path and the extra detail lines) and the chart with the pink highlight. The credit line in the
picture reads "Created by <PICTURE_CREATED_BY> on <date and time>" (the page keeps the person's
name). The picture is about as many pixels wide as the chart is on the screen (PICTURE_SCALE = 1;
use 2 for a sharper but 4 times bigger file). The search box and buttons
are not part of the picture. In Chrome and Edge a "Save as" window opens so you choose the
folder and file name; other browsers download the file in the normal way. If the logo's server
does not allow it (HubSpot's logo server does not), the logo is shown on the page but cannot be
put into the picture; the text then simply starts at the left edge.
FIREFOX PRIVACY NOTE: Firefox's fingerprinting protection ("resist fingerprinting", also used by
some privacy add-ons) scrambles any picture made through a canvas into a square of NOISE. The page
tests for this before saving. If the protection is on, it saves an SVG picture instead of a PNG
(a vector drawing built from text and the chart's own drawing, no logo; open it in any browser).
To get a PNG anyway: when Firefox asks about "canvas data" choose Allow and click the camera
again, switch the protection off for this page, or use Chrome or Edge.

SECURITY NOTES
--------------
  * The password protects the page by ENCRYPTION (AES-256-GCM, key from PBKDF2-HMAC-
    SHA256 with 250,000 rounds). The company data cannot be read from the page source
    without it. A weak password can still be guessed, so use a long one.
  * The page tells search engines not to index it (robots meta tag). That is a request,
    not a lock. The password is the real protection.
  * The assets folder is NOT protected: anyone who knows its address can read funnel.js, funnel.css
    and plotly.min.js. They hold only code, styles and the public Plotly library (the page
    code receives the company data as an argument from INSIDE the encrypted page, and the data
    is not left in a global variable). A scan for the heading, portal ID, e-mail, client names
    and company names found none of them in these files. Minifying and renaming only make the code
    harder to read; anyone who has the PASSWORD can still read and copy everything the browser runs,
    including the data. For that you would need per-person access, which is not built.
  * The copyright notices (a banner and short text lines in funnel.js and funnel.css, one Base64
    copy, and "noai, noimageai" in the robots tag) are plain, honest text. They are a deterrent,
    not a lock: they can be removed in seconds and many AI assistants treat text inside pasted
    code as data. No invisible characters are used (security tools treat those as an attack).
  * The PNG (if you enable it) is NOT protected. Do not share it by accident. The same goes for
    pictures saved with the camera button: they contain the selected company's details.
  * Logos are fetched from the servers named in the "Logo URL" column (mostly HubSpot) when a
    company is selected, so those servers can see the viewer's IP address. The address of the
    page itself is not sent (the images are loaded with no-referrer).
  * The page contains the name, domain and Record ID of every company in the export.
    Check who may see that before you share it.
  * Every run keeps its own folder and the script never deletes an old one. Each folder holds the company
    data of that run (encrypted in index.html), so delete the folders you no longer need and upload only the
    folder you mean to share.

TROUBLESHOOTING
---------------
  "The password feature needs the cryptography package"
        -> python -m pip install cryptography   (use the same Python as for the script)
  "The CSV is missing these HubSpot columns: [...]"
        -> the export lacks a required column; add it in HubSpot and export again.
  "WARNING: these stages are in the export but in no bucket"
        -> add those stage names to a bucket in the constants block.
  "WARNING: no 'Date entered' column in the export for: [...]"
        -> add those properties to the HubSpot export for full journeys.
  "Skipping N empty month(s) at the start"
        -> normal. Months before the first company exists are left out of the chart.
  "Setup window unavailable (...)"
        -> tkinter is missing or there is no screen. Install it (see the pip guide), or set
           SHOW_DIALOG = False and put the values in the constants block.
  The setup window is not visible
        -> it can open behind the editor. Look in the taskbar, or press Alt+Tab.
  "Agency logo: could not download it" when the script runs
        -> no internet at that moment, or the address is blocked. The page then loads the logo from
           the web, and it is left out of saved pictures. Run the script again when online.
  The camera button saves a picture without the logo
        -> normal for logos on HubSpot's servers (see THE CAMERA BUTTON). The logo is still shown on the page.
  The camera button saved an .svg file instead of a .png
        -> your browser blocks reading canvas pixels (see FIREFOX PRIVACY NOTE). The SVG is a normal
           picture: open it in a browser. Allow canvas data for the page (or use Chrome/Edge) for a PNG.
  The camera button does not offer a "Save as" window
        -> only Chrome and Edge can. Other browsers download the picture (check their download setting).
  After the password the page says "The page files could not be loaded"
        -> the assets folder is not next to index.html on the web host. Upload the whole folder.
  The page opens but shows only the password box
        -> enter the password. It must be opened over https:// or as a local file.
  Where is my output?
        -> in <client-name>/<yyyy-mm-dd-hh-mm-ss>/ next to the script (the console prints the exact folder).
           A client that is not in HUBSPOT_ACCOUNTS gives portal-<id>, and no portal gives no-client.

HOW THE CODE IS ORGANIZED
-------------------------
  lcs-graph.py          The launcher: checks Python and the packages, then runs the program. Keep it next to the
                        funnel folder.
  funnel/settings.py    USER DEFINED CONSTANTS (the block you edit) and RunSettings, the values of ONE run.
  funnel/clients.py     The HubSpot accounts shown in the setup window, each client's start date, and the names
                        made from a client's name (folder, heading, password).
  funnel/dialog.py      The setup window.
  funnel/loader.py      Step 0 and 1: checks the bucket settings, reads the CSV (only the columns it needs).
  funnel/journeys.py    Step 2 to 4: which companies are charted, each company's journey, month-end snapshots.
  funnel/sankey.py      Step 5 and 6: boxes, ribbons and the Plotly figure.
  funnel/search_index.py  Step 7, first part: one data row per company for the search box and the popups.
  funnel/assets.py      Step 7, second part: the page's code, styles and Plotly library in the assets folder.
  funnel/page.py        Step 7, last part: the final page, encrypted with the password.
  funnel/cli.py         The command line and the order in which the steps run.
  funnel/context.py     The values the steps hand to each other.
  funnel/web/           The page itself as real files: funnel.js, funnel.css, page.html and lock.html. Edit them
                        like any web file; the program reads them every run.
Importing any of these files does no work: nothing opens, reads a file or exits until main() runs. The settings
of a run live in one RunSettings object that is passed along, so nothing global is overwritten.

CODE CHECKS (for anyone who changes the script)
-----------------------------------------------
  python -m pip install pytest ruff pyright           (once)
  python -m pytest                                    runs test_lcs_graph.py (fast, needs no internet)
  python -m ruff check lcs-graph.py funnel test_lcs_graph.py
  pyright
The settings for all three are in pyproject.toml. requirements.txt lists what the script itself needs.
```
