import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = sys.argv[1]
INK, MUTED, EDGE, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
BLUE, ORANGE, TINT = "#2a78d6", "#eb6834", "#eef4fc"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})


def box(ax, x, y, w, h, title, body=None, accent=False, fill="white"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.12",
                                linewidth=2 if accent else 1.1, edgecolor=BLUE if accent else EDGE,
                                facecolor=TINT if accent else fill))
    if body:
        ax.text(x + w / 2, y + h - 0.28, title, ha="center", va="top", fontsize=10.5, fontweight="bold", color=INK)
        ax.text(x + w / 2, y + h - 0.62, body, ha="center", va="top", fontsize=8.6, color=MUTED, linespacing=1.35)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=10, fontweight="bold", color=INK)


def arrow(ax, x1, y1, x2, y2, style="-|>", rad=0.0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style, mutation_scale=12, color=EDGE,
                                 linewidth=1.1, connectionstyle=f"arc3,rad={rad}"))


def canvas(w, h):
    fig, ax = plt.subplots(figsize=(w, h), dpi=200)
    ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off")
    return fig, ax


# 1. Architecture ------------------------------------------------------------
fig, ax = canvas(10, 7.2)
ax.text(5, 6.95, "Three layers: interface, analysis core, and local storage", ha="center", fontsize=12, fontweight="bold")
ax.add_patch(FancyBboxPatch((0.2, 5.0), 9.6, 1.55, boxstyle="round,pad=0,rounding_size=0.12", fc="#f6f6f4", ec=GRID))
ax.text(0.4, 6.38, "Presentation layer (Streamlit, Arabic RTL)", fontsize=9.5, color=MUTED, fontweight="bold")
pages = ["Home", "Import", "Sentiment", "Dishes", "Compare", "Reports", "Model", "Dictionary"]
for i, p in enumerate(pages):
    ax.add_patch(FancyBboxPatch((0.4 + i * 1.18, 5.2), 1.06, 0.85, boxstyle="round,pad=0,rounding_size=0.12", lw=1.1, ec=EDGE, fc="white"))
    ax.text(0.4 + i * 1.18 + 0.53, 5.625, p, ha="center", va="center", fontsize=8.6, fontweight="bold")
ax.add_patch(FancyBboxPatch((0.2, 1.9), 9.6, 2.8, boxstyle="round,pad=0,rounding_size=0.12", fc="#f6f6f4", ec=GRID))
ax.text(0.4, 4.52, "Application core (Python package sra)", fontsize=9.5, color=MUTED, fontweight="bold")
core = [("Importer", "CSV / Excel / JSON\ncolumn mapping\nvalidation"), ("Text processing", "cleaning\nnormalisation\nclause split"),
        ("ABSA analyser", "lexicon + rules\n7 aspects\nconfidence"), ("Dish extractor", "57 dishes\n154 synonyms")]
for i, (t, b) in enumerate(core):
    box(ax, 0.4 + i * 2.35, 2.95, 2.15, 1.35, t, b)
core2 = [("ML models", "scikit-learn\noptional Transformers"), ("Analytics", "distributions, Wilson\nranking, trends"),
         ("Reports", "Excel (RTL)\nArabic PDF"), ("Connectors", "official APIs only\nX API v2")]
for i, (t, b) in enumerate(core2):
    box(ax, 0.4 + i * 2.35, 2.05, 2.15, 0.8, t, None)
ax.add_patch(FancyBboxPatch((0.2, 0.05), 9.6, 1.7, boxstyle="round,pad=0,rounding_size=0.12", fc="#f6f6f4", ec=GRID))
ax.text(0.4, 1.58, "Data layer", fontsize=9.5, color=MUTED, fontweight="bold")
box(ax, 0.4, 0.2, 5.0, 1.2, "SQLite database", "6 tables: datasets, reviews, analyses,\naspects, dishes, review_dishes", accent=True)
box(ax, 5.6, 0.2, 4.0, 1.2, "Files", "dish dictionary (CSV), trained model,\nArabic font for PDF")
arrow(ax, 5, 5.0, 5, 4.7); arrow(ax, 5, 1.9, 5, 1.75)
fig.savefig(f"{OUT}/fig_architecture.png", bbox_inches="tight"); plt.close(fig)

# 2. Analysis pipeline -------------------------------------------------------
fig, ax = canvas(10, 5.4)
ax.text(5, 5.15, "Each review is analysed clause by clause, then aggregated", ha="center", fontsize=12, fontweight="bold")
steps = [("1  Clean", "remove URLs,\nmask personal data"), ("2  Normalise", "alef, ta marbuta,\nelongation"),
         ("3  Split clauses", "punctuation and\nbas / lakin"), ("4  Find anchors", "aspect words\nand dish names")]
