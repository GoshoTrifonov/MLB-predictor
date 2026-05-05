"""
MLB Batter Strikeout (OVER 0.5) Picks — 3 Models for A/B/C comparison
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
