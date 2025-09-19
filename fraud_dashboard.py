# =====================================================
# DoorDash Take-Home Project — Fraud Detection & Trends
# Author: Faiz Syed
# Brief: An interactive Dash app to explore chargebacks/fraud,
#        surface leading signals, and translate insights into
#        actionable, minimal recommendations with jump-to-chart links.
# =====================================================

import os, base64, json
import pandas as pd
import numpy as np
import dash
from dash import dcc, html, dash_table, Input, Output, State, ALL
import plotly.express as px
from flask import Response  # for /healthz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

FILE_PATH = os.getenv(
    "DATA_FILE",
    os.path.join(BASE_DIR, "Fraud_Take_Home_Sheet_(3).xlsx")
)
LOGO_PATH = os.path.join(BASE_DIR, "DoorDashLogo.svg")

# ---------- DoorDash-ish Theme ----------
DD_RED = "#EB1700"
DD_RED_DARK = "#C51400"
DD_SLATE = "#101418"
DD_TEXT = "#1F2937"
DD_BG = "#F8F9FB"
DD_CARD_BG = "#FFFFFF"
DD_MUTE = "#6B7280"
DD_BORDER = "#E5E7EB"
DD_HILITE = "#FFEDE7"  # subtle highlight for targeted rec card

px.defaults.template = "plotly_white"
px.defaults.color_discrete_sequence = [DD_RED, "#334155", "#0EA5E9", "#14B8A6", "#F59E0B", "#6366F1"]

