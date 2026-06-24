"""
MLB Betting Prediction Dashboard — LIVE w/ Real Team Form + Real Pitchers + K-rate
- Pulls each team's last 10 + 20 game stats from MLB Stats API.
- Pulls each game's probable starter and his last-7-start ERA + K/9.
- Applies a POST-MODEL K-rate adjustment: a pitcher with higher K/9 nudges
  his team's win probability up. The trained model doesn't have a K feature
  so this is the only way to use Ks without retraining.
- Shows Base Home %, K-adjusted Model Home %, and Book Home % side by side.
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
LEAGUE_AVG_K9  = 8.50      # MLB starters ~8.4-8.6 K/9 in recent seasons
RECENT_STARTS  = 7         # window for "recent form" stats

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

st.sidebar.markdown("**Pitcher K-rate adjustment**")
apply_k_adj = st.sidebar.checkbox("Apply K-rate adjustment", value=True)
k_adj_pct   = st.sidebar.slider(
    "Win % shift per K/9 gap",
    0.5, 3.0, 1.5, 0.1,
    help="1.5% means a 3-K/9 advantage shifts the home prob by ~4.5%. Cap is ±10%."
)

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
            frac = frac[:1]
            return int(whole) + int(frac) / 3.0
        return float(s)
    except (ValueError, TypeError):
        return 0.0

def k_per_era(k9, era):
    """K/ERA dominance ratio. Higher = more strikeouts per earned run allowed,
    i.e. a pitcher who misses bats AND limits damage. ERA is floored at 0.5
    so a tiny-sample 0.00 ERA doesn't blow up to infinity."""
    if k9 is None or era is None:
        return None
    return round(k9 / max(era, 0.5), 2)

@st.cache_data(ttl=3600)
def get_team_recent_stats(team_id, n_games=20):
    """Fetch last N games for a team and compute rolling stats."""
    end_date = datetime.now(TORONTO_TZ).date()
    start_date = end_date - timedelta(days=45)
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "teamId": team_id, "sportId": 1,
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate":   end_date.strftime("%Y-%m-%d"),
        "hydrate":   "linescore",
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
            home_id, away_id = home["team"]["id"], away["team"]["id"]
            home_score, away_score = home.get("score", 0), away.get("score", 0)
            if team_id == home_id:
                runs_scored, runs_allowed = home_score, away_score
                won, is_home = home_score > away_score, True
            else:
                runs_scored, runs_allowed = away_score, home_score
                won, is_home = away_score > home_score, False
            games.append({
                "date":         game["gameDate"],
                "runs_scored":  runs_scored,
                "runs_allowed": runs_allowed,
                "won":          int(won),
                "is_home":      is_home,
            })
    if not games:
        return None
    return pd.DataFrame(games).sort_values("date").tail(n_games)

def compute_team_features(team_name):
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
        "home_wr_10":     df10[df10["is_home"]]["won"].mean()   if df10["is_home"].any()    else 0.54,
        "away_wr_10":     df10[~df10["is_home"]]["won"].mean()  if (~df10["is_home"]).any() else 0.46,
        "last_game_date": last_game_date,
    }

# ─────────────────────────────────────────────
# Probable pitchers + pitcher form (ERA + K/9)
# ─────────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_probable_pitchers():
    """One schedule call covering yesterday→+2 days; lookup keyed by
    (game_date, home_id, away_id) → probable pitcher ids/names."""
    start = datetime.now(TORONTO_TZ).date() - timedelta(days=1)
    end   = datetime.now(TORONTO_TZ).date() + timedelta(days=2)
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "sportId": 1,
        "startDate": start.strftime("%Y-%m-%d"),
        "endDate":   end.strftime("%Y-%m-%d"),
        "hydrate":   "probablePitcher",
    }
    try:
        data = requests.get(url, params=params, timeout=15).json()
    except Exception:
        return {}
    lookup = {}
    for date_entry in data.get("dates", []):
        gdate = date_entry.get("date")
        for g in date_entry.get("games", []):
            home, away = g["teams"]["home"], g["teams"]["away"]
            home_pit = home.get("probablePitcher", {})
            away_pit = away.get("probablePitcher", {})
            lookup[(gdate, home["team"]["id"], away["team"]["id"])] = {
                "home_pit_id":   home_pit.get("id"),
                "away_pit_id":   away_pit.get("id"),
                "home_pit_name": home_pit.get("fullName", "TBD"),
                "away_pit_name": away_pit.get("fullName", "TBD"),
            }
    return lookup

