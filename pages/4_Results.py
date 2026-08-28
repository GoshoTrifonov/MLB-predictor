"""
Results Tracker — Full model comparison
Handles: hrr (1+), hrr_2plus (2+), hr, k_over, moneyline, convergence
"""

import streamlit as st
import pandas as pd
import time
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from picks_storage import load_picks_history, save_picks_history, get_player_results

TORONTO_TZ = ZoneInfo("America/Toronto")

st.set_page_config(page_title="Results Tracker", page_icon="📊", layout="wide")
st.title("📊 Results Tracker — Model Comparison")
st.caption("Compare how each model's picks actually performed")

history, sha = load_picks_history()

if not history:
    st.info("No picks saved yet. Save picks on **HRR Picks**, **HR Picks**, **K Picks**, or **Home** first!")
    st.stop()

dates_sorted = sorted(history.keys(), reverse=True)
st.sidebar.markdown(f"**Tracked days:** {len(dates_sorted)}")

selected_date = st.selectbox("Pick a date to review", dates_sorted)
day_data = history[selected_date]

# ─────────────────────────────────────────────
# HELPERS — pick extraction
# ─────────────────────────────────────────────
def get_models_dict(prop_data):
    """Returns {letter: [picks]} if multi-model save format."""
    if not isinstance(prop_data, dict):
        return None
    picks_field = prop_data.get("picks")
    if isinstance(picks_field, dict):
        result = {}
        for k, v in picks_field.items():
            if k.startswith("model_") and isinstance(v, list):
                result[k.split("_", 1)[1]] = v
        return result if result else None
    return None

def get_legacy_picks(prop_data):
    """Returns flat list if old/simple save format."""
    if not isinstance(prop_data, dict):
        return None
    picks_field = prop_data.get("picks")
    if isinstance(picks_field, list):
        return picks_field
    return None

def all_pick_lists(prop_data):
    models = get_models_dict(prop_data)
    if models:
        for lst in models.values():
            yield lst
    legacy = get_legacy_picks(prop_data)
    if legacy:
        yield legacy

def is_verified(day_data):
    for prop_data in day_data.values():
        for pick_list in all_pick_lists(prop_data):
            for p in pick_list:
                if isinstance(p, dict) and p.get("verified_date") == selected_date:
                    return True
    return False

verified = is_verified(day_data)

# ─────────────────────────────────────────────
# WIN FUNCTIONS
# ─────────────────────────────────────────────
def hrr1_won(p):  return p.get("actual_HRR", 0) >= 1
def hrr2_won(p):  return p.get("actual_HRR", 0) >= 2
def hr_won(p):    return p.get("actual_HR", 0)  >= 1
def k_won(p):     return p.get("actual_K", 0)   >= 1

def model_summary(picks, win_fn):
    played = [p for p in picks if isinstance(p, dict) and p.get("played")]
    wins   = sum(1 for p in played if win_fn(p))
    return wins, len(played)

# ─────────────────────────────────────────────
# VERIFY BUTTON (player props)
# ─────────────────────────────────────────────
c1, c2 = st.columns([3, 1])
with c1:
    st.subheader(f"Picks from {selected_date}")
with c2:
    if not verified:
        if st.button("🔍 Check Results"):
            with st.spinner("Pulling actual results..."):
                unique_players = set()
                for prop_type, prop_data in day_data.items():
                    # only player-prop types need stat lookup
                    if prop_type in ("moneyline", "convergence"):
                        continue
                    for pick_list in all_pick_lists(prop_data):
                        for p in pick_list:
                            if isinstance(p, dict) and "Player" in p:
                                unique_players.add(p["Player"])

                results_map = {}
                for name in unique_players:
                    results_map[name] = get_player_results(name, selected_date)
                    time.sleep(0.15)

                for prop_type, prop_data in day_data.items():
                    if prop_type in ("moneyline", "convergence"):
                        continue
                    for pick_list in all_pick_lists(prop_data):
                        for p in pick_list:
                            if not isinstance(p, dict):
                                continue
                            r = results_map.get(p.get("Player")) or {}
                            p["actual_HRR"]    = r.get("HRR", 0)
                            p["actual_HR"]     = r.get("HR", 0)
                            p["actual_K"]      = r.get("K", 0)
                            p["played"]        = r.get("played", False)
                            p["verified_date"] = selected_date
                save_picks_history(history, sha)
            st.success("Results updated!")
            st.rerun()
    else:
        st.success("✅ Verified")

