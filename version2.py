# ─────────────────────────────────────────────────────────────────────────────
# MERGED STREAMLIT APP - TimeGap Analytics + Coin Usage Dashboard
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
import io
import os
from pathlib import Path
from collections import Counter
import re
import plotly.express as px
import math
import warnings
warnings.filterwarnings("ignore")

# ---------- Streamlit Config ----------
st.set_page_config(
    page_title="Coin Analytics Suite",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Adaptive Theme CSS (Light & Dark) ----------
st.markdown("""
    <style>
    /* ── LIGHT THEME ──────────────────────────────────── */
    [data-testid="stAppViewContainer"][data-theme="light"] {
        background: linear-gradient(135deg,#ffeef8 0%,#e3f2fd 50%,#fff9e6 100%);
    }
    [data-testid="stSidebar"][data-theme="light"] {
        background: linear-gradient(180deg,#f8e8ff 0%,#e8f5e9 100%);
    }

    /* ── DARK THEME ───────────────────────────────────── */
    [data-testid="stAppViewContainer"][data-theme="dark"] {
        background: linear-gradient(135deg,#1a0a2e 0%,#0d1b2e 50%,#1a1a0a 100%);
    }
    [data-testid="stSidebar"][data-theme="dark"] {
        background: linear-gradient(180deg,#1e1030 0%,#0e2010 100%);
    }

    /* ── SHARED (both themes) ─────────────────────────── */
    [data-testid="stMetricValue"]           { font-weight: 600; }
    .stTabs [data-baseweb="tab-list"]       { gap: 8px; padding: 10px; border-radius: 10px; }
    .stTabs [data-baseweb="tab"]            { border-radius: 8px; font-weight: 500; padding: 8px 16px; }
    .stTabs [aria-selected="true"]          {
        background: linear-gradient(90deg,#7b1fa2 0%,#1565c0 100%) !important;
        color: white !important;
    }
    .stButton>button {
        border-radius: 8px; border: none; font-weight: 500;
        background: linear-gradient(90deg,#ba68c8 0%,#64b5f6 100%); color: white;
    }
    .stButton>button:hover {
        background: linear-gradient(90deg,#9c27b0 0%,#1976d2 100%);
    }
    [data-testid="stDataFrame"]             { border-radius: 10px; }
    .streamlit-expanderHeader               { border-radius: 8px; font-weight: 500; }
    .stSelectbox, .stTextInput              { border-radius: 8px; }
    </style>
""", unsafe_allow_html=True)

# ── Detect active Streamlit theme ──────────────────────────────────────────
def _get_is_dark() -> bool:
    try:
        theme = st.get_option("theme.base")
        if theme is not None:
            return theme == "dark"
    except Exception:
        pass
    try:
        bg = st.get_option("theme.backgroundColor") or ""
        if bg.startswith("#") and len(bg) == 7:
            r, g, b = int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16)
            return (r * 0.299 + g * 0.587 + b * 0.114) < 128
    except Exception:
        pass
    return False

IS_DARK = _get_is_dark()
PLOTLY_TEMPLATE = "plotly_dark" if IS_DARK else "plotly_white"

# ── Matplotlib theme helper ────────────────────────────────────────────────
def apply_mpl_theme(fig, ax_or_axes=None):
    """Apply dark or light styling to a matplotlib figure and its axes."""
    if IS_DARK:
        bg, fg, spine = "#1e1e2e", "#e0e0e0", "#555566"
    else:
        bg, fg, spine = "#ffffff", "#1a1a1a", "#aaaaaa"
    fig.patch.set_facecolor(bg)
    axes = []
    if ax_or_axes is None:
        axes = fig.get_axes()
    elif hasattr(ax_or_axes, "__iter__") and not hasattr(ax_or_axes, "get_xlabel"):
        for a in ax_or_axes:
            if hasattr(a, "__iter__") and not hasattr(a, "get_xlabel"):
                axes.extend(list(a))
            else:
                axes.append(a)
    else:
        axes = [ax_or_axes]
    for ax in axes:
        ax.set_facecolor(bg)
        ax.tick_params(colors=fg)
        ax.xaxis.label.set_color(fg)
        ax.yaxis.label.set_color(fg)
        ax.title.set_color(fg)
        for sp in ax.spines.values():
            sp.set_edgecolor(spine)
        lgd = ax.get_legend()
        if lgd:
            lgd.get_frame().set_facecolor(bg)
            lgd.get_frame().set_edgecolor(spine)
            for t in lgd.get_texts():
                t.set_color(fg)
            lt = lgd.get_title()
            if lt:
                lt.set_color(fg)
    return fig

# ── Plotly theme helper ────────────────────────────────────────────────────
def plotly_theme(fig):
    """Apply consistent dark/light Plotly theme with transparent background."""
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig

st.title("🪙 Copernicus Dashboard")

# =====================================================================
# 📂 DATA LOADING — SHARED ENGINE
# =====================================================================
FILE_DEFAULT = "JEFile.xlsx"

@st.cache_data(show_spinner=True)
def load_data_from_upload(content_bytes: bytes, filename: str, sheet_name):
    if filename.lower().endswith(".csv"):
        return pd.read_csv(io.StringIO(content_bytes.decode()))
    return pd.read_excel(io.BytesIO(content_bytes), sheet_name=sheet_name)

@st.cache_data(show_spinner=True)
def load_data_from_path(path: str, sheet_name, mtime: float):
    p = Path(path)
    if p.suffix.lower() == ".csv":
        return pd.read_csv(p)
    return pd.read_excel(p, sheet_name=sheet_name)

def _normalize_sheet_name(x):
    return x if x.strip() else 0

def coerce_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    s = series.copy()
    s = s.replace({"True": True, "False": False, "true": True, "false": False, "YES": True, "NO": False})
    try:
        s_num = pd.to_numeric(s, errors="coerce")
        if pd.api.types.is_numeric_dtype(s_num):
            s = s_num.fillna(0).astype(int).astype(bool)
    except Exception:
        s = s.fillna(False)
    return s.astype(bool)

# ── Sidebar File Input ─────────────────────────────────────────────────────
st.sidebar.subheader("📁 Time Gap Data Source")
source_mode = st.sidebar.radio("Select source", ["Default file", "Upload file"])
sheet_input = st.sidebar.text_input("Sheet name (optional)", "")
uploaded_file = None

if source_mode == "Upload file":
    uploaded_file = st.sidebar.file_uploader("Upload File (.xlsx/.csv)", type=["xlsx", "csv"])

st.sidebar.header("Controls")
top_n = st.sidebar.slider("Number of users (time gap)", 5, 200, 30, 5)
bottom_n = top_n

if st.sidebar.button("Clear cache"):
    st.cache_data.clear()

# ── Load Data ──────────────────────────────────────────────────────────────
data = None
try:
    if source_mode == "Upload file" and uploaded_file:
        content = uploaded_file.getvalue()
        data = load_data_from_upload(content, uploaded_file.name, _normalize_sheet_name(sheet_input))
    else:
        p = Path(FILE_DEFAULT)
        if p.exists():
            data = load_data_from_path(str(p), _normalize_sheet_name(sheet_input), p.stat().st_mtime)
except Exception as e:
    st.error(f"File Load Error: {e}")

if data is None:
    st.warning("Upload a file or place JEFile.xlsx in app folder.")
    st.stop()

# =====================================================================
# 🧠 PROCESS TIME GAP DATA
# =====================================================================
expected_cols = ["UserID", "TimeGap_sec", "ProblemSolved", "CoinID_Transition", "Prev_PathID"]
if any(col not in data.columns for col in expected_cols):
    st.error("Uploaded file missing required columns.")
    st.dataframe(data.head())
    st.stop()

df = data.copy()
file2 = data.copy()

df["TimeGap_sec"] = pd.to_numeric(df["TimeGap_sec"], errors="coerce").fillna(0.0)
df["ProblemSolved"] = coerce_bool(df["ProblemSolved"])
df["CoinID_Transition"] = df["CoinID_Transition"].astype(str)
df["UserID"] = df["UserID"].astype(str)
df["Prev_PathID"] = df["Prev_PathID"].astype(str)

