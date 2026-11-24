import numpy as np, pandas as pd, itertools
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import f1_score, recall_score, accuracy_score, confusion_matrix
b = pd.read_pickle("sample.pkl").reset_index(drop=True)
X, y = b.t.values, b.y.values
# groups: binary char 3-5 cosine >= 0.85 (paper: each record its own group)
cv_ = CountVectorizer(analyzer="char", ngram_range=(3,5), binary=True).fit_transform(X).astype(float)
nrm = np.sqrt(cv_.multiply(cv_).sum(1)).A1; sim = (cv_ @ cv_.T).toarray() / np.outer(nrm, nrm)
np.fill_diagonal(sim, 0); print("max pair sim", sim.max().round(3), "pairs>=0.85:", int((sim>=0.85).sum()//2))
groups = np.arange(len(b))

def vec(kind, analyzer_char="char"):
    if kind == "word": return [TfidfVectorizer(analyzer="word", ngram_range=(1,2), token_pattern=r"(?u)\b\w+\b", min_df=2, sublinear_tf=True)]
    if kind == "char": return [TfidfVectorizer(analyzer=analyzer_char, ngram_range=(3,5), min_df=2, sublinear_tf=True)]
    return vec("word") + vec("char", analyzer_char)

def run(kind, weighted=True, seed=42, analyzer_char="char"):
    p = np.zeros(len(b))
    for tr, te in StratifiedGroupKFold(5, shuffle=True, random_state=seed).split(X, y, groups):
        vs = vec(kind, analyzer_char)
        Xtr = hstack([v.fit_transform(X[tr]) for v in vs]).tocsr(); Xte = hstack([v.transform(X[te]) for v in vs]).tocsr()
        m = LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced" if weighted else None).fit(Xtr, y[tr])
        p[te] = m.predict_proba(Xte)[:, 1]
    pred = (p > 0.5).astype(int)
    return dict(acc=accuracy_score(y,pred), mf1=f1_score(y,pred,average="macro"), bal=(recall_score(y,pred)+recall_score(y,pred,pos_label=0))/2,
                rf=recall_score(y,pred), rt=recall_score(y,pred,pos_label=0), cm=confusion_matrix(y,pred,labels=[0,1]).ravel().tolist()), p
for ac in ["char", "char_wb"]:
    print("== char analyzer:", ac)
    for k,w in [("word",True),("char",True),("hybrid",True),("hybrid",False)]:
        r,_ = run(k,w,analyzer_char=ac); print(f"{k:7s} w={w!s:5s} acc={r['acc']:.3f} mF1={r['mf1']:.3f} bal={r['bal']:.3f} recF={r['rf']:.3f} recT={r['rt']:.3f} cm(tn,fp,fn,tp)={r['cm']}")
