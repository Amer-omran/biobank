"""صفحة التقارير: اختيار المطعم والفترة، ملخص إحصائي، توصيات، وتصدير Excel وPDF وCSV."""

import pandas as pd
import streamlit as st

from sra import analytics, config, reports
from sra.analytics import Filters
from ui_pages.common import get_conn, no_data_message, sentiment_distribution_chart, setup_page, synthetic_banner

setup_page("التقارير", "ملخص إحصائي قابل للتصدير بصيغ Excel وPDF وCSV.")
conn = get_conn()

restaurants = analytics.restaurants_list(conn)
first, last = analytics.date_range(conn)
c1, c2 = st.columns(2)
chosen = c1.multiselect("المطعم (اتركه فارغًا لكل المطاعم)", restaurants, placeholder="كل المطاعم")
period = None
if first and last:
    period = c2.date_input("الفترة الزمنية", value=(pd.to_datetime(first).date(), pd.to_datetime(last).date()))
title = st.text_input("عنوان التقرير", value="تقرير تحليل مشاعر العملاء" + (f" — {'، '.join(chosen)}" if chosen else ""))

filters = Filters(restaurants=chosen or None)
if isinstance(period, (list, tuple)) and len(period) == 2:
    filters.start_date, filters.end_date = period[0].isoformat(), period[1].isoformat()

data = reports.build_report_data(conn, filters, title)
if not data["n_reviews"]:
    no_data_message()
    st.stop()
synthetic_banner(conn)

st.subheader("الملخص الإحصائي")
left, right = st.columns([2, 3])
with left:
    for line in reports.summary_lines(data):
        st.write("• " + line)
with right:
    st.plotly_chart(sentiment_distribution_chart(data["distribution"]), use_container_width=True)

if not data["aspects"].empty:
    st.subheader("جوانب الرأي")
    st.dataframe(pd.DataFrame({
        "الجانب": data["aspects"]["aspect_ar"],
        "عدد الإشارات": data["aspects"]["n"],
        "إيجابي": [analytics.fraction_text(int(p), int(n)) for p, n in zip(data["aspects"]["positive"], data["aspects"]["n"])],
        "سلبي": [analytics.fraction_text(int(p), int(n)) for p, n in zip(data["aspects"]["negative"], data["aspects"]["n"])],
    }), use_container_width=True, hide_index=True)

if not data["dishes"].empty:
    st.subheader("الوجبات الأكثر ذكرًا (مؤشر تفضيل)")
    st.dataframe(data["dishes"][["dish", "category", "mentions", "positive_pct", "negative_pct"]].rename(columns={
        "dish": "الوجبة", "category": "الفئة", "mentions": "تعليقات ذكرتها", "positive_pct": "إيجابي %",
        "negative_pct": "سلبي %"}), use_container_width=True, hide_index=True)

c1, c2 = st.columns(2)
with c1:
    st.subheader("أمثلة على الشكاوى")
    for r in data["complaints"].head(5).to_dict("records"):
        st.markdown(f"- **{config.ASPECT_AR[r['aspect']]}**: {r['evidence']}")
with c2:
    st.subheader("أمثلة على الإشادات")
    for r in data["praises"].head(5).to_dict("records"):
        st.markdown(f"- **{config.ASPECT_AR[r['aspect']]}**: {r['evidence']}")

st.subheader("التوصيات")
for rec in data["recommendations"]:
    st.write("• " + rec)
st.subheader("تنبيهات منهجية")
for caveat in data["caveats"]:
    st.caption("• " + caveat)

st.divider()
st.subheader("التصدير")
d1, d2, d3 = st.columns(3)
stamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M")
d1.download_button("⬇️ Excel", reports.export_excel(data), file_name=f"report_{stamp}.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
try:
    pdf_bytes = reports.export_pdf(data)
    d2.download_button("⬇️ PDF", pdf_bytes, file_name=f"report_{stamp}.pdf", mime="application/pdf")
except FileNotFoundError as exc:
    d2.error(str(exc))
d3.download_button("⬇️ CSV (التعليقات والنتائج)", reports.export_csv(data), file_name=f"reviews_{stamp}.csv",
                   mime="text/csv")
