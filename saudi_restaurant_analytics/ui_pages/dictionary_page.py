"""صفحة قاموس الوجبات: تعديل الأسماء والمرادفات والفئات، وتجربة الاستخراج."""

import pandas as pd
import streamlit as st

from sra import config, database
from sra.dishes import Dish, DishExtractor, load_dishes_csv, save_dishes_csv
from ui_pages.common import get_conn, setup_page

setup_page("قاموس الوجبات", "أضف وجبات أو مرادفات أو اختلافات إملائية؛ النظام لا يستخرج إلا ما في القاموس.")
conn = get_conn()

dishes = load_dishes_csv(config.DISHES_CSV)
table = pd.DataFrame([{"الاسم الموحد": d.canonical_name, "الفئة": d.category, "المرادفات (افصل بـ |)": "|".join(d.synonyms)}
                      for d in dishes])
st.caption(f"عدد الوجبات: {len(dishes)}. الملف: data/dishes_dictionary.csv")
edited = st.data_editor(table, num_rows="dynamic", use_container_width=True, hide_index=True, key="dish_editor")

if st.button("حفظ القاموس", type="primary"):
    new_dishes, seen, problems = [], set(), []
    for row in edited.to_dict("records"):
        name = str(row.get("الاسم الموحد") or "").strip()
        if not name or name == "nan":
            continue
        if name in seen:
            problems.append(f"الاسم مكرر: {name}")
            continue
        seen.add(name)
        synonyms = [s.strip() for s in str(row.get("المرادفات (افصل بـ |)") or "").split("|")
                    if s.strip() and s.strip() != "nan"]
        category = str(row.get("الفئة") or "").strip()
        new_dishes.append(Dish(name, "" if category == "nan" else category, synonyms))
    if problems:
        st.error("، ".join(problems))
    else:
        save_dishes_csv(new_dishes, config.DISHES_CSV)
        database.sync_dishes(conn, new_dishes)
        st.success(f"تم حفظ {len(new_dishes)} وجبة. أعد تشغيل التحليل (دون خيار «غير المحللة فقط») لتطبيق التغييرات.")

st.subheader("تجربة الاستخراج")
text = st.text_input("اكتب تعليقًا", value="طلبت الكبسه والبرقر، والشاورماااا كانت لذيذة")
if text:
    extractor = DishExtractor.from_csv(config.DISHES_CSV)
    found = extractor.extract(text)
    if found:
        for m in found:
            st.write(f"• «{m.matched_text}» ← {m.canonical_name}")
    else:
        st.caption("لم يُعثر على وجبة من القاموس.")
