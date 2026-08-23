"""
K-Rate Convergence Signal — Pitcher Strikeout Props vs Moneyline
================================================================
Uses Poisson distribution to model each starter's probability of hitting
5+ strikeouts, then checks whether that signal and the moneyline edge
point the same direction.

Why Poisson?
  Strikeouts per game are count events — each batter faced is a trial.
  Poisson(lambda) where lambda = expected Ks = k9_blend × avg_IP / 9.
  This is the same math sharp books use to set those Bet365 K prop lines.
  We compute it ourselves for free using the MLB Stats API.

Signal logic:
  k_edge   = home P(K≥5) minus away P(K≥5)   [positive = home pitcher dominates]
  ml_edge  = model_home_prob minus book_home_prob [from the moneyline model]
  STRONG   = both signals agree AND both exceed their threshold
  LEAN     = one signal fires, or both fire weakly
  PASS     = flat / insufficient data
  CONFLICT = signals disagree (useful to know — skip these)

No extra API calls — all pitcher data is cached from Home.py.
"""

import streamlit as st
import pandas as pd
import numpy as np
import joblib
import requests
from scipy.stats import poisson
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from picks_storage import save_todays_picks

TORONTO_TZ     = ZoneInfo("America/Toronto")
LEAGUE_AVG_ERA = 4.20
LEAGUE_AVG_K9  = 8.50
RECENT_STARTS  = 7
AVG_SP_IP      = 5.5    # typical starter goes ~5-6 innings; used as lambda divisor

st.set_page_config(page_title="🔥 K Convergence", page_icon="🔥", layout="wide")
st.title("🔥 K-Rate Convergence Signal")
st.caption(
    f"Poisson P(K≥5) vs Moneyline edge • "
    f"{datetime.now(TORONTO_TZ).strftime('%A, %B %d, %Y')} (Toronto time)"
)

# ── API key ──────────────────────────────────────────────────────────────────
try:
    ODDS_API_KEY = st.secrets["ODDS_API_KEY"]
except (FileNotFoundError, KeyError):
    ODDS_API_KEY = st.sidebar.text_input("Odds API Key", type="password")
    if not ODDS_API_KEY:
        st.warning("Add your Odds API key in the sidebar to continue.")
        st.stop()

# ── Sidebar ──────────────────────────────────────────────────────────────────
st.sidebar.markdown("### Convergence thresholds")
k_threshold  = st.sidebar.slider(
    "Min K-prob gap to fire (%)", 5, 30, 10,
    help="Minimum difference in P(K≥5) between the two pitchers to count as a K signal."
) / 100.0
ml_threshold = st.sidebar.slider(
    "Min moneyline edge to fire (%)", 1, 15, 5,
    help="Minimum model-vs-book edge to count as a moneyline signal."
) / 100.0
k_line       = st.sidebar.selectbox(
    "K prop line", [4, 5, 6, 7], index=1,
    help="Compute P(K ≥ this number). Bet365 default is 5."
)
avg_ip_input = st.sidebar.slider(
    "Assumed starter IP", 4.0, 7.0, AVG_SP_IP, 0.5,
    help="Expected innings per start — lambda = K/9 × IP / 9. ~5.5 is typical MLB average."
)

# ── Load model ───────────────────────────────────────────────────────────────
@st.cache_resource
def load_model():
    return joblib.load("model_final.pkl"), joblib.load("features_final.pkl")

try:
    model, FEATURES = load_model()
except FileNotFoundError:
    st.error("model_final.pkl not found.")
    st.stop()

# ── Team ID map ──────────────────────────────────────────────────────────────
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

# ── Helpers ──────────────────────────────────────────────────────────────────
def parse_ip(ip):
    try:
        s = str(ip)
        if "." in s:
            whole, frac = s.split(".")
            return int(whole) + int(frac[:1]) / 3.0
        return float(s)
    except (ValueError, TypeError):
        return 0.0

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
    dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00")).astimezone(TORONTO_TZ)
    return dt.strftime("%I:%M %p").lstrip("0")

