"""صفحة تحليل المشاعر: تشغيل التحليل، عرض الشعور ودرجة الثقة والتعليق الأصلي والجوانب."""

import pandas as pd
import streamlit as st

from sra import analytics, config, database, ml_model, pipeline
from sra.transformer_model import TransformerUnavailable, transformers_installed
from ui_pages.common import (
    format_sentiment_table,
    get_conn,
    no_data_message,
    sentiment_badges,
    sentiment_distribution_chart,
    setup_page,
    sidebar_filters,
    stacked_share_chart,
    synthetic_banner,
)

setup_page("تحليل المشاعر", "الشعور العام لكل تعليق مع درجة الثقة، والمشاعر حسب جوانب الرأي.")
conn = get_conn()

# ============================================================ تجربة نص
with st.expander("✍️ جرّب تحليل تعليق واحد", expanded=False):
    sample = st.text_area("اكتب تعليقًا", value="الكبسة لذيذة مرة بس الخدمة بطيئة والأسعار غالية")
    if sample.strip():
        result = pipeline.build_analyzer(conn).analyze(sample)
        st.markdown(sentiment_badges(result.label, result.confidence, result.is_mixed, result.is_uncertain),
                    unsafe_allow_html=True)
        st.caption(f"كلمات الرأي المكتشفة: {'، '.join(result.cues) or 'لا يوجد'}")
        if result.aspects:
            st.dataframe(format_sentiment_table(pd.DataFrame([a.__dict__ for a in result.aspects])),
                         use_container_width=True, hide_index=True)
        if result.dishes:
            st.write("الوجبات المذكورة: " + "، ".join(f"{d.dish} ({config.SENTIMENT_AR[d.sentiment]})"
                                                     for d in result.dishes))

# ========================================================== تشغيل التحليل
st.subheader("تشغيل التحليل")
datasets = database.list_datasets(conn)
if datasets.empty:
    no_data_message("مجموعات بيانات")
    st.stop()

labels = {int(r.id): f"{r.name} ({r.n_reviews} تعليقًا){' — اصطناعية' if r.is_synthetic else ''}"
          for r in datasets.itertuples()}
chosen = st.multiselect("مجموعات البيانات المراد تحليلها", list(labels), default=list(labels),
                        format_func=labels.get)

engines = {"lexicon": pipeline.ENGINES["lexicon"]}
meta = ml_model.load_metadata()
if meta:
    engines["sklearn"] = f"{pipeline.ENGINES['sklearn']} — {meta['model_version']}"
if transformers_installed():
    engines["transformers"] = f"{pipeline.ENGINES['transformers']} — {config.DEFAULT_TRANSFORMER_MODEL}"
engine = st.radio("محرك الشعور العام", list(engines), format_func=engines.get, horizontal=False)
if engine != "lexicon":
    st.caption("جوانب الرأي والوجبات تُستخرج دائمًا بمحلل القاموس، والمحرك المختار يحدد الشعور العام فقط.")
if engine == "sklearn" and meta and meta.get("data_is_synthetic"):
    st.warning("هذا النموذج دُرّب على بيانات اصطناعية؛ لا تعتمد عليه في نتائج بحثية.")
only_new = st.checkbox("تحليل التعليقات غير المحللة بهذا الإصدار فقط", value=True)

if st.button("تشغيل التحليل", type="primary", disabled=not chosen):
    bar = st.progress(0.0, text="جارٍ التحليل...")
    try:
        counts = pipeline.analyze_reviews(
            conn, chosen, engine=engine, only_new=only_new,
            progress=lambda done, total: bar.progress(done / max(total, 1), text=f"{done} من {total}"),
        )
    except (FileNotFoundError, TransformerUnavailable) as exc:
        st.error(str(exc))
        st.stop()
    bar.empty()
    st.success(
        f"تم تحليل {counts['analyzed']} تعليقًا بالإصدار {counts['model_version']}: "
        f"{counts['positive']} إيجابي، {counts['negative']} سلبي، {counts['neutral']} محايد؛ "
        f"منها {counts['mixed']} مختلط و{counts['uncertain']} غير مؤكد."
    )

st.divider()

# ================================================================ النتائج
filters = sidebar_filters(conn, "sent")
reviews = analytics.analyzed_reviews(conn, filters)
if reviews.empty:
    no_data_message()
    st.stop()
synthetic_banner(conn, filters.dataset_ids)

c1, c2 = st.columns([1, 1])
with c1:
    st.plotly_chart(sentiment_distribution_chart(analytics.sentiment_distribution(reviews)),
                    use_container_width=True)
with c2:
    aspects = analytics.aspects_frame(conn, filters)
    summary = analytics.aspect_summary(aspects)
    if not summary.empty:
        st.plotly_chart(stacked_share_chart(summary, "aspect_ar", "المشاعر حسب الجانب"), use_container_width=True)

n = len(reviews)
st.caption(f"المختلطة: {analytics.fraction_text(int(reviews['is_mixed'].sum()), n)} — "
           f"غير المؤكدة (ثقة أقل من {config.CONFIDENCE_THRESHOLD:.0%}): "
           f"{analytics.fraction_text(int(reviews['is_uncertain'].sum()), n)}")

st.subheader("التعليقات ونتائجها")
f1, f2, f3, f4 = st.columns(4)
sentiment_filter = f1.multiselect("الشعور", list(config.SENTIMENTS), format_func=config.SENTIMENT_AR.get,
                                  placeholder="الكل")
only_uncertain = f2.checkbox("غير المؤكدة فقط")
only_mixed = f3.checkbox("المختلطة فقط")
search = f4.text_input("بحث في النص")
view = reviews
if sentiment_filter:
    view = view[view["sentiment"].isin(sentiment_filter)]
if only_uncertain:
    view = view[view["is_uncertain"] == 1]
if only_mixed:
    view = view[view["is_mixed"] == 1]
if search.strip():
    view = view[view["text"].str.contains(search.strip(), regex=False, na=False)]
st.caption(f"المعروض: {len(view)} من {n}")
columns = ["text", "sentiment", "confidence", "is_mixed", "is_uncertain", "cues", "restaurant_name",
           "review_date", "original_rating", "model_version"]
st.dataframe(format_sentiment_table(view[columns]), use_container_width=True, hide_index=True,
             column_config={"درجة الثقة": st.column_config.ProgressColumn(min_value=0, max_value=1, format="%.2f")})

st.subheader("تفاصيل تعليق")
if not view.empty:
    options = view["review_id"].tolist()[:500]
    texts = dict(zip(view["review_id"], view["text"]))
    picked = st.selectbox("اختر تعليقًا", options, format_func=lambda i: texts[i][:90])
    row = view[view["review_id"] == picked].iloc[0]
    st.markdown(f'<div class="sra-card">{row["text"]}</div>', unsafe_allow_html=True)
    st.markdown(sentiment_badges(row["sentiment"], row["confidence"], bool(row["is_mixed"]),
                                 bool(row["is_uncertain"])), unsafe_allow_html=True)
    detail = aspects[aspects["review_id"] == picked] if not aspects.empty else aspects
    if detail.empty:
        st.caption("لم يُستخرج جانب رأي محدد من هذا التعليق.")
    else:
        st.dataframe(format_sentiment_table(detail[["aspect", "sentiment", "score", "evidence", "dish", "has_opinion"]]),
                     use_container_width=True, hide_index=True)
