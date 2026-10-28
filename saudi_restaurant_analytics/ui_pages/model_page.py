"""صفحة النموذج والتقييم: تدريب نموذج Scikit-learn، قياس الأداء، وحالة نموذج Hugging Face."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from sra import analytics, config, database, ml_model
from sra.importer import ratings_to_labels
from sra.transformer_model import transformers_installed
from ui_pages.common import get_conn, setup_page, sidebar_filters

setup_page("النموذج والتقييم", "درّب نموذج تعلم آلي وقِس أداءه على بيانات اختبار لم يرها أثناء التدريب.")
conn = get_conn()


def confusion_figure(matrix, labels, title):
    names = [config.SENTIMENT_AR[x] for x in labels]
    fig = go.Figure(go.Heatmap(z=matrix, x=names, y=names, colorscale=[[0, "#f0efec"], [1, "#1c5cab"]],
                               text=matrix, texttemplate="%{text}", showscale=False,
                               hovertemplate="الحقيقي: %{y}<br>المتوقع: %{x}<br>العدد: %{z}<extra></extra>"))
    fig.update_layout(title=title, height=340, xaxis_title="المتوقع", yaxis_title="الحقيقي",
                      font=dict(family="Tajawal, Segoe UI, sans-serif"))
    fig.update_yaxes(autorange="reversed")
    return fig


tab_train, tab_eval, tab_hf = st.tabs(["🏋️ تدريب Scikit-learn", "📏 مقارنة بالوسوم الأصلية", "🤗 Hugging Face"])

with tab_train:
    st.markdown(
        """
النموذج: **TF-IDF** (مقاطع حروف + كلمات) مع **انحدار لوجستي**. يحتاج وسومًا للتدريب:
- **عمود الوسم** المستورد مع البيانات (الأفضل، إن كان موسومًا بشريًا)، أو
- **وسوم مشتقة من التقييم الرقمي** (1-2 سلبي، 3 محايد، 4-5 إيجابي) — وسوم تقريبية قد تخالف نص التعليق.