# ─────────────────────────────────────────────
# DISPLAY HELPER — multi-model table
# ─────────────────────────────────────────────
def show_prop_section(label, prop_type, win_fn, actual_col, threshold_note):
    prop_data = day_data.get(prop_type)
    if not prop_data:
        return
    st.markdown(f"### {label}")
    if threshold_note:
        st.caption(threshold_note)
    models = get_models_dict(prop_data)
    if models:
        model_letters = sorted(models.keys())
        cols = st.columns(len(model_letters))
        for i, letter in enumerate(model_letters):
            picks = models.get(letter, [])
            wins, total = model_summary(picks, win_fn) if verified else (0, 0)
            with cols[i]:
                if verified and total > 0:
                    st.metric(f"Model {letter}", f"{wins}/{total}", f"{wins/total*100:.0f}%")
                else:
                    st.metric(f"Model {letter}", "—", f"{len(picks)} picks")

        chosen = st.radio("Show table for", model_letters, horizontal=True, key=f"{prop_type}_radio")
        picks  = models.get(chosen, [])
        df     = pd.DataFrame(picks)
        if verified and "played" in df.columns:
            df["Win?"] = df.apply(
                lambda r: "—" if not r.get("played")
                else ("✅" if win_fn(r) else "❌"), axis=1
            )
            show_cols = [c for c in ["Player","Team","Opp Pitcher", actual_col, "Win?"] if c in df.columns]
        else:
            show_cols = [c for c in df.columns if c in [
                "Player","Team","H/A","Opp Team","Opp Pitcher","Score","Per Game","2+ Rate"
            ]]
        if not df.empty:
            st.dataframe(df[show_cols], hide_index=True, use_container_width=True)
    else:
        picks = get_legacy_picks(prop_data) or []
        df    = pd.DataFrame(picks)
        if not df.empty:
            if verified and "played" in df.columns:
                df["Win?"] = df.apply(
                    lambda r: "—" if not r.get("played")
                    else ("✅" if win_fn(r) else "❌"), axis=1
                )
                show_cols = [c for c in ["Player","Team","Opp Pitcher", actual_col, "Win?"] if c in df.columns]
            else:
                show_cols = [c for c in df.columns if c in [
                    "Player","Team","Opp Pitcher","Score","Per Game"
                ]]
            st.dataframe(df[show_cols], hide_index=True, use_container_width=True)

# ─────────────────────────────────────────────
# PLAYER PROP SECTIONS
# ─────────────────────────────────────────────
show_prop_section(
    "🎯 H+R+RBI Picks — Over 0.5 (≥1)",
    "hrr", hrr1_won, "actual_HRR",
    "Win = player records at least 1 combined H+R+RBI"
)

show_prop_section(
    "🎯 H+R+RBI Picks — Over 1.5 (≥2)",
    "hrr_2plus", hrr2_won, "actual_HRR",
    "Win = player records at least 2 combined H+R+RBI • Harder line, higher payout"
)

# Side-by-side HRR 1+ vs 2+ comparison if both exist
if "hrr" in day_data and "hrr_2plus" in day_data and verified:
    st.markdown("#### 📊 HRR 1+ vs 2+ — same players, both thresholds")
    st.caption("Lets you see which players who hit 1+ also cleared 2+")
    # collect all players from both saves using model D (or B if D missing)
    def best_model_picks(prop_type):
        pd_ = day_data.get(prop_type)
        if not pd_: return []
        m = get_models_dict(pd_)
        if m:
            for letter in ["D", "C", "B"]:
                if letter in m: return m[letter]
        return get_legacy_picks(pd_) or []

    picks1 = best_model_picks("hrr")
    picks2 = best_model_picks("hrr_2plus")
    name_to_hrr = {p["Player"]: p.get("actual_HRR", 0)
                   for p in picks1 if isinstance(p, dict) and "Player" in p}
    compare_rows = []
    for p in picks2:
        if not isinstance(p, dict) or "Player" not in p: continue
        hrr_actual = name_to_hrr.get(p["Player"], p.get("actual_HRR", 0))
        compare_rows.append({
            "Player":    p["Player"],
            "Team":      p.get("Team",""),
            "Opp":       p.get("Opp Team",""),
            "Actual HRR": hrr_actual,
            "1+ ✓":      "✅" if hrr_actual >= 1 else "❌",
            "2+ ✓":      "✅" if hrr_actual >= 2 else "❌",
        })
    if compare_rows:
        st.dataframe(pd.DataFrame(compare_rows), hide_index=True, use_container_width=True)

