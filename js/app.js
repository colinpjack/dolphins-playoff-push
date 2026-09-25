const $ = (id) => document.getElementById(id);
const FINS = "MIA";

const TERMS = {
  "W-L": "Wins and losses. A tie, if one shows up, is listed as a third number.",
  PCT: "Winning percentage: wins divided by games played. Ties count as half a win.",
  PF: "Points scored this season.",
  PA: "Points allowed this season.",
  PPG: "Points scored per game. League average sits near 22.",
  DIFF: "Point differential: points scored minus points allowed. The fastest check on whether the record is real.",
  DIV: "Record against AFC East opponents. After head-to-head, this is the first divisional tiebreaker.",
  CONF: "Record against AFC opponents. Used after division record in the tiebreaker list.",
  GB: "Games back of the pivot in that table: the cut line on the AFC board, the division leader on the East board. A plus means that club is ahead of the pivot. A dash means they are even.",
  STRK: "Current winning or losing streak.",
  GR: "Games remaining. The regular season is 17 games, plus a bye that does not count.",
  Path: "Win the division and the berth is automatic. Otherwise the club is in the wild-card pool. Three wild cards get in.",
  SOS: "Strength of the remaining schedule: the average winning percentage of the opponents still left.",
  SEED: "Current AFC playoff seed. Seeds 1–4 are the division winners. Seeds 5–7 are the wild cards.",
  TO: "Turnover margin: takeaways minus giveaways. Positive means the Dolphins are winning the ball.",
  "3rd": "Third-down conversion rate. Around 40% is an average NFL offense.",
  RZ: "Red-zone touchdown rate: share of trips inside the opponent 20 that end in a touchdown. Good offenses live near 55–60%.",
  SACK: "Sack margin: sacks recorded by the defense minus sacks allowed by the offense.",
  YPG: "Net yards per game. Offense is pass plus rush. Defense is the yards allowed.",
  RTG: "NFL passer rating. Around 90 is average. Above 100 is a good season.",
  TKL: "Combined tackles.",
  YDS: "Yards from scrimmage in the category shown.",
  INT: "Interceptions.",
  TOP: "Time of possession per game. Thirty minutes is an even split of the clock.",
  Odds: "Share of simulated seasons in which Miami wins the AFC East or claims a wild card.",
};

function term(code, label = code) {
  const def = TERMS[code];
  if (!def) return esc(label);
  return `<abbr class="term" tabindex="0" title="${esc(def)}" data-tip="${esc(def)}">${esc(label)}</abbr>`;
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function fmtDate(iso, withTime = false) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  const opts = withTime
    ? { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "America/New_York" }
    : { weekday: "short", month: "short", day: "numeric", timeZone: "America/New_York" };
  return new Intl.DateTimeFormat("en-US", opts).format(date);
}