# ---------- Logo Loader ----------
def load_logo_src():
    if LOGO_PATH and os.path.exists(LOGO_PATH):
        ext = os.path.splitext(LOGO_PATH)[1].lower()
        mime = "image/png" if ext == ".png" else "image/svg+xml"
        with open(LOGO_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f"data:{mime};base64,{b64}"
    # Fallback red square
    return ("data:image/svg+xml;utf8,"
            "<svg xmlns='http://www.w3.org/2000/svg' width='40' height='40'>"
            "<rect width='40' height='40' fill='%23EB1700'/></svg>")

LOGO_SRC = load_logo_src()

# ---------- Helpers ----------
def to_bool_int(series):
    """Coerce various truthy/falsey values to 0/1."""
    def _map(x):
        if pd.isna(x):
            return 0
        s = str(x).strip().lower()
        if s in {"1","true","t","yes","y"}:
            return 1
        if s in {"0","false","f","no","n"}:
            return 0
        try:
            return 1 if float(s) != 0 else 0
        except:
            return 0
    return series.apply(_map).astype(int)

def safe_div(n, d):
    try:
        return float(n) / float(d) if d else 0.0
    except:
        return 0.0

def fmt_pct(x):
    try:
        return f"{x:.2%}"
    except:
        return "—"

def theme_fig(fig):
    """Minimal chart styling (no internal titles)."""
    fig.update_layout(
        title=None,
        margin=dict(l=16, r=16, t=16, b=16),
        plot_bgcolor=DD_CARD_BG,
        paper_bgcolor=DD_CARD_BG,
        font=dict(color=DD_TEXT, size=13),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hoverlabel=dict(bgcolor="white"),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#F1F5F9", zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#F1F5F9", zeroline=False)
    return fig

def section_title(text):
    return html.Div(text, style={"color": DD_SLATE, "fontWeight": 700, "margin": "4px 0 6px 0"})

def kpi_card(title, value, subtext=None):
    return html.Div(
        [
            html.Div(style={"height": "4px", "background": DD_RED, "borderRadius": "6px 6px 0 0", "marginBottom": "12px"}),
            html.Div(
                [
                    html.Div(title, style={"color": DD_MUTE, "fontSize": "13px", "fontWeight": 600, "letterSpacing": "0.3px"}),
                    html.Div(value, style={"color": DD_SLATE, "fontSize": "28px", "fontWeight": 700, "marginTop": "4px"}),
                    html.Div(subtext or "", style={"color": DD_MUTE, "fontSize": "12px", "marginTop": "6px"}),
                ]
            ),
        ],
        style={
            "background": DD_CARD_BG,
            "border": f"1px solid {DD_BORDER}",
            "borderRadius": "12px",
            "padding": "16px 18px",
            "minWidth": "200px",
            "boxShadow": "0 2px 10px rgba(16,20,24,0.04)"
        },
    )

def badge(text):
    return html.Span(
        text,
        style={
            "display": "inline-block", "padding": "2px 8px", "fontSize": "12px",
            "background": "#FFF1EE", "color": DD_RED_DARK, "border": f"1px solid {DD_BORDER}",
            "borderRadius": "999px", "marginRight": "6px"
        }
    )

def rec_card(title, trigger, why, actions, kpis, tags=None, highlight=False, _id=None, significance=None):
    """Recommendation card with trigger, a short significance line, why, actions, and KPIs."""
    return html.Div(
        [
            html.Div(style={"height": "4px", "background": DD_RED, "borderRadius": "8px 8px 0 0", "marginBottom": "10px"}),
            html.Div(
                [
                    html.Div(title, style={"fontWeight": 700, "color": DD_SLATE, "fontSize": "16px", "marginBottom": "6px"}),
                    html.Div([badge(t) for t in (tags or [])], style={"marginBottom": "8px"}),

                    html.Div(html.B("Trigger (rule): "), style={"marginTop": "6px"}),
                    html.Div(trigger, style={"color": DD_TEXT, "marginBottom": "4px"}),
                    html.Div(
                        significance or "",
                        style={"color": DD_MUTE, "fontSize": "12px", "marginBottom": "8px", "fontStyle": "italic"}
                    ),

                    html.Div(html.B("Why it helps: ")),
                    html.Div(why, style={"color": DD_TEXT, "marginBottom": "8px"}),

                    html.Div(html.B("Actions: ")),
                    html.Ul([html.Li(a) for a in actions], style={"marginTop": "4px", "marginBottom": "8px"}),

                    html.Div(html.B("KPIs to monitor: ")),
                    html.Ul([html.Li(k) for k in kpis], style={"marginTop": "4px", "marginBottom": "0"}),
                ]
            ),
        ],
        id=_id,
        style={
            "background": DD_CARD_BG if not highlight else DD_HILITE,
            "border": f"2px solid {DD_RED}" if highlight else f"1px solid {DD_BORDER}",
            "borderRadius": "12px",
            "padding": "12px 14px",
            "boxShadow": "0 2px 10px rgba(16,20,24,0.04)"
        },
    )

def info_card(title, md_blocks):
    """Assumptions card with MathJax-safe layout & scroll if needed."""
    return html.Div(
        [
            html.Div(style={"height": "4px", "background": DD_RED, "borderRadius": "8px 8px 0 0", "marginBottom": "10px"}),
            html.Div(
                [
                    html.Div(title, style={"fontWeight": 700, "color": DD_SLATE, "fontSize": "16px", "marginBottom": "6px"}),
                    *[
                        dcc.Markdown(
                            md,
                            mathjax=True,
                            style={
                                "fontSize": "14px",
                                "lineHeight": "1.55",
                                "whiteSpace": "normal",
                                "wordWrap": "break-word",
                                "overflowX": "auto",
                                "paddingBottom": "4px",
                            },
                        )
                        for md in md_blocks
                    ],
                ],
                style={"overflowX": "auto"}
            ),
        ],
        style={
            "background": DD_CARD_BG,
            "border": f"1px solid {DD_BORDER}",
            "borderRadius": "12px",
            "padding": "12px 14px",
            "boxShadow": "0 2px 10px rgba(16,20,24,0.04)",
            "overflow": "visible",
        },
    )

def bubble_btn(label, key):
    """Clickable chip that routes to a recommendation key."""
    return html.Button(
        label,
        id={"type": "rec-bubble", "key": key},
        n_clicks=0,
        style={
            "display": "inline-block",
            "padding": "6px 10px",
            "fontSize": "12px",
            "borderRadius": "999px",
            "border": f"1px solid {DD_BORDER}",
            "background": "#FFF6F3",
            "color": DD_RED_DARK,
            "cursor": "pointer",
            "marginRight": "8px",
            "marginTop": "4px",
        },
    )

# ---------- Load ----------
df = pd.read_excel(FILE_PATH)

# ---------- Preprocess ----------
df["CREATED_AT"] = pd.to_datetime(df.get("CREATED_AT"), errors="coerce")
df["DATE"] = df["CREATED_AT"].dt.date

# Temporal helpers for heatmap
df["HOUR"] = df["CREATED_AT"].dt.hour
df["DOW"]  = df["CREATED_AT"].dt.dayofweek  # 0=Mon..6=Sun
dow_map = {0:"Mon",1:"Tue",2:"Wed",3:"Thu",4:"Fri",5:"Sat",6:"Sun"}
df["DOW_LABEL"] = df["DOW"].map(dow_map)

# Numeric coercion
numeric_cols = [
    "GOV", "CHARGEBACK_COST", "SIFT_CREATE_ORDER_PA_SCORE",
    "FAIL_CHARGES_1HR", "FAIL_CHARGES_1D", "FAIL_CHARGES_7D",
    "DEVICE_DELIVERIES", "DEVICE_PCT_CHARGEBACK",
    "CCR_PAST_DELIVERIES", "CCR_CHARGEBACK_DELIVERIES", "CX_PCT_CHARGEBACK",
    "CX_UNIQUE_ADDRESSES", "UNIQUE_ADDRESS_PAST_1DAY", "UNIQUE_ADDRESS_PAST_7DAY",
    "CX_DEVICE_ORDER_NUM", "CX_ADDRESS_ORDER_NUM", "CX_CARD_ORDER_NUM", "CX_ORDER_NUM",
    "CX_AGE_ON_DELIVERY_BASED_ON_FIRST_ORDER"
]
for c in numeric_cols:
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")

# Booleans & label
df["RECEIVED_CHARGEBACK"] = to_bool_int(df["RECEIVED_CHARGEBACK"]) if "RECEIVED_CHARGEBACK" in df.columns else 0
df["IS_FRAUDULENT_CHARGEBACK"] = to_bool_int(df["IS_FRAUDULENT_CHARGEBACK"]) if "IS_FRAUDULENT_CHARGEBACK" in df.columns else 0
df["FRAUD_FLAG"] = df["IS_FRAUDULENT_CHARGEBACK"].astype(int)

# Money normalization
if "GOV" in df.columns:
    df["GOV"] = pd.to_numeric(df["GOV"], errors="coerce").fillna(0)
    df["GOV_DOLLARS"] = df["GOV"] / 100.0
else:
    df["GOV_DOLLARS"] = 0.0

# ---------- KPIs ----------
overall_deliveries = df["DELIVERY_ID"].nunique() if "DELIVERY_ID" in df.columns else len(df)
overall_cb = int(df["RECEIVED_CHARGEBACK"].sum())
overall_fraud = int(df["FRAUD_FLAG"].sum())
overall_cb_rate = safe_div(overall_cb, overall_deliveries)
overall_fraud_rate = safe_div(overall_fraud, overall_deliveries)
overall_cb_cost = float(df.get("CHARGEBACK_COST", pd.Series([0])).fillna(0).sum())
avg_gov = float(df["GOV_DOLLARS"].mean()) if "GOV_DOLLARS" in df.columns else 0.0
avg_sift = float(df.get("SIFT_CREATE_ORDER_PA_SCORE", pd.Series([np.nan])).mean())

# ---------- Daily Trends ----------
daily = df.groupby("DATE", dropna=False, observed=False).agg(
    deliveries=("DELIVERY_ID", "count"),
    chargebacks=("RECEIVED_CHARGEBACK", "sum"),
    fraudulent=("FRAUD_FLAG", "sum"),
    cb_cost=("CHARGEBACK_COST", "sum"),
    avg_sift=("SIFT_CREATE_ORDER_PA_SCORE", "mean"),
    avg_gov=("GOV_DOLLARS", "mean")
).reset_index()

daily["chargeback_rate"] = (daily["chargebacks"] / daily["deliveries"].replace(0, np.nan)).fillna(0)
daily["fraud_rate"] = (daily["fraudulent"] / daily["deliveries"].replace(0, np.nan)).fillna(0)

# ---------- Date-range note for KPIs (centered) ----------
if not daily.empty:
    _min_date = pd.to_datetime(daily["DATE"]).min()
    _max_date = pd.to_datetime(daily["DATE"]).max()
    kpi_date_note_text = f"Data range: {_min_date.strftime('%b %d, %Y')} – {_max_date.strftime('%b %d, %Y')}"
else:
    kpi_date_note_text = "Data range: —"

# ---------- Segments / Leading Signals ----------
if "PLATFORM" in df.columns:
    fraud_by_platform = (
        df.groupby("PLATFORM", dropna=False, observed=False)["FRAUD_FLAG"]
        .mean().reset_index().rename(columns={"FRAUD_FLAG": "fraud_rate"})
    )
else:
    fraud_by_platform = pd.DataFrame(columns=["PLATFORM", "fraud_rate"])

if "CX_UNIQUE_ADDRESSES" in df.columns:
    fraud_by_addr = (
        df.groupby("CX_UNIQUE_ADDRESSES", dropna=False, observed=False)["FRAUD_FLAG"]
        .mean().reset_index().rename(columns={"FRAUD_FLAG": "fraud_rate"}).sort_values("CX_UNIQUE_ADDRESSES")
    )
else:
    fraud_by_addr = pd.DataFrame(columns=["CX_UNIQUE_ADDRESSES", "fraud_rate"])

if "FAIL_CHARGES_1D" in df.columns:
    fraud_by_failed = (
        df.groupby("FAIL_CHARGES_1D", dropna=False, observed=False)["FRAUD_FLAG"]
        .mean().reset_index().rename(columns={"FRAUD_FLAG": "fraud_rate"}).sort_values("FAIL_CHARGES_1D")
    )
else:
    fraud_by_failed = pd.DataFrame(columns=["FAIL_CHARGES_1D", "fraud_rate"])

# GOV bins as strings to avoid Interval JSON issue
if "GOV_DOLLARS" in df.columns:
    df["GOV_BIN"] = pd.qcut(df["GOV_DOLLARS"].fillna(0), q=10, duplicates="drop")
    df["GOV_BIN_LABEL"] = df["GOV_BIN"].astype(str)
    fraud_by_gov_bin = (
        df.groupby("GOV_BIN_LABEL", dropna=False, observed=False)["FRAUD_FLAG"]
        .mean().reset_index().rename(columns={"FRAUD_FLAG": "fraud_rate", "GOV_BIN_LABEL": "GOV_BIN"})
    )
else:
    fraud_by_gov_bin = pd.DataFrame(columns=["GOV_BIN", "fraud_rate"])

# ---------- Temporal Heatmap (Day-of-Week × Hour) ----------
heat = (
    df.groupby(["DOW_LABEL","HOUR"], dropna=False, observed=False)["FRAUD_FLAG"]
      .mean().reset_index().rename(columns={"FRAUD_FLAG":"fraud_rate"})
)
order_dow = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
heat["DOW_LABEL"] = pd.Categorical(heat["DOW_LABEL"], categories=order_dow, ordered=True)
heat_pivot = heat.pivot(index="DOW_LABEL", columns="HOUR", values="fraud_rate").fillna(0)

# ---------- Quick Insight Helpers ----------
def last_vs_prior_7d(series_dates, values):
    s = pd.Series(values.values, index=pd.to_datetime(series_dates)).sort_index()
    if s.empty: return None
    last_date = s.index.max()
    last7 = s[(s.index > last_date - pd.Timedelta(days=7))]
    prior7 = s[(s.index > last_date - pd.Timedelta(days=14)) & (s.index <= last_date - pd.Timedelta(days=7))]
    if len(last7) == 0 or len(prior7) == 0: return None
    return float(last7.mean()), float(prior7.mean()), float(last7.mean() - prior7.mean())

def insight_rates_trend():
    res_cb = last_vs_prior_7d(daily["DATE"], daily["chargeback_rate"])
    res_fr = last_vs_prior_7d(daily["DATE"], daily["fraud_rate"])
    bullets = []
    if res_cb:
        last, prior, delta = res_cb
        bullets.append(f"Chargeback rate last 7d {fmt_pct(last)} vs prior 7d {fmt_pct(prior)} ({'+' if delta>=0 else ''}{fmt_pct(delta)}).")
    if res_fr:
        last, prior, delta = res_fr
        bullets.append(f"Fraud rate last 7d {fmt_pct(last)} vs prior 7d {fmt_pct(prior)} ({'+' if delta>=0 else ''}{fmt_pct(delta)}).")
    if not bullets:
        bullets.append("Insufficient recent data for 14-day comparison.")
    return bullets[:3]

def insight_cb_cost():
    s = pd.Series(daily["cb_cost"].values, index=pd.to_datetime(daily["DATE"])).sort_index()
    if s.empty: return ["No cost data available."]
    last7 = s.tail(7).sum()
    prior7 = s.tail(14).head(7).sum() if len(s) >= 14 else np.nan
    bullets = [f"Last 7d chargeback cost: ${last7:,.0f}."]
    if not np.isnan(prior7):
        change = last7 - prior7
        bullets.append(f"Prior 7d: ${prior7:,.0f} ({'+' if change>=0 else ''}{change:,.0f}).")
    bullets.append(f"Lifetime total CB cost: ${overall_cb_cost:,.0f}.")
    return bullets[:3]

def insight_sift_gov():
    bullets = []
    if "SIFT_CREATE_ORDER_PA_SCORE" in df.columns and not pd.isna(avg_sift):
        bullets.append(f"Average Sift score overall: {avg_sift:.2f}.")
    if "GOV_DOLLARS" in df.columns:
        bullets.append(f"Average order value: ${avg_gov:,.2f}.")
    if {"avg_sift", "fraud_rate"}.issubset(daily.columns):
        c = daily[["avg_sift", "fraud_rate"]].dropna().corr().iloc[0,1]
        if not np.isnan(c):
            bullets.append(f"Sift vs fraud (daily) correlation: {c:+.2f} (directional).")
    return bullets[:3] if bullets else ["No Sift/GOV data available."]

def insight_platform():
    if fraud_by_platform.empty: return ["No platform data available."]
    top = fraud_by_platform.loc[fraud_by_platform["fraud_rate"].idxmax()]
    bot = fraud_by_platform.loc[fraud_by_platform["fraud_rate"].idxmin()]
    return [
        f"Highest fraud platform: {top['PLATFORM']} ({fmt_pct(top['fraud_rate'])}).",
        f"Lowest fraud platform: {bot['PLATFORM']} ({fmt_pct(bot['fraud_rate'])}).",
        f"Overall fraud rate baseline: {fmt_pct(overall_fraud_rate)}.",
    ]

def insight_addresses():
    if fraud_by_addr.empty: return ["No address data available."]
    overall = overall_fraud_rate
    high = fraud_by_addr.sort_values("fraud_rate", ascending=False).head(1)
    bullets = [
        f"Highest fraud at {int(high['CX_UNIQUE_ADDRESSES'].iloc[0])} unique addresses ({fmt_pct(high['fraud_rate'].iloc[0])}).",
        f"Overall fraud rate baseline: {fmt_pct(overall)}.",
    ]
    if (fraud_by_addr["CX_UNIQUE_ADDRESSES"]>=2).any():
        gte2 = fraud_by_addr[fraud_by_addr["CX_UNIQUE_ADDRESSES"]>=2]["fraud_rate"].mean()
        bullets.append(f"2+ unique addresses avg fraud: {fmt_pct(gte2)} (vs baseline).")
    return bullets[:3]

def insight_failed():
    if fraud_by_failed.empty: return ["No failed charge data available."]
    zero = fraud_by_failed.loc[fraud_by_failed["FAIL_CHARGES_1D"]==0, "fraud_rate"]
    ge1 = fraud_by_failed.loc[fraud_by_failed["FAIL_CHARGES_1D"]>=1, "fraud_rate"]
    ge2 = fraud_by_failed.loc[fraud_by_failed["FAIL_CHARGES_1D"]>=2, "fraud_rate"]
    bullets = []
    if not zero.empty: bullets.append(f"0 failed charges fraud rate: {fmt_pct(zero.mean())}.")
    if not ge1.empty: bullets.append(f"≥1 failed charge: {fmt_pct(ge1.mean())}.")
    if not ge2.empty: bullets.append(f"≥2 failed charges: {fmt_pct(ge2.mean())}.")
    return bullets[:3] if bullets else ["Insufficient distribution across buckets."]

def insight_govbin():
    if fraud_by_gov_bin.empty: return ["No GOV bin data available."]
    top = fraud_by_gov_bin.loc[fraud_by_gov_bin["fraud_rate"].idxmax()]
    bot = fraud_by_gov_bin.loc[fraud_by_gov_bin["fraud_rate"].idxmin()]
    return [
        f"Highest fraud bin: {top['GOV_BIN']} ({fmt_pct(top['fraud_rate'])}).",
        f"Lowest fraud bin: {bot['GOV_BIN']} ({fmt_pct(bot['fraud_rate'])}).",
        f"Baseline fraud rate: {fmt_pct(overall_fraud_rate)}.",
    ][:3]

def insight_heatmap():
    return [
        "Heatmap shows fraud rate by day-of-week and hour; bright cells indicate risky windows.",
        "Use hot zones to set rate limits / staffing / step-up windows.",
    ]

# ---------- Glossary ----------
glossary_items = [
    ("DELIVERY_ID", "ID of Order/Delivery."),
    ("CREATED_AT", "Timestamp for order creation."),
    ("CONSUMER_ID", "ID of consumer account."),
    ("GOV", "Gross Order Value in cents; includes items subtotal, fees, taxes, tip."),
    ("CX_AGE_ON_DELIVERY_BASED_ON_FIRST_ORDER", "Consumer age in days at this delivery, since first order date."),
    ("PLATFORM", "Platform used at checkout (iOS/Android/Web)."),
    ("RECEIVED_CHARGEBACK", "Whether the delivery received a chargeback."),
    ("IS_FRAUDULENT_CHARGEBACK", "True if chargeback reason ∈ {'fraudulent','unrecognized','general'} per issuer."),
    ("CHARGEBACK_COST", "Potential chargeback cost in cents (txn amount + processor fee; goes to 0 if win)."),
    ("CX_DEVICE_ORDER_NUM", "Sequence number of orders by this consumer on this device."),
    ("CX_ADDRESS_ORDER_NUM", "Sequence number of orders by this consumer to this address."),
    ("CX_CARD_ORDER_NUM", "Sequence number of orders by this consumer using this card fingerprint."),
    ("CX_ORDER_NUM", "Sequence number of orders by this consumer (overall)."),
    ("CX_UNIQUE_ADDRESSES", "Total unique addresses this consumer has ever used (to date)."),
    ("UNIQUE_ADDRESS_PAST_1DAY", "Unique addresses used in last 24 hours from this order's creation."),
    ("UNIQUE_ADDRESS_PAST_7DAY", "Unique addresses used in last 7×24 hours from this order's creation."),
    ("SIFT_CREATE_ORDER_PA_SCORE", "Sift score for this order creation event."),
    ("FAIL_CHARGES_1HR", "Failed charge attempts in the hour before order."),
    ("FAIL_CHARGES_1D", "Failed charge attempts in the day before order."),
    ("FAIL_CHARGES_7D", "Failed charge attempts in the 7 days before order."),
    ("DEVICE_DELIVERIES", "Total deliveries placed by this device (to date)."),
    ("DEVICE_PCT_CHARGEBACK", "% of this device's deliveries that received chargebacks."),
    ("CCR_PAST_DELIVERIES", "Consumer's total deliveries prior to this one."),
    ("CCR_CHARGEBACK_DELIVERIES", "Consumer's total prior chargebacks."),
    ("CX_PCT_CHARGEBACK", "Consumer chargeback rate = CCR_CHARGEBACK_DELIVERIES / CCR_PAST_DELIVERIES."),
]
glossary_df = pd.DataFrame(glossary_items, columns=["Field", "Definition"])
glossary_map = dict(glossary_df.values)

# ---- Recommendation definitions (keys → content) ----
REC_DEFS = {
    "temporal": dict(
        title="Temporal Guardrails (Hot-Zone Windows)",
        trigger="Hours/days with above-baseline fraud in the Temporal Heatmap.",
        significance="Hot windows concentrate loss; targeted friction saves $ with low UX impact.",
        why="Abuse clusters in predictable windows (e.g., late nights). Rate-limits/step-up then reduce leakage with minimal overall UX cost.",
        actions=[
            "Tighten limits + 3DS in hot hours",
            "Queue high-GOV/high-risk to review",
            "Staff review to peaks"
        ],
        kpis=["Fraud in hot windows", "Approval vs off-hours", "Review SLA at peaks"],
        tags=["Time Windows", "Ops", "Rate Limits"],
    ),
    "failed_payments": dict(
        title="Step-up Verification on Failed Payments",
        trigger="FAIL_CHARGES_1HR ≥ 1 or FAIL_CHARGES_1D ≥ 2.",
        significance="Multiple declines often indicate card testing.",
        why="Repeated payment failures signal card testing; assurance reduces high-risk volume.",
        actions=[
            "Require 3DS/OTP",
            "Throttle retries / risky BINs",
            "Add cooldowns after multiple declines"
        ],
        kpis=["3DS pass rate", "Fraud on stepped-up traffic", "Approval rate impact"],
        tags=["Payments", "Velocity", "3DS"],
    ),
    "address_velocity": dict(
        title="Address Velocity & Uniqueness Control",
        trigger="UNIQUE_ADDRESS_PAST_1DAY ≥ 2 or UNIQUE_ADDRESS_PAST_7DAY ≥ 3; lifetime CX_UNIQUE_ADDRESSES in top decile.",
        significance="Many new/different addresses → reship/mule risk.",
        why="Many distinct addresses in short windows suggests reship/mule behavior.",
        actions=[
            "OTP on address change",
            "Cap new addresses/day",
            "Hold first order to a new address"
        ],
        kpis=["Fraud by address-velocity", "Review accept rate", "Time-to-fulfillment (flagged)"],
        tags=["Address", "Velocity"],
    ),
    "device": dict(
        title="Device-Level Risk Throttling",
        trigger="DEVICE_PCT_CHARGEBACK ≥ max(1%, 2× baseline) or repeated disputes on same device.",
        significance="Repeat abusers cluster on the same device or emulator.",
        why="Shared/emulated devices drive repeat abuse; throttling reduces serial loss.",
        actions=[
            "Increase friction / re-auth",
            "Cap daily orders / cool-offs",
            "Limit multi-account per device"
        ],
        kpis=["Fraud by device tier", "Legit conversion (flagged)", "Share throttled/blocked"],
        tags=["Device", "Rate Limits"],
    ),
    "sift": dict(
        title="Sift Thresholds with Feedback Loop",
        trigger="Top-decile Sift scores or above tuned threshold.",
        significance="High scores flag risk; tuning optimizes $ saved vs. friction.",
        why="External risk scores are predictive; local calibration maximizes $ saved vs. friction.",
        actions=[
            "Route to 3DS/review at cut-points",
            "Weekly backfill outcomes to Sift",
            "Use reason codes to tune"
        ],
        kpis=["Precision/Recall at threshold", "False-positive rate", "$ saved vs. revenue loss"],
        tags=["ML Score", "Calibration"],
    ),
    "gov": dict(
        title="High-Value (GOV) Order Scrutiny",
        trigger="Orders in top 20% GOV bins.",
        significance="High-GOV orders carry outsized loss per hit.",
        why="Payout incentives rise with order size; fraud often increases at the top end.",
        actions=[
            "3DS + re-verify address",
            "Short holds for risky high-GOV",
            "Escalate during spikes"
        ],
        kpis=["Fraud by GOV bin", "Approval after step-up", "NPS on high-GOV flow"],
        tags=["GOV", "Manual Review"],
    ),
    "platform": dict(
        title="Platform-Aware Guardrails",
        trigger="Platforms with above-baseline fraud rate.",
        significance="Some platforms are more bot-exposed or weakly instrumented.",
        why="Certain platform funnels/SDKs or bot exposure can inflate risk.",
        actions=[
            "Bot mitigation + phone verify",
            "Require account age / verified pay",
            "Fix instrumentation on risky paths"
        ],
        kpis=["Fraud by platform", "Checkout drop-off", "Bot signal quality"],
        tags=["Platform", "Bots"],
    ),
}

# ---------- Dash App ----------
app = dash.Dash(
    __name__,
    external_scripts=["https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"]
)
app.title = "Fraud Detection Dashboard"

# Expose WSGI server for Gunicorn and add health check
server = app.server

@server.route("/healthz")
def healthz():
    return Response("ok", status=200)

tabs_styles = {"height": "44px", "border": "none"}
tab_style = {
    "padding": "10px 16px",
    "fontWeight": 600,
    "border": f"1px solid {DD_BORDER}",
    "borderBottom": f"1px solid {DD_BORDER}",
    "background": DD_CARD_BG,
    "color": DD_TEXT,
}
tab_selected_style = {
    "padding": "10px 16px",
    "fontWeight": 700,
    "border": f"1px solid {DD_RED}",
    "borderBottom": f"2px solid {DD_RED}",
    "background": "#FFF6F3",
    "color": DD_RED_DARK,
}

def build_rec_cards(selected_key=None):
    """Return list of recommendation card components, selected one first + highlighted."""
    cards = []
    for key, cfg in REC_DEFS.items():
        cards.append((key, rec_card(
            title=cfg["title"], trigger=cfg["trigger"], significance=cfg.get("significance"),
            why=cfg["why"], actions=cfg["actions"], kpis=cfg["kpis"], tags=cfg["tags"],
            highlight=(key == selected_key), _id=f"rec-{key}"
        )))
    if selected_key and selected_key in REC_DEFS:
        cards.sort(key=lambda x: 0 if x[0]==selected_key else 1)
    return [c for _, c in cards]

# ---------- Layout builder ----------
def build_tabs():
    # --- Header: Grid with 3 columns: [logo] [centered title/subtitle] [spacer] ---
    header = html.Div(
        [
            # Column 1: Logo
            html.Div(
                html.Img(
                    src=LOGO_SRC,
                    style={"height": "28px", "display": "block"}
                ),
                style={"width": "48px", "display": "flex", "alignItems": "center"}  # fixed width
            ),

            # Column 2: Title + Subtitle
            html.Div(
                [
                    html.H1(
                        "DoorDash Project",
                        style={"color": DD_SLATE, "margin": 0, "fontSize": "24px", "lineHeight": "1", "textAlign": "center"}
                    ),
                    html.Div(
                        "• Fraud-focused monitoring & recommendations •",
                        style={"color": DD_MUTE, "marginTop": "6px", "textAlign": "center"}
                    ),
                    html.Div(
                        "By Faiz Syed",
                        style={"color": DD_MUTE, "marginTop": "4px", "textAlign": "center", "fontSize": "13px", "fontStyle": "italic"}
                    ),
                ],
                style={"display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center"}
            ),

            # Column 3: Spacer
            html.Div(style={"width": "48px"}),
        ],
        style={
            "display": "grid",
            "gridTemplateColumns": "48px 1fr 48px",
            "alignItems": "center",
            "columnGap": "10px",
            "background": DD_BG,
            "marginBottom": "4px",
        },
    )

    # --- KPIs grid and date note ---
    kpis = html.Div(
        [
            kpi_card("Chargeback Rate", fmt_pct(overall_cb_rate), "All deliveries"),
            kpi_card("Fraud Rate", fmt_pct(overall_fraud_rate), "Fraudulent chargebacks / deliveries"),
            kpi_card("Total Chargeback Cost ($)", f"{overall_cb_cost:,.0f}", "Sum of CB costs"),
            kpi_card("Avg GOV ($)", f"{avg_gov:,.2f}", "Order average"),
            kpi_card("Avg Sift Score", f"{avg_sift:.2f}" if not np.isnan(avg_sift) else "—", "Order creation"),
        ],
        style={
            "display": "grid",
            "gridTemplateColumns": "repeat(auto-fit, minmax(220px, 1fr))",
            "gap": "12px",
            "alignItems": "stretch",
            "margin": "14px 0 6px 0",
        },
    )

    date_note = html.Div(
        kpi_date_note_text,
        style={"color": DD_MUTE, "fontSize": "12px", "textAlign": "center", "marginBottom": "12px"}
    )

    # Trends Tab
    trends_tab = dcc.Tab(
        label="Fraud Trends", value="trends", style=tab_style, selected_style=tab_selected_style,
        children=[
            html.Br(),

            section_title("Temporal Fraud Heatmap (Day-of-Week × Hour)"),
            dcc.Graph(figure=theme_fig(px.imshow(
                heat_pivot,  # pass DF so labels render
                aspect="auto",
                labels=dict(color="Fraud Rate"),
            )) if not heat_pivot.empty else theme_fig(px.imshow(
                np.zeros((1,1)), aspect="auto", labels=dict(color="Fraud Rate")
            ))),
            html.Ul([html.Li(t) for t in insight_heatmap()], style={"color": DD_MUTE, "marginTop": "6px"}),
            html.Div([bubble_btn("See: Temporal Guardrails", "temporal")], style={"margin": "4px 0 12px 0"}),

            section_title("Daily Chargeback & Fraud Rates"),
            dcc.Graph(figure=theme_fig(px.line(daily, x="DATE", y=["chargeback_rate", "fraud_rate"]))),
            html.Ul([html.Li(t) for t in insight_rates_trend()], style={"color": DD_MUTE, "marginTop": "6px"}),

            section_title("Chargeback Cost Over Time ($)"),
            dcc.Graph(figure=theme_fig(px.line(daily, x="DATE", y="cb_cost"))),
            html.Ul([html.Li(t) for t in insight_cb_cost()], style={"color": DD_MUTE, "marginTop": "6px"}),

            section_title("Average Sift Score & GOV Over Time"),
            dcc.Graph(figure=theme_fig(px.line(daily, x="DATE", y=["avg_sift", "avg_gov"]))),
            html.Ul([html.Li(t) for t in insight_sift_gov()], style={"color": DD_MUTE, "marginTop": "6px"}),
            html.Div([bubble_btn("See: Sift Thresholds", "sift")], style={"margin": "4px 0 12px 0"}),

            section_title("Fraud Rate by Platform"),
            dcc.Graph(figure=theme_fig(px.bar(fraud_by_platform, x="PLATFORM", y="fraud_rate"))),
            html.Ul([html.Li(t) for t in insight_platform()], style={"color": DD_MUTE, "marginTop": "6px"}),
            html.Div([bubble_btn("See: Platform Guardrails", "platform")], style={"margin": "4px 0 12px 0"}),

            section_title("Fraud Rate vs Unique Addresses (lifetime)"),
            dcc.Graph(figure=theme_fig(px.line(fraud_by_addr, x="CX_UNIQUE_ADDRESSES", y="fraud_rate"))),
            html.Ul([html.Li(t) for t in insight_addresses()], style={"color": DD_MUTE, "marginTop": "6px"}),
            html.Div([bubble_btn("See: Address Velocity Controls", "address_velocity")], style={"margin": "4px 0 12px 0"}),

            section_title("Fraud Rate vs Failed Charges (1D)"),
            dcc.Graph(figure=theme_fig(px.line(fraud_by_failed, x="FAIL_CHARGES_1D", y="fraud_rate"))),
            html.Ul([html.Li(t) for t in insight_failed()], style={"color": DD_MUTE, "marginTop": "6px"}),
            html.Div([bubble_btn("See: Failed Payments Step-up", "failed_payments")], style={"margin": "4px 0 12px 0"}),

            section_title("Fraud Rate by GOV Bin"),
            dcc.Graph(figure=theme_fig(px.bar(fraud_by_gov_bin, x="GOV_BIN", y="fraud_rate"))),
            html.Ul([html.Li(t) for t in insight_govbin()], style={"color": DD_MUTE, "marginTop": "6px"}),
            html.Div([bubble_btn("See: High-Value (GOV) Scrutiny", "gov")], style={"margin": "4px 0 12px 0"}),
        ],
    )

    predictors_tab = dcc.Tab(
        label="Fraud Predictors", value="predictors", style=tab_style, selected_style=tab_selected_style,
        children=[
            html.Br(),
            section_title("Top 20 Predictors (Higher |Correlation| ⇒ Stronger Signal)"),
            dcc.Graph(
                figure=theme_fig(
                    px.bar(
                        (lambda _df:
                            _df.head(20).sort_values("CorrelationWithFraud")
                            if not _df.empty else
                            pd.DataFrame({"CorrelationWithFraud": [], "Feature": []})
                        )(pd.DataFrame({
                            "Feature": (lambda s: s.index.tolist())(
                                (df.select_dtypes(include=[np.number]).copy()
                                    .assign(FRAUD_FLAG=df["FRAUD_FLAG"].astype(int))
                                    .corr(numeric_only=True)["FRAUD_FLAG"]
                                    .drop(labels=["FRAUD_FLAG","IS_FRAUDULENT_CHARGEBACK"], errors="ignore"))
                            ),
                            "CorrelationWithFraud": (lambda s: s.values)(
                                (df.select_dtypes(include=[np.number]).copy()
                                    .assign(FRAUD_FLAG=df["FRAUD_FLAG"].astype(int))
                                    .corr(numeric_only=True)["FRAUD_FLAG"]
                                    .drop(labels=["FRAUD_FLAG","IS_FRAUDULENT_CHARGEBACK"], errors="ignore"))
                            )
                        })) ,
                        x="CorrelationWithFraud", y="Feature", orientation="h"
                    )
                )
            ),
            html.Ul(
                [
                    html.Li("Signals are univariate; treat as directional, not causal."),
                    html.Li("Use for rules/threshold ideas, then validate with multivariate models or experiments."),
                ],
                style={"color": DD_MUTE, "marginTop": "6px"}
            ),
            html.Div(
                [
                    bubble_btn("See: Failed Payments Step-up", "failed_payments"),
                    bubble_btn("See: Address Velocity Controls", "address_velocity"),
                    bubble_btn("See: High-Value (GOV) Scrutiny", "gov"),
                    bubble_btn("See: Platform Guardrails", "platform"),
                    bubble_btn("See: Sift Thresholds", "sift"),
                ],
                style={"margin": "8px 0 12px 0"}
            ),
        ],
    )

    recommendations_tab = dcc.Tab(
        label="Recommendations", value="recs", style=tab_style, selected_style=tab_selected_style,
        children=[
            html.Br(),
            section_title("Fraud Mitigation Recommendations"),
            html.Div(id="rec-cards", style={
                "display": "grid",
                "gridTemplateColumns": "repeat(auto-fit, minmax(320px, 1fr))",
                "gap": "12px",
            }),
        ],
    )

    assumptions_tab = dcc.Tab(
        label="Assumptions", value="assumptions", style=tab_style, selected_style=tab_selected_style,
        children=[
            html.Br(),
            section_title("Calculations & Assumptions"),
            html.Div(
                [
                    info_card(
                        "Time & Preprocessing",
                        [
                            "- We aggregate trends by **calendar date**: `DATE = date(CREATED_AT)`.",
                            "- Monetary normalization:",
                            r"$$\text{GOV\_DOLLARS} \,=\, \frac{\text{GOV (cents)}}{100}$$",
                            "- Boolean fields coerced to 0/1 via robust parsing.",
                            "- Heatmap uses `dayofweek` (Mon–Sun) × `hour` (0–23) on fraud rate.",
                        ],
                    ),
                    info_card(
                        "Rates & Ratios",
                        [
                            "- Daily chargeback rate:",
                            r"$$\text{CB\_rate}_{d} \,=\, \frac{\text{chargebacks}_{d}}{\text{deliveries}_{d}}$$",
                            "- Daily fraud rate:",
                            r"$$\text{Fraud\_rate}_{d} \,=\, \frac{\text{fraudulent\ deliveries}_{d}}{\text{deliveries}_{d}}$$",
                            "- Consumer chargeback rate:",
                            r"$$\text{CX\_PCT\_CHARGEBACK} \,=\, \frac{\text{CCR\_CHARGEBACK\_DELIVERIES}}{\text{CCR\_PAST\_DELIVERIES}}$$",
                        ],
                    ),
                    info_card(
                        "Binning & Grouping",
                        [
                            "- GOV risk bands use deciles: `qcut(GOV_DOLLARS, q=10, duplicates='drop')`.",
                            "- GOV bin labels are strings to avoid JSON serialization issues.",
                            "- GroupBy calls pass `observed=False` for pandas compatibility.",
                        ],
                    ),
                    info_card(
                        "Interpretation Notes",
                        [
                            "- Heatmap highlights **when** risk is elevated; apply guardrails in those windows.",
                            "- Correlations are univariate direction signals; confirm with tests/cohorts before policy.",
                            "- Divide-by-zero → 0.0; invalid numerics coerced to NaN and ignored by aggregations.",
                        ],
                    ),
                ],
                style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(420px, 1fr))", "gap": "12px"},
            ),
        ],
    )

    glossary_items_table = dash_table.DataTable(
        data=glossary_df.to_dict("records"),
        columns=[{"name": col, "id": col} for col in glossary_df.columns],
        style_table={"overflowX": "auto", "border": f"1px solid {DD_BORDER}"},
        style_header={"backgroundColor": "#FFF6F3", "fontWeight": "bold", "border": f"1px solid {DD_BORDER}"},
        style_cell={"textAlign": "left", "whiteSpace": "normal", "height": "auto", "border": f"1px solid {DD_BORDER}"},
        page_size=10,
        filter_action="none",
        sort_action="native",
    )

    glossary_tab = dcc.Tab(
        label="Glossary", value="glossary", style=tab_style, selected_style=tab_selected_style,
        children=[
            html.Br(),
            section_title("Field Definitions"),
            html.Div(
                [
                    html.Div("Choose a field:", style={"color": DD_MUTE, "marginBottom": "6px", "fontSize": "13px"}),
                    dcc.Dropdown(
                        id="glossary-dropdown",
                        options=[{"label": f, "value": f} for f in glossary_df["Field"]],
                        value=glossary_df["Field"].iloc[0] if not glossary_df.empty else None,
                        clearable=False,
                        searchable=False,
                        style={"border": f"1px solid {DD_BORDER}"}
                    ),
                ],
                style={"maxWidth": "520px", "margin": "0 auto 10px auto"},
            ),
            html.Div(id="glossary-definition-card", style={"maxWidth": "800px", "margin": "0 auto"}),
            html.Br(),
            glossary_items_table,
            html.Div("Source: Provided dataset/business definitions.",
                     style={"color": DD_MUTE, "fontSize": "12px", "marginTop": "8px", "textAlign": "center"}),
        ],
    )

    tabs = dcc.Tabs(
        id="tabs",
        value="trends",
        style=tabs_styles,
        children=[trends_tab, predictors_tab, recommendations_tab, assumptions_tab, glossary_tab],
    )
    return tabs, header, kpis, date_note

# ---------- Build page ----------
tabs_component, header_component, kpis_component, date_note_component = build_tabs()
app.layout = html.Div(
    [
        dcc.Store(id="rec_target", data=None),   # which recommendation to focus
        header_component,                        # header with logo left + centered title/subtitle
        kpis_component,                          # KPIs
        date_note_component,                     # centered date note
        tabs_component,                          # all tabs
    ],
    style={"maxWidth": "1200px", "margin": "0 auto", "padding": "16px", "background": DD_BG},
)

# ---------- Callbacks ----------
# Glossary definition card
@app.callback(
    Output("glossary-definition-card", "children"),
    Input("glossary-dropdown", "value")
)
def show_glossary_definition(field):
    if not field:
        return html.Div()
    definition = glossary_map.get(field, "—")
    return html.Div(
        [
            html.Div(style={"height": "4px", "background": DD_RED, "borderRadius": "8px 8px 0 0", "marginBottom": "10px"}),
            html.Div(
                [
                    html.Div(field, style={"fontWeight": 700, "color": DD_SLATE, "fontSize": "16px", "marginBottom": "6px"}),
                    html.Div(definition, style={"fontSize": "14px", "color": DD_TEXT}),
                ]
            ),
        ],
        style={
            "background": DD_CARD_BG, "border": f"1px solid {DD_BORDER}", "borderRadius": "12px",
            "padding": "12px 14px", "boxShadow": "0 2px 10px rgba(16,20,24,0.04)"
        },
    )

# Render recommendations, move selected to top + highlight
@app.callback(
    Output("rec-cards", "children"),
    Input("rec_target", "data")
)
def render_recommendations(selected_key):
    return build_rec_cards(selected_key)

# Bubble router: any bubble click → set target + switch to Recommendations tab
@app.callback(
    Output("rec_target", "data"),
    Output("tabs", "value"),
    Input({"type": "rec-bubble", "key": ALL}, "n_clicks"),
    State({"type": "rec-bubble", "key": ALL}, "id"),
    prevent_initial_call=True
)
def route_to_recommendation(all_clicks, all_ids):
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update
    trig = ctx.triggered[0]["prop_id"].split(".")[0]
    try:
        key = json.loads(trig)["key"]
    except Exception:
        key = None
    if key and key in REC_DEFS:
        return key, "recs"
    return dash.no_update, dash.no_update

if __name__ == "__main__":
    # Local/container run (Render uses gunicorn + server above)
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port, debug=False)
