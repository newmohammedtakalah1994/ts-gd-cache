// TS-GD: Time-Series-aware Greedy-Dual cache replacement (the proposed model), version 2.
// Idea: approximate the size-aware Belady policy (evict the object whose next request is farthest away, weighted
// by size) with a learned predictor. At eviction time we sample K cached objects, predict for each
//     d_hat = E[ log(time until its next request) | the object's state *now* ]
// with an online linear (least-squares) regression, and evict the object with the largest exp(d_hat) * S.
// Labels: the observed time to the next request, censored at CAP (24 h). The model is refit every RETRAIN
// seconds using only samples whose label is already known (no look-ahead).
// Feature groups (MODE):
//   I  instantaneous : recency, total frequency, request rate, decayed 15-min and 1-h counters
//   T  time series   : per-object 24-bin hour-of-day profile (exponentially decayed): expected requests in the next
//                      1 h and 6 h according to the profile, and the hours until the profile's daily peak
//   C  clustering    : streaming mini-batch k-Means on the PAA (8 x 3-hour segments) of normalised profiles;
//                      cluster shape -> share of the next 6 h and hours until the cluster's peak
//   S  shrinkage     : the T features are computed from the object's profile shrunk toward its cluster's typical
//                      daily shape: share_b = (P_b + M0 * cluster_b) / (mass + M0) — sparse objects borrow the pattern
//   R  regimes       : two separate regressions — recently active objects (last request < 1 h ago) and idle ones
//   G  GD admission  : as Greedy-Dual (libCacheSim's GDSF_can_insert): a missed object is not admitted if any of the
//                      sampled objects that would have to be evicted for it is predicted to be more valuable than it
//   A  admission     : a first-time object predicted not to return within THETA * CAP is not admitted
// usage: tsgdsim trace.bin cache_bytes test_start MODE(I|IT|ITC|ITCA|...) [K=64] [k=8] [THETA=0.9]
// env: TSGD_CAP_HOURS (prediction horizon, default 24), TSGD_SEED (random seed, default 42), TSGD_DUMP (per-request hit dump)
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cmath>
#include <vector>
#include <queue>
#include <string>
#include <random>
#include <chrono>
#include <algorithm>
struct Rec { uint32_t t, id, size; float cost; };
static const int D_MAX = 12;
struct Sample { float x[D_MAX]; uint32_t id, t; float label; };   // label < 0: unknown yet
struct Due { uint32_t due, idx; bool operator<(const Due& o) const { return due > o.due; } };