function relativeTime(iso) {
  const date = new Date(iso);
  const mins = Math.max(0, Math.round((Date.now() - date.getTime()) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return fmtDate(iso, true);
}

function fmtPct(value) {
  if (value == null || value === "") return "—";
  const text = Number(value).toFixed(3);
  return text.startsWith("0") ? text.slice(1) : text;
}

function signed(value) {
  if (value == null || value === "") return "—";
  const text = String(value);
  if (text.startsWith("+") || text.startsWith("-") || text === "0") return text;
  const n = Number(value);
  if (Number.isNaN(n)) return text;
  return `${n > 0 ? "+" : ""}${n}`;
}

function fmtOdds(pct) {
  if (pct == null || Number.isNaN(Number(pct))) return "—";
  const n = Number(pct);
  if (n > 0 && n < 1) return "<1%";
  if (n < 10) return `${n.toFixed(1)}%`;
  return `${Math.round(n)}%`;
}

function oneDecimal(value) {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return esc(value);
  return n.toFixed(1);
}

function trendBadge(direction) {
  if (!direction || direction === "flat") return "";
  const arrow = direction === "up" ? "▲" : "▼";
  return `<span class="trend ${esc(direction)}">${arrow}</span>`;
}

function teamCell(team) {
  return `<div class="team-cell">
    <img src="${esc(team.logo)}" alt="" />
    <span>${esc(team.abbr)}</span>
  </div>`;
}

function renderTicker(data) {
  const line = (data.ticker || []).join("   •   ") + "   •   ";
  $("tickerTrack").textContent = line + line;
}

function renderConclusion(data) {
  const out = Boolean(data.eliminated);
  document.body.classList.toggle("season-over", out);
  const banner = $("conclusion");
  if (banner) banner.hidden = !out;
}

function renderHero(data) {
  const narrative = data.narrative || {};
  const meters = data.meters || {};
  const primary = meters.primary || {};
  const third = meters.third || {};
  const odds = data.playoffOdds || {};
  $("statusKicker").textContent = narrative.kicker || "";
  $("headline").textContent = narrative.headline || "";
  $("blurb").textContent = narrative.blurb || "";
  $("primaryLabel").textContent = primary.label || "Games back of the cut line";
  $("primaryGiant").textContent = primary.value ?? "—";
  $("primarySub").textContent = primary.sub || "";
  const heat = primary.heat ?? 0;
  $("heatName").textContent = primary.heatLabel || "Season left";
  $("heatValue").textContent = primary.heatText || `${heat}`;
  $("heatFill").style.width = `${Math.max(0, Math.min(100, heat))}%`;
  $("heroChips").innerHTML = (data.chips || [])
    .map((chip) => `<div class="chip"><span>${esc(chip.label)}</span><strong>${esc(chip.value)}</strong></div>`)
    .join("");
  const pct = odds.percent;
  $("oddsGiant").textContent = fmtOdds(pct);
  $("oddsLine").textContent = odds.sims
    ? `${Number(odds.sims).toLocaleString("en-US")} sims · ${data.seasonGames || 17}-game season`
    : "";
  $("oddsNote").textContent = odds.note || "";
  const oddsCard = document.querySelector(".hero-score.odds");
  if (oddsCard) {
    oddsCard.classList.remove("longshot", "toss-up", "live");
    if (pct == null) {
      /* waiting on the simulation */
    } else if (pct < 25) {
      oddsCard.classList.add("longshot");
    } else if (pct < 45) {
      oddsCard.classList.add("toss-up");
    } else {
      oddsCard.classList.add("live");
    }
  }
  $("magicLabel").textContent = third.label || "Magic number to win the East";
  $("magicGiant").textContent = third.value ?? "—";
  $("magicLine").textContent = third.sub || "";
  $("magicNote").textContent = third.note || "";
  $("updatePill").textContent = `Updated ${relativeTime(data.generatedAt)}`;
  $("seasonPill").textContent = data.eliminated
    ? `${data.season} season over`
    : `${data.season} AFC`;
  if (data.legend) {
    $("legendIn").textContent = data.legend.in || "In a playoff spot";
    $("legendOut").textContent = data.legend.out || "Chasing";
  }
}

function renderKpis(data) {
  $("kpis").innerHTML = (data.kpis || []).map((kpi) => `
    <article class="kpi">
      <div class="label">${kpi.stat ? term(kpi.stat, kpi.label) : esc(kpi.label)}</div>
      <div class="value">${esc(kpi.value)}</div>
      <div class="hint">${esc(kpi.hint || "")}</div>
    </article>
  `).join("");
}

function renderTrends(data) {
  $("trends").innerHTML = (data.trends || []).map((card) => `
    <article class="trend-card ${esc(card.direction || "flat")}">
      <div class="label">${card.stat ? term(card.stat, card.label) : esc(card.label)}</div>
      <div class="value">${esc(card.value)} ${trendBadge(card.direction)}</div>
      <div class="hint">${esc(card.detail || "")}</div>
    </article>
  `).join("");
}

function renderPaths(data) {
  $("paths").innerHTML = ["division", "wildcard"].map((key) => {
    const path = (data.paths || {})[key] || {};
    return `<article class="path-card${path.in ? " in-path" : ""}">
      <h4>${esc(path.title || "")}</h4>
      <div class="path-num">${esc(path.value || "—")}</div>
      <p class="meta">${esc(path.detail || "")}</p>
    </article>`;
  }).join("");
}

function headerRow(labels) {
  return `<tr>${labels.map((label) => `<th>${label}</th>`).join("")}</tr>`;
}

function renderConference(data) {
  $("tableBlurb").textContent = data.tableBlurb || "";
  const head = [
    "#", "Team", term("Path", "Path"), term("W-L", "W-L"), term("PCT", "Pct"),
    term("PF", "PF"), term("PA", "PA"), term("DIFF", "Diff"), term("DIV", "Div"),
    term("STRK", "Strk"), term("GB", "GB"),
  ];
  document.querySelector("#conferenceTable thead").innerHTML = headerRow(head);
  document.querySelector("#conferenceTable tbody").innerHTML = (data.conference || []).map((team) => {
    const classes = [
      team.inField ? "row-in" : "",
      team.isFins ? "row-jays" : "",
      team.isCut ? "row-cut" : "",
    ].filter(Boolean).join(" ");
    const cut = team.isCut ? `<div class="cut-note">Last berth</div>` : "";
    return `<tr class="${classes}">
      <td>${esc(team.seed)}${cut}</td>
      <td>${teamCell(team)}${team.isFins ? " ★" : ""}</td>
      <td>${esc(team.path)}</td>
      <td>${esc(team.record)}</td>
      <td>${esc(fmtPct(team.pct))}</td>
      <td>${esc(team.pf)}</td>
      <td>${esc(team.pa)}</td>
      <td>${esc(signed(team.diff))}</td>
      <td>${esc(team.divisionRecord || "—")}</td>
      <td>${esc(team.streak || "—")}</td>
      <td>${esc(team.gb ?? "—")}</td>
    </tr>`;
  }).join("");
}

function renderEast(data) {
  const head = [
    "#", "Team", term("W-L", "W-L"), term("GB", "GB"), term("DIV", "Div"),
    "Home", "Road", term("DIFF", "Diff"), term("GR", "GR"),
  ];
  document.querySelector("#eastTable thead").innerHTML = headerRow(head);
  document.querySelector("#eastTable tbody").innerHTML = (data.east || []).map((team) => {
    const classes = [
      team.seed <= 4 ? "row-in" : "",
      team.isFins ? "row-jays" : "",
      team.divisionCut ? "row-cut" : "",
    ].filter(Boolean).join(" ");
    const cut = team.divisionCut ? `<div class="cut-note">East lead</div>` : "";
    return `<tr class="${classes}">
      <td>${esc(team.seed)}${cut}</td>
      <td>${teamCell(team)}</td>
      <td>${esc(team.record)}</td>
      <td>${esc(team.gb ?? "—")}</td>
      <td>${esc(team.divisionRecord || "—")}</td>
      <td>${esc(team.home || "—")}</td>
      <td>${esc(team.road || "—")}</td>
      <td>${esc(signed(team.diff))}</td>
      <td>${esc(team.gr ?? "—")}</td>
    </tr>`;
  }).join("");
}

function renderLeaders(data) {
  $("divLeaders").innerHTML = (data.leaders || []).map((team) => `
    <article class="div-card">
      <img src="${esc(team.logo)}" alt="" />
      <div>
        <strong>${esc(team.name)}</strong>
        <div class="meta">${esc(team.division)} · ${esc(team.record)} · ${esc(signed(team.diff))} · No. ${esc(team.seed)} seed</div>
      </div>
    </article>
  `).join("");
}

function metricMax(rows, getter) {
  return Math.max(...rows.map((row) => getter(row)), 0.0001);
}

function compareBlock(rows, block) {
  const max = metricMax(rows, block.get);
  const sorted = [...rows].sort((a, b) => block.get(b) - block.get(a));
  const body = sorted.map((team) => {
    const width = Math.max(8, Math.min(100, Math.round((block.get(team) / max) * 100)));
    return `<div class="compare-row">
      <div class="who"><img src="${esc(team.logo)}" alt="" />${esc(team.abbr)}</div>
      <div class="bar ${team.abbr === FINS ? "jays" : ""}"><span style="width:${width}%"></span></div>
      <b>${esc(block.format(team))}</b>
    </div>`;
  }).join("");
  return `<div class="compare-block"><header>${block.title}</header>${body}</div>`;
}

function renderCompare(data) {
  $("compareTitle").textContent = data.compareTitle || "AFC East";
  const rows = data.compare || [];
  const columns = [
    {
      heading: "The standings",
      blocks: [
        { title: "Wins", get: (team) => team.wins || 0, format: (team) => team.wins },
        { title: term("DIFF", "Point diff"), get: (team) => (Number(team.diff) || 0) + 80, format: (team) => signed(team.diff) },
        { title: term("PPG", "Points / game"), get: (team) => Number(team.ppg) || 0, format: (team) => oneDecimal(team.ppg) },
      ],
    },
    {
      heading: "The football",
      blocks: [
        { title: "Points allowed", get: (team) => Math.max(0, 60 - (Number(team.papg) || 0)), format: (team) => oneDecimal(team.papg) },
        { title: term("YPG", "Yards / game"), get: (team) => Number(team.ypg) || 0, format: (team) => oneDecimal(team.ypg) },
        { title: term("TO", "Turnover margin"), get: (team) => (Number(team.to) || 0) + 12, format: (team) => signed(team.to) },
      ],
    },
  ];
  $("compare").innerHTML = columns.map((col) => `
    <div class="compare-col">
      <h4>${esc(col.heading)}</h4>
      ${col.blocks.map((block) => compareBlock(rows, block)).join("")}
    </div>
  `).join("");
}

function renderSchedule(data) {
  const left = data.remaining || {};
  const sos = left.sos == null ? "—" : fmtPct(left.sos);
  const bye = left.bye ? ` · bye in week ${left.bye}` : "";
  $("gauntletBlurb").textContent =
    `${left.games || 0} games left · ${left.home || 0} home · ${left.away || 0} road · ` +
    `${left.division || 0} against the AFC East${bye} · opponent win rate ${sos}.`;
  const today = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
  }).format(new Date());
  $("tickets").innerHTML = (data.schedule || []).map((game) => {
    if (game.bye) {
      return `<article class="ticket">
        <div class="when">Week ${esc(game.week)}</div>
        <h4>Bye</h4>
        <div class="pitch">No game. The week off does not move the standings.</div>
        <div class="venue">Open date</div>
      </article>`;
    }
    const opp = game.opponent || {};
    const gameDay = game.date ? new Intl.DateTimeFormat("en-CA", {
      timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
    }).format(new Date(game.date)) : "";
    const isToday = gameDay === today;
    const tags = [
      game.week ? `Week ${game.week}` : "",
      game.divisionGame ? "AFC East" : (game.conferenceGame ? "AFC" : "NFC"),
      opp.record || "",
      opp.pct != null ? `Opp ${fmtPct(opp.pct)}` : "",
    ].filter(Boolean).join(" · ");
    const score = game.final
      ? `${game.result || ""} ${game.usScore}–${game.themScore}`
      : [game.venue, game.broadcast].filter(Boolean).join(" · ");
    const odds = game.final || game.finsWinPct == null
      ? ""
      : `<div class="ticket-odds"><div class="split-odds">Miami ${esc(game.finsWinPct)}%</div></div>`;
    const live = game.live ? `<div class="live">${esc(game.detail || "Live")}</div>` : "";
    return `<article class="ticket${isToday ? " today" : ""}">
      <div class="when">${esc(fmtDate(game.date, true))}</div>
      <h4>${game.isHome ? "vs" : "@"} ${esc(opp.abbr || "TBD")}</h4>
      <div class="pitch">${esc(tags)}</div>
      ${live}
      ${odds}
      <div class="venue">${esc(score || "")}</div>
    </article>`;
  }).join("");
}

