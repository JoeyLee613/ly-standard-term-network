# -*- coding: utf-8 -*-
"""论文插图生成（黑白，适配期刊单栏/通栏印刷）"""
from pathlib import Path
import csv, io, json, os, math, collections
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import networkx as nx

plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 9

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "results"
FIG = ROOT / "figures"
os.makedirs(FIG, exist_ok=True)

nodes = list(csv.DictReader(io.open(RUN / "nodes.csv", encoding="utf-8-sig")))
edges = list(csv.DictReader(io.open(RUN / "edges.csv", encoding="utf-8-sig")))
met = json.load(io.open(RUN / "network_metrics.json", encoding="utf-8"))
d = json.load(io.open(RUN / "evolution.json", encoding="utf-8"))

G = nx.Graph()
for r in nodes:
    G.add_node(r["term"], freq=int(r["freq"]), comm=int(r["community"]))
for r in edges:
    G.add_edge(r["source"], r["target"], weight=int(r["weight"]))

NAME = {19: "木材加工与林化产品", 7: "森林经营与生态工程", 6: "资源调查与灾害监测",
        10: "林业与园林机械", 11: "材料性能与试验方法", 22: "苗木质量与培育",
        8: "种苗繁育与野生动物", 17: "采运机械与验收", 5: "经济林栽培",
        14: "人造板制造", 4: "区域森林经营", 0: "植物新品种DUS测试",
        15: "分子鉴定", 29: "木材干燥", 38: "测树与计量", 40: "林副产物利用"}


def save(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"{name}.{ext}", dpi=340, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"{name} ok")


# ================================================================ 图1 术语共现网络
cc = collections.Counter(dd["comm"] for _, dd in G.nodes(data=True))
bigc = {c for c, n in cc.items() if n >= 5}
order = sorted(bigc, key=lambda c: -cc[c])
maxn = max(cc[c] for c in order)

keep_nodes = []
for c in bigc:
    ns = sorted([n for n, dd in G.nodes(data=True) if dd["comm"] == c],
                key=lambda x: -G.nodes[x]["freq"])
    keep_nodes += ns[:18]
H = G.subgraph(keep_nodes).copy()
print(f"图1 子图：{H.number_of_nodes()} 节点 / {H.number_of_edges()} 边 / {len(order)} 模块")

pos = {}
ncols, cell = 4, 2.80
for i, c in enumerate(order):
    r_, q_ = divmod(i, ncols)
    cx = (q_ - (ncols - 1) / 2) * cell
    cy = -(r_ - (math.ceil(len(order) / ncols) - 1) / 2) * cell
    sub = H.subgraph([n for n, dd in H.nodes(data=True) if dd["comm"] == c])
    sp = nx.spring_layout(sub, k=2.0, iterations=220, seed=11)
    if len(sp) > 1:
        mx = max(max(abs(v) for v in xy) for xy in sp.values()) or 1
        sp = {k: (v[0] / mx, v[1] / mx) for k, v in sp.items()}
    rad = 0.46 + 0.72 * (cc[c] / maxn) ** 0.5
    for n, (x, y) in sp.items():
        pos[n] = (cx + x * rad, cy + y * rad)

GRAYS = ["0.28", "0.50", "0.70", "0.87"]
fig, ax = plt.subplots(figsize=(7.6, 6.4))
for a, b, dd in H.edges(data=True):
    ca, cb = G.nodes[a]["comm"], G.nodes[b]["comm"]
    x1, y1 = pos[a]; x2, y2 = pos[b]
    if ca == cb:
        ax.plot([x1, x2], [y1, y2], color="0.55", lw=min(0.22 + 0.16 * dd["weight"], 1.5),
                alpha=0.62, zorder=1, solid_capstyle="round")
    elif dd["weight"] >= 4:                     # 仅绘实质桥梁（权≥4）
        ax.plot([x1, x2], [y1, y2], color="0.62", lw=0.42, ls=(0, (2.4, 2.0)),
                alpha=0.8, zorder=0.5)

for i, c in enumerate(order):
    ns = [n for n, dd in H.nodes(data=True) if dd["comm"] == c]
    ax.scatter([pos[n][0] for n in ns], [pos[n][1] for n in ns],
               s=[8 + 4.6 * (G.nodes[n]["freq"] ** 0.5) for n in ns],
               c=GRAYS[i % len(GRAYS)], edgecolors="black", linewidths=0.42,
               zorder=2, alpha=0.95)
    ys = [pos[n][1] for n in ns]
    xs = [pos[n][0] for n in ns]
    top1 = max(ns, key=lambda x: G.nodes[x]["freq"])
    ax.annotate(f"C{c} {NAME[c]}｜{top1}({G.nodes[top1]['freq']})",
                (sum(xs) / len(xs), min(ys) - 0.05), fontsize=6.3, ha="center",
                va="top", color="0.08", zorder=4,
                bbox=dict(boxstyle="round,pad=0.16", fc="white", ec="none", alpha=0.88))

ax.set_axis_off()
ax.margins(0.055)
plt.tight_layout()
save(fig, "fig1_term_network")

# ================================================================ 图2 模块对外连接率
comm_rows = list(csv.DictReader(io.open(RUN / "communities.csv", encoding="utf-8-sig")))
rows = sorted([(NAME[int(r["community"])], int(r["n_terms"]),
                float(r["outer_share_pct"]), int(r["community"])) for r in comm_rows],
              key=lambda x: x[2])

