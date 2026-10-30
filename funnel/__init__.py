"""Funnel Tracking: turns a HubSpot companies export into a password-protected lifecycle Sankey page.

Run it with ``python lcs-graph.py`` (see README.md). The modules, in the order the data flows through them:

    settings      the constants you edit, plus RunSettings (the values of one run)
    clients       the HubSpot accounts, their start dates and the per-client names
    dialog        the setup window
    loader        reads the CSV (only the columns it needs) and checks it
    journeys      which companies are charted, each company's journey, month-end snapshots
    sankey        boxes, ribbons and the Plotly figure
    search_index  one data row per company for the page's search box and popups
    assets        the page's code, styles and Plotly library (minified) in the assets folder
    page          the final HTML page, encrypted with the password
    cli           the command line and the order of the steps
"""

__version__ = "1.0.0"