file2["TimeGap_sec"] = pd.to_numeric(file2["TimeGap_sec"], errors="coerce").fillna(0.0)
file2["ProblemSolved"] = coerce_bool(file2["ProblemSolved"])
file2["CoinID_Transition"] = file2["CoinID_Transition"].astype(str)

unique_user_count = df["UserID"].nunique()

grouped = (
    df.groupby("CoinID_Transition")
    .agg(
        Avg_TimeGap_sec=("TimeGap_sec", "mean"),
        Success_Rate=("ProblemSolved", lambda x: (x == True).mean()),
        Unsuccess_Rate=("ProblemSolved", lambda x: (x == False).mean()),
    )
    .reset_index()
)

by_transition = df.groupby("CoinID_Transition")
avg_succ = by_transition.apply(
    lambda g: df.loc[g.index, "TimeGap_sec"][df.loc[g.index, "ProblemSolved"] == True].mean()
)
avg_unsucc = by_transition.apply(
    lambda g: df.loc[g.index, "TimeGap_sec"][df.loc[g.index, "ProblemSolved"] == False].mean()
)

grouped = (
    grouped.merge(avg_succ.rename("Avg_TimeGap_Success").reset_index(), on="CoinID_Transition", how="left")
           .merge(avg_unsucc.rename("Avg_TimeGap_Unsuccess").reset_index(), on="CoinID_Transition", how="left")
)

overall_means = grouped[["Avg_TimeGap_sec", "Avg_TimeGap_Success", "Avg_TimeGap_Unsuccess", "Success_Rate"]].mean()

file3 = df.copy()
user_timegap_status = (
    file3.groupby("UserID")["TimeGap_sec"].sum().reset_index().rename(columns={"TimeGap_sec": "Total_TimeGap_sec"})
)
user_status_map = file3.groupby("UserID")["ProblemSolved"].max().map({True: "Success", False: "Unsuccess"})
user_timegap_status["Status"] = user_timegap_status["UserID"].map(user_status_map)
user_timegap_status["Total_TimeGap_sec"] = user_timegap_status["Total_TimeGap_sec"].round(3)
file4 = user_timegap_status

user_timegap_by_status = (
    df.groupby(["UserID", "ProblemSolved"])["TimeGap_sec"]
    .sum()
    .unstack(fill_value=0)
    .rename(columns={True: "Total_TimeGap_Success", False: "Total_TimeGap_Unsuccess"})
    .reset_index()
)
user_timegap_by_status["Total_TimeGap_Success"] = user_timegap_by_status["Total_TimeGap_Success"].round(3)
user_timegap_by_status["Total_TimeGap_Unsuccess"] = user_timegap_by_status["Total_TimeGap_Unsuccess"].round(3)

file5 = user_timegap_by_status.merge(
    user_timegap_status[["UserID", "Status"]], on="UserID", how="left"
)
file5["Total_TimeGap_All"] = file5["Total_TimeGap_Success"] + file5["Total_TimeGap_Unsuccess"]
file5["Status"] = file5["Status"].fillna("Unsuccess")

parts = grouped["CoinID_Transition"].astype(str).str.split("->", n=1, expand=True)
if parts.shape[1] == 2:
    grouped["from"] = parts[0]
    grouped["to"] = parts[1]
else:
    grouped["from"] = grouped["CoinID_Transition"]
    grouped["to"] = grouped["CoinID_Transition"]

# =====================================================================
# 🎯 TOP-LEVEL TAB MENU
# =====================================================================
tabs = st.tabs([
    "Home",
    "🪙 Coin Usage Analytics",
    "📊 TimeGap Analysis",
    "📦 Movement Analysis"
])
(tab_home, tab_coin_usage, tab_timegap, tab_movement) = tabs

# =====================================================================
# 🏠 HOME TAB
# =====================================================================
def _home_plot():
    coins_list = list("ABCDEFGHIJ")
    coords = [
        (0, 0),
        (-1, -1), (1, -1),
        (-2, -2), (0, -2), (2, -2),
        (-3, -3), (-1, -3), (1, -3), (3, -3)
    ]
    x, y = zip(*coords)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=x, y=y, mode="markers+text",
        text=coins_list,
        textfont=dict(size=20, family="Arial Black"),
        textposition="middle center",
        marker=dict(size=80, color="#f9d342", line=dict(color="#1a1a1a", width=2), symbol="circle"),
        hoverinfo="text", name="Coins"
    ))
    fig.update_layout(
        title="🔺 Coin Puzzle: Triangular Arrangement of Coins A–J",
        title_x=0.5,
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False),
        template=PLOTLY_TEMPLATE,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=600,
        margin=dict(t=80, l=10, r=10, b=20),
        showlegend=False
    )
    coin_label_color = "#f0f0f0" if IS_DARK else "#1a1a1a"
    fig.update_traces(textfont=dict(color=coin_label_color))
    return fig

with tab_home:
    st.markdown("""
    ### 🪙 Welcome to the Copernicus Dashboard

    The **Coin Puzzle Project** is a data-driven visualization that explores how different coins perform
    across various success and failure scenarios.

    This dashboard helps analyze **coin usage patterns**, **performance trends**, and **success ratios**
    over time — enabling better decision-making and insights into behavioral dynamics.

    Each section provides an interactive view of data distributions, comparisons, and outcomes.
    Use the **tabs above** to navigate through detailed visualizations.
    """)
    st.plotly_chart(_home_plot(), use_container_width=True)

