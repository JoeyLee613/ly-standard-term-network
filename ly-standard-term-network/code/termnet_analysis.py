# -*- coding: utf-8 -*-
"""
林业行业标准题录的术语共现网络分析（正式版）
================================================
数据：LY/T、LY 行业标准题录 2841 条（全国标准信息公共服务平台，采集于 2026-11-15）
单元：标准名称中的领域术语（剥离体裁词后）
流程：术语抽取 → 共现网络 → 社区发现（多次运行取最优 + 稳健性）→ 中心性
      → 社区间连通性 → 时序演化 → 术语-体裁搭配
"""
from pathlib import Path
import csv, io, re, json, os, itertools, collections
import jieba
import networkx as nx
import community as community_louvain

jieba.setLogLevel(20)

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "data"
OUT = ROOT / "results"
os.makedirs(OUT, exist_ok=True)

# ================================================================ 1 术语口径
GENRE = {
    "技术规程", "技术规范", "技术条件", "技术要求", "技术导则", "技术标准",
    "试验方法", "测定方法", "检测方法", "分析方法", "评价方法",
    "规范", "规程", "导则", "指南", "通则", "总则", "准则", "规则", "规定",
    "要求", "条件", "方法", "测定", "测试", "检验", "评价", "评估",
    "分类", "等级", "规格", "指标", "体系", "标准", "型号", "参数", "标志",
    "术语", "词汇", "部分", "通用", "综合", "基本", "一般", "原则", "编制", "编写",
    "技术", "生产", "管理", "中国", "国家", "行业",
    "及其", "主要", "使用", "研究", "以及", "包括", "相关", "进行", "具有", "采用",
    "代替", "规定性", "规范性",
}
SYNONYM = {"木质": "木材", "木质材料": "木材", "森林资源": "资源"}

def normalize(name):
    n = re.sub(r"[（(][^）)]{0,40}[）)]", "", name)
    n = re.sub(r"第[一二三四五六七八九十\d]+部分\s*[:：]?", "", n)
    n = re.sub(r"[—\-－]{2,}", "", n)
    return n.strip()

def tokens(name):
    out, seen = [], set()
    for w in jieba.lcut(normalize(name)):
        w = w.strip()
        if len(w) < 2 or not re.match(r"^[\u4e00-\u9fa5]+$", w) or w in GENRE:
            continue
        w = SYNONYM.get(w, w)
        if w not in seen:
            seen.add(w); out.append(w)
    return out

def genre_of(name):
    """标注标准体裁类型，用于术语-体裁搭配分析"""
    n = normalize(name)
    rules = [
        ("试验检测方法", ["试验方法", "测定方法", "检测方法", "分析方法", "测试方法", "测定", "试验", "检验方法"]),
        ("产品与质量", ["质量等级", "等级", "规格", "技术要求", "技术条件", "质量要求"]),
        ("技术规程", ["技术规程", "规程", "技术规范", "规范", "作业规程"]),
        ("术语与分类", ["术语", "词汇", "分类", "代码", "命名"]),
        ("评价与认证", ["评价", "评估", "认证", "审核", "鉴定"]),
        ("导则与指南", ["导则", "指南", "通则", "总则", "准则"]),
    ]
    for label, kws in rules:
        if any(k in n for k in kws):
            return label
    # 无体裁标记的名称多为直接以对象命名的产品标准（如"沉香""竹牙签"）
    return "产品与质量" if len(n) <= 14 else "其他"

from datetime import datetime, timezone, timedelta
def year_of(ms):
    try:
        return datetime.fromtimestamp(int(ms) / 1000, timezone(timedelta(hours=8))).year
    except Exception:
        return None

rows = list(csv.DictReader(io.open(RUN / "ly_standards_raw.csv", encoding="utf-8-sig")))
docs = []
for r in rows:
    tk = tokens(r["chName"])
    if not tk:
        continue
    docs.append({"code": r["code"], "name": r["chName"], "terms": tk,
                 "year": year_of(r["issueDate"]), "status": r["status"],
                 "genre": genre_of(r["chName"])})
freq = collections.Counter(t for d in docs for t in d["terms"])
print(f"题录 {len(rows)} 条，可解析 {len(docs)} 条，术语 {len(freq)} 个，词次 {sum(freq.values())}")

# ================================================================ 2 网络
MIN_TERM_FREQ, MIN_EDGE_W = 3, 2
keep = sorted(t for t, c in freq.items() if c >= MIN_TERM_FREQ)
keepset = set(keep)
edges = collections.Counter()
for d in docs:
    ts = sorted({t for t in d["terms"] if t in keepset})
    for a, b in itertools.combinations(ts, 2):
        edges[(a, b)] += 1

