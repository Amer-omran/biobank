"""مكونات مشتركة بين صفحات الواجهة: الاتجاه من اليمين لليسار، الاتصال بالقاعدة، المرشحات، الرسوم."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from sra import analytics, config, database
from sra.analytics import Filters

RTL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stText, p, li, label, h1, h2, h3, h4, input, textarea, select {
    font-family: 'Tajawal', 'Segoe UI', 'Noto Sans Arabic', Tahoma, sans-serif;
}
.main .block-container, [data-testid="stSidebar"], [data-testid="stMarkdownContainer"],
[data-testid="stCaptionContainer"], .stAlert, [data-testid="stExpander"], [data-testid="stForm"],
[data-testid="stMetric"], [data-testid="stWidgetLabel"], .stRadio, .stCheckbox, .stSelectbox,
.stMultiSelect, .stTextInput, .stTextArea, .stDateInput, .stNumberInput, .stFileUploader, .stTabs {
    direction: rtl;
    text-align: right;
}
[data-testid="stSidebarNav"] { direction: rtl; }
[data-testid="stMetricValue"] { direction: ltr; text-align: right; }
.stDataFrame, .js-plotly-plot { direction: ltr; }
.sra-card {
    border: 1px solid rgba(31, 95, 74, 0.25); border-radius: 12px; padding: 0.8rem 1rem;
    margin-bottom: 0.6rem; background: rgba(31, 95, 74, 0.04);
}
.sra-badge {
    display: inline-block; padding: 0.1rem 0.6rem; border-radius: 999px; font-size: 0.85rem;
    color: #fff; margin-left: 0.3rem;
}
.sra-badge.outline { background: transparent; border: 1px solid #898781; color: inherit; }
.sra-synthetic {
    border-right: 5px solid #e34948; background: rgba(227, 73, 72, 0.08); padding: 0.6rem 1rem;
    border-radius: 6px; margin: 0.5rem 0 1rem 0;
}
</style>
"""

PLOT_FONT = dict(family="Tajawal, Segoe UI, Tahoma, sans-serif", size=14)


def setup_page(title: str, subtitle: str | None = None) -> None:
    st.markdown(RTL_CSS, unsafe_allow_html=True)
    st.title(title)
    if subtitle:
        st.caption(subtitle)


@st.cache_resource
def get_conn():
    """اتصال واحد بقاعدة البيانات طوال تشغيل التطبيق (تُنشأ القاعدة تلقائيًا أول مرة)."""
    return database.connect()


def synthetic_banner(conn, dataset_ids=None) -> None:
    ds = database.list_datasets(conn)
    if dataset_ids:
        ds = ds[ds["id"].isin(dataset_ids)]
    if not ds.empty and ds["is_synthetic"].astype(bool).any():
        st.markdown(
            '<div class="sra-synthetic">⚠️ <b>تنبيه:</b> البيانات المعروضة تشمل <b>بيانات تجريبية اصطناعية</b> '
            "مولدة آليًا لتجربة المنصة. أسماء المطاعم خيالية، والنتائج <b>ليست نتائج بحثية فعلية</b>.</div>",
            unsafe_allow_html=True,
        )