@st.cache_data(ttl=3600)
def get_pitcher_form(pitcher_id, recent_n=RECENT_STARTS):
    """One game-log call → ERA, K/9, and last-7 W/L outcomes for the last-N
    window and the whole season. Returns None if the pitcher is unknown or
    has < 3 IP."""
    if pitcher_id is None:
        return None
    season = datetime.now(TORONTO_TZ).year
    url = f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats"
    params = {"stats": "gameLog", "group": "pitching", "season": season}
    try:
        data = requests.get(url, params=params, timeout=10).json()
    except Exception:
        return None

    starts = []  # list of dicts per start, oldest → newest
    for split_group in data.get("stats", []):
        for s in split_group.get("splits", []):
            stat = s.get("stat", {})
            if stat.get("gamesStarted", 0) and stat["gamesStarted"] >= 1:
                er = stat.get("earnedRuns", 0)  or 0
                ip = parse_ip(stat.get("inningsPitched", 0))
                so = stat.get("strikeOuts", 0)  or 0
                w  = stat.get("wins", 0)        or 0
                l  = stat.get("losses", 0)      or 0
                # MLB Stats API gives W/L per start; if both 0 it's a No Decision.
                if   w >= 1: result = "W"
                elif l >= 1: result = "L"
                else:        result = "ND"
                starts.append({"er": er, "ip": ip, "so": so, "result": result})
    if not starts:
        return None

    def agg(window):
        tot_er = sum(x["er"] for x in window)
        tot_ip = sum(x["ip"] for x in window)
        tot_so = sum(x["so"] for x in window)
        if tot_ip < 3.0:
            return None, None
        return round(9.0 * tot_er / tot_ip, 2), round(9.0 * tot_so / tot_ip, 2)

    era_recent, k9_recent = agg(starts[-recent_n:])
    era_season, k9_season = agg(starts)

    # Blend for the K-rate adjustment: 60% season (stable) + 40% recent (form)
    if k9_season is not None and k9_recent is not None:
        k9_blend = round(0.6 * k9_season + 0.4 * k9_recent, 2)
    else:
        k9_blend = k9_season if k9_season is not None else k9_recent

    # Last 7 W/L icons, oldest → newest
    _icon = {"W": "✅", "L": "❌", "ND": "⚪"}
    last7 = starts[-7:]
    last7_icons = "".join(_icon[x["result"]] for x in last7) if last7 else "—"
    wins_last7 = sum(1 for x in last7 if x["result"] == "W")
    losses_last7 = sum(1 for x in last7 if x["result"] == "L")

    return {
        "era_recent":   era_recent,  # used as the model's ERA feature
        "k9_recent":    k9_recent,   # shown in the table
        "era_season":   era_season,
        "k9_season":    k9_season,   # also shown for verification vs Baseball-Ref
        "k9_blend":     k9_blend,    # used for the K-rate adjustment
        "last7_icons":  last7_icons, # ✅/❌/⚪ string, oldest → newest
        "wins_last7":   wins_last7,
        "losses_last7": losses_last7,
    }

def calc_rest_days(last_game_date, game_date):
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