# =====================================================================
# 🪙 COIN USAGE ANALYTICS TAB
# =====================================================================
with tab_coin_usage:

    @st.cache_data(show_spinner=False)
    def load_main_csv():
        path = "Coin_Usage_With_SuccessRates.csv"
        if not os.path.exists(path):
            st.error("❌ CSV file not found.")
            st.stop()
        df_coin = pd.read_csv(path)
        move_cols = ["1st Move", "2nd Move", "3rd Move", "4th Move", "5th Move"]
        df_coin["Coin ID"] = df_coin["Coin ID"].astype(str)
        return df_coin, move_cols

    @st.cache_data(show_spinner=False)
    def load_movement_excel():
        excel_path = "ExcelFile2.xlsx"
        if not os.path.exists(excel_path):
            return pd.DataFrame(), {}
        df_moves = pd.read_excel(excel_path, usecols=["ID", "Moves_CoinID"])
        df_moves["ID"] = df_moves["ID"].astype(str)

        def clean_moves(x):
            if pd.isna(x):
                return []
            try:
                items = [item.strip().strip("'").strip('"') for item in x.strip("[]").split(",")]
                return [i for i in items if i and i.lower() != "nan"]
            except Exception:
                return []

        df_moves["Moves_CoinID"] = df_moves["Moves_CoinID"].apply(clean_moves)
        df_moves = df_moves.explode("Moves_CoinID").reset_index(drop=True)
        df_moves = df_moves[df_moves["Moves_CoinID"].isin(df_coin["Coin ID"])]
        df_moves["MoveOrder"] = df_moves.groupby("ID").cumcount() + 1
        unique_coin_ids = sorted(df_moves["Moves_CoinID"].dropna().unique().tolist())
        coin_id_map = {coin: idx + 1 for idx, coin in enumerate(unique_coin_ids)}
        df_moves["CoinNumeric"] = df_moves["Moves_CoinID"].map(coin_id_map)
        return df_moves, coin_id_map

    try:
        df_coin, move_cols = load_main_csv()
        coins_cu = df_coin["Coin ID"].tolist()
        movement_result = load_movement_excel()
        if isinstance(movement_result, tuple):
            df_moves_cu, coin_id_map = movement_result
        else:
            df_moves_cu, coin_id_map = pd.DataFrame(), {}
    except Exception as e:
        st.error(f"Error loading coin data: {e}")
        st.stop()

    heatmap_df = df_coin.set_index("Coin ID")[move_cols].fillna(0).astype(int)
    heatmap_z = heatmap_df.values
    heatmap_x = move_cols
    heatmap_y = heatmap_df.index.tolist()
    z_min, z_max = float(np.min(heatmap_z)), float(np.max(heatmap_z))
    z_mid = (z_min + z_max) / 2.0 if z_max > z_min else z_max

    def plot_usage_bar():
        fig = go.Figure()
        for m in move_cols:
            fig.add_bar(x=coins_cu, y=df_coin[m].fillna(0), name=m)
        fig.update_layout(title="Coin Usage by Movement Order", barmode='group')
        return plotly_theme(fig)

    def plot_success_failure():
        fig = go.Figure()
        fig.add_scatter(marker_color="#81c784", x=coins_cu, y=df_coin["SuccessRate"], mode="lines+markers", name="Success")
        fig.add_scatter(marker_color="#e57373", x=coins_cu, y=df_coin["FailureRate"], mode="lines+markers", name="Failure")
        fig.update_layout(title="Success vs Failure Rate", yaxis_title="Rate")
        return plotly_theme(fig)

    def plot_heatmap():
        fig = go.Figure(go.Heatmap(
            z=heatmap_z, x=heatmap_x, y=heatmap_y,
            colorscale="Blues", colorbar=dict(title="Usage Count"),
            text=heatmap_z, texttemplate="%{text}", textfont={"size": 10}
        ))
        fig.update_layout(title="Heatmap of Coin Usage by Movement Order", height=600,
                          xaxis_title="Movement Order", yaxis_title="Coin ID")
        return plotly_theme(fig)

    def plot_coin_detail(c):
        sr = df_coin.set_index("Coin ID")["SuccessRate"]
        fr = df_coin.set_index("Coin ID")["FailureRate"]
        cnt = df_coin.set_index("Coin ID")["1st Move"]
        s = int(float(sr.get(c, 0)) * float(cnt.get(c, 0)))
        f = int(float(fr.get(c, 0)) * float(cnt.get(c, 0)))
        fig = go.Figure(go.Bar(x=["Success", "Failure"], y=[s, f],
                               marker_color=["#81c784", "#e57373"], text=[s, f], textposition="auto"))
        fig.update_layout(title=f"Success vs Failure for Coin {c}", yaxis_title="Count")
        return plotly_theme(fig)

    def plot_user_path(uid):
        u = df_moves_cu[df_moves_cu["ID"] == uid]
        if u.empty:
            fig = go.Figure()
            fig.add_annotation(text="No movement data for this user", showarrow=False)
            return plotly_theme(fig)
        u = u.dropna(subset=["CoinNumeric", "Moves_CoinID"])
        fig = go.Figure(go.Scatter(x=u["MoveOrder"], y=u["CoinNumeric"],
                                   text=u["Moves_CoinID"], mode="lines+markers+text",
                                   textposition="top center"))
        fig.update_yaxes(tickmode="array", tickvals=list(coin_id_map.values()),
                         ticktext=list(coin_id_map.keys()), title_text="Coin ID",
                         range=[0.5, len(coin_id_map) + 0.5])
        fig.update_xaxes(title_text="Movement Order", dtick=1)
        fig.update_layout(title=f"User {uid} Movement Path",
                          xaxis_title="Move Sequence", yaxis_title="Coin ID")
        return plotly_theme(fig)

    t2, t3, t4, t5, t6 = st.tabs(["Usage", "Success Lines", "Coin Detail", "User Paths", "Heatmap"])
    with t2:
        st.plotly_chart(plot_usage_bar(), use_container_width=True)
    with t3:
        st.plotly_chart(plot_success_failure(), use_container_width=True)
    with t4:
        c = st.selectbox("Coin", coins_cu)
        st.plotly_chart(plot_coin_detail(c), use_container_width=True)
    with t5:
        if df_moves_cu.empty:
            st.info("No movement data available")
        else:
            u = st.selectbox("User", sorted(df_moves_cu["ID"].unique()))
            st.plotly_chart(plot_user_path(u), use_container_width=True)
    with t6:
        st.plotly_chart(plot_heatmap(), use_container_width=True)

# =====================================================================
# 📊 TIMEGAP ANALYTICS TAB
# =====================================================================
with tab_timegap:
    (
        tab_overview, tab_distributions, tab_users, tab_transitions,
        tab_heatmaps, tab_pathids, tab_groups, tab_catcount,
    ) = st.tabs([
        "📊 Overview", "📈 Distributions", "🧍 User Stats",
        "🔁 Transitions", "🌡️ Heatmaps", "🧬 Coin Sequences",
        "🏷️ Group Analysis", "Categorical Count"
    ])

with tab_overview:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unique Users", f"{unique_user_count:,.0f}")
    c2.metric("Mean TimeGap (All)", f"{overall_means['Avg_TimeGap_sec']:.2f} s")
    c3.metric("Mean TimeGap (Success)", f"{overall_means['Avg_TimeGap_Success']:.2f} s")
    c4.metric("Success Rate (Mean)", f"{overall_means['Success_Rate']:.2%}")
    st.subheader("Grouped Transition Summary")
    st.dataframe(grouped.sort_values("Success_Rate", ascending=False), use_container_width=True)

with tab_distributions:
    st.subheader("Distribution of Total_TimeGap_sec by User Status")
    palette = {"Success": "blue", "Unsuccess": "darkorange"}
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.histplot(data=file4, x="Total_TimeGap_sec", hue="Status",
                 bins=50, kde=True, multiple="stack", palette=palette, ax=ax)
    ax.set_title("Distribution of Total_TimeGap_sec by User Status")
    ax.set_xlabel("Total_TimeGap_sec")
    ax.set_ylabel("Number of Users")
    apply_mpl_theme(fig)
    st.pyplot(fig)

with tab_users:
    from matplotlib.patches import Patch
    color_map = {"Success": "blue", "Unsuccess": "darkorange"}
    legend_elements = [
        Patch(facecolor=color_map["Success"], label="Success"),
        Patch(facecolor=color_map["Unsuccess"], label="Unsuccess"),
    ]

    st.subheader(f"Top {top_n} Users by Total_TimeGap_sec")
    top_users = file5.sort_values(by="Total_TimeGap_All", ascending=False).head(top_n)
    fig, ax = plt.subplots(figsize=(14, 7))
    colors_bar = top_users["Status"].map(color_map).fillna("gray")
    ax.bar(top_users["UserID"].astype(str), top_users["Total_TimeGap_All"], color=colors_bar)
    ax.set_ylabel("Total_TimeGap_sec")
    ax.set_xlabel("UserID")
    ax.set_title(f"Top {top_n} Users by Total TimeGap_sec (Color: Success/Unsuccess)")
    plt.setp(ax.get_xticklabels(), rotation=90)
    ax.legend(handles=legend_elements, title="Status")
    apply_mpl_theme(fig)
    st.pyplot(fig)

    st.subheader(f"Bottom {bottom_n} Users by Total_TimeGap_sec")
    bottom_users = file5.sort_values(by="Total_TimeGap_All", ascending=True).head(bottom_n)
    fig, ax = plt.subplots(figsize=(12, 6))
    colors_bar = bottom_users["Status"].map(color_map).fillna("gray")
    ax.bar(bottom_users["UserID"].astype(str), bottom_users["Total_TimeGap_All"], color=colors_bar)
    ax.set_title(f"Bottom {bottom_n} Users by Total_TimeGap_sec")
    ax.set_xlabel("UserID")
    ax.set_ylabel("Total_TimeGap_sec")
    plt.setp(ax.get_xticklabels(), rotation=90)
    ax.legend(handles=legend_elements, title="Status")
    apply_mpl_theme(fig)
    st.pyplot(fig)

    st.subheader(f"Highest/Lowest Successful TimeGap (Top {top_n})")
    success_df = file5[file5["Status"] == "Success"]
    top_success = success_df.nlargest(top_n, "Total_TimeGap_Success")
    least_success = success_df.nsmallest(top_n, "Total_TimeGap_Success")
    fig, axes = plt.subplots(1, 2, figsize=(18, 6))
    axes[0].barh(top_success["UserID"].astype(str), top_success["Total_TimeGap_Success"], color="blue")
    axes[0].set_title(f"Top {top_n} Users by Total Successful TimeGap_sec")
    axes[0].set_xlabel("Total_TimeGap_Success")
    axes[0].invert_yaxis()
    axes[1].barh(least_success["UserID"].astype(str), least_success["Total_TimeGap_Success"], color="lightblue")
    axes[1].set_title(f"Lowest {top_n} Users by Total Successful TimeGap_sec")
    axes[1].set_xlabel("Total_TimeGap_Success")
    axes[1].invert_yaxis()
    apply_mpl_theme(fig)
    st.pyplot(fig)

    st.subheader(f"Highest/Lowest Unsuccessful TimeGap (Top {top_n})")
    unsuccess_df = file5[file5["Status"] == "Unsuccess"]
    top_unsuccess = unsuccess_df.nlargest(top_n, "Total_TimeGap_Unsuccess")
    least_unsuccess = unsuccess_df.nsmallest(top_n, "Total_TimeGap_Unsuccess")
    fig, axes = plt.subplots(1, 2, figsize=(18, 6))
    axes[0].barh(top_unsuccess["UserID"].astype(str), top_unsuccess["Total_TimeGap_Unsuccess"], color="darkorange")
    axes[0].set_title(f"Top {top_n} Users by Total Unsuccessful TimeGap_sec")
    axes[0].set_xlabel("Total_TimeGap_Unsuccess")
    axes[0].invert_yaxis()
    axes[1].barh(least_unsuccess["UserID"].astype(str), least_unsuccess["Total_TimeGap_Unsuccess"], color="orange")
    axes[1].set_title(f"Lowest {top_n} Users by Total Unsuccessful TimeGap_sec")
    axes[1].set_xlabel("Total_TimeGap_Unsuccess")
    axes[1].invert_yaxis()
    apply_mpl_theme(fig)
    st.pyplot(fig)