def sidebar_filters(conn, key: str, show_model: bool = True, show_dates: bool = True) -> Filters:
    """مرشحات موحدة في الشريط الجانبي: مجموعة البيانات، المطعم، المدينة، الفترة، إصدار النموذج."""
    st.sidebar.header("المرشحات")
    datasets = database.list_datasets(conn)
    dataset_ids = None
    if not datasets.empty:
        labels = {int(r.id): f"{r.name}{' (اصطناعية)' if r.is_synthetic else ''}" for r in datasets.itertuples()}
        chosen = st.sidebar.multiselect("مجموعة البيانات", list(labels), format_func=labels.get,
                                        key=f"{key}_ds", placeholder="الكل")
        dataset_ids = chosen or None
    restaurants = st.sidebar.multiselect("المطعم", analytics.restaurants_list(conn), key=f"{key}_rest",
                                         placeholder="الكل") or None
    cities = st.sidebar.multiselect("المدينة", analytics.cities_list(conn), key=f"{key}_city",
                                    placeholder="الكل") or None
    start = end = None
    if show_dates:
        first, last = analytics.date_range(conn)
        if first and last:
            use_dates = st.sidebar.checkbox("تحديد فترة زمنية", key=f"{key}_use_dates")
            if use_dates:
                picked = st.sidebar.date_input("الفترة", value=(pd.to_datetime(first).date(), pd.to_datetime(last).date()),
                                               key=f"{key}_dates")
                if isinstance(picked, (list, tuple)) and len(picked) == 2:
                    start, end = picked[0].isoformat(), picked[1].isoformat()
    model_version = None
    if show_model:
        versions = database.model_versions(conn)
        if len(versions) > 1:
            choice = st.sidebar.selectbox("إصدار النموذج", ["أحدث تحليل لكل تعليق"] + versions, key=f"{key}_model")
            model_version = None if choice == "أحدث تحليل لكل تعليق" else choice
    return Filters(dataset_ids=dataset_ids, restaurants=restaurants, cities=cities,
                   start_date=start, end_date=end, model_version=model_version)


def sentiment_badges(sentiment: str, confidence: float, is_mixed: bool, is_uncertain: bool) -> str:
    color = config.SENTIMENT_COLORS[sentiment]
    html = f'<span class="sra-badge" style="background:{color}">{config.SENTIMENT_AR[sentiment]}</span>'
    html += f'<span class="sra-badge outline">الثقة {confidence:.0%}</span>'
    if is_mixed:
        html += '<span class="sra-badge outline">مشاعر مختلطة</span>'
    if is_uncertain:
        html += '<span class="sra-badge outline">⚠ غير مؤكد</span>'
    return html


def _rtl_layout(fig: go.Figure, height: int = 360, **kwargs) -> go.Figure:
    # وسيلة الإيضاح أسفل الرسم حتى لا تتداخل مع العنوان
    fig.update_layout(font=PLOT_FONT, height=height, margin=dict(l=20, r=20, t=50, b=60),
                      legend=dict(orientation="h", yanchor="top", y=-0.12, xanchor="right", x=1), **kwargs)
    return fig


def sentiment_distribution_chart(dist: pd.DataFrame, title: str = "توزيع المشاعر") -> go.Figure:
    """أعمدة أفقية تنمو من اليمين، مع تسمية مباشرة تبين العدد والمقام."""
    fig = go.Figure(go.Bar(
        y=dist["label"], x=dist["count"], orientation="h",
        marker=dict(color=[config.SENTIMENT_COLORS[s] for s in dist["sentiment"]], cornerradius=4),
        text=dist["text"], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{text}<extra></extra>",
    ))
    top = max(1, int(dist["count"].max()))
    fig.update_xaxes(range=[top * 1.45, 0], showgrid=True, gridcolor="rgba(137,135,129,0.2)", title="عدد التعليقات")
    fig.update_yaxes(side="right", categoryorder="array", categoryarray=list(dist["label"])[::-1])
    return _rtl_layout(fig, height=260, title=title, showlegend=False, bargap=0.35)


def stacked_share_chart(table: pd.DataFrame, label_col: str, title: str, n_col: str = "n",
                        height: int | None = None) -> go.Figure:
    """أعمدة مكدسة 100% (إيجابي/محايد/سلبي) مع عرض المقام في اسم الفئة."""
    labels = [f"{lbl} (ن={int(n)})" for lbl, n in zip(table[label_col], table[n_col])]
    fig = go.Figure()
    for s in ("positive", "neutral", "negative"):
        fig.add_bar(
            y=labels, x=table[f"{s}_pct"], name=config.SENTIMENT_AR[s], orientation="h",
            marker=dict(color=config.SENTIMENT_COLORS[s], line=dict(color="white", width=2)),
            customdata=table[[s, n_col]].values,
            hovertemplate="%{y}<br>" + config.SENTIMENT_AR[s] + ": %{customdata[0]} من %{customdata[1]} (%{x}%)<extra></extra>",
            text=[f"{v:.0f}%" if v >= 8 else "" for v in table[f"{s}_pct"]], textposition="inside",
            insidetextanchor="middle",
        )
    fig.update_layout(barmode="stack")
    fig.update_xaxes(range=[100, 0], ticksuffix="%")
    fig.update_yaxes(side="right", autorange="reversed")
    return _rtl_layout(fig, height=height or max(260, 48 * len(labels) + 90), title=title)