function renderRooting(data) {
  const games = data.rooting || [];
  $("rooting").innerHTML = games.length
    ? games.map((game) => `
      <article class="root-card">
        <div class="root-head">
          <span class="tag ${esc(game.tagClass || "race")}">${esc(game.interest || "AFC game")}</span>
        </div>
        <strong>${esc(game.awayAbbr)} @ ${esc(game.homeAbbr)}</strong>
        <div class="meta">${esc(fmtDate(game.date, true))}</div>
        <div class="score">${esc(game.awayAbbr)} ${esc(game.awayWinPct)}% · ${esc(game.homeAbbr)} ${esc(game.homeWinPct)}%</div>
        <p>${esc(game.note || "")}</p>
      </article>
    `).join("")
    : `<p class="meta">No AFC games in the next couple of weeks change the picture.</p>`;
}

function renderResults(data) {
  $("recentBlurb").textContent = data.recentBlurb || "";
  const games = data.recent || [];
  if (!games.length) {
    $("results").innerHTML = `<li><span></span><span>Regular-season results land here after opening week.</span><strong></strong></li>`;
    return;
  }
  $("results").innerHTML = games.slice().reverse().map((game) => {
    const opp = game.opponent || {};
    const mark = game.result || "•";
    return `<li>
      <span class="badge ${esc(mark)}">${esc(mark)}</span>
      <span>${game.isHome ? "vs" : "@"} ${esc(opp.abbr)} · ${esc(fmtDate(game.date))}</span>
      <strong>${esc(game.usScore)}–${esc(game.themScore)}</strong>
    </li>`;
  }).join("");
}

