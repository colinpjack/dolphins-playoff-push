#!/usr/bin/env python3
"""Fetch Miami Dolphins playoff-race data and write data.json for GitHub Pages."""

from __future__ import annotations

import json
import random
import ssl
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/New_York")
USER_AGENT = "DolphinsPlayoffDash/1.0 (+github-pages refresh)"
ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "data.json"
FINS = "MIA"
SEASON_GAMES = 17
SIMS = 5000
PYTH_EXP = 2.37
PRIOR_POINTS = 88  # about four games of league-average scoring
HOME_BUMP = 0.03

DIVISIONS = {
    "AFC East": ["BUF", "MIA", "NE", "NYJ"],
    "AFC North": ["BAL", "CIN", "CLE", "PIT"],
    "AFC South": ["HOU", "IND", "JAX", "TEN"],
    "AFC West": ["DEN", "KC", "LV", "LAC"],
    "NFC East": ["DAL", "NYG", "PHI", "WSH"],
    "NFC North": ["CHI", "DET", "GB", "MIN"],
    "NFC South": ["ATL", "CAR", "NO", "TB"],
    "NFC West": ["ARI", "LAR", "SF", "SEA"],
}
ABBR_DIV = {abbr: name for name, members in DIVISIONS.items() for abbr in members}
EAST = {"BUF", "MIA", "NE", "NYJ"}

_PREFER_CURL = False


def now_et() -> datetime:
    return datetime.now(TZ)


def fetch_json(url: str, retries: int = 3) -> dict:
    global _PREFER_CURL
    last_err: Exception | None = None
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if not _PREFER_CURL:
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=headers)
                ctx = ssl.create_default_context()
                with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
                    return json.load(resp)
            except Exception as err:
                last_err = err
                time.sleep(0.35 * (attempt + 1))
        _PREFER_CURL = True
    for attempt in range(retries):
        try:
            completed = subprocess.run(
                ["curl", "-fsSL", "-A", USER_AGENT, "--max-time", "45", url],
                check=True,
                capture_output=True,
                text=True,
                timeout=50,
            )
            return json.loads(completed.stdout)
        except Exception as err:
            last_err = err
            time.sleep(0.35 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last_err}") from last_err


def logo_of(team: dict) -> str:
    logos = team.get("logos") or []
    for logo in logos:
        href = logo.get("href") or ""
        if "/500/" in href:
            return href
    if logos:
        return logos[0].get("href") or ""
    return ""


def stat_index(stats: list) -> dict:
    indexed = {}
    for stat in stats or []:
        indexed[stat.get("name")] = {
            "value": stat.get("value"),
            "display": stat.get("displayValue"),
        }
    return indexed


def as_number(stat: dict | None, default: float = 0) -> float:
    if not stat:
        return default
    value = stat.get("value")
    if isinstance(value, (int, float)):
        return float(value)
    text = str(stat.get("display") or "").replace("+", "").replace(",", "").strip()
    if text in {"", "-", "—"}:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def as_int(stat: dict | None, default: int = 0) -> int:
    return int(round(as_number(stat, default)))


def split_record(text: str | None) -> tuple[int, int, int]:
    parts: list[int] = []
    for piece in str(text or "0-0").split("-"):
        piece = piece.strip()
        if not piece:
            continue
        try:
            parts.append(int(float(piece)))
        except ValueError:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def record_text(wins: int, losses: int, ties: int = 0) -> str:
    if ties:
        return f"{wins}-{losses}-{ties}"
    return f"{wins}-{losses}"


def signed(value: float | int | None) -> str:
    if value is None:
        return "—"
    number = float(value)
    if abs(number - round(number)) < 0.05:
        number = int(round(number))
        return f"+{number}" if number > 0 else str(number)
    text = f"{number:.1f}"
    return f"+{text}" if number > 0 else text


def fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    text = f"{value:.3f}"
    return text[1:] if text.startswith("0") else text


def fmt_gb(value: float) -> str:
    if abs(value) < 0.05:
        return "—"
    mag = abs(value)
    text = str(int(round(mag))) if abs(mag - round(mag)) < 0.05 else f"{mag:.1f}"
    return f"+{text}" if value < 0 else text


def gb_words(value: float) -> str:
    mag = abs(value)
    if mag < 0.05:
        return "even"
    key = round(mag * 2) / 2
    labels = {
        0.5: "a half-game",
        1.0: "one game",
        1.5: "a game and a half",
        2.0: "two games",
        2.5: "two and a half games",
        3.0: "three games",
        4.0: "four games",
    }
    return labels.get(key, f"{mag:g} games")


def games_back(team: dict, pivot: dict) -> float:
    if team["abbr"] == pivot["abbr"]:
        return 0.0
    return ((pivot["wins"] - team["wins"]) + (team["losses"] - pivot["losses"])) / 2.0


def win_rate(team: dict) -> float:
    played = team["wins"] + team["losses"] + team["ties"]
    if played <= 0:
        return 0.5
    return (team["wins"] + 0.5 * team["ties"]) / played


def model_wp(points_for: float, points_against: float) -> float:
    scored = max(points_for, 0) + PRIOR_POINTS
    allowed = max(points_against, 0) + PRIOR_POINTS
    top = scored ** PYTH_EXP
    bottom = allowed ** PYTH_EXP
    if top + bottom == 0:
        return 0.5
    return top / (top + bottom)


def win_prob(home_wp: float, away_wp: float, neutral: bool = False) -> float:
    bump = 0.0 if neutral else HOME_BUMP
    probability = 0.5 + (home_wp - away_wp) * 0.9 + bump
    return min(0.88, max(0.12, probability))


def categories_of(side) -> list:
    if isinstance(side, dict):
        return side.get("categories") or []
    if isinstance(side, list) and side and isinstance(side[0], dict) and "stats" in side[0]:
        return side
    return []