show_prop_section(
    "💥 HR Picks",
    "hr", hr_won, "actual_HR",
    "Win = player hits at least 1 home run"
)

show_prop_section(
    "🎰 K Over 0.5 Picks",
    "k_over", k_won, "actual_K",
    "Win = batter strikes out at least once"
)

# ─────────────────────────────────────────────
# MONEYLINE SECTION
# ─────────────────────────────────────────────
@st.cache_data(ttl=900)
def get_finished_games(date_str):
    url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {"sportId": 1, "date": date_str, "hydrate": "linescore"}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200: return []
        out = []
        for d in r.json().get("dates", []):
            for g in d.get("games", []):
                if g.get("status", {}).get("abstractGameState") != "Final": continue
                hm = g["teams"]["home"]
                aw = g["teams"]["away"]
                out.append({
                    "home": hm["team"]["name"],
                    "away": aw["team"]["name"],
                    "home_score": hm.get("score", 0),
                    "away_score": aw.get("score", 0),
                })
        return out
    except Exception:
        return []

def find_actual_result(matchup_str, date_str):
    if " @ " not in matchup_str: return None
    away_part, home_part = matchup_str.split(" @ ")
    for g in get_finished_games(date_str):
        h_match = home_part.lower() in g["home"].lower() or g["home"].lower() in home_part.lower()
        a_match = away_part.lower() in g["away"].lower() or g["away"].lower() in away_part.lower()
        if h_match and a_match:
            winner = "Home" if g["home_score"] > g["away_score"] else "Away"
            return {
                "winner": winner,
                "total":  g["home_score"] + g["away_score"],
                "score":  f"{g['away_score']}-{g['home_score']}",
            }
    return None

st.markdown("---")
st.markdown("## ⚾ Moneyline Tracker")
st.caption("Value bets from the Home page — settled automatically from MLB Stats API")

ml_rows = []
for date_key in sorted(history.keys(), reverse=True):
    ml_data = history[date_key].get("moneyline")
    if not ml_data: continue
    picks_list = ml_data.get("picks", []) if isinstance(ml_data, dict) else ml_data
    for pick in picks_list:
        if not isinstance(pick, dict): continue

        # Support both old format (bet string only) and new format (side field)
        bet_str = pick.get("bet", "")
        side    = pick.get("side", "")
        if not side:
            # derive from bet string for legacy picks
            if "Home" in bet_str: side = "Home"
            elif "Away" in bet_str: side = "Away"

        actual = find_actual_result(pick.get("matchup", ""), date_key)
        row = {
            "Date":          date_key,
            "Matchup":       pick.get("matchup", "—"),
            "Pitchers":      pick.get("pitchers", "—"),
            "Bet":           side or bet_str,
            "Book Home %":   f"{pick.get('book_home_prob', pick.get('_book_home_prob', ''))*100:.0f}%"
                             if isinstance(pick.get("book_home_prob", pick.get("_book_home_prob")), float)
                             else "—",
            "Model Home %":  f"{pick.get('model_home_prob', pick.get('_model_home_prob', ''))*100:.0f}%"
                             if isinstance(pick.get("model_home_prob", pick.get("_model_home_prob")), float)
                             else "—",
            "K Gap":         f"{pick.get('k_gap'):+.1f}" if isinstance(pick.get("k_gap"), (int,float)) else "—",
        }
        if actual:
            row["Score"]     = actual["score"]
            row["ML Result"] = ("✅ Win"  if actual["winner"] == side else "❌ Loss") if side else "➖"
            try:
                exp = float(pick.get("exp_runs", 0) or 0)
                row["Exp Runs"] = f"{exp:.1f}"
                row["Run Diff"] = f"±{abs(exp - actual['total']):.1f}"
            except (ValueError, TypeError):
                row["Exp Runs"] = "—"
                row["Run Diff"] = "—"
        else:
            row["Score"]     = "—"
            row["ML Result"] = "⏳ Pending"
            row["Exp Runs"]  = pick.get("exp_runs", "—")
            row["Run Diff"]  = "—"
        ml_rows.append(row)