function renderTiebreak(data) {
  const box = data.tiebreak || {};
  $("tiebreak").innerHTML = `
    <div class="kpis" style="margin:0">
      <article class="kpi"><div class="label">${term("DIV", "Division")}</div><div class="value">${esc(box.division ?? "—")}</div><div class="hint">AFC East games</div></article>
      <article class="kpi"><div class="label">${term("CONF", "Conference")}</div><div class="value">${esc(box.conference ?? "—")}</div><div class="hint">All AFC games</div></article>
      <article class="kpi"><div class="label">${term("DIFF", "Point diff")}</div><div class="value">${esc(box.diff ?? "—")}</div><div class="hint">Later in the tiebreaker list</div></article>
      <article class="kpi"><div class="label">Elim #</div><div class="value">${esc(box.elimination ?? "—")}</div><div class="hint">vs ${esc(box.elimRival || "the leader")} on wins</div></article>
    </div>
    <p class="lede">${esc(box.headToHead || "")}</p>
    <p class="lede">${esc(box.detail || "")}</p>
  `;
}

function playerCard(player) {
  const who = [player.position, player.jersey ? `#${player.jersey}` : ""].filter(Boolean).join(" · ");
  return `<article class="player">
    <img src="${esc(player.headshot)}" alt="" onerror="this.style.opacity='0.25'" />
    <div>
      <strong>${esc(player.name)}</strong>
      <div class="meta">${esc(who)}${player.line ? ` · ${esc(player.line)}` : ""}</div>
    </div>
    <div class="statline"><span class="statline-value">${esc(player.value ?? "—")}</span><span class="statline-label">${player.statLabel ? term(player.statLabel, player.statLabel) : ""}</span></div>
  </article>`;
}

