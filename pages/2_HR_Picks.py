"""
MLB Home Run Probability Picks
Combines batter HR rate, opposing pitcher HR/9 allowed, and park factor
to estimate each hitter's HR probability tonight.
"""

import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TORONTO_TZ = ZoneInfo("America/Toronto")

st.set_page_config(page_title="HR Picks", page_icon="💥", layout="wide")
st.title("💥 MLB Home Run Probability Picks")
st.caption(f"Tonight's HR candidates ranked by matchup + park • {datetime.now(TORONTO_TZ).strftime('%A, %B %d, %Y')}")

TEAM_IDS = [108,109,110,111,112,113,114,115,116,117,118,119,120,121,133,
            134,135,136,137,138,139,140,141,142,143,144,145,146,147,158]

TEAM_NAMES = {
    108:"LAA",109:"ARI",110:"BAL",111:"BOS",112:"CHC",113:"CIN",114:"CLE",
    115:"COL",116:"DET",117:"HOU",118:"KCR",119:"LAD",120:"WSN",121:"NYM",
    133:"OAK",134:"PIT",135:"SDP",136:"SEA",137:"SFG",138:"STL",139:"TBR",
    140:"TEX",141:"TOR",142:"MIN",143:"PHI",144:"ATL",145:"CHW",146:"MIA",
    147:"NYY",158:"MIL"
}

# Park HR factors (>1 = boosts HRs, <1 = suppresses)
# Based on 5-year averages from Baseball Savant park factors
PARK_HR_FACTORS = {
    115: 1.35,  # COL — Coors Field 🏔️
    147: 1.20,  # NYY — Yankee Stadium
    113: 1.18,  # CIN — Great American Ball Park
    111: 1.15,  # BOS — Fenway Park
    140: 1.13,  # TEX — Globe Life Field
    142: 1.10,  # MIN — Target Field
    158: 1.08,  # MIL — American Family Field
    110: 1.07,  # BAL — Camden Yards
    143: 1.05,  # PHI — Citizens Bank Park
    121: 1.03,  # NYM — Citi Field
    144: 1.02,  # ATL — Truist Park
    109: 1.01,  # ARI — Chase Field
    116: 1.00,  # DET — Comerica Park
    117: 0.99,  # HOU — Minute Maid
    119: 0.98,  # LAD — Dodger Stadium
    138: 0.97,  # STL — Busch Stadium
    108: 0.97,  # LAA — Angel Stadium
    145: 0.96,  # CHW — Guaranteed Rate
    146: 0.95,  # MIA — loanDepot park
    134: 0.95,  # PIT — PNC Park
    112: 0.94,  # CHC — Wrigley Field
    133: 0.93,  # OAK — Oakland Coliseum
    114: 0.93,  # CLE — Progressive Field
    136: 0.92,  # SEA — T-Mobile Park
    118: 0.92,  # KCR — Kauffman Stadium
    120: 0.90,  # WSN — Nationals Park
    141: 0.90,  # TOR — Rogers Centre
    137: 0.85,  # SFG — Oracle Park
    135: 0.83,  # SDP — Petco Park
    139: 0.82,  # TBR — Tropicana Field
}

LEAGUE_AVG_HR_RATE = 0.034  # ~3.4% chance per PA league-wide

# ─────────────────────────────────────────────
# DATA FETCHERS
# ─────────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_batter_season(team_id):
    """Pull season-to-date hitting stats for a team."""
    season = datetime.now(TORONTO_TZ).year
    url = "https://statsapi.mlb.com/api/v1/stats"
    params = {"stats":"season","group":"hitting","teamId":team_id,
              "season":season,"sportIds":1}
    try:
        return requests.get(url, params=params, timeout=10).json()
    except Exception:
        return {}

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
            home = g["teams"]["home"]
            away = g["teams"]["away"]
            home_id, away_id = home["team"]["id"], away["team"]["id"]
            home_pit = home.get("probablePitcher", {})
            away_pit = away.get("probablePitcher", {})
            venue_id = home_id  # game is at home team's park
            
            matchups[home_id] = {
                "opp_pit_id": away_pit.get("id"),
                "opp_pit_name": away_pit.get("fullName", "TBD"),
                "opp_team": TEAM_NAMES.get(away_id, str(away_id)),
                "park_team_id": venue_id,
            }
            matchups[away_id] = {
                "opp_pit_id": home_pit.get("id"),
                "opp_pit_name": home_pit.get("fullName", "TBD"),
                "opp_team": TEAM_NAMES.get(home_id, str(home_id)),
                "park_team_id": venue_id,
            }
    return matchups

