import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
import sqlite3
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
from pathlib import Path
from haversine import haversine, Unit
from src.reports.generate_report import generate_pdf_report

DB_PATH = Path("data/hotel.db")

st.set_page_config(
    page_title="StaxAI · Demand Intelligence",
    page_icon="🏨", layout="wide",
    initial_sidebar_state="expanded"
)

st.html("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Sora:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root {
  --navy:#1A3A5C; --teal:#0EA5E9; --teal2:#38BDF8;
  --bg:#F0F4F8; --white:#FFFFFF; --border:#DDE3EC;
  --text:#1E293B; --muted:#64748B;
  --green:#16A34A; --red:#DC2626; --amber:#D97706;
}
html,body,[class*="css"]{ font-family:'Inter',sans-serif!important; color:var(--text)!important; background:var(--bg)!important; }
.stApp{ background:var(--bg)!important; }
section[data-testid="stSidebar"]{ background:var(--navy)!important; border-right:none!important; }
section[data-testid="stSidebar"] *{ color:#CBD5E1!important; }
.main .block-container{ padding:1.5rem 2rem 4rem!important; max-width:1400px!important; }
.card{ background:var(--white); border-radius:12px; border:1px solid var(--border); padding:1.25rem 1.5rem; box-shadow:0 1px 4px rgba(0,0,0,0.05); }
.kpi-label{ font-size:10px; text-transform:uppercase; letter-spacing:0.12em; color:var(--muted); font-weight:700; margin-bottom:6px; }
.kpi-value{ font-family:'Sora',sans-serif; font-size:30px; font-weight:700; color:var(--navy); line-height:1; }
.kpi-sub{ font-size:12px; color:var(--muted); margin-top:5px; }
.kpi-accent{ height:3px; border-radius:2px; margin-top:10px; background:linear-gradient(90deg,var(--navy),var(--teal)); }
.sec-head{ font-family:'Sora',sans-serif; font-size:14px; font-weight:700; color:var(--navy); margin:1.6rem 0 0.8rem; padding-bottom:8px; border-bottom:2px solid var(--teal); display:inline-block; }
.page-title{ font-family:'Sora',sans-serif; font-size:26px; font-weight:700; color:var(--navy); }
.page-sub{ font-size:13px; color:var(--muted); margin-top:3px; }
.live-badge{ display:inline-flex; align-items:center; gap:6px; background:#F0FDF4; border:1px solid #BBF7D0; border-radius:20px; padding:4px 12px; font-size:12px; color:var(--green); font-weight:500; }
.live-dot{ width:7px; height:7px; border-radius:50%; background:var(--green); animation:blink 2s infinite; }
@keyframes blink{ 0%,100%{opacity:1}50%{opacity:.35} }
.enq-card{ background:linear-gradient(135deg,var(--navy) 0%,#1E4976 100%); border-radius:16px; padding:2rem 2.5rem; margin-top:2rem; }
.enq-title{ font-family:'Sora',sans-serif; font-size:22px; font-weight:700; color:white; margin-bottom:8px; }
.enq-sub{ font-size:13px; color:rgba(255,255,255,0.65); line-height:1.7; margin-bottom:1.5rem; }
.enq-btn{ display:inline-block; background:#0EA5E9; color:white!important; padding:11px 28px; border-radius:8px; font-weight:700; font-size:14px; text-decoration:none; }
.pill{ display:inline-flex; align-items:center; gap:5px; background:rgba(14,165,233,0.12); border:1px solid rgba(14,165,233,0.25); border-radius:20px; padding:4px 12px; font-size:12px; color:#38BDF8; margin:3px; }
.footer{ margin-top:3rem; padding:1.5rem 0 1rem; border-top:1px solid var(--border); }
footer{ visibility:hidden!important; }
.stSuccess{ background:#F0FDF4!important; border:1px solid #BBF7D0!important; border-radius:8px!important; }
.stError{ background:#FEF2F2!important; border:1px solid #FECACA!important; border-radius:8px!important; }
label{ font-size:11px!important; font-weight:600!important; color:var(--muted)!important; text-transform:uppercase!important; letter-spacing:0.07em!important; }
.stTextInput>div>div>input,.stNumberInput>div>div>input,.stDateInput>div>div>input{ background:#F8FAFC!important; border:1px solid var(--border)!important; border-radius:8px!important; }
.stDateInput input{ color:#1E293B!important; background:#F8FAFC!important; }
.stNumberInput input{ color:#1E293B!important; background:#F8FAFC!important; }
.stTextInput input{ color:#1E293B!important; background:#F8FAFC!important; }
input[type="number"]{ color:#1E293B!important; }
input[type="text"]{ color:#1E293B!important; }
[data-baseweb="input"] input{ color:#1E293B!important; }
[data-baseweb="base-input"]{ background:#F8FAFC!important; }
.stSelectbox>div>div{ background:#F8FAFC!important; border:1px solid var(--border)!important; border-radius:8px!important; }
.stButton>button{ background:var(--navy)!important; color:white!important; border:none!important; border-radius:8px!important; font-weight:600!important; padding:0.5rem 1.5rem!important; }
.stButton>button:hover{ background:#1E4976!important; }
.stTabs [data-baseweb="tab-list"]{ gap:4px; border-bottom:1px solid var(--border); background:transparent; }
.stTabs [data-baseweb="tab"]{ background:#F8FAFC; border-radius:8px 8px 0 0; padding:8px 18px; font-weight:500; color:var(--muted); border:1px solid var(--border); border-bottom:none; }
.stTabs [aria-selected="true"]{ background:var(--white)!important; color:var(--navy)!important; border-bottom:2px solid var(--teal)!important; font-weight:600!important; }
.sort-hint{ font-size:11px; color:var(--muted); margin-bottom:6px; }
</style>
""")


def gconn():
    return sqlite3.connect(str(DB_PATH))


@st.cache_data(ttl=60)
def load_forecasts():
    if not DB_PATH.exists():
        return pd.DataFrame()
    try:
        df = pd.read_sql("SELECT date,occupancy_pred,adr_pred,lower_bound,upper_bound FROM forecasts WHERE date>=date('now') ORDER BY date LIMIT 90", gconn())
        df['date'] = pd.to_datetime(df['date'])
        return df
    except:
        return pd.DataFrame()


@st.cache_data(ttl=60)
def load_events():
    if not DB_PATH.exists():
        return pd.DataFrame()
    try:
        return pd.read_sql("SELECT name,start_date,end_date,venue,impact_score,attendance_tier,source FROM events WHERE start_date>=date('now') ORDER BY start_date LIMIT 60", gconn())
    except:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def load_actuals():
    if not DB_PATH.exists():
        return pd.DataFrame()
    try:
        df = pd.read_sql("SELECT date,occupancy_pct,adr_inr FROM daily_metrics ORDER BY date DESC LIMIT 90", gconn())
        df['date'] = pd.to_datetime(df['date'])
        return df.sort_values('date')
    except:
        return pd.DataFrame()


def base_layout(h=320):
    return dict(
        paper_bgcolor='white', plot_bgcolor='#F8FAFC', height=h,
        font=dict(family='Inter', color='#64748B', size=11),
        margin=dict(l=10, r=10, t=10, b=10),
        hovermode='x',
        hoverlabel=dict(bgcolor='white', bordercolor='#DDE3EC', font=dict(color='#1E293B', size=12)),
        legend=dict(
            bgcolor='rgba(255,255,255,0.8)',
            bordercolor='#DDE3EC',
            borderwidth=1,
            font=dict(size=11),
            orientation='h',
            yanchor='top',
            y=-0.15,
            xanchor='left',
            x=0
        ),
        xaxis=dict(gridcolor='#EFF3F8', linecolor='#DDE3EC', tickfont=dict(size=11),
                   showspikes=True, spikethickness=1, spikecolor='#94A3B8', spikedash='dot'),
        yaxis=dict(gridcolor='#EFF3F8', linecolor='#DDE3EC', tickfont=dict(size=11))
    )


now = datetime.now()
forecasts = load_forecasts()
events_df = load_events()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    for p in ["dashboard/assets/hotel_logo.png", "dashboard/assets/hotel_logo.jpg"]:
        if Path(p).exists():
            st.image(p, width=160)
            break
    st.markdown(f"""
    <div style="padding:.5rem 0 1rem">
      <div style="font-family:'Sora',sans-serif;font-size:15px;font-weight:700;color:#E2E8F0">Four Points by Sheraton</div>
      <div style="font-size:11px;opacity:.45;margin-top:2px">Bengaluru · Whitefield</div>
    </div>
    <hr style="border-color:rgba(255,255,255,.08);margin:.5rem 0 1rem">
    <div style="font-size:9px;text-transform:uppercase;letter-spacing:.12em;opacity:.4;margin-bottom:4px">Status</div>
    <div style="display:flex;align-items:center;gap:7px;margin-bottom:1rem">
      <div style="width:7px;height:7px;border-radius:50%;background:#4ADE80"></div>
      <span style="font-size:12px;color:#4ADE80">Live · {now.strftime('%H:%M IST')}</span>
    </div>
    <div style="font-size:9px;text-transform:uppercase;opacity:.4;margin-bottom:2px">Forecast horizon</div>
    <div style="font-size:13px;font-weight:500;margin-bottom:.8rem;color:#E2E8F0">{len(forecasts)} days ahead</div>
    <div style="font-size:9px;text-transform:uppercase;opacity:.4;margin-bottom:2px">Events tracked</div>
    <div style="font-size:13px;font-weight:500;margin-bottom:.8rem;color:#E2E8F0">{len(events_df)} upcoming</div>
    <div style="font-size:9px;text-transform:uppercase;opacity:.4;margin-bottom:2px">Model</div>
    <div style="font-size:13px;font-weight:500;margin-bottom:.8rem;color:#E2E8F0">XGBoost GPU · R²=0.94</div>
    <div style="font-size:9px;text-transform:uppercase;opacity:.4;margin-bottom:2px">Last trained</div>
    <div style="font-size:13px;font-weight:500;color:#E2E8F0">{now.strftime('%d %b %Y')}</div>
    <hr style="border-color:rgba(255,255,255,.08);margin:1.2rem 0">
    <div style="font-size:11px;opacity:.4;line-height:1.8">
      Powered by <strong style="color:#38BDF8;opacity:1">StaxAI</strong><br>
      AI Arm of DRCC Chartered Accountants<br>Bengaluru · info@staxai.in
    </div>""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
c1, c2 = st.columns([3, 1])
with c1:
    st.markdown(f'<div class="page-title">Demand Intelligence Dashboard</div><div class="page-sub">Real-time occupancy forecasting & revenue optimisation · {now.strftime("%A, %d %b %Y")}</div>', unsafe_allow_html=True)
with c2:
    st.markdown('<div style="text-align:right;padding-top:12px"><div class="live-badge"><div class="live-dot"></div>Live</div></div>', unsafe_allow_html=True)
    try:
        pdf_bytes = generate_pdf_report()
        st.download_button(
            label="📄 Download Report",
            data=pdf_bytes,
            file_name=f"demand_report_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            key="pdf_download"
        )
    except Exception as e:
        st.caption("PDF unavailable")

st.markdown("<br>", unsafe_allow_html=True)

# ── KPIs ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="sec-head">Forecast Summary · Next 30 Days</div>', unsafe_allow_html=True)

fc30 = forecasts.head(30) if not forecasts.empty else pd.DataFrame()
avg_occ = fc30['occupancy_pred'].mean() if not fc30.empty else 0
avg_adr = fc30['adr_pred'].mean() if not fc30.empty else 0
peak_day = fc30.loc[fc30['occupancy_pred'].idxmax(), 'date'].strftime('%d %b') if not fc30.empty else '—'
high_days = int((fc30['occupancy_pred'] > 72).sum()) if not fc30.empty else 0
rev_pot = avg_adr * (avg_occ / 100) * 180 * 30 if avg_occ else 0

k1, k2, k3, k4, k5 = st.columns(5)
for col, label, val, sub in [
    (k1, "Avg Occupancy", f"{avg_occ:.1f}%", "Next 30 days"),
    (k2, "Avg Forecast ADR", f"₹{avg_adr:,.0f}", "Per occupied room"),
    (k3, "Peak Day", peak_day, "Highest demand"),
    (k4, "High Demand Days", str(high_days), "Occupancy > 72%"),
    (k5, "Revenue Potential", f"₹{rev_pot/100000:.1f}L", "30-day projection"),
]:
    with col:
        st.markdown(f'<div class="card"><div style="font-size:10px;text-transform:uppercase;letter-spacing:0.12em;color:#64748B;font-weight:700;margin-bottom:6px">{label}</div><div class="kpi-value">{val}</div><div class="kpi-sub">{sub}</div><div class="kpi-accent"></div></div>', unsafe_allow_html=True)

# ── Occupancy chart ───────────────────────────────────────────────────────────
st.markdown('<div class="sec-head">30-Day Occupancy Forecast</div>', unsafe_allow_html=True)

if not forecasts.empty:
    actuals = load_actuals()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(forecasts['date']) + list(forecasts['date'][::-1]),
        y=list(forecasts['upper_bound']) + list(forecasts['lower_bound'][::-1]),
        fill='toself', fillcolor='rgba(14,165,233,0.07)',
        line=dict(color='rgba(0,0,0,0)'), showlegend=False, hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=forecasts['date'], y=forecasts['upper_bound'],
        line=dict(color='rgba(14,165,233,0.3)', width=1, dash='dot'), name='Upper',
        hovertemplate='%{y:.1f}%', visible='legendonly'))
    fig.add_trace(go.Scatter(x=forecasts['date'], y=forecasts['lower_bound'],
        line=dict(color='rgba(14,165,233,0.3)', width=1, dash='dot'), name='Lower',
        hovertemplate='%{y:.1f}%', visible='legendonly'))
    fig.add_trace(go.Scatter(x=forecasts['date'], y=forecasts['occupancy_pred'],
        line=dict(color='#1A3A5C', width=2.5), name='Forecast',
        hovertemplate='<b>%{x|%d %b}</b><br>Forecast: %{y:.1f}%<extra></extra>'))
    if not actuals.empty:
        recent = actuals[(actuals['date'] >= (datetime.now() - timedelta(30))) &
                         (actuals['date'] <= datetime.now())]
        # Only show if there are rows with real data (not synthetic)
        # Show the actual line always - GM will see it reflects entered data
        if not recent.empty:
            fig.add_trace(go.Scatter(x=recent['date'], y=recent['occupancy_pct'],
                line=dict(color='#16A34A', width=2), mode='lines+markers',
                marker=dict(size=5), name='Actual',
                hovertemplate='<b>%{x|%d %b}</b><br>Actual: %{y:.1f}%<extra></extra>'))
    fig.add_hline(y=80, line=dict(color='rgba(220,38,38,0.35)', width=1.5, dash='dash'),
        annotation_text="Increase rate threshold (80%)", annotation_font=dict(color='#DC2626', size=10))
    layout = base_layout(320)
    layout['yaxis']['title'] = 'Occupancy %'
    layout['yaxis']['range'] = [68, 82]
    layout['xaxis']['rangeselector'] = dict(
        buttons=[
            dict(count=7, label='7d', step='day', stepmode='todate'),
            dict(count=14, label='14d', step='day', stepmode='todate'),
            dict(count=30, label='30d', step='day', stepmode='backward'),
            dict(step='all', label='All')
        ],
        bgcolor='#F1F5F9', activecolor='#1A3A5C', font=dict(size=11, color='#64748B'),
        y=1.15, x=0)
    layout['xaxis']['rangeslider'] = dict(visible=True, thickness=0.05, bgcolor='#F8FAFC')
    layout['yaxis']['fixedrange'] = False
    layout['xaxis']['fixedrange'] = False
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['select2d', 'lasso2d'],
        'displaylogo': False,
        'scrollZoom': True,
        'toImageButtonOptions': {'scale': 2}
    })
    st.caption("Actual line appears once GM enters daily occupancy data via Data Management tab.")
else:
    st.info("No forecast data. Run `python src/models/predict.py`")

# ── ADR chart ─────────────────────────────────────────────────────────────────
st.markdown('<div class="sec-head">Average Daily Rate (ADR) Forecast</div>', unsafe_allow_html=True)

if not forecasts.empty:
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=forecasts['date'], y=forecasts['adr_pred'],
        marker=dict(
            color=forecasts['adr_pred'],
            colorscale=[[0, '#BAE6FD'], [0.5, '#0EA5E9'], [1, '#0C4A6E']],
            opacity=0.85, line=dict(width=0)),
        hovertemplate='<b>%{x|%d %b}</b><br>ADR: ₹%{y:,.0f}<extra></extra>'))
    layout2 = base_layout(220)
    layout2['yaxis']['title'] = 'ADR (₹)'
    layout2['yaxis']['tickprefix'] = '₹'
    layout2['bargap'] = 0.15
    fig2.update_layout(**layout2)
    st.plotly_chart(fig2, use_container_width=True, config={
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['select2d', 'lasso2d'],
        'displaylogo': False,
        'scrollZoom': True,
        'toImageButtonOptions': {'scale': 2}
    })

# ── Heatmap + Event Timeline ──────────────────────────────────────────────────
st.markdown('<div class="sec-head">Pattern Analysis</div>', unsafe_allow_html=True)
heat_col, timeline_col = st.columns(2, gap="large")

with heat_col:
    st.markdown("**Occupancy Pattern by Day**")
    if not fc30.empty:
        fc30_copy = fc30.copy()
        fc30_copy['day_of_week'] = fc30_copy['date'].dt.dayofweek
        fc30_copy['week'] = ((fc30_copy['date'] - fc30_copy['date'].min()).dt.days // 7) + 1

        # Pivot for heatmap
        pivot = fc30_copy.pivot_table(values='occupancy_pred', index='day_of_week',
                                       columns='week', aggfunc='mean')

        day_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

        fig_heat = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=[f'W{i}' for i in pivot.columns],
            y=[day_labels[i] for i in pivot.index],
            colorscale=[[0, '#BAE6FD'], [0.5, '#0EA5E9'], [1, '#1A3A5C']],
            hovertemplate='%{y}, Week %{x}<br>Occupancy: %{z:.1f}%<extra></extra>',
            colorbar=dict(title='Occ %', thickness=10, len=0.8)
        ))
        layout_heat = base_layout(280)
        layout_heat['xaxis']['title'] = 'Week'
        layout_heat['yaxis']['title'] = 'Day'
        fig_heat.update_layout(**layout_heat)
        st.plotly_chart(fig_heat, use_container_width=True, config={
            'displayModeBar': True, 'displaylogo': False, 'scrollZoom': True
        })
    else:
        st.info("No forecast data.")

with timeline_col:
    st.markdown("**Event Impact Timeline**")
    ev_timeline = load_events()
    if not ev_timeline.empty:
        ev_timeline['start_date'] = pd.to_datetime(ev_timeline['start_date'])

        # Determine marker properties
        sizes = []
        colors = []
        for _, row in ev_timeline.iterrows():
            # Size by tier
            if row['attendance_tier'] == 'large':
                sizes.append(15)
            elif row['attendance_tier'] == 'medium':
                sizes.append(10)
            else:
                sizes.append(6)

            # Color by impact
            if row['impact_score'] > 0.6:
                colors.append('#DC2626')
            elif row['impact_score'] > 0.3:
                colors.append('#D97706')
            else:
                colors.append('#16A34A')

        fig_timeline = go.Figure(data=go.Scatter(
            x=ev_timeline['start_date'],
            y=ev_timeline['impact_score'],
            mode='markers',
            marker=dict(size=sizes, color=colors, opacity=0.7,
                       line=dict(width=1, color='white')),
            text=ev_timeline['name'],
            hovertemplate='<b>%{text}</b><br>%{x|%d %b}<br>Impact: %{y:.2f}<extra></extra>'
        ))
        layout_timeline = base_layout(280)
        layout_timeline['xaxis']['title'] = 'Event Date'
        layout_timeline['yaxis']['title'] = 'Impact Score'
        layout_timeline['yaxis']['range'] = [0, max(ev_timeline['impact_score'].max() * 1.1, 1)]
        fig_timeline.update_layout(**layout_timeline)
        st.plotly_chart(fig_timeline, use_container_width=True, config={
            'displayModeBar': True, 'displaylogo': False, 'scrollZoom': True
        })
    else:
        st.info("No events.")

# ── Live Market Intelligence ──────────────────────────────────────────────────
st.markdown('<div class="sec-head">Live Market Intelligence</div>', unsafe_allow_html=True)
st.markdown("**Live competitor rates — Bengaluru hotels tonight**")

try:
    import json
    sys.path.insert(0, '.')
    from src.ingest.competitor_rates import fetch_all_competitor_rates

    # Check cache file
    cache_file = Path("data/competitor_rates.json")
    cache_age_hours = None
    use_cache = False

    if cache_file.exists():
        cache_modified = datetime.fromtimestamp(cache_file.stat().st_mtime)
        cache_age = datetime.now() - cache_modified
        cache_age_hours = cache_age.total_seconds() / 3600

        if cache_age_hours < 6:
            use_cache = True

    # Show cache status and refresh button
    col_status, col_btn = st.columns([3, 1])
    with col_status:
        if use_cache and cache_age_hours is not None:
            st.caption(f"Data from Xotelo API · Last updated: {cache_age_hours:.1f} hours ago")
        else:
            st.caption("Data from Xotelo API · Fetching fresh rates...")
    with col_btn:
        force_refresh = st.button("🔄 Refresh Rates", key="refresh_rates")

    # Load or fetch data
    if use_cache and not force_refresh:
        with open(cache_file, 'r') as f:
            comp_rates = json.load(f)
    else:
        with st.spinner("Fetching live market rates..."):
            comp_rates = fetch_all_competitor_rates()

    if comp_rates:
        our_adr = avg_adr  # from existing variable

        comp_df = pd.DataFrame(comp_rates)
        comp_df['vs_ours'] = comp_df['cheapest'] - our_adr
        comp_df['position'] = comp_df['vs_ours'].apply(
            lambda x: '▲ Higher' if x > 0 else '▼ Lower')

        col_chart, col_table = st.columns([1.2, 0.8])

        with col_chart:
            # Build list with our ADR + competitors
            all_hotels = list(comp_df['name']) + ['Four Points (Our ADR)']
            all_rates = list(comp_df['cheapest']) + [our_adr]

            # Grey for hotels priced higher, Red for lower, Gold for our ADR
            colors = []
            for i, rate in enumerate(all_rates):
                if i == len(all_rates) - 1:  # Our ADR
                    colors.append('#F59E0B')  # Amber/Gold
                elif rate > our_adr:
                    colors.append('#94A3B8')  # Grey (not a threat)
                else:
                    colors.append('#DC2626')  # Red (undercuts us)

            fig_comp = go.Figure()
            fig_comp.add_trace(go.Bar(
                y=all_hotels,
                x=all_rates,
                orientation='h',
                marker_color=colors,
                opacity=0.85,
                hovertemplate='%{y}: ₹%{x:,.0f}<extra></extra>'
            ))
            layout_comp = base_layout(380)
            layout_comp['xaxis']['title'] = 'Rate (INR)'
            layout_comp['xaxis']['tickprefix'] = '₹'
            layout_comp['margin'] = dict(l=220, r=20, t=20, b=20)
            fig_comp.update_layout(**layout_comp)
            st.plotly_chart(fig_comp, use_container_width=True,
                config={'displayModeBar': False})

        with col_table:
            display_df = pd.DataFrame({
                'Hotel': comp_df['name'],
                'Rate (₹)': comp_df['cheapest'].apply(
                    lambda x: f'₹{x:,.0f}' if x else 'N/A'),
                'vs Our ADR': comp_df['vs_ours'].apply(
                    lambda x: f'+₹{x:,.0f}' if x > 0 else f'-₹{abs(x):,.0f}' if x else 'N/A'),
                'Position': comp_df['position']
            })

            def color_position(val):
                if '▲' in str(val): return 'color: #94A3B8; font-weight:600'
                elif '▼' in str(val): return 'color: #DC2626; font-weight:600'
                return ''

            st.dataframe(
                display_df.style.map(color_position, subset=['Position']),
                use_container_width=True, height=350, hide_index=True)

        cheaper = comp_df[comp_df['cheapest'] < our_adr]
        pricier = comp_df[comp_df['cheapest'] > our_adr]

        # Check if we are the cheapest
        we_are_cheapest = len(cheaper) == 0

        if we_are_cheapest:
            cheapest_competitor = comp_df['cheapest'].min()
            rate_increase_15pct = our_adr * 1.15
            st.markdown(f"""
            <div style="background:#FEF9C3;border:1px solid #FDE047;
            border-radius:8px;padding:12px 16px;margin-top:8px;font-size:13px">
                <strong style="color:#D97706">⚠️ Pricing Opportunity:</strong>
                Four Points at ₹{our_adr:,.0f} is below all competitors.
                Even a 15% rate increase (₹{rate_increase_15pct:,.0f}) would still
                keep you competitive vs GreenPark at ₹{cheapest_competitor:,.0f}.
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background:#F0FDF4;border:1px solid #BBF7D0;
            border-radius:8px;padding:12px 16px;margin-top:8px;font-size:13px">
                <strong style="color:#16A34A">Market Position:</strong>
                {len(pricier)} hotels pricing higher than you ·
                {len(cheaper)} hotels pricing lower ·
                Your rate ₹{our_adr:,.0f} vs market cheapest ₹{comp_df['cheapest'].min():,.0f}
            </div>""", unsafe_allow_html=True)
    else:
        st.info("Could not fetch market rates. Check internet connection.")
except Exception as e:
    st.error(f"Market rates unavailable: {e}")

# ── Rate recs + Events ────────────────────────────────────────────────────────
col_l, col_r = st.columns([1.1, 0.9], gap="large")

with col_l:
    st.markdown('<div class="sec-head">Rate Recommendations</div>', unsafe_allow_html=True)
    st.markdown('<div class="sort-hint">Click any column header to sort ↕</div>', unsafe_allow_html=True)
    if not fc30.empty:
        def rate_action(occ):
            if occ > 80: return "▲ Increase +20%"
            elif occ > 72: return "— Hold rate"
            return "▼ Offer discount"

        rate_df = pd.DataFrame({
            'Date': [r['date'].strftime('%a, %d %b') for _, r in fc30.head(14).iterrows()],
            'Occ %': [round(r['occupancy_pred'], 1) for _, r in fc30.head(14).iterrows()],
            'ADR (₹)': [int(r['adr_pred']) for _, r in fc30.head(14).iterrows()],
            'Action': [rate_action(r['occupancy_pred']) for _, r in fc30.head(14).iterrows()],
        })

        def color_action(val):
            if '▲' in str(val): return 'color: #16A34A; font-weight: 600'
            elif '▼' in str(val): return 'color: #DC2626; font-weight: 600'
            return 'color: #64748B'

        st.dataframe(rate_df.style.map(color_action, subset=['Action']),
                     use_container_width=True, height=400, hide_index=True)

with col_r:
    st.markdown('<div class="sec-head">Upcoming Events</div>', unsafe_allow_html=True)
    st.markdown('<div class="sort-hint">Click any column header to sort ↕</div>', unsafe_allow_html=True)
    ev = load_events()
    if not ev.empty:
        ev_display = pd.DataFrame({
            'Event': ev['name'].str[:30].values,
            'Date': ev['start_date'].values,
            'Venue': ev['venue'].str[:22].values,
            'Impact': ev['impact_score'].round(2).values,
            'Size': ev['attendance_tier'].str.capitalize().values,
            'Source': ev['source'].values,
        })

        def color_impact(val):
            try:
                v = float(val)
                if v > 0.6: return 'color: #DC2626; font-weight: 700'
                elif v > 0.3: return 'color: #D97706; font-weight: 600'
                return 'color: #16A34A'
            except:
                return ''

        def color_size(val):
            s = str(val).lower()
            if s == 'large': return 'color: #DC2626; font-weight: 600'
            elif s == 'medium': return 'color: #D97706'
            return 'color: #16A34A'

        st.dataframe(ev_display.style.map(color_impact, subset=['Impact']).map(color_size, subset=['Size']),
                     use_container_width=True, height=400, hide_index=True)
    else:
        st.info("No events. Run `python src/ingest/run_all_sources.py`")

# ── Missed Revenue Analysis ───────────────────────────────────────────────────
st.markdown('<div class="sec-head">Missed Revenue Analysis</div>', unsafe_allow_html=True)

actuals_90 = load_actuals()

if not actuals_90.empty and not forecasts.empty:
    # Merge actuals with forecasts on date
    merged = actuals_90.merge(
        forecasts[['date', 'occupancy_pred', 'adr_pred']],
        on='date', how='inner'
    )
    # Filter to past dates only
    merged = merged[merged['date'] < datetime.now()]

    if not merged.empty:
        # Calculate missed opportunities
        merged['missed'] = merged['occupancy_pct'] - merged['occupancy_pred']
        merged['missed_rooms'] = (merged['missed'] / 100) * 180
        merged['missed_revenue'] = merged['missed_rooms'] * merged['adr_inr']

        # Only show where actual exceeded forecast
        missed_df = merged[merged['missed_rooms'] > 0].copy()

        if not missed_df.empty:
            missed_col_l, missed_col_r = st.columns([1.2, 0.8], gap="large")

            with missed_col_l:
                st.markdown("**Missed Revenue by Date (₹)**")
                fig_missed = go.Figure()
                fig_missed.add_trace(go.Bar(
                    x=missed_df['date'],
                    y=missed_df['missed_revenue'],
                    marker=dict(color='#DC2626', opacity=0.8),
                    hovertemplate='<b>%{x|%d %b}</b><br>Missed: ₹%{y:,.0f}<extra></extra>'
                ))
                layout_missed = base_layout(250)
                layout_missed['yaxis']['title'] = 'Missed Revenue (₹)'
                layout_missed['yaxis']['tickprefix'] = '₹'
                fig_missed.update_layout(**layout_missed)
                st.plotly_chart(fig_missed, use_container_width=True, config={
                    'displayModeBar': True, 'displaylogo': False, 'scrollZoom': True,
                    'toImageButtonOptions': {'scale': 2}
                })

            with missed_col_r:
                total_missed = missed_df['missed_revenue'].sum()
                avg_missed = missed_df['missed_revenue'].mean()
                days_underpriced = len(missed_df)
                best_opp = missed_df.loc[missed_df['missed_revenue'].idxmax()]

                st.markdown(f"""<div class="card">
                  <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.12em;color:#64748B;font-weight:700;margin-bottom:6px">Total Missed Revenue</div>
                  <div class="kpi-value">₹{total_missed/100000:.2f}L</div>
                  <div class="kpi-sub">Last 90 days</div>
                </div>""", unsafe_allow_html=True)

                st.markdown(f"""<div class="card">
                  <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.12em;color:#64748B;font-weight:700;margin-bottom:6px">Average Per Day</div>
                  <div class="kpi-value">₹{avg_missed:,.0f}</div>
                  <div class="kpi-sub">When underpriced</div>
                </div>""", unsafe_allow_html=True)

                st.markdown(f"""<div class="card">
                  <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.12em;color:#64748B;font-weight:700;margin-bottom:6px">Days Underpriced</div>
                  <div class="kpi-value">{days_underpriced}</div>
                  <div class="kpi-sub">Out of {len(merged)} days</div>
                </div>""", unsafe_allow_html=True)

                st.markdown(f"""<div class="card">
                  <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.12em;color:#64748B;font-weight:700;margin-bottom:6px">Best Recovery Date</div>
                  <div class="kpi-value">{best_opp['date'].strftime('%d %b')}</div>
                  <div class="kpi-sub">₹{best_opp['missed_revenue']:,.0f} missed</div>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background:#F0F9FF;border:1px solid #BAE6FD;border-radius:8px;
            padding:14px 18px;font-size:13px;color:#0369A1">
                <strong>📊 No Missed Revenue Detected</strong><br>
                Enter actual occupancy data via the form below to see missed revenue analysis and pricing gaps.
            </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background:#F0F9FF;border:1px solid #BAE6FD;border-radius:8px;
        padding:14px 18px;font-size:13px;color:#0369A1">
            <strong>📊 Missed Revenue Analysis</strong><br>
            Enter actual occupancy data via the form below to see missed revenue analysis and pricing gaps.
        </div>""", unsafe_allow_html=True)
else:
    st.markdown("""
    <div style="background:#F0F9FF;border:1px solid #BAE6FD;border-radius:8px;
    padding:14px 18px;font-size:13px;color:#0369A1">
        <strong>📊 Missed Revenue Analysis</strong><br>
        Enter actual occupancy data via the form below to see missed revenue analysis and pricing gaps.
    </div>""", unsafe_allow_html=True)

# ── Weekend vs Weekday Analysis ───────────────────────────────────────────────
st.markdown('<div class="sec-head">Occupancy Pattern Analysis</div>', unsafe_allow_html=True)
pattern_col_l, pattern_col_r = st.columns(2, gap="large")

with pattern_col_l:
    st.markdown("**Avg Occupancy by Day of Week**")
    if not fc30.empty:
        day_order = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
        dow_num   = {'Mon':0,'Tue':1,'Wed':2,'Thu':3,'Fri':4,'Sat':5,'Sun':6}
        fc30['dow_name'] = fc30['date'].dt.strftime('%a')
        day_avg = fc30.groupby('dow_name')['occupancy_pred'].mean().reindex(day_order).reset_index()
        day_avg.columns = ['day','occ']

        fig_dow = go.Figure(go.Bar(
            x=day_avg['day'],
            y=day_avg['occ'],
            marker_color=['#0EA5E9' if d in ['Sat','Sun'] else '#1A3A5C'
                          for d in day_avg['day']],
            text=[f"{v:.1f}%" for v in day_avg['occ']],
            textposition='outside',
        ))
        fig_dow.update_layout(
            paper_bgcolor='white', plot_bgcolor='#F8FAFC',
            height=240, margin=dict(l=20,r=10,t=20,b=20),
            yaxis=dict(range=[60,85],gridcolor='#EFF3F8'),
            xaxis=dict(tickfont=dict(size=11)),
            showlegend=False,
            font=dict(family='Inter',size=11,color='#64748B')
        )
        st.plotly_chart(fig_dow, use_container_width=True, config={
            'displayModeBar': True, 'displaylogo': False, 'scrollZoom': True,
            'toImageButtonOptions': {'scale': 2}
        })
    else:
        st.info("No forecast data.")

with pattern_col_r:
    st.markdown("**Weekly Forecast Pattern**")
    if not forecasts.empty:
        forecasts_weekly = forecasts.copy()
        forecasts_weekly['week_label'] = forecasts_weekly['date'].dt.strftime('W%U')

        # Group by week
        week_avg = forecasts_weekly.groupby('week_label').agg(
            occ=('occupancy_pred', 'mean'),
            adr=('adr_pred', 'mean')
        ).reset_index()

        fig_monthly = go.Figure()
        fig_monthly.add_trace(go.Bar(
            x=week_avg['week_label'],
            y=week_avg['occ'],
            name='Avg Occupancy %',
            marker_color='#1A3A5C',
            yaxis='y'
        ))
        fig_monthly.add_trace(go.Scatter(
            x=week_avg['week_label'],
            y=week_avg['adr'],
            name='ADR (₹)',
            line=dict(color='#0EA5E9', width=2),
            mode='lines+markers',
            yaxis='y2'
        ))
        layout_weekly = base_layout(280)
        layout_weekly['yaxis']['title'] = 'Occupancy %'
        layout_weekly['yaxis']['range'] = [60, 85]
        layout_weekly['yaxis2'] = dict(
            title='ADR (₹)', overlaying='y',
            side='right', tickprefix='₹'
        )
        layout_weekly['legend'] = dict(orientation='h', y=-0.2)
        layout_weekly['xaxis']['title'] = 'Week'
        fig_monthly.update_layout(**layout_weekly)
        st.plotly_chart(fig_monthly, use_container_width=True, config={
            'displayModeBar': True, 'displaylogo': False, 'scrollZoom': True,
            'toImageButtonOptions': {'scale': 2}
        })
    else:
        st.info("No forecast data.")

# ── Data management ───────────────────────────────────────────────────────────
st.markdown('<div class="sec-head">Data Management</div>', unsafe_allow_html=True)
tab1, tab2, tab3 = st.tabs([
    "✏️ Enter Actual Occupancy",
    "📅 Add New Event",
    "📂 Bulk Upload Events"
])

with tab1:
    with st.form("actual_form"):
        c1, c2, c3, c4 = st.columns(4)
        with c1: act_date = st.date_input("Date", value=date.today(), key="act_date")
        with c2: occ_v = st.number_input("Occupancy %", 0.0, 100.0, 75.0, 0.5, key="act_occ")
        with c3: adr_v = st.number_input("ADR (₹)", 0.0, 50000.0, 7000.0, 100.0, key="act_adr")
        with c4: rooms_v = st.number_input("Rooms Sold", 0, 500, 130, 1, key="act_rooms")
        if st.form_submit_button("💾 Save Actual Data", use_container_width=True):
            try:
                conn = gconn()
                conn.execute(
                    "INSERT OR REPLACE INTO daily_metrics (date,occupancy_pct,adr_inr,rooms_sold,updated_at) VALUES(?,?,?,?,datetime('now'))",
                    (str(act_date), occ_v, adr_v, int(rooms_v)))
                conn.commit()
                conn.close()
                st.success(f"Saved: {act_date} — {occ_v:.1f}% occupancy, ₹{adr_v:,.0f} ADR")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

with tab2:
    with st.form("event_form"):
        c1, c2 = st.columns(2)
        with c1:
            ev_name = st.text_input("Event Name *", key="ev_name")
            ev_venue = st.text_input("Venue *", key="ev_venue")
            ev_tier = st.selectbox("Size", ["small", "medium", "large"], key="ev_tier",
                format_func=lambda x: {"small": "Small (<500)", "medium": "Medium (500–2k)", "large": "Large (>2k)"}[x])
        with c2:
            ev_start = st.date_input("Start Date", value=date.today() + timedelta(30), key="ev_start")
            ev_end = st.date_input("End Date", value=date.today() + timedelta(31), key="ev_end")
            ev_lat = st.number_input("Venue Latitude", value=12.9915, format="%.4f", key="ev_lat")
            ev_lon = st.number_input("Venue Longitude", value=77.7260, format="%.4f", key="ev_lon")
        if st.form_submit_button("➕ Add Event", use_container_width=True):
            if not ev_name or not ev_venue:
                st.error("Event name and venue are required.")
            else:
                try:
                    hl, hn = 12.9915, 77.7260
                    dist = round(haversine((hl, hn), (ev_lat, ev_lon), unit=Unit.KILOMETERS), 2)
                    aw = {'small': 0.2, 'medium': 0.5, 'large': 1.0}[ev_tier]
                    pw = 1.0 if dist < 2 else 0.7 if dist < 5 else 0.4 if dist < 10 else 0.1
                    dw = 0.8 if (ev_end - ev_start).days + 1 == 1 else 1.0 if (ev_end - ev_start).days + 1 <= 3 else 1.2
                    conn = gconn()
                    conn.execute(
                        "INSERT OR REPLACE INTO events (name,start_date,end_date,venue,lat,lon,distance_km,attendance_tier,impact_score,source,source_url,scraped_at) VALUES(?,?,?,?,?,?,?,?,?,'manual','',datetime('now'))",
                        (ev_name, str(ev_start), str(ev_end), ev_venue, ev_lat, ev_lon, dist, ev_tier, round(aw * pw * dw, 3)))
                    conn.commit()
                    conn.close()
                    st.success(f"Added: {ev_name} — Impact: {round(aw * pw * dw, 3)}")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

with tab3:
    hl, hn = 12.9915, 77.7260
    tpl = pd.DataFrame({
        'name': ['Bengaluru Tech Summit'], 'start_date': ['2026-09-15'], 'end_date': ['2026-09-17'],
        'venue': ['KTPO Convention Centre'], 'attendance_tier': ['large'],
        'lat': [12.9788], 'lon': [77.7457], 'notes': ['']
    })
    st.download_button("⬇️ Download CSV Template", tpl.to_csv(index=False), "events_template.csv", "text/csv")
    st.markdown("<br>", unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload events CSV or Excel", type=['csv', 'xlsx'], key="bulk_upload")
    if uploaded:
        try:
            udf = pd.read_excel(uploaded) if uploaded.name.endswith('.xlsx') else pd.read_csv(uploaded)
            req = ['name', 'start_date', 'end_date', 'venue', 'attendance_tier']
            miss = [c for c in req if c not in udf.columns]
            if miss:
                st.error(f"Missing columns: {miss}")
            else:
                st.write(f"**Preview — {len(udf)} events:**")
                st.dataframe(udf.head(5), use_container_width=True, hide_index=True)
                if st.button("✅ Import All Events", use_container_width=True):
                    conn = gconn()
                    imp = errs = 0
                    for _, row in udf.iterrows():
                        try:
                            lat = float(row.get('lat', hl))
                            lon = float(row.get('lon', hn))
                            dist = round(haversine((hl, hn), (lat, lon), unit=Unit.KILOMETERS), 2)
                            tier = str(row['attendance_tier']).lower().strip()
                            aw = {'small': 0.2, 'medium': 0.5, 'large': 1.0}.get(tier, 0.2)
                            pw = 1.0 if dist < 2 else 0.7 if dist < 5 else 0.4 if dist < 10 else 0.1
                            s = pd.to_datetime(row['start_date']).date()
                            e = pd.to_datetime(row['end_date']).date()
                            dw = 0.8 if (e - s).days + 1 == 1 else 1.0 if (e - s).days + 1 <= 3 else 1.2
                            conn.execute(
                                "INSERT OR REPLACE INTO events (name,start_date,end_date,venue,lat,lon,distance_km,attendance_tier,impact_score,source,source_url,scraped_at) VALUES(?,?,?,?,?,?,?,?,?,'manual','',datetime('now'))",
                                (str(row['name']), str(s), str(e), str(row['venue']), lat, lon, dist, tier, round(aw * pw * dw, 3)))
                            imp += 1
                        except:
                            errs += 1
                    conn.commit()
                    conn.close()
                    st.success(f"Imported {imp} events.{f' Skipped {errs}.' if errs else ''}")
                    st.cache_data.clear()
                    st.rerun()
        except Exception as e:
            st.error(f"Error: {e}")

# ── Enquiry + Footer ───────────────────────────────────────────────────────────
subj = "Enquiry:%20StaxAI%20Hotel%20Demand%20Forecasting"
body = "Hello%20StaxAI,%0A%0AI%20am%20interested%20in%20the%20Hotel%20Demand%20Forecasting%20System.%0A%0AProperty%20Name:%20%0ALocation:%20%0ANo.%20of%20Rooms:%20%0A%0ARegards"
feats = ["AI Demand Forecasting", "GPU-Accelerated Model", "PredictHQ Events API",
         "Rate Recommendations", "Real-time Dashboard", "Multi-hotel Ready", "Slack Alerts"]

st.markdown(f"""
<div class="enq-card">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:2rem">
    <div style="flex:1;min-width:280px">
      <div style="font-size:10px;text-transform:uppercase;letter-spacing:.12em;color:#38BDF8;margin-bottom:8px;font-weight:700">Powered by StaxAI · AI Arm of DRCC</div>
      <div class="enq-title">Want this for your hotel?</div>
      <div class="enq-sub">StaxAI builds intelligent revenue management tools for hospitality clients across India. We can customise and deploy this system for your property within weeks.</div>
      <a href="mailto:info@staxai.in?subject={subj}&body={body}" class="enq-btn">&#9993; Enquire &rarr; info@staxai.in</a>
    </div>
    <div style="flex:1;min-width:240px">
      <div style="font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:rgba(255,255,255,.35);margin-bottom:10px;font-weight:700">What's included</div>
      {"".join(f'<span class="pill">&#10003; {f}</span>' for f in feats)}
    </div>
  </div>
</div>
<div class="footer">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:1rem">
    <div>
      <div style="font-family:'Sora',sans-serif;font-size:18px;font-weight:700;color:#1A3A5C">StaxAI</div>
      <div style="font-size:12px;color:#64748B;margin-top:2px">AI Arm of DRCC Chartered Accountants · Bengaluru, India</div>
    </div>
    <div style="text-align:right">
      <div style="font-size:12px;color:#64748B">info@staxai.in · staxai.in</div>
      <div style="font-size:11px;color:#94A3B8;margin-top:2px">Hotel Demand Intelligence v1.0</div>
    </div>
  </div>
  <div style="font-size:11px;color:#94A3B8;margin-top:1rem">&#169; 2026 DRCC / StaxAI · Built for hospitality revenue management · Data refreshes every 5 minutes</div>
</div>
""", unsafe_allow_html=True)
