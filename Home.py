"""
MLB Betting Prediction Dashboard — LIVE w/ Real Team Form
Pulls each team's last 10 + 20 game stats from MLB Stats API.
"""

import streamlit as st
import pandas as pd
import numpy as np
import joblib
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TORONTO_TZ = ZoneInfo("America/Toronto")

st.set_page_config(page_title="MLB Predictor", page_icon="⚾", layout="wide")
st.title("⚾ MLB Game Predictor — Live")
st.caption(f"Today's games • {datetime.now(TORONTO_TZ).strftime('%A, %B %d, %Y')} (Toronto time)")

# ── API key ──
try:
    ODDS_API_KEY = st.secrets["ODDS_API_KEY"]
except (FileNotFoundError, KeyError):
    ODDS_API_KEY = st.sidebar.text_input("Odds API Key", type="password")
    if not ODDS_API_KEY:
        st.warning("Add your Odds API key in the sidebar to continue.")
        st.stop()

# ── load model ──
@st.cache_resource
def load_model():
    return joblib.load("model_final.pkl"), joblib.load("features_final.pkl")

try:
    model, FEATURES = load_model()
except FileNotFoundError:
    st.error("model_final.pkl or features_final.pkl not found in repo.")
    st.stop()

# ─────────────────────────────────────────────
# MLB STATS API — team name → ID lookup
# ─────────────────────────────────────────────
TEAM_IDS = {
    "Arizona Diamondbacks": 109, "Atlanta Braves": 144, "Baltimore Orioles": 110,
    "Boston Red Sox": 111, "Chicago Cubs": 112, "Chicago White Sox": 145,
    "Cincinnati Reds": 113, "Cleveland Guardians": 114, "Colorado Rockies": 115,
    "Detroit Tigers": 116, "Houston Astros": 117, "Kansas City Royals": 118,
    "Los Angeles Angels": 108, "Los Angeles Dodgers": 119, "Miami Marlins": 146,
    "Milwaukee Brewers": 158, "Minnesota Twins": 142, "New York Mets": 121,
    "New York Yankees": 147, "Athletics": 133, "Oakland Athletics": 133,
    "Philadelphia Phillies": 143, "Pittsburgh Pirates": 134,
    "San Diego Padres": 135, "San Francisco Giants": 137, "Seattle Mariners": 136,
    "St. Louis Cardinals": 138, "Tampa Bay Rays": 139, "Texas Rangers": 140,
    "Toronto Blue Jays": 141, "Washington Nationals": 120,
}

@st.cache_data(ttl=3600)  # cache for 1 hour
def get_team_recent_stats(team_id, n_games=20):
    """Fetch last N games for a team and compute rolling stats."""
    end_date = datetime.now(TORONTO_TZ).date()
    start_date = end_date - timedelta(days=45)  # look back ~6 weeks for safety

    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "teamId": team_id,
        "sportId": 1,
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "hydrate": "linescore"
    }
    r = requests.get(url, params=params)
    if r.status_code != 200:
        return None

    data = r.json()
    games = []
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            if game.get("status", {}).get("abstractGameState") != "Final":
                continue
            home = game["teams"]["home"]
            away = game["teams"]["away"]
            home_id = home["team"]["id"]
            away_id = away["team"]["id"]
            home_score = home.get("score", 0)
            away_score = away.get("score", 0)

            if team_id == home_id:
                runs_scored  = home_score
                runs_allowed = away_score
                won          = home_score > away_score
                is_home      = True
            else:
                runs_scored  = away_score
                runs_allowed = home_score
                won          = away_score > home_score
                is_home      = False

            games.append({
                "date":         game["gameDate"],
                "runs_scored":  runs_scored,
                "runs_allowed": runs_allowed,
                "won":          int(won),
                "is_home":      is_home,
            })

    if not games:
        return None

    df = pd.DataFrame(games).sort_values("date").tail(n_games)
    return df

def compute_team_features(team_name):
    """Build last-5/10/20 stats for one team."""
    team_id = TEAM_IDS.get(team_name)
    if team_id is None:
        return None
    df20 = get_team_recent_stats(team_id, 20)
    if df20 is None or df20.empty:
        return None
    df10 = df20.tail(10)
    df5  = df20.tail(5)
    return {
        "runs_5":      df5["runs_scored"].mean(),
        "runs_10":     df10["runs_scored"].mean(),
        "runs_20":     df20["runs_scored"].mean(),
        "allowed_10":  df10["runs_allowed"].mean(),
        "allowed_20":  df20["runs_allowed"].mean(),
        "win_rate_10": df10["won"].mean(),
        "home_wr_10":  df10[df10["is_home"]]["won"].mean() if df10["is_home"].any() else 0.54,
        "away_wr_10":  df10[~df10["is_home"]]["won"].mean() if (~df10["is_home"]).any() else 0.46,
    }

# ── fetch today's odds ──
@st.cache_data(ttl=600)
def fetch_todays_games(api_key):
    url = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"
    params = {"apiKey": api_key, "regions": "us", "markets": "h2h", "oddsFormat": "american"}
    r = requests.get(url, params=params)
    if r.status_code != 200:
        st.error(f"API error: {r.status_code} — {r.text}")
        return []
    return r.json()