def utc_to_toronto_date(utc_str):
    return datetime.fromisoformat(utc_str.replace("Z", "+00:00")).astimezone(TORONTO_TZ).date()

def fmt(v, digits=2):
    return f"{v:.{digits}f}" if v is not None else "—"

def poisson_p_over(k9_blend, ip, line):
    """P(strikeouts >= line) using Poisson with lambda = expected Ks."""
    if k9_blend is None or k9_blend <= 0:
        return None
    lam = k9_blend * ip / 9.0
    # P(K >= line) = 1 - P(K <= line-1) = 1 - CDF(line-1)
    return round(1.0 - poisson.cdf(line - 1, lam), 3)

def convergence_signal(k_edge, ml_edge, k_thresh, ml_thresh):
    """
    k_edge  > 0 means home pitcher has higher P(K≥line)
    ml_edge > 0 means model favours home team vs book
    Returns (signal_str, favoured_side, strength)
    """
    k_fires_home  = k_edge  >=  k_thresh
    k_fires_away  = k_edge  <= -k_thresh
    ml_fires_home = ml_edge >=  ml_thresh
    ml_fires_away = ml_edge <= -ml_thresh

    both_home = k_fires_home and ml_fires_home
    both_away = k_fires_away and ml_fires_away
    conflict  = (k_fires_home and ml_fires_away) or (k_fires_away and ml_fires_home)

    if both_home:
        return "🔥 STRONG — Home", "Home", 3
    if both_away:
        return "🔥 STRONG — Away", "Away", 3
    if conflict:
        return "⚠️ CONFLICT", "—", 0
    if k_fires_home or ml_fires_home:
        return "✅ LEAN — Home", "Home", 1
    if k_fires_away or ml_fires_away:
        return "✅ LEAN — Away", "Away", 1
    return "⚪ PASS", "—", 0

# ── Data fetchers (identical logic to Home.py, same cache keys) ──────────────
@st.cache_data(ttl=3600)
def get_team_recent_stats(team_id, n_games=20):
    end_date   = datetime.now(TORONTO_TZ).date()
    start_date = end_date - timedelta(days=45)
    url    = "https://statsapi.mlb.com/api/v1/schedule"
    params = {"teamId": team_id, "sportId": 1,
              "startDate": start_date.strftime("%Y-%m-%d"),
              "endDate":   end_date.strftime("%Y-%m-%d"),
              "hydrate":   "linescore"}
    try:
        r = requests.get(url, params=params, timeout=15)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    games = []
    for de in r.json().get("dates", []):
        for g in de.get("games", []):
            if g.get("status", {}).get("abstractGameState") != "Final":
                continue
            hm, aw = g["teams"]["home"], g["teams"]["away"]
            hs, as_ = hm.get("score", 0), aw.get("score", 0)
            if team_id == hm["team"]["id"]:
                rs, ra, won, ih = hs, as_, hs > as_, True
            else:
                rs, ra, won, ih = as_, hs, as_ > hs, False
            games.append({"date": g["gameDate"], "runs_scored": rs,
                          "runs_allowed": ra, "won": int(won), "is_home": ih})
    if not games:
        return None
    return pd.DataFrame(games).sort_values("date").tail(n_games)

def compute_team_features(team_name):
    tid = TEAM_IDS.get(team_name)
    if not tid:
        return None
    df20 = get_team_recent_stats(tid, 20)
    if df20 is None or df20.empty:
        return None
    df10, df5 = df20.tail(10), df20.tail(5)
    try:
        lgd = pd.to_datetime(df20["date"].iloc[-1]).date()
    except Exception:
        lgd = None
    return {
        "runs_5":    df5["runs_scored"].mean(),
        "runs_10":   df10["runs_scored"].mean(),
        "allowed_10": df10["runs_allowed"].mean(),
        "win_rate_10": df10["won"].mean(),
        "home_wr_10": df10[df10["is_home"]]["won"].mean()  if df10["is_home"].any()    else 0.54,
        "away_wr_10": df10[~df10["is_home"]]["won"].mean() if (~df10["is_home"]).any() else 0.46,
        "last_game_date": lgd,
    }

