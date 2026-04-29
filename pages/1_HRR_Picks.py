"""
MLB H+R+RBI Player Props Picker
Combines form, AVG, and OPS into one composite score
to surface today's top picks.
"""

import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TORONTO_TZ = ZoneInfo("America/Toronto")

st.set_page_config(page_title="H+R+RBI Picks", page_icon="🎯", layout="wide")
st.title("🎯 MLB H+R+RBI Top Picks")
st.caption(f"Today's top hitters by combined form score • {datetime.now(TORONTO_TZ).strftime('%A, %B %d, %Y')}")

TEAM_IDS = [108,109,110,111,112,113,114,115,116,117,118,119,120,121,133,
            134,135,136,137,138,139,140,141,142,143,144,145,146,147,158]

TEAM_NAMES = {
    108:"LAA",109:"ARI",110:"BAL",111:"BOS",112:"CHC",113:"CIN",114:"CLE",
    115:"COL",116:"DET",117:"HOU",118:"KCR",119:"LAD",120:"WSN",121:"NYM",
    133:"OAK",134:"PIT",135:"SDP",136:"SEA",137:"SFG",138:"STL",139:"TBR",
    140:"TEX",141:"TOR",142:"MIN",143:"PHI",144:"ATL",145:"CHW",146:"MIA",
    147:"NYY",158:"MIL"
}

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
def get_todays_teams():
    """Return set of team_ids playing today."""
    today = datetime.now(TORONTO_TZ).strftime("%Y-%m-%d")
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today}"
    try:
        data = requests.get(url, timeout=10).json()
        playing = set()
        for d in data.get("dates", []):
            for g in d.get("games", []):
                playing.add(g["teams"]["home"]["team"]["id"])
                playing.add(g["teams"]["away"]["team"]["id"])
        return playing
    except Exception:
        return set(TEAM_IDS)  # fallback: all teams

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

# ── Sidebar ──
days = st.sidebar.slider("Days back for form", 5, 20, 10)
min_games = st.sidebar.slider("Minimum games played", 3, 10, 5)
playing_only = st.sidebar.checkbox("Only show players playing today", value=True)
search = st.sidebar.text_input("Search player").lower()

# ── Fetch ──
with st.spinner(f"Pulling last {days}-day form for all hitters..."):
    df = fetch_all_batters(days)

df = df[df["G"] >= min_games].dropna(subset=["AVG","OPS"])

if playing_only:
    todays_teams = get_todays_teams()
    df = df[df["team_id"].isin(todays_teams)]

if search:
    df = df[df["Player"].str.lower().str.contains(search)]

# ── COMPOSITE SCORE ──
# Normalize each metric to 0-1, then weight & combine
df["pg_norm"]  = (df["Per Game"] - df["Per Game"].min()) / (df["Per Game"].max() - df["Per Game"].min())
df["avg_norm"] = (df["AVG"] - df["AVG"].min()) / (df["AVG"].max() - df["AVG"].min())
df["ops_norm"] = (df["OPS"] - df["OPS"].min()) / (df["OPS"].max() - df["OPS"].min())

# Weights: form is most important (50%), then OPS (30%), then AVG (20%)
df["Score"] = (df["pg_norm"]*0.5 + df["ops_norm"]*0.3 + df["avg_norm"]*0.2) * 100
df["Score"] = df["Score"].round(1)

df = df.sort_values("Score", ascending=False).reset_index(drop=True)

# ── HEADLINE METRICS ──
c1, c2, c3 = st.columns(3)
c1.metric("Hitters tracked", len(df))
c2.metric("Avg form (H+R+RBI/G)", f"{df['Per Game'].mean():.2f}")
c3.metric("Avg OPS", f"{df['OPS'].mean():.3f}")

st.markdown("---")

# ── TOP PICKS — Tiered View ──
def show_picks(df_in, n, title, emoji):
    st.markdown(f"### {emoji} {title}")
    cols_show = ["Player","Team","G","Per Game","AVG","OPS","Score"]
    st.dataframe(df_in.head(n)[cols_show], hide_index=True, use_container_width=True)

show_picks(df, 3, "Top 3 — Strongest Plays", "🏆")
show_picks(df.iloc[3:9], 6, "Picks 4–9 — Solid Backup Plays", "💎")
show_picks(df.iloc[9:18], 9, "Picks 10–18 — Honorable Mentions", "📋")

# ── FULL TABLE ──
with st.expander("📊 Full ranked list"):
    st.dataframe(df[["Player","Team","G","H","R","RBI","Per Game","AVG","OPS","Score"]],
                 hide_index=True, use_container_width=True)

# ── HOW IT WORKS ──
with st.expander("ℹ️ How the Score is calculated"):
    st.markdown("""
    The **Score** combines three metrics weighted by importance:
    - **50% — Per Game (H+R+RBI)** form over the last N days
    - **30% — OPS** (overall hitting quality)
    - **20% — AVG** (consistency)
    
    Each metric is normalized 0–1 across all qualifying hitters, weighted, then scaled to 0–100.
    
    **How to bet:**
    - Top 3 = strongest plays — H+R+RBI 1.5 line is usually a smart Over
    - Picks 4–9 = solid backups for parlays
    - Cross-reference with the opposing pitcher's recent ERA on the Home page
    """)
