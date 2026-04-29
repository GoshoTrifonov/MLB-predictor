"""
MLB H+R+RBI Top Picks — Pitcher-Adjusted (with Save button)
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

st.set_page_config(page_title="H+R+RBI Picks", page_icon="🎯", layout="wide")
st.title("🎯 MLB H+R+RBI Top Picks")
st.caption(f"Tonight's hitters ranked vs opposing pitcher quality • {datetime.now(TORONTO_TZ).strftime('%A, %B %d, %Y')}")

TEAM_IDS = [108,109,110,111,112,113,114,115,116,117,118,119,120,121,133,
            134,135,136,137,138,139,140,141,142,143,144,145,146,147,158]

TEAM_NAMES = {
    108:"LAA",109:"ARI",110:"BAL",111:"BOS",112:"CHC",113:"CIN",114:"CLE",
    115:"COL",116:"DET",117:"HOU",118:"KCR",119:"LAD",120:"WSN",121:"NYM",
    133:"OAK",134:"PIT",135:"SDP",136:"SEA",137:"SFG",138:"STL",139:"TBR",
    140:"TEX",141:"TOR",142:"MIN",143:"PHI",144:"ATL",145:"CHW",146:"MIA",
    147:"NYY",158:"MIL"
}

LEAGUE_AVG_ERA = 4.20

@st.cache_data(ttl=3600)
def get_team_form(team_id, days_back=10):
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
            matchups[home_id] = {
                "opp_pit_id": away_pit.get("id"),
                "opp_pit_name": away_pit.get("fullName", "TBD"),
                "opp_team": TEAM_NAMES.get(away_id, str(away_id)),
            }
            matchups[away_id] = {
                "opp_pit_id": home_pit.get("id"),
                "opp_pit_name": home_pit.get("fullName", "TBD"),
                "opp_team": TEAM_NAMES.get(home_id, str(home_id)),
            }
    return matchups

@st.cache_data(ttl=3600)
def get_pitcher_stats(pitcher_id):
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
                era = pd.to_numeric(stat.get("era"), errors="coerce")
                return {"era": era}
    except Exception:
        pass
    return None

@st.cache_data(ttl=3600)
def fetch_all_batters(days_back=10):
    rows = []
    for tid in TEAM_IDS:
        data = get_team_form(tid, days_back)
        for split in data.get("stats", []):
            for s in split.get("splits", []):
                p = s.get("player", {})
                st_ = s.get("stat", {})
                g = st_.get("gamesPlayed", 0)
                if g < 3: continue
                hrr = st_.get("hits",0) + st_.get("runs",0) + st_.get("rbi",0)
                rows.append({
                    "Player":   p.get("fullName"),
                    "team_id":  tid,
                    "Team":     TEAM_NAMES.get(tid, str(tid)),
                    "G":        g,
                    "AB":       st_.get("atBats",0),
                    "H":        st_.get("hits",0),
                    "R":        st_.get("runs",0),
                    "RBI":      st_.get("rbi",0),
                    "Per Game": round(hrr / g, 2) if g else 0,
                    "AVG":      pd.to_numeric(st_.get("avg"), errors="coerce"),
                    "OPS":      pd.to_numeric(st_.get("ops"), errors="coerce"),
                })
        time.sleep(0.1)
    return pd.DataFrame(rows)

# Sidebar
days = st.sidebar.slider("Days back for form", 5, 20, 10)
min_games = st.sidebar.slider("Minimum games played", 3, 10, 5)
search = st.sidebar.text_input("Search player").lower()

with st.spinner("Pulling batter form..."):
    df = fetch_all_batters(days)

with st.spinner("Pulling tonight's matchups..."):
    matchups = get_todays_matchups()

df = df[df["G"] >= min_games].dropna(subset=["AVG","OPS"])
df = df[df["team_id"].isin(matchups.keys())].copy()

df["Opp Pitcher"] = df["team_id"].map(lambda t: matchups.get(t, {}).get("opp_pit_name", "TBD"))
df["Opp Team"]    = df["team_id"].map(lambda t: matchups.get(t, {}).get("opp_team", "?"))
df["opp_pit_id"]  = df["team_id"].map(lambda t: matchups.get(t, {}).get("opp_pit_id"))

unique_pitchers = df["opp_pit_id"].dropna().unique()
pitcher_cache = {}
prog = st.progress(0, text="Fetching pitcher stats...")
for i, pid in enumerate(unique_pitchers):
    pitcher_cache[int(pid)] = get_pitcher_stats(int(pid))
    prog.progress((i+1) / len(unique_pitchers))
prog.empty()

def pitcher_difficulty_factor(pid):
    if pd.isna(pid): return 1.0
    stats = pitcher_cache.get(int(pid))
    if not stats or pd.isna(stats.get("era")): return 1.0
    return max(0.5, min(1.5, stats["era"] / LEAGUE_AVG_ERA))

df["PDF"] = df["opp_pit_id"].apply(pitcher_difficulty_factor).round(2)
df["Opp ERA"] = df["opp_pit_id"].apply(
    lambda pid: round(pitcher_cache.get(int(pid), {}).get("era"), 2)
                 if pd.notna(pid) and pitcher_cache.get(int(pid)) else None
)

if search:
    df = df[df["Player"].str.lower().str.contains(search)]

df["pg_norm"]  = (df["Per Game"] - df["Per Game"].min()) / (df["Per Game"].max() - df["Per Game"].min())
df["avg_norm"] = (df["AVG"] - df["AVG"].min()) / (df["AVG"].max() - df["AVG"].min())
df["ops_norm"] = (df["OPS"] - df["OPS"].min()) / (df["OPS"].max() - df["OPS"].min())

base = (df["pg_norm"]*0.5 + df["ops_norm"]*0.3 + df["avg_norm"]*0.2) * 100
df["Score"] = (base * df["PDF"]).round(1)
df = df.sort_values("Score", ascending=False).reset_index(drop=True)

# ── SAVE BUTTON ──
c1, c2, c3 = st.columns([2,1,2])
with c2:
    if st.button("💾 Save Today's Picks", use_container_width=True):
        top10 = df.head(10).copy()
        picks_to_save = top10[["Player","Team","Opp Team","Opp Pitcher","Score","Per Game","AVG","OPS"]].to_dict(orient="records")
        if save_todays_picks("hrr", picks_to_save):
            st.success("✅ Top 10 H+R+RBI picks saved!")
        else:
            st.error("Save failed — check GITHUB_TOKEN in secrets.")

st.markdown("---")

c1, c2, c3 = st.columns(3)
c1.metric("Hitters playing tonight", len(df))
c2.metric("Avg form", f"{df['Per Game'].mean():.2f}")
c3.metric("Avg opp ERA", f"{df['Opp ERA'].mean():.2f}" if df['Opp ERA'].notna().any() else "—")

display_cols = ["Player","Team","Opp Team","Opp Pitcher","Opp ERA","PDF",
                "G","Per Game","AVG","OPS","Score"]

def show_picks(df_in, n, title, emoji):
    st.markdown(f"### {emoji} {title}")
    st.dataframe(df_in.head(n)[display_cols], hide_index=True, use_container_width=True)

show_picks(df, 3, "Top 3 — Strongest Plays", "🏆")
show_picks(df.iloc[3:9], 6, "Picks 4–9 — Solid Backup Plays", "💎")
show_picks(df.iloc[9:18], 9, "Picks 10–18 — Honorable Mentions", "📋")

with st.expander("📊 Full ranked list"):
    st.dataframe(df[display_cols], hide_index=True, use_container_width=True)
