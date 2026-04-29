"""
Results Tracker — A/B/C model comparison with rolling stats.
"""

import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
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
    st.info("No picks saved yet. Go to **HRR Picks** or **HR Picks** and click 'Save All 3 Models' to start tracking!")
    st.stop()

dates_sorted = sorted(history.keys(), reverse=True)
st.sidebar.markdown(f"**Tracked days:** {len(dates_sorted)}")

selected_date = st.selectbox("Pick a date to review", dates_sorted)
day_data = history[selected_date]

# Detect format: new (with model_A/B/C subkeys) or old (single picks list)
def is_multi_model(prop_data):
    if not isinstance(prop_data, dict): return False
    return any(k.startswith("model_") for k in prop_data.keys())

# ── VERIFY BUTTON ──
def all_verified(day_data):
    flat_picks = []
    for prop_data in day_data.values():
        if is_multi_model(prop_data):
            for k, lst in prop_data.items():
                if k.startswith("model_"):
                    flat_picks.extend(lst)
        elif "picks" in prop_data:
            flat_picks.extend(prop_data["picks"])
    return all(p.get("verified_date") == selected_date for p in flat_picks) if flat_picks else False

verified = all_verified(day_data)

c1, c2 = st.columns([3,1])
with c1:
    st.subheader(f"Picks from {selected_date}")
with c2:
    if not verified:
        if st.button("🔍 Check Results"):
            with st.spinner("Pulling actual results..."):
                # Build one set of unique players to query (avoid duplicate API calls)
                unique_players = set()
                for prop_data in day_data.values():
                    if is_multi_model(prop_data):
                        for k, lst in prop_data.items():
                            if k.startswith("model_"):
                                for p in lst:
                                    unique_players.add(p["Player"])
                    elif "picks" in prop_data:
                        for p in prop_data["picks"]:
                            unique_players.add(p["Player"])
                
                results_map = {}
                for name in unique_players:
                    results_map[name] = get_player_results(name, selected_date)
                    time.sleep(0.15)
                
                # Apply results back to all picks
                for prop_data in day_data.values():
                    if is_multi_model(prop_data):
                        for k, lst in prop_data.items():
                            if k.startswith("model_"):
                                for p in lst:
                                    r = results_map.get(p["Player"]) or {}
                                    p["actual_HRR"] = r.get("HRR", 0)
                                    p["actual_HR"]  = r.get("HR", 0)
                                    p["played"]     = r.get("played", False)
                                    p["verified_date"] = selected_date
                    elif "picks" in prop_data:
                        for p in prop_data["picks"]:
                            r = results_map.get(p["Player"]) or {}
                            p["actual_HRR"] = r.get("HRR", 0)
                            p["actual_HR"]  = r.get("HR", 0)
                            p["played"]     = r.get("played", False)
                            p["verified_date"] = selected_date
                save_picks_history(history, sha)
            st.success("Results updated!")
            st.rerun()
    else:
        st.success("✅ Verified")

# ── DISPLAY PER MODEL ──
def hrr_won(p):
    return p.get("actual_HRR", 0) >= 1
def hr_won(p):
    return p.get("actual_HR", 0) >= 1

def model_summary(picks, win_fn):
    played = [p for p in picks if p.get("played")]
    wins = sum(1 for p in played if win_fn(p))
    return wins, len(played)

for prop_type, prop_data in day_data.items():
    label = "🎯 H+R+RBI Picks" if prop_type == "hrr" else "💥 HR Picks"
    win_fn = hrr_won if prop_type == "hrr" else hr_won
    actual_col = "actual_HRR" if prop_type == "hrr" else "actual_HR"
    
    st.markdown(f"### {label}")
    
    if is_multi_model(prop_data):
        # New 3-model format
        cols = st.columns(3)
        for i, model_key in enumerate(["model_A","model_B","model_C"]):
            picks = prop_data.get(model_key, [])
            wins, total = model_summary(picks, win_fn) if verified else (0, 0)
            with cols[i]:
                model_letter = model_key.split("_")[1]
                if verified and total > 0:
                    st.metric(f"Model {model_letter}", f"{wins}/{total}", f"{wins/total*100:.0f}%")
                else:
                    st.metric(f"Model {model_letter}", "—", f"{len(picks)} picks")
        
        # Detailed table
        chosen = st.radio(f"Show table for", ["A","B","C"], horizontal=True, key=f"{prop_type}_radio")
        picks = prop_data.get(f"model_{chosen}", [])
        df = pd.DataFrame(picks)
        if verified and "played" in df.columns:
            df["Win?"] = df.apply(
                lambda r: "—" if not r.get("played")
                else ("✅" if win_fn(r) else "❌"),
                axis=1
            )
            cols_show = ["Player","Team","Opp Pitcher", actual_col, "Win?"]
            cols_show = [c for c in cols_show if c in df.columns]
        else:
            cols_show = [c for c in df.columns if c in [
                "Player","Team","Opp Team","Opp Pitcher","Score","HR Prob %","Per Game","H/A"
            ]]
        st.dataframe(df[cols_show], hide_index=True, use_container_width=True)
    elif "picks" in prop_data:
        # Legacy single-model format
        picks = prop_data["picks"]
        df = pd.DataFrame(picks)
        if verified and "played" in df.columns:
            df["Win?"] = df.apply(
                lambda r: "—" if not r.get("played")
                else ("✅" if win_fn(r) else "❌"),
                axis=1
            )
            cols_show = [c for c in ["Player","Team","Opp Pitcher", actual_col, "Win?"] if c in df.columns]
        else:
            cols_show = [c for c in df.columns if c in [
                "Player","Team","Opp Pitcher","Score","HR Prob %","Per Game"
            ]]
        st.dataframe(df[cols_show], hide_index=True, use_container_width=True)

# ── ROLLING A/B/C LEADERBOARD ──
st.markdown("---")
st.subheader("📈 Rolling Performance (All Tracked Days)")

def aggregate(prop_type, win_fn):
    by_model = {"A":[], "B":[], "C":[], "legacy":[]}
    for date, day_data in history.items():
        prop_data = day_data.get(prop_type)
        if not prop_data: continue
        if is_multi_model(prop_data):
            for letter in ["A","B","C"]:
                for p in prop_data.get(f"model_{letter}", []):
                    if p.get("played"):
                        by_model[letter].append(win_fn(p))
        elif "picks" in prop_data:
            for p in prop_data["picks"]:
                if p.get("played"):
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
    **For each saved day, we store top 10 picks from all 3 models simultaneously.**
    
    When you click "Check Results", actual H+R+RBI and HRs are pulled and each pick is graded.
    
    - **HRR pick wins** = actual H+R+RBI ≥ 1
    - **HR pick wins** = actual HR ≥ 1
    
    The rolling leaderboard accumulates across **all days** — after a week of data, 
    you'll see clearly whether pitcher and home/away factors actually improve win rate.
    """)
