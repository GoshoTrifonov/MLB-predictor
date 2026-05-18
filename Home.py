"""
MLB Betting Prediction Dashboard — LIVE w/ Real Team Form + Real Pitchers
- Pulls each team's last 10 + 20 game stats from MLB Stats API.
- Pulls each game's probable starting pitcher and his last-5-start ERA.
- Computes real rest days from the schedule.
- Shows Model Home % vs Book Home % so every pick is auditable.
"""

import streamlit as st
import pandas as pd
import numpy as np
import joblib
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from picks_storage import save_todays_picks

TORONTO_TZ = ZoneInfo("America/Toronto")
LEAGUE_AVG_ERA = 4.20

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

# ── sidebar controls ──
edge_threshold = st.sidebar.slider("Min edge to bet (%)", 1, 15, 5) / 100.0

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

def parse_ip(ip):
    """MLB innings-pitched uses .1 / .2 to mean 1/3 and 2/3 of an inning
    (e.g. '5.2' = 5 and 2/3 IP) — it CANNOT be read as a plain decimal."""
    try:
        s = str(ip)
        if "." in s:
            whole, frac = s.split(".")
            frac = frac[:1]  # only the first digit counts the thirds
            return int(whole) + int(frac) / 3.0
        return float(s)
    except (ValueError, TypeError):
        return 0.0

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
    try:
        r = requests.get(url, params=params, timeout=15)
    except Exception:
        return None
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
    try:
        last_game_date = pd.to_datetime(df20["date"].iloc[-1]).date()
    except Exception:
        last_game_date = None
    return {
        "runs_5":         df5["runs_scored"].mean(),
        "runs_10":        df10["runs_scored"].mean(),
        "runs_20":        df20["runs_scored"].mean(),
        "allowed_10":     df10["runs_allowed"].mean(),
        "allowed_20":     df20["runs_allowed"].mean(),
        "win_rate_10":    df10["won"].mean(),
        "home_wr_10":     df10[df10["is_home"]]["won"].mean() if df10["is_home"].any() else 0.54,
        "away_wr_10":     df10[~df10["is_home"]]["won"].mean() if (~df10["is_home"]).any() else 0.46,
        "last_game_date": last_game_date,
    }

# ─────────────────────────────────────────────
# Probable pitchers + last-5-start ERA
# ─────────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_probable_pitchers():
    """One schedule call covering yesterday→+2 days, returns a lookup keyed by
    (game_date, home_id, away_id) → probable pitcher ids/names."""
    start = datetime.now(TORONTO_TZ).date() - timedelta(days=1)
    end   = datetime.now(TORONTO_TZ).date() + timedelta(days=2)
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1,
        "startDate": start.strftime("%Y-%m-%d"),
        "endDate": end.strftime("%Y-%m-%d"),
        "hydrate": "probablePitcher",
    }
    try:
        data = requests.get(url, params=params, timeout=15).json()
    except Exception:
        return {}
    lookup = {}
    for date_entry in data.get("dates", []):
        gdate = date_entry.get("date")
        for g in date_entry.get("games", []):
            home = g["teams"]["home"]
            away = g["teams"]["away"]
            home_pit = home.get("probablePitcher", {})
            away_pit = away.get("probablePitcher", {})
            # note: a doubleheader will collide on this key — last one wins
            lookup[(gdate, home["team"]["id"], away["team"]["id"])] = {
                "home_pit_id":   home_pit.get("id"),
                "away_pit_id":   away_pit.get("id"),
                "home_pit_name": home_pit.get("fullName", "TBD"),
                "away_pit_name": away_pit.get("fullName", "TBD"),
            }
    return lookup

