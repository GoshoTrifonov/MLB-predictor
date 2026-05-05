"""
MLB Batter Strikeout (OVER 0.5) Picks — 3 Models for A/B/C comparison
- Model A: Form only (high K rate baseline)
- Model B: Form + Pitcher K/9 difficulty
- Model C: Form + Pitcher + Home/Away (full)

Goal: Identify batters MOST LIKELY to strike out at least once.
"""

import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from picks_storage import save_todays_picks

TORONTO_TZ = ZoneInfo("America/Toronto")

st.set_page_config(page_title="K Picks", page_icon="🎰", layout="wide")
st.title("🎰 MLB Batter Strikeout OVER 0.5 Picks")
st.caption(f"3-model A/B/C comparison • {datetime.now(TORONTO_TZ).strftime('%A, %B %d, %Y')}")

TEAM_IDS = [108,109,110,111,112,113,114,115,116,117,118,119,120,121,133,
            134,135,136,137,138,139,140,141,142,143,144,145,146,147,158]

TEAM_NAMES = {
    108:"LAA",109:"ARI",110:"BAL",111:"BOS",112:"CHC",113:"CIN",114:"CLE",
    115:"COL",116:"DET",117:"HOU",118:"KCR",119:"LAD",120:"WSN",121:"NYM",
    133:"OAK",134:"PIT",135:"SDP",136:"SEA",137:"SFG",138:"STL",139:"TBR",
    140:"TEX",141:"TOR",142:"MIN",143:"PHI",144:"ATL",145:"CHW",146:"MIA",
    147:"NYY",158:"MIL"
}

LEAGUE_AVG_K9 = 8.7

@st.cache_data(ttl=3600)
def get_team_form(team_id, days_back=15):
    end = datetime.now(TORONTO_TZ).date()
    start = end - timedelta(days=days_back)
    url = "https://statsapi.mlb.com/api/v1/stats"
    params = {
        "stats":"byDateRange","group":"hitting",
        "startDate":start.strftime("%Y-%m-%d"),
        "endDate":end.strftime("%Y-%m-%d"),
        "teamId":team_id,"season":end.year,"sportIds":1,
    }
    try:
        return requests.get(url, params=params, timeout=10).json()
    except Exception:
        return {}

@st.cache_data(ttl=3600)
def get_team_splits(team_id):
    season = datetime.now(TORONTO_TZ).year
    url = "https://statsapi.mlb.com/api/v1/stats"
    params = {
        "stats": "statSplits", "group": "hitting", "sitCodes": "h,a",
        "teamId": team_id, "season": season, "sportIds": 1,
    }
    try:
        return requests.get(url, params=params, timeout=10).json()
    except Exception:
        return {}

def parse_team_splits(data):
    out = {}
    for split in data.get("stats", []):
        for s in split.get("splits", []):
            sit = s.get("split", {}).get("code")
            pid = s.get("player", {}).get("id")
            if not pid: continue
            ops = pd.to_numeric(s.get("stat", {}).get("ops"), errors="coerce")
            if pid not in out: out[pid] = {}
            if sit == "h":   out[pid]["home_ops"] = ops
            elif sit == "a": out[pid]["away_ops"] = ops
    return out

@st.cache_data(ttl=3600)
def get_todays_matchups():
    today = datetime.now(TORONTO_TZ).strftime("%Y-%m-%d")
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}&hydrate=probablePitcher"
    try:
        data = requests.get(url, timeout=10).json()
    except Exception:
        return {}
    matchups = {}
    for d in data.get("dates", []):
        for g in d.get("games", []):
            home, away = g["teams"]["home"], g["teams"]["away"]
            home_id, away_id = home["team"]["id"], away["team"]["id"]
            home_pit = home.get("probablePitcher", {})
            away_pit = away.get("probablePitcher", {})
            matchups[home_id] = {
                "opp_pit_id": away_pit.get("id"),
                "opp_pit_name": away_pit.get("fullName", "TBD"),
                "opp_team": TEAM_NAMES.get(away_id, str(away_id)),
                "is_home": True,
            }
            matchups[away_id] = {
                "opp_pit_id": home_pit.get("id"),
                "opp_pit_name": home_pit.get("fullName", "TBD"),
                "opp_team": TEAM_NAMES.get(home_id, str(home_id)),
                "is_home": False,
            }
    return matchups

@st.cache_data(ttl=3600)
def get_pitcher_k9(pitcher_id):
    if pitcher_id is None: return None
    season = datetime.now(TORONTO_TZ).year
    url = f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats"
    params = {"stats":"season","group":"pitching","season":season}
    try:
        data = requests.get(url, params=params, timeout=10).json()
        for split in data.get("stats", []):
            for s in split.get("splits", []):
                stat = s.get("stat", {})
                k9 = pd.to_numeric(stat.get("strikeoutsPer9Inn"), errors="coerce")
                if pd.notna(k9):
                    return {"k9": k9}
                ks = stat.get("strikeOuts", 0)
                ip = pd.to_numeric(stat.get("inningsPitched", "0.0"), errors="coerce")
                if pd.notna(ip) and ip > 0:
                    return {"k9": (ks * 9) / ip}
    except Exception:
        pass
    return None

