"""صفحة استيراد البيانات: رفع CSV/Excel، معاينة، اختيار الأعمدة، التحقق، الاستيراد."""

import pandas as pd
import streamlit as st

from sra import config, connectors, database, importer
from ui_pages.common import get_conn, setup_page

setup_page("استيراد البيانات", "ارفع ملف CSV أو Excel، ثم حدد الأعمدة بنفسك؛ لا نفترض أسماء الأعمدة مسبقًا.")
conn = get_conn()

NONE = "— لا يوجد —"
ROLE_LABELS = {
    "text": "عمود التعليقات (إلزامي)",
    "restaurant": "عمود اسم المطعم",
    "date": "عمود التاريخ",
    "rating": "عمود التقييم الرقمي",
    "city": "عمود المدينة",
    "label": "عمود الوسم (إيجابي/سلبي/محايد) إن وُجد",
    "source": "عمود المصدر",
}

tab_file, tab_api, tab_manage = st.tabs(["📄 رفع ملف", "🔌 واجهة رسمية (API)", "🗂️ إدارة المجموعات"])

# ============================================================== رفع ملف
with tab_file:
    uploaded = st.file_uploader("اختر الملف", type=["csv", "tsv", "txt", "xlsx", "xlsm", "xls"])
    if uploaded is not None:
        sheet = 0
        if uploaded.name.lower().endswith((".xlsx", ".xlsm", ".xls")):
            try:
                sheets = importer.excel_sheet_names(uploaded)
                sheet = st.selectbox("ورقة العمل", sheets) if len(sheets) > 1 else sheets[0]
            except Exception as exc:  # noqa: BLE001
                st.error(f"تعذر قراءة أوراق الملف: {exc}")
                st.stop()
        try:
            uploaded.seek(0)
            df = importer.read_table(uploaded, uploaded.name, sheet_name=sheet)
        except ValueError as exc:
            st.error(str(exc))
            st.stop()

        st.success(f"تمت قراءة الملف: {len(df):,} صفًا و{len(df.columns)} عمودًا.")
        st.subheader("معاينة البيانات")
        st.dataframe(df.head(20), use_container_width=True)

        st.subheader("اختيار الأعمدة")
        st.caption("الاقتراحات أدناه تخمين أولي من أسماء الأعمدة ومحتواها؛ راجعها وغيّرها عند الحاجة.")
        suggestion = importer.suggest_mapping(df)
        options = [NONE] + list(df.columns)
        chosen = {}
        cols = st.columns(2)
        for i, (role, label) in enumerate(ROLE_LABELS.items()):
            default = suggestion.get(role)
            index = options.index(default) if default in options else 0
            chosen[role] = cols[i % 2].selectbox(label, options, index=index, key=f"map_{role}")

        if chosen["text"] == NONE:
            st.warning("يجب اختيار عمود التعليقات للمتابعة.")
            st.stop()
        selected = [v for v in chosen.values() if v != NONE]
        if len(selected) != len(set(selected)):
            st.error("اخترت العمود نفسه لأكثر من دور؛ صحح الاختيار.")
            st.stop()

        mapping = importer.ColumnMapping(**{k: (None if v == NONE else v) for k, v in chosen.items()})

        st.subheader("إعدادات الاستيراد")
        c1, c2 = st.columns(2)
        datasets = database.list_datasets(conn)
        dataset_name = c1.text_input("اسم مجموعة البيانات", value=uploaded.name.rsplit(".", 1)[0])
        default_source = c2.text_input("المصدر (إن لم يوجد عمود مصدر)", value="ملف مستورد")
        dedupe = st.checkbox("حذف التعليقات المكررة (النص نفسه للمطعم نفسه في التاريخ نفسه)", value=True)
        is_synthetic = st.checkbox("هذه بيانات اصطناعية/تجريبية وليست آراء حقيقية", value=False)
        if dataset_name in set(datasets["name"]):
            st.info("توجد مجموعة بهذا الاسم؛ ستُضاف التعليقات الجديدة إليها مع تجاهل المكرر.")

        report = importer.prepare_dataframe(df, mapping, dedupe=dedupe, default_source=default_source)
        st.subheader("نتيجة التحقق")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("صفوف الملف", report.total_rows)
        m2.metric("صفوف صالحة", report.valid_rows)
        m3.metric("تعليقات فارغة", report.empty_text_rows)
        m4.metric("مكررة داخل الملف", report.duplicate_rows)
        for err in report.errors:
            st.error(err)
        for warn in report.warnings:
            st.warning(warn)
        if report.valid_rows:
            with st.expander("معاينة البيانات بعد التنظيف"):
                st.dataframe(report.data.drop(columns=["text_hash"]).head(30), use_container_width=True)

        if report.ok and st.button("استيراد إلى قاعدة البيانات", type="primary"):
            if not dataset_name.strip():
                st.error("اكتب اسمًا لمجموعة البيانات.")
                st.stop()
            dataset_id = database.get_or_create_dataset(conn, dataset_name.strip(), "file", is_synthetic,
                                                        f"مستورد من {uploaded.name}")
            result = database.insert_reviews(conn, dataset_id, report.data, keep_duplicates=not dedupe)
            st.success(f"تم استيراد {result['inserted']} تعليقًا. تم تجاهل {result['skipped_duplicates']} "
                       "تعليقًا موجودًا مسبقًا في القاعدة. انتقل الآن إلى صفحة «تحليل المشاعر».")

