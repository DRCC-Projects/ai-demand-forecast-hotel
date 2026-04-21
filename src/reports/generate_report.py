"""
Hotel Demand Forecast - PDF Report Generator
Place at: src/reports/generate_report.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import io, json, sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, HRFlowable
)
from reportlab.graphics.shapes import (
    Drawing, Rect, String, Line, PolyLine
)

# ── Colours ────────────────────────────────────────────────────────────────────
NAVY  = colors.HexColor('#1A3A5C')
TEAL  = colors.HexColor('#0EA5E9')
LIGHT = colors.HexColor('#F0F4F8')
WHITE = colors.white
MUTED = colors.HexColor('#64748B')
GREEN = colors.HexColor('#16A34A')
RED   = colors.HexColor('#DC2626')
AMBER = colors.HexColor('#D97706')
BORD  = colors.HexColor('#DDE3EC')
GOLD  = colors.HexColor('#F59E0B')

DB_PATH   = Path("data/hotel.db")
COMP_PATH = Path("data/competitor_rates.json")

def gconn(): return sqlite3.connect(str(DB_PATH))

def load_data():
    fc = pd.DataFrame(); ac = pd.DataFrame()
    ev = pd.DataFrame(); comp = []
    if DB_PATH.exists():
        try:
            fc = pd.read_sql(
                "SELECT date,occupancy_pred,adr_pred,lower_bound,upper_bound "
                "FROM forecasts WHERE date>=date('now') ORDER BY date LIMIT 30", gconn())
            fc['date'] = pd.to_datetime(fc['date'])
        except: pass
        try:
            ac = pd.read_sql(
                "SELECT date,occupancy_pct,adr_inr FROM daily_metrics "
                "ORDER BY date DESC LIMIT 30", gconn())
            ac['date'] = pd.to_datetime(ac['date'])
        except: pass
        try:
            ev = pd.read_sql(
                "SELECT name,start_date,end_date,venue,impact_score,attendance_tier "
                "FROM events WHERE start_date>=date('now') "
                "AND name NOT LIKE 'Test%' "
                "ORDER BY impact_score DESC LIMIT 7", gconn())
        except: pass
    if COMP_PATH.exists():
        try:
            raw = json.loads(COMP_PATH.read_text())
            comp = raw if isinstance(raw, list) else raw.get('hotels', [])
        except: pass
    return fc, ac, ev, comp

# ── Drawing helpers ────────────────────────────────────────────────────────────
def sparkline(dates, vals, W=255, H=72):
    d = Drawing(W, H)
    n = len(vals)
    if n < 2: return d
    PL, PR, PT, PB = 26, 6, 8, 18
    cw = W - PL - PR; ch = H - PT - PB
    mn, mx = min(vals), max(vals)
    rng = mx - mn if mx != mn else 1
    pts = []
    for i, v in enumerate(vals):
        x = PL + (i / (n-1)) * cw
        y = PB + ((v - mn) / rng) * ch
        pts += [x, y]
    # threshold 80
    if mn <= 80 <= mx:
        ty = PB + ((80 - mn) / rng) * ch
        d.add(Line(PL, ty, W-PR, ty, strokeColor=RED,
                   strokeWidth=0.7, strokeDashArray=[3,2]))
    d.add(PolyLine(pts, strokeColor=NAVY, strokeWidth=1.6, fillColor=None))
    # axes
    d.add(Line(PL, PB, W-PR, PB, strokeColor=BORD, strokeWidth=0.4))
    d.add(Line(PL, PB, PL, PB+ch, strokeColor=BORD, strokeWidth=0.4))
    # x labels
    for idx in [0, n//2, n-1]:
        x = PL + (idx/(n-1))*cw
        lbl = dates[idx].strftime('%d %b') if hasattr(dates[idx], 'strftime') else str(dates[idx])
        d.add(String(x, PB-11, lbl, fontSize=6.5, fillColor=MUTED, textAnchor='middle'))
    # y labels
    for v in [mn, (mn+mx)/2, mx]:
        y = PB + ((v-mn)/rng)*ch
        d.add(String(PL-2, y-2.5, f'{v:.0f}%', fontSize=6, fillColor=MUTED, textAnchor='end'))
    return d

def horiz_bars(names, values, our_adr, W=200, H=110):
    """Horizontal bar chart with full hotel names on left."""
    d = Drawing(W, H)
    n = len(values)
    if n == 0: return d
    PL, PR, PT, PB = 105, 8, 6, 6
    cw = W - PL - PR
    ch = H - PT - PB
    bar_h = (ch / n) * 0.6
    gap   = (ch / n) * 0.4
    mx = max(values) if values else 1

    for i, (name, val) in enumerate(zip(names, values)):
        y = PB + (n-1-i) * (ch/n) + gap/2
        bw = (val / mx) * cw
        is_ours = 'FOUR POINTS' in name.upper()
        fc = GOLD if is_ours else colors.HexColor('#94A3B8')
        d.add(Rect(PL, y, bw, bar_h, fillColor=fc,
                   strokeColor=None, strokeWidth=0))
        # Name label (left)
        short = name[:22]
        d.add(String(PL-3, y + bar_h/2 - 3, short,
                     fontSize=6.5, fillColor=NAVY if is_ours else MUTED,
                     textAnchor='end'))
        # Value label (right of bar)
        d.add(String(PL + bw + 2, y + bar_h/2 - 3,
                     f'Rs.{val:,.0f}',
                     fontSize=6.5, fillColor=NAVY, textAnchor='start'))
    # our ADR vertical line
    our_x = PL + (our_adr / mx) * cw
    d.add(Line(our_x, PB, our_x, PB+ch,
               strokeColor=NAVY, strokeWidth=1, strokeDashArray=[3,2]))
    d.add(String(our_x, PB+ch+2, 'Our ADR',
                 fontSize=6, fillColor=NAVY, textAnchor='middle'))
    d.add(Line(PL, PB, W-PR, PB, strokeColor=BORD, strokeWidth=0.4))
    return d

# ── Main generator ─────────────────────────────────────────────────────────────
def generate_pdf_report():
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
        leftMargin=16*mm, rightMargin=16*mm,
        topMargin=12*mm, bottomMargin=12*mm)

    fc, ac, ev, comp = load_data()
    now = datetime.now()

    avg_occ  = fc['occupancy_pred'].mean() if not fc.empty else 0
    avg_adr  = fc['adr_pred'].mean()       if not fc.empty else 0
    peak_day = (fc.loc[fc['occupancy_pred'].idxmax(),'date'].strftime('%d %b')
                if not fc.empty else '—')
    high_d   = int((fc['occupancy_pred']>72).sum()) if not fc.empty else 0
    rev_pot  = avg_adr*(avg_occ/100)*180*30 if avg_occ else 0

    S = []  # story

    # ── Header ──────────────────────────────────────────────────────────────
    def ps(name, **kw):
        kw.setdefault('fontName', 'Helvetica')
        return ParagraphStyle(name, **kw)

    hdr = Table([[
        Paragraph('<b>Demand Intelligence Report</b>',
                  ps('ht', fontName='Helvetica-Bold', fontSize=15, textColor=NAVY)),
        Paragraph(f'Four Points by Sheraton · Bengaluru Whitefield<br/>'
                  f'Generated: {now.strftime("%d %b %Y, %H:%M IST")}',
                  ps('hs', fontSize=8, textColor=MUTED, alignment=TA_RIGHT))
    ]], colWidths=[95*mm, 81*mm])
    hdr.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),
                             ('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    S.append(hdr)
    S.append(HRFlowable(width='100%', thickness=2, color=TEAL, spaceAfter=6))

    # ── KPI Cards ───────────────────────────────────────────────────────────
    def kpi(label, val, sub):
        t = Table([
            [Paragraph(label, ps('kl', fontSize=7, textColor=MUTED))],
            [Paragraph(f'<b>{val}</b>', ps('kv', fontName='Helvetica-Bold',
                                            fontSize=15, textColor=NAVY))],
            [Paragraph(sub,   ps('ks', fontSize=6.5,
                                 textColor=colors.HexColor('#94A3B8')))],
        ], colWidths=[34*mm])
        t.setStyle(TableStyle([
            ('BOX',(0,0),(-1,-1),0.5,BORD),
            ('BACKGROUND',(0,0),(-1,-1),WHITE),
            ('LEFTPADDING',(0,0),(-1,-1),5),
            ('RIGHTPADDING',(0,0),(-1,-1),5),
            ('TOPPADDING',(0,0),(-1,-1),5),
            ('BOTTOMPADDING',(0,0),(-1,-1),5),
            ('LINEBELOW',(0,0),(-1,0),1.5,TEAL),
        ]))
        return t

    kpis = Table([[
        kpi('AVG OCCUPANCY',    f'{avg_occ:.1f}%',        'Next 30 days'),
        kpi('AVG FORECAST ADR', f'Rs.{avg_adr:,.0f}',     'Per occupied room'),
        kpi('PEAK DAY',          peak_day,                 'Highest demand'),
        kpi('HIGH DEMAND DAYS',  str(high_d),              'Occupancy > 72%'),
        kpi('REVENUE POTENTIAL', f'Rs.{rev_pot/100000:.1f}L','30-day projection'),
    ]], colWidths=[35*mm]*5)
    kpis.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),1),
        ('RIGHTPADDING',(0,0),(-1,-1),1),
    ]))
    S.append(kpis)
    S.append(Spacer(1,6))

    # ── Sparkline + Rate Recs ───────────────────────────────────────────────
    sec = ps('sec', fontName='Helvetica-Bold', fontSize=8.5, textColor=NAVY, spaceAfter=3)
    td  = ps('td',  fontSize=7.5)
    th  = ps('th',  fontName='Helvetica-Bold', fontSize=7, textColor=MUTED)

    left = []
    left.append(Paragraph('30-Day Occupancy Forecast', sec))
    if not fc.empty:
        left.append(sparkline(list(fc['date']),
                              list(fc['occupancy_pred'].round(1)),
                              W=255, H=72))
        left.append(Paragraph(
            '<font color="#DC2626">— —</font>'
            '<font color="#64748B">  80% rate-increase threshold</font>',
            ps('lg', fontSize=7, textColor=MUTED, spaceBefore=2)))
    else:
        left.append(Paragraph('No forecast data.', ps('n', fontSize=8, textColor=MUTED)))

    right = []
    right.append(Paragraph('Rate Recommendations — Next 14 Days', sec))

    def rec(occ):
        if occ>80:   return 'Increase +20%', GREEN.hexval()
        if occ>72:   return 'Hold rate',      MUTED.hexval()
        return 'Offer discount', RED.hexval()

    if not fc.empty:
        rrows = [[Paragraph('<b>Date</b>',th), Paragraph('<b>Occ%</b>',th),
                  Paragraph('<b>ADR</b>',th),  Paragraph('<b>Action</b>',th)]]
        for _, r in fc.head(14).iterrows():
            act, col = rec(r['occupancy_pred'])
            rrows.append([
                Paragraph(r['date'].strftime('%a %d %b'), td),
                Paragraph(f"{r['occupancy_pred']:.1f}%",  td),
                Paragraph(f"Rs.{r['adr_pred']:,.0f}",     td),
                Paragraph(f'<font color="{col}"><b>{act}</b></font>',
                          ps('ta', fontName='Helvetica-Bold', fontSize=7.5)),
            ])
        rt = Table(rrows, colWidths=[22*mm,13*mm,18*mm,24*mm])
        rt.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),LIGHT),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,colors.HexColor('#F8FAFC')]),
            ('BOX',(0,0),(-1,-1),0.4,BORD),
            ('INNERGRID',(0,0),(-1,-1),0.3,BORD),
            ('TOPPADDING',(0,0),(-1,-1),2),
            ('BOTTOMPADDING',(0,0),(-1,-1),2),
            ('LEFTPADDING',(0,0),(-1,-1),4),
            ('RIGHTPADDING',(0,0),(-1,-1),4),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ]))
        right.append(rt)

    two = Table([[left, right]], colWidths=[88*mm, 88*mm])
    two.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),0),
        ('RIGHTPADDING',(0,0),(0,-1),5),
        ('RIGHTPADDING',(1,0),(1,-1),0),
    ]))
    S.append(two)
    S.append(Spacer(1,5))

    # ── Market Intelligence ─────────────────────────────────────────────────
    S.append(HRFlowable(width='100%', thickness=0.5, color=BORD, spaceAfter=4))
    S.append(Paragraph('Live Market Intelligence — Competitor Rates Tonight', sec))

    valid = [h for h in comp if h.get('cheapest') and h['cheapest'] > 1000]
    if valid:
        sorted_comp = sorted(valid, key=lambda x: x['cheapest'])
        all_h = sorted_comp + [{'name':'FOUR POINTS (Our Forecast ADR)',
                                 'cheapest': avg_adr}]
        all_h = sorted(all_h, key=lambda x: x['cheapest'])
        names  = [h['name'] for h in all_h]
        values = [h['cheapest'] for h in all_h]

        chart = horiz_bars(names, values, avg_adr, W=195, H=max(80, len(all_h)*14+12))

        crows = [[Paragraph('<b>Hotel</b>',th),
                  Paragraph('<b>Rate</b>',th),
                  Paragraph('<b>vs Our ADR</b>',th)]]
        for h in sorted_comp:
            diff = h['cheapest'] - avg_adr
            dc = GREEN.hexval() if diff>0 else RED.hexval()
            ds = f"+Rs.{diff:,.0f}" if diff>0 else f"-Rs.{abs(diff):,.0f}"
            crows.append([
                Paragraph(h['name'][:24], td),
                Paragraph(f"Rs.{h['cheapest']:,.0f}", td),
                Paragraph(f'<font color="{dc}"><b>{ds}</b></font>',
                          ps('cv', fontName='Helvetica-Bold', fontSize=7.5)),
            ])
        ct = Table(crows, colWidths=[38*mm,18*mm,20*mm])
        ct.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),LIGHT),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,colors.HexColor('#F8FAFC')]),
            ('BOX',(0,0),(-1,-1),0.4,BORD),
            ('INNERGRID',(0,0),(-1,-1),0.3,BORD),
            ('TOPPADDING',(0,0),(-1,-1),2),
            ('BOTTOMPADDING',(0,0),(-1,-1),2),
            ('LEFTPADDING',(0,0),(-1,-1),4),
            ('RIGHTPADDING',(0,0),(-1,-1),4),
        ]))
        mi = Table([[chart, ct]], colWidths=[100*mm, 80*mm])
        mi.setStyle(TableStyle([
            ('VALIGN',(0,0),(-1,-1),'TOP'),
            ('RIGHTPADDING',(0,0),(0,-1),5),
        ]))
        S.append(mi)
    else:
        S.append(Paragraph('Run competitor rate fetch to populate market data.',
                           ps('n', fontSize=8, textColor=MUTED)))

    S.append(Spacer(1,5))

    # ── Upcoming Events ─────────────────────────────────────────────────────
    S.append(HRFlowable(width='100%', thickness=0.5, color=BORD, spaceAfter=4))
    S.append(Paragraph('Upcoming Demand Events', sec))

    if not ev.empty:
        erows = [[Paragraph('<b>Event</b>',th), Paragraph('<b>Date</b>',th),
                  Paragraph('<b>Venue</b>',th),  Paragraph('<b>Impact</b>',th),
                  Paragraph('<b>Size</b>',th)]]
        for _, r in ev.iterrows():
            imp = float(r['impact_score'])
            ic  = RED.hexval() if imp>0.6 else AMBER.hexval() if imp>0.3 else GREEN.hexval()
            erows.append([
                Paragraph(str(r['name'])[:35],   td),
                Paragraph(str(r['start_date']),  td),
                Paragraph(str(r['venue'])[:20],  td),
                Paragraph(f'<font color="{ic}"><b>{imp:.2f}</b></font>',
                          ps('ei', fontName='Helvetica-Bold', fontSize=7.5)),
                Paragraph(str(r['attendance_tier']).capitalize(), td),
            ])
        et = Table(erows, colWidths=[57*mm,20*mm,38*mm,14*mm,17*mm])
        et.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),LIGHT),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[WHITE,colors.HexColor('#F8FAFC')]),
            ('BOX',(0,0),(-1,-1),0.4,BORD),
            ('INNERGRID',(0,0),(-1,-1),0.3,BORD),
            ('TOPPADDING',(0,0),(-1,-1),2),
            ('BOTTOMPADDING',(0,0),(-1,-1),2),
            ('LEFTPADDING',(0,0),(-1,-1),4),
            ('RIGHTPADDING',(0,0),(-1,-1),4),
        ]))
        S.append(et)
    else:
        S.append(Paragraph('No upcoming events.',
                           ps('n', fontSize=8, textColor=MUTED)))

    # ── Footer ───────────────────────────────────────────────────────────────
    S.append(Spacer(1,5))
    S.append(HRFlowable(width='100%', thickness=1, color=NAVY, spaceAfter=3))
    ft = Table([[
        Paragraph('<b>StaxAI</b> · AI Arm of DRCC Chartered Accountants · Bengaluru',
                  ps('fl', fontSize=7.5, textColor=MUTED)),
        Paragraph(f'info@staxai.in · staxai.in · Confidential · {now.strftime("%d %b %Y")}',
                  ps('fr', fontSize=7.5, textColor=MUTED, alignment=TA_RIGHT)),
    ]], colWidths=[95*mm, 81*mm])
    ft.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    S.append(ft)

    doc.build(S)
    buf.seek(0)
    return buf.read()


if __name__ == '__main__':
    print("Generating PDF...")
    os.chdir(Path(__file__).parent.parent.parent)
    pdf = generate_pdf_report()
    out = Path("reports/demand_forecast_report.pdf")
    out.parent.mkdir(exist_ok=True)
    out.write_bytes(pdf)
    print(f"Saved: {out} ({len(pdf):,} bytes)")
