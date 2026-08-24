"""
K-Rate Convergence Signal — Pitcher Strikeout Props vs Moneyline
================================================================
Uses Poisson distribution to model each starter's probability of hitting
5+ strikeouts, then checks whether that signal and the moneyline edge
point the same direction.

Top of page: prominent cards for the 1-3 strongest signals today.
Below: full ranked table of all games.
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
AVG_SP_IP      = 5.5

st.set_page_config(page_title="🔥 K Convergence", page_icon="🔥", layout="wide")
st.title("🔥 K-Rate Convergence Signal")
st.caption(
    f"Poisson P(K≥5) × Moneyline edge • "
    f"{datetime.now(TORONTO_TZ).strftime('%A, %B %d, %Y')} (Toronto time)"
)

# ── API key ───────────────────────────────────────────────────────────────────
try:
    ODDS_API_KEY = st.secrets["ODDS_API_KEY"]
except (FileNotFoundError, KeyError):
    ODDS_API_KEY = st.sidebar.text_input("Odds API Key", type="password")
    if not ODDS_API_KEY:
        st.warning("Add your Odds API key in the sidebar to continue.")
        st.stop()

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.markdown("### Signal thresholds")
k_threshold  = st.sidebar.slider(
    "Min K-prob gap (%)", 5, 30, 10,
    help="Minimum P(K≥line) difference between pitchers to fire K signal."
) / 100.0
ml_threshold = st.sidebar.slider(
    "Min ML edge (%)", 1, 15, 5,
    help="Minimum model-vs-book edge to fire ML signal."
) / 100.0
k_line = st.sidebar.selectbox(
    "K prop line", [4, 5, 6, 7], index=1,
    help="Compute P(K ≥ this). Bet365 default is 5."
)
avg_ip_input = st.sidebar.slider(
    "Assumed starter IP", 4.0, 7.0, AVG_SP_IP, 0.5,
    help="Expected innings per start. ~5.5 is typical MLB average."
)
date_choice = st.sidebar.radio(
    "Show games for:", ["Today", "Tomorrow", "All available"]
)

# ── Load model ────────────────────────────────────────────────────────────────
@st.cache_resource
def load_model():
    return joblib.load("model_final.pkl"), joblib.load("features_final.pkl")

try:
    model, FEATURES = load_model()
except FileNotFoundError:
    st.error("model_final.pkl not found.")
    st.stop()

# ── Team IDs ──────────────────────────────────────────────────────────────────
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

# ── Helpers ───────────────────────────────────────────────────────────────────
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
    return 100/(american+100) if american > 0 else -american/(-american+100)

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

def poisson_p_over(k9_blend, ip, line):
    if k9_blend is None or k9_blend <= 0: return None
    lam = k9_blend * ip / 9.0
    return round(1.0 - poisson.cdf(line - 1, lam), 3)

def convergence_signal(k_edge, ml_edge, k_thresh, ml_thresh):
    k_home  = k_edge  >=  k_thresh
    k_away  = k_edge  <= -k_thresh
    ml_home = ml_edge >=  ml_thresh
    ml_away = ml_edge <= -ml_thresh

    if k_home and ml_home:  return "🔥 STRONG — Home", "Home", 3
    if k_away and ml_away:  return "🔥 STRONG — Away", "Away", 3
    if (k_home and ml_away) or (k_away and ml_home):
                            return "⚠️ CONFLICT",      "—",    0
    if k_home or ml_home:  return "✅ LEAN — Home",   "Home", 1
    if k_away or ml_away:  return "✅ LEAN — Away",   "Away", 1
    return "⚪ PASS", "—", 0

def strength_label(s):
    return {3: "STRONG", 1: "LEAN", 0: "PASS/CONFLICT"}.get(s, "—")

def strength_color(s):
    return {3: "#ff4b4b", 1: "#21ba45", 0: "#888"}.get(s, "#888")

# ── Data fetchers ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_team_recent_stats(team_id, n_games=20):
    end   = datetime.now(TORONTO_TZ).date()
    start = end - timedelta(days=45)
    url   = "https://statsapi.mlb.com/api/v1/schedule"
    params = {"teamId": team_id, "sportId": 1,
              "startDate": start.strftime("%Y-%m-%d"),
              "endDate":   end.strftime("%Y-%m-%d"),
              "hydrate": "linescore"}
    try:
        r = requests.get(url, params=params, timeout=15)
    except Exception:
        return None
    if r.status_code != 200: return None
    games = []
    for de in r.json().get("dates", []):
        for g in de.get("games", []):
            if g.get("status", {}).get("abstractGameState") != "Final": continue
            hm, aw = g["teams"]["home"], g["teams"]["away"]
            hs, as_ = hm.get("score", 0), aw.get("score", 0)
            if team_id == hm["team"]["id"]:
                rs, ra, won, ih = hs, as_, hs > as_, True
            else:
                rs, ra, won, ih = as_, hs, as_ > hs, False
            games.append({"date": g["gameDate"], "runs_scored": rs,
                          "runs_allowed": ra, "won": int(won), "is_home": ih})
    if not games: return None
    return pd.DataFrame(games).sort_values("date").tail(n_games)

def compute_team_features(team_name):
    tid = TEAM_IDS.get(team_name)
    if not tid: return None
    df20 = get_team_recent_stats(tid, 20)
    if df20 is None or df20.empty: return None
    df10, df5 = df20.tail(10), df20.tail(5)
    try:
        lgd = pd.to_datetime(df20["date"].iloc[-1]).date()
    except Exception:
        lgd = None
    return {
        "runs_5":    df5["runs_scored"].mean(),
        "runs_10":   df10["runs_scored"].mean(),
        "allowed_10": df10["runs_allowed"].mean(),
        "home_wr_10": df10[df10["is_home"]]["won"].mean()  if df10["is_home"].any()    else 0.54,
        "away_wr_10": df10[~df10["is_home"]]["won"].mean() if (~df10["is_home"]).any() else 0.46,
        "last_game_date": lgd,
    }

@st.cache_data(ttl=3600)
def get_probable_pitchers():
    start  = datetime.now(TORONTO_TZ).date() - timedelta(days=1)
    end    = datetime.now(TORONTO_TZ).date() + timedelta(days=2)
    params = {"sportId": 1,
              "startDate": start.strftime("%Y-%m-%d"),
              "endDate":   end.strftime("%Y-%m-%d"),
              "hydrate": "probablePitcher"}
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
            hp = hm.get("probablePitcher", {})
            ap = aw.get("probablePitcher", {})
            lookup[(gdate, hm["team"]["id"], aw["team"]["id"])] = {
                "home_pit_id":   hp.get("id"),
                "away_pit_id":   ap.get("id"),
                "home_pit_name": hp.get("fullName", "TBD"),
                "away_pit_name": ap.get("fullName", "TBD"),
            }
    return lookup

@st.cache_data(ttl=3600)
def get_pitcher_form(pitcher_id, recent_n=RECENT_STARTS):
    if pitcher_id is None: return None
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
    if not starts: return None

    def agg(window):
        ter = sum(x["er"] for x in window)
        tip = sum(x["ip"] for x in window)
        tso = sum(x["so"] for x in window)
        if tip < 3.0: return None, None, None
        return (round(9*ter/tip, 2), round(9*tso/tip, 2), round(tip/len(window), 1))

    era_r, k9_r, ip_r = agg(starts[-recent_n:])
    era_s, k9_s, ip_s = agg(starts)

    if k9_s is not None and k9_r is not None:
        k9_blend = round(0.6*k9_s + 0.4*k9_r, 2)
    else:
        k9_blend = k9_s if k9_s is not None else k9_r

    avg_ip = ip_r if ip_r is not None else (ip_s if ip_s is not None else AVG_SP_IP)
    last7_ks = [x["so"] for x in starts[-7:]]

    return {
        "era_recent": era_r, "k9_recent": k9_r,
        "k9_season":  k9_s,  "k9_blend":  k9_blend,
        "avg_ip": avg_ip,    "last7_ks": last7_ks,
    }

@st.cache_data(ttl=600)
def fetch_todays_games(api_key):
    url    = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds"
    params = {"apiKey": api_key, "regions": "us",
              "markets": "h2h", "oddsFormat": "american"}
    try:
        r = requests.get(url, params=params, timeout=15)
    except Exception as e:
        st.error(f"Odds API failed: {e}")
        return []
    if r.status_code != 200:
        st.error(f"API error {r.status_code}: {r.text}")
        return []
    return r.json()

def calc_rest_days(lgd, gd):
    if lgd is None or gd is None: return 1
    try: return max(0, min((gd - lgd).days, 6))
    except: return 1

# ── Main ──────────────────────────────────────────────────────────────────────
with st.spinner("Loading games and pitcher data…"):
    games     = fetch_todays_games(ODDS_API_KEY)
    pp_lookup = get_probable_pitchers()

if not games:
    st.info("No MLB games found.")
    st.stop()

today_local = datetime.now(TORONTO_TZ).date()
fallback    = {"runs_5": 4.5, "runs_10": 4.5, "allowed_10": 4.5,
               "home_wr_10": 0.54, "away_wr_10": 0.46, "last_game_date": None}

rows = []
prog = st.progress(0, text="Computing convergence signals…")

for i, game in enumerate(games):
    home, away = game["home_team"], game["away_team"]
    game_date  = utc_to_toronto_date(game["commence_time"])

    if date_choice == "Today"    and game_date != today_local:           continue
    if date_choice == "Tomorrow" and (game_date - today_local).days != 1: continue

    home_odds, away_odds = avg_odds(game)
    if home_odds is None or away_odds is None: continue

    book_home_prob = odds_to_prob(home_odds)
    book_away_prob = odds_to_prob(away_odds)

    home_stats = compute_team_features(home) or dict(fallback)
    away_stats = compute_team_features(away) or dict(fallback)

    pit = pp_lookup.get((game_date.strftime("%Y-%m-%d"),
                         TEAM_IDS.get(home), TEAM_IDS.get(away)), {})
    home_pit_name = pit.get("home_pit_name", "TBD")
    away_pit_name = pit.get("away_pit_name", "TBD")
    home_form = get_pitcher_form(pit.get("home_pit_id"))
    away_form = get_pitcher_form(pit.get("away_pit_id"))

    home_k9b = home_form["k9_blend"] if home_form else None
    away_k9b = away_form["k9_blend"] if away_form else None
    home_ip  = max(home_form["avg_ip"], avg_ip_input-1.0) if home_form else avg_ip_input
    away_ip  = max(away_form["avg_ip"], avg_ip_input-1.0) if away_form else avg_ip_input

    home_pk = poisson_p_over(home_k9b, home_ip, k_line)
    away_pk = poisson_p_over(away_k9b, away_ip, k_line)
    k_edge  = round(home_pk - away_pk, 3) if (home_pk and away_pk) else None

    # Moneyline model
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
    feat            = pd.DataFrame([feat_dict])[FEATURES]
    prob            = model.predict_proba(feat)[0]
    model_home_prob = prob[1]
    ml_edge         = round(model_home_prob - book_home_prob, 3)

    if k_edge is not None:
        signal, favoured, strength = convergence_signal(
            k_edge, ml_edge, k_threshold, ml_threshold)
    else:
        signal, favoured, strength = "❓ No data", "—", 0

    home_ks_str = " ".join(str(k) for k in (home_form["last7_ks"] if home_form else []))
    away_ks_str = " ".join(str(k) for k in (away_form["last7_ks"] if away_form else []))

    # Bet team name — human readable
    if favoured == "Home":
        bet_team = home
        bet_pk   = home_pk
        dom_pit  = home_pit_name
        und_pit  = away_pit_name
        dom_ks   = home_ks_str
        dom_k9   = home_k9b
        dom_pk   = home_pk
        opp_pk   = away_pk
    elif favoured == "Away":
        bet_team = away
        bet_pk   = away_pk
        dom_pit  = away_pit_name
        und_pit  = home_pit_name
        dom_ks   = away_ks_str
        dom_k9   = away_k9b
        dom_pk   = away_pk
        opp_pk   = home_pk
    else:
        bet_team = "—"
        bet_pk   = None
        dom_pit  = "—"
        und_pit  = "—"
        dom_ks   = "—"
        dom_k9   = None
        dom_pk   = None
        opp_pk   = None

    rows.append({
        # Display
        "Time":            utc_to_toronto(game["commence_time"]),
        "Matchup":         f"{away} @ {home}",
        "Away SP":         away_pit_name.split()[-1] if away_pit_name != "TBD" else "TBD",
        "Away K9":         fmt(away_k9b, 1),
        f"Away P(K≥{k_line})": f"{away_pk*100:.0f}%" if away_pk else "—",
        "Away last 7 Ks":  away_ks_str or "—",
        "Home SP":         home_pit_name.split()[-1] if home_pit_name != "TBD" else "TBD",
        "Home K9":         fmt(home_k9b, 1),
        f"Home P(K≥{k_line})": f"{home_pk*100:.0f}%" if home_pk else "—",
        "Home last 7 Ks":  home_ks_str or "—",
        "K Edge (H−A)":    f"{k_edge*100:+.0f}%" if k_edge is not None else "—",
        "ML Edge (H)":     f"{ml_edge*100:+.0f}%",
        "Book Home %":     f"{book_home_prob*100:.0f}%",
        "Signal":          signal,
        # Card fields
        "_strength":   strength,
        "_favoured":   favoured,
        "_bet_team":   bet_team,
        "_matchup":    f"{away} @ {home}",
        "_time":       utc_to_toronto(game["commence_time"]),
        "_dom_pit":    dom_pit,
        "_und_pit":    und_pit,
        "_dom_k9":     dom_k9,
        "_dom_pk":     dom_pk,
        "_opp_pk":     opp_pk,
        "_k_edge":     k_edge,
        "_ml_edge":    ml_edge,
        "_dom_ks":     dom_ks,
        "_book_home":  book_home_prob,
        "_model_home": model_home_prob,
        # Save fields
        "_home_pk":    home_pk,
        "_away_pk":    away_pk,
        "_home_k9":    home_k9b,
        "_away_k9":    away_k9b,
    })
    prog.progress((i+1)/len(games))

prog.empty()

if not rows:
    st.info("No games for the selected day.")
    st.stop()

df = pd.DataFrame(rows)
strong_df = df[df["_strength"] == 3].sort_values("_k_edge", key=abs, ascending=False)
lean_df   = df[df["_strength"] == 1].sort_values("_k_edge", key=abs, ascending=False)
rest_df   = df[df["_strength"] == 0]

# ═══════════════════════════════════════════════════════════════════════
# TOP SECTION — Highlight cards for strong signals
# ═══════════════════════════════════════════════════════════════════════
if not strong_df.empty:
    st.markdown("## 🔥 Today's Best Convergence Bets")
    st.caption("Both K-rate dominance AND moneyline edge point the same team.")

    # Show up to 3 cards
    card_rows = strong_df.head(3).to_dict(orient="records")
    cols = st.columns(len(card_rows))

    for col, r in zip(cols, card_rows):
        dom_pk_pct = f"{r['_dom_pk']*100:.0f}%" if r["_dom_pk"] else "—"
        opp_pk_pct = f"{r['_opp_pk']*100:.0f}%" if r["_opp_pk"] else "—"
        k_gap_pct  = f"{abs(r['_k_edge'])*100:.0f}%" if r["_k_edge"] is not None else "—"
        ml_pct     = f"{abs(r['_ml_edge'])*100:.0f}%" if r["_ml_edge"] is not None else "—"
        dom_k9_str = f"{r['_dom_k9']:.1f}" if r["_dom_k9"] else "—"

        with col:
            st.markdown(f"""
