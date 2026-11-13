"""The HubSpot accounts LeadCoverage works in, their start dates, and the names made from a client's name."""
from __future__ import annotations

import os
import re
from datetime import date, datetime

from .settings import DEFAULT_HEADING

# --- HubSpot accounts offered in the setup window -------------------------------------
# The "HubSpot portal ID" drop-down in the setup window lists these accounts (name, portal ID), sorted
# alphabetically by name. Choosing one sets HUBSPOT_PORTAL_ID for that run; the first entry of the
# drop-down, "Other - Type ID", lets you type any other portal ID. Left out on purpose: sandboxes, demo
# accounts, webhook integrations, the EASE McLeod UAT migration, GearTrack / Cox, ODW - Taylor and
# Buchanan's training account. Add, rename or remove (name, ID) pairs freely. The name of the account that
# matches HUBSPOT_PORTAL_ID also names the run's output folder (see OUTPUT_ROOT).
HUBSPOT_ACCOUNTS = [
    ("Account Management", "21143463"),
    ("Avathon", "20074161"),
    ("Barrett Distribution", "210573"),
    ("Bridgeway", "50770841"),
    ("Buchanan Hauling", "50613674"),
    ("Century Supply Chain Solutions", "51712495"),
    ("Circle Logistics", "6029765"),
    ("Da Vinci", "21618651"),
    ("Datatruck", "47344444"),
    ("Ease Logistics", "50652750"),
    ("EFL Global", "244533847"),
    ("EFM Global Logistics", "145720674"),
    ("englandlogistics.com", "244636736"),
    ("Gilmer", "50802530"),
    ("GreyOrange Inc.", "7436378"),
    ("Group CRM LIVE", "147219467"),
    ("HEED! Event Logistics", "25637159"),
    ("Highway", "46456425"),
    ("ICAT Logistics, Inc.", "8674942"),
    ("ITF Group", "48053876"),
    ("Knichel Logistics, Inc.", "2602605"),
    ("Larkin Express Logistics LLC", "47202549"),
    ("LeadCoverage", "612489"),
    ("Lean Solutions Group", "6406393"),
    ("Magnus Technologies", "6824531"),
    ("nuVizz", "23571968"),
    ("ODW Logistics", "287536"),
    ("ON Partners", "4231261"),
    ("pittohio.com", "52139903"),
    ("Redwood Logistics", "22284649"),
    ("Sage Freight LLC", "45381661"),
    ("Source Logistics", "47063821"),
    ("Tabi Connect", "50908697"),
    ("The McFarland Group", "39497892"),
    ("Traffix", "49675250"),
    ("Unilog", "20889631"),
    ("USMMG/Alliance/Port X", "51267041"),
    ("W.B. Skinner", "244722849"),
]

# --- Start dates filled in by the setup window -------------------------------------------
# Choosing a client in the setup window's portal drop-down fills the "Start date" box with that client's
# date from this table (portal ID -> "yyyy-mm-dd"). The dates are not shown anywhere else and you can still
# change the box afterwards. Each date is the day LeadCoverage kicked off or got into the client's HubSpot,
# checked against kickoff recaps, Fireflies, Slack and partner-seat messages (Oct 2026). A portal that is not
# listed here (Group CRM LIVE, or "Other - Type ID") leaves the Start date box as it was. The box is ignored
# while "Auto-detect start date" is ticked.
ACCOUNT_START_DATES = {
    "21143463": "2023-02-01",    # Account Management (NFI Industries)
    "20074161": "2026-09-02",    # Avathon
    "210573": "2026-09-02",      # Barrett Distribution
    "50770841": "2026-01-07",    # Bridgeway
    "50613674": "2026-01-13",    # Buchanan Hauling
    "51712495": "2026-10-14",    # Century Supply Chain Solutions
    "6029765": "2022-01-12",     # Circle Logistics
    "21618651": "2026-05-13",    # Da Vinci
    "47344444": "2026-02-06",    # Datatruck
    "50652750": "2025-12-04",    # Ease Logistics
    "244533847": "2026-01-05",   # EFL Global
    "145720674": "2025-02-14",   # EFM Global Logistics
    "244636736": "2026-04-02",   # englandlogistics.com
    "50802530": "2026-07-31",    # Gilmer
    "7436378": "2020-04-27",     # GreyOrange Inc.
    "25637159": "2026-10-12",    # HEED! Event Logistics
    "46456425": "2025-04-25",    # Highway
    "8674942": "2026-03-13",     # ICAT Logistics, Inc.
    "48053876": "2024-11-20",    # ITF Group
    "2602605": "2026-09-04",     # Knichel Logistics, Inc.
    "47202549": "2026-06-26",    # Larkin Express Logistics LLC
    "612489": "2021-01-15",      # LeadCoverage
    "6406393": "2024-01-21",     # Lean Solutions Group
    "6824531": "2025-06-10",     # Magnus Technologies
    "23571968": "2023-01-02",    # nuVizz
    "287536": "2023-03-17",      # ODW Logistics
    "4231261": "2022-01-06",     # ON Partners
    "52139903": "2026-10-09",    # pittohio.com
    "22284649": "2022-07-18",    # Redwood Logistics
    "45381661": "2024-03-13",    # Sage Freight LLC
    "47063821": "2025-11-06",    # Source Logistics
    "50908697": "2026-01-29",    # Tabi Connect
    "39497892": "2026-02-19",    # The McFarland Group
    "49675250": "2026-03-09",    # Traffix
    "20889631": "2025-12-01",    # Unilog
    "51267041": "2026-05-18",    # USMMG/Alliance/Port X
    "244722849": "2026-06-02",   # W.B. Skinner
}

