"""
Results Tracker — see how yesterday's (and prior) picks actually performed.
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
st.title("📊 Results Tracker")
st.caption("See how saved picks actually performed")

# ── Load history ──
history, sha = load_picks_history()

if not history:
    st.info("No picks saved yet. Go to **HRR Picks** or **HR Picks** and click 'Save Today's Picks' to start tracking!")
    st.stop()

dates_sorted = sorted(history.keys(), reverse=True)
st.sidebar.markdown(f"**Tracked days:** {len(dates_sorted)}")

# ── Date picker ──
selected_date = st.selectbox("Pick a date to review", dates_sorted)

# ── Verify button ──
day_data = history[selected_date]
all_verified = all(v.get("verified") for v in day_data.values()) if day_data else False

c1, c2 = st.columns([3,1])
with c1:
    st.subheader(f"Picks from {selected_date}")
with c2:
    if not all_verified:
        if st.button("🔍 Check Results"):
            with st.spinner("Pulling actual results..."):
                for prop_type, prop_data in day_data.items():
                    for pick in prop_data["picks"]:
                        results = get_player_results(pick["Player"], selected_date)
                        if results:
                            pick["actual_HRR"] = results.get("HRR", 0)
                            pick["actual_HR"]  = results.get("HR", 0)
                            pick["played"]     = results.get("played", False)
                        time.sleep(0.2)
                    prop_data["verified"] = True
                save_picks_history(history, sha)
            st.success("Results updated!")
            st.rerun()
    else:
        st.success("✅ Verified")

# ── Display picks ──
for prop_type, prop_data in day_data.items():
    label = "🎯 H+R+RBI Picks" if prop_type == "hrr" else "💥 HR Picks"
    st.markdown(f"### {label}")
    
    picks = prop_data["picks"]
    df = pd.DataFrame(picks)
    
    if prop_data.get("verified"):
        # Show actual results
        if prop_type == "hrr":
            # Win condition: actual H+R+RBI >= 2 (typical 1.5 line)
            df["Win?"] = df.apply(
                lambda r: "—" if not r.get("played") 
                else ("✅" if r.get("actual_HRR", 0) >= 2 else "❌"),
                axis=1
            )
            cols_show = ["Player","Team","Opp Pitcher","Score","actual_HRR","Win?"]
        else:  # HR picks
            df["Win?"] = df.apply(
                lambda r: "—" if not r.get("played")
                else ("✅" if r.get("actual_HR", 0) >= 1 else "❌"),
                axis=1
            )
            cols_show = ["Player","Team","Opp Pitcher","HR Prob %","actual_HR","Win?"]
        
        cols_show = [c for c in cols_show if c in df.columns]
        st.dataframe(df[cols_show], hide_index=True, use_container_width=True)
        
        # Summary
        played = df["Win?"] != "—"
        wins = (df["Win?"] == "✅").sum()
        total = played.sum()
        if total > 0:
            st.metric(f"{label} Win Rate", f"{wins}/{total} ({wins/total*100:.1f}%)")
    else:
        cols_show = [c for c in df.columns if c in [
            "Player","Team","Opp Pitcher","Score","HR Prob %","Per Game"]]
        st.dataframe(df[cols_show], hide_index=True, use_container_width=True)

# ── ROLLING STATS ──
st.markdown("---")
st.subheader("📈 Rolling Performance")

all_hrr_results = []
all_hr_results = []
for date, day_data in history.items():
    if "hrr" in day_data and day_data["hrr"].get("verified"):
        for p in day_data["hrr"]["picks"]:
            if p.get("played"):
                all_hrr_results.append({
                    "date": date,
                    "player": p["Player"],
                    "won": p.get("actual_HRR", 0) >= 2
                })
    if "hr" in day_data and day_data["hr"].get("verified"):
        for p in day_data["hr"]["picks"]:
            if p.get("played"):
                all_hr_results.append({
                    "date": date,
                    "player": p["Player"],
                    "won": p.get("actual_HR", 0) >= 1
                })

c1, c2 = st.columns(2)
with c1:
    st.markdown("**🎯 H+R+RBI Picks Overall**")
    if all_hrr_results:
        wr = sum(r["won"] for r in all_hrr_results) / len(all_hrr_results) * 100
        st.metric("Win Rate", f"{wr:.1f}%", f"{len(all_hrr_results)} picks tracked")
    else:
        st.info("No verified HRR picks yet")

with c2:
    st.markdown("**💥 HR Picks Overall**")
    if all_hr_results:
        wr = sum(r["won"] for r in all_hr_results) / len(all_hr_results) * 100
        st.metric("HR Hit Rate", f"{wr:.1f}%", f"{len(all_hr_results)} picks tracked")
    else:
        st.info("No verified HR picks yet")

with st.expander("ℹ️ How tracking works"):
    st.markdown("""
    - **HRR pick wins** if the player's actual H+R+RBI is **2 or more** (typical 1.5 line)
    - **HR pick wins** if the player hits **1+ home run**
    - Click **Check Results** the day after picks are saved to verify
    - "—" means the player didn't play (rest day, sub, etc.)
    
    Picks are saved to your GitHub repo as `picks_history.json`.
    """)
