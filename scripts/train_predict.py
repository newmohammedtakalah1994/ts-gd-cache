"""Train the classifier of a learning-augmented baseline on the warm-up period and predict a class for every request.
  kmeans : Benadit et al. 2014 — k-Means clusters, each cluster labelled by majority (threshold 0.5)
  knn    : Pernabas et al. 2019 (DMCM-core) — K-nearest-neighbour classifier
Temporal protocol: fit on the first 80% of the warm-up period, choose the hyper-parameter (k / K) by G-mean on the
last 20%, refit on the whole warm-up period, then predict all requests. Test-period metrics are reported.
Features: log1p transform, then min-max scaling fitted on the warm-up period (the papers scale to [0,1]).
Uses scikit-learn when available (exact KNN); otherwise numpy (KNN on 32-level quantised features).
usage: python3 scripts/train_predict.py <trace.bin> kmeans|knn [SWL]"""
import sys, os, json, time, numpy as np
trace, method = sys.argv[1], sys.argv[2]; SWL = int(sys.argv[3]) if len(sys.argv) > 3 else 900
meta = json.load(open(trace + '.json')); W_END = meta['warmup_end']
z = np.load(trace.replace('.bin', f'_feat{SWL}.npz')); X, y, t = z['X'], z['y'], z['t']; del z
rng = np.random.default_rng(42)
try:
    import sklearn; from sklearn.cluster import KMeans; from sklearn.neighbors import KNeighborsClassifier; SK = True
except ImportError:
    SK = False
X[:, 3] *= np.float32(1000.0); np.log1p(X, out=X)          # in place (memory-safe)
warm = t < W_END
mn = np.array([X[warm, j].min() for j in range(5)], np.float32); mx = np.array([X[warm, j].max() for j in range(5)], np.float32)
X -= mn; X /= np.maximum(mx - mn, np.float32(1e-9)); Xn = X
cut = int(W_END * 0.8)
idx_tr = np.flatnonzero(t < cut); idx_va = np.flatnonzero((t >= cut) & warm); idx_all = np.flatnonzero(warm)
def sample(ix, m): return ix if len(ix) <= m else rng.choice(ix, m, replace=False)
def gmean(yt, yp):
    tpr = (yp & yt).sum() / max(1, yt.sum()); tnr = (~yp & ~yt).sum() / max(1, (~yt).sum())
    return float(np.sqrt(tpr * tnr)), float(tpr), float(tnr)

def kmeans_fit(A, k, iters=60):
    if SK: return KMeans(n_clusters=k, n_init=3, random_state=0).fit(A).cluster_centers_.astype(np.float32)
    C = A[rng.integers(len(A))][None]                       # k-means++ init
    for _ in range(1, k):
        d = ((A[:, None, :] - C[None]) ** 2).sum(-1).min(1); C = np.vstack([C, A[rng.choice(len(A), p=d / d.sum())]])
    for _ in range(iters):
        lab = ((A[:, None, :] - C[None]) ** 2).sum(-1).argmin(1)
        newC = np.array([A[lab == j].mean(0) if (lab == j).any() else C[j] for j in range(k)], np.float32)
        if np.allclose(newC, C, atol=1e-5): break
        C = newC
    return C
def assign(A, C, chunk=500_000):
    return np.concatenate([((A[i:i + chunk, None, :] - C[None]) ** 2).sum(-1).argmin(1) for i in range(0, len(A), chunk)])

def knn_predict(R, ry, Q, K):
    if SK:
        return KNeighborsClassifier(n_neighbors=K, algorithm='kd_tree', n_jobs=-1).fit(R, ry).predict(Q).astype(bool)
    q = np.minimum((Q * 32).astype(np.int64), 31); code = (((q[:, 0] * 32 + q[:, 1]) * 32 + q[:, 2]) * 32 + q[:, 3]) * 32 + q[:, 4]
    uc, inv = np.unique(code, return_inverse=True)
    U = np.stack([(uc // 32 ** (4 - j)) % 32 for j in range(5)], 1).astype(np.float32) / 32 + 1 / 64
    out = np.empty(len(uc), bool); rn = (R ** 2).sum(1)
    for i in range(0, len(uc), 4000):
        u = U[i:i + 4000]; d = (u ** 2).sum(1)[:, None] - 2 * u @ R.T + rn[None]
        nb = np.argpartition(d, K - 1, axis=1)[:, :K]; out[i:i + 4000] = ry[nb].mean(1) > 0.5
    return out[inv]

t0 = time.time(); sel = {}
if method == 'kmeans':
    s_tr = sample(idx_tr, 200_000); s_va = sample(idx_va, 100_000)
    for k in [2, 4, 8, 16, 32, 64]:
        C = kmeans_fit(Xn[s_tr], k); lt = assign(Xn[s_tr], C)
        p = np.array([y[s_tr][lt == j].mean() if (lt == j).any() else 0 for j in range(k)])
        sel[k] = gmean(y[s_va], (p > 0.5)[assign(Xn[s_va], C)])[0]; print('k', k, 'val G-mean %.4f' % sel[k], flush=True)
    best = max(sel, key=sel.get); s_all = sample(idx_all, 250_000)
    C = kmeans_fit(Xn[s_all], best); lt = assign(Xn[s_all], C)
    p = np.array([y[s_all][lt == j].mean() if (lt == j).any() else 0 for j in range(best)])
    pred = (p > 0.5)[assign(Xn, C)]
    extra = dict(k=best, cluster_revisit_prob=[round(float(v), 3) for v in p])
else:
    s_tr = sample(idx_tr, 20_000 if not SK else 100_000); s_va = sample(idx_va, 50_000)
    for K in [1, 5, 11, 21]:
        sel[K] = gmean(y[s_va], knn_predict(Xn[s_tr], y[s_tr], Xn[s_va], K))[0]; print('K', K, 'val G-mean %.4f' % sel[K], flush=True)
    best = max(sel, key=sel.get); s_all = sample(idx_all, 20_000 if not SK else 100_000)
    pred = knn_predict(Xn[s_all], y[s_all], Xn, best); extra = dict(K=best, reference_points=len(s_all))
test = t >= meta['test_start']
g, tpr, tnr = gmean(y[test], pred[test])
res = dict(trace=os.path.basename(trace), method=method, sklearn=SK, val_gmean=sel, test_accuracy=float((pred[test] == y[test]).mean()),
           test_TPR=tpr, test_TNR=tnr, test_gmean=g, predicted_positive_rate=float(pred.mean()), seconds=round(time.time() - t0, 1), **extra)
pred.astype(np.float32).tofile(trace.replace('.bin', f'_{method}.w'))
open('results/classifier_metrics.jsonl', 'a').write(json.dumps(res) + '\n'); print(json.dumps(res))