for i, (t, b) in enumerate(steps):
    box(ax, 0.2 + i * 2.45, 3.25, 2.2, 1.35, t, b)
    if i < 3:
        arrow(ax, 0.2 + i * 2.45 + 2.2, 3.92, 0.2 + (i + 1) * 2.45, 3.92)
steps2 = [("5  Score opinions", "lexicon, phrases,\nnegation, intensifiers"), ("6  Assign", "implicit aspect or\nnearest anchor"),
          ("7  Aspect results", "label per aspect\n+ evidence clause"), ("8  Overall result", "label, confidence,\nmixed / uncertain")]
for i, (t, b) in enumerate(steps2):
    x = 7.55 - i * 2.45
    box(ax, x, 0.85, 2.2, 1.35, t, b, accent=(i == 3))
    if i < 3:
        arrow(ax, x, 1.52, x - 0.25, 1.52)
arrow(ax, 8.65, 3.25, 8.65, 2.2)
ax.text(5, 0.35, "Clauses after a contrast word (bas, lakin) are weighted x1.3 in the overall score.", ha="center", fontsize=9, color=MUTED)
fig.savefig(f"{OUT}/fig_pipeline.png", bbox_inches="tight"); plt.close(fig)

# 3. ERD ---------------------------------------------------------------------
fig, ax = canvas(10, 6.4)
ax.set_ylim(-0.3, 6.4)
ax.text(5, 6.15, "Six tables linked by foreign keys with cascading deletes", ha="center", fontsize=12, fontweight="bold")
def table(x, y, name, cols, w=2.9):
    h = 0.52 + 0.27 * len(cols)
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.08", fc="white", ec=EDGE, lw=1.1))
    ax.add_patch(FancyBboxPatch((x, y + h - 0.42), w, 0.42, boxstyle="round,pad=0,rounding_size=0.08", fc=TINT, ec=EDGE, lw=1.1))
    ax.text(x + 0.12, y + h - 0.21, name, va="center", fontsize=10, fontweight="bold")
    for i, c in enumerate(cols):
        ax.text(x + 0.12, y + h - 0.6 - i * 0.27, c, va="center", fontsize=8.3, color=INK if "PK" in c or "FK" in c else MUTED)
    return h
table(0.2, 3.9, "datasets", ["id  PK", "name  UNIQUE", "source_type", "is_synthetic", "created_at"])
table(3.55, 2.55, "reviews", ["id  PK", "dataset_id  FK", "text, clean_text", "text_hash, dup_index", "restaurant_name, city",
                              "review_date", "original_rating", "external_label"])
table(6.9, 2.55, "analyses", ["id  PK", "review_id  FK", "model_name, model_version", "sentiment, confidence",
                              "is_mixed, is_uncertain", "positive/negative_score", "analyzed_at"])
table(6.9, 0.15, "aspects", ["id  PK", "analysis_id  FK", "aspect, sentiment, score", "evidence, has_opinion", "dish_id  FK"])
table(3.55, 0.15, "review_dishes", ["analysis_id  FK  (PK)", "dish_id  FK  (PK)", "matched_text", "sentiment, evidence"])
table(0.2, 0.15, "dishes", ["id  PK", "canonical_name  UNIQUE", "category", "synonyms", "is_active"])
arrow(ax, 3.1, 4.6, 3.55, 4.6, style="-"); ax.text(3.2, 4.68, "1:N", fontsize=8, color=MUTED)
arrow(ax, 6.45, 4.6, 6.9, 4.6, style="-"); ax.text(6.55, 4.68, "1:N", fontsize=8, color=MUTED)
arrow(ax, 8.35, 2.55, 8.35, 2.02, style="-"); ax.text(8.45, 2.22, "1:N", fontsize=8, color=MUTED)
arrow(ax, 7.0, 2.55, 6.2, 1.75, style="-"); ax.text(6.35, 2.2, "1:N", fontsize=8, color=MUTED)
ax.plot([1.65, 1.65, 8.35, 8.35], [0.15, -0.12, -0.12, 0.15], color=EDGE, lw=1.1)
ax.text(5.0, -0.06, "aspects.dish_id  references  dishes.id  (N:1)", ha="center", fontsize=8, color=MUTED)
arrow(ax, 3.1, 0.75, 3.55, 0.75, style="-"); ax.text(3.2, 0.83, "1:N", fontsize=8, color=MUTED)
fig.savefig(f"{OUT}/fig_erd.png", bbox_inches="tight"); plt.close(fig)