with tab_transitions:
    st.subheader("Success vs Unsuccess Rates by CoinID_Transition")
    coins_trans = sorted(
        set(grouped["from"].dropna().unique()).union(set(grouped["to"].dropna().unique()))
    )
    if len(coins_trans) == 0:
        st.info("No Coin IDs available for filtering.")
    else:
        sel_coin = st.selectbox("Coin ID", coins_trans, index=0)
        scope = st.radio("Match scope", ["Either side", "From only", "To only"], horizontal=True)
        if scope == "From only":
            filt = grouped["from"] == sel_coin
        elif scope == "To only":
            filt = grouped["to"] == sel_coin
        else:
            filt = (grouped["from"] == sel_coin) | (grouped["to"] == sel_coin)
        filtered = grouped.loc[filt].copy()
        if filtered.empty:
            st.warning("No transitions match the current selection.")
        else:
            filtered_sorted = filtered.sort_values(by="Success_Rate", ascending=False)
            x = np.arange(len(filtered_sorted))
            width = 0.4
            fig, ax = plt.subplots(figsize=(14, 5))
            ax.bar(x - width/2, filtered_sorted["Success_Rate"].fillna(0), width, label="Success Rate", color="mediumblue")
            ax.bar(x + width/2, filtered_sorted["Unsuccess_Rate"].fillna(0), width, label="Unsuccess Rate", color="lightgreen", alpha=0.8)
            ax.set_xticks(x)
            ax.set_xticklabels(filtered_sorted["CoinID_Transition"], rotation=90)
            ax.set_title(f"Success and Unsuccess Rates by CoinID_Transition (filtered by {sel_coin})")
            ax.set_xlabel("CoinID_Transition")
            ax.set_ylabel("Rate")
            ax.legend()
            fig.tight_layout()
            apply_mpl_theme(fig)
            st.pyplot(fig)

    grouped_sorted = grouped.sort_values(by="Success_Rate", ascending=False)
    x = np.arange(len(grouped_sorted)) * 1.5
    width = 0.5
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.bar(x - width / 2, grouped_sorted["Success_Rate"], width, label="Success Rate", color="blue")
    ax.bar(x + width / 2, grouped_sorted["Unsuccess_Rate"], width, label="Unsuccess Rate", color="darkorange")
    ax.set_xticks(x)
    ax.set_xticklabels(grouped_sorted["CoinID_Transition"], rotation=90)
    ax.set_title("Success and Unsuccess Rates by CoinID_Transition")
    ax.set_xlabel("CoinID_Transition")
    ax.set_ylabel("Rate")
    ax.legend()
    apply_mpl_theme(fig)
    st.pyplot(fig)

    st.subheader("Average TimeGap: Success vs Unsuccess (sorted by Avg TimeGap)")
    grouped_time = grouped.sort_values(by="Avg_TimeGap_sec", ascending=False)
    x = np.arange(len(grouped_time))
    width = 0.35
    fig, ax = plt.subplots(figsize=(16, 6))
    ax.bar(x - width / 2, grouped_time["Avg_TimeGap_Success"].fillna(0), width, label="Avg TimeGap (Success)", color="blue", alpha=0.9)
    ax.bar(x + width / 2, grouped_time["Avg_TimeGap_Unsuccess"].fillna(0), width, label="Avg TimeGap (Unsuccess)", color="darkorange", alpha=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(grouped_time["CoinID_Transition"], rotation=90)
    ax.set_title("Average TimeGap_sec: Success vs Unsuccess by CoinID_Transition")
    ax.set_xlabel("CoinID_Transition")
    ax.set_ylabel("Avg_TimeGap_sec")
    ax.legend()
    apply_mpl_theme(fig)
    st.pyplot(fig)

with tab_heatmaps:
    st.subheader("Avg Successful TimeGap_sec")
    success_matrix = grouped.pivot(index="from", columns="to", values="Avg_TimeGap_Success")
    if success_matrix is None or success_matrix.empty or success_matrix.count().sum() == 0:
        st.info("No data available to render the Successful TimeGap heatmap.")
    else:
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(success_matrix.fillna(0), annot=True, fmt=".2f", cmap="Greens",
                    cbar_kws={"label": "Avg Successful TimeGap_sec"}, ax=ax)
        ax.set_xlabel("To CoinID")
        ax.set_ylabel("From CoinID")
        ax.set_title("Average Successful TimeGap_sec")
        apply_mpl_theme(fig)
        st.pyplot(fig)

    st.subheader("Avg Unsuccessful TimeGap_sec")
    unsuccess_matrix = grouped.pivot(index="from", columns="to", values="Avg_TimeGap_Unsuccess")
    if unsuccess_matrix is None or unsuccess_matrix.empty or unsuccess_matrix.count().sum() == 0:
        st.info("No data available to render the Unsuccessful TimeGap heatmap.")
    else:
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(unsuccess_matrix.fillna(0), annot=True, fmt=".2f", cmap="Reds",
                    cbar_kws={"label": "Avg Unsuccessful TimeGap_sec"}, ax=ax)
        ax.set_xlabel("To CoinID")
        ax.set_ylabel("From CoinID")
        ax.set_title("Average Unsuccessful TimeGap_sec")
        apply_mpl_theme(fig)
        st.pyplot(fig)

with tab_pathids:
    st.subheader("CoinID Sequence Analysis")
    ps = (
        df[["UserID", "Prev_PathID", "TimeGap_sec", "ProblemSolved"]]
        .loc[lambda d: d["Prev_PathID"].notna()]
        .rename(columns={"Prev_PathID": "PathID"})
        .reset_index(drop=True)
    )
    if ps.empty:
        st.info("No rows with Prev_PathID found; PathID analysis is unavailable.")
    else:
        ps_agg = (
            ps.groupby("PathID", as_index=True)
            .agg(
                Count=("UserID", "count"),
                Avg_TimeGap_sec=("TimeGap_sec", "mean"),
                Solved_Count=("ProblemSolved", lambda x: (x == True).sum()),
                Unsolved_Count=("ProblemSolved", lambda x: (x == False).sum()),
            )
        )
        if ps_agg.empty:
            st.info("No PathID aggregates available to plot.")
        else:
            denom = ps_agg["Solved_Count"] + ps_agg["Unsolved_Count"]
            ps_agg["Success_Rate"] = ps_agg["Solved_Count"] / denom.replace(0, 1)
            sel_paths = ps_agg["Count"].sort_values(ascending=False).index[:10]
            if len(sel_paths) == 0:
                st.info("No PathIDs to show in charts.")
            else:
                fig, ax = plt.subplots(figsize=(12, 4))
                ps_agg.loc[sel_paths, "Count"].plot(kind="bar", color="tab:blue", ax=ax)
                ax.set_title("Top 10 CoinID Sequence by Count")
                ax.set_ylabel("Count")
                ax.set_xlabel("PathSequence")
                plt.setp(ax.get_xticklabels(), rotation=45)
                apply_mpl_theme(fig)
                st.pyplot(fig)

                fig, ax = plt.subplots(figsize=(12, 4))
                ps_agg.loc[sel_paths, "Avg_TimeGap_sec"].plot(kind="bar", color="tab:orange", ax=ax)
                ax.set_title("Average TimeGap_sec for Top 10 CoinID Sequence")
                ax.set_ylabel("Avg_TimeGap_sec")
                ax.set_xlabel("PathSequence")
                plt.setp(ax.get_xticklabels(), rotation=45)
                apply_mpl_theme(fig)
                st.pyplot(fig)

                sel_low = ps_agg["Avg_TimeGap_sec"].nsmallest(10).sort_values(ascending=True)
                if len(sel_low) > 0:
                    fig, ax = plt.subplots(figsize=(12, 4))
                    sel_low.plot(kind="bar", color="tab:orange", ax=ax)
                    ax.set_title("Average TimeGap_sec for Lowest 10 CoinID sequence")
                    ax.set_ylabel("Avg_TimeGap_sec")
                    ax.set_xlabel("PathSequence")
                    plt.setp(ax.get_xticklabels(), rotation=45)
                    apply_mpl_theme(fig)
                    st.pyplot(fig)
                else:
                    st.info("No PathIDs with the lowest average time gaps to display.")

with tab_groups:
    st.subheader("Group-wise transition summary")
    file2["Group"] = file2["CoinID_Transition"].astype(str).str[0]
    groups = sorted([g for g in file2["Group"].dropna().unique().tolist() if isinstance(g, str) and len(g) > 0])
    if len(groups) == 0:
        st.info("No groups found from CoinID_Transition first characters.")
    else:
        group_choice = st.selectbox("CoinID initial", groups, index=0,
                                    help="Select the starting character of CoinID_Transition")
        group_df = file2[file2["Group"] == group_choice]
        if group_df.empty:
            st.info("No rows match this group selection.")
        else:
            summary = (
                group_df.groupby(["CoinID_Transition", "ProblemSolved"])["TimeGap_sec"]
                .mean().reset_index()
                .pivot(index="CoinID_Transition", columns="ProblemSolved", values="TimeGap_sec")
                .rename(columns={True: "Success", False: "Unsuccess"})
                .sort_values(by="Success", ascending=False)
            )
            if summary is None or summary.empty:
                st.info("No data available for this group.")
            else:
                fig, ax = plt.subplots(figsize=(12, 6))
                cols_to_plot = [c for c in ["Success", "Unsuccess"] if c in summary.columns]
                summary[cols_to_plot].fillna(0).plot(kind="bar", ax=ax, color=["blue", "darkorange"][:len(cols_to_plot)])
                ax.set_title(f'Average TimeGap_sec for transitions starting with "{group_choice}" (Success vs Unsuccess)')
                ax.set_xlabel("CoinID_Transition")
                ax.set_ylabel("Avg_TimeGap_sec")
                plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
                ax.legend(title="ProblemSolved")
                fig.tight_layout()
                apply_mpl_theme(fig)
                st.pyplot(fig)
                st.dataframe(summary.round(3), use_container_width=True)

with tab_catcount:
    st.header("📦 Categorical Variable Analysis")
    cat = pd.read_excel("Catdata.xlsx")
    m1 = cat
    cat_cols = [c for c in m1.columns if m1[c].dtype == "object" and m1[c].nunique() <= 200]
    st.subheader("📊 Categorical Value Counts")
    selected_cat = st.selectbox("Select a categorical column:", cat_cols)
    if selected_cat:
        s = m1[selected_cat].fillna("Missing").value_counts().reset_index()
        s.columns = [selected_cat, "count"]
        fig = px.bar(s.sort_values("count"), x="count", y=selected_cat, orientation="h",
                     title=f"Counts for {selected_cat}")
        fig.update_layout(height=450)
        plotly_theme(fig)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("🧩 Correlation Heatmap for Selected Variables")
    available_cols = [
        "Companionship", "EnjoysPuzzles", "FeelInsight", "FeelStuck",
        "WayOfSolvingTheProblem", "GaveUpReason", "TerminationType"
    ]
    st.markdown("Select variables for correlation analysis:")
    selected_vars = []
    col1, col2 = st.columns(2)
    with col1:
        for col in available_cols[:4]:
            if st.checkbox(col, value=True):
                selected_vars.append(col)
    with col2:
        for col in available_cols[4:]:
            if st.checkbox(col, value=True):
                selected_vars.append(col)

    if len(selected_vars) >= 2:
        corr_df = m1[selected_vars].copy()
        for c in selected_vars:
            corr_df[c] = corr_df[c].astype("category").cat.codes
        corr_matrix = corr_df.corr()
        fig, ax = plt.subplots(figsize=(max(8, len(selected_vars) * 1.0), max(6, len(selected_vars) * 0.9)))
        sns.heatmap(corr_matrix, annot=True, cmap="coolwarm", fmt=".2f",
                    center=0, linewidths=0.5, square=True, ax=ax)
        ax.set_title(f"Correlation Heatmap ({len(selected_vars)} variables)")
        apply_mpl_theme(fig)
        st.pyplot(fig)
    else:
        st.info("Please select at least 2 variables to display the correlation heatmap.")

# =====================================================================
# 📦 MOVEMENT ANALYSIS TAB
# =====================================================================
with tab_movement:

    # ── Sidebar upload ───────────────────────────────────────────────
    st.sidebar.header("📁 Movement Data Source")
    uploaded_mov = st.sidebar.file_uploader("Upload Movement Data (.xlsx)", type=["xlsx"])

    @st.cache_data(show_spinner=True)
    def load_movement_data(file_path):
        try:
            return pd.read_excel(file_path)
        except Exception as e:
            st.error(f"Error loading file: {e}")
            return None

    if uploaded_mov:
        df_mov_raw = load_movement_data(uploaded_mov)
    else:
        default_path = "combined_jun_sep.xlsx"
        if os.path.exists(default_path):
            df_mov_raw = load_movement_data(default_path)
        else:
            st.warning("⚠️ Please upload a movement data file (combined_jun_sep.xlsx)")
            st.info("Expected columns: ID, Moves_CoinID, Moves_StartTime, Moves_BoardID_From, Moves_BoardID_To, Date")
            st.stop()

    if df_mov_raw is None:
        st.stop()

    # ── Process movement data ────────────────────────────────────────
    @st.cache_data(show_spinner=True)
    def process_movement_data(_df):
        df_moves = _df[_df["Moves_CoinID"].notnull()].copy()
        df_moves["Moves_Time_Fixed"] = df_moves["Moves_StartTime"].astype(str).str.replace(r":(\d{3})$", r".\1", regex=True)
        df_moves["Moves_Timestamp_Str"] = df_moves["Date"].astype(str) + " " + df_moves["Moves_Time_Fixed"]
        df_moves["Moves_Timestamp"] = pd.to_datetime(df_moves["Moves_Timestamp_Str"], format="%Y-%m-%d %H:%M:%S.%f", errors="coerce")
        df_moves["Coin_Name"] = df_moves["Moves_CoinID"].astype(str).str.strip().apply(lambda x: f"Coin {x}")
        df_moves = df_moves[["ID", "Moves_Timestamp", "Coin_Name", "Moves_BoardID_From", "Moves_BoardID_To"]]
        df_moves = df_moves.sort_values(by=["ID", "Moves_Timestamp"]).reset_index(drop=True)
        df_moves["Move_Description"] = df_moves.apply(
            lambda row: f"{row['Coin_Name']} moved from {int(row['Moves_BoardID_From'])} to {int(row['Moves_BoardID_To'])}", axis=1
        )
        participant_moves = df_moves.groupby("ID")["Move_Description"].apply(list).reset_index()
        participant_moves["Movement_Pattern"] = participant_moves["Move_Description"].apply(lambda moves: " -> ".join(moves))
        return df_moves, participant_moves

    df_moves, participant_moves = process_movement_data(df_mov_raw)

    # ── Pattern classification helpers ──────────────────────────────
    MOVEMENT_ACROSS_MEDIAN = {("J", 49, 13), ("A", 19, 37), ("D", 25, 43)}
    ROSETTE_A = {("D", 25, 43), ("J", 49, 37), ("A", 19, 13)}
    ROSETTE_B = {("J", 49, 43), ("D", 25, 13), ("A", 19, 37)}
    ALL_PATTERNS = [MOVEMENT_ACROSS_MEDIAN, ROSETTE_A, ROSETTE_B]

    def extract_move_tuple(move_str):
        parts = move_str.split()
        try:
            return (parts[1], int(parts[4]), int(parts[6]))
        except (IndexError, ValueError):
            return None

    def classify_detected_pattern(moves):
        if len(moves) < 3:
            return "Neither"
        move_tuples = [t for t in (extract_move_tuple(m) for m in moves) if t]
        for i in range(len(move_tuples) - 2):
            window = set(move_tuples[i:i + 3])
            if window == MOVEMENT_ACROSS_MEDIAN:
                return "Movement across the median"
            elif window == ROSETTE_A:
                return "Rosette A"
            elif window == ROSETTE_B:
                return "Rosette B"
        return "Neither"

    def classify_behaviour(moves):
        move_tuples = [t for t in (extract_move_tuple(m) for m in moves) if t]
        for i in range(len(move_tuples) - 2):
            window = set(move_tuples[i:i + 3])
            if window in ALL_PATTERNS:
                return "Goal-directed (full strategy)"
        correct_moves = {
            ("J", 49, 13), ("A", 19, 37), ("D", 25, 43),
            ("J", 49, 37), ("A", 19, 13), ("J", 49, 43), ("D", 25, 13)
        }
        correct_count = sum(1 for m in move_tuples if m in correct_moves)
        if correct_count >= 2:
            return "Partial insight"
        if any(start == end for (_, start, end) in move_tuples):
            return "Repetitive / stalled"
        return "Exploratory search"

    # ── Subtab list (8 tabs, new Pattern Analysis added last) ────────
    (
        mv_tab_overview, mv_tab_freq, mv_tab_seq, mv_tab_participant,
        mv_tab_common, mv_tab_success, mv_tab_viz, mv_tab_pattern
    ) = st.tabs([
        "📊 Overview",
        "📈 All Moves Frequency",
        "🔄 Move Sequences",
        "👥 Participant Analysis",
        "🎲 Common Patterns",
        "🎯 Success Analysis",
        "📍 Movement Visualization",
        "🧠 Pattern Analysis",
    ])

    # ── TAB 1: OVERVIEW ──────────────────────────────────────────────
    with mv_tab_overview:
        st.header("📊 Movement Statistics Overview")
        moves_per_participant = df_moves.groupby("ID").size()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Participants", len(participant_moves))
        col2.metric("Total Moves", len(df_moves))
        col3.metric("Avg Moves/Participant", f"{moves_per_participant.mean():.2f}")
        col4.metric("Max Moves", int(moves_per_participant.max()))
        st.subheader("Descriptive Statistics")
        st.dataframe(moves_per_participant.describe().to_frame().T, use_container_width=True)
        st.subheader("Distribution of Moves per Participant")
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.hist(moves_per_participant, bins=30, color="skyblue", edgecolor="black", alpha=0.7)
        ax.axvline(moves_per_participant.mean(), color="red", linestyle="--", label="Mean")
        ax.legend()
        apply_mpl_theme(fig)
        st.pyplot(fig)

    # ── TAB 2: ALL MOVES FREQUENCY ───────────────────────────────────
    with mv_tab_freq:
        st.header("📈 Most Frequently Moved Coins (All Moves)")
        all_moves = participant_moves["Movement_Pattern"].str.split(" -> ").explode()
        coin_names_ex = all_moves.str.extract(r"Coin (\w)")
        coin_counts = coin_names_ex[0].value_counts()
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(coin_counts.index, coin_counts.values, color="#64b5f6", edgecolor="black")
        ax.set_title("Most Frequently Moved Coins (All Moves)")
        apply_mpl_theme(fig)
        st.pyplot(fig)

    # ── TAB 3: MOVE SEQUENCES ────────────────────────────────────────
    with mv_tab_seq:
        st.header("🔄 Common Move Sequences")

        def extract_coins(movement_str):
            return re.findall(r"Coin (\w)", movement_str)

        participant_moves["Coins_List"] = participant_moves["Movement_Pattern"].apply(extract_coins)

        st.subheader("Top 15 Most Common Coin Move Pairs (Bigrams)")

        def bigrams_fn(lst):
            return [(lst[i], lst[i + 1]) for i in range(len(lst) - 1)]

        participant_moves["Coin_Bigrams"] = participant_moves["Coins_List"].apply(bigrams_fn)
        all_bigrams = [bg for sub in participant_moves["Coin_Bigrams"] for bg in sub]
        bigram_counts = Counter(all_bigrams)
        bigram_df = pd.DataFrame(bigram_counts.items(), columns=["Bigram", "Count"])
        bigram_df = bigram_df.sort_values("Count", ascending=False).head(15)
        bigram_df["Transition"] = bigram_df["Bigram"].apply(lambda x: f"{x[0]} -> {x[1]}")
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.barh(range(len(bigram_df)), bigram_df["Count"], color="#81c784")
        ax.set_yticks(range(len(bigram_df)))
        ax.set_yticklabels(bigram_df["Transition"])
        ax.set_xlabel("Frequency")
        ax.set_title("Top 15 Most Common Coin Move Bigrams")
        ax.invert_yaxis()
        apply_mpl_theme(fig)
        st.pyplot(fig)

        st.subheader("Top 15 Most Common Coin Move Triplets")

        def get_triplets(moves):
            return [(moves[i], moves[i + 1], moves[i + 2]) for i in range(len(moves) - 2)] if len(moves) > 2 else []

        participant_moves["Move_List"] = participant_moves["Movement_Pattern"].str.split(" -> ")
        participant_moves["Triplets"] = participant_moves["Move_List"].apply(get_triplets)
        all_triplets = [t for sub in participant_moves["Triplets"] for t in sub]
        triplet_freq = Counter(all_triplets)
        top_triplets = triplet_freq.most_common(15)
        triplet_labels = [" -> ".join(triplet) for triplet, _ in top_triplets]
        counts = [count for _, count in top_triplets]
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.barh(triplet_labels[::-1], counts[::-1], color="#ffb74d")
        ax.set_xlabel("Frequency")
        ax.set_title("Top 15 Most Frequent Move Triplets")
        apply_mpl_theme(fig)
        st.pyplot(fig)

    # ── TAB 4: PARTICIPANT ANALYSIS ──────────────────────────────────
    with mv_tab_participant:
        st.header("👥 Individual Participant Movement Analysis")
        participants_list = sorted(participant_moves["ID"].unique())
        selected_participant = st.selectbox("Select Participant", participants_list, key="participant_select")
        if selected_participant:
            participant_data = (
                df_moves[df_moves["ID"] == selected_participant]
                .sort_values("Moves_Timestamp")
                .reset_index(drop=True)
            )
            col1, col2 = st.columns(2)
            col1.metric("Total Moves", len(participant_data))
            col2.metric("Unique Coins Moved", participant_data["Coin_Name"].nunique())
            st.subheader("Movement Pattern")
            pattern = participant_moves[participant_moves["ID"] == selected_participant]["Movement_Pattern"].values[0]
            st.info(pattern)
            st.subheader("Movement Path on Board")

            def boardid_to_xy(board_id):
                return board_id % 8, board_id // 8

            fig, ax = plt.subplots(figsize=(10, 10))
            ax.set_xlim(-1, 8)
            ax.set_ylim(-1, 8)
            ax.set_xticks(range(8))
            ax.set_yticks(range(8))
            ax.set_title(f"Movement Path for Participant {selected_participant}", fontsize=14, fontweight="bold")
            for xg in range(8):
                for yg in range(8):
                    cell_fc = "#2a2a3a" if IS_DARK else "white"
                    cell_ec = "#555566" if IS_DARK else "lightgray"
                    cell_tc = "#aaaaaa" if IS_DARK else "gray"
                    ax.add_patch(plt.Rectangle((xg - 0.5, yg - 0.5), 1, 1, edgecolor=cell_ec, facecolor=cell_fc))
                    ax.text(xg, yg, str(yg * 8 + xg), ha="center", va="center", fontsize=8, color=cell_tc)
            arrow_colors = ["red", "blue", "green", "orange", "purple", "brown", "pink", "cyan", "olive", "magenta"]
            for i, row in participant_data.iterrows():
                xs, ys = boardid_to_xy(int(row["Moves_BoardID_From"]))
                xe, ye = boardid_to_xy(int(row["Moves_BoardID_To"]))
                color = arrow_colors[i % len(arrow_colors)]
                ax.arrow(xs, ys, xe - xs, ye - ys, head_width=0.2, head_length=0.25,
                         fc=color, ec=color, linewidth=2, length_includes_head=True)
            apply_mpl_theme(fig)
            st.pyplot(fig)

            st.subheader("Detailed Moves")
            display_data = participant_data[["Moves_Timestamp", "Coin_Name", "Moves_BoardID_From", "Moves_BoardID_To"]].copy()
            display_data["Moves_Timestamp"] = display_data["Moves_Timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
            st.dataframe(display_data, use_container_width=True)

    # ── TAB 5: COMMON PATTERNS ───────────────────────────────────────
    with mv_tab_common:
        st.header("🎲 Common Movement Patterns")
        common_patterns = participant_moves["Movement_Pattern"].value_counts().head(10)

        def is_failed_sequence(seq):
            moves = [m.strip() for m in seq.split("->")]
            for m in moves:
                parts = m.split()
                if len(parts) >= 7:
                    try:
                        if int(parts[4]) != int(parts[6]):
                            return False
                    except ValueError:
                        return False
            return True

        pattern_data = []
        for pattern, count in common_patterns.items():
            pattern_data.append({
                "Pattern": pattern,
                "Count": count,
                "Status": "Failed" if is_failed_sequence(pattern) else "Success"
            })
        pattern_df = pd.DataFrame(pattern_data)
        fig, ax = plt.subplots(figsize=(14, 8))
        colors_map = {"Success": "#81c784", "Failed": "#e57373"}
        bar_colors = [colors_map[s] for s in pattern_df["Status"]]
        ax.barh(range(len(pattern_df)), pattern_df["Count"], color=bar_colors)
        ax.set_yticks(range(len(pattern_df)))
        ax.set_yticklabels([f"{i+1}. {row['Pattern'][:60]}..." for i, row in pattern_df.iterrows()], fontsize=9)
        ax.set_xlabel("Number of Occurrences", fontsize=12)
        ax.set_title("Top 10 Common Movement Sequences", fontsize=14, fontweight="bold")
        ax.invert_yaxis()
        from matplotlib.patches import Patch as MPatch
        legend_elements = [MPatch(facecolor="#81c784", label="Successful Moves"), MPatch(facecolor="#e57373", label="Failed Moves")]
        ax.legend(handles=legend_elements, loc="lower right")
        apply_mpl_theme(fig)
        st.pyplot(fig)
        st.subheader("Pattern Details")
        st.dataframe(pattern_df, use_container_width=True)

    # ── TAB 6: SUCCESS ANALYSIS ──────────────────────────────────────
    with mv_tab_success:
        st.subheader("🎯 Key Coins for Successful Movements")
        coin_success_counts = {"J": 1009, "D": 1017, "A": 1020}
        colors_succ = ["blue", "orange", "purple"]
        fig, ax = plt.subplots(figsize=(8, 6))
        bars = ax.bar(coin_success_counts.keys(), coin_success_counts.values(), color=colors_succ)
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, height + 10, f"{int(height)}",
                    ha="center", fontsize=10, fontweight="bold")
        ax.set_title("Key Coins for Successful Movements", fontsize=14)
        ax.set_xlabel("Coin")
        ax.set_ylabel("Number of Moves")
        ax.set_ylim(0, max(coin_success_counts.values()) + 100)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        apply_mpl_theme(fig)
        st.pyplot(fig)
        st.subheader("Move Statistics by Coin")
        all_moves_list = participant_moves["Movement_Pattern"].str.split(" -> ").explode()
        coin_extract = all_moves_list.str.extract(r"Coin (\w)")
        coin_stats = coin_extract[0].value_counts().reset_index()
        coin_stats.columns = ["Coin", "Total Moves"]
        st.dataframe(coin_stats, use_container_width=True)

    # ── TAB 7: MOVEMENT VISUALIZATION ────────────────────────────────
    with mv_tab_viz:
        st.header("🎥 Coin Movement Visualization (Animated)")

        @st.cache_data
        def load_animation_data():
            df_anim = pd.read_excel("combined_jun_sep.xlsx")
            df_anim = df_anim[["ID", "Moves_CoinID", "Moves_StartTime", "Moves_BoardID_From", "Moves_BoardID_To"]].dropna(subset=["Moves_CoinID"])
            df_anim["Moves_StartTime"] = pd.to_datetime(df_anim["Moves_StartTime"], errors="coerce")
            return df_anim

        df_anim = load_animation_data()
        participant_ids = sorted(df_anim["ID"].unique())
        selected_id = st.selectbox("Select Participant:", participant_ids)
        df_id = df_anim[df_anim["ID"] == selected_id].sort_values("Moves_StartTime")

        initial_positions = {
            "A": 19, "B": 21, "C": 23, "D": 25,
            "E": 29, "F": 31, "G": 33,
            "H": 39, "I": 41, "J": 49
        }
        BASELINE_ROW = 3

        def cell_to_xy(cell):
            return cell % 9, (cell // 9) - BASELINE_ROW

        @st.cache_data
        def build_animation_frames(_df_id, _initial_positions):
            current_positions = _initial_positions.copy()
            frames = []
            for coin, pos in current_positions.items():
                x, y = cell_to_xy(pos)
                frames.append({"frame": 0, "coin": coin, "x": x, "y": y})
            frame_count = 1
            for _, row in _df_id.iterrows():
                coin = row["Moves_CoinID"]
                dst = int(row["Moves_BoardID_To"])
                current_positions[coin] = dst
                for c, p in current_positions.items():
                    x, y = cell_to_xy(p)
                    frames.append({"frame": frame_count, "coin": c, "x": x, "y": y})
                frame_count += 1
            return pd.DataFrame(frames)

        movement_df = build_animation_frames(df_id, initial_positions)
        ymin = movement_df["y"].min() - 1
        ymax = movement_df["y"].max() + 1
        fig = px.scatter(
            movement_df, x="x", y="y",
            animation_frame="frame", animation_group="coin",
            color="coin", hover_name="coin",
            range_x=[-1, 9], range_y=[ymin, ymax],
            size=[20] * len(movement_df),
            title=f"Animated Coin Movement — Participant {selected_id}",
            template=PLOTLY_TEMPLATE
        )
        fig.update_traces(marker=dict(size=18))
        fig.update_layout(width=700, height=550,
                          xaxis=dict(dtick=1, range=[-0.5, 8.5]),
                          yaxis=dict(dtick=1, range=[ymin, ymax]))
        fig.update_yaxes(scaleanchor="x")
        try:
            fig.layout.updatemenus[0].buttons[0].args[1]["frame"]["redraw"] = False
        except Exception:
            pass
        st.plotly_chart(fig, use_container_width=True)

    # ── TAB 8: PATTERN ANALYSIS (NEW) ────────────────────────────────
    with mv_tab_pattern:
        st.header("🧠 Movement Pattern Analysis")
        st.markdown("""
        This section classifies each participant's move sequence into one of four recognised
        strategic patterns and breaks down distribution by participant count, overall percentage,
        gender, and age group.
        """)

        # ── Compute detected patterns ────────────────────────────────
        @st.cache_data
        def compute_patterns(_participant_moves, _df_mov_raw):
            pm = _participant_moves.copy()
            pm["Detected_Pattern"] = pm["Move_Description"].apply(classify_detected_pattern)
            pm["Behaviour_Type"] = pm["Move_Description"].apply(classify_behaviour)

            # Try to merge demographics if columns exist
            merged = None
            demo_cols_gender = ["ID", "Gender"]
            demo_cols_age = ["ID", "Age"]
            has_gender = all(c in _df_mov_raw.columns for c in demo_cols_gender)
            has_age = all(c in _df_mov_raw.columns for c in demo_cols_age)

            if has_gender or has_age:
                demo_cols = ["ID"] + (["Gender"] if has_gender else []) + (["Age"] if has_age else [])
                demo = _df_mov_raw[demo_cols].drop_duplicates("ID")
                merged = pm.merge(demo, on="ID", how="left")

            return pm, merged, has_gender, has_age

        pm_classified, merged_demo, has_gender, has_age = compute_patterns(participant_moves, df_mov_raw)

        # ── CHART 1: Overall Distribution by Number of Participants ──
        st.subheader("📊 Overall Distribution of Movement Patterns (Number of Participants)")

        pattern_counts_raw = pm_classified["Detected_Pattern"].value_counts()
        preferred_order = ["Neither", "Movement across the median", "Rosette B", "Rosette A"]
        order_present = [p for p in preferred_order if p in pattern_counts_raw.index]
        rest = [p for p in pattern_counts_raw.index if p not in preferred_order]
        pattern_counts_chart1 = pattern_counts_raw.reindex(order_present + rest).dropna()

        colors_chart1 = ["#3A86FF", "#8338EC", "#FF006E", "#2A9D8F"][:len(pattern_counts_chart1)]
        fig1, ax1 = plt.subplots(figsize=(8, 5))
        pattern_counts_chart1.plot(kind="bar", color=colors_chart1, width=0.6, ax=ax1)
        ax1.set_title("Overall Distribution of Movement Patterns (Number of Participants)", fontsize=13)
        ax1.set_xlabel("Movement Pattern")
        ax1.set_ylabel("Number of Participants")
        ax1.set_xticklabels(pattern_counts_chart1.index, rotation=20, ha="right")
        ax1.spines["top"].set_visible(False)
        ax1.spines["right"].set_visible(False)
        ax1.yaxis.grid(True, linestyle="--", alpha=0.4)
        apply_mpl_theme(fig1, ax1)
        st.pyplot(fig1)
        plt.close(fig1)

        # ── CHART 2: Overall Distribution by Percentage ───────────────
        st.subheader("📊 Overall Distribution of Movement Patterns (Percentage)")

        pct_order = ["Movement across the median", "Neither", "Rosette A", "Rosette B"]
        pct_present = [p for p in pct_order if p in pattern_counts_raw.index]
        pct_rest = [p for p in pattern_counts_raw.index if p not in pct_order]
        pattern_pct = (pattern_counts_raw / pattern_counts_raw.sum()).reindex(pct_present + pct_rest).dropna()

        colors_chart2 = ["#6A0DAD", "#E65100", "#2E7D32", "#800000"][:len(pattern_pct)]
        labels_chart2 = [{"Movement across the median": "Median", "Neither": "Neither",
                           "Rosette A": "Rosette A", "Rosette B": "Rosette B"}.get(p, p) for p in pattern_pct.index]
        fig2, ax2 = plt.subplots(figsize=(8, 5))
        pattern_pct.plot(kind="bar", color=colors_chart2, width=0.6, ax=ax2)
        ax2.set_title("Overall Distribution of Movement Patterns", fontsize=13)
        ax2.set_xlabel("Pattern")
        ax2.set_ylabel("Percentage (%)")
        ax2.set_xticklabels(labels_chart2, rotation=0)
        ax2.set_ylim(0, 1)
        ax2.set_yticks([0, 0.25, 0.5, 0.75, 1])
        ax2.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_visible(False)
        ax2.yaxis.grid(True, linestyle="--", alpha=0.3)
        apply_mpl_theme(fig2, ax2)
        st.pyplot(fig2)
        plt.close(fig2)

        # ── CHART 3: By Gender ─────────────────────────────────────────
        st.subheader("📊 Movement Patterns by Gender")

        if has_gender and merged_demo is not None:
            gender_map = {0: "Male", 1: "Female", 2: "Non-binary", 3: "Prefer not to say"}
            merged_demo["Gender_Label"] = merged_demo["Gender"].map(gender_map).fillna("Unknown")

            pattern_gender = (
                merged_demo.groupby(["Gender_Label", "Detected_Pattern"])["ID"]
                .nunique()
                .unstack(fill_value=0)
            )
            # Reindex gender rows in preferred order
            gender_order = ["Male", "Female", "Non-binary", "Prefer not to say"]
            gender_order_present = [g for g in gender_order if g in pattern_gender.index]
            pattern_gender = pattern_gender.reindex(gender_order_present, fill_value=0)
            pattern_gender_prop = pattern_gender.div(pattern_gender.sum(axis=1).replace(0, 1), axis=0)

            # Rename columns to short labels
            col_rename = {"Movement across the median": "Median", "Neither": "Neither",
                          "Rosette A": "Rosette A", "Rosette B": "Rosette B"}
            pattern_gender_prop.columns = [col_rename.get(c, c) for c in pattern_gender_prop.columns]

            colors_chart3 = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"][:len(pattern_gender_prop.columns)]
            fig3, ax3 = plt.subplots(figsize=(9, 6))
            pattern_gender_prop.plot(kind="bar", stacked=True, width=0.7, color=colors_chart3, ax=ax3)
            ax3.set_title("Movement Patterns by Gender", fontsize=13)
            ax3.set_xlabel("Gender", fontsize=11)
            ax3.set_ylabel("Percentage (%)", fontsize=11)
            ax3.set_xticklabels(ax3.get_xticklabels(), rotation=0)
            ax3.set_ylim(0, 1)
            ax3.set_yticks([0, 0.25, 0.5, 0.75, 1])
            ax3.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
            ax3.legend(title="Pattern", bbox_to_anchor=(1.02, 1), loc="upper left")
            apply_mpl_theme(fig3, ax3)
            st.pyplot(fig3)
            plt.close(fig3)
        else:
            st.info("ℹ️ No **Gender** column found in the movement data. This chart requires a 'Gender' column (0=Male, 1=Female, 2=Non-binary, 3=Prefer not to say).")

        # ── CHART 4: By Age Group ──────────────────────────────────────
        st.subheader("📊 Percentage of Movement Patterns Across Age Groups")

        if has_age and merged_demo is not None:
            merged_age = merged_demo[(merged_demo["Age"] > 0) & (merged_demo["Age"] <= 100)].copy()
            bins = [0, 18, 25, 35, 50, 100]
            labels_age = ["<18", "18–25", "26–35", "36–50", "50+"]
            merged_age["Age_Group"] = pd.cut(merged_age["Age"], bins=bins, labels=labels_age)

            pattern_age = (
                merged_age.groupby(["Age_Group", "Detected_Pattern"])["ID"]
                .nunique()
                .unstack(fill_value=0)
            )
            pattern_age = pattern_age.reindex([l for l in labels_age if l in pattern_age.index], fill_value=0)
            pattern_age_prop = pattern_age.div(pattern_age.sum(axis=1).replace(0, 1), axis=0)

            colors_chart4 = ["#4B0082", "#E6B325", "#0B6623", "#B22222"][:len(pattern_age_prop.columns)]
            fig4, ax4 = plt.subplots(figsize=(10, 6))
            pattern_age_prop.plot(kind="bar", color=colors_chart4, width=0.7, ax=ax4)
            ax4.set_title("Percentage of Movement Patterns Across Age Groups", fontsize=14)
            ax4.set_xlabel("Age Group", fontsize=12)
            ax4.set_ylabel("Percentage (%)", fontsize=12)
            ax4.set_xticklabels(ax4.get_xticklabels(), rotation=0)
            ax4.set_ylim(0, 1)
            ax4.set_yticks([0, 0.25, 0.5, 0.75, 1])
            ax4.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
            ax4.legend(title="Pattern", bbox_to_anchor=(1.02, 1), loc="upper left")
            ax4.spines["top"].set_visible(False)
            ax4.spines["right"].set_visible(False)
            apply_mpl_theme(fig4, ax4)
            st.pyplot(fig4)
            plt.close(fig4)
        else:
            st.info("ℹ️ No **Age** column found in the movement data. This chart requires an 'Age' column (numeric).")

        # ── Summary table ──────────────────────────────────────────────
        st.subheader("📋 Pattern Classification Summary")
        summary_df = pm_classified[["ID", "Detected_Pattern", "Behaviour_Type"]].copy()
        st.dataframe(summary_df, use_container_width=True)

        # ── Download ───────────────────────────────────────────────────
        csv_bytes = summary_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download Pattern Summary CSV",
            data=csv_bytes,
            file_name="pattern_analysis_summary.csv",
            mime="text/csv"
        )

# =====================================================================
# FOOTER
# =====================================================================
st.markdown("---")
st.caption("🪙 Copernicus Dashboard | Built with Streamlit")