@st.cache_data(ttl=3600)
def get_pitcher_hr_rate(pitcher_id):
    """Return pitcher's HR/9 from season stats."""
    if pitcher_id is None:
        return None
    season = datetime.now(TORONTO_TZ).year
    url = f"https://statsapi.mlb.com/api/v1/people/{pitcher_id}/stats"
    params = {"stats":"season","group":"pitching","season":season}
    try:
        data = requests.get(url, params=params, timeout=10).json()
        for split in data.get("stats", []):
            for s in split.get("splits", []):
                stat = s.get("stat", {})
                hr = stat.get("homeRuns", 0)
                ip_str = stat.get("inningsPitched", "0")
                ip = float(ip_str) if ip_str else 0
                if ip > 0:
                    return {"hr_per_9": (hr / ip) * 9, "ip": ip, "hr": hr}
    except Exception:
        pass
    return None

@st.cache_data(ttl=3600)
def fetch_all_batter_hr_stats():
    """Get every batter's season HR + PA stats."""
    rows = []
    for tid in TEAM_IDS:
        data = get_batter_season(tid)
        for split in data.get("stats", []):
            for s in split.get("splits", []):
                p = s.get("player", {})
                st_ = s.get("stat", {})
                pa = st_.get("plateAppearances", 0)
                if pa < 30:  # need meaningful sample
                    continue
                hr = st_.get("homeRuns", 0)
                ab = st_.get("atBats", 0)
                rows.append({
                    "Player":  p.get("fullName"),
                    "team_id": tid,
                    "Team":    TEAM_NAMES.get(tid, str(tid)),
                    "G":       st_.get("gamesPlayed", 0),
                    "PA":      pa,
                    "AB":      ab,
                    "HR":      hr,
                    "HR/PA":   round(hr / pa, 4) if pa else 0,
                    "AB/HR":   round(ab / hr, 1) if hr else None,
                    "ISO":     pd.to_numeric(st_.get("ops"), errors="coerce"),  # OPS as power proxy
                    "SLG":     pd.to_numeric(st_.get("slg"), errors="coerce"),
                })
        time.sleep(0.1)
    return pd.DataFrame(rows)

# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────
min_pa = st.sidebar.slider("Min plate appearances", 30, 100, 50)
min_hr = st.sidebar.slider("Min season HRs", 0, 10, 1)
search = st.sidebar.text_input("Search player").lower()

# ─────────────────────────────────────────────
# FETCH
# ─────────────────────────────────────────────
with st.spinner("Pulling batter HR stats..."):
    df = fetch_all_batter_hr_stats()

with st.spinner("Pulling tonight's matchups..."):
    matchups = get_todays_matchups()

df = df[(df["PA"] >= min_pa) & (df["HR"] >= min_hr)].copy()

# Filter to today's teams
df = df[df["team_id"].isin(matchups.keys())].copy()

if len(df) == 0:
    st.warning("No qualifying batters playing today.")
    st.stop()

# Attach matchup info
df["Opp Pitcher"] = df["team_id"].map(lambda t: matchups.get(t,{}).get("opp_pit_name","TBD"))
df["Opp Team"]    = df["team_id"].map(lambda t: matchups.get(t,{}).get("opp_team","?"))
df["opp_pit_id"]  = df["team_id"].map(lambda t: matchups.get(t,{}).get("opp_pit_id"))
df["park_id"]     = df["team_id"].map(lambda t: matchups.get(t,{}).get("park_team_id"))
df["Park Factor"] = df["park_id"].map(PARK_HR_FACTORS).fillna(1.0).round(2)

# ─────────────────────────────────────────────
# FETCH PITCHER STATS
# ─────────────────────────────────────────────
unique_pids = df["opp_pit_id"].dropna().unique()
pit_cache = {}
prog = st.progress(0, text="Fetching pitcher HR/9...")
for i, pid in enumerate(unique_pids):
    pit_cache[int(pid)] = get_pitcher_hr_rate(int(pid))
    prog.progress((i+1)/len(unique_pids))