@st.cache_data(ttl=3600)
def get_probable_pitchers():
    start = datetime.now(TORONTO_TZ).date() - timedelta(days=1)
    end   = datetime.now(TORONTO_TZ).date() + timedelta(days=2)
    params = {"sportId": 1,
              "startDate": start.strftime("%Y-%m-%d"),
              "endDate":   end.strftime("%Y-%m-%d"),
              "hydrate":   "probablePitcher"}
    try:
        data = requests.get("https://statsapi.mlb.com/api/v1/schedule",
                            params=params, timeout=15).json()
    except Exception:
        return {}
    lookup = {}
    for de in data.get("dates", []):
        gdate = de.get("date")
        for g in de.get("games", []):
            hm, aw = g["teams"]["home"], g["teams"]["away"]
            hp, ap = hm.get("probablePitcher", {}), aw.get("probablePitcher", {})
            lookup[(gdate, hm["team"]["id"], aw["team"]["id"])] = {
                "home_pit_id":   hp.get("id"),
                "away_pit_id":   ap.get("id"),
                "home_pit_name": hp.get("fullName", "TBD"),
                "away_pit_name": ap.get("fullName", "TBD"),
            }
    return lookup

@st.cache_data(ttl=3600)
def get_pitcher_form(pitcher_id, recent_n=RECENT_STARTS):
    if pitcher_id is None:
        return None
    season = datetime.now(TORONTO_TZ).year
    url    = f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats"
    params = {"stats": "gameLog", "group": "pitching", "season": season}
    try:
        data = requests.get(url, params=params, timeout=10).json()
    except Exception:
        return None
    starts = []
    for sg in data.get("stats", []):
        for s in sg.get("splits", []):
            stat = s.get("stat", {})
            if stat.get("gamesStarted", 0) and stat["gamesStarted"] >= 1:
                er = stat.get("earnedRuns", 0) or 0
                ip = parse_ip(stat.get("inningsPitched", 0))
                so = stat.get("strikeOuts", 0) or 0
                starts.append({"er": er, "ip": ip, "so": so})
    if not starts:
        return None

    def agg(window):
        ter = sum(x["er"] for x in window)
        tip = sum(x["ip"] for x in window)
        tso = sum(x["so"] for x in window)
        if tip < 3.0:
            return None, None, None
        return (round(9.0 * ter / tip, 2),
                round(9.0 * tso / tip, 2),
                round(tip / len(window), 1))   # avg IP per start

    era_r, k9_r, ip_r = agg(starts[-recent_n:])
    era_s, k9_s, ip_s = agg(starts)

    if k9_s is not None and k9_r is not None:
        k9_blend = round(0.6 * k9_s + 0.4 * k9_r, 2)
    else:
        k9_blend = k9_s if k9_s is not None else k9_r

    # avg IP per start from recent window (for lambda calc)
    avg_ip = ip_r if ip_r is not None else (ip_s if ip_s is not None else AVG_SP_IP)

    # Actual K counts per start (last 7) for the detail row
    last7_ks = [x["so"] for x in starts[-7:]]

    return {
        "era_recent": era_r,
        "k9_recent":  k9_r,
        "k9_season":  k9_s,
        "k9_blend":   k9_blend,
        "avg_ip":     avg_ip,
        "last7_ks":   last7_ks,   # raw K counts, oldest → newest
    }

@st.cache_data(ttl=600)
def fetch_todays_games(api_key):
    url    = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"
    params = {"apiKey": api_key, "regions": "us",
              "markets": "h2h", "oddsFormat": "american"}
    try:
        r = requests.get(url, params=params, timeout=15)
    except Exception as e:
        st.error(f"Odds API request failed: {e}")
        return []
    if r.status_code != 200:
        st.error(f"API error {r.status_code}: {r.text}")
        return []
    return r.json()