if not ml_rows:
    st.info("No moneyline picks saved yet. Go to **Home** and click '💾 Save Today's Picks'.")
else:
    ml_df = pd.DataFrame(ml_rows)
    settled = ml_df[ml_df["ML Result"].isin(["✅ Win","❌ Loss"])]
    wins    = (settled["ML Result"] == "✅ Win").sum()
    total_b = len(settled)
    win_pct = round(wins/total_b*100, 1) if total_b else 0

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total Picks",  len(ml_df))
    c2.metric("Settled",      total_b)
    c3.metric("ML Win Rate",  f"{win_pct}%")
    c4.metric("Pending",      (ml_df["ML Result"]=="⏳ Pending").sum())

    show_cols = [c for c in ["Date","Matchup","Pitchers","Bet","Book Home %",
                              "Model Home %","K Gap","Score","Exp Runs",
                              "Run Diff","ML Result"] if c in ml_df.columns]
    st.dataframe(ml_df[show_cols], hide_index=True, use_container_width=True)

# ─────────────────────────────────────────────
# CONVERGENCE SECTION
# ─────────────────────────────────────────────
st.markdown("---")
st.markdown("## 🔥 Convergence Picks Tracker")
st.caption("K-rate + moneyline signal picks from the Convergence page")

conv_rows = []
for date_key in sorted(history.keys(), reverse=True):
    conv_data = history[date_key].get("convergence")
    if not conv_data: continue
    picks_list = conv_data.get("picks", []) if isinstance(conv_data, dict) else conv_data
    for pick in picks_list:
        if not isinstance(pick, dict): continue
        bet_team = pick.get("bet_team", pick.get("favoured", "—"))
        actual   = find_actual_result(pick.get("matchup", ""), date_key)
        row = {
            "Date":       date_key,
            "Matchup":    pick.get("matchup", "—"),
            "Signal":     pick.get("signal", "—"),
            "Bet Team":   bet_team,
            "Home SP":    pick.get("home_sp", "—"),
            "Away SP":    pick.get("away_sp", "—"),
            "Home K9":    f"{pick['home_k9']:.1f}" if isinstance(pick.get("home_k9"), float) else "—",
            "Away K9":    f"{pick['away_k9']:.1f}" if isinstance(pick.get("away_k9"), float) else "—",
            "Home P(K≥5)":f"{pick['home_pk']*100:.0f}%" if isinstance(pick.get("home_pk"), float) else "—",
            "Away P(K≥5)":f"{pick['away_pk']*100:.0f}%" if isinstance(pick.get("away_pk"), float) else "—",
            "K Edge":     f"{pick['k_edge']*100:+.0f}%" if isinstance(pick.get("k_edge"), float) else "—",
            "ML Edge":    f"{pick['ml_edge']*100:+.0f}%" if isinstance(pick.get("ml_edge"), float) else "—",
        }
        if actual:
            row["Score"] = actual["score"]
            # determine whether the bet team was home or away
            if " @ " in pick.get("matchup",""):
                away_name, home_name = pick["matchup"].split(" @ ")
                if bet_team and bet_team.lower() in home_name.lower():
                    bet_side = "Home"
                elif bet_team and bet_team.lower() in away_name.lower():
                    bet_side = "Away"
                else:
                    bet_side = pick.get("favoured","")
            else:
                bet_side = pick.get("favoured","")
            row["Result"] = ("✅ Win" if actual["winner"] == bet_side else "❌ Loss") \
                            if bet_side in ("Home","Away") else "❓"
        else:
            row["Score"]  = "—"
            row["Result"] = "⏳ Pending"
        conv_rows.append(row)

if not conv_rows:
    st.info("No convergence picks saved yet. Go to the **K Convergence** page and save picks.")
