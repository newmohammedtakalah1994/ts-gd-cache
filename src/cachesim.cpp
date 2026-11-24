// Trace-driven cache simulator (baseline replacement policies).
// Input: binary trace of records {uint32 t, uint32 id (dense), uint32 size, float cost}, time-ordered.
// All policies share one framework: each cached object has a priority key; evict the smallest key.
// Keys:  LRU   : time of last access
//        LFUDA : L + F                       (Arlitt et al. 2000)
//        GDS   : L + C/S                     (Cao & Irani 1997)
//        GDSF  : L + C*F/S                   (Cherkasova 1998)
//        GDSFA : GDSF with the admission rule of libCacheSim: a missed object is not inserted if any object that would
//                have to be evicted for it has a higher key than the new object (canonical Greedy-Dual behaviour)
//        GDSTAR: L + (C*F/S)^(1/beta)        (Jin & Bestavros 2000)
//        BELADY: -(next access index)        (offline optimum for unit sizes; upper-bound reference)
//        KMGDSF: L + C*F/S + W                (Benadit et al. 2014; W = predicted class 0/1 from a weights file)
//        DMCM  : L + (C*F + K_prev) * (prev_gap/cur_gap) / S, evicting predicted class-0 objects first
//                (Pernabas et al. 2019, Eq. 5 under our interpretation; W = KNN class from a weights file)
//        BELADYSIZE: -(reuse distance * size) (offline size-aware reference, as in libCacheSim)
// F = number of requests since the object entered the cache. L = key of the last evicted object (inflation).
// Cost C: "one" -> 1 (maximises hit ratio), "latency" -> recorded time-to-first-byte / time-taken.
// Statistics are collected only for requests with t >= test_start (earlier requests warm the cache).
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <vector>
#include <queue>
#include <string>
#include <chrono>
struct Rec { uint32_t t, id, size; float cost; };
struct HE { double key; uint32_t id; uint32_t ver; bool operator<(const HE& o) const { return key > o.key; } };
int main(int argc, char** argv) {
  if (argc < 6) { fprintf(stderr, "usage: cachesim trace.bin ALG cache_bytes test_start cost(one|latency) [beta]\n"); return 1; }
  const char* path = argv[1]; std::string alg = argv[2]; double cap = atof(argv[3]);
  uint32_t test_start = (uint32_t)atol(argv[4]); bool lat = std::string(argv[5]) == "latency";
  double beta = argc > 6 ? atof(argv[6]) : 2.0;
  std::vector<float> W;                                    // optional per-request prediction (class 0/1)
  if (argc > 7) { FILE* wf = fopen(argv[7], "rb"); if (!wf) { perror("weights"); return 1; }
    fseek(wf, 0, SEEK_END); size_t m = ftell(wf) / 4; fseek(wf, 0, SEEK_SET); W.resize(m);
    if (fread(W.data(), 4, m, wf) != m) return 1; fclose(wf); }
  FILE* f = fopen(path, "rb"); if (!f) { perror("trace"); return 1; }
  fseek(f, 0, SEEK_END); size_t n = ftell(f) / sizeof(Rec); fseek(f, 0, SEEK_SET);
  std::vector<Rec> tr(n); if (fread(tr.data(), sizeof(Rec), n, f) != n) { fprintf(stderr, "read error\n"); return 1; } fclose(f);
  uint32_t nobj = 0; for (auto& r : tr) if (r.id + 1 > nobj) nobj = r.id + 1;
  std::vector<uint32_t> nxt;
  bool belady = alg == "BELADY" || alg == "BELADYSIZE";
  if (belady) {   // next access index of each request
    nxt.assign(n, UINT32_MAX); std::vector<uint32_t> last(nobj, UINT32_MAX);
    for (size_t i = n; i-- > 0;) { nxt[i] = last[tr[i].id]; last[tr[i].id] = (uint32_t)i; }
  }
  if ((alg == "KMGDSF" || alg == "DMCM" || alg == "PRED") && W.size() != n) { fprintf(stderr, "weights file required (%zu vs %zu)\n", W.size(), n); return 1; }
  bool dmcm = alg == "DMCM";
  std::vector<uint32_t> lastT(nobj, 0), gapPrev(nobj, 0); std::vector<uint8_t> seen(nobj, 0), cls(nobj, 0); std::vector<double> kprev(nobj, 0);
  std::vector<uint8_t> in(nobj, 0); std::vector<uint32_t> osz(nobj, 0), freq(nobj, 0), ver(nobj, 0);
  std::priority_queue<HE> pqs[2]; std::priority_queue<HE>& pq = pqs[0]; double used = 0, L = 0; size_t cached = 0;
  uint64_t req = 0, hits = 0; double bytes = 0, hbytes = 0;
  auto keyof = [&](size_t i, uint32_t id) -> double {
    double C = lat ? std::max(1e-6, (double)tr[i].cost) : 1.0, S = std::max(1u, osz[id]), F = freq[id];
    if (alg == "LRU") return (double)i;
    if (alg == "LFUDA") return L + F;
    if (alg == "GDS") return L + C / S;
    if (alg == "GDSF" || alg == "GDSFA") return L + C * F / S;
    if (alg == "GDSTAR") return L + pow(C * F / S, 1.0 / beta);
    if (alg == "KMGDSF") return L + C * F / S + W[i];
    if (alg == "PRED") return L + C * (double)W[i] / S;                // proposed-model prototype: learned P(reuse) replaces F
    if (dmcm) { double cur = std::max(1.0, (double)(tr[i].t - lastT[id])); double ratio = gapPrev[id] > 0 ? std::min(100.0, std::max(0.01, gapPrev[id] / cur)) : 1.0;
                return L + (C * F + kprev[id]) * ratio / S; }
    if (alg == "BELADY") return nxt[i] == UINT32_MAX ? -1e18 : -(double)nxt[i];
    if (alg == "BELADYSIZE") return nxt[i] == UINT32_MAX ? -1e18 : -(double)(nxt[i] - i) * S;  // farthest reuse x size
    fprintf(stderr, "unknown alg\n"); exit(1);
  };
  auto t0 = std::chrono::steady_clock::now();
  for (size_t i = 0; i < n; ++i) {
    const Rec& r = tr[i]; uint32_t id = r.id; bool meas = r.t >= test_start;
    if (meas) { req++; bytes += r.size; }
    auto evict_one = [&](uint32_t keep) -> bool {   // evict the valid entry with the smallest key (never `keep`); queue 0 first
      for (int qi = 0; qi < 2; ++qi) {
        std::priority_queue<HE>& q = pqs[qi]; std::vector<HE> held; bool ok = false;
        while (!q.empty()) {
          HE e = q.top(); q.pop();
          if (!in[e.id] || e.ver != ver[e.id]) continue;          // stale entry
          if (e.id == keep) { held.push_back(e); continue; }
          in[e.id] = 0; used -= osz[e.id]; cached--; if (!belady && alg != "LRU") L = e.key; ok = true; break;
        }
        for (auto& h : held) q.push(h);
        if (ok) return true;
      }
      return false;
    };
    auto push = [&](uint32_t id, double k) { int qi = (dmcm && cls[id]) ? 1 : 0; pqs[qi].push({k, id, ver[id]}); if (dmcm) kprev[id] = k; };
    if (dmcm) cls[id] = W[i] > 0.5f;
    if (in[id]) {
      if (meas) { hits++; hbytes += r.size; }
      if (r.size != osz[id]) { used += (double)r.size - osz[id]; osz[id] = r.size; }   // object was updated
      while (used > cap && evict_one(id)) {}
      freq[id]++; ver[id]++; push(id, keyof(i, id));
    } else {
      if ((double)r.size > cap || r.size == 0) { goto hist; }
      if (belady && nxt[i] == UINT32_MAX) { goto hist; }
      if (alg == "GDSFA" && used + r.size > cap) {          // admission test (as GDSF_can_insert in libCacheSim)
        double knew = L + (lat ? std::max(1e-6, (double)r.cost) : 1.0) / std::max(1u, r.size);
        double need = used + r.size - cap; std::vector<HE> popped; bool ok = true;
        while (need > 0 && !pq.empty()) { HE e = pq.top(); pq.pop(); popped.push_back(e);
          if (!in[e.id] || e.ver != ver[e.id]) continue;
          if (e.key > knew) { ok = false; break; } need -= osz[e.id]; }
        for (auto& e : popped) pq.push(e);
        if (!ok) { goto hist; }
      }            // optimal: never admit an object with no future use
      while (used + r.size > cap && evict_one(UINT32_MAX)) {}
      in[id] = 1; osz[id] = r.size; freq[id] = 1; used += r.size; cached++; kprev[id] = 0;
      ver[id]++; push(id, keyof(i, id));
    }
  hist:
    if (seen[id]) gapPrev[id] = r.t - lastT[id];
    seen[id] = 1; lastT[id] = r.t;
    for (auto& q : pqs) if (q.size() > 4 * cached + 1000000) {   // compact stale entries
      std::priority_queue<HE> q2; while (!q.empty()) { HE e = q.top(); q.pop(); if (in[e.id] && e.ver == ver[e.id]) q2.push(e); } q.swap(q2);
    }
  }
  double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
  printf("{\"alg\":\"%s\",\"cost\":\"%s\",\"beta\":%g,\"cache_bytes\":%.0f,\"requests\":%llu,\"hit_ratio\":%.6f,\"byte_hit_ratio\":%.6f,\"sim_seconds\":%.2f,\"us_per_request\":%.4f}\n",
         alg.c_str(), lat ? "latency" : "one", beta, cap, (unsigned long long)req, req ? (double)hits / req : 0, bytes > 0 ? hbytes / bytes : 0, secs, 1e6 * secs / n);
  return 0;
}