<div style="
    border: 2px solid #ff4b4b;
    border-radius: 12px;
    padding: 18px 16px;
    background: linear-gradient(135deg, #1a0000 0%, #2d0000 100%);
    height: 100%;
">
    <div style="font-size:11px; color:#aaa; letter-spacing:1px; margin-bottom:4px;">
        {r['_time']} ET
    </div>
    <div style="font-size:14px; color:#ddd; margin-bottom:12px;">
        {r['_matchup']}
    </div>
    <div style="font-size:24px; font-weight:700; color:#ff4b4b; margin-bottom:4px;">
        🔥 {r['_bet_team']}
    </div>
    <div style="font-size:12px; color:#aaa; margin-bottom:16px;">
        BET THIS TEAM
    </div>
    <hr style="border-color:#333; margin:10px 0;">
    <div style="font-size:12px; color:#ccc; margin-bottom:6px;">
        <b style="color:#ff8c00;">✦ Dominant SP:</b> {r['_dom_pit']}
    </div>
    <div style="font-size:12px; color:#ccc; margin-bottom:6px;">
        <b>K/9:</b> {dom_k9_str} &nbsp;|&nbsp; <b>P(K≥{k_line}):</b> {dom_pk_pct}
    </div>
    <div style="font-size:12px; color:#aaa; margin-bottom:4px;">
        <b>Opp SP:</b> {r['_und_pit']}
    </div>
    <div style="font-size:12px; color:#aaa; margin-bottom:14px;">
        <b>P(K≥{k_line}):</b> {opp_pk_pct}
    </div>
    <hr style="border-color:#333; margin:10px 0;">
    <div style="display:flex; justify-content:space-between; margin-top:8px;">
        <div style="text-align:center;">
            <div style="font-size:18px; font-weight:700; color:#21ba45;">
                {k_gap_pct}
            </div>
            <div style="font-size:10px; color:#888;">K-PROB GAP</div>
        </div>
        <div style="text-align:center;">
            <div style="font-size:18px; font-weight:700; color:#21ba45;">
                {ml_pct}
            </div>
            <div style="font-size:10px; color:#888;">ML EDGE</div>
        </div>
        <div style="text-align:center;">
            <div style="font-size:18px; font-weight:700; color:#ff8c00;">
                {r['_dom_ks']}
            </div>
            <div style="font-size:10px; color:#888;">LAST 7 Ks</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

    st.markdown("")  # spacer

elif not lean_df.empty:
    st.info("No strong convergence today — best leans shown below.")
else:
    st.info("No convergence signals today. All games in the full table below.")

# ═══════════════════════════════════════════════════════════════════════
# FULL TABLE
# ═══════════════════════════════════════════════════════════════════════
table_cols = [
    "Time", "Matchup",
    "Away SP", "Away K9", f"Away P(K≥{k_line})", "Away last 7 Ks",
    "Home SP", "Home K9", f"Home P(K≥{k_line})", "Home last 7 Ks",
    "K Edge (H−A)", "ML Edge (H)", "Book Home %", "Signal",
]

st.markdown("---")
st.markdown("### 📊 All Games — Ranked by Signal Strength")

if not strong_df.empty:
    st.markdown("#### 🔥 Strong Convergence")
    st.dataframe(strong_df[table_cols], hide_index=True, use_container_width=True)

if not lean_df.empty:
    st.markdown("#### ✅ Lean")
    st.dataframe(lean_df[table_cols], hide_index=True, use_container_width=True)

with st.expander(f"⚪ Pass / Conflict ({len(rest_df)} games)"):
    st.dataframe(rest_df[table_cols], hide_index=True, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════
# METRICS + SAVE
# ═══════════════════════════════════════════════════════════════════════
st.markdown("---")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Games analysed", len(df))
c2.metric("🔥 Strong", len(strong_df))
c3.metric("✅ Lean",   len(lean_df))
c4.metric("⚪ Rest",   len(rest_df))

signal_games = df[df["_strength"] > 0]
if not signal_games.empty:
    c1, c2, c3 = st.columns([2, 1, 2])
    with c2:
        if st.button("💾 Save Picks", use_container_width=True):
            picks = []
            for r in signal_games.to_dict(orient="records"):
                picks.append({
                    "matchup":    r["_matchup"],
                    "signal":     r["Signal"],
                    "favoured":   r["_favoured"],
                    "bet_team":   r["_bet_team"],
                    "home_sp":    r["Home SP"],
                    "away_sp":    r["Away SP"],
                    "home_k9":    r["_home_k9"],
                    "away_k9":    r["_away_k9"],
                    "home_pk":    r["_home_pk"],
                    "away_pk":    r["_away_pk"],
                    "k_edge":     r["_k_edge"],
                    "ml_edge":    r["_ml_edge"],
                    "model_home": r["_model_home"],
                    "book_home":  r["_book_home"],
                    "k_line":     k_line,
                })
            if save_todays_picks("convergence", picks):
                st.success("✅ Convergence picks saved!")
            else:
                st.error("Save failed — check GITHUB_TOKEN.")

# ═══════════════════════════════════════════════════════════════════════
# EXPLAINER
# ═══════════════════════════════════════════════════════════════════════
with st.expander("ℹ️ How the convergence signal works"):
    st.markdown(f"""
**The core idea**
You observed that when a pitcher's K prop odds are much lower (more likely to strikeout)
than the opponent's, AND the moneyline also favours that pitcher's team — the win rate
is very high. This page automates that observation.

**Why Poisson?**
Strikeouts per start are count events — each batter faced is a trial. Poisson gives
the mathematically correct probability of hitting any K threshold given a pitcher's
rate. This is the same math sportsbooks use to set those Bet365 lines.

`lambda = K/9_blend × avg_IP / 9`
`P(K ≥ {k_line}) = 1 − Poisson_CDF({k_line-1}, lambda)`

K/9 blend = 60% season + 40% last {RECENT_STARTS} starts.

**Signal tiers**
| Signal | Condition |
|--------|-----------|
| 🔥 STRONG | K-prob gap ≥ {k_threshold*100:.0f}% **AND** ML edge ≥ {ml_threshold*100:.0f}%, same team |
| ✅ LEAN | One signal fires |
| ⚠️ CONFLICT | Signals point opposite teams — skip |
| ⚪ PASS | Neither threshold met |

**Reading the cards**
Each 🔥 card shows the team to bet, the dominant pitcher with his K/9 and P(K≥{k_line}),
the opponent pitcher, the K-prob gap between them, the moneyline model edge,
and the dominant pitcher's last 7 actual K totals (oldest → newest) as a
quick sanity check that the rate is real and not a fluke.

**Tracking your edge**
Save picks daily. Once you have 20+ results, compare 🔥 STRONG win rate vs
✅ LEAN — if Strong is materially higher, tighten the thresholds.
Tune the K threshold and ML threshold in the sidebar.
    """)