def index_categories(categories: list) -> dict:
    indexed = {}
    for category in categories:
        bucket = {}
        for stat in category.get("stats") or []:
            bucket[stat.get("name")] = stat.get("value", stat.get("displayValue"))
            bucket[f"{stat.get('name')}__display"] = stat.get("displayValue")
        indexed[category.get("name")] = bucket
    return indexed


def num_from(bucket: dict, key: str, default=None):
    if key not in bucket or bucket[key] is None:
        return default
    value = bucket[key]
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace("+", "").replace("%", "").replace(",", "").strip()
    if text in {"", "-", "—"}:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def parse_team(entry: dict, conference: str) -> dict:
    raw = entry["team"]
    stats = stat_index(entry.get("stats"))
    wins = as_int(stats.get("wins"))
    losses = as_int(stats.get("losses"))
    ties = as_int(stats.get("ties"))
    points_for = as_int(stats.get("pointsFor"))
    points_against = as_int(stats.get("pointsAgainst"))
    diff = as_int(stats.get("pointDifferential"))
    div_w, div_l, div_t = split_record((stats.get("divisionRecord") or {}).get("display"))
    conf_w, conf_l, conf_t = split_record((stats.get("vs. Conf.") or {}).get("display"))
    abbr = raw.get("abbreviation") or ""
    division = ABBR_DIV.get(abbr, "Other")
    played = wins + losses + ties
    return {
        "abbr": abbr,
        "id": str(raw.get("id") or ""),
        "name": raw.get("displayName") or abbr,
        "nickname": raw.get("name") or raw.get("shortDisplayName") or abbr,
        "logo": logo_of(raw),
        "conference": conference,
        "division": division,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "gp": played,
        "pf": points_for,
        "pa": points_against,
        "diff": diff,
        "seed": as_int(stats.get("playoffSeed"), 99),
        "streak": (stats.get("streak") or {}).get("display") or "—",
        "divisionRecord": (stats.get("divisionRecord") or {}).get("display") or record_text(div_w, div_l, div_t),
        "conferenceRecord": (stats.get("vs. Conf.") or {}).get("display") or record_text(conf_w, conf_l, conf_t),
        "home": (stats.get("Home") or {}).get("display") or "—",
        "road": (stats.get("Road") or {}).get("display") or "—",
        "divWins": div_w,
        "confWins": conf_w,
        "wp": model_wp(points_for, points_against),
        "pct": win_rate({
            "wins": wins,
            "losses": losses,
            "ties": ties,
        }),
    }


def broadcast_names(comp: dict) -> str:
    names: list[str] = []
    for item in comp.get("broadcasts") or []:
        media = item.get("media") or {}
        candidates = list(item.get("names") or [])
        if media.get("shortName"):
            candidates.append(media["shortName"])
        for name in candidates:
            if name and name not in names:
                names.append(name)
    return ", ".join(names[:2])


def parse_schedule(payload: dict) -> tuple[list[dict], int | None]:
    games = []
    for event in payload.get("events") or []:
        comp = (event.get("competitions") or [{}])[0]
        status = (comp.get("status") or {}).get("type") or {}
        sides = {}
        for competitor in comp.get("competitors") or []:
            team = competitor.get("team") or {}
            score = competitor.get("score") or {}
            sides[competitor.get("homeAway")] = {
                "abbr": team.get("abbreviation") or "",
                "name": team.get("displayName") or team.get("name") or "",
                "nickname": team.get("name") or team.get("shortDisplayName") or "",
                "score": score.get("displayValue") if isinstance(score, dict) else score,
                "logo": logo_of(team),
            }
        if "home" not in sides or "away" not in sides:
            continue
        week = event.get("week") or {}
        games.append({
            "id": str(comp.get("id") or event.get("id")),
            "date": event.get("date") or comp.get("date") or "",
            "week": week.get("number"),
            "name": event.get("shortName") or event.get("name") or "",
            "completed": bool(status.get("completed")),
            "state": status.get("state") or "",
            "detail": status.get("shortDetail") or status.get("detail") or "",
            "home": sides["home"],
            "away": sides["away"],
            "venue": (comp.get("venue") or {}).get("fullName") or "",
            "broadcast": broadcast_names(comp),
            "neutral": bool(comp.get("neutralSite")),
        })
    bye = payload.get("byeWeek")
    try:
        bye_week = int(bye) if bye else None
    except (TypeError, ValueError):
        bye_week = None
    return games, bye_week


def load_standings() -> tuple[int, dict]:
    payload = fetch_json("https://site.web.api.espn.com/apis/v2/sports/football/nfl/standings")
    season = int((payload.get("season") or {}).get("year") or now_et().year)
    teams = {}
    for conference in payload.get("children") or []:
        conf_abbr = conference.get("abbreviation") or ""
        entries = (conference.get("standings") or {}).get("entries") or []
        for entry in entries:
            team = parse_team(entry, conf_abbr)
            if team["abbr"]:
                teams[team["abbr"]] = team
    if FINS not in teams:
        raise RuntimeError("Miami was not in the NFL standings feed")
    return season, teams


def load_schedules(season: int, teams: dict) -> dict:
    found: dict[str, tuple[list[dict], int | None]] = {}

    def pull(abbr: str) -> tuple[str, list[dict], int | None]:
        team_id = teams[abbr]["id"]
        url = (
            "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/"
            f"teams/{team_id}/schedule?season={season}"
        )
        games, bye = parse_schedule(fetch_json(url))
        return abbr, games, bye

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(pull, abbr) for abbr in teams]
        for future in as_completed(futures):
            abbr, games, bye = future.result()
            found[abbr] = (games, bye)
    return found


