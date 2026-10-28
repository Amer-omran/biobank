"""صفحة تحليل الوجبات: الأكثر ذكرًا، توزيع المشاعر لكل وجبة، الجوانب، البحث، الكلمات والموضوعات."""

import streamlit as st

from sra import analytics, config
from ui_pages.common import (
    count_bar_chart,
    format_sentiment_table,
    get_conn,
    no_data_message,
    setup_page,
    sidebar_filters,
    stacked_share_chart,
    synthetic_banner,
)

setup_page("تحليل الوجبات وتفضيلات الطعام",
           "مؤشرات تفضيل مستنتجة من التعليقات — عدد مرات الذكر لا يعني عدد مرات الشراء.")
conn = get_conn()
filters = sidebar_filters(conn, "dish")
dishes = analytics.dishes_frame(conn, filters)
reviews = analytics.analyzed_reviews(conn, filters)
if reviews.empty:
    no_data_message()
    st.stop()
synthetic_banner(conn, filters.dataset_ids)

summary = analytics.dish_summary(dishes)
st.info(f"ذُكرت وجبة واحدة على الأقل في {dishes['review_id'].nunique() if not dishes.empty else 0} "
        f"من {len(reviews)} تعليقًا محللًا. الاستخراج يعتمد على قاموس الوجبات فقط، فلا تظهر وجبة لم تُذكر نصًا.")

if summary.empty:
    st.warning("لم يُعثر على أسماء وجبات من القاموس في التعليقات المختارة. أضف أسماء من صفحة «قاموس الوجبات».")
else:
    top_n = st.slider("عدد الوجبات المعروضة", 5, min(30, max(5, len(summary))), min(10, len(summary)))
    top = summary.head(top_n)
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(count_bar_chart(top, "dish", "mentions", "الوجبات الأكثر ذكرًا (عدد التعليقات)"),
                        use_container_width=True)
    with c2:
        st.plotly_chart(stacked_share_chart(top, "dish", "توزيع المشاعر تجاه كل وجبة", n_col="mentions"),
                        use_container_width=True)
    st.caption("الوجبات ذات العدد القليل من الإشارات (ن صغيرة) لا تكفي لاستنتاج تفضيل واضح.")

    st.subheader("البحث عن وجبة")
    dish = st.selectbox("اختر وجبة", summary["dish"].tolist())
    row = summary[summary["dish"] == dish].iloc[0]
    m1, m2, m3 = st.columns(3)
    m1.metric("تعليقات ذكرتها", int(row["mentions"]))
    m2.metric("إيجابي", analytics.fraction_text(int(row["positive"]), int(row["mentions"])))
    m3.metric("سلبي", analytics.fraction_text(int(row["negative"]), int(row["mentions"])))

    aspects = analytics.aspects_frame(conn, filters)
    dish_aspects = aspects[aspects["dish"] == dish] if not aspects.empty else aspects
    aspect_table = analytics.aspect_summary(dish_aspects)
    if not aspect_table.empty:
        st.plotly_chart(stacked_share_chart(aspect_table, "aspect_ar", f"جوانب الرضا والشكاوى المرتبطة بـ {dish}"),
                        use_container_width=True)
    mentions = dishes[dishes["dish"] == dish]
    by_restaurant = analytics.counts_table(mentions.dropna(subset=["restaurant_name"]), ["restaurant_name"])
    if not by_restaurant.empty:
        st.markdown("**حسب المطعم**")
        st.dataframe(by_restaurant.rename(columns={"restaurant_name": "المطعم", "n": "الإشارات",
                                                   "positive": "إيجابي", "negative": "سلبي", "neutral": "محايد",
                                                   "positive_pct": "إيجابي %", "negative_pct": "سلبي %",
                                                   "neutral_pct": "محايد %"}),
                     use_container_width=True, hide_index=True)
    st.markdown("**تعليقات ذكرت الوجبة**")
    st.dataframe(format_sentiment_table(mentions[["text", "matched_text", "sentiment", "evidence", "restaurant_name"]]
                                        .rename(columns={"matched_text": "كما وردت"})),
                 use_container_width=True, hide_index=True)

st.divider()
st.subheader("أبرز جوانب الرضا والشكاوى (لكل الوجبات والخدمات)")
highlights = analytics.satisfaction_highlights(analytics.aspects_frame(conn, filters))
c1, c2 = st.columns(2)
for col, key, title, pct in ((c1, "strengths", "أعلى رضا", "positive"), (c2, "complaints", "أعلى شكاوى", "negative")):
    with col:
        st.markdown(f"**{title}** (جوانب لها 5 إشارات على الأقل)")
        table = highlights[key].head(4)
        for r in table.to_dict("records"):
            st.write(f"• {r['aspect_ar']}: {analytics.fraction_text(int(r[pct]), int(r['n']))}")
        if table.empty:
            st.caption("لا توجد إشارات كافية.")

st.subheader("الكلمات والعبارات الأكثر تكرارًا")
k1, k2 = st.columns(2)
sentiment_choice = k1.selectbox("في التعليقات", ["all", *config.SENTIMENTS],
                                format_func=lambda s: "كل التعليقات" if s == "all" else config.SENTIMENT_AR[s])
ngram = k2.radio("النوع", [1, 2], format_func=lambda n: "كلمات" if n == 1 else "عبارات ثنائية", horizontal=True)
texts = reviews if sentiment_choice == "all" else reviews[reviews["sentiment"] == sentiment_choice]
keywords = analytics.top_keywords(texts["clean_text"], 20, ngram)
if not keywords.empty:
    st.plotly_chart(count_bar_chart(keywords, "term", "count", "الأكثر تكرارًا", color="#1c5cab"),
                    use_container_width=True)

with st.expander("الموضوعات المستخرجة آليًا (NMF)"):
    topics = analytics.extract_topics(texts["clean_text"].tolist())
    if not topics:
        st.caption("تحتاج إلى 30 تعليقًا على الأقل لاستخراج الموضوعات.")
    for i, words in enumerate(topics, 1):
        st.write(f"الموضوع {i}: " + "، ".join(words))
    st.caption("الموضوعات مجموعات كلمات تتكرر معًا؛ تسميتها وتفسيرها يحتاجان مراجعة بشرية.")