# --- Stage names forced for one account ------------------------------------------------
# The first (Subscriber) box of every chart is labelled with the name the account's own export uses for that stage
# (Subscriber, Prospect, Target ...). Use this table only to show a DIFFERENT name for an account: portal ID ->
# {bucket: name}. The buckets are OTHER, SUBSCRIBER, LEAD, MQL, SQL, OPP and CUSTOMER.
ACCOUNT_STAGE_LABELS = {
    "20889631": {"SUBSCRIBER": "Prospect"},    # Unilog: its HubSpot stage is "Subscriber" but the chart says Prospect
}

# The first entry of the portal drop-down: it shows a box where any other portal ID can be typed.
OTHER_PORTAL_LABEL = "Other - Type ID"


def portal_choices() -> list[tuple[str, str, str]]:
    """List the entries of the portal drop-down, sorted alphabetically by company name.

    The entries come from HUBSPOT_ACCOUNTS. Capitals are ignored when sorting, so "nuVizz" sits
    among the N's. "Other - Type ID" is added by the window itself, above these.

    Returns:
        Tuples ``(label, name, portal_id)``. ``label`` is the text shown in the drop-down, for
        example ``"Unilog (20889631)"``.
    """
    ordered = sorted(HUBSPOT_ACCOUNTS, key=lambda account: account[0].casefold())
    return [(f"{name} ({portal_id})", name, portal_id) for name, portal_id in ordered]


def start_date_for_portal(portal_id: str) -> date | None:
    """Look up the start date stored for a portal in ACCOUNT_START_DATES.

    Args:
        portal_id: The HubSpot portal ID, for example ``"20889631"``.

    Returns:
        The start date as a ``datetime.date``, or None when the portal has no date in the table
        (or the stored text is not a valid yyyy-mm-dd date).
    """
    text = ACCOUNT_START_DATES.get(str(portal_id).strip())
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def stage_label_overrides(portal_id: str) -> dict[str, str]:
    """The stage names forced for an account in ACCOUNT_STAGE_LABELS ({} when there are none).

    Args:
        portal_id: The HubSpot portal ID, for example ``"20889631"``.

    Returns:
        ``{bucket key: name}``, for example ``{"SUBSCRIBER": "Prospect"}``.
    """
    return dict(ACCOUNT_STAGE_LABELS.get(str(portal_id).strip(), {}))


def client_slug(name: str) -> str:
    """Turn a name into lower case words joined by single hyphens, safe to use in a file name.

    Every run of spaces and special characters becomes ONE hyphen, and hyphens at the ends are
    dropped: ``"Century Supply Chain Solutions"`` -> ``"century-supply-chain-solutions"``,
    ``"ICAT Logistics, Inc."`` -> ``"icat-logistics-inc"``. A name with no letters or digits gives ``""``.
    """
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def password_for_client(name: str) -> str:
    """Make the automatic password for a client: lower case, hyphens, then ``-funnel``.

    Every run of spaces and special characters becomes ONE hyphen, and hyphens at the ends are
    dropped: ``"Century Supply Chain Solutions"`` -> ``"century-supply-chain-solutions-funnel"``,
    ``"W.B. Skinner"`` -> ``"w-b-skinner-funnel"``.
    """
    slug = client_slug(name)
    return f"{slug}-funnel" if slug else "funnel"


def heading_for_client(name: str) -> str:
    """Put the client's name in front of the default page heading: ``"Buchanan Hauling Funnel Tracking"``."""
    return f"{name} {DEFAULT_HEADING}"



def client_folder_name(portal_id: str) -> str:
    """Name of the client's folder inside OUTPUT_ROOT, found from the portal ID.

    The portal ID is looked up in HUBSPOT_ACCOUNTS, so the folder carries the name that was picked in the
    setup window's drop-down, written by ``client_slug`` (``"Century Supply Chain Solutions"`` ->
    ``century-supply-chain-solutions``). A portal ID that is not in the list (typed in with "Other - Type ID")
    gives ``portal-<id>``; no portal ID at all gives ``no-client``.
    """
    portal = portal_id.strip()
    for name, portal_id in HUBSPOT_ACCOUNTS:
        if portal_id == portal:
            return client_slug(name) or "client"
    return f"portal-{client_slug(portal) or 'unknown'}" if portal else "no-client"



def make_output_folder(root: str, portal_id: str, run_time: datetime) -> str:
    """Create and return this run's own output folder: ``<root>/<client-name>/<yyyy-mm-dd-hh-mm-ss>``.

    Args:
        root: The folder that holds every run (OUTPUT_ROOT).
        portal_id: The HubSpot portal ID, which gives the client's folder name.
        run_time: The moment Run was clicked (or the script started), in this computer's time.

    The time is ``run_time``. The folder is always NEW:
    if one with that name already exists (two runs in the same second) ``-2``, ``-3`` ... is added, so nothing
    from an earlier run is ever overwritten.

    Returns:
        The path of the new, empty folder.
    """
    base = os.path.join(root, client_folder_name(portal_id), f"{run_time:%Y-%m-%d-%H-%M-%S}")
    folder, number = base, 1
    while True:
        try:
            os.makedirs(folder)                  # creates the client folder too; fails if THIS folder exists
            return folder
        except FileExistsError:
            number += 1
            folder = f"{base}-{number}"