@st.cache_data(ttl=3600)
def get_pitcher_era_roll5(pitcher_id, n_starts=5):
    """ERA over the pitcher's last N starts: 9 * total ER / total IP.
    Returns None if the pitcher is unknown or has too little data."""
    if pitcher_id is None:
        return None
    season = datetime.now(TORONTO_TZ).year
    url = f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats"
    params = {"stats": "gameLog", "group": "pitching", "season": season}
    try:
        data = requests.get(url, params=params, timeout=10).json()
    except Exception:
        return None
    starts = []
    for split_group in data.get("stats", []):
        for s in split_group.get("splits", []):
            stat = s.get("stat", {})
            if stat.get("gamesStarted", 0) and stat["gamesStarted"] >= 1:
                er = stat.get("earnedRuns", 0) or 0
                ip = parse_ip(stat.get("inningsPitched", 0))
                starts.append((er, ip))
    starts = starts[-n_starts:]  # game log is oldest → newest
    total_er = sum(er for er, ip in starts)
    total_ip = sum(ip for er, ip in starts)
    if total_ip < 3.0:          # not enough innings to trust — fall back
        return None
    return round(9.0 * total_er / total_ip, 2)

def calc_rest_days(last_game_date, game_date):
    """Days between a team's last completed game and the game being predicted."""
    if last_game_date is None or game_date is None:
        return 1
    try:
        return max(0, min((game_date - last_game_date).days, 6))
    except Exception:
        return 1

# ── fetch today's odds ──
@st.cache_data(ttl=600)
def fetch_todays_games(api_key):
    url = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"
    params = {"apiKey": api_key, "regions": "us", "markets": "h2h", "oddsFormat": "american"}
    try:
        r = requests.get(url, params=params, timeout=15)
    except Exception as e:
        st.error(f"Odds API request failed: {e}")
        return []
    if r.status_code != 200:
        st.error(f"API error: {r.status_code} — {r.text}")
        return []
    return r.json()

games = fetch_todays_games(ODDS_API_KEY)
if not games:
    st.info("No MLB games scheduled today.")
    st.stop()

st.success(f"Found {len(games)} games available")

pp_lookup = get_probable_pitchers()

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
                      "win_rate_10": 0.5, "home_wr_10": 0.54, "away_wr_10": 0.46,
                      "last_game_date": None}
        away_stats = home_stats.copy()

    # ── Probable pitchers → real last-5-start ERA ──
    pit = pp_lookup.get((game_date.strftime("%Y-%m-%d"),
                         TEAM_IDS.get(home), TEAM_IDS.get(away)), {})
    home_pit_name = pit.get("home_pit_name", "TBD")
    away_pit_name = pit.get("away_pit_name", "TBD")
    home_era = get_pitcher_era_roll5(pit.get("home_pit_id"))   # None if unavailable
    away_era = get_pitcher_era_roll5(pit.get("away_pit_id"))
    home_era_feat = home_era if home_era is not None else LEAGUE_AVG_ERA
    away_era_feat = away_era if away_era is not None else LEAGUE_AVG_ERA

    # ── Real rest days ──
    home_rest = calc_rest_days(home_stats.get("last_game_date"), game_date)
    away_rest = calc_rest_days(away_stats.get("last_game_date"), game_date)

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
        "home_rest_days":           home_rest,         # was hardcoded 1
        "visitor_rest_days":        away_rest,         # was hardcoded 1
        "h2h_home_win_roll":        0.5,               # still a default — low signal
        "home_sp_era_roll5":        home_era_feat,     # was hardcoded 4.0
        "visitor_sp_era_roll5":     away_era_feat,     # was hardcoded 4.0
    }
    feat = pd.DataFrame([feat_dict])[FEATURES]
    prob = model.predict_proba(feat)[0]
    model_home_prob, model_away_prob = prob[1], prob[0]

    edge_home = model_home_prob - book_home_prob
    edge_away = model_away_prob - book_away_prob

    # ── Bet recommendation (FIXED: positive home edge → bet HOME) ──
    if edge_home >= edge_threshold and edge_home >= edge_away:
        bet  = f"🟢 Home +{edge_home*100:.0f}%"
        side = "Home"
    elif edge_away >= edge_threshold:
        bet  = f"🟢 Away +{edge_away*100:.0f}%"
        side = "Away"
    else:
        bet  = "⚪ Pass"
        side = "Pass"

    expected_runs = (home_stats["runs_10"] + away_stats["runs_10"]) / 1.2

    def era_str(e):
        return f"{e:.2f}" if e is not None else "—"

    results.append({
        "Time (TO)":     utc_to_toronto(game["commence_time"]),
        "Matchup":       f"{away} @ {home}",
        "Pitchers (A@H)": f"{away_pit_name.split()[-1]} {era_str(away_era)} @ "
                          f"{home_pit_name.split()[-1]} {era_str(home_era)}",
        "Home L10 R":    f"{home_stats['runs_10']:.1f}",
        "Away L10 R":    f"{away_stats['runs_10']:.1f}",
        "Exp Runs":      f"{expected_runs:.1f}",
        "Model Home %":  f"{model_home_prob*100:.0f}%",
        "Book Home %":   f"{book_home_prob*100:.0f}%",
        "Bet?":          bet,
        # extra fields kept for the Results page (not all shown in the table)
        "_side":             side,
        "_model_home_prob":  round(model_home_prob, 3),
        "_book_home_prob":   round(book_home_prob, 3),
    })

