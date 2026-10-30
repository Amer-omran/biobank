"""صفحة مقارنة المطاعم والمدن، مع حد أدنى للبيانات قبل أي ترتيب."""

import streamlit as st

from sra import analytics, config
from ui_pages.common import (
    get_conn,
    no_data_message,
    setup_page,
    sidebar_filters,
    stacked_share_chart,
    synthetic_banner,
    trend_chart,
)

setup_page("مقارنة المطاعم", "كل نسبة معروضة مع بسطها ومقامها، ولا يُرتب مطعم بيانات تعليقاته غير كافية.")
conn = get_conn()
filters = sidebar_filters(conn, "cmp")
min_reviews = st.sidebar.number_input("الحد الأدنى من التعليقات للترتيب", 5, 500, config.MIN_REVIEWS_FOR_RANKING)

all_restaurants = analytics.restaurants_list(conn)
if not all_restaurants:
    no_data_message("مطاعم")
    st.stop()
chosen = st.multiselect("اختر مطعمًا أو أكثر للمقارنة", all_restaurants,
                        default=filters.restaurants or all_restaurants[: min(4, len(all_restaurants))])
if not chosen:
    st.info("اختر مطعمًا واحدًا على الأقل.")
    st.stop()
filters.restaurants = chosen
reviews = analytics.analyzed_reviews(conn, filters)
if reviews.empty:
    no_data_message()
    st.stop()
synthetic_banner(conn, filters.dataset_ids)

comparison = analytics.restaurant_comparison(reviews, int(min_reviews))
st.subheader("الشعور العام لكل مطعم")
st.plotly_chart(stacked_share_chart(comparison, "restaurant_name", "توزيع المشاعر لكل مطعم"),
                use_container_width=True)

table = comparison.copy()
table["rank"] = table["rank"].map(lambda r: "—" if r != r else int(r))
table["ci"] = table.apply(lambda r: f"{r['positive_ci_low']}% – {r['positive_ci_high']}%", axis=1)
table["status"] = table["rankable"].map({True: "كافية للترتيب", False: f"غير كافية (< {int(min_reviews)})"})
st.dataframe(
    table[["rank", "restaurant_name", "n", "positive_text", "ci", "negative_pct", "status"]].rename(columns={
        "rank": "الترتيب", "restaurant_name": "المطعم", "n": "عدد التعليقات", "positive_text": "الإيجابي (بسط من مقام)",
        "ci": "فترة الثقة 95% للإيجابي", "negative_pct": "سلبي %", "status": "حالة البيانات"}),
    use_container_width=True, hide_index=True,
)
st.caption("الترتيب يعتمد على الحد الأدنى لفترة ثقة ويلسون للنسبة الإيجابية، حتى لا يتقدم مطعم بعدد "
           "قليل جدًا من التعليقات. الفروق الصغيرة بين فترات متداخلة قد لا تكون فروقًا حقيقية.")
if (~comparison["rankable"]).any():
    names = "، ".join(comparison.loc[~comparison["rankable"], "restaurant_name"])
    st.warning(f"لم تُرتب المطاعم التالية لقلة بياناتها: {names}")

st.subheader("المقارنة حسب جوانب الرأي")
aspects = analytics.aspects_frame(conn, filters)
matrix = analytics.restaurant_aspect_matrix(aspects, chosen)
if matrix.empty:
    st.info("لا توجد جوانب رأي كافية.")
else:
    aspect = st.selectbox("الجانب", list(config.ASPECTS), format_func=config.ASPECT_AR.get)
    sub = matrix[matrix["aspect"] == aspect]
    if sub.empty:
        st.info("لا توجد إشارات لهذا الجانب في المطاعم المختارة.")
    else:
        st.plotly_chart(stacked_share_chart(sub, "restaurant_name", f"{config.ASPECT_AR[aspect]} حسب المطعم"),
                        use_container_width=True)
    pivot = matrix.pivot_table(index="aspect_ar", columns="restaurant_name", values="positive_text", aggfunc="first")
    pivot.index.name, pivot.columns.name = "الجانب", None
    st.markdown("**نسبة الإشارات الإيجابية لكل جانب (بسط من مقام)**")
    st.dataframe(pivot.fillna("لا توجد بيانات"), use_container_width=True)

st.subheader("الاتجاه عبر الزمن")
trend_restaurant = st.selectbox("المطعم", chosen, key="trend_rest")
trend = analytics.sentiment_trend(reviews[reviews["restaurant_name"] == trend_restaurant],
                                  st.radio("الفترة", ["M", "Q"], horizontal=True,
                                           format_func={"M": "شهري", "Q": "ربع سنوي"}.get))
if trend.empty:
    st.info("لا توجد تواريخ في بيانات هذا المطعم.")
else:
    st.plotly_chart(trend_chart(trend), use_container_width=True)
    st.caption("الفترات ذات العدد القليل من التعليقات (انظر ن عند المرور على النقاط) تتذبذب نسبها كثيرًا.")

st.subheader("المقارنة بين المدن")
cities = analytics.city_comparison(analytics.analyzed_reviews(conn, analytics.Filters(
    dataset_ids=filters.dataset_ids, start_date=filters.start_date, end_date=filters.end_date,
    model_version=filters.model_version)), int(min_reviews))
if cities.empty:
    st.info("لا توجد بيانات مدن موثوقة (أسماء مدن سعودية معروفة) في البيانات المختارة.")
else:
    enough = cities[cities["enough_data"]]
    if not enough.empty:
        st.plotly_chart(stacked_share_chart(enough, "city", "توزيع المشاعر حسب المدينة"), use_container_width=True)
    low = cities[~cities["enough_data"]]
    if not low.empty:
        st.caption("مدن بيانات غير كافية للمقارنة: " + "، ".join(f"{c} (ن={n})" for c, n in zip(low["city"], low["n"])))
    st.caption("تعكس المقارنة المطاعم الموجودة في البيانات لكل مدينة، ولا تمثل المدينة كلها.")