function renderPlayers(data) {
  const players = data.players || {};
  const note = players.label || "";
  if (note) {
    $("qbBlurb").textContent = note;
  }
  const qb = players.quarterback || [];
  const skill = players.skill || [];
  const defense = players.defense || [];
  $("quarterback").innerHTML = qb.map(playerCard).join("")
    || `<p class="meta">Quarterback numbers show up once the season feed posts them.</p>`;
  $("skill").innerHTML = skill.map(playerCard).join("")
    || `<p class="meta">Skill-player yards will land here after the next refresh.</p>`;
  $("defense").innerHTML = defense.map(playerCard).join("")
    || `<p class="meta">Defensive counting stats will land here after the next refresh.</p>`;
}

function renderInjuries(data) {
  const rows = data.injuries || [];
  $("injuryMeta").innerHTML = `<span class="pill ghost">${rows.length} listed</span>`;
  $("injuries").innerHTML = rows.length
    ? rows.map((injury) => `
      <article class="injury">
        <span class="status">${esc(injury.status || "Out")}</span>
        <strong>${esc(injury.name)}${injury.position ? ` · ${esc(injury.position)}` : ""}</strong>
        ${injury.detail ? `<p>${esc(injury.detail)}</p>` : ""}
      </article>
    `).join("")
    : `<p class="meta">Nobody on the Dolphins roster is currently flagged injured or on IR.</p>`;
}

