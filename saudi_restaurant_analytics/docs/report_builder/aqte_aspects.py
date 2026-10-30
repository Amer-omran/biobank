import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
rows = {  # aspect_ar: (train, test, total) as read from AQTE aspect_distribution.csv
 "الطعام": (23947, 3056, 27003), "المطعم": (6661, 890, 7551), "الخدمة": (4331, 663, 4994), "السعر": (3424, 532, 3956),
 "طاقم العمل": (3253, 514, 3767), "النظافة": (2069, 304, 2373), "المشروبات": (1731, 185, 1916), "الديكور": (1660, 234, 1894),
 "التعامل": (1386, 197, 1583), "التجربة": (1178, 317, 1495), "الجودة": (1149, 193, 1342), "الأجواء": (1038, 195, 1233),
 "الكمية": (931, 179, 1110), "السرعة": (885, 159, 1044), "الطلب عن بعد": (426, 51, 477), "الإدارة": (391, 62, 453),
 "التنوع": (212, 85, 297), "مواقف السيارات": (179, 33, 212), "التغليف": (181, 18, 199), "المقهى": (124, 36, 160),
 "التنظيم": (119, 25, 144), "الرائحة": (89, 19, 108), "التوفر": (63, 40, 103), "الترفيه": (84, 8, 92), "الأمان": (60, 4, 64),
 "المخبز": (23, 3, 26), "الكافتيريا": (11, 1, 12), "الفندق": (8, 0, 8), "المتجر": (4, 0, 4)}
bad = [k for k, (a, b, c) in rows.items() if a + b != c]
print("row sums ok" if not bad else f"row sum mismatch: {bad}")
print("total", sum(c for _, _, c in rows.values()), "train", sum(a for a, _, _ in rows.values()), "test", sum(b for _, b, _ in rows.values()))
m = {"Food quality": ["الطعام", "المشروبات", "الجودة"], "Service": ["الخدمة", "طاقم العمل", "التعامل", "السرعة", "الإدارة", "التنظيم"],
     "Price": ["السعر"], "Ambiance": ["الديكور", "الأجواء", "مواقف السيارات", "الترفيه"], "Cleanliness": ["النظافة", "الرائحة"],
     "Quantity": ["الكمية"], "Delivery": ["الطلب عن بعد", "التغليف"]}
agg = {k: sum(rows[a][2] for a in v) for k, v in m.items()}
general = sum(c for k, (_, _, c) in rows.items() if not any(k in v for v in m.values()))
print(agg, "unmapped/general", general)
if len(sys.argv) > 1:
    items = sorted(agg.items(), key=lambda kv: kv[1])
    fig, ax = plt.subplots(figsize=(7.5, 3.6), dpi=200)
    ax.barh([k for k, _ in items], [v for _, v in items], color="#2a78d6", height=0.6)
    for i, (k, v) in enumerate(items): ax.text(v + 300, i, f"{v:,}", va="center", fontsize=8.5)
    ax.set_xlim(0, max(agg.values()) * 1.15); ax.set_xlabel("Annotated opinion mentions (train + test)")
    ax.grid(axis="x", color="#e1e0d9"); ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("Customers write about food far more than any other aspect", fontsize=10.5, loc="left", fontweight="bold")
    fig.tight_layout(); fig.savefig(sys.argv[1] + "/fig_aqte_aspects.png")