def calc_rest_days(last_game_date, game_date):
    if last_game_date is None or game_date is None:
        return 1
    try:
        return max(0, min((game_date - last_game_date).days, 6))
    except Exception:
        return 1

# ── Main ─────────────────────────────────────────────────────────────────────
today_local = datetime.now(TORONTO_TZ).date()
date_choice = st.radio("Show games for:", ["Today", "Tomorrow", "All available"],
                       horizontal=True)

with st.spinner("Loading games and pitcher data…"):
    games      = fetch_todays_games(ODDS_API_KEY)
    pp_lookup  = get_probable_pitchers()

if not games:
    st.info("No MLB games found.")
    st.stop()

fallback_stats = {
    "runs_5": 4.5, "runs_10": 4.5, "allowed_10": 4.5,
    "win_rate_10": 0.5, "home_wr_10": 0.54, "away_wr_10": 0.46,
    "last_game_date": None,
}

rows = []
prog = st.progress(0, text="Computing convergence signals…")

for i, game in enumerate(games):
    home, away = game["home_team"], game["away_team"]
    game_date  = utc_to_toronto_date(game["commence_time"])

    if date_choice == "Today"    and game_date != today_local:
        continue
    if date_choice == "Tomorrow" and (game_date - today_local).days != 1:
        continue

    home_odds, away_odds = avg_odds(game)
    if home_odds is None or away_odds is None:
        continue

    book_home_prob = odds_to_prob(home_odds)
    book_away_prob = odds_to_prob(away_odds)

    home_stats = compute_team_features(home) or dict(fallback_stats)
    away_stats = compute_team_features(away) or dict(fallback_stats)

    pit = pp_lookup.get((game_date.strftime("%Y-%m-%d"),
                         TEAM_IDS.get(home), TEAM_IDS.get(away)), {})
    home_pit_name = pit.get("home_pit_name", "TBD")
    away_pit_name = pit.get("away_pit_name", "TBD")
    home_form = get_pitcher_form(pit.get("home_pit_id"))
    away_form = get_pitcher_form(pit.get("away_pit_id"))

    # ── Poisson K probabilities ──────────────────────────────────────────────
    home_k9b   = home_form["k9_blend"] if home_form else None
    away_k9b   = away_form["k9_blend"] if away_form else None
    home_ip    = home_form["avg_ip"]   if home_form else avg_ip_input
    away_ip    = away_form["avg_ip"]   if away_form else avg_ip_input

    # Use the user's chosen IP slider as a floor — don't let a short recent window
    # deflate lambda too aggressively
    home_ip = max(home_ip, avg_ip_input - 1.0) if home_ip else avg_ip_input
    away_ip = max(away_ip, avg_ip_input - 1.0) if away_ip else avg_ip_input

    home_pk = poisson_p_over(home_k9b, home_ip, k_line)
    away_pk = poisson_p_over(away_k9b, away_ip, k_line)

    k_edge = None
    if home_pk is not None and away_pk is not None:
        k_edge = round(home_pk - away_pk, 3)

    # ── Moneyline model ──────────────────────────────────────────────────────
    home_era_feat = (home_form["era_recent"] if home_form and home_form["era_recent"]
                     else LEAGUE_AVG_ERA)
    away_era_feat = (away_form["era_recent"] if away_form and away_form["era_recent"]
                     else LEAGUE_AVG_ERA)
    home_rest = calc_rest_days(home_stats.get("last_game_date"), game_date)
    away_rest = calc_rest_days(away_stats.get("last_game_date"), game_date)

    feat_dict = {
        "home_runs_roll10":        home_stats["runs_10"],
        "visitor_runs_roll10":     away_stats["runs_10"],
        "home_runs_roll5":         home_stats["runs_5"],
        "visitor_runs_roll5":      away_stats["runs_5"],
        "home_win_roll10":         home_stats["home_wr_10"],
        "visitor_away_win_roll10": away_stats["away_wr_10"],
        "home_allowed_roll10":     home_stats["allowed_10"],
        "visitor_allowed_roll10":  away_stats["allowed_10"],
        "home_rest_days":          home_rest,
        "visitor_rest_days":       away_rest,
        "h2h_home_win_roll":       0.5,
        "home_sp_era_roll5":       home_era_feat,
        "visitor_sp_era_roll5":    away_era_feat,
    }
    feat           = pd.DataFrame([feat_dict])[FEATURES]
    prob           = model.predict_proba(feat)[0]
    model_home_prob = prob[1]
    ml_edge        = round(model_home_prob - book_home_prob, 3)

    # ── Convergence signal ───────────────────────────────────────────────────
    if k_edge is not None:
        signal, favoured, strength = convergence_signal(
            k_edge, ml_edge, k_threshold, ml_threshold
        )
    else:
        signal, favoured, strength = "❓ No pitcher data", "—", 0

    # Last 7 actual K counts for quick visual
    home_ks_str = " ".join(str(k) for k in (home_form["last7_ks"] if home_form else []))
    away_ks_str = " ".join(str(k) for k in (away_form["last7_ks"] if away_form else []))

    rows.append({
        "Time (TO)":          utc_to_toronto(game["commence_time"]),
        "Matchup":            f"{away} @ {home}",
        "Away SP":            away_pit_name.split()[-1] if away_pit_name != "TBD" else "TBD",
        "Away K9":            fmt(away_k9b, 1),
        f"Away P(K≥{k_line})": f"{away_pk*100:.0f}%" if away_pk else "—",
        "Away last 7 Ks":     away_ks_str or "—",
        "Home SP":            home_pit_name.split()[-1] if home_pit_name != "TBD" else "TBD",
        "Home K9":            fmt(home_k9b, 1),
        f"Home P(K≥{k_line})": f"{home_pk*100:.0f}%" if home_pk else "—",
        "Home last 7 Ks":     home_ks_str or "—",
        "K Edge (H−A)":       f"{k_edge*100:+.0f}%" if k_edge is not None else "—",
        "ML Edge (H)":        f"{ml_edge*100:+.0f}%",
        "Book Home %":        f"{book_home_prob*100:.0f}%",
        "Signal":             signal,
        # hidden for save
        "_favoured":          favoured,
        "_strength":          strength,
        "_home_pk":           home_pk,
        "_away_pk":           away_pk,
        "_k_edge":            k_edge,
        "_ml_edge":           ml_edge,
        "_model_home_prob":   round(model_home_prob, 3),
        "_book_home_prob":    round(book_home_prob, 3),
        "_home_k9":           home_k9b,
        "_away_k9":           away_k9b,
    })
    prog.progress((i + 1) / len(games))

