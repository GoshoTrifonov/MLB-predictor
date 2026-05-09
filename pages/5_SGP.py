"""
SGP (Same Game Parlay) Builder
Finds today's games with strong overlap of HRR + K picks.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from picks_storage import load_picks_history

TORONTO_TZ = ZoneInfo("America/Toronto")

st.set_page_config(page_title="SGP Builder", page_icon="🎲", layout="wide")
st.title("🎲 SGP Builder — HRR × K")
st.caption(f"Find games with strong HRR + K picks • {datetime.now(TORONTO_TZ).strftime('%A, %B %d, %Y')}")

history, _ = load_picks_history()
today = datetime.now(TORONTO_TZ).strftime("%Y-%m-%d")
today_data = history.get(today, {})

if not today_data:
    st.warning("⚠️ No picks saved for today yet. Save HRR and K picks first, then come back!")
    st.stop()

# ── Pull saved picks ─────────────────────────────────────────────────────────
hrr_data = today_data.get("hrr",    {}).get("picks", {})
k_data   = today_data.get("k_over", {}).get("picks", {})

if not isinstance(hrr_data, dict) or not isinstance(k_data, dict):
    st.warning("Need both HRR and K picks saved in 3-model format. Save fresh picks today.")
    st.stop()

hrr_models = sorted([k.split("_",1)[1] for k in hrr_data.keys() if k.startswith("model_")])
k_models   = sorted([k.split("_",1)[1] for k in k_data.keys() if k.startswith("model_")])

if not hrr_models or not k_models:
    st.warning("Need both HRR and K picks saved today.")
    st.stop()

# ── Pick which models to use ─────────────────────────────────────────────────
c1, c2 = st.columns(2)
with c1:
    hrr_choice = st.radio("HRR model:", hrr_models, 
                           index=len(hrr_models)-1, horizontal=True)
with c2:
    k_choice = st.radio("K model:", k_models,
                         index=len(k_models)-1, horizontal=True)

hrr_picks = hrr_data.get(f"model_{hrr_choice}", [])
k_picks   = k_data.get(f"model_{k_choice}", [])

# ── Group picks by game ──────────────────────────────────────────────────────
def game_key(pick):
    team = pick.get("Team", "?")
    opp  = pick.get("Opp Team", "?")
    return tuple(sorted([team, opp]))

games = {}
for p in hrr_picks:
    gk = game_key(p)
    games.setdefault(gk, {"hrr": [], "k": []})
    games[gk]["hrr"].append(p)

for p in k_picks:
    gk = game_key(p)
    games.setdefault(gk, {"hrr": [], "k": []})
    games[gk]["k"].append(p)

# ── Filter to games with both legs ───────────────────────────────────────────
sgp_games = {gk: legs for gk, legs in games.items() if legs["hrr"] and legs["k"]}

st.markdown("---")

if not sgp_games:
    st.info("No games today have BOTH an HRR pick AND a K pick. Need overlap to build SGP. "
            "Try saving with more lenient filters, or check back later.")
    st.stop()

def combined_score(legs):
    best_hrr = max(legs["hrr"], key=lambda p: p.get("Score", 0))
    best_k   = max(legs["k"],   key=lambda p: p.get("Score", 0))
    return best_hrr.get("Score", 0) + best_k.get("Score", 0)

sorted_games = sorted(sgp_games.items(), key=lambda x: combined_score(x[1]), reverse=True)

st.success(f"🎯 Found **{len(sorted_games)}** SGP candidate game(s)")

for gk, legs in sorted_games:
    team1, team2 = gk
    best_hrr = max(legs["hrr"], key=lambda p: p.get("Score", 0))
    best_k   = max(legs["k"],   key=lambda p: p.get("Score", 0))
    combined = combined_score(legs)

    with st.container(border=True):
        st.markdown(f"### {team1} vs {team2}  ·  Combined: **{combined:.1f}**")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**🎯 HRR Leg (Over 0.5 H+R+RBI)**")
            st.markdown(f"**{best_hrr.get('Player', '?')}** ({best_hrr.get('Team', '?')}) {best_hrr.get('H/A', '')}")
            st.caption(f"vs {best_hrr.get('Opp Pitcher', '?')}")
            st.metric("Score", f"{best_hrr.get('Score', '—')}")

        with c2:
            st.markdown("**🎰 K Leg (Over 0.5 K)**")
            st.markdown(f"**{best_k.get('Player', '?')}** ({best_k.get('Team', '?')}) {best_k.get('H/A', '')}")
            st.caption(f"vs {best_k.get('Opp Pitcher', '?')}")
            st.metric("Score", f"{best_k.get('Score', '—')}")

with st.expander("ℹ️ How it works"):
    st.markdown("""
    **Reads today's saved picks** and finds games where we have BOTH:
    - A strong **HRR pick** (batter likely to hit/score/RBI)
    - A strong **K pick** (batter likely to strike out — different player, often the opposing team)
    
    These games are good candidates for a **2-leg Same Game Parlay**.
    
    **Workflow:**
    1. Save HRR picks (HRR Picks page → 💾)
    2. Save K picks (K Picks page → 💾)
    3. Come here to see the overlap, ranked by combined leg strength.
    
    💡 **Tip:** SGPs are correlated — high-scoring games tend to have more HRR AND more strikeouts. 
    The "Combined Score" gives you a rough ranking of which games look best.
    
    🔜 **Coming next:** add expected game total runs as a 3rd leg, plus HR Picks integration.
    """)
