"""
MLB HR Probability — 3 Models for A/B/C comparison
- Model A: HR/PA only (baseline)
- Model B: HR/PA + Pitcher
- Model C: HR/PA + Pitcher + Park + Home/Away (full)
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

st.set_page_config(page_title="HR Picks", page_icon="💥", layout="wide")
st.title("💥 MLB Home Run Probability Picks")
st.caption(f"3-model A/B/C comparison • {datetime.now(TORONTO_TZ).strftime('%A, %B %d, %Y')}")

TEAM_IDS = [108,109,110,111,112,113,114,115,116,117,118,119,120,121,133,
            134,135,136,137,138,139,140,141,142,143,144,145,146,147,158]

TEAM_NAMES = {
    108:"LAA",109:"ARI",110:"BAL",111:"BOS",112:"CHC",113:"CIN",114:"CLE",
    115:"COL",116:"DET",117:"HOU",118:"KCR",119:"LAD",120:"WSN",121:"NYM",
    133:"OAK",134:"PIT",135:"SDP",136:"SEA",137:"SFG",138:"STL",139:"TBR",
    140:"TEX",141:"TOR",142:"MIN",143:"PHI",144:"ATL",145:"CHW",146:"MIA",
    147:"NYY",158:"MIL"
}

PARK_HR_FACTORS = {
    115:1.35,147:1.20,113:1.18,111:1.15,140:1.13,142:1.10,158:1.08,110:1.07,
    143:1.05,121:1.03,144:1.02,109:1.01,116:1.00,117:0.99,119:0.98,138:0.97,
    108:0.97,145:0.96,146:0.95,134:0.95,112:0.94,133:0.93,114:0.93,136:0.92,
    118:0.92,120:0.90,141:0.90,137:0.85,135:0.83,139:0.82,
}

LEAGUE_AVG_HR_PER_9 = 1.20
PA_PER_GAME = 4

@st.cache_data(ttl=3600)
def get_batter_season(team_id):
    season = datetime.now(TORONTO_TZ).year
    url = "https://statsapi.mlb.com/api/v1/stats"
    params = {"stats":"season","group":"hitting","teamId":team_id,
              "season":season,"sportIds":1}
    try:
        return requests.get(url, params=params, timeout=10).json()
    except Exception:
        return {}

@st.cache_data(ttl=3600)
def get_team_hr_splits(team_id):
    season = datetime.now(TORONTO_TZ).year
    url = "https://statsapi.mlb.com/api/v1/stats"
    params = {
        "stats":"statSplits","group":"hitting","sitCodes":"h,a",
        "teamId":team_id,"season":season,"sportIds":1,
    }
    try:
        return requests.get(url, params=params, timeout=10).json()
    except Exception:
        return {}

def parse_hr_splits(data):
    out = {}
    for split in data.get("stats", []):
        for s in split.get("splits", []):
            sit = s.get("split", {}).get("code")
            pid = s.get("player", {}).get("id")
            if not pid: continue
            stat = s.get("stat", {})
            hr = stat.get("homeRuns", 0)
            pa = stat.get("plateAppearances", 0)
            rate = hr / pa if pa else 0
            if pid not in out: out[pid] = {}
            if sit == "h":   out[pid]["home_hrr"] = rate
            elif sit == "a": out[pid]["away_hrr"] = rate
    return out

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
            home, away = g["teams"]["home"], g["teams"]["away"]
            home_id, away_id = home["team"]["id"], away["team"]["id"]
            home_pit = home.get("probablePitcher", {})
            away_pit = away.get("probablePitcher", {})
            matchups[home_id] = {
                "opp_pit_id": away_pit.get("id"),
                "opp_pit_name": away_pit.get("fullName", "TBD"),
                "opp_team": TEAM_NAMES.get(away_id, str(away_id)),
                "park_team_id": home_id, "is_home": True,
            }
            matchups[away_id] = {
                "opp_pit_id": home_pit.get("id"),
                "opp_pit_name": home_pit.get("fullName", "TBD"),
                "opp_team": TEAM_NAMES.get(home_id, str(home_id)),
                "park_team_id": home_id, "is_home": False,
            }
    return matchups

@st.cache_data(ttl=3600)
def get_pitcher_hr_rate(pitcher_id):
    if pitcher_id is None: return None
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
                    return {"hr_per_9": (hr / ip) * 9}
    except Exception:
        pass
    return None

@st.cache_data(ttl=3600)
def fetch_all_batter_hr_stats():
    rows = []
    splits_by_player = {}
    for tid in TEAM_IDS:
        data = get_batter_season(tid)
        splits_data = get_team_hr_splits(tid)
        splits_by_player.update(parse_hr_splits(splits_data))
        for split in data.get("stats", []):
            for s in split.get("splits", []):
                p = s.get("player", {})
                st_ = s.get("stat", {})
                pa = st_.get("plateAppearances", 0)
                if pa < 30: continue
                hr = st_.get("homeRuns", 0)
                pid = p.get("id")
                rows.append({
                    "player_id": pid,
                    "Player":  p.get("fullName"),
                    "team_id": tid,
                    "Team":    TEAM_NAMES.get(tid, str(tid)),
                    "G":       st_.get("gamesPlayed", 0),
                    "PA":      pa,
                    "HR":      hr,
                    "HR/PA":   round(hr / pa, 4) if pa else 0,
                    "home_hrr": splits_by_player.get(pid, {}).get("home_hrr"),
                    "away_hrr": splits_by_player.get(pid, {}).get("away_hrr"),
                })
        time.sleep(0.1)
    return pd.DataFrame(rows)

# Sidebar
min_pa = st.sidebar.slider("Min plate appearances", 30, 150, 80)
min_hr = st.sidebar.slider("Min season HRs", 0, 15, 2)
search = st.sidebar.text_input("Search player").lower()
which_model = st.sidebar.radio("Display model", ["Model C (Full)","Model B","Model A"], index=0)

with st.spinner("Pulling batter HR stats + splits..."):
    df = fetch_all_batter_hr_stats()

with st.spinner("Pulling tonight's matchups..."):
    matchups = get_todays_matchups()

df = df[(df["PA"] >= min_pa) & (df["HR"] >= min_hr)].copy()
df = df[df["team_id"].isin(matchups.keys())].copy()

if len(df) == 0:
    st.warning("No qualifying batters playing today.")
    st.stop()

df["Opp Pitcher"] = df["team_id"].map(lambda t: matchups.get(t,{}).get("opp_pit_name","TBD"))
df["Opp Team"]    = df["team_id"].map(lambda t: matchups.get(t,{}).get("opp_team","?"))
df["opp_pit_id"]  = df["team_id"].map(lambda t: matchups.get(t,{}).get("opp_pit_id"))
df["park_id"]     = df["team_id"].map(lambda t: matchups.get(t,{}).get("park_team_id"))
df["is_home"]     = df["team_id"].map(lambda t: matchups.get(t,{}).get("is_home", False))
df["H/A"]         = df["is_home"].map({True:"🏠", False:"✈️"})
df["Park Factor"] = df["park_id"].map(PARK_HR_FACTORS).fillna(1.0).round(2)

# Pitcher fetch
unique_pids = df["opp_pit_id"].dropna().unique()
pit_cache = {}
prog = st.progress(0, text="Fetching pitcher HR/9...")
for i, pid in enumerate(unique_pids):
    pit_cache[int(pid)] = get_pitcher_hr_rate(int(pid))
    prog.progress((i+1)/len(unique_pids))
prog.empty()

def pitcher_hr_factor(pid):
    if pd.isna(pid): return 1.0
    stats = pit_cache.get(int(pid))
    if not stats or stats.get("hr_per_9") is None: return 1.0
    return max(0.5, min(2.0, stats["hr_per_9"] / LEAGUE_AVG_HR_PER_9))

def loc_hr_factor(row):
    h = row.get("home_hrr"); a = row.get("away_hrr")
    if pd.isna(h) or pd.isna(a): return 1.0
    relevant = h if row["is_home"] else a
    avg = (h + a) / 2
    if avg == 0: return 1.0
    return max(0.6, min(1.4, relevant / avg))

df["Opp HR/9"]   = df["opp_pit_id"].apply(
    lambda pid: round(pit_cache.get(int(pid),{}).get("hr_per_9"), 2)
                 if pd.notna(pid) and pit_cache.get(int(pid)) else None
)
df["Pit Factor"] = df["opp_pit_id"].apply(pitcher_hr_factor).round(2)
df["Loc Factor"] = df.apply(loc_hr_factor, axis=1).round(2)

# Three model probabilities
def hr_prob(adj_hr_pa):
    return ((1 - (1 - adj_hr_pa)**PA_PER_GAME) * 100).round(1)

df["Adj A"] = df["HR/PA"].round(4)
df["Adj B"] = (df["HR/PA"] * df["Pit Factor"]).round(4)
df["Adj C"] = (df["HR/PA"] * df["Pit Factor"] * df["Park Factor"] * df["Loc Factor"]).round(4)

df["HR% A"] = hr_prob(df["Adj A"])
df["HR% B"] = hr_prob(df["Adj B"])
df["HR% C"] = hr_prob(df["Adj C"])

def prob_to_odds(p):
    p = p / 100
    if p <= 0 or p >= 1: return "—"
    if p >= 0.5: return f"-{int(p / (1 - p) * 100)}"
    return f"+{int((1 - p) / p * 100)}"

df["Fair Odds C"] = df["HR% C"].apply(prob_to_odds)

if search:
    df = df[df["Player"].str.lower().str.contains(search)]

active_col = {"Model A":"HR% A","Model B":"HR% B","Model C (Full)":"HR% C"}[which_model]
df = df.sort_values(active_col, ascending=False).reset_index(drop=True)

# Save button
c1, c2, c3 = st.columns([2,1,2])
with c2:
    if st.button("💾 Save All 3 Models", use_container_width=True):
        out = {}
        for m, prob_col in [("A","HR% A"),("B","HR% B"),("C","HR% C")]:
            top10 = df.sort_values(prob_col, ascending=False).head(10).copy()
            out[f"model_{m}"] = top10[[
                "Player","Team","Opp Team","Opp Pitcher","H/A",
                prob_col,"HR/PA","PA","HR","Park Factor","Pit Factor","Loc Factor"
            ]].rename(columns={prob_col:"HR Prob %"}).to_dict(orient="records")
        if save_todays_picks("hr", out):
            st.success("✅ All 3 model picks saved!")
        else:
            st.error("Save failed — check GITHUB_TOKEN.")

st.markdown("---")

c1, c2, c3 = st.columns(3)
c1.metric("Batters playing", len(df))
c2.metric(f"Avg HR Prob ({which_model[:7]})", f"{df[active_col].mean():.1f}%")
c3.metric(f"Top HR Prob ({which_model[:7]})", f"{df[active_col].max():.1f}%")

display_cols = ["Player","Team","H/A","Opp Team","Opp Pitcher","Opp HR/9",
                "Park Factor","Pit Factor","Loc Factor",
                "PA","HR","HR/PA","HR% A","HR% B","HR% C","Fair Odds C"]

st.markdown(f"### Showing rankings by **{which_model}**")

def show_picks(df_in, n, title, emoji):
    st.markdown(f"#### {emoji} {title}")
    st.dataframe(df_in.head(n)[display_cols], hide_index=True, use_container_width=True)

show_picks(df, 3, "Top 3", "💥")
show_picks(df.iloc[3:9], 6, "Picks 4–9", "🎯")
show_picks(df.iloc[9:18], 9, "Picks 10–18", "📋")

with st.expander("📊 Full ranked list"):
    st.dataframe(df[display_cols], hide_index=True, use_container_width=True)

with st.expander("ℹ️ Models explained"):
    st.markdown("""
    All three start with each batter's season **HR/PA** rate.
    
    - **Model A** = HR/PA only (baseline) → `prob = 1 - (1 - HR/PA)^4`
    - **Model B** = HR/PA × Pitcher Factor
    - **Model C** = HR/PA × Pitcher × Park × Location (full)
    
    💾 Save button stores top 10 from each model so we can compare on **Results** page.
    """)