fig, ax = plt.subplots(figsize=(6.9, 4.3))
vals = [r[2] for r in rows]
ax.barh(range(len(rows)), vals,
        color=["0.34" if v < 15 else ("0.60" if v < 30 else "0.84") for v in vals],
        edgecolor="black", linewidth=0.6, height=0.66)
for i, (nm, n, v, c) in enumerate(rows):
    ax.text(v + 0.9, i, f"{v:.1f}%  (n={n})", va="center", fontsize=7.2,
            bbox=dict(boxstyle="square,pad=0.10", fc="white", ec="none"))
ax.set_yticks(range(len(rows)))
ax.set_yticklabels([f"{r[0]} (C{r[3]})" for r in rows], fontsize=7.6)
ax.axvline(met["outer_weight_share"], color="0.12", ls="--", lw=0.9, zorder=0)
ax.text(met["outer_weight_share"] - 0.5, len(rows) - 0.30,
        f"全网均值 {met['outer_weight_share']:.1f}%", fontsize=7, color="0.12",
        ha="right", va="bottom",
        bbox=dict(boxstyle="square,pad=0.12", fc="white", ec="none"))
ax.set_xlabel("模块对外连接率 / %（该模块与其余模块的共现权重占比）", fontsize=8.6)
ax.set_xlim(0, max(vals) * 1.30)
ax.spines[["top", "right"]].set_visible(False)
ax.tick_params(axis="y", length=0)
plt.tight_layout()
save(fig, "fig2_module_coupling")

# ================================================================ 图3 术语占比四时段迁移
ev = [e for e in d["evol"] if abs(e["delta_pp"]) >= 1.3]
up = [e for e in ev if e["delta_pp"] > 0][:8]
dn = [e for e in ev if e["delta_pp"] < 0][-8:][::-1]
sel = dn + up

fig, ax = plt.subplots(figsize=(7.8, 4.9))
X = [0, 1, 2, 3]
ax.set_xticks(X)
ax.set_xticklabels(["2009 年及以前\n(n=797)", "2010—2014 年\n(n=643)",
                    "2015—2019 年\n(n=869)", "2020—2026 年\n(n=520)"],
                   fontsize=7.4)
ax.set_xlim(-0.15, 4.66)
ax.grid(axis="y", ls=":", lw=0.5, color="0.82")

for e in sel:
    col = "0.12" if e["delta_pp"] > 0 else "0.58"
    ax.plot(X, e["shares"], marker="o", ms=3.0, lw=1.15, color=col,
            ls="-" if e["delta_pp"] > 0 else "--", alpha=0.92, zorder=2)

# 标签防重叠：按末端值排序后强制最小间距，加引线指回真实端点
lab = sorted(sel, key=lambda e: e["shares"][3])
ymin, ymax = 0, max(e["shares"][3] for e in sel)
gap = (ymax - ymin) * 0.056 + 0.20
adj = []
for i, e in enumerate(lab):
    y = max(e["shares"][3], 0.42 if i == 0 else adj[-1] + gap)
    adj.append(y)
over = adj[-1] - (ymax + 0.30)
if over > 0:
    adj = [y - over for y in adj]
    adj[0] = max(adj[0], 0.32)

for e, yl in zip(lab, adj):
    col = "0.12" if e["delta_pp"] > 0 else "0.58"
    ax.annotate(e["term"], xy=(3, e["shares"][3]), xytext=(3.26, yl),
                fontsize=7.0, va="center", color=col,
                arrowprops=dict(arrowstyle="-", lw=0.5, color=col,
                                shrinkA=0, shrinkB=2,
                                connectionstyle="arc3,rad=0"))

ax.set_ylim(-0.95, ymax * 1.20)
ax.set_ylabel("术语在同期标准中的出现率 / %", fontsize=8.6)
ax.spines[["top", "right"]].set_visible(False)
ax.legend(handles=[Line2D([], [], color="0.12", lw=1.3, ls="-", label="占比上升"),
                   Line2D([], [], color="0.58", lw=1.3, ls="--", label="占比下降")],
          fontsize=7.4, loc="upper left", frameon=False)
plt.tight_layout()
save(fig, "fig3_term_evolution")

# ================================================================ 图4 新术语进入率
ny = {int(k): v for k, v in d["new_by_year"].items()}
ty = {int(k): v for k, v in d["tot_by_year"].items()}
yrs = [y for y in range(2005, 2027) if ty.get(y, 0) >= 30]
ratio = [ny.get(y, 0) / ty[y] * 100 for y in yrs]

fig, ax = plt.subplots(figsize=(6.7, 3.6))
ax.bar(yrs, ratio, color="0.74", edgecolor="black", linewidth=0.6, width=0.68)
ax.plot(yrs, ratio, color="0.12", lw=1.1, marker="o", ms=2.8)
ax.axhline(100, color="0.38", ls=":", lw=0.9)
ax.text(yrs[-1] + 0.2, 100, "  新术语数 = 当年标准数", fontsize=6.9, color="0.32",
        va="center", ha="left")
ax.annotate("", xy=(yrs[-1], 100), xytext=(yrs[-1] + 0.15, 100),
            arrowprops=dict(arrowstyle="-", lw=0.7, color="0.38"))
ax.set_ylabel("新术语数 / 当年标准数 / %", fontsize=8.4)
ax.set_xlabel("发布年份", fontsize=8.4)
ax.spines[["top", "right"]].set_visible(False)
ax.tick_params(labelsize=7.6)
ax.set_xlim(yrs[0] - 0.7, yrs[-1] + 2.6)
ax.set_ylim(0, max(ratio) * 1.14)
plt.tight_layout()
save(fig, "fig4_new_term_rate")

print("全部完成")