@st.cache_data(ttl=3600)
def get_player_gamelog(player_id):
    season = datetime.now(TORONTO_TZ).year
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
    params = {"stats": "gameLog", "group": "hitting", "season": season}
    try:
        data = requests.get(url, params=params, timeout=10).json()
        games = []
        for split_group in data.get("stats", []):
            for s in split_group.get("splits", []):
                stat = s.get("stat", {})
                ks = stat.get("strikeOuts", 0)
                is_home = s.get("isHome", None)
                games.append({"ks": ks, "is_home": is_home})
        return games
    except Exception:
        return []

@st.cache_data(ttl=3600)
def fetch_all_batters(days_back=15):
    rows = []
    splits_by_player = {}
    for tid in TEAM_IDS:
        data = get_team_form(tid, days_back)
        splits_data = get_team_splits(tid)
        splits_by_player.update(parse_team_splits(splits_data))
        for split in data.get("stats", []):
            for s in split.get("splits", []):
                p = s.get("player", {})
                st_ = s.get("stat", {})
                g = st_.get("gamesPlayed", 0)
                if g < 3: continue
                ks = st_.get("strikeOuts", 0)
                pa = st_.get("plateAppearances", 0)
                pid = p.get("id")
                rows.append({
                    "player_id": pid,
                    "Player":   p.get("fullName"),
                    "team_id":  tid,
                    "Team":     TEAM_NAMES.get(tid, str(tid)),
                    "G":        g,
                    "PA":       pa,
                    "K/G":      round(ks / g, 2) if g else 0,
                    "K/PA":     round(ks / pa, 3) if pa else 0,
                    "AVG":      pd.to_numeric(st_.get("avg"), errors="coerce"),
                    "OPS":      pd.to_numeric(st_.get("ops"), errors="coerce"),
                    "home_ops": splits_by_player.get(pid, {}).get("home_ops"),
                    "away_ops": splits_by_player.get(pid, {}).get("away_ops"),
                })
        time.sleep(0.1)
    return pd.DataFrame(rows)

# Sidebar
days = st.sidebar.slider("Days back for form", 5, 20, 15)
min_games = st.sidebar.slider("Minimum games played", 3, 10, 7)
search = st.sidebar.text_input("Search player").lower()
which_model = st.sidebar.radio("Display model", ["Model C (Full)","Model B","Model A"], index=0)
k_threshold = st.sidebar.slider("Win = Ks ≥", 1, 3, 1)

with st.spinner("Pulling batter form + splits..."):
    df = fetch_all_batters(days)

with st.spinner("Pulling tonight's matchups..."):
    matchups = get_todays_matchups()

df = df[df["G"] >= min_games].dropna(subset=["AVG","OPS"])
df = df[df["team_id"].isin(matchups.keys())].copy()

df["Opp Pitcher"] = df["team_id"].map(lambda t: matchups.get(t, {}).get("opp_pit_name", "TBD"))
df["Opp Team"]    = df["team_id"].map(lambda t: matchups.get(t, {}).get("opp_team", "?"))
df["opp_pit_id"]  = df["team_id"].map(lambda t: matchups.get(t, {}).get("opp_pit_id"))
df["is_home"]     = df["team_id"].map(lambda t: matchups.get(t, {}).get("is_home", False))
df["H/A"]         = df["is_home"].map({True:"🏠", False:"✈️"})

# Pitcher fetch
unique_pitchers = df["opp_pit_id"].dropna().unique()
pitcher_cache = {}
prog = st.progress(0, text="Fetching pitcher K/9 stats...")
for i, pid in enumerate(unique_pitchers):
    pitcher_cache[int(pid)] = get_pitcher_k9(int(pid))
    prog.progress((i+1) / len(unique_pitchers))
prog.empty()

# Last 7 streak
streak_ids = df["player_id"].dropna().unique()
streak_prog = st.progress(0, text="Fetching last 7 game logs...")
for i, pid in enumerate(streak_ids):
    get_player_gamelog(int(pid))
    streak_prog.progress((i + 1) / len(streak_ids))
streak_prog.empty()

def make_last7(player_id, ks_for_win=1):
    games = get_player_gamelog(int(player_id))
    last7 = games[-7:]
    icons = []
    for g in last7:
        result = "✅" if g["ks"] >= ks_for_win else "❌"
        if g.get("is_home") is True:    loc = "H"
        elif g.get("is_home") is False: loc = "A"
        else:                           loc = ""
        icons.append(result + loc)
    return " ".join(icons) if icons else "—"

df["Last 7 (old→new)"] = df["player_id"].apply(lambda pid: make_last7(pid, k_threshold))

def pitcher_k_difficulty(pid):
    """For OVER bets: high opp K/9 = tough = HIGH PDF (boosts score)."""
