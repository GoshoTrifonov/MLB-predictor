"""
Shared utility for storing/retrieving picks history.
Uses GitHub repo as a JSON datastore.
"""

import streamlit as st
import requests
import json
import base64
from datetime import datetime
from zoneinfo import ZoneInfo

TORONTO_TZ = ZoneInfo("America/Toronto")
PICKS_FILE = "picks_history.json"

def _gh_headers():
    token = st.secrets.get("GITHUB_TOKEN")
    return {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

def _gh_repo():
    return st.secrets.get("GITHUB_REPO", "")

def load_picks_history():
    """Pull picks history from GitHub. Returns dict and SHA for updates."""
    repo = _gh_repo()
    url = f"https://api.github.com/repos/{repo}/contents/{PICKS_FILE}"
    try:
        r = requests.get(url, headers=_gh_headers(), timeout=10)
        if r.status_code == 200:
            j = r.json()
            content = base64.b64decode(j["content"]).decode()
            return json.loads(content), j["sha"]
        elif r.status_code == 404:
            # File doesn't exist yet
            return {}, None
        else:
            return {}, None
    except Exception as e:
        st.error(f"Could not load history: {e}")
        return {}, None

def save_picks_history(history, sha=None):
    """Push updated picks history to GitHub."""
    repo = _gh_repo()
    url = f"https://api.github.com/repos/{repo}/contents/{PICKS_FILE}"
    content = json.dumps(history, indent=2)
    encoded = base64.b64encode(content.encode()).decode()
    body = {
        "message": f"Update picks {datetime.now(TORONTO_TZ).strftime('%Y-%m-%d %H:%M')}",
        "content": encoded,
    }
    if sha:
        body["sha"] = sha
    try:
        r = requests.put(url, headers=_gh_headers(), json=body, timeout=15)
        return r.status_code in (200, 201)
    except Exception as e:
        st.error(f"Could not save history: {e}")
        return False

def save_todays_picks(picks_type, picks_list):
    """
    Save today's picks under {date}/{type}.
    picks_type: 'hrr' or 'hr'
    picks_list: list of dicts with player info
    """
    today = datetime.now(TORONTO_TZ).strftime("%Y-%m-%d")
    history, sha = load_picks_history()
    if today not in history:
        history[today] = {}
    history[today][picks_type] = {
        "picks":     picks_list,
        "saved_at":  datetime.now(TORONTO_TZ).isoformat(),
        "verified":  False,
    }
    return save_picks_history(history, sha)

@st.cache_data(ttl=86400)
def _player_id_lookup(player_name):
    """Find MLB player ID by name. Cached for 24h."""
    url = "https://statsapi.mlb.com/api/v1/sports/1/players"
    params = {"season": datetime.now(TORONTO_TZ).year}
    try:
        r = requests.get(url, params=params, timeout=15).json()
        for p in r.get("people", []):
            if p.get("fullName", "").lower() == player_name.lower():
                return p["id"]
        # Fallback: partial match
        for p in r.get("people", []):
            if player_name.lower() in p.get("fullName", "").lower():
                return p["id"]
    except Exception:
        pass
    return None


def get_player_results(player_name, date_str):
    """Look up actual H+R+RBI and HRs for a player on a given date."""
    player_id = _player_id_lookup(player_name)
    if not player_id:
        return {"played": False, "HRR": 0, "HR": 0}

    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
    params = {
        "stats": "gameLog",
        "group": "hitting",
        "startDate": date_str,
        "endDate":   date_str,
        "season":    date_str[:4],
        "sportId":   1,
    }
    try:
        r = requests.get(url, params=params, timeout=10).json()
        for split in r.get("stats", []):
            for s in split.get("splits", []):
                stat = s.get("stat", {})
                hits = stat.get("hits", 0)
                runs = stat.get("runs", 0)
                rbi  = stat.get("rbi", 0)
                hrs  = stat.get("homeRuns", 0)
                ab   = stat.get("atBats", 0)
                return {
                    "H": hits, "R": runs, "RBI": rbi, "HR": hrs, "AB": ab,
                    "HRR": hits + runs + rbi,
                    "played": ab > 0,
                }
    except Exception:
        pass
    return {"played": False, "HRR": 0, "HR": 0}