progress_text.empty()

table_cols = ["Time (TO)","Matchup","Pitchers (A@H)","Home L10 R","Away L10 R",
              "Exp Runs","Model Home %","Book Home %","Bet?"]
results_df = pd.DataFrame(results)

st.markdown("### Today's Games & Model Edge")
if len(results_df) > 0:
    st.dataframe(results_df[table_cols], use_container_width=True, hide_index=True)
else:
    st.info("No games for the selected day.")

# Save button — saves moneyline + exp runs picks
if len(results_df) > 0:
    c1, c2, c3 = st.columns([2, 1, 2])
    with c2:
        if st.button("💾 Save Today's Picks", use_container_width=True):
            picks_to_save = []
            for r in results:
                if r["_side"] == "Pass":
                    continue  # Skip non-value bets
                picks_to_save.append({
                    "matchup":         r["Matchup"],
                    "side":            r["_side"],          # "Home" / "Away" — use this to settle
                    "pitchers":        r["Pitchers (A@H)"],
                    "home_l10":        r["Home L10 R"],
                    "away_l10":        r["Away L10 R"],
                    "exp_runs":        r["Exp Runs"],
                    "model_home_prob": r["_model_home_prob"],
                    "book_home_prob":  r["_book_home_prob"],
                    "bet":             r["Bet?"],
                })
            if save_todays_picks("moneyline", picks_to_save):
                st.success("✅ Picks saved!")
            else:
                st.error("Save failed — check GITHUB_TOKEN.")

value_bets = results_df[results_df["Bet?"] != "⚪ Pass"] if len(results_df) > 0 else results_df
st.markdown("---")
c1, c2, c3 = st.columns(3)
c1.metric("Games shown", len(results_df))
c2.metric("Value bets", len(value_bets))
c3.metric("Pass", len(results_df) - len(value_bets))

if len(value_bets) > 0:
    st.markdown("### 🎯 Value Bets")
    st.dataframe(value_bets[table_cols], use_container_width=True, hide_index=True)

with st.expander("ℹ️ How this works"):
    st.markdown(f"""
    - **Pitchers (A@H)** = probable starters with their **last-5-start ERA**
      (live from MLB Stats API). Shows "—" when a starter is TBD or has too
      few innings, in which case the model uses league average ({LEAGUE_AVG_ERA}).
    - **L10 R** = average runs scored over the last 10 games (live data).
    - **Model Home %** = the model's predicted probability the **home** team wins.
    - **Book Home %** = sportsbook implied probability for the home team (avg of books).
    - **Edge** = Model − Book. **Bet trigger** = edge ≥ {edge_threshold*100:.0f}%
      (adjustable in the sidebar). A positive *home* edge means bet **Home**.
    - **Rest days** are now computed from the schedule (was hardcoded).
    - **Head-to-head** still uses a 0.5 default — small samples make it low-signal.

    **⚠️ Verify the model's class encoding:** for an obvious home favorite,
    *Model Home %* should be well above 50%. If favorites consistently show
    *below* 50%, the model's classes are reversed — swap `prob[1]` / `prob[0]`.

    Stats are cached for 1 hour to save API calls.
    """)