G = nx.Graph()
for t in keep:
    G.add_node(t, freq=freq[t])
for (a, b), w in sorted(edges.items()):
    if w >= MIN_EDGE_W:
        G.add_edge(a, b, weight=w)
iso = [n for n in G if G.degree(n) == 0]
G.remove_nodes_from(iso)
print(f"网络 节点 {G.number_of_nodes()} 边 {G.number_of_edges()}（移除无边节点 {len(iso)}）")

comps = sorted(nx.connected_components(G), key=len, reverse=True)
giant = G.subgraph(comps[0]).copy()

# ================================================================ 3 社区发现（多次取优）
best_q, best_part, qs = -1, None, []
for seed in range(200):
    p = community_louvain.best_partition(G, weight="weight", random_state=seed)
    q = community_louvain.modularity(p, G, weight="weight")
    qs.append(q)
    if q > best_q:
        best_q, best_part = q, p
partition = best_part
n_comm = len(set(partition.values()))
print(f"Louvain 200 次：Q 均值 {sum(qs)/len(qs):.4f}，区间 [{min(qs):.4f}, {max(qs):.4f}]，取最优 {best_q:.4f}，社区 {n_comm} 个")

comm_terms = collections.defaultdict(list)
for t, c in partition.items():
    comm_terms[c].append(t)
comm_terms = {c: sorted(ts, key=lambda x: -freq[x]) for c, ts in comm_terms.items()}
big = {c: ts for c, ts in comm_terms.items() if len(ts) >= 5}
big = dict(sorted(big.items(), key=lambda kv: -len(kv[1])))
cov = sum(len(v) for v in big.values())
print(f"规模>=5 的社区 {len(big)} 个，覆盖节点 {cov}/{G.number_of_nodes()}（{cov/G.number_of_nodes()*100:.1f}%）")

# ================================================================ 4 社区间连通性
inner = outer = 0
for a, b, d in G.edges(data=True):
    if partition[a] == partition[b]:
        inner += d["weight"]
    else:
        outer += d["weight"]
ext_ratio = outer / (inner + outer) * 100
print(f"社区内边权 {inner}，社区间 {outer}，社区间占比 {ext_ratio:.1f}%")

comm_ext = {}
for c, ts in big.items():
    ii = sum(d["weight"] for _, _, d in G.subgraph(ts).edges(data=True))
    oo = sum(d["weight"] for u in ts for _, _, d in G.edges(u, data=True) if partition[_] != c)
    comm_ext[c] = {"n": len(ts), "inner_w": ii, "outer_w": oo,
                   "ext_share": round(oo / (ii + oo) * 100, 1) if ii + oo else 0}

# ================================================================ 5 中心性
deg = nx.degree_centrality(G)
btw = nx.betweenness_centrality(G, weight=None, normalized=True)

# ================================================================ 6 时序演化
PERIODS = [(0, 2009), (2010, 2014), (2015, 2019), (2020, 2026)]
NP = len(PERIODS)
def pidx(y):
    if y is None: return None
    for i, (a, b) in enumerate(PERIODS):
        if a <= y <= b: return i
    return None

term_period = collections.defaultdict(lambda: [0] * NP)
period_total = [0] * NP
first_year = {}
for d in docs:
    if d["year"]:
        for t in d["terms"]:
            if t not in first_year or d["year"] < first_year[t][0]:
                first_year[t] = (d["year"], d["name"])
    i = pidx(d["year"])
    if i is None: continue
    period_total[i] += 1
    for t in set(d["terms"]):
        if t in G:
            term_period[t][i] += 1
print(f"各时段标准数 {period_total}")

new_by_year = collections.Counter()
tot_by_year = collections.Counter()
for d in docs:
    if not d["year"]: continue
    tot_by_year[d["year"]] += 1
for t, (y, _) in first_year.items():
    if y: new_by_year[y] += 1

evol = []
for t, arr in term_period.items():
    tt = sum(arr)
    if tt < 8: continue
    sh = [arr[i] / period_total[i] if period_total[i] else 0 for i in range(NP)]
    evol.append({"term": t, "counts": arr, "shares": [round(s * 100, 2) for s in sh],
                 "delta_pp": round((sh[NP - 1] - sh[0]) * 100, 2), "total": tt,
                 "comm": partition[t]})
evol.sort(key=lambda x: -x["delta_pp"])

# ================================================================ 7 术语-体裁搭配
genre_terms = collections.defaultdict(collections.Counter)
genre_cnt = collections.Counter()
for d in docs:
    genre_cnt[d["genre"]] += 1
    for t in set(d["terms"]):
        if t in G:
            genre_terms[d["genre"]][t] += 1

