// All page behaviour lives inside this one function. The page calls it with the data written by
// Python (company rows, month names, stage names, box numbers ...) as soon as this file has loaded.
// So no variable leaks into the global scope, and the data is never left in a global variable.
window.__fs = function (DATA) {
  var _n = "__NOTICE_FULL__";
  // rows: one array per company (the column order is documented in the Python code).
  // STAGE: the six stage names. MONTHS: the month names, one per chart column.
  var rows = DATA.rows, STAGE = DATA.stages, MONTHS = DATA.months;
  // The Plotly chart element and the main page elements we need to talk to.
  var gd = document.getElementById("sankey-plot");
  var q = document.getElementById("q"), sug = document.getElementById("sug");
  var info = document.getElementById("info"), svg = document.getElementById("ov");
  var wrap = document.getElementById("wrap");
  // Color of the pink highlight line and outlines.
  var HI = DATA.highlight;
  // Lower-case [name, domain] for every row, computed once so searching is fast.
  var lower = rows.map(function (r) { return [r[0].toLowerCase(), r[1].toLowerCase()]; });
  // current: row number of the company being shown (null = none). matches: latest search result.
  var current = null, matches = [];

  /**
   * Reduce a web address to just its domain so "https://www.acme.com/page" matches "acme.com".
   * @param {string} s Text typed by the user (already lower case).
   * @return {string} The domain part only.
   */
  function normDomain(s) {
    return s.replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/[\/?#].*$/, "");
  }

  /**
   * Find companies whose name or domain matches the typed text.
   * Order of the result: exact matches, then "starts with", then "contains".
   * @param {string} text What the user typed.
   * @return {{all: number[], exact: number}} Row numbers (best first) and the exact-match count.
   */
  function search(text) {
    var t = text.trim().toLowerCase();
    if (!t) return { all: [], exact: 0 };
    var d = normDomain(t);
    var exact = [], starts = [], inc = [];
    for (var i = 0; i < rows.length; i++) {
      var n = lower[i][0], dm = lower[i][1];
      if (n === t || (d && dm === d)) exact.push(i);
      else if (n.indexOf(t) === 0 || (d && dm.indexOf(d) === 0)) starts.push(i);
      else if (n.indexOf(t) !== -1 || (d && dm.indexOf(d) !== -1)) inc.push(i);
    }
    return { all: exact.concat(starts, inc), exact: exact.length };
  }

  /**
   * Describe a company's current stage, e.g. "Opportunity since 2026-02-23 (backfill date)".
   * @param {Array} r One company row.
   * @return {string} Text for the lists and the info line.
   */
  function stageSince(r) {
    return (r[5] || "no stage") + (r[8] ? " since " + r[8] + (r[9] ? " (backfill date)" : "") : "");
  }

  /**
   * Small helper that creates an HTML element with a class and plain text.
   * (textContent is used on purpose: company names can never inject HTML.)
   * @param {string} tag Element name, e.g. "div".
   * @param {string} cls CSS class (or "").
   * @param {string} [text] Text content.
   * @return {HTMLElement} The new element.
   */
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  /**
   * Fill the drop-down under the search box with the best matches (first 12).
   * @param {number[]} all Row numbers of the matching companies.
   */
  function renderSuggestions(all) {
    sug.innerHTML = "";
    if (!all.length) {
      if (q.value.trim()) { sug.appendChild(el("div", "item", "No matches")); sug.style.display = "block"; }
      else sug.style.display = "none";
      return;
    }
    all.slice(0, 12).forEach(function (i) {
      var r = rows[i];
      var d = el("div", "item");
      d.appendChild(el("b", "", r[0] || "(no name)"));
      d.appendChild(el("span", "sub", "   " + (r[1] || "no domain") + "   |   " + stageSince(r) +
                                      "   |   Created " + r[3]));
      if (r[6]) d.appendChild(el("span", "nc", "   |   not in chart"));
      // mousedown (not click) so the choice registers before the search box loses focus
      d.addEventListener("mousedown", function (ev) { ev.preventDefault(); choose(i); });
      sug.appendChild(d);
    });
    if (all.length > 12) sug.appendChild(el("div", "item sub", all.length - 12 + " more, keep typing to narrow"));
    sug.style.display = "block";
  }

  /**
   * Turn a month-by-month stage string into readable runs, e.g.
   * "Lead (Dec 2025 to Jul 2026)" ">" "SQL (Aug 2026 to Oct 2026)". A stage the company only passed THROUGH inside
   * one month is listed in its place, e.g. "MQL (Aug 2026, passed through)", so the path does not look as if it jumped.
   * @param {string} snap One character per month: "-" = not created yet, otherwise the stage level.
   * @param {number[]} [via] The stages passed through inside a month: [month, stage, month, stage, ...] in order.
   * @return {string[]} One text per run of identical stages.
   */
  function runs(snap, via) {
    var out = [], k = 0, v = 0, stopMonths = {};
    via = via || [];
    for (var s2 = 0; s2 < via.length; s2 += 2) stopMonths[via[s2]] = true;
    while (k < snap.length) {
      // the stages passed through during month k come before that month's own (month-end) stage
      while (v + 1 < via.length && via[v] === k) {
        out.push(STAGE[via[v + 1]] + " (" + MONTHS[k] + ", passed through)");
        v += 2;
      }
      var c = snap[k], j = k;
      while (j + 1 < snap.length && snap[j + 1] === c && !stopMonths[j + 1]) j++;
      if (c !== "-") out.push(STAGE[+c] + " (" + (k === j ? MONTHS[k] : MONTHS[k] + " to " + MONTHS[j]) + ")");
      k = j + 1;
    }
    return out;
  }

  /**
   * Turn the logo stored in a row back into a web address.
   * @param {Array} r One company row.
   * @return {string} The logo address, or "" when there is none (or it is not an http/https address).
   */
  function logoFor(r) {
    var t = r[13];
    if (!t || t.length !== 2) return "";
    var url = t[0] >= 0 ? DATA.logoPrefixes[t[0]] + t[1] : t[1];
    return /^https?:\/\//i.test(url) ? url : "";
  }

  /**
   * Make a web address from a company's domain name, for the link on its logo.
   * @param {string} domain The domain as stored in the export (for example "acme.com").
   * @return {string} "https://acme.com", or "" when there is no usable domain.
   */
  function domainLink(domain) {
    var d = String(domain || "").trim().replace(/^https?:\/\//i, "").replace(/\/.*$/, "");
    return /^[A-Za-z0-9][A-Za-z0-9.\-]*\.[A-Za-z]{2,}$/.test(d) ? "https://" + d : "";
  }

  /**
   * Work out everything shown about a company, as plain data. The text under the search box
   * and the downloaded picture are both drawn from this, so they always say the same thing.
   * @param {number} i Row number of the company.
   * @return {{name: string, rest: string, second: string, details: Array, logo: string, link: string}}
   *     name: the company name. rest: domain, Record ID, created date and current stage.
   *     second: the month-end path (or the reason the company is not on the chart).
   *     details: one list of [label, value] pairs that are not blank (in the order of DETAIL_LINES).
   *     logo: the logo web address ("" when there is none).
   *     link: the company's website address ("" when it has no usable domain).
   */
  function infoModel(i) {
    var _n = "__NOTICE_SHORT__";
    var r = rows[i];
    var model = {
      name: r[0] || "(no name)",
      rest: "   " + (r[1] || "no domain") + "   |   Record ID " + r[2] +
            "   |   Created " + r[3] + "   |   Current stage: " + stageSince(r),
      second: "",
      details: [],
      logo: logoFor(r),
      link: domainLink(r[1])
    };
    if (r[6]) {
      // A company that is not on the chart only gets the reason, no path.
      model.second = r[6];
    } else {
      var trail = runs(r[4], r[16]);
      if (r[7]) trail.unshift(DATA.preName + " (created " + r[3] + ")");
      model.second = "Month-end path: " + trail.join("  >  ");
    }
    // The details are stored as [field number, value, field number, value, ...]. A value that
    // is a number means "look this text up in the shared list" (DATA.strs).
    var d = r[12], byField = {};
    if (d && d.length) {
      for (var k = 0; k + 1 < d.length; k += 2) {
        var v = d[k + 1];
        byField[d[k]] = (typeof v === "number") ? DATA.strs[v] : v;
      }
      // One flat list of the pairs this company has, group after group. The groups only decide the order;
      // they do not start new lines.
      DATA.detailGroups.forEach(function (group) {
        group.forEach(function (fi) {
          if (byField[fi] !== undefined) model.details.push([DATA.detailLabels[fi], byField[fi]]);
        });
      });
    }
    return model;
  }

  /**
   * Write the company panel under the search box: the logo column (company logo with the
   * agency logo under it), the name (a HubSpot link when a portal ID was configured), details,
   * month-end path, and the extra detail lines.
   * The company logo links to the company's website and the agency logo to the agency's site,
   * both in a new window.
   * @param {number} i Row number of the company.
   */
  function showInfo(i) {
    var _n = "__NOTICE_SHORT__";
    var r = rows[i], m = infoModel(i);
    info.innerHTML = "";
    var holder = el("div", "inforow");
    // --- the logo column, floated at the left so the text runs along it and, below it, on to the left margin.
    // The company logo has a fixed 64 px place: when there is no logo (or it does not load) that place stays
    // blank, so the agency logo under it never moves. ---
    var col = el("div", "logocol");
    if (m.logo) {
      // A link to the company's website when it has a domain, otherwise a plain box. The logo is
      // an ordinary image tag; its place stays blank if the address does not load, and the page
      // address is not sent along (no-referrer).
      var box = el(m.link ? "a" : "div", "logobox");
      if (m.link) {
        box.href = m.link;
        box.target = "_blank";
        box.rel = "noopener noreferrer";
        box.title = "Open " + m.link.replace("https://", "") + " in a new window";
      }
      var img = document.createElement("img");
      img.referrerPolicy = "no-referrer";
      img.alt = "";
      img.onerror = function () { box.style.visibility = "hidden"; };      // hidden, but its place stays
      img.src = m.logo;
      box.appendChild(img);
      col.appendChild(box);
    } else if (DATA.agencyLogo) {
      col.appendChild(el("div", "logogap"));                               // blank place for the missing company logo
    }
    if (DATA.agencyLogo) {
      var agencyLinked = /^https?:\/\//i.test(DATA.agencyLink || "");
      var agency = el(agencyLinked ? "a" : "div", "agencylogo");
      if (agencyLinked) {
        agency.href = DATA.agencyLink;
        agency.target = "_blank";
        agency.rel = "noopener noreferrer";
        agency.title = "Open " + DATA.agencyLink.replace(/^https?:\/\//i, "") + " in a new window";
      }
      var agencyImg = document.createElement("img");
      agencyImg.referrerPolicy = "no-referrer";
      agencyImg.alt = "Agency logo";
      agencyImg.onerror = function () { agency.style.display = "none"; };
      agencyImg.src = DATA.agencyLogo;
      agency.appendChild(agencyImg);
      col.appendChild(agency);
    }
    if (col.childNodes.length) holder.appendChild(col);

    // --- the text: name and facts, path, details ---
    var text = el("div", "infotext");
    var head = el("div", "");
    if (DATA.hubspotBase && r[2]) {
      var link = el("a", "", m.name);
      link.href = DATA.hubspotBase + encodeURIComponent(r[2]);
      link.target = "_blank";
      link.rel = "noopener";
      link.style.fontWeight = "bold";
      link.title = "Open this company in HubSpot";
      head.appendChild(link);
    } else {
      head.appendChild(el("b", "", m.name));
    }
    head.appendChild(document.createTextNode(m.rest));
    text.appendChild(head);
    text.appendChild(el("div", "path", m.second));
    // The extra details: ONE <dl> holding every label/value pair. Each pair is its own <div> holding one
    // <dt> (the label) and one <dd> (the value); the CSS lets a line break only between pairs.
    if (m.details.length) {
      var dl = el("dl", "detail");
      m.details.forEach(function (pair) {
        var item = el("div", "");
        item.appendChild(el("dt", "", pair[0]));
        item.appendChild(el("dd", "", pair[1]));
        dl.appendChild(item);
      });
      text.appendChild(dl);
    }
    holder.appendChild(text);
    info.appendChild(holder);
  }
  /**
   * Make an rgba color 70% more transparent (used to fade the ribbons behind a highlight).
   * @param {string} c A color such as "rgba(47,128,237,0.55)".
   * @return {string} The same color with its opacity multiplied by 0.3.
   */
  function dim(c) {
    var m = /rgba\(([^)]+)\)/.exec(c);
    if (!m) return c;
    var p = m[1].split(",");
    return "rgba(" + p[0] + "," + p[1] + "," + p[2] + "," + (parseFloat(p[3]) * 0.3) + ")";
  }

  /**
   * Fade all ribbons (so the highlight stands out) or restore their original colors.
   * @param {boolean} dimmed true = fade, false = restore.
   */
  function setRibbons(dimmed) {
    var colors = dimmed ? DATA.linkColors.map(dim) : DATA.linkColors;
    Plotly.restyle(gd, { "link.color": [colors] }, [0]);
  }

  /**
   * Select a company: show its details, fade the ribbons and draw its highlight.
   * @param {number} i Row number of the company.
   */
  function choose(i) {
    current = i;
    sug.style.display = "none";
    showInfo(i);
    // the camera button appears as soon as a company is selected
    snapBtn.style.display = "inline-block";
    if (!rows[i][6]) { setRibbons(true); }
    else { setRibbons(false); }
    draw();
    // Plotly redraws asynchronously after restyle, so draw again a little later to be sure.
    setTimeout(draw, 400);
    setTimeout(draw, 1000);
  }

  /** Remove the selection: empty the search box and info text, erase the highlight, restore ribbons. */
  function clearAll() {
    current = null; q.value = ""; sug.style.display = "none"; info.innerHTML = "";
    svg.innerHTML = "";
    snapBtn.style.display = "none"; snapMsg.textContent = "";
    setRibbons(false);
  }

  /**
   * Measure every box on the screen. Plotly decides the final pixel positions, so the
   * highlight is placed by reading them back from the page.
   * @return {Object} Box number -> {l, r, t, h, y} (left, right, top, height, vertical centre; pixels,
   *     relative to the chart wrapper).
   */
  function nodeBoxes() {
    var wr = wrap.getBoundingClientRect(), out = {};
    var els = gd.querySelectorAll(".sankey-node");
    for (var n = 0; n < els.length; n++) {
      var d = els[n].__data__;
      if (!d || d.index === undefined) continue;
      var rect = els[n].querySelector(".node-rect") || els[n];
      var b = rect.getBoundingClientRect();
      out[d.index] = { l: b.left - wr.left, r: b.right - wr.left, t: b.top - wr.top,
                       h: Math.max(b.height, 5), y: (b.top + b.bottom) / 2 - wr.top };
    }
    return out;
  }

  /**
   * Create an SVG element with attributes (the HTML helper el() cannot make SVG).
   * @param {string} tag SVG element name, e.g. "path".
   * @param {Object} attrs Attribute name -> value.
   * @return {Element} The new element.
   */
  function mk(tag, attrs) {
    var e = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (var a in attrs) e.setAttribute(a, attrs[a]);
    return e;
  }

  /**
   * Draw the pink journey line and the pink outlines around the selected company's boxes.
   * Does nothing when no company is selected or the company is not on the chart.
   */
  function draw() {
    svg.innerHTML = "";
    if (current === null || rows[current][6]) return;
    var wr = wrap.getBoundingClientRect();
    // make the overlay exactly as big as the chart
    svg.setAttribute("width", wr.width); svg.setAttribute("height", wr.height);
    var boxes = nodeBoxes(), snap = rows[current][4], via = rows[current][16] || [], pts = [], idx;
    // Pre-bucket companies start at the Pre box.
    if (rows[current][7] && DATA.pre >= 0 && boxes[DATA.pre]) pts.push(boxes[DATA.pre]);
    // One box per month the company exists in (found through the month_stage -> box number table). Before a month's
    // own box come the boxes of the stages the company only passed THROUGH during that month (via = [month, stage,
    // month, stage, ...] in order), so a company that went Lead, MQL, SQL and Opp inside one month does not look as
    // if it skipped MQL and SQL.
    var vi = 0;
    for (var k = 0; k < snap.length; k++) {
      while (vi + 1 < via.length && via[vi] === k) {
        idx = DATA.nodes[k + "_" + via[vi + 1]];
        if (idx !== undefined && boxes[idx]) pts.push(boxes[idx]);
        vi += 2;
      }
      if (snap[k] === "-") continue;
      idx = DATA.nodes[k + "_" + snap[k]];
      if (idx !== undefined && boxes[idx]) pts.push(boxes[idx]);
    }
    // From each box to the next: a smooth S-shaped curve when the next box is in a later column, or a straight line
    // from centre to centre when it is in the SAME column (a stage passed through that month). Short stubs join the
    // curves to the straight lines inside a box. Each line is drawn twice: a white underlay and the colored line.
    var lines = [];
    function toRight(a, b) { return b.l >= a.r - 1; }
    for (var p = 0; p + 1 < pts.length; p++) {
      var a = pts[p], b = pts[p + 1], cxa = (a.l + a.r) / 2, cxb = (b.l + b.r) / 2;
      if (toRight(a, b)) {
        var xm = (a.r + b.l) / 2;
        lines.push("M" + a.r + "," + a.y + " C" + xm + "," + a.y + " " + xm + "," + b.y + " " + b.l + "," + b.y);
        if (p + 2 < pts.length && !toRight(b, pts[p + 2])) lines.push("M" + b.l + "," + b.y + " L" + cxb + "," + b.y);
      } else {
        lines.push("M" + cxa + "," + a.y + " L" + cxb + "," + b.y);
        if (p + 2 < pts.length && toRight(b, pts[p + 2])) lines.push("M" + cxb + "," + b.y + " L" + b.r + "," + b.y);
      }
    }
    lines.forEach(function (dstr) {
      svg.appendChild(mk("path", { d: dstr, fill: "none", stroke: "#fff", "stroke-width": 8, "stroke-opacity": 0.9 }));
      svg.appendChild(mk("path", { d: dstr, fill: "none", stroke: HI, "stroke-width": 4 }));
    });
    // A pink outline (with a white halo) around every box on the journey.
    pts.forEach(function (b) {
      svg.appendChild(mk("rect", { x: b.l - 4, y: b.y - b.h / 2 - 4, width: b.r - b.l + 8, height: b.h + 8,
                                   fill: "none", stroke: "#fff", "stroke-width": 6 }));
      svg.appendChild(mk("rect", { x: b.l - 4, y: b.y - b.h / 2 - 4, width: b.r - b.l + 8, height: b.h + 8,
                                   fill: "none", stroke: HI, "stroke-width": 3 }));
    });
  }

  // --- Search box events -----------------------------------------------------------
  // Typing: update the suggestions; if exactly one company matches exactly, select it.
  q.addEventListener("input", function () {
    var res = search(q.value);
    matches = res.all;
    renderSuggestions(matches);
    if (res.exact === 1) choose(matches[0]);
  });
  // Enter selects the best match, Escape clears everything.
  q.addEventListener("keydown", function (ev) {
    if (ev.key === "Enter" && matches.length) { ev.preventDefault(); choose(matches[0]); }
    if (ev.key === "Escape") clearAll();
  });
  // Show the suggestions again when the box regains focus; hide them (after a short delay
  // so a click on a suggestion still registers) when it loses focus.
  q.addEventListener("focus", function () { if (matches.length) renderSuggestions(matches); });
  q.addEventListener("blur", function () { setTimeout(function () { sug.style.display = "none"; }, 150); });
  document.getElementById("clear").addEventListener("click", clearAll);

  // --- "Random" button -------------------------------------------------------------
  // cand = row numbers of ALL charted companies (a company that is not charted has no journey
  // to show). There is no date limit: only the "Random success" button is limited by a date.
  var cand = [];
  for (var c = 0; c < rows.length; c++) {
    if (!rows[c][6]) cand.push(c);
  }
  document.getElementById("rand").addEventListener("click", function () {
    if (!cand.length) return;
    var i = cand[Math.floor(Math.random() * cand.length)];
    q.value = rows[i][0] || rows[i][1];
    matches = search(q.value).all;
    choose(i);
  });

  // --- "Random success" button ------------------------------------------------------
  // succ = row numbers flagged by Python as success stories (field 10 of each row = 1; see is_success_journey).
  var succ = [];
  for (var s2 = 0; s2 < rows.length; s2++) { if (rows[s2][10] === 1) succ.push(s2); }
  var succBtn = document.getElementById("success");
  // Grey the button out when no company qualifies.
  if (!succ.length) { succBtn.disabled = true; succBtn.title = "No companies match yet"; }
  succBtn.addEventListener("click", function () {
    if (!succ.length) return;
    var i = succ[Math.floor(Math.random() * succ.length)];
    q.value = rows[i][0] || rows[i][1];
    matches = search(q.value).all;
    choose(i);
  });

  // ---- click a stage box to list its companies ----
  // idxKey: Plotly box number -> [month column, stage level] (the reverse of DATA.nodes).
  var idxKey = {};
  for (var key in DATA.nodes) { idxKey[DATA.nodes[key]] = key.split("_").map(Number); }
  // Popup elements.
  var mbg = document.getElementById("modalbg"), mtitle = document.getElementById("mtitle");
  var mfilter = document.getElementById("mfilter"), mcount = document.getElementById("mcount");
  var mlist = document.getElementById("mlist");
  // The popup can show three groups of companies for the clicked box:
  //   membersNow   = companies IN the stage at the end of that month (the first number on the box)
  //   membersEver  = companies that have EVER been in the stage up to that month (the bracketed number)
  //   membersShort = companies that ENTERED the stage during that month and LEFT it by the end of the next month
  // members is whichever group is showing; popMode ("now", "ever" or "short") says which one.
  // SHOW_MAX: list length cap.
  var members = [], membersNow = [], membersEver = [], membersShort = [], popMode = "now";
  var SHOW_MAX = 500;
  var mnow = document.getElementById("mnow"), mever = document.getElementById("mever");
  var mshort = document.getElementById("mshort");

  // Sorting. sortBy: "name" (alphabetical), "created" (create date) or "entered" (date entered the
  // stage). sortAsc: true = ascending, false = descending. The choice is kept while the page stays open.
  var sortBy = "name", sortAsc = true;
  var sortBtns = { name: document.getElementById("sname"), created: document.getElementById("screated"),
                   entered: document.getElementById("sentered") };
  var sortAscBtn = document.getElementById("sasc"), sortDscBtn = document.getElementById("sdsc");
  // For the stage popup that is open: popDay[row] = the day the company entered this stage (its latest
  // entry on or before the end of the month shown; days since 1970-01-01), popNew[row] = true when it
  // entered the stage DURING that month (shown as a red asterisk). popIsStage is false for the Pre box,
  // which has neither.
  var popDay = {}, popNew = {}, popIsStage = false;
  // For the "Only in stage for this month" group: popLeft[row] = the day the company left the stage, and
  // popWindow = [first day it may have entered, last day it may have left] (days since 1970-01-01).
  var popLeft = {}, popWindow = null;

  // "Show only" check boxes: one per stage a company can be IN NOW (its level is row field 15; -1 = a stage in
  // no bucket, shown as "Other"). nowOn[level] says whether that box is ticked; a company is listed only when
  // the box for its current stage is ticked. All boxes start ticked.
  var NOW_ORDER = [4, 5, 3, 2, 1, 0, -1], nowOn = {}, nowBoxes = {};
  NOW_ORDER.forEach(function (lv) {
    var lab = el("label", "nowbox"), box = document.createElement("input");
    box.type = "checkbox";
    box.checked = true;
    nowOn[lv] = true;
    box.addEventListener("change", function () { nowOn[lv] = box.checked; renderModal(); });
    lab.appendChild(box);
    lab.appendChild(document.createTextNode(" Now " + (lv >= 0 ? STAGE[lv] : "Other")));
    document.getElementById("mchecks").appendChild(lab);
    nowBoxes[lv] = box;
  });

  /**
   * Tick or untick every "Show only" box (the list is not redrawn here).
   * @param {boolean} on true = tick all, false = untick all.
   */
  function setNowAll(on) {
    NOW_ORDER.forEach(function (lv) { nowOn[lv] = on; nowBoxes[lv].checked = on; });
  }

  /**
   * The last day of the month AFTER the month that starts on the given day.
   * @param {number} startDay First day of a month, as days since 1970-01-01.
   * @return {number} The last day of the following month, as days since 1970-01-01.
   */
  function nextMonthEndDay(startDay) {
    var d = new Date(startDay * 86400000);
    return Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 2, 0) / 86400000;
  }

  /**
   * Turn a day number (days since 1970-01-01) into text like "2026-02-23".
   * @param {number} day The day number.
   * @return {string} The date as YYYY-MM-DD.
   */
  function dayText(day) {
    return new Date(day * 86400000).toISOString().slice(0, 10);
  }

  /**
   * Compare two companies (row numbers) for the popup's sort order. Companies that tie on the chosen
   * field are put in A to Z order, whichever direction was chosen, so the list never jumps around.
   * @param {number} a Row number of the first company.
   * @param {number} b Row number of the second company.
   * @return {number} Negative, zero or positive, as for Array.sort.
   */
  function compareRows(a, b) {
    var cmp = 0;
    if (sortBy === "created") {
      cmp = rows[a][3] < rows[b][3] ? -1 : rows[a][3] > rows[b][3] ? 1 : 0;      // YYYY-MM-DD text sorts correctly
    } else if (sortBy === "entered") {
      cmp = (popDay[a] || 0) - (popDay[b] || 0);
    } else {
      cmp = lower[a][0] < lower[b][0] ? -1 : lower[a][0] > lower[b][0] ? 1 : 0;   // alphabetical (lexicographic)
    }
    if (cmp !== 0) return sortAsc ? cmp : -cmp;
    if (lower[a][0] !== lower[b][0]) return lower[a][0] < lower[b][0] ? -1 : 1;
    return a - b;
  }

  /** Sort both groups of the open popup with the current choice (they may be the same list for the Pre box). */
  function sortLists() {
    membersNow.sort(compareRows);
    if (membersEver !== membersNow) membersEver.sort(compareRows);
    membersShort.sort(compareRows);
  }

  /** Show which sort buttons are active. */
  function showSortButtons() {
    Object.keys(sortBtns).forEach(function (key) {
      sortBtns[key].className = "sbtn" + (sortBy === key ? " on" : "");
    });
    sortAscBtn.className = "sbtn" + (sortAsc ? " on" : "");
    sortDscBtn.className = "sbtn" + (sortAsc ? "" : " on");
  }

  /** Apply a changed sort choice: sort, update the buttons and redraw the list (the filter text stays). */
  function resort() {
    sortLists();
    showSortButtons();
    members = groupFor(popMode);
    renderModal();
  }

  /**
   * The list of companies for a group.
   * @param {string} mode "now", "ever" or "short".
   * @return {number[]} The row numbers of that group.
   */
  function groupFor(mode) {
    return mode === "ever" ? membersEver : mode === "short" ? membersShort : membersNow;
  }

  /**
   * Rebuild the popup list from `members`, applying the "Show only" boxes (the company's current stage must
   * be ticked) and the filter text (first 500 shown).
   */
  function renderModal() {
    var t = mfilter.value.trim().toLowerCase();
    var shown = members.filter(function (i) {
      return nowOn[rows[i][15]] && (!t || lower[i][0].indexOf(t) !== -1 || lower[i][1].indexOf(t) !== -1);
    });
    mlist.innerHTML = "";
    shown.slice(0, SHOW_MAX).forEach(function (i) {
      var r = rows[i];
      var d = el("div", "mrow");
      d.appendChild(el("b", "", r[0] || "(no name)"));
      if (popNew[i]) d.appendChild(el("span", "new", "*"));        // red asterisk: entered this stage this month
      var entered = (i in popDay) ? "   |   entered this stage " + dayText(popDay[i]) : "";
      if (popMode === "short" && (i in popLeft)) entered += "   |   left it " + dayText(popLeft[i]);
      d.appendChild(el("span", "sub", "   " + (r[1] || "no domain") + "   |   now: " + stageSince(r) +
                                      "   |   Created " + r[3] + entered));
      // Clicking a name closes the popup and shows that company's journey.
      d.addEventListener("click", function () {
        mbg.style.display = "none";
        q.value = r[0] || r[1];
        matches = search(q.value).all;
        choose(i);
      });
      mlist.appendChild(d);
    });
    mcount.textContent = shown.length.toLocaleString() + " of " + members.length.toLocaleString() +
      " companies" + (shown.length > SHOW_MAX ? " (showing the first " + SHOW_MAX + ", type to narrow)" : "") +
      (popMode === "ever" ? ", including ones that have since moved on" : "") +
      (popMode === "short" && popWindow ? ", entered on or after " + dayText(popWindow[0]) +
        " and left on or before " + dayText(popWindow[1]) : "") +
      ". Click a name to see its journey.";
    if (popIsStage) {
      // the key to the red asterisk
      mcount.appendChild(document.createTextNode("  "));
      mcount.appendChild(el("span", "new", "*"));
      mcount.appendChild(document.createTextNode(" = entered this stage during this month."));
    }
  }

  /**
   * Switch the popup between the three groups of companies and redraw the list.
   * @param {string} mode "now" = in the stage at month end, "ever" = ever been in the stage,
   *     "short" = entered the stage this month and left it by the end of next month.
   */
  function setMode(mode) {
    popMode = mode;
    mnow.className = "mmode" + (mode === "now" ? " on" : "");
    mever.className = "mmode" + (mode === "ever" ? " on" : "");
    mshort.className = "mmode" + (mode === "short" ? " on" : "");
    members = groupFor(mode);
    mfilter.value = "";
    renderModal();
  }

  /**
   * Open the popup for a clicked box: collect its three groups of companies, tick all the "Show only" boxes,
   * sort them (A to Z unless another sort was chosen) and show the "in the stage at month end" group, with a
   * red asterisk after each company that entered the stage that month.
   * @param {number} nodeIdx Plotly's number of the clicked box.
   */
  function openStage(nodeIdx) {
    var _n = "__NOTICE_SHORT__";
    var title;
    membersNow = [];
    membersEver = [];
    membersShort = [];
    popDay = {};
    popNew = {};
    popLeft = {};
    popWindow = null;
    setNowAll(true);                                       // every new popup starts with all "Show only" boxes ticked
    if (nodeIdx === DATA.pre) {
      // the Pre box: every charted company flagged as belonging to the Pre bucket
      title = DATA.preName;
      for (var i = 0; i < rows.length; i++) if (rows[i][7] && !rows[i][6]) membersNow.push(i);
      // for the Pre box both groups are the same, so the switch is hidden
      membersEver = membersNow;
      document.getElementById("mmode").style.display = "none";
      // The Pre bucket is not a stage, so there is no "date entered stage" to sort by.
      popIsStage = false;
      sortBtns.entered.disabled = true;
      if (sortBy === "entered") sortBy = "name";
    } else {
      // kl = [month column, stage level] for this box.
      var kl = idxKey[nodeIdx];
      // Not a real box (for example one of the invisible helper boxes): do nothing.
      if (!kl) return;
      title = STAGE[kl[1]] + " at the end of " + MONTHS[kl[0]];
      var want = String(kl[1]);
      // companies whose month-end stage string has this stage at this month
      for (var j = 0; j < rows.length; j++) {
        if (rows[j][4] && rows[j][4].charAt(kl[0]) === want) membersNow.push(j);
        // ever been in this stage: the company's first month in it is this month or earlier
        var first = rows[j][11];
        if (first && first.length && first[kl[1]] >= 0 && first[kl[1]] <= kl[0]) membersEver.push(j);
      }
      document.getElementById("mmode").style.display = "flex";
      // For every listed company work out (a) the day it ENTERED this stage: its latest entry on or
      // before the end of the month shown, and (b) whether any entry happened DURING that month. The
      // entries of a company are stored as [stage, day, stage, day, ...].
      popIsStage = true;
      sortBtns.entered.disabled = false;
      var monthStart = DATA.monthStartDays[kl[0]], monthEnd = DATA.monthEndDays[kl[0]];
      var tally = function (list) {
        list.forEach(function (idx) {
          if (idx in popDay) return;                       // already worked out (a company can be in both lists)
          var entries = rows[idx][14], best = null, fresh = false;
          for (var p = 0; entries && p + 1 < entries.length; p += 2) {
            if (entries[p] !== kl[1]) continue;            // an entry into a different stage
            var day = entries[p + 1];
            if (day <= monthEnd && (best === null || day > best)) best = day;
            if (day >= monthStart && day <= monthEnd) fresh = true;
          }
          popDay[idx] = best === null ? 0 : best;
          popNew[idx] = fresh;
        });
      };
      tally(membersNow);
      tally(membersEver);
      // "Only in stage for this month": a company qualifies when one of its visits to this stage STARTED during
      // the month shown and ENDED on or before the last day of the NEXT month. A visit ends at the company's next
      // entry (its path moves straight from one stage to another), so a visit that is still going does not count.
      popWindow = [monthStart, nextMonthEndDay(monthStart)];
      membersEver.forEach(function (idx) {
        var entries = rows[idx][14];
        for (var p = 0; entries && p + 3 < entries.length; p += 2) {
          if (entries[p] !== kl[1]) continue;              // an entry into a different stage
          var inDay = entries[p + 1], outDay = entries[p + 3];
          if (inDay >= popWindow[0] && inDay <= monthEnd && outDay <= popWindow[1]) {
            membersShort.push(idx);
            popLeft[idx] = outDay;
            break;
          }
        }
      });
    }
    sortLists();
    showSortButtons();
    // the three switch buttons show how many companies are in each group
    mnow.textContent = "In the stage at month end (" + membersNow.length.toLocaleString() + ")";
    mever.textContent = "Ever been in the stage (" + membersEver.length.toLocaleString() + ")";
    mshort.textContent = "Only in stage for this month (" + membersShort.length.toLocaleString() + ")";
    mtitle.textContent = title;
    setMode("now");
    mbg.style.display = "block";
    mfilter.focus();
  }

  /**
   * Open the popup for a clicked ribbon: list the companies that made that move between two neighbouring
   * month ends (or that started in the Pre box and were in that stage at the end of the first month).
   * The popup has one group only, so the three-way switch is hidden.
   * @param {number} linkIdx Plotly's number of the clicked ribbon.
   */
  function openLink(linkIdx) {
    var lk = DATA.links && DATA.links[linkIdx];
    if (!lk) return;                                       // a helper ribbon: do nothing
    var fromPre = lk[0] === DATA.pre, a = null, b = idxKey[lk[1]];
    if (!fromPre) a = idxKey[lk[0]];
    if (!b || (!fromPre && !a)) return;
    membersNow = []; membersEver = []; membersShort = [];
    popDay = {}; popNew = {}; popLeft = {}; popWindow = null;
    setNowAll(true);
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i][4];
      if (!s) continue;
      if (fromPre) {
        if (rows[i][7] && !rows[i][6] && s.charAt(0) === String(b[1])) membersNow.push(i);
      } else if (s.charAt(a[0]) === String(a[1]) && s.charAt(b[0]) === String(b[1])) {
        membersNow.push(i);
      }
    }
    membersEver = membersNow;
    var kind = fromPre ? "from " + DATA.preName : a[1] === b[1] ? "stayed" : b[1] > a[1] ? "moved up" : "moved down";
    mtitle.textContent = fromPre
      ? DATA.preName + " to " + STAGE[b[1]] + " at the end of " + MONTHS[b[0]]
      : STAGE[a[1]] + " at the end of " + MONTHS[a[0]] + " to " + STAGE[b[1]] + " at the end of " +
        MONTHS[b[0]] + " (" + kind + ")";
    document.getElementById("mmode").style.display = "none";
    popIsStage = false;
    sortBtns.entered.disabled = true;
    if (sortBy === "entered") sortBy = "name";
    sortLists();
    showSortButtons();
    popMode = "now";
    members = membersNow;
    mfilter.value = "";
    renderModal();
    mbg.style.display = "block";
    mfilter.focus();
  }

  // Popup events: typing filters the list; the X, a click outside, or Escape closes it.
  mfilter.addEventListener("input", renderModal);
  // Sort buttons: choose what to sort by, and ascending or descending.
  Object.keys(sortBtns).forEach(function (key) {
    sortBtns[key].addEventListener("click", function () { sortBy = key; resort(); });
  });
  sortAscBtn.addEventListener("click", function () { sortAsc = true; resort(); });
  sortDscBtn.addEventListener("click", function () { sortAsc = false; resort(); });
  mnow.addEventListener("click", function () { setMode("now"); });
  mever.addEventListener("click", function () { setMode("ever"); });
  mshort.addEventListener("click", function () { setMode("short"); });
  document.getElementById("mall").addEventListener("click", function () { setNowAll(true); renderModal(); });
  document.getElementById("mnone").addEventListener("click", function () { setNowAll(false); renderModal(); });
  document.getElementById("mclose").addEventListener("click", function () { mbg.style.display = "none"; });
  mbg.addEventListener("mousedown", function (ev) { if (ev.target === mbg) mbg.style.display = "none"; });
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") mbg.style.display = "none"; });

  // ---- the camera button: save a picture of the page ----
  // The picture is built here in the browser (no extra library): the page heading and notes, the
  // selected company's panel (with its logo when the logo's server allows it), and the chart with
  // the pink highlight on top. The search box and buttons are left out.
  var snapBtn = document.getElementById("snap"), snapMsg = document.getElementById("snapmsg");
  var snapBusy = false;                      // true while a picture is being made (ignores double clicks)

  /**
   * Show a short status message next to the camera button.
   * @param {string} text The message.
   * @param {number} [ms] Clear it again after this many milliseconds (omit to keep it).
   */
  function snapSay(text, ms) {
    snapMsg.textContent = text;
    if (ms) setTimeout(function () { if (snapMsg.textContent === text) snapMsg.textContent = ""; }, ms);
  }

  /**
   * Load an image from a web address or a data address.
   * @param {string} src The address.
   * @return {Promise<HTMLImageElement>} Resolves with the loaded image.
   */
  function loadImage(src) {
    return new Promise(function (resolve, reject) {
      var im = new Image();
      im.onload = function () { resolve(im); };
      im.onerror = function () { reject(new Error("an image could not be loaded")); };
      im.src = src;
    });
  }

  /**
   * Try to fetch a company logo in a way that lets it be drawn into the picture. Browsers only
   * allow that when the logo's server gives permission (a CORS header). Without it the logo is
   * still shown on the page, but cannot be put into the picture, so this returns null.
   * @param {string} url The logo address ("" for none).
   * @return {Promise<ImageBitmap|null>} The logo, or null.
   */
  async function logoBitmap(url) {
    if (!url) return null;
    try {
      var resp = await fetch(url, { mode: "cors", referrerPolicy: "no-referrer" });
      if (!resp.ok) return null;
      return await createImageBitmap(await resp.blob());
    } catch (e) {
      return null;
    }
  }

  /**
   * Lay coloured pieces of text out into lines that fit a width (used for the picture).
   * @param {CanvasRenderingContext2D} ctx A drawing context, only used to measure text.
   * @param {Array} pieces Items like {text, bold, color}, drawn one after the other.
   * @param {number|function(number): number} maxWidth Line width in pixels, or a function giving the width of
   *     line number k (0 = the first line of this text): the lines beside the logos are shorter than the rest.
   * @param {number} [size] Font size in pixels (default 13).
   * @return {Array} Lines; each line is a list of {text, font, color, x} (x = distance from the line start).
   */
  function layoutRich(ctx, pieces, maxWidth, size) {
    var lines = [[]], x = 0;
    var widthFor = typeof maxWidth === "function" ? maxWidth : function () { return maxWidth; };
    pieces.forEach(function (p) {
      var font = (p.bold ? "bold " : "") + (size || 13) + "px Arial, Helvetica, sans-serif";
      ctx.font = font;
      // split into words and the spaces between them, keeping the spaces
      p.text.split(/(\s+)/).forEach(function (word) {
        if (!word) return;
        var isSpace = !/\S/.test(word);
        var width = ctx.measureText(word).width;
        if (!isSpace && x > 0 && x + width > widthFor(lines.length - 1)) { lines.push([]); x = 0; }   // start a new line
        if (isSpace && x === 0) return;                                              // no spaces at the start of a line
        lines[lines.length - 1].push({ text: word, font: font, color: p.color, x: x });
        x += width;
      });
    });
    return lines;
  }

  /**
   * Test whether the browser lets this page read pixels back out of a canvas.
   * Firefox's fingerprinting protection ("resist fingerprinting"; some privacy add-ons and
   * browsers do the same) hands back RANDOM NOISE instead of the real pixels, and a PNG made
   * through a canvas is then a square of noise. The test paints two known colors on a tiny
   * canvas and checks that they come back unchanged.
   * @return {boolean} true when canvas pixels can be trusted.
   */
  function canvasReadable() {
    var c = document.createElement("canvas");
    c.width = 16;
    c.height = 16;
    var x = c.getContext("2d");
    if (!x) return false;
    x.fillStyle = "#123456"; x.fillRect(0, 0, 8, 16);
    x.fillStyle = "#fedcba"; x.fillRect(8, 0, 8, 16);
    var d = x.getImageData(0, 0, 16, 16).data, tol = 8;
    for (var py = 0; py < 16; py += 5) {
      for (var px = 0; px < 16; px += 3) {
        var i = (py * 16 + px) * 4, want = px < 8 ? [18, 52, 86] : [254, 220, 186];
        if (Math.abs(d[i] - want[0]) > tol || Math.abs(d[i + 1] - want[1]) > tol ||
            Math.abs(d[i + 2] - want[2]) > tol || Math.abs(d[i + 3] - 255) > tol) return false;
      }
    }
    return true;
  }

  /**
   * Lay "label: value" pairs out into lines (used for the picture, to match the page). A line
   * only breaks BETWEEN whole pairs; a pair that is longer than a whole line wraps inside itself.
   * Like the page, a pair that is too wide for the short lines beside the logos moves down below them.
   * @param {CanvasRenderingContext2D} ctx A drawing context, only used to measure text.
   * @param {Array} pairs Items [label, value].
   * @param {number|function(number): number} maxWidth Line width in pixels, or a function giving the width of
   *     line number k (0 = the first line of this text).
   * @return {Array} Lines; each line is a list of {text, font, color, x}. A line in the middle can be empty (skipped).
   */
  function layoutPairs(ctx, pairs, maxWidth) {
    var font = "12px Arial, Helvetica, sans-serif", gap = 28;
    var widthFor = typeof maxWidth === "function" ? maxWidth : function () { return maxWidth; };
    ctx.font = font;
    var lines = [[]], x = 0;
    pairs.forEach(function (pair) {
      var label = pair[0] + ":", value = pair[1];
      var labelW = ctx.measureText(label + " ").width, width = labelW + ctx.measureText(value).width;
      var cur = lines[lines.length - 1];
      var startX = cur.length ? x + gap : 0;
      if (cur.length && startX + width > widthFor(lines.length - 1)) {   // not enough room after the previous pair: the WHOLE pair moves down
        lines.push([]);
        cur = lines[lines.length - 1];
        startX = 0;
      }
      // Too wide for a short line beside the logos, but the lines below them are wider: move down to those.
      while (width > widthFor(lines.length - 1) && widthFor(lines.length) > widthFor(lines.length - 1)) {
        lines.push([]);
        cur = lines[lines.length - 1];
        startX = 0;
      }
      if (width <= widthFor(lines.length - 1)) {
        cur.push({ text: label, font: font, color: "#666", x: startX });
        cur.push({ text: value, font: font, color: "#111", x: startX + labelW });
        x = startX + width;
      } else {
        // longer than a whole line: it has to wrap inside itself
        lines.pop();                                       // (the current line is empty here)
        layoutRich(ctx, [{ text: label + " ", bold: false, color: "#666" },
                         { text: value, bold: false, color: "#111" }],
                   function (k) { return widthFor(lines.length + k); }, 12)
          .forEach(function (ln) { lines.push(ln); });
        lines.push([]);                                    // the next pair starts on a fresh line
        x = 0;
      }
    });
    while (lines.length && lines[lines.length - 1].length === 0) lines.pop();   // no empty lines at the end
    return lines;
  }

  /**
   * Work out what goes where in the picture. Shared by the PNG and the SVG versions.
   * @param {boolean} useLogo true = try to fetch the company logo so it can be drawn into a PNG.
   * @return {Promise<Object>} chartW/chartH (chart size), W (picture width), pad, top (where the
   *     company panel starts), chartTop (where the chart starts), totalH (picture height),
   *     cmds (the pieces of text to draw: {text, font, color, x, y}), bmp (the company logo or
   *     null), agency (the agency logo image or null) and agencyBox ({x, y, w, h} where it goes).
   */
  async function snapshotLayout(useLogo) {
    var _nb = "__NOTICE_B64__";
    var m = infoModel(current);
    var chartW = gd._fullLayout.width, chartH = gd._fullLayout.height;
    var W = Math.max(chartW, 900), pad = 20, lineH = 18;
    var font = function (bold, size) { return (bold ? "bold " : "") + size + "px Arial, Helvetica, sans-serif"; };
    var meas = document.createElement("canvas").getContext("2d");
    var bmp = useLogo ? await logoBitmap(m.logo) : null;   // null when the logo cannot be used in the picture
    // The agency logo is built into the page as a data address, so it can always be drawn.
    var agency = null, agencyW = 0, agencyH = 0;
    if (DATA.agencyLogoEmbedded) {
      try {
        agency = await loadImage(DATA.agencyLogo);
        var fitA = Math.min(64 / agency.naturalWidth, 48 / agency.naturalHeight, 1);
        agencyW = agency.naturalWidth * fitA;
        agencyH = agency.naturalHeight * fitA;
      } catch (e) {
        agency = null;
      }
    }
    // The logo column sits at the left: a 64 px place for the company logo (blank when there is none) with the
    // agency logo under it. Like on the page, the first lines of text run along its right side and the lines
    // below it continue to the left margin.
    var hasCol = !!(bmp || agency);
    var leftX = pad + (hasCol ? 76 : 0);
    var colH = hasCol ? 64 + (agency ? 8 + agencyH : 0) : 0;
    var beside = hasCol ? Math.ceil((colH + 6) / lineH) : 0;     // how many lines are shorter because of the logo column
    var narrowW = W - leftX - pad, wideW = W - 2 * pad;
    var widthAt = function (k) { return k < beside ? narrowW : wideW; };    // width of text line number k

    // --- the page heading, then ONE line with the note and the credit ---
    var cmds = [];                                   // everything to draw: {text, font, color, x, y}
    var y = pad + 24;
    var headingEl = document.querySelector("#head h1");
    cmds.push({ text: headingEl ? headingEl.textContent : "", font: font(true, 24), color: "#000", x: pad, y: y });
    y += 24;
    // The credit in the picture is its own text ("Created by <agency> on ..."), not the page's.
    var creditEl = document.getElementById("credit");
    var credit = creditEl.getAttribute("data-picture") || creditEl.innerText;
    var note = document.getElementById("excluded").innerText;
    cmds.push({ text: (note ? note + "   |   " : "") + credit, font: font(false, 13), color: "#555", x: pad, y: y });
    y += 18;

    // --- the selected company's panel (same text as under the search box) ---
    var top = y;
    var lines = layoutRich(meas, [{ text: m.name, bold: true, color: "#000" },
                                  { text: m.rest, bold: false, color: "#000" }], widthAt);
    var base2 = lines.length;
    lines = lines.concat(layoutRich(meas, [{ text: m.second, bold: false, color: "#333" }],
                                    function (k) { return widthAt(base2 + k); }));
    var base3 = lines.length;
    lines = lines.concat(layoutPairs(meas, m.details, function (k) { return widthAt(base3 + k); }));   // one flow of pairs
    lines.forEach(function (ln, k) {
      ln.forEach(function (tok) {
        cmds.push({ text: tok.text, font: tok.font, color: tok.color, x: (k < beside ? leftX : pad) + tok.x, y: top + 13 + k * lineH });
      });
    });
    // the agency logo goes under the company logo's place (which stays blank when there is no company logo)
    var agencyY = top + 72;
    var blockH = Math.max(lines.length * lineH, colH);
    var chartTop = top + blockH + 14;
    return { chartW: chartW, chartH: chartH, W: W, pad: pad, top: top, chartTop: chartTop,
             totalH: chartTop + chartH, cmds: cmds, bmp: bmp, agency: agency,
             agencyBox: { x: pad + (64 - agencyW) / 2, y: agencyY, w: agencyW, h: agencyH } };
  }

  /**
   * A copy of the chart's data with the box outlines switched off. Plotly draws the chart
   * again from its data for the picture, and in that copy the two invisible helper boxes would
   * show a thin outline. The outlines of the real boxes are drawn again by realBoxOutlines().
   * The month names above the counts are a frozen row on the page, not part of the chart's own text, so they
   * are put back above the counts in this copy (each count block carries its column name in "name").
   * @return {Object} A figure ({data, layout}) for Plotly.toImage.
   */
  function figureWithoutOutlines() {
    var fig = JSON.parse(JSON.stringify({ data: gd.data, layout: gd.layout }));
    fig.data[0].node.line = { width: 0, color: "rgba(0,0,0,0)" };
    (fig.layout.annotations || []).forEach(function (a) {
      if (a.name) a.text = "<b>" + a.name + "</b><br>" + a.text;
    });
    return fig;
  }

  /**
   * The thin outline of every real box, read from what is drawn on the screen right now.
   * @return {Array} Items {x, y, w, h, stroke, lineWidth}, in pixels from the top left of the chart.
   */
  function realBoxOutlines() {
    var out = [], wrapBox = wrap.getBoundingClientRect();
    gd.querySelectorAll(".sankey-node").forEach(function (nodeEl) {
      if (!nodeEl.__data__ || DATA.dummyNodes.indexOf(nodeEl.__data__.index) !== -1) return;   // skip the helpers
      var rectEl = nodeEl.querySelector(".node-rect");
      if (!rectEl) return;
      var style = getComputedStyle(rectEl), box = rectEl.getBoundingClientRect();
      if (style.stroke === "none") return;
      out.push({ x: box.left - wrapBox.left, y: box.top - wrapBox.top, w: box.width, h: box.height,
                 stroke: style.stroke, lineWidth: parseFloat(style.strokeWidth) || 0.5 });
    });
    return out;
  }

  /**
   * Check a finished PNG by decoding it again: its top left corner must be the white background.
   * Some privacy add-ons only scramble the final image export, which the early test in
   * canvasReadable cannot see; this catches that.
   * @param {Blob} blob The PNG.
   * @return {Promise<boolean>} true when the corner is white.
   */
  async function pngLooksRight(blob) {
    try {
      var bmp = await createImageBitmap(blob);
      var c = document.createElement("canvas");
      c.width = 4;
      c.height = 4;
      var x = c.getContext("2d");
      x.drawImage(bmp, 0, 0, 4, 4, 0, 0, 4, 4);
      var d = x.getImageData(0, 0, 4, 4).data;
      for (var i = 0; i < d.length; i += 4) {
        if (d[i] < 240 || d[i + 1] < 240 || d[i + 2] < 240) return false;
      }
      return true;
    } catch (e) {
      return false;
    }
  }

  /**
   * Build the picture as a PNG file.
   * @return {Promise<Blob>} The picture. If the browser scrambled it, an error with the property
   *     "scrambled" set to true is thrown instead, so the caller can use the SVG picture.
   */
  async function buildSnapshot() {
    var _n = "__NOTICE_SHORT__";
    var L = await snapshotLayout(true);
    var chartW = L.chartW, chartH = L.chartH, W = L.W, pad = L.pad, top = L.top, chartTop = L.chartTop;
    var totalH = L.totalH, bmp = L.bmp;

    // --- picture size: DATA.pictureScale (set by PICTURE_SCALE) pixels per screen pixel, reduced
    //     if needed to stay within the browser's canvas limits ---
    var s = Math.min(DATA.pictureScale || 1, 16000 / W, 16000 / totalH, Math.sqrt(2.4e8 / (W * totalH)));
    var canvas = document.createElement("canvas");
    canvas.width = Math.round(W * s);
    canvas.height = Math.round(totalH * s);
    var ctx = canvas.getContext("2d");
    ctx.scale(s, s);
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, W, totalH);
    L.cmds.forEach(function (c) { ctx.font = c.font; ctx.fillStyle = c.color; ctx.fillText(c.text, c.x, c.y); });

    // --- the company logo, scaled to fit a 64 pixel box, and the agency logo under it ---
    if (bmp) {
      ctx.strokeStyle = "#ddd";
      ctx.strokeRect(pad + 0.5, top + 0.5, 63, 63);
      var fit = Math.min(56 / bmp.width, 56 / bmp.height, 1);
      var lw = bmp.width * fit, lh = bmp.height * fit;
      ctx.drawImage(bmp, pad + (64 - lw) / 2, top + (64 - lh) / 2, lw, lh);
    }
    if (L.agency) ctx.drawImage(L.agency, L.agencyBox.x, L.agencyBox.y, L.agencyBox.w, L.agencyBox.h);

    // --- the chart (drawn by Plotly) and the pink highlight on top of it ---
    var chartUrl = await Plotly.toImage(figureWithoutOutlines(), { format: "png", width: chartW, height: chartH, scale: s });
    ctx.drawImage(await loadImage(chartUrl), 0, chartTop, chartW, chartH);
    realBoxOutlines().forEach(function (o) {
      ctx.strokeStyle = o.stroke;
      ctx.lineWidth = o.lineWidth;
      ctx.strokeRect(o.x, chartTop + o.y, o.w, o.h);
    });
    if (svg.childNodes.length) {
      var ov = svg.cloneNode(true);
      ov.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      ov.setAttribute("width", chartW);
      ov.setAttribute("height", chartH);
      var svgUrl = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(ov));
      ctx.drawImage(await loadImage(svgUrl), 0, chartTop, chartW, chartH);
    }

    // Last safety check: the top left corner is plain white background. If it is not, the
    // browser scrambled the pixels (privacy protection), so stop instead of saving noise.
    var corner = ctx.getImageData(0, 0, 2, 2).data;
    var scrambled = new Error("the browser scrambled the picture (privacy protection). Allow canvas data for this page, or use Chrome or Edge");
    scrambled.scrambled = true;
    if (corner[0] < 240 || corner[1] < 240 || corner[2] < 240) throw scrambled;
    var png = await new Promise(function (resolve, reject) {
      canvas.toBlob(function (b) { if (b) resolve(b); else reject(new Error("the picture could not be encoded")); }, "image/png");
    });
    if (!(await pngLooksRight(png))) throw scrambled;     // the exported file itself came out scrambled
    return png;
  }

  /**
   * Build the picture as an SVG file. Used instead of the PNG when the browser blocks reading
   * canvas pixels (see canvasReadable). An SVG is a vector drawing made of text and shapes, so
   * no canvas is involved: it cannot be scrambled, stays sharp at any size, and opens in any
   * browser. It is built from the same layout as the PNG, but without the company logo.
   * @return {Promise<Blob>} The picture.
   */
  async function buildSnapshotSvg() {
    var L = await snapshotLayout(false);
    var esc = function (t) {
      return String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    };
    var parts = [
      '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="' + L.W +
        '" height="' + L.totalH + '" viewBox="0 0 ' + L.W + " " + L.totalH + '">',
      '<rect width="100%" height="100%" fill="#ffffff"/>'
    ];
    // the text: heading, notes, company panel and detail lines
    L.cmds.forEach(function (c) {
      if (!/\S/.test(c.text)) return;               // spaces only: nothing to draw
      var size = parseFloat((/(\d+(?:\.\d+)?)px/.exec(c.font) || [0, 13])[1]);
      parts.push('<text x="' + c.x + '" y="' + c.y + '" font-family="Arial, Helvetica, sans-serif" font-size="' + size +
                 '"' + (/^bold /.test(c.font) ? ' font-weight="bold"' : "") + ' fill="' + esc(c.color) +
                 '" xml:space="preserve">' + esc(c.text) + "</text>");
    });
    // the agency logo (built into the page, so it can be placed in the file)
    if (L.agency) {
      parts.push('<image x="' + L.agencyBox.x + '" y="' + L.agencyBox.y + '" width="' + L.agencyBox.w + '" height="' + L.agencyBox.h +
                 '" href="' + esc(DATA.agencyLogo) + '" xlink:href="' + esc(DATA.agencyLogo) + '"/>');
    }
    // the chart: Plotly draws it as SVG, which is placed in the picture as an embedded image
    var chartUrl = await Plotly.toImage(figureWithoutOutlines(), { format: "svg", width: L.chartW, height: L.chartH });
    var chartText = chartUrl.indexOf(";base64,") !== -1
      ? atob(chartUrl.slice(chartUrl.indexOf(";base64,") + 8))
      : decodeURIComponent(chartUrl.slice(chartUrl.indexOf(",") + 1));
    var chartB64 = btoa(unescape(encodeURIComponent(chartText)));
    parts.push('<image x="0" y="' + L.chartTop + '" width="' + L.chartW + '" height="' + L.chartH +
               '" href="data:image/svg+xml;base64,' + chartB64 + '" xlink:href="data:image/svg+xml;base64,' + chartB64 + '"/>');
    // the thin outline of every real box
    realBoxOutlines().forEach(function (o) {
      parts.push('<rect x="' + o.x + '" y="' + (L.chartTop + o.y) + '" width="' + o.w + '" height="' + o.h +
                 '" fill="none" stroke="' + esc(o.stroke) + '" stroke-width="' + o.lineWidth + '"/>');
    });
    // the pink highlight (the overlay is already SVG)
    if (svg.childNodes.length) {
      var ov = svg.cloneNode(true);
      ov.setAttribute("xmlns", "http://www.w3.org/2000/svg");
      ov.setAttribute("x", 0);
      ov.setAttribute("y", L.chartTop);
      ov.setAttribute("width", L.chartW);
      ov.setAttribute("height", L.chartH);
      parts.push(new XMLSerializer().serializeToString(ov));
    }
    parts.push("</svg>");
    return new Blob([parts.join("\n")], { type: "image/svg+xml" });
  }

  /**
   * A file name for the picture, for example "Funnel Tracking - Acme - 2026-10-28.png".
   * Characters that are not allowed in file names are replaced.
   * @param {string} ext The file ending without the dot ("png" or "svg").
   * @return {string} The file name.
   */
  function snapshotName(ext) {
    var headingEl = document.querySelector("#head h1");
    var heading = (headingEl && headingEl.textContent) || "Funnel Tracking";
    var r = rows[current], who = r[0] || r[1] || "company";
    var d = new Date(), two = function (n) { return (n < 10 ? "0" : "") + n; };
    var stamp = d.getFullYear() + "-" + two(d.getMonth() + 1) + "-" + two(d.getDate());
    var base = (heading + " - " + who + " - " + stamp).replace(/[\\\/:*?"<>|]+/g, "-").slice(0, 120);
    return base + "." + ext;
  }

  /**
   * The camera button: ask where to save, build the picture and save it.
   * Chrome and Edge show a "Save as" window so you choose the folder and name. Other browsers
   * cannot do that, so the picture is downloaded the normal way (the browser's own download
   * setting decides whether it asks where to save).
   * Normally the picture is a PNG. If the browser blocks reading canvas pixels (Firefox with
   * fingerprinting protection) a PNG would be a square of noise, so an SVG picture is saved
   * instead and a message explains why.
   */
  async function takeSnapshot() {
    var _n = "__NOTICE_SHORT__";
    if (current === null || snapBusy) return;
    snapBusy = true;
    try {
      var asPng = canvasReadable();                // false = the browser would scramble a PNG
      var fileName = snapshotName(asPng ? "png" : "svg");
      var handle = null;
      // Ask WHERE to save first, while the click is still fresh: browsers only allow the
      // save window straight after a click.
      if (window.showSaveFilePicker) {
        try {
          handle = await window.showSaveFilePicker({
            suggestedName: fileName,
            types: [asPng ? { description: "PNG image", accept: { "image/png": [".png"] } }
                          : { description: "SVG image", accept: { "image/svg+xml": [".svg"] } }]
          });
        } catch (e) {
          if (e && e.name === "AbortError") { snapBusy = false; return; }   // Cancel was pressed: do nothing
          handle = null;                                                    // any other problem: fall back to a normal download
        }
      }
      snapSay("Creating the picture ...");
      draw();                                      // make sure the highlight matches what is on screen
      var blob;
      if (asPng) {
        try {
          blob = await buildSnapshot();
        } catch (e) {
          // A scrambled PNG: use the SVG picture instead (not possible once a PNG file name was chosen in the Save-as window).
          if (handle || !(e && e.scrambled)) throw e;
          asPng = false;
          fileName = snapshotName("svg");
        }
      }
      if (!asPng) blob = await buildSnapshotSvg();
      if (handle) {
        var writer = await handle.createWritable();
        await writer.write(blob);
        await writer.close();
      } else {
        var url = URL.createObjectURL(blob), link = document.createElement("a");
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
      }
      if (asPng) {
        snapSay("Picture saved.", 4000);
      } else {
        snapSay("Saved as an SVG picture (open it in a browser) because your browser's privacy protection blocks PNG " +
                "images. If Firefox asks about canvas data, choose Allow and click the camera again, or use Chrome or Edge.", 20000);
      }
    } catch (e) {
      snapSay("Could not save the picture: " + (e && e.message ? e.message : e), 12000);
    }
    snapBusy = false;
  }
  snapBtn.addEventListener("click", takeSnapshot);

  // ---- moving around the chart: the compass arrows and the starting position ----
  // The chart scrolls inside the "scroller" box (both scroll bars are always shown). The four compass arrows
  // jump to an edge, and the chart starts scrolled as far up and as far right as it can go.
  var scroller = document.getElementById("scroller");
  var compass = { n: document.getElementById("cn"), w: document.getElementById("cw"),
                  e: document.getElementById("ce"), s: document.getElementById("cs") };

  /**
   * Scroll the chart all the way to one edge. Only that direction changes: the north and south arrows move
   * up and down, the west and east arrows move sideways, so the other position is kept.
   * @param {string} dir "n" = top-most, "s" = bottom-most, "w" = left-most, "e" = right-most.
   */
  function goEdge(dir) {
    var opts = { behavior: "smooth" };
    if (dir === "n") opts.top = 0;
    if (dir === "s") opts.top = scroller.scrollHeight - scroller.clientHeight;
    if (dir === "w") opts.left = 0;
    if (dir === "e") opts.left = scroller.scrollWidth - scroller.clientWidth;
    scroller.scrollTo(opts);
  }

  /** Grey out each compass arrow while the chart is already at that edge (or cannot move that way at all). */
  function showCompass() {
    var maxX = scroller.scrollWidth - scroller.clientWidth, maxY = scroller.scrollHeight - scroller.clientHeight;
    compass.n.disabled = scroller.scrollTop <= 2;
    compass.s.disabled = scroller.scrollTop >= maxY - 2;
    compass.w.disabled = scroller.scrollLeft <= 2;
    compass.e.disabled = scroller.scrollLeft >= maxX - 2;
  }

  /** Put the chart in its starting position: scrolled as far right and as far up as possible. */
  function goStart() {
    scroller.scrollLeft = scroller.scrollWidth - scroller.clientWidth;
    scroller.scrollTop = 0;
    showCompass();
  }

  Object.keys(compass).forEach(function (dir) {
    compass[dir].addEventListener("click", function () { goEdge(dir); });
  });
  scroller.addEventListener("scroll", showCompass);
  window.addEventListener("resize", showCompass);
  goStart();

  // ---- the frozen month names ----
  // One row with just the column names (the months, and the Pre bucket). It sits right above the counts at the top
  // of the chart and sticks to the top of the chart box while you scroll up and down (CSS: position sticky).
  // DATA.columns = [[name, x], ...] where x is the column's place across the plot area (0 = left edge, 1 = right edge).
  var monthRow = document.getElementById("months");
  DATA.columns.forEach(function (c) { monthRow.appendChild(el("span", "mcol", c[0])); });

  /**
   * Place the month names: each one over its column, and the whole row just above the counts. Plotly decides
   * where the columns and the counts really are, so this reads them back from the drawn chart. It runs again
   * every time Plotly redraws.
   */
  function placeMonthRow() {
    var size = gd._fullLayout && gd._fullLayout._size;
    if (!size) return;
    DATA.columns.forEach(function (c, k) { monthRow.childNodes[k].style.left = (size.l + c[1] * size.w) + "px"; });
    // The top of the highest count block drawn by plotly (the month names at the bottom are much lower down).
    var wrapTop = wrap.getBoundingClientRect().top, y = Infinity;
    gd.querySelectorAll(".annotation").forEach(function (a) {
      y = Math.min(y, a.getBoundingClientRect().top - wrapTop);
    });
    var row = monthRow.offsetHeight, gap = Math.max(0, (isFinite(y) ? y : row + 2) - row - 2);
    monthRow.style.marginTop = gap + "px";                   // the row sits 2 px above the counts ...
    monthRow.style.marginBottom = -(gap + row) + "px";       // ... and takes no room, so the chart is not pushed down
  }

  // the two invisible boxes and the invisible ribbon that keep plotly's box sizes right
  /**
   * Hide the invisible helper boxes and ribbons that the Python code added to keep
   * Plotly's box sizes correct. They are transparent already; hiding them also removes
   * them from mouse hovering and clicking.
   */
  function hideDummies() {
    gd.querySelectorAll(".sankey-node").forEach(function (e) {
      if (e.__data__ && DATA.dummyNodes.indexOf(e.__data__.index) !== -1) e.style.display = "none";
    });
    gd.querySelectorAll(".sankey-link").forEach(function (e) {
      var d = e.__data__;
      var idx = d && (d.link ? d.link.index : d.index);
      if (DATA.dummyLinks.indexOf(idx) !== -1) e.style.display = "none";
    });
  }

  // Wait (checking every 100 ms) until Plotly has finished drawing the boxes, then wire
  // up the chart events. Plotly draws asynchronously, so this cannot be done immediately.
  var timer = setInterval(function () {
    if (gd && gd._fullLayout && gd.querySelectorAll(".sankey-node").length > 0 && gd.on) {
      clearInterval(timer);
      hideDummies();
      placeMonthRow();
      goStart();                                           // the chart is drawn now: start at the top right
      // Clicking a box opens the popup for that stage; clicking a ribbon (it has a "source") opens it for that move.
      gd.on("plotly_click", function (ev) {
        var p = ev && ev.points && ev.points[0];
        if (!p || p.pointNumber === undefined) return;
        if (p.source !== undefined) openLink(p.pointNumber);
        else openStage(p.pointNumber);
      });
      // Every time Plotly redraws, hide the helpers again and re-draw the highlight.
      gd.on("plotly_afterplot", function () { hideDummies(); placeMonthRow(); setTimeout(draw, 50); });
      // Re-draw the highlight when the browser window changes size.
      window.addEventListener("resize", function () { setTimeout(draw, 300); });
    }
  }, 100);
};