prog.empty()

if not rows:
    st.info("No games for the selected day.")
    st.stop()

df = pd.DataFrame(rows)

# ── Surface strong signals first ─────────────────────────────────────────────
strong = df[df["_strength"] == 3]
lean   = df[df["_strength"] == 1]
rest   = df[df["_strength"] == 0]

table_cols = [
    "Time (TO)", "Matchup",
    "Away SP", "Away K9", f"Away P(K≥{k_line})", "Away last 7 Ks",
    "Home SP", "Home K9", f"Home P(K≥{k_line})", "Home last 7 Ks",
    "K Edge (H−A)", "ML Edge (H)", "Book Home %", "Signal",
]

if not strong.empty:
    st.markdown("## 🔥 Strong Convergence")
    st.caption("Both K-rate AND moneyline edge point the same team — your high-confidence tier.")
    st.dataframe(strong[table_cols], hide_index=True, use_container_width=True)

if not lean.empty:
    st.markdown("## ✅ Lean")
    st.caption("One signal fires, or both fire weakly.")
    st.dataframe(lean[table_cols], hide_index=True, use_container_width=True)

with st.expander(f"⚪ Pass / Conflict ({len(rest)} games)"):
    st.dataframe(rest[table_cols], hide_index=True, use_container_width=True)

