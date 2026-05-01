"""
MLB H+R+RBI Top Picks — 3 Models for A/B/C comparison
- Model A: Form only (baseline)
- Model B: Form + Pitcher difficulty
- Model C: Form + Pitcher + Home/Away (full)
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

LEAGUE_AVG_ERA = 4.20

@st.cache_data(ttl=3600)
def get_team_form(team_id, days_back=15):
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
def get_team_splits(team_id):
    season = datetime.now(TORONTO_TZ).year
    url = "https://statsapi.mlb.com/api/v1/stats"
    params = {
        "stats": "statSplits", "group": "hitting", "sitCodes": "h,a",
        "teamId": team_id, "season": season, "sportIds": 1,
    }
    try:
        return requests.get(url, params=params, timeout=10).json()
    except Exception:
        return {}

def parse_team_splits(data):
    out = {}
    for split in data.get("stats", []):
        for s in split.get("splits", []):
            sit = s.get("split", {}).get("code")
            pid = s.get("player", {}).get("id")
            if not pid: continue
            ops = pd.to_numeric(s.get("stat", {}).get("ops"), errors="coerce")
            if pid not in out: out[pid] = {}
            if sit == "h":   out[pid]["home_ops"] = ops
            elif sit == "a": out[pid]["away_ops"] = ops
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
                "is_home": True,
            }
            matchups[away_id] = {
                "opp_pit_id": home_pit.get("id"),
                "opp_pit_name": home_pit.get("fullName", "TBD"),
                "opp_team": TEAM_NAMES.get(home_id, str(home_id)),
                "is_home": False,
            }
    return matchups

@st.cache_data(ttl=3600)
def get_pitcher_stats(pitcher_id):
    if pitcher_id is None: return None
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
def get_player_gamelog(player_id):
    season = datetime.now(TORONTO_TZ).year
    url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats"
    params = {"stats": "gameLog", "group": "hitting", "season": season}
    try:
        data = requests.get(url, params=params, timeout=10).json()
        games = []
        for split_group in data.get("stats", []):
            for s in split_group.get("splits", []):
                stat = s.get("stat", {})
                hrr = stat.get("hits", 0) + stat.get("runs", 0) + stat.get("rbi", 0)
                is_home = s.get("isHome", None)
                games.append({"hrr": hrr, "is_home": is_home})
        return games  # oldest → newest
    except Exception:
        return []
@st.cache_data(ttl=3600)
def fetch_all_batters(days_back=15):
    rows = []
    splits_by_player = {}
    for tid in TEAM_IDS:
        data = get_team_form(tid, days_back)
        splits_data = get_team_splits(tid)
        splits_by_player.update(parse_team_splits(splits_data))
        for split in data.get("stats", []):
            for s in split.get("splits", []):
                p = s.get("player", {})
                st_ = s.get("stat", {})
                g = st_.get("gamesPlayed", 0)
                if g < 3: continue
                hrr = st_.get("hits",0) + st_.get("runs",0) + st_.get("rbi",0)
                pid = p.get("id")
                rows.append({
                    "player_id": pid,
                    "Player":   p.get("fullName"),
                    "team_id":  tid,
                    "Team":     TEAM_NAMES.get(tid, str(tid)),
                    "G":        g,
                    "Per Game": round(hrr / g, 2) if g else 0,
                    "AVG":      pd.to_numeric(st_.get("avg"), errors="coerce"),
                    "OPS":      pd.to_numeric(st_.get("ops"), errors="coerce"),
                    "home_ops": splits_by_player.get(pid, {}).get("home_ops"),
                    "away_ops": splits_by_player.get(pid, {}).get("away_ops"),
                })
        time.sleep(0.1)
    return pd.DataFrame(rows)

# Sidebar
days = st.sidebar.slider("Days back for form", 5, 20, 15)
min_games = st.sidebar.slider("Minimum games played", 3, 10, 7)
search = st.sidebar.text_input("Search player").lower()
which_model = st.sidebar.radio("Display model", ["Model C (Full)","Model B","Model A"], index=0)

with st.spinner("Pulling batter form + splits..."):
    df = fetch_all_batters(days)

with st.spinner("Pulling tonight's matchups..."):
    matchups = get_todays_matchups()

df = df[df["G"] >= min_games].dropna(subset=["AVG","OPS"])
df = df[df["team_id"].isin(matchups.keys())].copy()

df["Opp Pitcher"] = df["team_id"].map(lambda t: matchups.get(t, {}).get("opp_pit_name", "TBD"))
df["Opp Team"]    = df["team_id"].map(lambda t: matchups.get(t, {}).get("opp_team", "?"))
df["opp_pit_id"]  = df["team_id"].map(lambda t: matchups.get(t, {}).get("opp_pit_id"))
df["is_home"]     = df["team_id"].map(lambda t: matchups.get(t, {}).get("is_home", False))
df["H/A"]         = df["is_home"].map({True:"🏠", False:"✈️"})

# Pitcher fetch
unique_pitchers = df["opp_pit_id"].dropna().unique()
pitcher_cache = {}
prog = st.progress(0, text="Fetching pitcher stats...")
for i, pid in enumerate(unique_pitchers):
    pitcher_cache[int(pid)] = get_pitcher_stats(int(pid))
    prog.progress((i+1) / len(unique_pitchers))
prog.empty()
# Last 5 games streak
streak_ids = df["player_id"].dropna().unique()
streak_prog = st.progress(0, text="Fetching last 5 game logs...")
for i, pid in enumerate(streak_ids):
    get_player_gamelog(int(pid))
    streak_prog.progress((i + 1) / len(streak_ids))
streak_prog.empty()

def make_last10(player_id, threshold=1):
    games = get_player_gamelog(int(player_id))
    last10 = games[-10:]
    icons = []
    for g in last10:
        result = "✅" if g["hrr"] >= threshold else "❌"
        if g.get("is_home") is True:
            loc = "H"
        elif g.get("is_home") is False:
            loc = "A"
        else:
            loc = ""
        icons.append(result + loc)
    return " ".join(icons) if icons else "—"

df["Last 10 (old→new)"] = df["player_id"].apply(make_last10)
def pitcher_difficulty_factor(pid):
    if pd.isna(pid): return 1.0
    stats = pitcher_cache.get(int(pid))
    if not stats or pd.isna(stats.get("era")): return 1.0
    return max(0.5, min(1.5, stats["era"] / LEAGUE_AVG_ERA))

def location_factor(row):
    h = row.get("home_ops"); a = row.get("away_ops")
    if pd.isna(h) or pd.isna(a) or a == 0: return 1.0
    relevant = h if row["is_home"] else a
    avg = (h + a) / 2
    if avg == 0: return 1.0
    return max(0.7, min(1.3, relevant / avg))

df["PDF"]        = df["opp_pit_id"].apply(pitcher_difficulty_factor).round(2)
df["Loc Factor"] = df.apply(location_factor, axis=1).round(2)
df["Opp ERA"]    = df["opp_pit_id"].apply(
    lambda pid: round(pitcher_cache.get(int(pid), {}).get("era"), 2)
                 if pd.notna(pid) and pitcher_cache.get(int(pid)) else None
)

if search:
    df = df[df["Player"].str.lower().str.contains(search)]

# Build base score
df["pg_norm"]  = (df["Per Game"] - df["Per Game"].min()) / (df["Per Game"].max() - df["Per Game"].min())
df["avg_norm"] = (df["AVG"] - df["AVG"].min()) / (df["AVG"].max() - df["AVG"].min())
df["ops_norm"] = (df["OPS"] - df["OPS"].min()) / (df["OPS"].max() - df["OPS"].min())
base = (df["pg_norm"]*0.5 + df["ops_norm"]*0.3 + df["avg_norm"]*0.2) * 100

# Three model scores
df["Score A"] = base.round(1)                                   # form only
df["Score B"] = (base * df["PDF"]).round(1)                     # + pitcher
df["Score C"] = (base * df["PDF"] * df["Loc Factor"]).round(1)  # + location

active_score = {"Model A":"Score A","Model B":"Score B","Model C (Full)":"Score C"}[which_model]
df = df.sort_values(active_score, ascending=False).reset_index(drop=True)

# Save button — saves all 3 models' top 10 in one shot
c1, c2, c3 = st.columns([2,1,2])
with c2:
    if st.button("💾 Save All 3 Models", use_container_width=True):
        out = {}
        for m, score_col in [("A","Score A"),("B","Score B"),("C","Score C")]:
            top10 = df.sort_values(score_col, ascending=False).head(10).copy()
            out[f"model_{m}"] = top10[[
                "Player","Team","Opp Team","Opp Pitcher","H/A",
                score_col,"Per Game","AVG","OPS","PDF","Loc Factor"
            ]].rename(columns={score_col:"Score"}).to_dict(orient="records")
        if save_todays_picks("hrr", out):
            st.success("✅ All 3 model picks saved!")
        else:
            st.error("Save failed — check GITHUB_TOKEN.")

st.markdown("---")

c1, c2, c3 = st.columns(3)
c1.metric("Hitters playing", len(df))
c2.metric("Avg form (H+R+RBI/G)", f"{df['Per Game'].mean():.2f}")
c3.metric("Avg opp ERA", f"{df['Opp ERA'].mean():.2f}" if df['Opp ERA'].notna().any() else "—")

display_cols = ["Player","Last 10 (old→new)","Team","H/A","Opp Team","Opp Pitcher","Score A","Score B","Score C"]

st.markdown(f"### Showing rankings by **{which_model}**")
def show_picks(df_in, n, title, emoji):
    st.markdown(f"#### {emoji} {title}")
    st.dataframe(df_in.head(n)[display_cols], hide_index=True, use_container_width=True)

show_picks(df, 3, "Top 3", "🏆")
show_picks(df.iloc[3:9], 6, "Picks 4–9", "💎")
show_picks(df.iloc[9:18], 9, "Picks 10–18", "📋")

with st.expander("📊 Full ranked list"):
    st.dataframe(df[display_cols], hide_index=True, use_container_width=True)

with st.expander("ℹ️ Models explained"):
    st.markdown("""
    All three use the same **Base Score**: 50% form + 30% OPS + 20% AVG.
    
    - **Model A** = Base only (no adjustments)
    - **Model B** = Base × Pitcher Difficulty Factor (PDF)
    - **Model C** = Base × PDF × Location Factor (full model)
    
    💾 The "Save All 3 Models" button stores the top 10 from each model so we can compare 
    win rates on the **Results** page.
    """)