else:
    conv_df   = pd.DataFrame(conv_rows)
    c_settled = conv_df[conv_df["Result"].isin(["✅ Win","❌ Loss"])]
    c_wins    = (c_settled["Result"] == "✅ Win").sum()
    c_total   = len(c_settled)
    c_pct     = round(c_wins/c_total*100, 1) if c_total else 0

    # Strong vs Lean breakdown
    strong = c_settled[c_settled["Signal"].str.contains("STRONG", na=False)]
    lean   = c_settled[c_settled["Signal"].str.contains("LEAN",   na=False)]
    s_pct  = round((strong["Result"]=="✅ Win").sum()/len(strong)*100,1) if len(strong) else 0
    l_pct  = round((lean["Result"]  =="✅ Win").sum()/len(lean)*100,  1) if len(lean)   else 0

    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Total Picks",     len(conv_df))
    c2.metric("Settled",         c_total)
    c3.metric("Overall Win %",   f"{c_pct}%")
    c4.metric("🔥 Strong Win %", f"{s_pct}%", f"{len(strong)} bets")
    c5.metric("✅ Lean Win %",   f"{l_pct}%", f"{len(lean)} bets")

    show_cols = [c for c in ["Date","Matchup","Signal","Bet Team","Home SP","Away SP",
                              "Home K9","Away K9","Home P(K≥5)","Away P(K≥5)",
                              "K Edge","ML Edge","Score","Result"] if c in conv_df.columns]
    st.dataframe(conv_df[show_cols], hide_index=True, use_container_width=True)

    if c_total >= 5:
        st.markdown("#### 🔥 vs ✅ breakdown tells you whether to tighten thresholds")
        st.caption("If Strong win % is materially above Lean, increase the K-gap threshold in the Convergence sidebar.")

# ─────────────────────────────────────────────
# ROLLING LEADERBOARD
# ─────────────────────────────────────────────
st.markdown("---")
st.subheader("📈 Rolling Performance (All Tracked Days)")

def aggregate(prop_type, win_fn):
    by_model = {}
    for date, day in history.items():
        prop_data = day.get(prop_type)
        if not prop_data: continue
        models = get_models_dict(prop_data)
        if models:
            for letter, picks in models.items():
                by_model.setdefault(letter, [])
                for p in picks:
                    if isinstance(p, dict) and p.get("played"):
                        by_model[letter].append(win_fn(p))
        else:
            legacy = get_legacy_picks(prop_data) or []
            by_model.setdefault("legacy", [])
            for p in legacy:
                if isinstance(p, dict) and p.get("played"):
                    by_model["legacy"].append(win_fn(p))
    return by_model

def render_leaderboard(col, label, prop_type, win_fn):
    with col:
        st.markdown(f"**{label}**")
        agg = aggregate(prop_type, win_fn)
        if not agg:
            st.caption("No data yet")
            return
        for letter in sorted(agg.keys()):
            results = agg[letter]
            if results:
                wr = sum(results)/len(results)*100
                st.metric(f"Model {letter}", f"{wr:.1f}%", f"{sum(results)}/{len(results)}")
            else:
                st.metric(f"Model {letter}", "—")

c1,c2,c3,c4,c5 = st.columns(5)
render_leaderboard(c1, "🎯 HRR 1+",    "hrr",      hrr1_won)
render_leaderboard(c2, "🎯 HRR 2+",    "hrr_2plus",hrr2_won)
render_leaderboard(c3, "💥 HR",        "hr",       hr_won)
render_leaderboard(c4, "🎰 K Over",    "k_over",   k_won)

with c5:
    st.markdown("**🔥 Convergence**")
    if conv_rows:
        st.metric("Overall", f"{c_pct}%", f"{c_wins}/{c_total}")
        if len(strong) > 0:
            st.metric("Strong", f"{s_pct}%", f"{len(strong)} bets")
        if len(lean) > 0:
            st.metric("Lean",   f"{l_pct}%", f"{len(lean)} bets")
    else:
        st.caption("No data yet")

with st.expander("ℹ️ How tracking works"):
    st.markdown("""
**Player props** — click **Check Results** the day after to pull actual stats from MLB Stats API.
- **HRR 1+** win = H+R+RBI ≥ 1
- **HRR 2+** win = H+R+RBI ≥ 2 (harder line, tracked separately)
- **HR** win = HR ≥ 1
- **K Over** win = strikeouts ≥ 1

**Moneyline** — settled automatically against the MLB schedule. Shows score, run total, and whether the bet team won.
New fields: Pitchers, Book/Model %, K Gap are stored with each pick for post-analysis.

**Convergence** — settled automatically. Broken down by 🔥 Strong vs ✅ Lean signal so you can tune the thresholds.
If Strong is materially above Lean after 20+ picks, tighten the K-gap threshold in the sidebar.

Rolling leaderboard accumulates across all tracked days.
    """)
