"""
Streamlit dashboard for hotel demand forecasting.
Shows forecast, events, and allows entering actual occupancy data.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path

# Database path
DB_PATH = Path("data/hotel.db")

# Page config
st.set_page_config(
    page_title="Hotel Demand Forecast",
    page_icon="🏨",
    layout="wide"
)


@st.cache_data(ttl=300)
def load_forecast_data():
    """Load forecast data for next 30 days"""
    if not DB_PATH.exists():
        return pd.DataFrame()

    conn = sqlite3.connect(DB_PATH)
    today = date.today()
    thirty_days = today + timedelta(days=30)

    query = """
    SELECT date, occupancy_pred, adr_pred, lower_bound, upper_bound
    FROM forecasts
    WHERE date >= ? AND date <= ?
    ORDER BY date
    """

    df = pd.read_sql_query(query, conn, params=(today.isoformat(), thirty_days.isoformat()))
    conn.close()

    if len(df) > 0:
        df['date'] = pd.to_datetime(df['date'])

    return df


@st.cache_data(ttl=300)
def load_upcoming_events():
    """Load upcoming events"""
    if not DB_PATH.exists():
        return pd.DataFrame()

    conn = sqlite3.connect(DB_PATH)
    today = date.today()

    query = """
    SELECT name, start_date, venue, impact_score, attendance_tier
    FROM events
    WHERE start_date >= ?
    ORDER BY start_date
    LIMIT 20
    """

    df = pd.read_sql_query(query, conn, params=(today.isoformat(),))
    conn.close()

    if len(df) > 0:
        df['start_date'] = pd.to_datetime(df['start_date'])

    return df


def save_actual_occupancy(date_val, occupancy_pct, adr_inr, rooms_sold):
    """Save actual occupancy data to database"""
    if not DB_PATH.exists():
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO daily_metrics (date, occupancy_pct, adr_inr, rooms_sold, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                occupancy_pct = excluded.occupancy_pct,
                adr_inr = excluded.adr_inr,
                rooms_sold = excluded.rooms_sold,
                updated_at = excluded.updated_at
        """, (date_val.isoformat(), occupancy_pct, adr_inr, rooms_sold, datetime.now().isoformat()))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error saving data: {e}")
        return False


def get_rate_recommendation(occupancy):
    """Get rate recommendation based on occupancy"""
    if occupancy > 80:
        return "Increase +20%"
    elif occupancy > 65:
        return "Hold rate"
    else:
        return "Offer discount"


def color_by_impact(row):
    """Color code rows by impact score"""
    if row['impact_score'] > 0.6:
        return ['background-color: #ffcccc'] * len(row)  # Red
    elif row['impact_score'] > 0.3:
        return ['background-color: #ffe5cc'] * len(row)  # Orange
    else:
        return ['background-color: #ccffcc'] * len(row)  # Green


# Sidebar
st.sidebar.title("🏨 Whitefield Hotel")
st.sidebar.write("**Demand Forecasting Dashboard**")
st.sidebar.write("")
st.sidebar.write(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# Main title
st.title("Hotel Demand Forecast Dashboard")
st.write("Real-time occupancy and ADR predictions for optimal revenue management")
st.divider()

# Load data
df_forecast = load_forecast_data()
df_events = load_upcoming_events()

# SECTION 1 - Header Metrics
st.subheader("📊 Forecast Summary (Next 30 Days)")

if len(df_forecast) > 0:
    col1, col2, col3, col4 = st.columns(4)

    avg_occupancy = df_forecast['occupancy_pred'].mean()
    avg_adr = df_forecast['adr_pred'].mean()
    peak_day = df_forecast.loc[df_forecast['occupancy_pred'].idxmax(), 'date'].strftime('%b %d')
    high_demand_days = len(df_forecast[df_forecast['occupancy_pred'] > 72])

    with col1:
        st.metric("Avg Forecast Occupancy", f"{avg_occupancy:.1f}%")

    with col2:
        st.metric("Avg Forecast ADR", f"₹{avg_adr:,.0f}")

    with col3:
        st.metric("Peak Day", peak_day)

    with col4:
        st.metric("High Demand Days (>80%)", high_demand_days)

else:
    st.warning("No forecast data available. Please run the prediction model first.")

st.divider()

# SECTION 2 - Forecast Chart
st.subheader("📈 30-Day Occupancy Forecast")

if len(df_forecast) > 0:
    # Prepare chart data
    chart_data = df_forecast.set_index('date')[['occupancy_pred', 'lower_bound', 'upper_bound']]
    chart_data.columns = ['Forecast', 'Lower Bound', 'Upper Bound']

    st.line_chart(chart_data)

    # Rate recommendation table
    st.subheader("💰 Rate Recommendations")

    df_recommendations = df_forecast.copy()
    df_recommendations['date'] = df_recommendations['date'].dt.strftime('%Y-%m-%d')
    df_recommendations['occupancy_pred'] = df_recommendations['occupancy_pred'].round(1)
    df_recommendations['adr_pred'] = df_recommendations['adr_pred'].round(0)
    df_recommendations['rate_recommendation'] = df_recommendations['occupancy_pred'].apply(
        get_rate_recommendation
    )

    st.dataframe(
        df_recommendations[['date', 'occupancy_pred', 'adr_pred', 'rate_recommendation']],
        use_container_width=True,
        hide_index=True
    )

else:
    st.info("No forecast data to display.")

st.divider()

# SECTION 3 - Two columns
col_left, col_right = st.columns(2)

# Left column - Upcoming Events
with col_left:
    st.subheader("📅 Upcoming Events")

    if len(df_events) > 0:
        df_events_display = df_events.copy()
        df_events_display['start_date'] = df_events_display['start_date'].dt.strftime('%Y-%m-%d')
        df_events_display['impact_score'] = df_events_display['impact_score'].round(2)

        # Apply color coding
        styled_df = df_events_display.style.apply(color_by_impact, axis=1)

        st.dataframe(
            styled_df,
            use_container_width=True,
            height=300,
            hide_index=True
        )
    else:
        st.info("No upcoming events found.")

# Right column - Enter Actual Occupancy
with col_right:
    st.subheader("✏️ Enter Actual Occupancy")

    with st.form("occupancy_form"):
        date_input = st.date_input(
            "Date",
            value=date.today(),
            max_value=date.today()
        )

        occupancy_input = st.number_input(
            "Occupancy %",
            min_value=0.0,
            max_value=100.0,
            value=75.0,
            step=0.1
        )

        adr_input = st.number_input(
            "ADR (INR)",
            min_value=0.0,
            value=7000.0,
            step=100.0
        )

        rooms_sold_input = st.number_input(
            "Rooms Sold",
            min_value=0,
            value=130,
            step=1
        )

        submitted = st.form_submit_button("💾 Save Actual Data")

        if submitted:
            success = save_actual_occupancy(
                date_input,
                occupancy_input,
                adr_input,
                rooms_sold_input
            )
            if success:
                st.success("✅ Saved! Data has been recorded.")
                # Clear cache to refresh data
                st.cache_data.clear()
            else:
                st.error("❌ Failed to save data. Please try again.")

# Footer
st.divider()
st.caption("Built with ❤️ for revenue optimization | Data updates every 5 minutes")