function bindTermTips() {
  let tip = document.getElementById("termTip");
  if (!tip) {
    tip = document.createElement("div");
    tip.id = "termTip";
    tip.className = "term-tip";
    tip.setAttribute("role", "tooltip");
    document.body.appendChild(tip);
  }
  document.querySelectorAll("abbr.term").forEach((el) => {
    if (!el.dataset.tip && el.getAttribute("title")) el.dataset.tip = el.getAttribute("title");
    if (el.dataset.tip && !el.getAttribute("aria-label")) {
      el.setAttribute("aria-label", `${el.textContent}: ${el.dataset.tip}`);
    }
    el.removeAttribute("title");
  });
  const place = (el) => {
    const text = el.dataset.tip;
    if (!text) return;
    tip.textContent = text;
    tip.classList.add("show");
    const pad = 12;
    const rect = el.getBoundingClientRect();
    const left = Math.max(pad, Math.min(rect.left + rect.width / 2 - tip.offsetWidth / 2, window.innerWidth - tip.offsetWidth - pad));
    let top = rect.top - tip.offsetHeight - 8;
    if (top < pad) top = Math.min(rect.bottom + 8, window.innerHeight - tip.offsetHeight - pad);
    tip.style.left = `${Math.round(left)}px`;
    tip.style.top = `${Math.round(top)}px`;
  };
  const hide = () => tip.classList.remove("show");
  if (bindTermTips.bound) return;
  bindTermTips.bound = true;
  document.addEventListener("pointerover", (event) => {
    const el = event.target.closest?.("abbr.term");
    if (el) place(el);
  });
  document.addEventListener("pointerout", (event) => {
    const el = event.target.closest?.("abbr.term");
    if (!el) return;
    if (event.relatedTarget && el.contains(event.relatedTarget)) return;
    hide();
  });
  document.addEventListener("focusin", (event) => {
    const el = event.target.closest?.("abbr.term");
    if (el) place(el);
  });
  document.addEventListener("focusout", hide);
  window.addEventListener("scroll", hide, true);
}

async function boot() {
  try {
    const res = await fetch(`data.json?t=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error("Could not load data.json");
    const data = await res.json();
    renderTicker(data);
    renderConclusion(data);
    renderHero(data);
    renderKpis(data);
    renderTrends(data);
    renderPaths(data);
    renderConference(data);
    renderEast(data);
    renderLeaders(data);
    renderCompare(data);
    renderSchedule(data);
    renderRooting(data);
    renderResults(data);
    renderTiebreak(data);
    renderInjuries(data);
    renderPlayers(data);
    bindTermTips();
  } catch (err) {
    $("headline").textContent = "Dashboard needs a data refresh";
    $("blurb").textContent = "Run scripts/fetch_playoff_data.py, then reload this page.";
    console.error(err);
  }
}

boot();