def fmt(v, digits=2):
    return f"{v:.{digits}f}" if v is not None else "—"

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
        fallback = {"runs_5": 4.5, "runs_10": 4.5, "runs_20": 4.5,
                    "allowed_10": 4.5, "allowed_20": 4.5,
                    "win_rate_10": 0.5, "home_wr_10": 0.54, "away_wr_10": 0.46,
                    "last_game_date": None}
        home_stats = home_stats or fallback
        away_stats = away_stats or dict(fallback)

    # ── Probable pitchers → real last-7-start ERA + K/9 ──
    pit = pp_lookup.get((game_date.strftime("%Y-%m-%d"),
                         TEAM_IDS.get(home), TEAM_IDS.get(away)), {})
    home_pit_name = pit.get("home_pit_name", "TBD")
    away_pit_name = pit.get("away_pit_name", "TBD")
    home_form = get_pitcher_form(pit.get("home_pit_id"))
    away_form = get_pitcher_form(pit.get("away_pit_id"))

    home_era = home_form["era_recent"] if home_form else None
    away_era = away_form["era_recent"] if away_form else None
    home_k9  = home_form["k9_recent"]  if home_form else None
    away_k9  = away_form["k9_recent"]  if away_form else None
    home_k9_season = home_form["k9_season"]   if home_form else None
    away_k9_season = away_form["k9_season"]   if away_form else None
    home_l7        = home_form["last7_icons"] if home_form else "—"
    away_l7        = away_form["last7_icons"] if away_form else "—"

    home_k_era = k_per_era(home_k9, home_era)
    away_k_era = k_per_era(away_k9, away_era)

    home_era_feat = home_era if home_era is not None else LEAGUE_AVG_ERA
    away_era_feat = away_era if away_era is not None else LEAGUE_AVG_ERA

    # Rest days
    home_rest = calc_rest_days(home_stats.get("last_game_date"), game_date)
    away_rest = calc_rest_days(away_stats.get("last_game_date"), game_date)

    # Feature vector — same 13 keys the trained model expects
    feat_dict = {
        "home_runs_roll10":         home_stats["runs_10"],
        "visitor_runs_roll10":      away_stats["runs_10"],
        "home_runs_roll5":          home_stats["runs_5"],
        "visitor_runs_roll5":       away_stats["runs_5"],
        "home_win_roll10":          home_stats["home_wr_10"],
        "visitor_away_win_roll10":  away_stats["away_wr_10"],
        "home_allowed_roll10":      home_stats["allowed_10"],
        "visitor_allowed_roll10":   away_stats["allowed_10"],
        "home_rest_days":           home_rest,
        "visitor_rest_days":        away_rest,
        "h2h_home_win_roll":        0.5,
        "home_sp_era_roll5":        home_era_feat,
        "visitor_sp_era_roll5":     away_era_feat,
    }
    feat = pd.DataFrame([feat_dict])[FEATURES]
    prob = model.predict_proba(feat)[0]
    base_home_prob = prob[1]                # model's raw output
    base_away_prob = prob[0]

    # ── K-rate adjustment (post-model) ──
    # The trained model has no K feature. We nudge its output based on the
    # K/9 gap between the two starters: higher-K pitcher → his team gains
    # win prob. Capped at ±10% so one signal can't dominate.
    home_k9_blend = home_form["k9_blend"] if home_form else None
    away_k9_blend = away_form["k9_blend"] if away_form else None
    k_gap = None
    k_adj = 0.0
    if apply_k_adj and home_k9_blend is not None and away_k9_blend is not None:
        k_gap = home_k9_blend - away_k9_blend
        k_adj = max(-0.10, min(0.10, k_gap * (k_adj_pct / 100.0)))

    model_home_prob = max(0.02, min(0.98, base_home_prob + k_adj))
    model_away_prob = 1.0 - model_home_prob

    edge_home = model_home_prob - book_home_prob
    edge_away = model_away_prob - book_away_prob

    if edge_home >= edge_threshold and edge_home >= edge_away:
        bet, side = f"🟢 Home +{edge_home*100:.0f}%", "Home"
    elif edge_away >= edge_threshold:
        bet, side = f"🟢 Away +{edge_away*100:.0f}%", "Away"
    else:
        bet, side = "⚪ Pass", "Pass"

    expected_runs = (home_stats["runs_10"] + away_stats["runs_10"]) / 1.2

    # SP column shows recent ERA / recent K9 (s = season K9 for verification)
    pitchers_str = (
        f"{away_pit_name.split()[-1]} ({fmt(away_era)}/{fmt(away_k9, 1)}"
        f"·s{fmt(away_k9_season, 1)})"
        f" @ "
        f"{home_pit_name.split()[-1]} ({fmt(home_era)}/{fmt(home_k9, 1)}"
        f"·s{fmt(home_k9_season, 1)})"
    )
    k_gap_str  = f"{k_gap:+.1f}" if k_gap is not None else "—"
    k_era_str  = f"{fmt(away_k_era, 1)} / {fmt(home_k_era, 1)}"
    last7_str  = f"{away_l7}  {home_l7}"   # away first, home second — matches A/H

    results.append({
        "Time (TO)":         utc_to_toronto(game["commence_time"]),
        "Matchup":           f"{away} @ {home}",
        "SP (ERA/K9·sK9)":   pitchers_str,
        "Last 7 (A | H)":    last7_str,
        "K Gap (H−A)":       k_gap_str,
        "K/ERA (A/H)":       k_era_str,
        "Exp Runs":          f"{expected_runs:.1f}",
        "Base Home %":       f"{base_home_prob*100:.0f}%",
        "Model Home %":      f"{model_home_prob*100:.0f}%",
        "Book Home %":       f"{book_home_prob*100:.0f}%",
        "Bet?":              bet,
        # extra fields for the Results page
        "_side":             side,
        "_home_l10":         f"{home_stats['runs_10']:.1f}",
        "_away_l10":         f"{away_stats['runs_10']:.1f}",
        "_base_home_prob":   round(base_home_prob, 3),
        "_model_home_prob":  round(model_home_prob, 3),
        "_book_home_prob":   round(book_home_prob, 3),
        "_k_gap":            None if k_gap is None else round(k_gap, 2),
        "_k_adj":            round(k_adj, 3),
        "_home_k_era":       home_k_era,
        "_away_k_era":       away_k_era,
        "_home_k9_season":   home_k9_season,
        "_away_k9_season":   away_k9_season,
        "_home_last7":       home_l7,
        "_away_last7":       away_l7,
    })

