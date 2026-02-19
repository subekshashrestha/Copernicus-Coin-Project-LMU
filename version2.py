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
import ipywidgets as widgets
from IPython.display import display
import plotly.express as px
import math



# ---------- Streamlit Config ----------
st.set_page_config(
    page_title="Coin Analytics Suite",
    page_icon="🪙",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Pastel Theme Styling ----------
st.markdown("""
    <style>
    /* Main background */
    .stApp {
        background: linear-gradient(135deg, #ffeef8 0%, #e3f2fd 50%, #fff9e6 100%);
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8e8ff 0%, #e8f5e9 100%);
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        color: #5e35b1;
        font-weight: 600;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #6a1b9a !important;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #fff3e0;
        padding: 10px;
        border-radius: 10px;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: #ffccbc;
        border-radius: 8px;
        color: #bf360c;
        font-weight: 500;
        padding: 8px 16px;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(90deg, #ce93d8 0%, #90caf9 100%);
        color: white !important;
    }
    
    /* Buttons */
    .stButton>button {
        background: linear-gradient(90deg, #ba68c8 0%, #64b5f6 100%);
        color: white;
        border-radius: 8px;
        border: none;
        font-weight: 500;
    }
    
    .stButton>button:hover {
        background: linear-gradient(90deg, #ab47bc 0%, #42a5f5 100%);
        border: none;
    }
    
    /* Dataframes */
    [data-testid="stDataFrame"] {
        background-color: #fff;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(156, 39, 176, 0.1);
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background-color: #f3e5f5;
        border-radius: 8px;
        color: #7b1fa2;
        font-weight: 500;
    }
    
    /* Select boxes and inputs */
    .stSelectbox, .stTextInput {
        background-color: rgba(255, 255, 255, 0.8);
        border-radius: 8px;
    }
    
    /* Info boxes */
    .stInfo {
        background-color: #e1f5fe;
        border-left: 4px solid #4fc3f7;
    }
    
    /* Warning boxes */
    .stWarning {
        background-color: #fff9c4;
        border-left: 4px solid #ffb74d;
    }
    
    /* Error boxes */
    .stError {
        background-color: #ffebee;
        border-left: 4px solid #ef5350;
    }
    
    /* Success boxes */
    .stSuccess {
        background-color: #e8f5e9;
        border-left: 4px solid #66bb6a;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🪙 Copernicus Dashboard")


# =====================================================================
# 📂 DATA LOADING — SHARED ENGINE
# =====================================================================
FILE_DEFAULT = "C:/Users/tanma/OneDrive/Documents/GitHub/Coin-Project/JEFile.xlsx"

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

# ───────────────────────────────────────────────
# Sidebar File Input
# ───────────────────────────────────────────────
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

# ---------------- LOAD DATA ----------------
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

# ---------------- CLEAN DATA ----------------
df["TimeGap_sec"] = pd.to_numeric(df["TimeGap_sec"], errors="coerce").fillna(0.0)
df["ProblemSolved"] = coerce_bool(df["ProblemSolved"])
df["CoinID_Transition"] = df["CoinID_Transition"].astype(str)
df["UserID"] = df["UserID"].astype(str)
df["Prev_PathID"] = df["Prev_PathID"].astype(str)

file2["TimeGap_sec"] = pd.to_numeric(file2["TimeGap_sec"], errors="coerce").fillna(0.0)
file2["ProblemSolved"] = coerce_bool(file2["ProblemSolved"])
file2["CoinID_Transition"] = file2["CoinID_Transition"].astype(str)

# ---------------- TIMEGAP AGGREGATION ----------------
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

# Per-user totals and status
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

# Split transitions into from/to for heatmaps
parts = grouped["CoinID_Transition"].astype(str).str.split("->", n=1, expand=True)
if parts.shape[1] == 2:
    grouped["from"] = parts[0]
    grouped["to"] = parts[1]
else:
    grouped["from"] = grouped["CoinID_Transition"]
    grouped["to"] = grouped["CoinID_Transition"]

# ---------------------------------------------------------------------
# 🎯 TAB MENU SYSTEM
# ---------------------------------------------------------------------
tabs = st.tabs([
    "Home",
    "🪙 Coin Usage Analytics",
    "📊 TimeGap Analysis",
    "📦 Movement Analysis"
])

(tab_home, tab_coin_usage, tab_timegap, tab_movement) = tabs

def plot():

    #tab_overview, tab_distributions, tab_users, tab_transitions, tab_heatmaps, tab_pathids, tab_groups,

    # ---------------------------------------
    # 🪙 Description / Intro for the Home Page
    # ---------------------------------------
    st.markdown("""
    ### 🪙 Welcome to the Copernicus  Dashboard

    The **Coin Puzzle Project** is a data-driven visualization that explores how different coins perform 
    across various success and failure scenarios.

    This dashboard helps analyze **coin usage patterns**, **performance trends**, and **success ratios** 
    over time — enabling better decision-making and insights into behavioral dynamics.

    Each section provides an interactive view of data distributions, comparisons, and outcomes.  
    Use the **tabs above** to navigate through detailed visualizations.
    """)

    # ---------------------------------------
    # 🔺 Create Triangle Layout for Coins (A–J)
    # ---------------------------------------
    coins = list("ABCDEFGHIJ")

    # Coordinates forming a triangle arrangement
    coords = [
        (0, 0),                  # A - top
        (-1, -1), (1, -1),       # B, C
        (-2, -2), (0, -2), (2, -2),   # D, E, F
        (-3, -3), (-1, -3), (1, -3), (3, -3)  # G, H, I, J
    ]

    x, y = zip(*coords)

    # ---------------------------------------
    # 📊 Create Plotly Figure
    # ---------------------------------------
    fig = go.Figure()

    # Add coin markers (as gold circles with labels)
    fig.add_trace(go.Scatter(
        x=x,
        y=y,
        mode="markers+text",
        text=coins,
        textfont=dict(size=20, color="#1a1a1a", family="Arial Black"),
        textposition="middle center",
        marker=dict(
            size=80,
            color="#f9d342",  # rich gold
            line=dict(color="#1a1a1a", width=2),
            symbol="circle"
        ),
        hoverinfo="text",
        name="Coins"
    ))

    # ---------------------------------------
    # 🎨 Layout Styling
    # ---------------------------------------
    fig.update_layout(
        title="🔺 Coin Puzzle: Triangular Arrangement of Coins A–J",
        title_x=0.5,
        xaxis=dict(showgrid=False, zeroline=False, visible=False),
        yaxis=dict(showgrid=False, zeroline=False, visible=False),
        template="plotly_dark",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        height=600,
        margin=dict(t=80, l=10, r=10, b=20),
        showlegend=False
    )

    # ---------------------------------------
    # ✅ Return the Figure
    # ---------------------------------------
    return fig

with tab_home:
    st.plotly_chart(plot(), use_container_width=True)
 # =====================================================================
# 🟨 8. COIN USAGE DASHBOARD (UNCHANGED)
# =====================================================================
with tab_coin_usage:
    #st.header("🪙 Coin Usage & Movement Dashboard")

    # ---------------- LOAD COIN CSV ----------------
    @st.cache_data(show_spinner=False)
    def load_main_csv():
        path = "C:/Users/tanma/OneDrive/Documents/GitHub/Coin-Project/Coin_Usage_With_SuccessRates (1) (1).csv"
        if not os.path.exists(path):
            st.error("❌ CSV file not found.")
            st.stop()
        df_coin = pd.read_csv(path)
        move_cols = ["1st Move", "2nd Move", "3rd Move", "4th Move", "5th Move"]
        df_coin["Coin ID"] = df_coin["Coin ID"].astype(str)
        return df_coin, move_cols

    # ---------------- MOVEMENT EXCEL ----------------
    @st.cache_data(show_spinner=False)
    def load_movement_excel():
        excel_path = "C:/Users/tanma/OneDrive/Documents/GitHub/Coin-Project/ExcelFile2.xlsx"
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

    # -----------------------------
    # LOAD CACHED DATA
    # -----------------------------
    try:
        df_coin, move_cols = load_main_csv()
        coins = df_coin["Coin ID"].tolist()
        
        # Load movement data
        movement_result = load_movement_excel()
        if isinstance(movement_result, tuple):
            df_moves, coin_id_map = movement_result
        else:
            df_moves, coin_id_map = pd.DataFrame(), {}
    except Exception as e:
        st.error(f"Error loading coin data: {e}")
        st.stop()

    # -----------------------------
    # HEATMAP DATA
    # -----------------------------
    heatmap_df = df_coin.set_index("Coin ID")[move_cols].fillna(0).astype(int)
    heatmap_z = heatmap_df.values
    heatmap_x = move_cols
    heatmap_y = heatmap_df.index.tolist()

    z_min, z_max = float(np.min(heatmap_z)), float(np.max(heatmap_z))
    z_mid = (z_min + z_max) / 2.0 if z_max > z_min else z_max
    annotations = [
        dict(x=col, y=row, text=str(int(heatmap_z[iy][ix])),
            showarrow=False, font=dict(color="white" if heatmap_z[iy][ix] >= z_mid else "black", size=11))
        for iy, row in enumerate(heatmap_y)
        for ix, col in enumerate(heatmap_x)
    ]

    # ---------------- COIN USAGE BAR ----------------
    def plot_usage_bar():
        fig = go.Figure()
        for m in move_cols:
            fig.add_bar(x=coins, y=df_coin[m].fillna(0), name=m)
        return fig.update_layout(title="Coin Usage by Movement Order", barmode='group')

    # ---------------- SUCCESS VS FAILURE ----------------
    def plot_success_failure():
        fig = go.Figure()
        fig.add_scatter(marker_color="#81c784", x=coins, y=df_coin["SuccessRate"], mode="lines+markers", name="Success")
        fig.add_scatter(marker_color="#e57373", x=coins, y=df_coin["FailureRate"], mode="lines+markers", name="Failure")
        return fig.update_layout(title="Success vs Failure Rate", yaxis_title="Rate")

    # ---------------- HEATMAP ----------------
    def plot_heatmap():
        fig = go.Figure(go.Heatmap(
            z=heatmap_z, 
            x=heatmap_x, 
            y=heatmap_y,
            colorscale="Blues", 
            colorbar=dict(title="Usage Count"),
            text=heatmap_z,
            texttemplate="%{text}",
            textfont={"size": 10}
        ))
        fig.update_layout(
            title="Heatmap of Coin Usage by Movement Order",
            height=600,
            xaxis_title="Movement Order",
            yaxis_title="Coin ID"
        )
        return fig

    # ---------------- COIN DETAIL ----------------
    def plot_coin_detail(c):
        sr = df_coin.set_index("Coin ID")["SuccessRate"]
        fr = df_coin.set_index("Coin ID")["FailureRate"]
        cnt = df_coin.set_index("Coin ID")["1st Move"]
        s = int(float(sr.get(c, 0)) * float(cnt.get(c, 0)))
        f = int(float(fr.get(c, 0)) * float(cnt.get(c, 0)))
        fig = go.Figure(go.Bar(x=["Success", "Failure"], y=[s, f], marker_color=["#81c784", "#e57373"], text=[s, f], textposition="auto"))
        fig.update_layout(title=f"Success vs Failure for Coin {c}", yaxis_title="Count")
        return fig

    # ---------------- USER PATH ----------------
    def plot_user_path(uid):
        u = df_moves[df_moves["ID"] == uid]
        if u.empty:
            fig = go.Figure()
            fig.add_annotation(text="No movement data for this user", showarrow=False)
            return fig.update_layout(title=f"User {uid} Movement")
        
        # Drop any NaN or unmapped points
        u = u.dropna(subset=["CoinNumeric", "Moves_CoinID"])
        
        fig = go.Figure(go.Scatter(
            x=u["MoveOrder"],
            y=u["CoinNumeric"],
            text=u["Moves_CoinID"], 
            mode="lines+markers+text",
            textposition="top center"
        ))
        fig.update_yaxes(
            tickmode="array",
            tickvals=list(coin_id_map.values()),
            ticktext=list(coin_id_map.keys()),
            title_text="Coin ID",
            range=[0.5, len(coin_id_map) + 0.5]
        )
        fig.update_xaxes(
            title_text="Movement Order",
            dtick=1
        )
        fig.update_layout(
            title=f"User {uid} Movement Path",
            xaxis_title="Move Sequence",
            yaxis_title="Coin ID"
        )
        return fig

    # ---------------- UI ----------------
    t2, t3, t4, t5, t6 = st.tabs(["Usage", "Success Lines", "Coin Detail", "User Paths", "Heatmap"])
    
    
    with t2: 
        st.plotly_chart(plot_usage_bar(), use_container_width=True)
    
    with t3: 
        st.plotly_chart(plot_success_failure(), use_container_width=True)
    
    with t4:
        c = st.selectbox("Coin", coins)
        st.plotly_chart(plot_coin_detail(c), use_container_width=True)
    
    with t5:
        if df_moves.empty:
            st.info("No movement data available")
        else:
            u = st.selectbox("User", sorted(df_moves["ID"].unique()))
            st.plotly_chart(plot_user_path(u), use_container_width=True)
    
    with t6: 
        st.plotly_chart(plot_heatmap(), use_container_width=True)


# =====================================================================
# 🟦 TIMEGAP ANALYTICS TABS (1-7)
# =====================================================================


with tab_timegap:
    # Create all subtabs
    (
        tab_overview,
        tab_distributions,
        tab_users,
        tab_transitions,
        tab_heatmaps,
        tab_pathids,
        tab_groups,
        tab_catcount,
    ) = st.tabs([
        "📊 Overview",
        "📈 Distributions",
        "🧍 User Stats",
        "🔁 Transitions",
        "🌡️ Heatmaps",
        "🧬 Coin Sequences",
        "🏷️ Group Analysis",
        "Catagorical Count"
    ])
    

# ---------- 1. Overview ----------
with tab_overview:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unique Users", f"{unique_user_count:,.0f}")
    c2.metric("Mean TimeGap (All)", f"{overall_means['Avg_TimeGap_sec']:.2f} s")
    c3.metric("Mean TimeGap (Success)", f"{overall_means['Avg_TimeGap_Success']:.2f} s")
    c4.metric("Success Rate (Mean)", f"{overall_means['Success_Rate']:.2%}")

    st.subheader("Grouped Transition Summary")
    st.dataframe(grouped.sort_values("Success_Rate", ascending=False), use_container_width=True)

# ---------- 2. Distributions ----------
with tab_distributions:
    st.subheader("Distribution of Total_TimeGap_sec by User Status")
    palette = {"Success": "blue", "Unsuccess": "darkorange"}
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.histplot(
        data=file4, x="Total_TimeGap_sec", hue="Status",
        bins=50, kde=True, multiple="stack", palette=palette, ax=ax
    )
    ax.set_title("Distribution of Total_TimeGap_sec by User Status")
    ax.set_xlabel("Total_TimeGap_sec")
    ax.set_ylabel("Number of Users")
    st.pyplot(fig)

# ---------- 3. Users ----------
with tab_users:
    color_map = {"Success": "blue", "Unsuccess": "darkorange"}
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=color_map["Success"], label="Success"),
        Patch(facecolor=color_map["Unsuccess"], label="Unsuccess"),
    ]

    st.subheader(f"Top {top_n} Users by Total_TimeGap_sec")
    top_users = file5.sort_values(by="Total_TimeGap_All", ascending=False).head(top_n)
    fig, ax = plt.subplots(figsize=(14, 7))
    colors = top_users["Status"].map(color_map).fillna("gray")
    ax.bar(top_users["UserID"].astype(str), top_users["Total_TimeGap_All"], color=colors)
    ax.set_ylabel("Total_TimeGap_sec")
    ax.set_xlabel("UserID")
    ax.set_title(f"Top {top_n} Users by Total TimeGap_sec (Color: Success/Unsuccess)")
    plt.setp(ax.get_xticklabels(), rotation=90)
    ax.legend(handles=legend_elements, title="Status")
    st.pyplot(fig)

    st.subheader(f"Bottom {bottom_n} Users by Total_TimeGap_sec")
    bottom_users = file5.sort_values(by="Total_TimeGap_All", ascending=True).head(bottom_n)
    fig, ax = plt.subplots(figsize=(12, 6))
    colors = bottom_users["Status"].map(color_map).fillna("gray")
    ax.bar(bottom_users["UserID"].astype(str), bottom_users["Total_TimeGap_All"], color=colors)
    ax.set_title(f"Bottom {bottom_n} Users by Total_TimeGap_sec")
    ax.set_xlabel("UserID")
    ax.set_ylabel("Total_TimeGap_sec")
    plt.setp(ax.get_xticklabels(), rotation=90)
    ax.legend(handles=legend_elements, title="Status")
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
    st.pyplot(fig)

# ---------- 4. Transitions ----------
with tab_transitions:
    st.subheader("Success vs Unsuccess Rates by CoinID_Transition")
    
    # Collect unique coins from both ends
    coins = sorted(set(grouped["from"].dropna().unique()).union(set(grouped["to"].dropna().unique())))
    
    if len(coins) == 0:
        st.info("No Coin IDs available for filtering.")
    else:
        sel_coin = st.selectbox("Coin ID", coins, index=0, help="Show transitions that involve this coin")
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
            # Sort and plot filtered rates
            filtered_sorted = filtered.sort_values(by="Success_Rate", ascending=False)
            x = np.arange(len(filtered_sorted))
            width = 0.4
            
            fig, ax = plt.subplots(figsize=(14, 5))
            ax.bar(
                x - width/2,
                filtered_sorted["Success_Rate"].fillna(0),
                width,
                label="Success Rate",
                color="mediumblue",
            )
            ax.bar(
                x + width/2,
                filtered_sorted["Unsuccess_Rate"].fillna(0),
                width,
                label="Unsuccess Rate",
                color="lightgreen",
                alpha=0.8,
            )
            ax.set_xticks(x)
            ax.set_xticklabels(filtered_sorted["CoinID_Transition"], rotation=90)
            ax.set_title(f"Success and Unsuccess Rates by CoinID_Transition (filtered by {sel_coin})")
            ax.set_xlabel("CoinID_Transition")
            ax.set_ylabel("Rate")
            ax.legend()
            fig.tight_layout()
            st.pyplot(fig)

    grouped_sorted = grouped.sort_values(by="Success_Rate", ascending=False)
    gap = 1.5
    x = np.arange(len(grouped_sorted)) * gap
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
    st.pyplot(fig)

# ---------- 5. Heatmaps ----------
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
        st.pyplot(fig)

# ---------- 6. PathIDs ----------
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
                st.pyplot(fig)

                fig, ax = plt.subplots(figsize=(12, 4))
                ps_agg.loc[sel_paths, "Avg_TimeGap_sec"].plot(kind="bar", color="tab:orange", ax=ax)
                ax.set_title("Average TimeGap_sec for Top 10 CoinID Sequence")
                ax.set_ylabel("Avg_TimeGap_sec")
                ax.set_xlabel("PathSequence")
                plt.setp(ax.get_xticklabels(), rotation=45)
                st.pyplot(fig)

                sel_low = ps_agg["Avg_TimeGap_sec"].nsmallest(10).sort_values(ascending=True)
                if len(sel_low) > 0:
                    fig, ax = plt.subplots(figsize=(12, 4))
                    sel_low.plot(kind="bar", color="tab:orange", ax=ax)
                    ax.set_title("Average TimeGap_sec for Lowest 10 CoinID sequence")
                    ax.set_ylabel("Avg_TimeGap_sec")
                    ax.set_xlabel("PathSequence")
                    plt.setp(ax.get_xticklabels(), rotation=45)
                    st.pyplot(fig)
                else:
                    st.info("No PathIDs with the lowest average time gaps to display.")

# ---------- 7. Groups ----------
with tab_groups:
    st.subheader('Group-wise transition summary')

    file2["Group"] = file2["CoinID_Transition"].astype(str).str[0]
    groups = sorted([g for g in file2["Group"].dropna().unique().tolist() if isinstance(g, str) and len(g) > 0])

    if len(groups) == 0:
        st.info("No groups found from CoinID_Transition first characters.")
    else:
        group_choice = st.selectbox(
            "CoinID initial",
            groups,
            index=0,
            help="Select the starting character of CoinID_Transition",
        )

        group_df = file2[file2["Group"] == group_choice]
        if group_df.empty:
            st.info("No rows match this group selection.")
        else:
            summary = (
                group_df.groupby(["CoinID_Transition", "ProblemSolved"])["TimeGap_sec"]
                .mean()
                .reset_index()
                .pivot(index="CoinID_Transition", columns="ProblemSolved", values="TimeGap_sec")
                .rename(columns={True: "Success", False: "Unsuccess"})
                .sort_values(by="Success", ascending=False)
            )

            if summary is None or summary.empty:
                st.info("No data available for this group.")
            else:
                # Bar chart
                fig, ax = plt.subplots(figsize=(12, 6))
                cols_to_plot = [c for c in ["Success", "Unsuccess"] if c in summary.columns]
                summary[cols_to_plot].fillna(0).plot(kind="bar", ax=ax, color=["blue", "darkorange"][:len(cols_to_plot)])
                ax.set_title(f'Average TimeGap_sec for transitions starting with "{group_choice}" (Success vs Unsuccess)')
                ax.set_xlabel("CoinID_Transition")
                ax.set_ylabel("Avg_TimeGap_sec")
                plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
                ax.legend(title="ProblemSolved")
                fig.tight_layout()
                st.pyplot(fig)

                # Table
                st.dataframe(summary.round(3), use_container_width=True)

with tab_catcount:

    st.header("📦 Categorical Variable Analysis")

    # Load data
    cat = pd.read_excel(
        'C:/Users/tanma/OneDrive/Documents/GitHub/Coin-Project/Catdata.xlsx'
    )
    m1 = cat

    # Identify categorical columns
    cat_cols = [
        c for c in m1.columns
        if m1[c].dtype == 'object' and m1[c].nunique() <= 200
    ]

    st.subheader("📊 Categorical Value Counts")

    # Streamlit dropdown for categorical columns
    selected_cat = st.selectbox("Select a categorical column:", cat_cols)

    # --- PLOT CATEGORICAL COUNTS ---
    if selected_cat:
        s = (
            m1[selected_cat]
            .fillna("Missing")
            .value_counts()
            .reset_index()
        )
        s.columns = [selected_cat, "count"]

        fig = px.bar(
            s.sort_values("count"),
            x="count",
            y=selected_cat,
            orientation="h",
            title=f"Counts for {selected_cat}"
        )
        fig.update_layout(height=450)
        st.plotly_chart(fig, use_container_width=True)

    # ------------------------------
    # 🔥 Correlation Heatmap Section
    # ------------------------------
    st.subheader("🧩 Correlation Heatmap for Selected Variables")

    available_cols = [
        'Companionship', 'EnjoysPuzzles', 'FeelInsight', 'FeelStuck',
        'WayOfSolvingTheProblem', 'GaveUpReason', 'TerminationType'
    ]

    st.markdown("Select variables for correlation analysis:")

    # Layout for checkboxes (two columns)
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

    # --- COMPUTE HEATMAP ---
    if len(selected_vars) >= 2:
        corr_df = m1[selected_vars].copy()

        # Encode categories → numeric codes
        for c in selected_vars:
            corr_df[c] = corr_df[c].astype("category").cat.codes

        corr_matrix = corr_df.corr()

        fig, ax = plt.subplots(
            figsize=(
                max(8, len(selected_vars) * 1.0),
                max(6, len(selected_vars) * 0.9)
            )
        )

        sns.heatmap(
            corr_matrix,
            annot=True,
            cmap="coolwarm",
            fmt=".2f",
            center=0,
            linewidths=0.5,
            square=True,
            ax=ax
        )
        ax.set_title(f"Correlation Heatmap ({len(selected_vars)} variables)")
        st.pyplot(fig)

    else:
        st.info("Please select at least 2 variables to display the correlation heatmap.")




# ✅ Corrected version of Movement Analysis section (properly nested subtabs)

# =====================================================================
# 📦 MOVEMENT ANALYSIS TAB
# =====================================================================
with tab_movement:
    #st.header("📦 Movement Analysis")

    import warnings
    warnings.filterwarnings("ignore")

    # =====================================================================
    # 📂 DATA LOADING
    # =====================================================================
    @st.cache_data(show_spinner=True)
    def load_movement_data(file_path):
        """Load the movement data from Excel"""
        try:
            df = pd.read_excel(file_path)
            return df
        except Exception as e:
            st.error(f"Error loading file: {e}")
            return None

    # Sidebar file upload
    st.sidebar.header("📁 Movement Data Source")
    uploaded_file = st.sidebar.file_uploader("Upload Movement Data (.xlsx)", type=["xlsx"])

    if uploaded_file:
        df = load_movement_data(uploaded_file)
    else:
        default_path = "C:/Users/tanma/OneDrive/Documents/GitHub/Coin-Project/combined_jun_sep.xlsx"
        if os.path.exists(default_path):
            df = load_movement_data(default_path)
        else:
            st.warning("⚠️ Please upload a movement data file (combined_jun_sep.xlsx)")
            st.info("Expected columns: ID, Moves_CoinID, Moves_StartTime, Moves_BoardID_From, Moves_BoardID_To, Date")
            st.stop()

    if df is None:
        st.stop()

    # =====================================================================
    # 🧠 DATA PROCESSING
    # =====================================================================
    @st.cache_data(show_spinner=True)
    def process_movement_data(_df):
        """Process and clean the movement data"""
        df_moves = _df[_df['Moves_CoinID'].notnull()].copy()
        df_moves['Moves_Time_Fixed'] = df_moves['Moves_StartTime'].astype(str).str.replace(r':(\d{3})$', r'.\1', regex=True)
        df_moves['Moves_Timestamp_Str'] = df_moves['Date'].astype(str) + ' ' + df_moves['Moves_Time_Fixed']
        df_moves['Moves_Timestamp'] = pd.to_datetime(df_moves['Moves_Timestamp_Str'], format='%Y-%m-%d %H:%M:%S.%f', errors='coerce')
        df_moves['Coin_Name'] = df_moves['Moves_CoinID'].astype(str).str.strip().apply(lambda x: f"Coin {x}")
        df_moves = df_moves[['ID', 'Moves_Timestamp', 'Coin_Name', 'Moves_BoardID_From', 'Moves_BoardID_To']]
        df_moves = df_moves.sort_values(by=['ID', 'Moves_Timestamp']).reset_index(drop=True)
        df_moves['Move_Description'] = df_moves.apply(
            lambda row: f"{row['Coin_Name']} moved from {int(row['Moves_BoardID_From'])} to {int(row['Moves_BoardID_To'])}", axis=1
        )
        participant_moves = df_moves.groupby('ID')['Move_Description'].apply(list).reset_index()
        participant_moves['Movement_Pattern'] = participant_moves['Move_Description'].apply(lambda moves: ' -> '.join(moves))
        return df_moves, participant_moves

    df_moves, participant_moves = process_movement_data(df)

    # =====================================================================
    # 🎯 MOVEMENT ANALYSIS SUBTABS
    # =====================================================================
    tabs = st.tabs([
        "📊 Overview",
        "📈 All Moves Frequency",
        "🔄 Move Sequences",
        "👥 Participant Analysis",
        "🎲 Common Patterns",
        "🎯 Success Analysis",
        "📍 Movement Visualization"
    ])

    # -----------------------------------------------------------------
    # TAB 1: OVERVIEW
    # -----------------------------------------------------------------
    with tabs[0]:
        st.header("📊 Movement Statistics Overview")
        moves_per_participant = df_moves.groupby('ID').size()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Participants", len(participant_moves))
        col2.metric("Total Moves", len(df_moves))
        col3.metric("Avg Moves/Participant", f"{moves_per_participant.mean():.2f}")
        col4.metric("Max Moves", int(moves_per_participant.max()))
        st.subheader("Descriptive Statistics")
        st.dataframe(moves_per_participant.describe().to_frame().T, use_container_width=True)
        st.subheader("Distribution of Moves per Participant")
        fig, ax = plt.subplots(figsize=(12, 5))
        ax.hist(moves_per_participant, bins=30, color='skyblue', edgecolor='black', alpha=0.7)
        ax.axvline(moves_per_participant.mean(), color='red', linestyle='--', label='Mean')
        ax.legend()
        st.pyplot(fig)

    # -----------------------------------------------------------------
    # TAB 2: ALL MOVES FREQUENCY
    # -----------------------------------------------------------------
    with tabs[1]:
        st.header("📈 Most Frequently Moved Coins (All Moves)")
        all_moves = participant_moves['Movement_Pattern'].str.split(' -> ').explode()
        coin_names = all_moves.str.extract(r'Coin (\w)')
        coin_counts = coin_names[0].value_counts()
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(coin_counts.index, coin_counts.values, color='#64b5f6', edgecolor='black')
        ax.set_title('Most Frequently Moved Coins (All Moves)')
        st.pyplot(fig)

    with tabs[2]:
        st.header("🔄 Common Move Sequences")
        
        # Extract coins function
        def extract_coins(movement_str):
            coins = re.findall(r'Coin (\w)', movement_str)
            return coins
        
        participant_moves['Coins_List'] = participant_moves['Movement_Pattern'].apply(extract_coins)
        
        # BIGRAMS
        st.subheader("Top 15 Most Common Coin Move Pairs (Bigrams)")
        
        def bigrams(lst):
            return [(lst[i], lst[i+1]) for i in range(len(lst)-1)]
        
        participant_moves['Coin_Bigrams'] = participant_moves['Coins_List'].apply(bigrams)
        all_bigrams = [bigram for sublist in participant_moves['Coin_Bigrams'] for bigram in sublist]
        bigram_counts = Counter(all_bigrams)
        
        bigram_df = pd.DataFrame(bigram_counts.items(), columns=['Bigram', 'Count'])
        bigram_df = bigram_df.sort_values('Count', ascending=False).head(15)
        bigram_df['Transition'] = bigram_df['Bigram'].apply(lambda x: f"{x[0]} -> {x[1]}")
        
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.barh(range(len(bigram_df)), bigram_df['Count'], color='#81c784')
        ax.set_yticks(range(len(bigram_df)))
        ax.set_yticklabels(bigram_df['Transition'])
        ax.set_xlabel('Frequency')
        ax.set_title('Top 15 Most Common Coin Move Bigrams')
        ax.invert_yaxis()
        st.pyplot(fig)
        
        # TRIPLETS
        st.subheader("Top 15 Most Common Coin Move Triplets")
        
        def get_triplets(moves):
            return [(moves[i], moves[i+1], moves[i+2]) for i in range(len(moves)-2)] if len(moves) > 2 else []
        
        participant_moves['Move_List'] = participant_moves['Movement_Pattern'].str.split(' -> ')
        participant_moves['Triplets'] = participant_moves['Move_List'].apply(get_triplets)
        all_triplets = [triplet for sublist in participant_moves['Triplets'] for triplet in sublist]
        triplet_freq = Counter(all_triplets)
        
        top_triplets = triplet_freq.most_common(15)
        triplet_labels = [' -> '.join(triplet) for triplet, _ in top_triplets]
        counts = [count for _, count in top_triplets]
        
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.barh(triplet_labels[::-1], counts[::-1], color='#ffb74d')
        ax.set_xlabel('Frequency')
        ax.set_title('Top 15 Most Frequent Move Triplets')
        st.pyplot(fig)

    with tabs[3]:
        st.header("👥 Individual Participant Movement Analysis")
        
        participants_list = sorted(participant_moves['ID'].unique())
        selected_participant = st.selectbox("Select Participant", participants_list, key="participant_select")
        
        if selected_participant:
            participant_data = df_moves[df_moves['ID'] == selected_participant].sort_values('Moves_Timestamp').reset_index(drop=True)
            
            # Info
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Moves", len(participant_data))
            with col2:
                unique_coins = participant_data['Coin_Name'].nunique()
                st.metric("Unique Coins Moved", unique_coins)
            
            # Movement pattern
            st.subheader("Movement Pattern")
            pattern = participant_moves[participant_moves['ID'] == selected_participant]['Movement_Pattern'].values[0]
            st.info(pattern)
            
            # Board visualization
            st.subheader("Movement Path on Board")
            
            def boardid_to_xy(board_id):
                return board_id % 8, board_id // 8
            
            fig, ax = plt.subplots(figsize=(10, 10))
            ax.set_xlim(-1, 8)
            ax.set_ylim(-1, 8)
            ax.set_xticks(range(8))
            ax.set_yticks(range(8))
            ax.set_title(f'Movement Path for Participant {selected_participant}', fontsize=14, fontweight='bold')
            
            # Draw grid
            for x in range(8):
                for y in range(8):
                    ax.add_patch(plt.Rectangle((x - 0.5, y - 0.5), 1, 1, edgecolor='lightgray', facecolor='white'))
                    ax.text(x, y, str(y * 8 + x), ha='center', va='center', fontsize=8, color='gray')
            
            # Draw arrows
            colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'cyan', 'olive', 'magenta']
            for i, row in participant_data.iterrows():
                x_start, y_start = boardid_to_xy(int(row['Moves_BoardID_From']))
                x_end, y_end = boardid_to_xy(int(row['Moves_BoardID_To']))
                color = colors[i % len(colors)]
                
                ax.arrow(x_start, y_start, x_end - x_start, y_end - y_start,
                        head_width=0.2, head_length=0.25, fc=color, ec=color, linewidth=2,
                        length_includes_head=True)
            
            st.pyplot(fig)
        
        # Detailed moves table
        st.subheader("Detailed Moves")
        display_data = participant_data[['Moves_Timestamp', 'Coin_Name', 'Moves_BoardID_From', 'Moves_BoardID_To']].copy()
        display_data['Moves_Timestamp'] = display_data['Moves_Timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        st.dataframe(display_data, use_container_width=True)

    # =====================================================================
    # TAB 6: COMMON PATTERNS
    # =====================================================================
    with tabs[4]:
        st.header("🎲 Common Movement Patterns")
        
        common_patterns = participant_moves['Movement_Pattern'].value_counts().head(10)
        
        # Classify patterns
        def is_failed_sequence(seq):
            moves = [m.strip() for m in seq.split('->')]
            for m in moves:
                parts = m.split()
                if len(parts) >= 7:
                    try:
                        from_grid = int(parts[4])
                        to_grid = int(parts[6])
                        if from_grid != to_grid:
                            return False
                    except ValueError:
                        return False
            return True
        
        pattern_data = []
        for pattern, count in common_patterns.items():
            is_failed = is_failed_sequence(pattern)
            pattern_data.append({
                'Pattern': pattern,
                'Count': count,
                'Status': 'Failed' if is_failed else 'Success'
            })
        
        pattern_df = pd.DataFrame(pattern_data)
        
        # Plot
        fig, ax = plt.subplots(figsize=(14, 8))
        colors_map = {'Success': '#81c784', 'Failed': '#e57373'}
        bar_colors = [colors_map[status] for status in pattern_df['Status']]
        
        ax.barh(range(len(pattern_df)), pattern_df['Count'], color=bar_colors)
        ax.set_yticks(range(len(pattern_df)))
        ax.set_yticklabels([f"{i+1}. {row['Pattern'][:60]}..." for i, row in pattern_df.iterrows()], fontsize=9)
        ax.set_xlabel('Number of Occurrences', fontsize=12)
        ax.set_title('Top 10 Common Movement Sequences', fontsize=14, fontweight='bold')
        ax.invert_yaxis()
        
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#81c784', label='Successful Moves'),
            Patch(facecolor='#e57373', label='Failed Moves')
        ]
        ax.legend(handles=legend_elements, loc='lower right')
        
        st.pyplot(fig)
        
        # Data table
        st.subheader("Pattern Details")
        st.dataframe(pattern_df, use_container_width=True)

    # =====================================================================
    # TAB 7: SUCCESS ANALYSIS
    # =====================================================================
    with tabs[5]:    
        st.subheader("🎯 Key Coins for Successful Movements")
        #st.info("This analysis shows which coins are most frequently moved in successful sequences")
        
        # Example data - you can calculate actual success rates if ProblemSolved column exists
        coin_success_counts = {
            'J': 1009,
            'D': 1017,
            'A': 1020,
        }
        
        colors = ['blue', 'orange', 'purple']
        
        fig, ax = plt.subplots(figsize=(8, 6))
        bars = ax.bar(coin_success_counts.keys(), coin_success_counts.values(), color=colors)
        
        # Add count labels on bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, height + 10, f'{int(height)}',
                    ha='center', fontsize=10, fontweight='bold')
        
        ax.set_title("Key Coins for Successful Movements", fontsize=14)
        ax.set_xlabel("Coin")
        ax.set_ylabel("Number of Moves")
        ax.set_ylim(0, max(coin_success_counts.values()) + 100)
        ax.grid(axis='y', linestyle='--', alpha=0.4)
        
        st.pyplot(fig)
        
        # Statistics
        st.subheader("Move Statistics by Coin")
        all_moves_list = participant_moves['Movement_Pattern'].str.split(' -> ').explode()
        coin_extract = all_moves_list.str.extract(r'Coin (\w)')
        coin_stats = coin_extract[0].value_counts().reset_index()
        coin_stats.columns = ['Coin', 'Total Moves']
        st.dataframe(coin_stats, use_container_width=True)

    # =====================================================================
    # TAB 8: MOVEMENT VISUALIZATION
    # =====================================================================


    with tabs[6]:

        st.header("🎥 Coin Movement Visualization (Optimized & Animated)")

        # ============================================================
        # 1) CACHED: Load movement data once per session
        # ============================================================
        @st.cache_data
        def load_movement_data():
            df = pd.read_excel(
                "C:/Users/tanma/OneDrive/Documents/GitHub/Coin-Project/combined_jun_sep.xlsx"
            )
            df = df[
                ["ID", "Moves_CoinID", "Moves_StartTime",
                "Moves_BoardID_From", "Moves_BoardID_To"]
            ].dropna(subset=["Moves_CoinID"])
            df["Moves_StartTime"] = pd.to_datetime(df["Moves_StartTime"], errors="coerce")
            return df

        df = load_movement_data()

        # Participant dropdown
        participant_ids = sorted(df["ID"].unique())
        selected_id = st.selectbox("Select Participant:", participant_ids)

        df_id = df[df["ID"] == selected_id].sort_values("Moves_StartTime")

        # ============================================================
        # 2) CONSTANT: Initial positions (9×7 grid = 63 cells)
        # ============================================================
        initial_positions = {
            "A": 19, "B": 21, "C": 23, "D": 25,
            "E": 29, "F": 31, "G": 33,
            "H": 39, "I": 41,
            "J": 49
        }

        # ============================================================
        # 3) Convert board cell index → X,Y coordinates (supports negative y)
        # ============================================================
        BASELINE_ROW = 3  # baseline row = 0, moves below = negative y

        def cell_to_xy(cell):
            x = cell % 9
            y = (cell // 9) - BASELINE_ROW  # baseline = 0
            return x, y

        # ============================================================
        # 4) Build animation frames (cached)
        # ============================================================
        @st.cache_data
        def build_animation_frames(df_id, initial_positions):
            current_positions = initial_positions.copy()
            frames = []

            # Frame 0: initial positions
            for coin, pos in current_positions.items():
                x, y = cell_to_xy(pos)
                frames.append({"frame": 0, "coin": coin, "x": x, "y": y})

            frame_count = 1

            # Subsequent frames: one per movement
            for _, row in df_id.iterrows():
                coin = row["Moves_CoinID"]
                dst = int(row["Moves_BoardID_To"])
                current_positions[coin] = dst

                for c, p in current_positions.items():
                    x, y = cell_to_xy(p)
                    frames.append({"frame": frame_count, "coin": c, "x": x, "y": y})

                frame_count += 1

            return pd.DataFrame(frames)

        movement_df = build_animation_frames(df_id, initial_positions)

        # ============================================================
        # 5) Determine y-axis limits dynamically
        # ============================================================
        ymin = movement_df['y'].min() - 1
        ymax = movement_df['y'].max() + 1

        # ============================================================
        # 6) Board layout configuration
        # ============================================================
        @st.cache_data
        def base_plot_layout(ymin, ymax):
            return dict(
                width=700,
                height=550,
                xaxis=dict(dtick=1, range=[-0.5, 8.5]),
                yaxis=dict(dtick=1, range=[ymin, ymax]),
                showlegend=True,
            )

        layout = base_plot_layout(ymin, ymax)

        # ============================================================
        # 7) Create Plotly animation
        # ============================================================
        fig = px.scatter(
            movement_df,
            x="x",
            y="y",
            animation_frame="frame",
            animation_group="coin",
            color="coin",
            hover_name="coin",
            range_x=[-1, 9],
            range_y=[ymin, ymax],
            size=[20] * len(movement_df),
            title=f"Animated Coin Movement — Participant {selected_id}"
        )

        fig.update_traces(marker=dict(size=18))
        fig.update_layout(**layout)
        fig.update_yaxes(scaleanchor="x")  # maintain square cells

        # Performance optimization
        try:
            fig.layout.updatemenus[0].buttons[0].args[1]["frame"]["redraw"] = False
        except:
            pass

        # ============================================================
        # 8) Display in Streamlit
        # ============================================================
        st.plotly_chart(fig, use_container_width=True)



# =====================================================================
# FOOTER
# =====================================================================
st.markdown("---")
st.caption("🪙 Copernicus Dashboard | Built with Streamlit")
