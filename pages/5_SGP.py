"""
SGP (Same Game Parlay) Builder — v2
Multi-leg view: all HRR + K + HR picks per game with smart notes.
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
st.title("🎲 SGP Builder — Multi-Leg")
st.caption(f"All HRR + K + HR overlaps per game • {datetime.now(TORONTO_TZ).strftime('%A, %B %d, %Y')}")

history, _ = load_picks_history()
today = datetime.now(TORONTO_TZ).strftime("%Y-%m-%d")
today_data = history.get(today, {})

if not today_data:
    st.warning("⚠️ No picks saved for today yet. Save HRR / K / HR picks first.")
    st.stop()

# ── Pull saved picks ─────────────────────────────────────────────────────────
def get_picks_for(prop_type):
    data = today_data.get(prop_type, {}).get("picks", {})
    if not isinstance(data, dict):
        return {}, []
    models = sorted([k.split("_",1)[1] for k in data.keys() if k.startswith("model_")])
    return data, models

hrr_data, hrr_models = get_picks_for("hrr")
k_data,   k_models   = get_picks_for("k_over")
hr_data,  hr_models  = get_picks_for("hr")

# Status row
status = []
status.append(f"✅ HRR ({','.join(hrr_models)})" if hrr_models else "❌ HRR")
status.append(f"✅ K ({','.join(k_models)})"     if k_models   else "❌ K")
status.append(f"✅ HR ({','.join(hr_models)})"   if hr_models  else "❌ HR")
st.caption("Saved today: " + " · ".join(status))

if not (hrr_models or k_models or hr_models):
    st.warning("Save at least 2 prop types today to see SGP candidates.")
    st.stop()

# ── Model selectors ──────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
with c1:
    hrr_choice = st.radio("HRR model", hrr_models, index=len(hrr_models)-1, horizontal=True) if hrr_models else None
with c2:
    k_choice = st.radio("K model", k_models, index=len(k_models)-1, horizontal=True) if k_models else None
with c3:
    hr_choice = st.radio("HR model", hr_models, index=len(hr_models)-1, horizontal=True) if hr_models else None

hrr_picks = hrr_data.get(f"model_{hrr_choice}", []) if hrr_choice else []
k_picks   = k_data.get(f"model_{k_choice}", [])    if k_choice   else []
hr_picks  = hr_data.get(f"model_{hr_choice}", [])  if hr_choice  else []

# ── Group picks by game ──────────────────────────────────────────────────────
def game_key(pick):
    return tuple(sorted([pick.get("Team", "?"), pick.get("Opp Team", "?")]))

games = {}
for p in hrr_picks:
    gk = game_key(p); games.setdefault(gk, {"hrr": [], "k": [], "hr": []})["hrr"].append(p)
for p in k_picks:
    gk = game_key(p); games.setdefault(gk, {"hrr": [], "k": [], "hr": []})["k"].append(p)
for p in hr_picks:
    gk = game_key(p); games.setdefault(gk, {"hrr": [], "k": [], "hr": []})["hr"].append(p)

# Filter: games with 2+ prop types
multi_leg_games = {gk: legs for gk, legs in games.items() 
                   if sum(1 for t in ["hrr","k","hr"] if legs[t]) >= 2}

st.markdown("---")

if not multi_leg_games:
    st.info("No games today have 2+ prop types overlapping. Save more picks!")
    st.stop()

# ── Helpers ──────────────────────────────────────────────────────────────────
def safe_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None

def make_notes(pick, prop_type):
    notes = []
    momentum = safe_float(pick.get("Momentum"))
    pdf = safe_float(pick.get("PDF"))
    loc = safe_float(pick.get("Loc Factor"))

    if prop_type == "hrr":
        if momentum is not None:
            if momentum >= 1.10:  notes.append("🔥 hot")
            elif momentum <= 0.90: notes.append("🥶 cold")
        if pdf is not None:
            if pdf >= 1.20:   notes.append("🎯 weak pitcher")
            elif pdf <= 0.80: notes.append("🛡️ ace")
        if loc is not None:
            if loc >= 1.15:   notes.append("💪 thrives here")
            elif loc <= 0.85: notes.append("⚠️ struggles here")
    elif prop_type == "k":
        if pdf is not None:
            if pdf >= 1.15:   notes.append("🎯 high-K pitcher")
            elif pdf <= 0.85: notes.append("🛡️ contact pitcher")
    elif prop_type == "hr":
        prob = safe_float(pick.get("HR Prob %"))
        park = safe_float(pick.get("Park Factor"))
        pitf = safe_float(pick.get("Pit Factor"))
        if prob is not None and prob >= 12: notes.append("💥 high HR%")
        if park is not None and park >= 1.15: notes.append("🏟️ HR park")
        if pitf is not None and pitf >= 1.20: notes.append("🎯 HR-prone P")

    return " ".join(notes) if notes else "—"

PROP_LABEL = {"hrr": "🎯 HRR", "k": "🎰 K", "hr": "💥 HR"}

# Sort games by total leg strength
def total_score(legs):
    s = 0
    for typ in ["hrr", "k"]:
        for p in legs[typ]:
            s += safe_float(p.get("Score")) or 0
    for p in legs["hr"]:
        s += (safe_float(p.get("HR Prob %")) or 0) * 5
    return s

sorted_games = sorted(multi_leg_games.items(), key=lambda x: total_score(x[1]), reverse=True)

st.success(f"🎯 Found **{len(sorted_games)}** SGP candidate game(s)")

# ── Display each game ────────────────────────────────────────────────────────
for gk, legs in sorted_games:
    team1, team2 = gk
    n_legs = sum(len(legs[t]) for t in ["hrr","k","hr"])

    with st.container(border=True):
        st.markdown(f"### {team1} vs {team2}  ·  {n_legs} available legs")

        rows = []
        for typ in ["hrr", "k", "hr"]:
            for p in legs[typ]:
                score_display = f"{p.get('HR Prob %', '—')}%" if typ == "hr" else f"{p.get('Score', '—')}"
                rows.append({
                    "Prop":        PROP_LABEL[typ],
                    "Player":      p.get("Player", "?"),
                    "Team":        p.get("Team", "?"),
                    "H/A":         p.get("H/A", ""),
                    "Opp Pitcher": p.get("Opp Pitcher", "?"),
                    "Score":       score_display,
                    "Notes":       make_notes(p, typ),
                })

        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

# ── Strategy notes ───────────────────────────────────────────────────────────
with st.expander("⚠️ SGP strategy — read before going greedy!"):
    st.markdown("""
    **The math truth bomb:**
    
    - 2 legs at 60% each = **36%** win rate
    - 3 legs = **22%**
    - 4 legs = **13%**
    
    Books happily pay 6-1 on a 4-leg SGP because the math is on their side.
    
    **Smart construction tips:**
    
    🟢 **Best combo:** HRR from Team A + K from Team B (opposite sides)
    - Same dynamic helps both: high-scoring game → Team A hits AND its pitcher Ks Team B
    
    🔴 **Avoid:** Multiple HRR picks from the same lineup
    - One bad pitching day sinks them all together
    
    🟡 **Same-team HRR + K:** Anti-correlated — if hitters connect, they aren't striking out
    
    **Notes legend:**
    - 🔥 hot / 🥶 cold — recent form (Momentum)
    - 🎯 favorable matchup / 🛡️ tough matchup
    - 💪 thrives here / ⚠️ struggles here — location split
    - 💥 high HR% / 🏟️ HR-friendly park / 🎯 HR-prone pitcher
    """)
