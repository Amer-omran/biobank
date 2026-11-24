"""Reproduce the study's sample and models (Gulf Colleges graduation project) from the pinned AraFacts 2 file."""
import re, sys, unicodedata, json
import numpy as np, pandas as pd
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import f1_score, recall_score, accuracy_score, confusion_matrix

RAW = sys.argv[1]
URL = re.compile(r"(?:https?://|www\.)\S+", re.I); MENTION = re.compile(r"@\w+")
DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
ALIF = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي"})
def norm(t):
    t = unicodedata.normalize("NFKC", str(t))
    t = URL.sub(" ", t); t = MENTION.sub(" ", t)
    t = "".join(c for c in t if unicodedata.category(c) not in ("Mn", "Cf"))
    t = t.translate(ALIF).replace("ـ", "").translate(DIG)
    return re.sub(r"\s+", " ", t).strip().lower()

d = pd.read_csv(RAW, dtype=str, keep_default_na=False)
print("all", len(d))
h = d[d.normalized_category.str.strip().str.lower() == "health"]; print("health", len(h))
lab = h.normalized_label.str.strip().str.lower()
b = h[lab.isin(["false", "true"])].copy(); print("binary", len(b))
b = b[b.claim_type.astype(str).str.strip().isin(["0", "0.0"])].copy(); print("text-only", len(b))
b["y"] = (b.normalized_label.str.strip().str.lower() == "false").astype(int)  # positive = false
b["t"] = b.claim.map(norm)
b = b[b.t.str.contains("[؀-ۿ]")]
print("final", len(b), "false", b.y.sum(), "true", (1 - b.y).sum())
b["year"] = b.date.str[:4]
b.to_pickle("sample.pkl")