int main(int argc, char** argv) {
  if (argc < 5) { fprintf(stderr, "usage: tsgdsim trace cache_bytes test_start MODE [K] [k] [theta]\n"); return 1; }
  const char* path = argv[1]; double cap = atof(argv[2]); uint32_t test_start = atol(argv[3]); std::string mode = argv[4];
  int K = argc > 5 ? atoi(argv[5]) : 64, NC = argc > 6 ? atoi(argv[6]) : 8; double THETA = argc > 7 ? atof(argv[7]) : 0.9;
  bool useS = mode.find('S') != std::string::npos; bool useR = mode.find('R') != std::string::npos, useG = mode.find('G') != std::string::npos; bool useT = mode.find('T') != std::string::npos, useC = mode.find('C') != std::string::npos, useA = mode.find('A') != std::string::npos;
  const double TAU_P = 2 * 86400.0, RETRAIN = 6 * 3600.0, TRAIN_WINDOW = 3 * 86400.0;
  const double CAP = getenv("TSGD_CAP_HOURS") ? atof(getenv("TSGD_CAP_HOURS")) * 3600.0 : 86400.0;   // prediction horizon (default 24 h; env override for the sensitivity study)
  FILE* f = fopen(path, "rb"); if (!f) { perror("trace"); return 1; }
  fseek(f, 0, SEEK_END); size_t n = ftell(f) / sizeof(Rec); fseek(f, 0, SEEK_SET);
  std::vector<Rec> tr(n); if (fread(tr.data(), sizeof(Rec), n, f) != n) return 1; fclose(f);
  uint32_t nobj = 0; for (auto& r : tr) nobj = std::max(nobj, r.id + 1);
  std::vector<uint32_t> prevT(nobj, 0), lastT(nobj, 0), firstT(nobj, 0), freq(nobj, 0), cupd(nobj, 0), ptime(nobj, 0), osz(nobj, 0);
  std::vector<float> c15(nobj, 0), c1h(nobj, 0), prof((size_t)nobj * 24, 0.f);
  std::vector<int32_t> pos(nobj, -1); std::vector<uint32_t> cached;
  std::vector<std::vector<uint32_t>> waiting(nobj);           // pending sample indices per object
  const unsigned long long SEED = getenv("TSGD_SEED") ? strtoull(getenv("TSGD_SEED"), nullptr, 10) : 42ULL;   // random sampling seed (default 42)
  std::mt19937_64 rng(SEED);
  int D = 5 + (useT ? 3 : 0) + (useC ? 2 : 0);
  std::vector<double> wR[2] = {std::vector<double>(D + 1, 0.0), std::vector<double>(D + 1, 0.0)}, muR[2] = {std::vector<double>(D, 0.0), std::vector<double>(D, 0.0)}, sdR[2] = {std::vector<double>(D, 1.0), std::vector<double>(D, 1.0)};
  std::vector<double>& w = wR[0]; bool trained = false; double nextTrain = RETRAIN; (void)w;
  const float REG_T = (float)log1p(60.0);   // x[0] = log1p(recency minutes) >= this <=> idle for >= 1 h double nextTrain = RETRAIN;
  std::vector<std::vector<float>> cent(NC, std::vector<float>(8, 1.f / 8)); std::vector<double> ccount(NC, 0); bool cinit = false;
  auto hb = [](double t) { return (int)fmod(t / 3600.0, 24.0); };
  auto touch = [&](uint32_t id, uint32_t t) {
    double dt = (double)t - cupd[id]; c15[id] = c15[id] * exp(-dt / 900.0) + 1; c1h[id] = c1h[id] * exp(-dt / 3600.0) + 1; cupd[id] = t;
    double dp = (double)t - ptime[id]; float* P = &prof[(size_t)id * 24];
    if (dp > 0) { float df = (float)exp(-dp / TAU_P); for (int b = 0; b < 24; ++b) P[b] *= df; } P[hb(t)] += 1; ptime[id] = t;
  };
  auto paa = [&](uint32_t id, float out[8], double& mass) {
    float* P = &prof[(size_t)id * 24]; mass = 0; for (int s = 0; s < 8; ++s) { out[s] = P[3 * s] + P[3 * s + 1] + P[3 * s + 2]; mass += out[s]; }
    if (mass > 0) for (int s = 0; s < 8; ++s) out[s] /= mass;
  };
  auto feat = [&](uint32_t id, uint32_t now, float* x) {
    double rec = now > lastT[id] ? (double)now - lastT[id] : (freq[id] > 1 ? (double)now - prevT[id] : 30 * 86400.0);
    double age = std::max(3600.0, (double)now - firstT[id]), dt = (double)now - cupd[id];
    int j = 0;
    x[j++] = log1p(rec / 60.0); x[j++] = log1p(freq[id]); x[j++] = log1p(freq[id] / age * 3600.0);
    x[j++] = log1p(c15[id] * exp(-dt / 900.0)); x[j++] = log1p(c1h[id] * exp(-dt / 3600.0));
    if (useT) {
      float* P = &prof[(size_t)id * 24]; double decay = exp(-((double)now - ptime[id]) / TAU_P), days = TAU_P / 86400.0;
      double Q[24], mass = 0; for (int b = 0; b < 24; ++b) { Q[b] = P[b] * decay; mass += Q[b]; }
      if (useS && cinit) {                                   // shrink toward the cluster's daily shape (hourly share = segment share / 3)
        const double M0 = 5.0; float v[8]; double m; paa(id, v, m); const float* c8; float avg[8] = {0};
        if (m >= 2) { int best = 0; double bd = 1e30; for (int c = 0; c < NC; ++c) { double d = 0; for (int q = 0; q < 8; ++q) d += (v[q] - cent[c][q]) * (v[q] - cent[c][q]); if (d < bd) { bd = d; best = c; } } c8 = cent[best].data(); }
        else { for (int c = 0; c < NC; ++c) for (int q = 0; q < 8; ++q) avg[q] += cent[c][q] / NC; c8 = avg; }
        for (int b = 0; b < 24; ++b) Q[b] = mass * (Q[b] + M0 * c8[b / 3] / 3.0) / (mass + M0);   // same total volume, smoothed shape
      }
      double n1 = Q[hb(now)] / days, n6 = 0; for (int k = 0; k < 6; ++k) n6 += Q[hb(now + 3600.0 * k)];
      n6 /= days; int pk = 0; for (int b = 1; b < 24; ++b) if (Q[b] > Q[pk]) pk = b;
      x[j++] = log1p(n1); x[j++] = log1p(n6); x[j++] = ((pk - hb(now) + 24) % 24) / 24.0;
    }
    if (useC) {
      float v[8]; double m; paa(id, v, m); const float* c8; float avg[8] = {0};
      if (m >= 2 && cinit) { int best = 0; double bd = 1e30;
        for (int c = 0; c < NC; ++c) { double d = 0; for (int s = 0; s < 8; ++s) d += (v[s] - cent[c][s]) * (v[s] - cent[c][s]); if (d < bd) { bd = d; best = c; } }
        c8 = cent[best].data(); }
      else { for (int c = 0; c < NC; ++c) for (int s = 0; s < 8; ++s) avg[s] += cent[c][s] / NC; c8 = avg; }
      int seg = hb(now) / 3; double sh = c8[seg] + c8[(seg + 1) % 8];          // next ~6 h
      int pk = 0; for (int s = 1; s < 8; ++s) if (c8[s] > c8[pk]) pk = s;
      x[j++] = log(sh * 4 + 0.01); x[j++] = ((pk - seg + 8) % 8) / 8.0;
    }
  };
  auto pred = [&](const float* x, uint32_t id, uint32_t now) {   // predicted log seconds to next request
    if (!trained) { double age = std::max(3600.0, (double)now - firstT[id]); return log(std::min(CAP, age / freq[id])); }
    int g = (useR && x[0] >= REG_T) ? 1 : 0; const std::vector<double>& ww = wR[g]; const std::vector<double>& mm = muR[g]; const std::vector<double>& ss = sdR[g];
    double z = ww[D]; for (int j = 0; j < D; ++j) z += ww[j] * (x[j] - mm[j]) / ss[j]; return z;
  };
  std::vector<Sample> samples; std::priority_queue<Due> pending;
  auto train = [&](uint32_t now) {
    std::vector<int> idx; for (size_t i = 0; i < samples.size(); ++i) if (samples[i].label >= 0 && samples[i].t + TRAIN_WINDOW + CAP >= now) idx.push_back(i);
    if (idx.size() < 5000) return;
    if (idx.size() > 400000) { std::shuffle(idx.begin(), idx.end(), rng); idx.resize(400000); }
    auto fit = [&](const std::vector<int>& I, std::vector<double>& w, std::vector<double>& mu, std::vector<double>& sd) {
      if (I.size() < 2000) return;
      for (int j = 0; j < D; ++j) { double s = 0, s2 = 0; for (int i : I) { s += samples[i].x[j]; s2 += (double)samples[i].x[j] * samples[i].x[j]; }
        mu[j] = s / I.size(); sd[j] = sqrt(std::max(1e-9, s2 / I.size() - mu[j] * mu[j])); }
      int m = D + 1; std::vector<double> A(m * m, 0), b(m, 0); double z[D_MAX + 1];
      for (int i : I) { for (int j = 0; j < D; ++j) z[j] = (samples[i].x[j] - mu[j]) / sd[j]; z[D] = 1;
        for (int j = 0; j < m; ++j) { b[j] += z[j] * samples[i].label; for (int k = 0; k < m; ++k) A[j * m + k] += z[j] * z[k]; } }
      for (int j = 0; j < D; ++j) A[j * m + j] += 1e-3 * I.size();
      for (int c = 0; c < m; ++c) { int pv = c; for (int r = c + 1; r < m; ++r) if (fabs(A[r * m + c]) > fabs(A[pv * m + c])) pv = r;
        for (int k = 0; k < m; ++k) std::swap(A[c * m + k], A[pv * m + k]); std::swap(b[c], b[pv]);
        for (int r = c + 1; r < m; ++r) { double fct = A[r * m + c] / A[c * m + c]; for (int k = c; k < m; ++k) A[r * m + k] -= fct * A[c * m + k]; b[r] -= fct * b[c]; } }
      for (int c = m - 1; c >= 0; --c) { double s = b[c]; for (int k = c + 1; k < m; ++k) s -= A[c * m + k] * w[k]; w[c] = s / A[c * m + c]; }
    };
    if (!useR) fit(idx, wR[0], muR[0], sdR[0]);
    else { std::vector<int> I0, I1; for (int i : idx) (samples[i].x[0] >= REG_T ? I1 : I0).push_back(i);
      fit(I0, wR[0], muR[0], sdR[0]); fit(I1, wR[1], muR[1], sdR[1]); }
    trained = true;
    // drop resolved samples that are too old (keep unresolved ones: they are still referenced)
    std::vector<Sample> s2; std::vector<int> remap(samples.size(), -1);
    for (size_t i = 0; i < samples.size(); ++i) if (samples[i].label < 0 || samples[i].t + TRAIN_WINDOW + CAP >= now) { remap[i] = s2.size(); s2.push_back(samples[i]); }
    std::priority_queue<Due> p2; while (!pending.empty()) { Due d = pending.top(); pending.pop(); if (remap[d.idx] >= 0) p2.push({d.due, (uint32_t)remap[d.idx]}); }
    pending.swap(p2);
    for (auto& v : waiting) { size_t k = 0; for (uint32_t s : v) if (remap[s] >= 0 && s2[remap[s]].label < 0) v[k++] = remap[s]; v.resize(k); }
    samples.swap(s2);
  };
  auto add_sample = [&](uint32_t id, uint32_t now) {
    Sample s; feat(id, now, s.x); s.id = id; s.t = now; s.label = -1; samples.push_back(s);
    uint32_t k = samples.size() - 1; waiting[id].push_back(k); pending.push({now + (uint32_t)CAP, k});
  };
  // Streaming mini-batch k-Means on PAA profiles (v3 fixes: start only after objects have >= 1 day of history,
  // k-means++ seeding, re-seeding of empty/starved clusters, learning-rate floor for non-stationary workloads).
  uint32_t traceStart = tr.empty() ? 0 : tr[0].t;
  auto cluster_update = [&](uint32_t now) {
    if (!(useC || useS) || cached.empty() || now < traceStart + 86400) return;
    std::vector<std::vector<float>> batch;
    for (int b = 0; b < 4000; ++b) { uint32_t id = cached[rng() % cached.size()]; if (now - firstT[id] < 86400) continue;
      float v[8]; double m; paa(id, v, m); if (m >= 5) batch.push_back(std::vector<float>(v, v + 8)); }
    if (batch.size() < (size_t)(4 * NC)) return;
    auto d2 = [](const std::vector<float>& a, const std::vector<float>& b) { double d = 0; for (int s = 0; s < 8; ++s) d += (a[s] - b[s]) * (a[s] - b[s]); return d; };
    if (!cinit) {                                            // k-means++ seeding
      cent[0] = batch[rng() % batch.size()];
      for (int c = 1; c < NC; ++c) { std::vector<double> dist(batch.size()); double tot = 0;
        for (size_t i = 0; i < batch.size(); ++i) { double m = 1e30; for (int q = 0; q < c; ++q) m = std::min(m, d2(batch[i], cent[q])); dist[i] = m; tot += m; }
        double u = std::uniform_real_distribution<double>(0, tot)(rng); size_t pick = 0; for (; pick + 1 < batch.size() && u > dist[pick]; ++pick) u -= dist[pick];
        cent[c] = batch[pick]; }
      cinit = true;
    }
    std::vector<int> hits(NC, 0);
    for (auto& v : batch) { int best = 0; double bd = 1e30; for (int c = 0; c < NC; ++c) { double d = d2(v, cent[c]); if (d < bd) { bd = d; best = c; } }
      hits[best]++; ccount[best] += 1; double eta = std::max(1.0 / ccount[best], 0.01);
      for (int s = 0; s < 8; ++s) cent[best][s] = (1 - eta) * cent[best][s] + eta * v[s]; }
    for (int c = 0; c < NC; ++c) if (hits[c] == 0) { cent[c] = batch[rng() % batch.size()]; ccount[c] = 1; }   // re-seed starved clusters
  };
  double used = 0; uint64_t req = 0, hits = 0, evictions = 0, bypass = 0; double bytes = 0, hbytes = 0; uint32_t nextClu = 3600, evCtr = 0, missCtr = 0;
  auto evict_one = [&](uint32_t now, uint32_t keep) {
    if (cached.size() <= 1) return false;
    uint32_t vict = UINT32_MAX; double bv = -1e300; float x[D_MAX];
    for (int s = 0; s < K; ++s) { uint32_t id = cached[rng() % cached.size()]; if (id == keep) continue;
      feat(id, now, x); double v = pred(x, id, now) + log((double)std::max(1u, osz[id])); if (v > bv) { bv = v; vict = id; } }
    if (vict == UINT32_MAX) return false;
    if (++evCtr % 4 == 0) add_sample(cached[rng() % cached.size()], now);      // training sample: a random cached object
    int p = pos[vict]; cached[p] = cached.back(); pos[cached[p]] = p; cached.pop_back(); pos[vict] = -1; used -= osz[vict]; evictions++;
    return true;
  };
  // optional: dump one byte per request (1 = hit) for per-request analysis (env TSGD_DUMP=path)
  const char* dump = getenv("TSGD_DUMP"); std::vector<uint8_t> hitv(dump ? n : 0, 0);
  auto t0 = std::chrono::steady_clock::now();
  for (size_t i = 0; i < n; ++i) {
    const Rec& r = tr[i]; uint32_t id = r.id, now = r.t; bool meas = now >= test_start;
    while (!pending.empty() && pending.top().due <= now) { Due d = pending.top(); pending.pop(); if (samples[d.idx].label < 0) samples[d.idx].label = log(CAP); }
    for (uint32_t s : waiting[id]) if (samples[s].label < 0) samples[s].label = log(std::max(1.0, std::min(CAP, (double)now - samples[s].t)));
    waiting[id].clear();
    if (now >= nextTrain) { train(now); nextTrain = now + RETRAIN; }
    if (now >= nextClu) { cluster_update(now); nextClu = now + 3600; }
    if (freq[id] == 0) firstT[id] = now;
    freq[id]++; touch(id, now); prevT[id] = lastT[id]; lastT[id] = now;
    if (meas) { req++; bytes += r.size; }
    if (pos[id] >= 0) {
      if (meas) { hits++; hbytes += r.size; } if (dump) hitv[i] = 1;
      if (r.size != osz[id]) { used += (double)r.size - osz[id]; osz[id] = r.size; while (used > cap && evict_one(now, id)) {} }
      continue;
    }
    if ((double)r.size > cap || r.size == 0) continue;
    if (++missCtr % 8 == 0) add_sample(id, now);                                 // training sample at admission time
    if (useG && trained && used + r.size > cap && cached.size() > 1) {      // Greedy-Dual style admission test
      float x[D_MAX]; feat(id, now, x); double vnew = pred(x, id, now) + log((double)r.size);
      std::vector<std::pair<double, uint32_t>> cand;
      for (int s = 0; s < K; ++s) { uint32_t c = cached[rng() % cached.size()]; bool dup = false; for (auto& q : cand) if (q.second == c) { dup = true; break; }
        if (dup) continue; feat(c, now, x); cand.push_back({pred(x, c, now) + log((double)std::max(1u, osz[c])), c}); }
      std::sort(cand.begin(), cand.end(), [](const std::pair<double, uint32_t>& a, const std::pair<double, uint32_t>& b) { return a.first > b.first; });
      double need = used + r.size - cap; bool ok = true; size_t nv = 0;
      for (; nv < cand.size() && need > 0; ++nv) { if (cand[nv].first < vnew) { ok = false; break; } need -= osz[cand[nv].second]; }
      if (!ok) { bypass++; continue; }
      for (size_t q = 0; q < nv; ++q) { uint32_t v = cand[q].second; int p = pos[v]; cached[p] = cached.back(); pos[cached[p]] = p; cached.pop_back(); pos[v] = -1; used -= osz[v]; evictions++; }
    }
    if (useA && trained && freq[id] == 1) { float x[D_MAX]; feat(id, now, x); if (pred(x, id, now) > log(THETA * CAP)) { bypass++; continue; } }
    osz[id] = r.size; used += r.size; pos[id] = cached.size(); cached.push_back(id);
    while (used > cap && evict_one(now, id)) {}
  }
  double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  if (dump) { FILE* df = fopen(dump, "wb"); fwrite(hitv.data(), 1, n, df); fclose(df); }
  printf("{\"alg\":\"TSGD\",\"seed\":%llu,\"cap_hours\":%g,\"mode\":\"%s\",\"K\":%d,\"k\":%d,\"theta\":%g,\"cache_bytes\":%.0f,\"requests\":%llu,\"hit_ratio\":%.6f,\"byte_hit_ratio\":%.6f,\"evictions\":%llu,\"bypassed\":%llu,\"sim_seconds\":%.2f,\"us_per_request\":%.4f,\"weights\":[",
         SEED, CAP / 3600.0, mode.c_str(), K, NC, THETA, cap, (unsigned long long)req, req ? (double)hits / req : 0, bytes > 0 ? hbytes / bytes : 0,
         (unsigned long long)evictions, (unsigned long long)bypass, secs, 1e6 * secs / n);
  for (int j = 0; j <= D; ++j) printf("%s%.4f", j ? "," : "", wR[0][j]); printf("],\"weights_idle\":[");
  for (int j = 0; j <= D; ++j) printf("%s%.4f", j ? "," : "", wR[1][j]); printf("]");
  if (useC) { printf(",\"centroids\":["); for (int c = 0; c < NC; ++c) { printf("%s{\"n\":%.0f,\"paa\":[", c ? "," : "", ccount[c]);
      for (int q = 0; q < 8; ++q) printf("%s%.4f", q ? "," : "", cent[c][q]); printf("]}"); } printf("]"); }
  printf("}\n");
  return 0;
}