# ============================================================ واجهة API
with tab_api:
    st.markdown(
        """
**استخدم الواجهات الرسمية والمصرح بها فقط.** لا تدعم المنصة أي كشط لصفحات الويب أو تجاوز لشروط المنصات.

- الطريقة الموصى بها: صدّر التقييمات من الأداة الرسمية للمنصة (مثل لوحة النشاط التجاري) إلى CSV ثم ارفعه من تبويب «رفع ملف».
- موصل X API v2: يحتاج مفتاحًا في متغير البيئة `X_BEARER_TOKEN` وفئة اشتراك تسمح بالبحث. تأكد أن شروط اشتراكك تسمح بتخزين المحتوى لأغراض البحث.
- لا نحفظ أسماء الحسابات أو معرفاتها؛ نحفظ النص والتاريخ والمصدر فقط، مع إخفاء الأرقام والبريد.
"""
    )
    status = connectors.connector_status()
    if not status["X API"]:
        st.info(f"المفتاح غير معرّف. عرّف متغير البيئة {config.X_BEARER_TOKEN_ENV} ثم أعد تشغيل المنصة.")
    else:
        with st.form("x_api"):
            query = st.text_input("عبارة البحث", placeholder="مثال: \"اسم المطعم\" (أكل OR خدمة)")
            restaurant = st.text_input("اسم المطعم المرتبط (اختياري)")
            max_results = st.slider("عدد النتائج (10-100)", 10, 100, 50)
            dataset_name = st.text_input("اسم مجموعة البيانات", value="X API")
            submitted = st.form_submit_button("جلب واستيراد")
        if submitted:
            try:
                fetched = connectors.XRecentSearchConnector(query, max_results, restaurant or None).fetch()
            except connectors.ConnectorError as exc:
                st.error(str(exc))
                st.stop()
            if fetched.empty:
                st.info("لا توجد نتائج.")
            else:
                mapping = importer.ColumnMapping(text="text", date="review_date", restaurant="restaurant_name",
                                                 source="source")
                report = importer.prepare_dataframe(fetched, mapping)
                dataset_id = database.get_or_create_dataset(conn, dataset_name, "api", False,
                                                            "مجلوب عبر X API v2 الرسمي")
                result = database.insert_reviews(conn, dataset_id, report.data)
                st.success(f"تم استيراد {result['inserted']} تعليقًا.")

# ========================================================= إدارة المجموعات
with tab_manage:
    datasets = database.list_datasets(conn)
    if datasets.empty:
        st.info("لا توجد مجموعات بيانات بعد.")
    else:
        view = datasets.rename(columns={"id": "الرقم", "name": "الاسم", "source_type": "النوع",
                                        "is_synthetic": "اصطناعية", "description": "الوصف",
                                        "created_at": "تاريخ الإنشاء", "n_reviews": "عدد التعليقات"})
        view["اصطناعية"] = view["اصطناعية"].map({1: "نعم", 0: "لا"})
        st.dataframe(view, use_container_width=True, hide_index=True)
        labels = dict(zip(datasets["id"], datasets["name"]))
        target = st.selectbox("حذف مجموعة بيانات (مع تعليقاتها وتحليلاتها)", list(labels), format_func=labels.get)
        confirm = st.checkbox("أؤكد الحذف النهائي")
        if st.button("حذف", disabled=not confirm):
            database.delete_dataset(conn, int(target))
            st.success("تم الحذف.")
            st.rerun()

    with st.expander("صيغة الملف المتوقعة (مثال)"):
        st.dataframe(pd.DataFrame({
            "التعليق": ["الكبسة لذيذة بس الخدمة بطيئة", "الأسعار غالية والكمية قليلة"],
            "المطعم": ["مطعم أ", "مطعم ب"], "التاريخ": ["2025-01-15", "2025-02-03"],
            "التقييم": [4, 2], "المدينة": ["الرياض", "جدة"],
        }), hide_index=True)
        st.caption("أسماء الأعمدة حرة؛ ستختارها يدويًا بعد الرفع. ملف تجريبي جاهز: data/sample/demo_reviews_synthetic.csv")