progress_text.empty()

table_cols = ["Time (TO)","Matchup","SP (ERA/K9·sK9)","Last 7 (A | H)",
              "K Gap (H−A)","K/ERA (A/H)","Exp Runs",
              "Base Home %","Model Home %","Book Home %","Bet?"]
results_df = pd.DataFrame(results)

st.markdown("### Today's Games & Model Edge")
if len(results_df) > 0:
    st.dataframe(results_df[table_cols], use_container_width=True, hide_index=True)
else:
    st.info("No games for the selected day.")

# Save button — saves moneyline picks with K-rate context
if len(results_df) > 0:
    c1, c2, c3 = st.columns([2, 1, 2])
    with c2:
        if st.button("💾 Save Today's Picks", use_container_width=True):
            picks_to_save = []
            for r in results:
                if r["_side"] == "Pass":
                    continue
                picks_to_save.append({
                    "matchup":         r["Matchup"],
                    "side":            r["_side"],
                    "pitchers":        r["SP (ERA/K9·sK9)"],
                    "home_l10":        r["_home_l10"],
                    "away_l10":        r["_away_l10"],
                    "exp_runs":        r["Exp Runs"],
                    "base_home_prob":  r["_base_home_prob"],
                    "model_home_prob": r["_model_home_prob"],
                    "book_home_prob":  r["_book_home_prob"],
                    "k_gap":           r["_k_gap"],
                    "k_adj":           r["_k_adj"],
                    "home_k_era":      r["_home_k_era"],
                    "away_k_era":      r["_away_k_era"],
                    "home_k9_season":  r["_home_k9_season"],
                    "away_k9_season":  r["_away_k9_season"],
                    "home_last7":      r["_home_last7"],
                    "away_last7":      r["_away_last7"],
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
**Pitcher columns**
- **SP (ERA/K9·sK9)** = each probable starter shown as `Lastname (ERA/K9·sK9)`.
  ERA and K9 are over the last **{RECENT_STARTS}** starts; **sK9** is the
  full-season K/9 for cross-checking against Baseball-Reference. A recent
  K/9 running 2–3 above season K/9 is normal during a hot streak — it's
  not a bug, it's why we look at recent form. "—" means TBD or too few
  innings (<3) and the model falls back to league averages (ERA
  {LEAGUE_AVG_ERA}, K/9 {LEAGUE_AVG_K9}).
- **Last 7 (A | H)** = each starter's W/L outcomes over his last 7 starts,
  oldest → newest. ✅ = win, ❌ = loss, ⚪ = no decision. Useful as a glance
  read on form; pitcher wins/losses depend heavily on run support and
  bullpen luck, so this is more "vibe check" than predictive signal.
- **K Gap (H−A)** = home K/9 minus away K/9 (60% season + 40% recent blend).
  Positive = home pitcher misses more bats.
- **K/ERA (A/H)** = strikeouts per earned run, per pitcher. Higher = more
  dominant (lots of Ks, few earned runs). A K/ERA of 4+ is elite; under 2 is
  struggling. Lets you spot a true mismatch at a glance.

**How the K-rate adjustment works**
- The trained model has no strikeout feature, so K rate is applied **after**
  the model runs:
  `adj = K_gap × {k_adj_pct:.1f}%/K9`, capped at ±10%.
  Example: a +3 K/9 gap → +{3 * k_adj_pct:.1f}% on the home team's win prob.
- **Base Home %** = model output before adjustment.
  **Model Home %** = after — this is what the bet recommendation uses.
- Toggle/tune both in the sidebar to A/B test against tracked results.

**Other features**
- L10 R = runs scored over the last 10 games (live).
- Rest days computed from the schedule (no longer hardcoded).
- H2H still defaults to 0.5 (small samples, low signal).
- **Edge** = Model − Book. **Bet trigger** = edge ≥ {edge_threshold*100:.0f}% (sidebar).

**⚠️ Sanity check the model's class encoding:** for an obvious home favorite,
*Base Home %* should be well above 50%. If favorites consistently show *below*
50%, the model's classes are reversed — swap `prob[1]` / `prob[0]`.

**⚠️ This is a post-model band-aid.** If the K signal helps in tracked results,
retrain `model_final.pkl` in Colab with K/9 as a proper feature — it'll work
better inside the model than bolted onto it. If it doesn't help, disable the
toggle and you've saved yourself a retrain.

Stats cached 1 hour to save API calls.
    """)