# ── Summary metrics ───────────────────────────────────────────────────────────
st.markdown("---")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Games analysed", len(df))
c2.metric("🔥 Strong signals", len(strong))
c3.metric("✅ Leans", len(lean))
c4.metric("⚪ Pass / Conflict", len(rest))

# ── Save button ───────────────────────────────────────────────────────────────
if not strong.empty or not lean.empty:
    c1, c2, c3 = st.columns([2, 1, 2])
    with c2:
        if st.button("💾 Save Convergence Picks", use_container_width=True):
            picks = []
            for r in rows:
                if r["_strength"] == 0:
                    continue
                picks.append({
                    "matchup":         r["Matchup"],
                    "signal":          r["Signal"],
                    "favoured":        r["_favoured"],
                    "home_sp":         r["Home SP"],
                    "away_sp":         r["Away SP"],
                    "home_k9":         r["_home_k9"],
                    "away_k9":         r["_away_k9"],
                    "home_pk":         r["_home_pk"],
                    "away_pk":         r["_away_pk"],
                    "k_edge":          r["_k_edge"],
                    "ml_edge":         r["_ml_edge"],
                    "model_home_prob": r["_model_home_prob"],
                    "book_home_prob":  r["_book_home_prob"],
                    "k_line":          k_line,
                    "k_threshold":     k_threshold,
                    "ml_threshold":    ml_threshold,
                })
            if save_todays_picks("convergence", picks):
                st.success("✅ Convergence picks saved!")
            else:
                st.error("Save failed — check GITHUB_TOKEN.")

# ── Explain ───────────────────────────────────────────────────────────────────
with st.expander("ℹ️ How the convergence signal works"):
    st.markdown(f"""
**Why Poisson?**
Strikeouts per game are *count events* — every batter faced is a trial.
The Poisson distribution models count events perfectly: given a pitcher's
expected strikeout rate (K/9 × innings / 9), it returns the exact probability
of hitting any K threshold. This is the same math sharp sportsbooks use to set
those Bet365 lines. We compute it ourselves, for free, using the MLB Stats API.

**Lambda calculation**
`lambda = k9_blend × avg_IP / 9`
where `k9_blend` = 60% season K/9 + 40% last-{RECENT_STARTS}-start K/9 (stable
but responsive to recent form), and `avg_IP` = that pitcher's recent average
innings per start. You can adjust the assumed IP in the sidebar.

`P(K ≥ {k_line}) = 1 − Poisson_CDF({k_line-1}, lambda)`

**K Edge** = home P(K≥{k_line}) minus away P(K≥{k_line}). Positive = home
pitcher more likely to dominate.

**Moneyline Edge** = model's home win probability minus the book's implied
probability. Positive = model sees value on the home team.

**Signal tiers**
| Signal | Condition |
|--------|-----------|
| 🔥 STRONG | Both K edge ≥ {k_threshold*100:.0f}% **and** ML edge ≥ {ml_threshold*100:.0f}%, same team |
| ✅ LEAN   | One signal fires, or both fire but weakly |
| ⚠️ CONFLICT | Signals point opposite teams |
| ⚪ PASS   | Neither signal meets threshold |

**Last 7 Ks** = actual strikeout totals from each of the pitcher's last 7 starts,
oldest → newest. Cross-check this against the K/9 blend — if the recent Ks are
consistently above or below the blend, your eye is catching something the average missed.

**Tracking your edge**
Save picks with the button above. Once you have 20+ convergence picks tracked,
compare the 🔥 STRONG win rate vs ✅ LEAN win rate — if Strong is materially
higher, tighten the thresholds. If they're similar, the K signal alone is doing
the work and you can relax the ML threshold.
    """)
