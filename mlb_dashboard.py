"""
MLB Betting Prediction Dashboard — LIVE EDITION
Fetches today's games + odds from The Odds API,
runs each through the trained model to find value bets.
All times displayed in Toronto timezone.
"""

import streamlit as st
import pandas as pd
import numpy as np
import joblib
import requests
from datetime import datetime
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

st.success(f"Found {len(games)} games today")

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
    """Convert ISO UTC time string to Toronto local time."""
    dt_utc = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
    dt_local = dt_utc.astimezone(TORONTO_TZ)
    return dt_local.strftime("%I:%M %p").lstrip("0")

# ── league-average baseline features ──
DEFAULTS = {
    "home_runs_roll10": 4.5, "visitor_runs_roll10": 4.5,
    "home_runs_roll5": 4.5,  "visitor_runs_roll5": 4.5,
    "home_win_roll10": 0.54, "visitor_away_win_roll10": 0.46,
    "home_allowed_roll10": 4.5, "visitor_allowed_roll10": 4.5,
    "home_rest_days": 1, "visitor_rest_days": 1,
    "h2h_home_win_roll": 0.5,
    "home_sp_era_roll5": 4.0, "visitor_sp_era_roll5": 4.0,
}

# ── per-game predictions ──
results = []
for game in games:
    home, away = game["home_team"], game["away_team"]
    home_odds, away_odds = avg_odds(game)
    if home_odds is None or away_odds is None:
        continue

    book_home_prob = odds_to_prob(home_odds)
    book_away_prob = odds_to_prob(away_odds)

    feat = pd.DataFrame([DEFAULTS])[FEATURES]
    prob = model.predict_proba(feat)[0]
    model_home_prob = prob[1]
    model_away_prob = prob[0]

    edge_home = model_home_prob - book_home_prob
    edge_away = model_away_prob - book_away_prob

    results.append({
        "Time (TO)":    utc_to_toronto(game["commence_time"]),
        "Matchup":      f"{away} @ {home}",
        "Book Home %":  f"{book_home_prob:.1%}",
        "Model Home %": f"{model_home_prob:.1%}",
        "Edge Home":    f"{edge_home:+.1%}",
        "Edge Away":    f"{edge_away:+.1%}",
        "Home Odds":    int(home_odds),
        "Away Odds":    int(away_odds),
        "Bet?":         "🟢 HOME" if edge_home > 0.05 else (
                         "🟢 AWAY" if edge_away > 0.05 else "⚪ Pass")
    })

results_df = pd.DataFrame(results)

st.markdown("### Today's Games & Model Edge")
st.dataframe(results_df, use_container_width=True, hide_index=True)

value_bets = results_df[results_df["Bet?"] != "⚪ Pass"]
st.markdown("---")
c1, c2, c3 = st.columns(3)
c1.metric("Games today", len(results_df))
c2.metric("Value bets found", len(value_bets))
c3.metric("Pass", len(results_df) - len(value_bets))

if len(value_bets) > 0:
    st.markdown("### 🎯 Value Bets")
    st.dataframe(value_bets, use_container_width=True, hide_index=True)

with st.expander("ℹ️ How this works"):
    st.markdown("""
    - **Book %** = sportsbook implied probability  
    - **Model %** = Random Forest prediction  
    - **Edge** = Model − Book. Positive edge = book may be wrong  
    - **Bet trigger** = edge ≥ 5%
    
    ⚠️ Current model uses league-average inputs. Next step: feed live recent team stats per game.
    """)
