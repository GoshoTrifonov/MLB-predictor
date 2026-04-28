"""
MLB Betting Prediction Dashboard
================================
Streamlit app for game-level home win predictions
using the trained Random Forest model.

To run:
    pip install streamlit pandas scikit-learn joblib numpy
    streamlit run mlb_dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import joblib
from pathlib import Path

# ─────────────────────────────────────────────
# PAGE SETUP
# ─────────────────────────────────────────────
st.set_page_config(page_title="MLB Predictor", page_icon="⚾", layout="wide")

st.title("⚾ MLB Game Predictor")
st.caption("Random Forest model trained on 2021–2023 game logs")

# ─────────────────────────────────────────────
# LOAD MODEL
# ─────────────────────────────────────────────
@st.cache_resource
def load_model():
    model = joblib.load("model_final.pkl")
    features = joblib.load("features_final.pkl")
    return model, features

try:
    model, FEATURES = load_model()
    st.sidebar.success("✅ Model loaded")
except FileNotFoundError:
    st.error("❌ model_final.pkl or features_final.pkl not found. "
             "Place them in the same folder as this script.")
    st.stop()

# ─────────────────────────────────────────────
# SIDEBAR — INPUT MATCHUP
# ─────────────────────────────────────────────
st.sidebar.header("Matchup Setup")

teams = ["NYY","BOS","TBR","TOR","BAL","CLE","CHW","DET","KCR","MIN",
         "HOU","LAA","OAK","SEA","TEX","ATL","MIA","NYM","PHI","WSN",
         "CHC","CIN","MIL","PIT","STL","ARI","COL","LAD","SDP","SFG"]

home_team    = st.sidebar.selectbox("🏠 Home team",    teams, index=0)
visitor_team = st.sidebar.selectbox("✈️  Visitor team", teams, index=1)

st.sidebar.markdown("---")
st.sidebar.subheader("Recent form (last 10 games)")

home_runs_roll10    = st.sidebar.slider("Home avg runs scored",   0.0, 10.0, 4.5, 0.1)
visitor_runs_roll10 = st.sidebar.slider("Visitor avg runs scored",0.0, 10.0, 4.5, 0.1)
home_runs_roll5     = st.sidebar.slider("Home runs (last 5)",     0.0, 10.0, 4.5, 0.1)
visitor_runs_roll5  = st.sidebar.slider("Visitor runs (last 5)",  0.0, 10.0, 4.5, 0.1)
home_win_roll10     = st.sidebar.slider("Home win % at home",     0.0, 1.0, 0.55, 0.01)
visitor_away_win    = st.sidebar.slider("Visitor win % on road",  0.0, 1.0, 0.45, 0.01)
home_allowed        = st.sidebar.slider("Home runs allowed avg",  0.0, 10.0, 4.5, 0.1)
visitor_allowed     = st.sidebar.slider("Visitor runs allowed",   0.0, 10.0, 4.5, 0.1)

st.sidebar.markdown("---")
st.sidebar.subheader("Other factors")

home_rest    = st.sidebar.slider("Home rest days",    0, 7, 1)
visitor_rest = st.sidebar.slider("Visitor rest days", 0, 7, 1)
h2h_home_win = st.sidebar.slider("H2H home win rate", 0.0, 1.0, 0.5, 0.01)

st.sidebar.markdown("---")
st.sidebar.subheader("Starting pitchers")

home_sp_era    = st.sidebar.slider("Home SP runs allowed (last 5)",    0.0, 10.0, 4.0, 0.1)
visitor_sp_era = st.sidebar.slider("Visitor SP runs allowed (last 5)", 0.0, 10.0, 4.0, 0.1)

# ─────────────────────────────────────────────
# BUILD FEATURE VECTOR
# ─────────────────────────────────────────────
input_features = pd.DataFrame([{
    "home_runs_roll10":         home_runs_roll10,
    "visitor_runs_roll10":      visitor_runs_roll10,
    "home_runs_roll5":          home_runs_roll5,
    "visitor_runs_roll5":       visitor_runs_roll5,
    "home_win_roll10":          home_win_roll10,
    "visitor_away_win_roll10":  visitor_away_win,
    "home_allowed_roll10":      home_allowed,
    "visitor_allowed_roll10":   visitor_allowed,
    "home_rest_days":           home_rest,
    "visitor_rest_days":        visitor_rest,
    "h2h_home_win_roll":        h2h_home_win,
    "home_sp_era_roll5":        home_sp_era,
    "visitor_sp_era_roll5":     visitor_sp_era,
}])[FEATURES]

# ─────────────────────────────────────────────
# PREDICT
# ─────────────────────────────────────────────
prob = model.predict_proba(input_features)[0]
home_win_prob   = prob[1]
visitor_win_prob= prob[0]
prediction      = "HOME" if home_win_prob > 0.5 else "VISITOR"
confidence      = max(prob)

# ─────────────────────────────────────────────
# DISPLAY
# ─────────────────────────────────────────────
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(f"🏠 {home_team} Win Probability", f"{home_win_prob:.1%}")
with col2:
    st.metric(f"✈️ {visitor_team} Win Probability", f"{visitor_win_prob:.1%}")
with col3:
    st.metric("🎯 Confidence", f"{confidence:.1%}")

st.markdown("---")

# Bet recommendation
st.subheader("Bet Recommendation")
if confidence < 0.55:
    st.warning("⚠️ Low confidence — skip this game")
elif confidence < 0.60:
    st.info(f"📊 Lean **{prediction}** ({home_team if prediction=='HOME' else visitor_team})")
else:
    st.success(f"✅ Strong pick: **{prediction}** ({home_team if prediction=='HOME' else visitor_team})")

# Implied odds calculation
st.markdown("### Fair Odds (American)")
def prob_to_odds(p):
    if p >= 0.5:
        return f"-{int(p / (1 - p) * 100)}"
    else:
        return f"+{int((1 - p) / p * 100)}"

c1, c2 = st.columns(2)
with c1:
    st.write(f"**{home_team}** fair odds: `{prob_to_odds(home_win_prob)}`")
with c2:
    st.write(f"**{visitor_team}** fair odds: `{prob_to_odds(visitor_win_prob)}`")

st.caption("If sportsbook odds are *better* than fair odds, there's value in the bet.")

# ─────────────────────────────────────────────
# FEATURE IMPORTANCE
# ─────────────────────────────────────────────
st.markdown("---")
st.subheader("Model Feature Importance")

importance = pd.DataFrame({
    "feature": FEATURES,
    "importance": model.feature_importances_
}).sort_values("importance", ascending=True)

st.bar_chart(importance.set_index("feature"))

# ─────────────────────────────────────────────
# DEBUG
# ─────────────────────────────────────────────
with st.expander("🔧 Debug — input features"):
    st.dataframe(input_features.T)