games = fetch_todays_games(ODDS_API_KEY)
if not games:
    st.info("No MLB games scheduled today.")
    st.stop()

st.success(f"Found {len(games)} games available")

# ── helpers ──
def odds_to_prob(american):
    return 100 / (american + 100) if american > 0 else -american / (-american + 100)

def avg_odds(game):
    home, away = game["home_team"], game["away_team"]
    h, a = [], []
    for book in game.get("bookmakers", []):
        for market in book["markets"]:
            if market["key"] == "h2h":
                for o in market["outcomes"]:
                    if o["name"] == home: h.append(o["price"])
                    elif o["name"] == away: a.append(o["price"])
    return (np.mean(h) if h else None, np.mean(a) if a else None)

def utc_to_toronto(utc_str):
    dt = datetime.fromisoformat(utc_str.replace("Z","+00:00")).astimezone(TORONTO_TZ)
    return dt.strftime("%I:%M %p").lstrip("0")

def utc_to_toronto_date(utc_str):
    return datetime.fromisoformat(utc_str.replace("Z","+00:00")).astimezone(TORONTO_TZ).date()

# ── per-game predictions ──
today_local = datetime.now(TORONTO_TZ).date()
date_choice = st.radio("Show games for:", ["Today","Tomorrow","All available"], horizontal=True)

# Progress bar while fetching team stats
progress_text = st.empty()
results = []

for i, game in enumerate(games):
    home, away = game["home_team"], game["away_team"]
    game_date = utc_to_toronto_date(game["commence_time"])

    if date_choice == "Today" and game_date != today_local:
        continue
    if date_choice == "Tomorrow" and (game_date - today_local).days != 1:
        continue

    progress_text.text(f"Fetching stats for {away} @ {home}…")

    home_odds, away_odds = avg_odds(game)
    if home_odds is None or away_odds is None:
        continue

    book_home_prob = odds_to_prob(home_odds)
    book_away_prob = odds_to_prob(away_odds)

    home_stats = compute_team_features(home)
    away_stats = compute_team_features(away)

    if home_stats is None or away_stats is None:
        # fallback to defaults if stats fetch fails
        home_stats = {"runs_5": 4.5, "runs_10": 4.5, "runs_20": 4.5,
                       "allowed_10": 4.5, "allowed_20": 4.5,
                       "win_rate_10": 0.5, "home_wr_10": 0.54, "away_wr_10": 0.46}
        away_stats = home_stats.copy()

    # Build the feature vector (using existing model FEATURES list)
    feat_dict = {
        "home_runs_roll10":         home_stats["runs_10"],
        "visitor_runs_roll10":      away_stats["runs_10"],
        "home_runs_roll5":          home_stats["runs_5"],
        "visitor_runs_roll5":       away_stats["runs_5"],
        "home_win_roll10":          home_stats["home_wr_10"],
        "visitor_away_win_roll10":  away_stats["away_wr_10"],
        "home_allowed_roll10":      home_stats["allowed_10"],
        "visitor_allowed_roll10":   away_stats["allowed_10"],
        "home_rest_days":           1,
        "visitor_rest_days":        1,
        "h2h_home_win_roll":        0.5,
        "home_sp_era_roll5":        4.0,
        "visitor_sp_era_roll5":     4.0,
    }
    feat = pd.DataFrame([feat_dict])[FEATURES]
    prob = model.predict_proba(feat)[0]
    model_home_prob, model_away_prob = prob[1], prob[0]

    edge_home = model_home_prob - book_home_prob
    edge_away = model_away_prob - book_away_prob

    expected_runs = (home_stats["runs_10"] + away_stats["runs_10"]) / 1.2

    results.append({
        "Time (TO)":     utc_to_toronto(game["commence_time"]),
        "Matchup":       f"{away} @ {home}",
        "Home L10 R":    f"{home_stats['runs_10']:.1f}",
        "Away L10 R":    f"{away_stats['runs_10']:.1f}",
        "Exp Runs":      f"{expected_runs:.1f}",
        "Bet?":          "🟢 Away" if edge_home > 0.05 else (
                          "🟢 Home" if edge_away > 0.05 else "⚪ Pass")
    })

progress_text.empty()
results_df = pd.DataFrame(results)

st.markdown("### Today's Games & Model Edge")
st.dataframe(results_df, use_container_width=True, hide_index=True)

value_bets = results_df[results_df["Bet?"] != "⚪ Pass"]
st.markdown("---")
c1, c2, c3 = st.columns(3)
c1.metric("Games shown", len(results_df))
c2.metric("Value bets", len(value_bets))
c3.metric("Pass", len(results_df) - len(value_bets))

if len(value_bets) > 0:
    st.markdown("### 🎯 Value Bets")
    st.dataframe(value_bets, use_container_width=True, hide_index=True)

with st.expander("ℹ️ How this works"):
    st.markdown("""
    - **L10 R / L20 R** = average runs scored over last 10 / 20 games (live data from MLB Stats API)
    - **Book %** = sportsbook implied probability (avg across books)
    - **Model %** = Random Forest prediction
    - **Edge** = Model − Book; positive = potential value
    - **Bet trigger** = edge ≥ 5%
    
    Stats are cached for 1 hour to save API calls.
    """)
