import re, unicodedata
URL = re.compile(r"(?:https?://|www\.)\S+", re.I); MENTION = re.compile(r"@\w+")
DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
ALIF = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي"})
def norm(t):
    t = unicodedata.normalize("NFKC", str(t))
    t = URL.sub(" ", t); t = MENTION.sub(" ", t)
    t = "".join(c for c in t if unicodedata.category(c) not in ("Mn", "Cf"))
    t = t.translate(ALIF).replace("ـ", "").translate(DIG)
    return re.sub(r"\s+", " ", t).strip().lower()

