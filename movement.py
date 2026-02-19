import pandas as pd
import streamlit as st
import plotly.express as px

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