prog.empty()

LEAGUE_AVG_HR_PER_9 = 1.20

def pitcher_hr_factor(pid):
    if pd.isna(pid):
        return 1.0
    stats = pit_cache.get(int(pid))
    if not stats or stats.get("hr_per_9") is None:
        return 1.0
    factor = stats["hr_per_9"] / LEAGUE_AVG_HR_PER_9
    return max(0.5, min(2.0, factor))

df["Opp HR/9"] = df["opp_pit_id"].apply(
    lambda pid: round(pit_cache.get(int(pid),{}).get("hr_per_9"), 2)
                 if pd.notna(pid) and pit_cache.get(int(pid)) else None
)
df["Pit Factor"] = df["opp_pit_id"].apply(pitcher_hr_factor).round(2)

# ─────────────────────────────────────────────
# HR PROBABILITY CALCULATION
# ─────────────────────────────────────────────
# Estimated PA per game ≈ 4
PA_PER_GAME = 4

# Adjusted HR/PA = batter base × pitcher factor × park factor
df["Adj HR/PA"] = (df["HR/PA"] * df["Pit Factor"] * df["Park Factor"]).round(4)

# P(at least 1 HR) = 1 - (1 - HR/PA)^PA
df["HR Prob %"] = (1 - (1 - df["Adj HR/PA"])**PA_PER_GAME) * 100
df["HR Prob %"] = df["HR Prob %"].round(1)

# Implied fair odds for "to hit a HR"
def prob_to_odds(p):
    p = p / 100
    if p <= 0 or p >= 1:
        return "—"
    if p >= 0.5:
        return f"-{int(p / (1 - p) * 100)}"
    return f"+{int((1 - p) / p * 100)}"

df["Fair Odds"] = df["HR Prob %"].apply(prob_to_odds)

if search:
    df = df[df["Player"].str.lower().str.contains(search)]

df = df.sort_values("HR Prob %", ascending=False).reset_index(drop=True)

# ─────────────────────────────────────────────
# DISPLAY
# ─────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
c1.metric("Batters playing tonight", len(df))
c2.metric("Avg HR Prob", f"{df['HR Prob %'].mean():.1f}%")
c3.metric("Top HR Prob", f"{df['HR Prob %'].max():.1f}%")

st.markdown("---")

display_cols = ["Player","Team","Opp Team","Opp Pitcher","Opp HR/9","Park Factor","Pit Factor",
                "PA","HR","HR/PA","HR Prob %","Fair Odds"]

def show_picks(df_in, n, title, emoji):
    st.markdown(f"### {emoji} {title}")
    st.dataframe(df_in.head(n)[display_cols], hide_index=True, use_container_width=True)

show_picks(df, 3, "Top 3 — Best HR Bets", "💥")
show_picks(df.iloc[3:9], 6, "Picks 4–9 — Strong Backup Plays", "🎯")
show_picks(df.iloc[9:18], 9, "Picks 10–18 — Honorable Mentions", "📋")

with st.expander("📊 Full ranked list"):
    st.dataframe(df[display_cols], hide_index=True, use_container_width=True)

with st.expander("ℹ️ How HR probability is calculated"):
    st.markdown("""
    **Inputs:**
    - **HR/PA** — batter's home run rate per plate appearance (season)
    - **Pit Factor** — opposing pitcher's HR/9 ÷ league avg (1.20)
    - **Park Factor** — venue's historical HR boost/suppression (Coors = 1.35, Petco = 0.83)
    
    **Formula:**
    ```
    Adjusted HR/PA = HR/PA × Pit Factor × Park Factor
    HR Prob % = 1 - (1 - Adjusted HR/PA)^4
    ```
    (Using 4 plate appearances per game as the average.)
    
    **Fair Odds** = the American odds equivalent of the HR probability.
    
    **How to bet:**
    - If sportsbook offers HR odds **better** than Fair Odds → potential value
    - Example: Fair Odds +400, sportsbook offers +500 → +1% edge per bet
    - HR props are high-variance — never stake more than 1% of bankroll per pick
    """)