def load_team_stats(team_id: str) -> dict | None:
    url = f"https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/statistics"
    try:
        payload = fetch_json(url)
    except Exception:
        return None
    results = payload.get("results") or {}
    own = index_categories(categories_of(results.get("stats")))
    opp = index_categories(categories_of(results.get("opponent")))
    passing = own.get("passing") or {}
    rushing = own.get("rushing") or {}
    misc = own.get("miscellaneous") or {}
    defense = own.get("defensive") or {}
    opp_pass = opp.get("passing") or {}
    opp_def = opp.get("defensive") or {}
    games = num_from(passing, "teamGamesPlayed") or num_from(rushing, "teamGamesPlayed") or 0
    sacks_for = num_from(defense, "sacks", 0) or 0
    sacks_allowed = num_from(passing, "sacks", 0)
    if sacks_allowed is None:
        sacks_allowed = num_from(opp_def, "sacks", 0) or 0
    return {
        "ypg": num_from(passing, "yardsPerGame"),
        "yapg": num_from(opp_pass, "yardsPerGame"),
        "ppg": num_from(passing, "totalPointsPerGame"),
        "papg": num_from(opp_pass, "totalPointsPerGame"),
        "third": num_from(misc, "thirdDownConvPct"),
        "thirdDisplay": (misc.get("thirdDownEff__display") if misc else None),
        "rz": num_from(misc, "redzoneTouchdownPct"),
        "to": num_from(misc, "turnOverDifferential"),
        "topSeconds": num_from(misc, "possessionTimeSeconds"),
        "sacksFor": sacks_for,
        "sacksAllowed": sacks_allowed or 0,
        "qbRating": num_from(passing, "QBRating"),
        "completion": num_from(passing, "completionPct"),
        "gp": games,
    }


def athlete_id(ref: str) -> str:
    path = (ref or "").split("?")[0].rstrip("/")
    return path.split("/")[-1] if path else ""


def roster_index(payload: dict) -> tuple[dict, list]:
    indexed = {}
    injuries = []
    for group in payload.get("athletes") or []:
        group_name = group.get("position") or ""
        for player in group.get("items") or []:
            position = (player.get("position") or {}).get("abbreviation") or ""
            headshot = (player.get("headshot") or {}).get("href") or ""
            info = {
                "id": str(player.get("id") or ""),
                "name": player.get("displayName") or player.get("fullName") or "",
                "position": position,
                "jersey": player.get("jersey") or "",
                "headshot": headshot,
            }
            if info["id"]:
                indexed[info["id"]] = info
            injury_rows = player.get("injuries") or []
            on_ir = group_name == "injuredReserveOrOut"
            if not injury_rows and not on_ir:
                continue
            status = "IR" if on_ir else ""
            comment = ""
            if injury_rows and isinstance(injury_rows[0], dict):
                item = injury_rows[0]
                status = item.get("status") or status or "Injured"
                details = item.get("details") if isinstance(item.get("details"), dict) else {}
                comment = item.get("shortComment") or item.get("longComment") or details.get("type") or ""
            injuries.append({
                "name": info["name"],
                "position": position,
                "status": status or "Out",
                "detail": comment,
            })
    return indexed, injuries


def leader_list(payload: dict, name: str) -> list:
    for category in payload.get("categories") or []:
        if category.get("name") == name:
            return category.get("leaders") or []
    return []


def pack_leader(row: dict, roster: dict, stat_label: str) -> dict:
    aid = athlete_id((row.get("athlete") or {}).get("$ref") or "")
    info = roster.get(aid, {})
    value = row.get("value")
    display_value = row.get("displayValue") or ""
    short = display_value
    if isinstance(value, (int, float)) and stat_label in {"YDS", "TKL", "INT", "SACK", "RTG"}:
        short = str(int(value)) if float(value).is_integer() else f"{float(value):.1f}"
    return {
        "id": aid,
        "name": info.get("name") or "Dolphins",
        "position": info.get("position") or "",
        "jersey": info.get("jersey") or "",
        "headshot": info.get("headshot") or "",
        "line": display_value,
        "value": short,
        "statLabel": stat_label,
    }


def build_players(roster: dict, leaders: dict) -> dict:
    passing = leader_list(leaders, "passingLeader")
    rating_rows = {athlete_id((row.get("athlete") or {}).get("$ref") or ""): row for row in leader_list(leaders, "quarterbackRating")}
    quarterbacks = []
    qb_ids = set()
    if passing:
        qb = pack_leader(passing[0], roster, "RTG")
        rated = rating_rows.get(qb["id"])
        if rated and rated.get("value") is not None:
            qb["value"] = f"{float(rated['value']):.1f}"
            qb["statLabel"] = "RTG"
        qb["line"] = passing[0].get("displayValue") or qb["line"]
        quarterbacks.append(qb)
        qb_ids.add(qb["id"])

    skill = []
    seen = set(qb_ids)
    for row in leader_list(leaders, "rushingLeader")[:5]:
        player = pack_leader(row, roster, "YDS")
        if not player["id"] or player["id"] in seen:
            continue
        seen.add(player["id"])
        skill.append(player)
        if len(skill) == 4:
            break
    for row in leader_list(leaders, "receivingLeader")[:8]:
        player = pack_leader(row, roster, "YDS")
        if not player["id"] or player["id"] in seen:
            continue
        seen.add(player["id"])
        skill.append(player)
    skill.sort(key=lambda player: float(player["value"]) if str(player["value"]).replace(".", "", 1).isdigit() else 0, reverse=True)
    skill = skill[:8]

    defense = []
    defense_seen = {}
    for row in leader_list(leaders, "totalTackles")[:6]:
        player = pack_leader(row, roster, "TKL")
        if not player["id"]:
            continue
        defense_seen[player["id"]] = player
        defense.append(player)
    for row, label in (
        *[(item, "SACK") for item in leader_list(leaders, "sacks")[:4]],
        *[(item, "INT") for item in leader_list(leaders, "interceptions")[:4]],
    ):
        player = pack_leader(row, roster, label)
        if not player["id"]:
            continue
        if player["id"] in defense_seen:
            existing = defense_seen[player["id"]]
            extra = f"{player['value']} {label}"
            if extra not in existing["line"]:
                existing["line"] = f"{existing['line']} · {extra}" if existing["line"] else extra
            continue
        defense_seen[player["id"]] = player
        defense.append(player)
    return {
        "label": "Regular-season counting stats. Hover a label for the definition.",
        "quarterback": quarterbacks[:1],
        "skill": skill[:8],
        "defense": defense[:8],
    }


