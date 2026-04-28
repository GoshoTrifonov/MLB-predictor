"""
MLB H+R+RBI Player Props Picker
Pulls today's active hitters with their last-10-day H+R+RBI form
and displays a ranked leaderboard.
"""

import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

TORONTO_TZ = ZoneInfo("America/Toronto")

st.set_page_config(page_title="H+R+RBI Picks", page_icon="🎯", layout="wide")
st.title("🎯 MLB H+R+RBI Form Tracker")
st.caption(f"Last 10 days form • {datetime.now(TORONTO_TZ).strftime('%A, %B %d, %Y')}")

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
                    "Team":     TEAM_NAMES.get(tid, tid),
                    "G":        g,
                    "AB":       st_.get("atBats",0),
                    "H":        st_.get("hits",0),
                    "R":        st_.get("runs",0),
                    "RBI":      st_.get("rbi",0),
                    "H+R+RBI":  hrr,
                    "Per Game": round(hrr / g, 2) if g else 0,
                    "AVG":      st_.get("avg"),
                    "OPS":      st_.get("ops"),
                })
        time.sleep(0.1)
    return pd.DataFrame(rows)

# ── Sidebar controls ──
days = st.sidebar.slider("Days back for form", 5, 20, 10)
min_games = st.sidebar.slider("Minimum games played", 3, 10, 5)
search = st.sidebar.text_input("Search player").lower()

# ── Fetch data ──
with st.spinner(f"Pulling last {days}-day form for all hitters..."):
    df = fetch_all_batters(days)

df = df[df["G"] >= min_games].sort_values("Per Game", ascending=False)

if search:
    df = df[df["Player"].str.lower().str.contains(search)]

# ── Display ──
st.markdown(f"### Top H+R+RBI hitters (last {days} days)")
st.metric("Active hitters tracked", len(df))

st.dataframe(
    df[["Player","Team","G","H","R","RBI","H+R+RBI","Per Game","AVG","OPS"]],
    use_container_width=True, hide_index=True
)

# ── Quick filters ──
st.markdown("---")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**🔥 Hottest (3.0+ per game)**")
    hot = df[df["Per Game"] >= 3.0][["Player","Team","Per Game"]].head(10)
    st.dataframe(hot, hide_index=True, use_container_width=True)

with col2:
    st.markdown("**📈 Best AVG**")
    if "AVG" in df.columns:
        best_avg = df.dropna(subset=["AVG"]).copy()
        best_avg["AVG_n"] = pd.to_numeric(best_avg["AVG"], errors="coerce")
        best_avg = best_avg.nlargest(10, "AVG_n")[["Player","Team","AVG","Per Game"]]
        st.dataframe(best_avg, hide_index=True, use_container_width=True)

with col3:
    st.markdown("**💪 Best OPS**")
    if "OPS" in df.columns:
        best_ops = df.dropna(subset=["OPS"]).copy()
        best_ops["OPS_n"] = pd.to_numeric(best_ops["OPS"], errors="coerce")
        best_ops = best_ops.nlargest(10, "OPS_n")[["Player","Team","OPS","Per Game"]]
        st.dataframe(best_ops, hide_index=True, use_container_width=True)

with st.expander("ℹ️ How to use this"):
    st.markdown("""
    - **Per Game** = avg H+R+RBI per game over the last N days
    - When a sportsbook posts an H+R+RBI prop (usually 1.5 or 2.5):
      - If the player's recent **Per Game > line + 0.5** → consider OVER
      - If the player's recent **Per Game < line - 0.5** → consider UNDER
    - Cross-reference with the opposing pitcher's quality (use the main predictor page)
    
    ⚠️ This is form-only. For full edge calc we'd need today's prop lines from a sportsbook API.
    """)