# 4. Development and evaluation design --------------------------------------
fig, ax = canvas(10.8, 6.0)
ax.text(5.2, 5.75, "The test split is used once, after the lexicon was frozen", ha="center", fontsize=12, fontweight="bold")
box(ax, 3.4, 4.7, 3.6, 0.65, "AQTE dataset: 14,783 reviews")
box(ax, 0.3, 3.55, 3.6, 0.65, "Test split (~1,900)")
box(ax, 6.1, 3.55, 3.6, 0.65, "Training split (~12,900)")
arrow(ax, 5.2, 4.7, 2.1, 4.2); arrow(ax, 5.2, 4.7, 7.9, 4.2)
loop = ["Measure on 2,000-review dev sample", "Analyse errors, review terms", "Edit lexicon + regression test"]
ys = [2.6, 1.85, 1.1]
for i, t in enumerate(loop):
    ax.add_patch(FancyBboxPatch((6.1, ys[i]), 3.6, 0.5, boxstyle="round,pad=0,rounding_size=0.12", lw=1.1, ec=EDGE, fc="white"))
    ax.text(7.9, ys[i] + 0.25, t, ha="center", va="center", fontsize=9, fontweight="bold")
arrow(ax, 7.9, 3.55, 7.9, 3.1); arrow(ax, 7.9, 2.6, 7.9, 2.35); arrow(ax, 7.9, 1.85, 7.9, 1.6)
arrow(ax, 9.7, 1.35, 9.7, 2.85, rad=0.55)
ax.text(10.25, 2.1, "4\nversions", fontsize=8.5, color=MUTED, ha="center", va="center")
box(ax, 6.1, 0.3, 3.6, 0.5, "Frozen lexicon v1.3")
arrow(ax, 7.9, 1.1, 7.9, 0.8)
box(ax, 4.0, 2.0, 2.0, 0.5, "Train scikit-learn")
arrow(ax, 6.1, 3.7, 5.0, 2.5)
box(ax, 0.3, 0.2, 3.6, 0.85, "Final evaluation", "once, on the test split", accent=True)
arrow(ax, 2.1, 3.55, 2.1, 1.05)
ax.text(2.25, 2.3, "untouched until\nfinal evaluation", fontsize=9, color=MUTED)
arrow(ax, 6.1, 0.55, 3.9, 0.55)
arrow(ax, 4.6, 2.0, 3.9, 0.9)
fig.savefig(f"{OUT}/fig_dev_design.png", bbox_inches="tight"); plt.close(fig)

# 5. Development progression chart -----------------------------------------
fig, ax = plt.subplots(figsize=(7.5, 3.6), dpi=200)
versions = ["v1.0", "v1.1", "v1.2", "v1.3"]
f1 = [0.775, 0.800, 0.803, 0.814]; rec = [0.705, 0.741, 0.748, 0.779]
ax.plot(versions, f1, color=BLUE, lw=2, marker="o", ms=7, label="Aspect F1")
ax.plot(versions, rec, color=ORANGE, lw=2, marker="o", ms=7, label="Aspect recall")
for x, v in zip(versions, f1): ax.annotate(f"{v:.3f}", (x, v), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8.5, color=INK)
for x, v in zip(versions, rec): ax.annotate(f"{v:.3f}", (x, v), textcoords="offset points", xytext=(0, -15), ha="center", fontsize=8.5, color=INK)
ax.set_ylim(0.65, 0.85); ax.set_ylabel("Score"); ax.grid(axis="y", color=GRID); ax.spines[["top", "right"]].set_visible(False)
ax.set_title("Aspect detection improved with each lexicon version (dev sample, n = 2,000)", fontsize=10.5, loc="left", fontweight="bold")
ax.legend(frameon=False, loc="lower right")
fig.tight_layout(); fig.savefig(f"{OUT}/fig_dev_progress.png"); plt.close(fig)

# 6. Per-aspect dev results v1.3 --------------------------------------------
fig, ax = plt.subplots(figsize=(7.5, 3.9), dpi=200)
aspects = ["Food quality", "Price", "Service", "Cleanliness", "Ambiance", "Quantity", "Delivery"]
f1a = [0.926, 0.866, 0.795, 0.735, 0.611, 0.459, 0.354]
n = [1658, 546, 928, 309, 314, 111, 77]
y = list(range(len(aspects)))[::-1]
ax.barh(y, f1a, color=BLUE, height=0.6)
for yi, v, k in zip(y, f1a, n): ax.text(v + 0.01, yi, f"{v:.2f}  (n = {k})", va="center", fontsize=8.5)
ax.set_yticks(y, aspects); ax.set_xlim(0, 1.15); ax.set_xlabel("F1")
ax.grid(axis="x", color=GRID); ax.spines[["top", "right"]].set_visible(False)
ax.set_title("Aspects with many examples are detected best (v1.3, dev sample)", fontsize=10.5, loc="left", fontweight="bold")
fig.tight_layout(); fig.savefig(f"{OUT}/fig_dev_aspects.png"); plt.close(fig)
print("ok")