def fmt_clock(total_seconds: float | None, games: float) -> str:
    if not total_seconds or not games:
        return "—"
    per = int(round(total_seconds / games))
    return f"{per // 60}:{per % 60:02d}"


def local_dt(iso: str) -> datetime | None:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(TZ)
    except ValueError:
        return None


def fmt_when(iso: str, with_time: bool = True) -> str:
    moment = local_dt(iso)
    if not moment:
        return iso
    if with_time:
        return moment.strftime("%a, %b %-d · %-I:%M %p")
    return moment.strftime("%a, %b %-d")


def direction_for(kind: str, value: float | None) -> str:
    if value is None:
        return "flat"
    marks = {
        "diff": (0, 0),
        "margin": (0, 0),
        "third": (40, 34),
        "rz": (55, 40),
        "sack": (0, 0),
        "to": (0, 0),
        "top": (30, 28),
        "qb": (90, 80),
    }
    good, bad = marks.get(kind, (0, 0))
    if kind == "top":
        # value is minutes
        if value >= good:
            return "up"
        if value <= bad:
            return "down"
        return "flat"
    if value > good:
        return "up"
    if value < bad:
        return "down"
    return "flat"


def simulate(teams: dict, games: list[dict]) -> tuple[int, int, int]:
    rng = random.Random(2026)
    afc = [abbr for abbr, team in teams.items() if team["conference"] == "AFC"]
    divisions = {name: members for name, members in DIVISIONS.items() if name.startswith("AFC")}
    base = {
        abbr: {
            "wins": team["wins"],
            "div": team["divWins"],
            "conf": team["confWins"],
            "diff": team["diff"],
        }
        for abbr, team in teams.items()
    }
    made = division_titles = wildcards = 0
    for _ in range(SIMS):
        state = {abbr: dict(row) for abbr, row in base.items()}
        for game in games:
            home = game["home"]
            away = game["away"]
            home_wins = rng.random() < game["p"]
            margin = max(1, int(round(abs(rng.gauss((game["p"] - 0.5) * 16, 7)))))
            winner, loser = (home, away) if home_wins else (away, home)
            state[winner]["wins"] += 1
            state[winner]["diff"] += margin
            state[loser]["diff"] -= margin
            if game["sameDiv"]:
                state[winner]["div"] += 1
            if game["sameConf"]:
                state[winner]["conf"] += 1

        def rank(abbr: str) -> tuple:
            row = state[abbr]
            return (row["wins"], row["div"], row["conf"], row["diff"])

        winners = set()
        for members in divisions.values():
            present = [abbr for abbr in members if abbr in state]
            if present:
                winners.add(max(present, key=rank))
        pool = [abbr for abbr in afc if abbr not in winners]
        pool.sort(key=rank, reverse=True)
        wildcard = set(pool[:3])
        if FINS in winners:
            made += 1
            division_titles += 1
        elif FINS in wildcard:
            made += 1
            wildcards += 1
    return made, division_titles, wildcards


def unique_games(schedules: dict, teams: dict) -> list[dict]:
    seen = set()
    games = []
    for abbr, (rows, _bye) in schedules.items():
        for game in rows:
            if game["id"] in seen:
                continue
            home = game["home"]["abbr"]
            away = game["away"]["abbr"]
            if home not in teams or away not in teams:
                continue
            if game["completed"]:
                continue
            if teams[home]["conference"] != "AFC" and teams[away]["conference"] != "AFC":
                continue
            seen.add(game["id"])
            games.append({
                "id": game["id"],
                "date": game["date"],
                "week": game["week"],
                "home": home,
                "away": away,
                "neutral": game["neutral"],
                "sameDiv": teams[home]["division"] == teams[away]["division"] and teams[home]["division"] != "Other",
                "sameConf": teams[home]["conference"] == teams[away]["conference"],
                "p": win_prob(teams[home]["wp"], teams[away]["wp"], game["neutral"]),
                "venue": game["venue"],
                "broadcast": game["broadcast"],
                "detail": game["detail"],
                "state": game["state"],
                "name": game["name"],
            })
    games.sort(key=lambda game: (game.get("date") or "", game["id"]))
    return games


def miami_games(schedules: dict) -> list[dict]:
    rows, bye = schedules.get(FINS, ([], None))
    return rows, bye


def attach_remaining(teams: dict, schedules: dict) -> None:
    for abbr, team in teams.items():
        rows, _bye = schedules.get(abbr, ([], None))
        left = [game for game in rows if not game["completed"]]
        team["gr"] = len(left) if rows else max(0, SEASON_GAMES - team["gp"])


def public_team(team: dict, **extra) -> dict:
    row = {
        "abbr": team["abbr"],
        "name": team["name"],
        "nickname": team["nickname"],
        "logo": team["logo"],
        "conference": team["conference"],
        "division": team["division"],
        "seed": team["seed"],
        "wins": team["wins"],
        "losses": team["losses"],
        "ties": team["ties"],
        "record": record_text(team["wins"], team["losses"], team["ties"]),
        "pct": round(team["pct"], 3),
        "pf": team["pf"],
        "pa": team["pa"],
        "diff": team["diff"],
        "ppg": round(team["pf"] / team["gp"], 1) if team["gp"] else None,
        "papg": round(team["pa"] / team["gp"], 1) if team["gp"] else None,
        "streak": team["streak"],
        "divisionRecord": team["divisionRecord"],
        "conferenceRecord": team["conferenceRecord"],
        "home": team["home"],
        "road": team["road"],
        "gr": team.get("gr"),
        "ypg": team.get("ypg"),
        "yapg": team.get("yapg"),
        "to": team.get("to"),
    }
    row.update(extra)
    return row


def path_label(team: dict) -> str:
    if team["seed"] <= 4:
        short = team["division"].replace("AFC ", "").replace("NFC ", "")
        return f"{short} champ"
    if team["seed"] <= 7:
        return "Wild card"
    return "Outside"