def trend_chart(trend: pd.DataFrame, title: str = "اتجاه المشاعر عبر الزمن") -> go.Figure:
    fig = go.Figure()
    for s in ("positive", "neutral", "negative"):
        fig.add_scatter(
            x=trend["period"], y=trend[f"{s}_pct"], name=config.SENTIMENT_AR[s], mode="lines+markers",
            line=dict(color=config.SENTIMENT_COLORS[s], width=2), marker=dict(size=8),
            customdata=trend[[s, "n"]].values,
            hovertemplate="%{x}<br>" + config.SENTIMENT_AR[s] + ": %{customdata[0]} من %{customdata[1]} (%{y}%)<extra></extra>",
        )
    fig.update_yaxes(title="النسبة %", ticksuffix="%", rangemode="tozero", gridcolor="rgba(137,135,129,0.2)")
    fig.update_xaxes(title="الشهر")
    return _rtl_layout(fig, height=380, title=title, hovermode="x unified")


def count_bar_chart(table: pd.DataFrame, label_col: str, value_col: str, title: str,
                    color: str = "#2a78d6") -> go.Figure:
    fig = go.Figure(go.Bar(
        y=table[label_col], x=table[value_col], orientation="h", marker=dict(color=color, cornerradius=4),
        text=table[value_col], textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{x}<extra></extra>",
    ))
    top = max(1, float(table[value_col].max())) if len(table) else 1
    fig.update_xaxes(range=[top * 1.2, 0], gridcolor="rgba(137,135,129,0.2)")
    fig.update_yaxes(side="right", autorange="reversed")
    return _rtl_layout(fig, height=max(260, 30 * len(table) + 90), title=title, showlegend=False)


def format_sentiment_table(df: pd.DataFrame) -> pd.DataFrame:
    """تحويل أسماء الأعمدة والقيم إلى العربية للعرض."""
    out = df.copy()
    if "sentiment" in out:
        out["sentiment"] = out["sentiment"].map(config.SENTIMENT_AR)
    if "aspect" in out:
        out["aspect"] = out["aspect"].map(config.ASPECT_AR)
    for col in ("is_mixed", "is_uncertain", "has_opinion"):
        if col in out:
            out[col] = out[col].map({1: "نعم", 0: "لا", True: "نعم", False: "لا"})
    return out.rename(columns={
        "text": "التعليق الأصلي", "restaurant_name": "المطعم", "city": "المدينة", "review_date": "التاريخ",
        "original_rating": "التقييم الأصلي", "sentiment": "الشعور", "confidence": "درجة الثقة",
        "is_mixed": "مختلط", "is_uncertain": "غير مؤكد", "cues": "كلمات الرأي", "aspect": "الجانب",
        "evidence": "العبارة الداعمة", "dish": "الوجبة", "has_opinion": "يوجد رأي", "score": "الدرجة",
        "dataset": "مجموعة البيانات", "model_version": "إصدار النموذج", "external_label": "الوسم الأصلي",
    })


def no_data_message(what: str = "تعليقات محللة") -> None:
    st.info(f"لا توجد {what} بعد. ابدأ من صفحة «استيراد البيانات» ثم «تحليل المشاعر»، "
            "أو حمّل البيانات التجريبية من الصفحة الرئيسية.")