تُقسم البيانات 80% تدريب و20% اختبار، والأرقام المعروضة من بيانات الاختبار فقط.
"""
    )
    datasets = database.list_datasets(conn)
    if datasets.empty:
        st.info("لا توجد بيانات. استورد بيانات أولًا.")
        st.stop()
    labels = {int(r.id): f"{r.name}{' (اصطناعية)' if r.is_synthetic else ''}" for r in datasets.itertuples()}
    chosen = st.multiselect("بيانات التدريب", list(labels), default=list(labels), format_func=labels.get)
    source = st.radio("مصدر الوسوم", ["labels", "ratings"], horizontal=True,
                      format_func={"labels": "عمود الوسم", "ratings": "مشتقة من التقييم"}.get)
    rating_max = st.number_input("أعلى قيمة في مقياس التقييم", 1.0, 100.0, 5.0) if source == "ratings" else 5.0

    reviews = database.fetch_reviews(conn, chosen)
    reviews["label"] = (ratings_to_labels(reviews["original_rating"], rating_max) if source == "ratings"
                        else reviews["external_label"])
    usable = reviews.dropna(subset=["label"])
    st.write(f"تعليقات موسومة صالحة للتدريب: **{len(usable)}** من {len(reviews)}")
    if not usable.empty:
        st.write("توزيع الوسوم:", usable["label"].map(config.SENTIMENT_AR).value_counts().to_dict())
    synthetic = bool(datasets[datasets["id"].isin(chosen)]["is_synthetic"].astype(bool).any())
    if synthetic:
        st.warning("بيانات التدريب تشمل بيانات اصطناعية مولدة من قوالب محدودة؛ الأداء عليها سيبدو مرتفعًا "
                   "بشكل مضلل ولا يعبر عن أداء حقيقي على تعليقات العملاء.")

    if st.button("تدريب وتقييم", type="primary", disabled=usable.empty):
        try:
            with st.spinner("جارٍ التدريب..."):
                model, meta = ml_model.train_and_evaluate(usable["clean_text"], usable["label"],
                                                          data_is_synthetic=synthetic, label_source=source)
            ml_model.save_model(model, meta)
            st.success(f"تم حفظ النموذج بالإصدار {meta['model_version']}. يمكنك الآن اختياره في صفحة «تحليل المشاعر».")
        except ValueError as exc:
            st.error(str(exc))

    meta = ml_model.load_metadata()
    if meta:
        st.subheader("النموذج المحفوظ حاليًا")
        m = meta["metrics"]
        c1, c2, c3 = st.columns(3)
        c1.metric("الدقة (Accuracy)", f"{m['accuracy']:.1%}")
        c2.metric("Macro-F1", f"{m['macro_f1']:.3f}")
        c3.metric("حجم الاختبار", m["n_test"])
        st.caption(f"الإصدار: {meta['model_version']} — تاريخ التدريب: {meta['trained_at']} — "
                   f"عدد الأمثلة: {meta['n_samples']} — مصدر الوسوم: {meta['label_source']}"
                   + (" — ⚠ بيانات اصطناعية" if meta.get("data_is_synthetic") else ""))
        rows = [{"الصنف": config.SENTIMENT_AR.get(k, k), "Precision": round(v["precision"], 3),
                 "Recall": round(v["recall"], 3), "F1": round(v["f1-score"], 3), "العدد": int(v["support"])}
                for k, v in m["report"].items() if k in config.SENTIMENTS]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.plotly_chart(confusion_figure(m["confusion_matrix"], m["classes"], "مصفوفة الالتباس (بيانات الاختبار)"),
                        use_container_width=True)

with tab_eval:
    st.markdown("قارن نتائج التحليل المخزنة بالوسوم الأصلية الموجودة في البيانات (إن وُجدت).")
    filters = sidebar_filters(conn, "eval", show_dates=False)
    reviews = analytics.analyzed_reviews(conn, filters)
    agreement = analytics.agreement_with_labels(reviews)
    if agreement is None:
        st.info("لا توجد وسوم أصلية في التعليقات المحللة المختارة.")
    else:
        st.metric("نسبة الاتفاق مع الوسوم", f"{agreement['accuracy']:.1%}", help=f"على {agreement['n']} تعليقًا")
        if reviews["is_synthetic"].astype(bool).any():
            st.warning("الوسوم في البيانات التجريبية مولدة آليًا مع النص نفسه، فهذه النسبة لا تقيس أداءً حقيقيًا.")
        st.plotly_chart(confusion_figure(agreement["confusion_matrix"], agreement["labels"], "الوسم الأصلي مقابل نتيجة التحليل"),
                        use_container_width=True)

with tab_hf:
    st.markdown(
        f"""
**النموذج المقترح:** `{config.DEFAULT_TRANSFORMER_MODEL}`

- نموذج CAMeLBERT مضبوط لتصنيف المشاعر في **اللهجات العربية** (إيجابي/سلبي/محايد) حسب ما هو منشور عنه.
- **قبل الاعتماد عليه:** افتح بطاقة النموذج على Hugging Face وتحقق من: بيانات التدريب ومجالها (تغريدات عامة وليست مراجعات مطاعم)، أسماء الوسوم، الرخصة، والقيود المذكورة.
- المنصة تقرأ أسماء الوسوم من إعدادات النموذج نفسه، وترفض النموذج إن لم تكن وسومه واضحة.
- لتغيير النموذج عرّف متغير البيئة `SRA_TRANSFORMER_MODEL`.
- النموذج يحدد الشعور العام فقط؛ الجوانب والوجبات تبقى من محلل القاموس.
"""
    )
    if transformers_installed():
        st.success("مكتبة transformers مثبتة. اختر المحرك من صفحة «تحليل المشاعر» (يُنزل النموذج أول مرة ويحتاج إنترنت).")
    else:
        st.info("مكتبة transformers غير مثبتة (اختيارية). للتثبيت: pip install -r requirements-optional.txt")