def build_payload() -> dict:
    season, teams = load_standings()
    schedules = load_schedules(season, teams)
    attach_remaining(teams, schedules)
    east_ids = [teams[abbr]["id"] for abbr in ("BUF", "MIA", "NE", "NYJ") if abbr in teams]
    stats_by_id = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(load_team_stats, team_id): team_id for team_id in east_ids}
        for future in as_completed(futures):
            stats_by_id[futures[future]] = future.result()
    for abbr in EAST:
        stats = stats_by_id.get(teams[abbr]["id"]) if abbr in teams else None
        if not stats:
            continue
        teams[abbr]["ypg"] = None if stats["ypg"] is None else round(stats["ypg"], 1)
        teams[abbr]["yapg"] = None if stats["yapg"] is None else round(stats["yapg"], 1)
        teams[abbr]["to"] = None if stats["to"] is None else int(round(stats["to"]))
        if abbr == FINS:
            teams[abbr]["efficiency"] = stats

    fins = teams[FINS]
    efficiency = fins.get("efficiency") or {}
    mia_rows, bye_week = miami_games(schedules)
    upcoming_models = unique_games(schedules, teams)
    made, division_titles, wildcards = simulate(teams, upcoming_models)
    odds = 100 * made / SIMS
    division_odds = 100 * division_titles / SIMS
    wildcard_odds = 100 * wildcards / SIMS

    afc = [team for team in teams.values() if team["conference"] == "AFC"]
    afc.sort(key=lambda team: (team["seed"], -team["wins"], team["losses"], -team["diff"]))
    cut = next((team for team in afc if team["seed"] == 7), afc[6] if len(afc) > 6 else afc[-1])
    east = [teams[abbr] for abbr in ("BUF", "MIA", "NE", "NYJ") if abbr in teams]
    east.sort(key=lambda team: (team["seed"], -team["wins"], -team["diff"]))
    east_leader = east[0]
    gb_cut = games_back(fins, cut)
    gb_div = games_back(fins, east_leader)
    in_field = fins["seed"] <= 7
    mia_max = fins["wins"] + int(fins.get("gr") or 0)
    teams_clear = [team for team in afc if team["abbr"] != FINS and team["wins"] > mia_max]
    eliminated = len(teams_clear) >= 7
    clinched = all(
        team["wins"] + int(team.get("gr") or 0) < fins["wins"]
        for team in afc
        if team["abbr"] != FINS
    )

    rivals = [team for team in east if team["abbr"] != FINS]
    magic_rows = []
    for rival in rivals:
        magic_rows.append((18 - fins["wins"] - rival["losses"], rival))
    magic_rows.sort(key=lambda item: item[0], reverse=True)
    magic, magic_rival = magic_rows[0]
    elim_rows = [(18 - fins["losses"] - rival["wins"], rival) for rival in rivals]
    elim_rows.sort(key=lambda item: item[0])
    elimination, elim_rival = elim_rows[0]

    def fins_win_pct(opponent: str, miami_home: bool, neutral: bool) -> int:
        opp = teams[opponent]
        if miami_home:
            probability = win_prob(fins["wp"], opp["wp"], neutral)
        else:
            probability = 1 - win_prob(opp["wp"], fins["wp"], neutral)
        return int(round(probability * 100))

    schedule_cards = []
    recent = []
    for game in mia_rows:
        home = game["home"]["abbr"]
        away = game["away"]["abbr"]
        miami_home = home == FINS
        opponent = away if miami_home else home
        opp = teams.get(opponent, {})
        us_score = game["home"]["score"] if miami_home else game["away"]["score"]
        them_score = game["away"]["score"] if miami_home else game["home"]["score"]
        card = {
            "id": game["id"],
            "date": game["date"],
            "week": game["week"],
            "isHome": miami_home,
            "opponent": {
                "abbr": opponent,
                "name": opp.get("name") or game["away" if miami_home else "home"]["name"],
                "nickname": opp.get("nickname") or "",
                "logo": opp.get("logo") or "",
                "record": record_text(opp["wins"], opp["losses"], opp["ties"]) if opp else "",
                "pct": opp.get("pct"),
            },
            "divisionGame": opponent in EAST,
            "conferenceGame": opp.get("conference") == "AFC",
            "venue": game["venue"],
            "broadcast": game["broadcast"],
            "detail": game["detail"],
            "live": game["state"] == "in",
            "final": game["completed"],
            "finsWinPct": fins_win_pct(opponent, miami_home, game["neutral"]) if opponent in teams and not game["completed"] else None,
            "homeAbbr": home,
            "awayAbbr": away,
            "homeScore": game["home"]["score"],
            "awayScore": game["away"]["score"],
            "usScore": us_score,
            "themScore": them_score,
        }
        if game["completed"]:
            try:
                us_n = float(us_score)
                them_n = float(them_score)
            except (TypeError, ValueError):
                us_n = them_n = 0
            card["result"] = "W" if us_n > them_n else "L" if us_n < them_n else "T"
            recent.append(card)
        else:
            schedule_cards.append(card)

    if bye_week:
        current_week = min([game["week"] for game in schedule_cards if game.get("week")], default=bye_week)
        if bye_week >= current_week:
            schedule_cards.append({
                "bye": True,
                "week": bye_week,
                "date": "",
                "isHome": True,
                "opponent": {},
                "venue": "Open date",
                "broadcast": "",
                "finsWinPct": None,
                "final": False,
                "live": False,
            })
    schedule_cards.sort(key=lambda game: (game.get("week") or 99, game.get("date") or ""))

    remaining_games = [game for game in schedule_cards if not game.get("bye") and not game.get("final")]
    sos_values = [game["opponent"].get("pct") for game in remaining_games if game["opponent"].get("pct") is not None]
    sos = sum(sos_values) / len(sos_values) if sos_values else None
    home_left = sum(1 for game in remaining_games if game["isHome"])
    division_left = sum(1 for game in remaining_games if game.get("divisionGame"))

    next_game = remaining_games[0] if remaining_games else None
    next_label = "Season complete"
    if next_game:
        moment = local_dt(next_game["date"])
        day = moment.strftime("%a") if moment else "Next"
        spot = "vs" if next_game["isHome"] else "@"
        next_label = f"{day} {spot} {next_game['opponent']['abbr']}"

    leaders = []
    for division in ("AFC East", "AFC North", "AFC South", "AFC West"):
        members = [teams[abbr] for abbr in DIVISIONS[division] if abbr in teams]
        if not members:
            continue
        leader = min(members, key=lambda team: (team["seed"], -team["wins"], -team["diff"]))
        leaders.append(public_team(leader))

    def row_for(team: dict, pivot: dict, cut_team: bool = False) -> dict:
        return public_team(
            team,
            gb=fmt_gb(games_back(team, pivot)),
            gbValue=round(games_back(team, pivot), 2),
            path=path_label(team),
            inField=team["seed"] <= 7,
            isFins=team["abbr"] == FINS,
            isCut=team["abbr"] == cut_team if isinstance(cut_team, str) else team["seed"] == 7,
        )

    conference_rows = []
    for team in afc:
        conference_rows.append(row_for(team, cut))
    east_rows = [row_for(team, east_leader) for team in east]
    for row, team in zip(east_rows, east):
        row["isCut"] = False
        row["divisionCut"] = team["abbr"] == east_leader["abbr"]

    rooting = []
    horizon = now_et() + timedelta(days=12)
    candidates = []
    for game in upcoming_models:
        moment = local_dt(game["date"])
        if not moment or moment > horizon:
            continue
        involved = {game["home"], game["away"]}
        priority = 5
        if FINS in involved:
            priority = 0
        elif involved & EAST:
            priority = 1
        elif any(teams[abbr]["seed"] == 7 for abbr in involved):
            priority = 2
        elif any(teams[abbr]["conference"] == "AFC" and teams[abbr]["seed"] <= 10 for abbr in involved):
            priority = 3
        else:
            continue
        candidates.append((moment, priority, game))
    candidates.sort(key=lambda item: (item[0], item[1]))
    for moment, _priority, game in candidates[:8]:
        home = teams[game["home"]]
        away = teams[game["away"]]
        home_pct = int(round(game["p"] * 100))
        away_pct = 100 - home_pct
        if FINS in (game["home"], game["away"]):
            tag = "Fins game"
            tag_class = "jays"
            opp = away if game["home"] == FINS else home
            spot = "at home" if game["home"] == FINS else "on the road"
            note = f"Miami is {spot} against the {opp['nickname']}."
        else:
            notes = []
            for club in (away, home):
                if club["abbr"] in EAST and club["abbr"] != FINS:
                    notes.append(f"A {club['nickname']} loss helps the East race.")
                elif club["conference"] == "AFC" and club["seed"] <= 7:
                    notes.append(f"The {club['nickname']} hold the No. {club['seed']} seed. A loss helps the cut line.")
            tag = "Need a loss" if notes else "AFC game"
            tag_class = "need" if notes else "race"
            note = " ".join(notes[:2]) or "Two clubs still in the AFC picture."
        rooting.append({
            "date": game["date"],
            "homeAbbr": home["abbr"],
            "awayAbbr": away["abbr"],
            "homeWinPct": home_pct,
            "awayWinPct": away_pct,
            "interest": tag,
            "tagClass": tag_class,
            "note": note,
            "live": False,
        })

    h2h = []
    for game in recent:
        if game["opponent"]["abbr"] in EAST:
            h2h.append(
                f"{game['result']} {game['usScore']}–{game['themScore']} "
                f"{'vs' if game['isHome'] else '@'} {game['opponent']['abbr']}"
            )
    next_division = next((game for game in remaining_games if game.get("divisionGame")), None)
    if h2h:
        h2h_text = "Head-to-head inside the East: " + "; ".join(h2h) + "."
    elif next_division:
        h2h_text = (
            f"No AFC East games yet. The first is Week {next_division['week']} "
            f"{'vs' if next_division['isHome'] else '@'} {next_division['opponent']['abbr']}."
        )
    else:
        h2h_text = "No AFC East games left on the schedule."

    ppg = efficiency.get("ppg")
    papg = efficiency.get("papg")
    third = efficiency.get("third")
    rz = efficiency.get("rz")
    sack_margin = None
    if efficiency:
        sack_margin = (efficiency.get("sacksFor") or 0) - (efficiency.get("sacksAllowed") or 0)
    turnover = efficiency.get("to")
    top_text = fmt_clock(efficiency.get("topSeconds"), efficiency.get("gp") or fins["gp"] or 0)
    top_minutes = None
    if efficiency.get("topSeconds") and (efficiency.get("gp") or fins["gp"]):
        top_minutes = (efficiency["topSeconds"] / (efficiency.get("gp") or fins["gp"])) / 60
    ypg = efficiency.get("ypg")
    yapg = efficiency.get("yapg")
    qb = efficiency.get("qbRating")

    if eliminated:
        headline = "See ya next season"
        kicker = "Mathematically out"
        blurb = "The Dolphins cannot catch seven AFC teams even if they win out."
    elif clinched:
        headline = "January football"
        kicker = "Playoff berth clinched"
        blurb = f"The Dolphins are in. They are the AFC No. {fins['seed']} seed at {record_text(fins['wins'], fins['losses'], fins['ties'])}."
    elif in_field:
        headline = f"Holding the No. {fins['seed']} seed"
        kicker = "Inside the AFC field"
        blurb = (
            f"The Dolphins are {record_text(fins['wins'], fins['losses'], fins['ties'])} and currently in. "
            f"The cushion on the cut line is {gb_words(abs(gb_cut))}."
        )
    elif gb_div <= gb_cut:
        headline = f"{gb_words(gb_div).capitalize()} back of the East"
        kicker = "AFC playoff race"
        blurb = (
            f"The Dolphins are {record_text(fins['wins'], fins['losses'], fins['ties'])} with a {signed(fins['diff'])} point differential, "
            f"{gb_words(gb_div)} behind the {east_leader['nickname']} in the AFC East, and {gb_words(gb_cut)} off the last wild-card berth. "
            f"{fins.get('gr', 0)} games left"
        )
    else:
        headline = f"{gb_words(gb_cut).capitalize()} off the cut line"
        kicker = "AFC playoff race"
        blurb = (
            f"The Dolphins are {record_text(fins['wins'], fins['losses'], fins['ties'])} with a {signed(fins['diff'])} point differential, "
            f"{gb_words(gb_cut)} behind the last AFC playoff spot, and {gb_words(gb_div)} back of the {east_leader['nickname']} in the East. "
            f"{fins.get('gr', 0)} games left"
        )
    if next_game and not eliminated and not clinched and not in_field:
        moment = local_dt(next_game["date"])
        day = moment.strftime("%A") if moment else "next"
        if next_game["isHome"]:
            blurb += f", starting {day} at home against the {next_game['opponent']['nickname']}."
        else:
            blurb += f", starting {day} at the {next_game['opponent']['nickname']}."
    elif not blurb.endswith("."):
        blurb += "."

    if in_field and not eliminated:
        primary = {"label": "AFC playoff seed", "value": f"#{fins['seed']}", "sub": "Inside the field of seven", "heatLabel": "Season left"}
    elif eliminated:
        primary = {"label": "Playoff berth", "value": "OUT", "sub": "Cannot catch the field", "heatLabel": "Season left"}
    else:
        primary = {
            "label": "Games back of the cut line",
            "value": fmt_gb(gb_cut),
            "sub": f"of the No. 7 seed · {cut['abbr']} {record_text(cut['wins'], cut['losses'], cut['ties'])}",
            "heatLabel": "Season left",
        }
    games_left = int(fins.get("gr") or 0)
    primary["heat"] = int(round(100 * games_left / SEASON_GAMES)) if SEASON_GAMES else 0
    primary["heatText"] = f"{games_left} left"

    if clinched and fins["division"] == east_leader["division"] and fins["abbr"] == east_leader["abbr"] and magic <= 0:
        magic_meter = {"label": "AFC East", "value": "IN", "sub": "Division clinched on wins", "note": ""}
    elif eliminated:
        magic_meter = {"label": "Elimination", "value": "OUT", "sub": "The East and the wild card are both gone", "note": ""}
    else:
        magic_meter = {
            "label": "Magic number to win the East",
            "value": "0" if magic <= 0 else str(magic),
            "sub": f"MIA wins + {magic_rival['abbr']} losses",
            "note": (
                f"The {magic_rival['nickname']} are the team to catch. "
                f"Elimination number vs the {elim_rival['nickname']} is {max(elimination, 0)}."
            ),
        }

    odds_note = (
        f"Division title in {division_odds:.1f}% of sims, wild card in {wildcard_odds:.1f}%. "
        "Point differential, shrunk toward average, plus home field. Not a betting line."
    )

    def kpi(stat: str, label: str, value, hint: str) -> dict:
        return {"stat": stat, "label": label, "value": value, "hint": hint}

    third_display = efficiency.get("thirdDisplay") or ("—" if third is None else f"{third:.0f}%")
    kpis = [
        kpi("W-L", "Record", record_text(fins["wins"], fins["losses"], fins["ties"]), fins["streak"] if fins["streak"] != "—" else "This season"),
        kpi("DIFF", "Point diff", signed(fins["diff"]), "Points scored minus points allowed"),
        kpi("PPG", "Points / game", "—" if ppg is None else f"{ppg:.1f}", "League average sits near 22"),
        kpi("PA", "Points allowed", "—" if papg is None else f"{papg:.1f}", "Per game. Lower is the whole defense"),
        kpi("YPG", "Yards / game", "—" if ypg is None else f"{ypg:.1f}", "Total offense, pass plus rush"),
        kpi("YPG", "Yards allowed", "—" if yapg is None else f"{yapg:.1f}", "What the defense is giving up"),
        kpi("TO", "Turnover margin", "—" if turnover is None else signed(turnover), "Takeaways minus giveaways"),
        kpi("3rd", "Third down", "—" if third is None else f"{third:.0f}%", f"{third_display} · around 40% is average" if third_display else "Around 40% is average"),
        kpi("RZ", "Red zone TDs", "—" if rz is None else f"{rz:.0f}%", "Trips inside the 20 that become touchdowns"),
        kpi("SACK", "Sack margin", "—" if sack_margin is None else signed(sack_margin), "Sacks recorded minus sacks allowed"),
        kpi("DIV", "Division", fins["divisionRecord"], "AFC East record. First tiebreaker after head-to-head"),
        kpi("CONF", "Conference", fins["conferenceRecord"], "AFC record. Matters once division record is tied"),
    ]

    scoring_margin = None if ppg is None or papg is None else ppg - papg
    trends = [
        {
            "stat": "DIFF",
            "label": "Point differential",
            "value": signed(fins["diff"]),
            "detail": "The cleanest 'are they actually this good?' check.",
            "direction": direction_for("diff", fins["diff"]),
        },
        {
            "stat": "PPG",
            "label": "Scoring margin / game",
            "value": "—" if scoring_margin is None else signed(round(scoring_margin, 1)),
            "detail": "—" if ppg is None else f"{ppg:.1f} scored, {papg:.1f} allowed.",
            "direction": direction_for("margin", scoring_margin),
        },
        {
            "stat": "3rd",
            "label": "Third down",
            "value": "—" if third is None else f"{third:.0f}%",
            "detail": third_display if third_display else "Conversions on third down.",
            "direction": direction_for("third", third),
        },
        {
            "stat": "RZ",
            "label": "Red zone TDs",
            "value": "—" if rz is None else f"{rz:.0f}%",
            "detail": "Touchdown rate inside the opponent 20.",
            "direction": direction_for("rz", rz),
        },
        {
            "stat": "SACK",
            "label": "Sack margin",
            "value": "—" if sack_margin is None else signed(sack_margin),
            "detail": "Pass rush minus pass protection.",
            "direction": direction_for("sack", sack_margin),
        },
        {
            "stat": "TOP",
            "label": "Time of possession",
            "value": top_text,
            "detail": "Per game. Thirty minutes is a split clock.",
            "direction": direction_for("top", top_minutes),
        },
    ]

    division_path = {
        "title": "AFC East",
        "value": "IN" if fins["abbr"] == east_leader["abbr"] and fins["seed"] <= 4 else f"{fmt_gb(gb_div)} GB",
        "detail": (
            f"The {east_leader['nickname']} lead at {record_text(east_leader['wins'], east_leader['losses'], east_leader['ties'])}. "
            f"Dolphins are {fins['divisionRecord']} inside the division. Win the East and the seed is automatic."
        ),
        "in": fins["seed"] <= 4,
    }
    wildcard_path = {
        "title": "Wild card",
        "value": "IN" if 5 <= fins["seed"] <= 7 else ("Not needed" if fins["seed"] <= 4 else f"{fmt_gb(gb_cut)} GB"),
        "detail": (
            f"The {cut['nickname']} hold the last berth at {record_text(cut['wins'], cut['losses'], cut['ties'])}. "
            "Three wild cards get in after the four division winners."
        ),
        "in": 5 <= fins["seed"] <= 7,
    }

    projected = fins["wins"] + games_left * fins["wp"]
    chips = [
        {"label": "Record", "value": record_text(fins["wins"], fins["losses"], fins["ties"])},
        {"label": "AFC seed", "value": f"No. {fins['seed']}"},
        {"label": "Streak", "value": fins["streak"]},
        {"label": "Next", "value": next_label},
        {"label": "Point diff", "value": signed(fins["diff"])},
        {"label": "Projected wins", "value": f"{projected:.1f}"},
    ]

    ticker = [
        f"DOLPHINS {record_text(fins['wins'], fins['losses'], fins['ties'])}",
        f"AFC NO. {fins['seed']}",
        fins["streak"],
        f"POINT DIFF {signed(fins['diff'])}",
        f"{fmt_gb(gb_div)} GB OF {east_leader['abbr']} IN THE EAST",
        f"{fmt_gb(gb_cut)} GB OF THE CUT LINE",
        f"NEXT {next_label.upper()}",
    ]
    if bye_week:
        ticker.append(f"BYE WEEK {bye_week}")
    if qb is not None:
        ticker.append(f"PASSER RATING {qb:.1f}")

    players = {"quarterback": [], "skill": [], "defense": [], "label": ""}
    injuries = []
    try:
        roster_payload = fetch_json(
            "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/teams/15/roster"
        )
        leaders_payload = fetch_json(
            "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/"
            f"seasons/{season}/types/2/teams/15/leaders"
        )
        roster, injuries = roster_index(roster_payload)
        players = build_players(roster, leaders_payload)
    except Exception:
        players = {"quarterback": [], "skill": [], "defense": [], "label": "Roster feed was unavailable on this refresh."}

    compare = []
    for team in east:
        item = public_team(team)
        compare.append(item)

    return {
        "generatedAt": now_et().isoformat(),
        "season": season,
        "seasonGames": SEASON_GAMES,
        "team": FINS,
        "teamName": fins["name"],
        "eliminated": eliminated,
        "clinched": clinched,
        "ticker": ticker,
        "narrative": {"kicker": kicker, "headline": headline, "blurb": blurb},
        "chips": chips,
        "meters": {"primary": primary, "third": magic_meter},
        "playoffOdds": {
            "percent": round(odds, 2),
            "sims": SIMS,
            "note": odds_note,
            "divisionPercent": round(division_odds, 2),
            "wildcardPercent": round(wildcard_odds, 2),
        },
        "kpis": kpis,
        "trends": trends,
        "paths": {"division": division_path, "wildcard": wildcard_path},
        "tableBlurb": "Seven AFC clubs play on: four division winners and three wild cards. The line under the seventh seed is the whole race.",
        "legend": {"in": "In a playoff spot", "out": "Chasing"},
        "conference": conference_rows,
        "east": east_rows,
        "leaders": leaders,
        "compareTitle": "AFC East",
        "compare": compare,
        "remaining": {
            "games": len(remaining_games),
            "home": home_left,
            "away": len(remaining_games) - home_left,
            "division": division_left,
            "bye": bye_week,
            "sos": None if sos is None else round(sos, 3),
        },
        "schedule": schedule_cards,
        "rooting": rooting,
        "recent": recent,
        "recentBlurb": "The games already in the book.",
        "tiebreak": {
            "division": fins["divisionRecord"],
            "conference": fins["conferenceRecord"],
            "diff": signed(fins["diff"]),
            "headToHead": h2h_text,
            "detail": (
                "If the East finishes level, the NFL starts with head-to-head, then division record, "
                "then common games, then conference record. Point differential is the eye test. "
                "It is not the first tiebreaker."
            ),
            "elimination": max(elimination, 0),
            "elimRival": elim_rival["abbr"],
        },
        "injuries": injuries,
        "players": players,
        "qbRating": None if qb is None else round(qb, 1),
    }


def stable(payload: dict) -> str:
    copy = dict(payload)
    copy.pop("generatedAt", None)
    return json.dumps(copy, sort_keys=True, separators=(",", ":"))


def main() -> None:
    payload = build_payload()
    fresh = stable(payload)
    if OUT_PATH.exists():
        try:
            previous = json.loads(OUT_PATH.read_text())
        except json.JSONDecodeError:
            previous = None
        if previous and stable(previous) == fresh:
            print("No standings or schedule changes.")
            return
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    odds = payload["playoffOdds"]["percent"]
    fins = next(team for team in payload["conference"] if team["isFins"])
    print(
        f"Wrote {OUT_PATH.name}: {fins['record']}, seed {fins['seed']}, "
        f"playoff odds {odds}%, {payload['remaining']['games']} games left."
    )


if __name__ == "__main__":
    main()
