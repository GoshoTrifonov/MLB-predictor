"""
Results Tracker — A/B/C model comparison
Handles nested structure: history[date][prop_type]["picks"]["model_X"]
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from picks_storage import load_picks_history, save_picks_history, get_player_results

TORONTO_TZ = ZoneInfo("America/Toronto")

st.set_page_config(page_title="Results Tracker", page_icon="📊", layout="wide")
st.title("📊 Results Tracker — A/B/C Comparison")
st.caption("Compare how each model's picks actually performed")

history, sha = load_picks_history()



if not history:
    st.info("No picks saved yet. Save picks on **HRR Picks** or **HR Picks** first!")
    st.stop()

dates_sorted = sorted(history.keys(), reverse=True)
st.sidebar.markdown(f"**Tracked days:** {len(dates_sorted)}")

selected_date = st.selectbox("Pick a date to review", dates_sorted)
day_data = history[selected_date]

# ─────────────────────────────────────────────
# HELPER: Extract all picks from a day's data
# ─────────────────────────────────────────────
def get_models_dict(prop_data):
    """Returns {'A': [...], 'B': [...], 'C': [...]} or None if legacy format."""
    if not isinstance(prop_data, dict):
        return None
    picks_field = prop_data.get("picks")
    if isinstance(picks_field, dict):
        # New format: picks is a dict with model_A/B/C keys
        result = {}
        for k, v in picks_field.items():
            if k.startswith("model_") and isinstance(v, list):
                letter = k.split("_", 1)[1]
                result[letter] = v
        return result if result else None
    return None

def get_legacy_picks(prop_data):
    """Returns picks list for legacy single-model format, or None."""
    if not isinstance(prop_data, dict):
        return None
    picks_field = prop_data.get("picks")
    if isinstance(picks_field, list):
        return picks_field
    return None

def all_pick_lists(prop_data):
    """Yield all pick lists regardless of format."""
    models = get_models_dict(prop_data)
    if models:
        for letter, lst in models.items():
            yield lst
    legacy = get_legacy_picks(prop_data)
    if legacy:
        yield legacy

def is_verified(day_data):
    """A day is verified if any pick has the verified_date set."""
    for prop_data in day_data.values():
        for pick_list in all_pick_lists(prop_data):
            for p in pick_list:
                if isinstance(p, dict) and p.get("verified_date") == selected_date:
                    return True
    return False

verified = is_verified(day_data)

# ─────────────────────────────────────────────
# VERIFY BUTTON
# ─────────────────────────────────────────────
c1, c2 = st.columns([3,1])
with c1:
    st.subheader(f"Picks from {selected_date}")
with c2:
    if not verified:
        if st.button("🔍 Check Results"):
            with st.spinner("Pulling actual results..."):
                # Collect unique players to query
                unique_players = set()
                for prop_data in day_data.values():
                    for pick_list in all_pick_lists(prop_data):
                        for p in pick_list:
                            if isinstance(p, dict) and "Player" in p:
                                unique_players.add(p["Player"])
                
                results_map = {}
                for name in unique_players:
                    results_map[name] = get_player_results(name, selected_date)
                    time.sleep(0.15)
                
                # Apply results back to all picks
                for prop_data in day_data.values():
                    for pick_list in all_pick_lists(prop_data):
                        for p in pick_list:
                            if not isinstance(p, dict): continue
                            r = results_map.get(p.get("Player")) or {}
                            p["actual_HRR"]    = r.get("HRR", 0)
                            p["actual_HR"]     = r.get("HR", 0)
                            p["played"]        = r.get("played", False)
                            p["verified_date"] = selected_date
                save_picks_history(history, sha)
            st.success("Results updated!")
            st.rerun()
    else:
        st.success("✅ Verified")

# ─────────────────────────────────────────────
# WIN FUNCTIONS
# ─────────────────────────────────────────────
def hrr_won(p):
    return p.get("actual_HRR", 0) >= 1

def hr_won(p):
    return p.get("actual_HR", 0) >= 1

def model_summary(picks, win_fn):
    played = [p for p in picks if isinstance(p, dict) and p.get("played")]
    wins = sum(1 for p in played if win_fn(p))
    return wins, len(played)

# ─────────────────────────────────────────────
# DISPLAY EACH PROP TYPE
# ─────────────────────────────────────────────
for prop_type, prop_data in day_data.items():
    label = "🎯 H+R+RBI Picks" if prop_type == "hrr" else "💥 HR Picks"
    win_fn = hrr_won if prop_type == "hrr" else hr_won
    actual_col = "actual_HRR" if prop_type == "hrr" else "actual_HR"
    
    st.markdown(f"### {label}")
    
    models = get_models_dict(prop_data)
    
    if models:
        # 3-model format
        cols = st.columns(3)
        for i, letter in enumerate(["A","B","C"]):
            picks = models.get(letter, [])
            wins, total = model_summary(picks, win_fn) if verified else (0, 0)
            with cols[i]:
                if verified and total > 0:
                    st.metric(f"Model {letter}", f"{wins}/{total}", f"{wins/total*100:.0f}%")
                else:
                    st.metric(f"Model {letter}", "—", f"{len(picks)} picks")
        
        chosen = st.radio("Show table for", ["A","B","C"], horizontal=True, key=f"{prop_type}_radio")
        picks = models.get(chosen, [])
        df = pd.DataFrame(picks)
        if verified and "played" in df.columns:
            df["Win?"] = df.apply(
                lambda r: "—" if not r.get("played")
                else ("✅" if win_fn(r) else "❌"), axis=1
            )
            cols_show = [c for c in ["Player","Team","Opp Pitcher", actual_col, "Win?"] if c in df.columns]
        else:
            cols_show = [c for c in df.columns if c in [
                "Player","Team","H/A","Opp Team","Opp Pitcher","Score","HR Prob %","Per Game"
            ]]
        if not df.empty:
            st.dataframe(df[cols_show], hide_index=True, use_container_width=True)
    else:
        # Legacy format
        picks = get_legacy_picks(prop_data) or []
        df = pd.DataFrame(picks)
        if not df.empty:
            if verified and "played" in df.columns:
                df["Win?"] = df.apply(
                    lambda r: "—" if not r.get("played")
                    else ("✅" if win_fn(r) else "❌"), axis=1
                )
                cols_show = [c for c in ["Player","Team","Opp Pitcher", actual_col, "Win?"] if c in df.columns]
            else:
                cols_show = [c for c in df.columns if c in [
                    "Player","Team","Opp Pitcher","Score","HR Prob %","Per Game"
                ]]
            st.dataframe(df[cols_show], hide_index=True, use_container_width=True)

# ─────────────────────────────────────────────
# ROLLING A/B/C LEADERBOARD
# ─────────────────────────────────────────────
st.markdown("---")
st.subheader("📈 Rolling Performance (All Tracked Days)")

def aggregate(prop_type, win_fn):
    by_model = {"A":[], "B":[], "C":[], "legacy":[]}
    for date, day_data in history.items():
        prop_data = day_data.get(prop_type)
        if not prop_data: continue
        models = get_models_dict(prop_data)
        if models:
            for letter, picks in models.items():
                for p in picks:
                    if isinstance(p, dict) and p.get("played"):
                        by_model[letter].append(win_fn(p))
        else:
            legacy = get_legacy_picks(prop_data) or []
            for p in legacy:
                if isinstance(p, dict) and p.get("played"):
                    by_model["legacy"].append(win_fn(p))
    return by_model

c1, c2 = st.columns(2)

with c1:
    st.markdown("**🎯 H+R+RBI Models**")
    agg = aggregate("hrr", hrr_won)
    for letter in ["A","B","C"]:
        results = agg[letter]
        if results:
            wr = sum(results)/len(results)*100
            st.metric(f"Model {letter}", f"{wr:.1f}%", f"{sum(results)}/{len(results)}")
        else:
            st.metric(f"Model {letter}", "—")

with c2:
    st.markdown("**💥 HR Models**")
    agg = aggregate("hr", hr_won)
    for letter in ["A","B","C"]:
        results = agg[letter]
        if results:
            wr = sum(results)/len(results)*100
            st.metric(f"Model {letter}", f"{wr:.1f}%", f"{sum(results)}/{len(results)}")
        else:
            st.metric(f"Model {letter}", "—")

with st.expander("ℹ️ How A/B/C tracking works"):
    st.markdown("""
    Each save stores top 10 picks from all 3 models simultaneously.
    
    Click **Check Results** the day after to verify.
    
    - **HRR pick wins** = actual H+R+RBI ≥ 1
    - **HR pick wins** = actual HR ≥ 1
    
    Rolling leaderboard accumulates across all tracked days.
    """)
# ═══════════════════════════════════════════════════════════════════════════
# MONEYLINE & EXP RUNS TRACKING (from Home page)
# ═══════════════════════════════════════════════════════════════════════════

import requests

st.markdown("---")
st.markdown("## ⚾ Moneyline & Run Total Tracker")
st.caption("From the Home page picks (value bets only)")

ml_history = history  # reuse already-loaded data

@st.cache_data(ttl=900)
def get_finished_games(date_str):
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {"sportId": 1, "date": date_str, "hydrate": "linescore"}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            return []
        out = []
        for d in r.json().get("dates", []):
            for g in d.get("games", []):
                if g.get("status", {}).get("abstractGameState") != "Final":
                    continue
                home = g["teams"]["home"]
                away = g["teams"]["away"]
                out.append({
                    "home":       home["team"]["name"],
                    "away":       away["team"]["name"],
                    "home_score": home.get("score", 0),
                    "away_score": away.get("score", 0),
                })
        return out
    except Exception:
        return []

def find_actual_result(matchup_str, date_str):
    if " @ " not in matchup_str:
        return None
    away, home = matchup_str.split(" @ ")
    for g in get_finished_games(date_str):
        if (home.lower() in g["home"].lower() or g["home"].lower() in home.lower()) and \
           (away.lower() in g["away"].lower() or g["away"].lower() in away.lower()):
            winner = "Home" if g["home_score"] > g["away_score"] else "Away"
            return {
                "winner": winner,
                "total":  g["home_score"] + g["away_score"],
                "score":  f"{g['away_score']}-{g['home_score']}",
            }
    return None

ml_rows = []
for date_key in sorted(ml_history.keys(), reverse=True):
    day = ml_history[date_key]
    if "moneyline" not in day:
        continue
    
    # Handle both flat list and nested {"picks": [...]} structures
    ml_data = day["moneyline"]
    if isinstance(ml_data, dict):
        picks_list = ml_data.get("picks", [])
    elif isinstance(ml_data, list):
        picks_list = ml_data
    else:
        picks_list = []
    
    for pick in picks_list:
        if not isinstance(pick, dict):
            continue
        actual = find_actual_result(pick.get("matchup", ""), date_key)
        row = {
            "Date":     date_key,
            "Matchup":  pick["matchup"],
            "Home L10": pick.get("home_l10", "—"),
            "Away L10": pick.get("away_l10", "—"),
            "Exp Runs": pick.get("exp_runs", "—"),
            "Bet":      pick.get("bet", "—"),
        }
        if actual:
            row["Score"] = actual["score"]
            row["Total"] = actual["total"]
            bet = pick.get("bet", "")
            if "Home" in bet:
                row["ML Result"] = "✅ Win" if actual["winner"] == "Home" else "❌ Loss"
            elif "Away" in bet:
                row["ML Result"] = "✅ Win" if actual["winner"] == "Away" else "❌ Loss"
            else:
                row["ML Result"] = "➖ Pass"
            try:
                exp = float(pick.get("exp_runs", 0))
                row["Diff"] = round(abs(exp - actual["total"]), 1)
            except (ValueError, TypeError):
                row["Diff"] = "—"
        else:
            row["Score"]     = "—"
            row["Total"]     = "—"
            row["ML Result"] = "⏳ Pending"
            row["Diff"]      = "—"
        ml_rows.append(row)

if not :
    st.info("No moneyline picks saved yet. Go to **Home** and click '💾 Save Today's Picks'.")
else:
    ml_df = pd.DataFrame(ml_rows)
    settled = ml_df[ml_df["ML Result"].isin(["✅ Win", "❌ Loss"])]
    wins    = (settled["ML Result"] == "✅ Win").sum()
    total_b = len(settled)
    win_pct = round(wins / total_b * 100, 1) if total_b else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Picks", len(ml_df))
    c2.metric("Settled Bets", total_b)
    c3.metric("ML Win Rate", f"{win_pct}%")
    c4.metric("Pending", (ml_df["ML Result"] == "⏳ Pending").sum())

    valid_diffs = [r["Diff"] for r in ml_rows if isinstance(r["Diff"], (int, float))]
    if valid_diffs:
        avg_diff = round(sum(valid_diffs) / len(valid_diffs), 2)
        st.metric("Avg Exp Runs Error", f"±{avg_diff} runs",
                  help="Lower = better run total predictions")

    st.dataframe(ml_df, hide_index=True, use_container_width=True)
