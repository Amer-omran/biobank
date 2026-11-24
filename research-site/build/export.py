import json, numpy as np, pandas as pd
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score
b = pd.read_pickle("sample.pkl").reset_index(drop=True)
tr = b[b.year < "2021"]; te = b[(b.year >= "2021") & (b.year <= "2023")]
print("train", len(tr), "test", len(te), "test true", int((1-te.y).sum()))
wv = TfidfVectorizer(analyzer="word", ngram_range=(1,2), token_pattern=r"(?u)\b\w+\b", min_df=2, sublinear_tf=True)
cv = TfidfVectorizer(analyzer="char", ngram_range=(3,5), min_df=2, sublinear_tf=True)
Xtr = hstack([wv.fit_transform(tr.t), cv.fit_transform(tr.t)]).tocsr()
m = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced").fit(Xtr, tr.y)
Xte = hstack([wv.transform(te.t), cv.transform(te.t)]).tocsr()
p = m.predict_proba(Xte)[:,1]; pred = (p > 0.5).astype(int)
tn, fp, fn, tp = confusion_matrix(te.y, pred, labels=[0,1]).ravel()
print(f"temporal test (this re-implementation): macroF1={f1_score(te.y,pred,average='macro'):.3f} false {tp}/{tp+fn} true {tn}/{tn+fp}")
nw = len(wv.vocabulary_); coef = m.coef_[0]
model = {
  "name": "hybrid-tfidf-logreg (pre-2021 AraFacts 2 health, text-only)",
  "trained_on": {"records": int(len(tr)), "false": int(tr.y.sum()), "true": int((1-tr.y).sum()), "years": "2016-2020"},
  "threshold": 0.5, "intercept": float(m.intercept_[0]),
  "word": {k: [round(float(wv.idf_[i]),5), round(float(coef[i]),6)] for k,i in wv.vocabulary_.items()},
  "char": {k: [round(float(cv.idf_[i]),5), round(float(coef[nw+i]),6)] for k,i in cv.vocabulary_.items()},
  "temporal_check": {"n": int(len(te)), "macro_f1": round(float(f1_score(te.y,pred,average='macro')),3), "false_found": int(tp), "false_total": int(tp+fn), "true_found": int(tn), "true_total": int(tn+fp)},
}
json.dump(model, open("model.json","w"), ensure_ascii=False, separators=(",",":"))
# reference scores for JS parity test
samples = ["الثوم يعالج فيروس كورونا خلال يوم واحد", "منظمة الصحة العالمية تعلن انتهاء جائحة كورونا", "شرب الماء الساخن مع الليمون يقتل الفيروس", "وزارة الصحة: اللقاح آمن وفعال للأطفال"]
from prep_norm import norm
ref = [{"text": s, "score": float(m.predict_proba(hstack([wv.transform([norm(s)]), cv.transform([norm(s)])]))[0,1])} for s in samples]
json.dump(ref, open("ref_scores.json","w"), ensure_ascii=False, indent=1)
print("vocab word", nw, "char", len(cv.vocabulary_)); print(ref)
