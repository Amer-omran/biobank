"""نقطة تشغيل المنصة.

التشغيل:
    streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="منصة تحليل مشاعر عملاء المطاعم",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page("ui_pages/home.py", title="الرئيسية", icon="🏠", default=True),
    st.Page("ui_pages/import_data.py", title="استيراد البيانات", icon="📥"),
    st.Page("ui_pages/sentiment_page.py", title="تحليل المشاعر", icon="💬"),
    st.Page("ui_pages/dishes_page.py", title="تحليل الوجبات", icon="🍛"),
    st.Page("ui_pages/compare_page.py", title="مقارنة المطاعم", icon="⚖️"),
    st.Page("ui_pages/reports_page.py", title="التقارير", icon="📄"),
    st.Page("ui_pages/model_page.py", title="النموذج والتقييم", icon="🧠"),
    st.Page("ui_pages/dictionary_page.py", title="قاموس الوجبات", icon="📖"),
]
st.navigation(pages).run()
