"""الصفحة الرئيسية: وصف المشروع، الأعداد الأساسية، توزيع المشاعر، حالة البيانات."""

import streamlit as st

from sra import analytics, database, demo_data, pipeline
from ui_pages.common import get_conn, no_data_message, sentiment_distribution_chart, setup_page, synthetic_banner

setup_page("منصة ذكاء اصطناعي لتحليل مشاعر العملاء وتفضيلات الوجبات",
           "Saudi Restaurant Sentiment & Food Preference Analytics Platform")
conn = get_conn()

st.markdown(
    """
<div class="sra-card">
تحلل المنصة مراجعات المطاعم والتعليقات العربية (الفصحى واللهجة السعودية) لاستخراج:
<ul>
<li><b>الشعور العام</b> لكل تعليق: إيجابي، سلبي، محايد، مع درجة ثقة وكشف المشاعر المختلطة.</li>
<li><b>المشاعر حسب الجانب</b>: جودة الطعام، السعر، الكمية، الخدمة، التوصيل، النظافة، الأجواء.</li>
<li><b>الوجبات المذكورة</b> وشعور العملاء تجاهها، اعتمادًا على قاموس قابل للتعديل.</li>
<li><b>مقارنات</b> بين المطاعم والمدن واتجاهات زمنية، مع تقارير Excel وPDF.</li>
</ul>
النتائج <b>مؤشرات مستنتجة من التعليقات</b>: كثرة ذكر وجبة لا تعني كثرة شرائها.
</div>
""",
    unsafe_allow_html=True,
)

stats = analytics.overview(conn)
c1, c2, c3, c4 = st.columns(4)
c1.metric("عدد التعليقات", f"{stats['n_reviews']:,}")
c2.metric("عدد المطاعم", f"{stats['n_restaurants']:,}")
c3.metric("التعليقات المحللة", f"{stats['n_analyzed']:,}")
c4.metric("وجبات في القاموس", f"{stats['n_dishes']:,}")

synthetic_banner(conn)

left, right = st.columns([3, 2])
with left:
    reviews = analytics.analyzed_reviews(conn)
    if reviews.empty:
        no_data_message()
    else:
        st.plotly_chart(sentiment_distribution_chart(analytics.sentiment_distribution(reviews)),
                        use_container_width=True)
with right:
    st.subheader("حالة البيانات")
    n = stats["n_reviews"]

    def share(k):
        return f"{k} من {n}" if n else "—"

    st.markdown(
        f"""
- مجموعات البيانات: **{stats['n_datasets']}**
- تعليقات تحمل تاريخًا: **{share(stats['n_with_date'])}**
- تعليقات تحمل مدينة: **{share(stats['n_with_city'])}**
- تعليقات تحمل تقييمًا رقميًا: **{share(stats['n_with_rating'])}**
- تعليقات اصطناعية (تجريبية): **{share(stats['n_synthetic_reviews'])}**
- تعليقات لم تُحلل بعد: **{max(0, n - stats['n_analyzed'])}**
"""
    )
    integrity = database.integrity_report(conn)
    if integrity["foreign_key_violations"] == 0 and integrity["integrity"] == "ok":
        st.success("سلامة قاعدة البيانات والعلاقات: سليمة ✓")
    else:
        st.error(f"مشكلة في سلامة قاعدة البيانات: {integrity}")

st.divider()
st.subheader("ابدأ بسرعة")
st.write("لا تملك بيانات حقيقية بعد؟ حمّل بيانات تجريبية اصطناعية لتجربة كل صفحات المنصة.")
if st.button("تحميل البيانات التجريبية وتحليلها", type="primary"):
    with st.spinner("جارٍ التوليد والتحليل..."):
        result = demo_data.load_demo_into_db(conn)
        counts = pipeline.analyze_reviews(conn, [result["dataset_id"]], only_new=True)
    st.success(f"أُضيف {result['inserted']} تعليقًا تجريبيًا (تجاهل {result['skipped_duplicates']} مكررًا موجودًا)، "
               f"وحُلل {counts['analyzed']} تعليقًا.")
    st.rerun()