multi_genre = []
for t in G.nodes:
    gs = [g for g in genre_terms if genre_terms[g][t] > 0]
    if len(gs) >= 3:
        multi_genre.append({"term": t, "n_genre": len(gs), "freq": freq[t],
                            "genres": {g: genre_terms[g][t] for g in gs}})
multi_genre.sort(key=lambda x: (-x["n_genre"], -x["freq"]))

# ================================================================ 8 输出
metrics = {
    "n_records": len(rows), "n_records_parsed": len(docs),
    "n_terms_total": len(freq), "term_word_count": sum(freq.values()),
    "avg_terms_per_record": round(sum(len(d["terms"]) for d in docs) / len(docs), 2),
    "n_terms_in_net": G.number_of_nodes(), "n_edges": G.number_of_edges(),
    "min_term_freq": MIN_TERM_FREQ, "min_edge_weight": MIN_EDGE_W,
    "density": round(nx.density(G), 4),
    "avg_degree": round(2 * G.number_of_edges() / G.number_of_nodes(), 2),
    "n_components": len(comps), "giant_nodes": len(comps[0]),
    "giant_share": round(len(comps[0]) / G.number_of_nodes() * 100, 1),
    "avg_clustering": round(nx.average_clustering(G), 4),
    "giant_avg_path": round(nx.average_shortest_path_length(giant), 3),
    "giant_diameter": nx.diameter(giant),
    "modularity": round(best_q, 4),
    "q_mean_200": round(sum(qs) / len(qs), 4),
    "q_min_200": round(min(qs), 4), "q_max_200": round(max(qs), 4),
    "n_communities": n_comm, "n_communities_ge5": len(big),
    "big_comm_coverage": round(cov / G.number_of_nodes() * 100, 1),
    "weight_inner": inner, "weight_outer": outer, "outer_weight_share": round(ext_ratio, 1),
    "periods": PERIODS, "period_total": period_total,
}
json.dump(metrics, io.open(OUT / "network_metrics.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\n=== 指标 ===")
for k in ["density", "avg_degree", "avg_clustering", "giant_avg_path", "giant_diameter",
          "modularity", "q_mean_200", "n_communities_ge5", "big_comm_coverage",
          "weight_inner", "weight_outer", "outer_weight_share"]:
    print(f"  {k:22s} {metrics[k]}")

print("\n=== 大社区（>=5节点）===")
for c, ts in big.items():
    print(f"  C{c} n={len(ts):3d} 对外{e['ext_share'] if (e:=comm_ext[c]) else 0:5.1f}%  " + "、".join(f"{t}({freq[t]})" for t in ts[:10]))

with io.open(OUT / "nodes.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["term", "freq", "community", "degree_cent", "betweenness_cent"]
               + [f"p{i+1}" for i in range(NP)] + ["delta_pp", "first_year"])
    for n in G.nodes:
        tp = term_period.get(n, [0] * NP); tt = sum(tp)
        dlt = round((tp[NP - 1] / period_total[NP - 1] - tp[0] / period_total[0]) * 100, 2) \
            if tt >= 8 and period_total[0] and period_total[NP - 1] else ""
        w.writerow([n, freq[n], partition[n], round(deg[n], 4), round(btw[n], 4)]
                   + tp + [dlt, first_year.get(n, ("", ""))[0]])

with io.open(OUT / "edges.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["source", "target", "weight"])
    for a, b, d in G.edges(data=True):
        w.writerow([a, b, d["weight"]])

with io.open(OUT / "communities.txt", "w", encoding="utf-8") as f:
    f.write(f"Q={best_q:.4f} (200次均值 {sum(qs)/len(qs):.4f}), {n_comm} 社区\n")
    f.write(f"社区内边权 {inner} / 社区间 {outer} = 间占比 {ext_ratio:.1f}%\n\n")
    for c, ts in big.items():
        f.write(f"C{c} n={len(ts)} 对外{comm_ext[c]['ext_share']}%: "
                + "、".join(f"{t}({freq[t]})" for t in ts[:40]) + "\n\n")

json.dump({"periods": PERIODS, "period_total": period_total, "evol": evol,
           "new_by_year": dict(sorted(new_by_year.items())),
           "tot_by_year": dict(sorted(tot_by_year.items())),
           "genre_cnt": dict(genre_cnt),
           "multi_genre": multi_genre[:40]},
          io.open(OUT / "evolution.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

with io.open(OUT / "communities.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["community", "n_terms", "outer_share_pct", "top_terms"])
    for c, ts in big.items():
        w.writerow([c, len(ts), comm_ext[c]["ext_share"],
                    "、".join(f"{t}({freq[t]})" for t in ts[:15])])

print(f"\n已输出到 {OUT}")
