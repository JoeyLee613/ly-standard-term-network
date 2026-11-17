# -*- coding: utf-8 -*-
"""
采集「行业标准信息服务平台」(hbba.sacinfo.org.cn) 中 industry=林业 的全部标准题录。
用途：林业行业标准体系结构分析（论文 A）的原始数据。
只取公开题录字段，不涉及任何内部或涉密信息。

运行：python fetch_standards.py
输出：../data/ly_standards_raw.csv + ly_standards_raw.json
"""
import json
import time
import csv
import os
import sys
import urllib.parse
import urllib.request

API = "https://hbba.sacinfo.org.cn/stdQueryList"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Referer": "https://hbba.sacinfo.org.cn/stdList",
    "X-Requested-With": "XMLHttpRequest",
}
SIZE = 100


def query(page_no: int, industry: str = "林业"):
    data = urllib.parse.urlencode(
        {"current": page_no, "size": SIZE, "industry": industry}
    ).encode()
    req = urllib.request.Request(API, data=data, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    os.makedirs(out_dir, exist_ok=True)

    first = query(1)
    total = first["total"]
    pages = first["pages"]
    print(f"total={total} pages={pages} size={SIZE}")

    rows = list(first["records"])
    for p in range(2, pages + 1):
        for attempt in range(3):
            try:
                d = query(p)
                rows.extend(d["records"])
                print(f"  page {p}/{pages}  +{len(d['records'])}  cum={len(rows)}")
                break
            except Exception as e:
                print(f"  page {p} retry {attempt+1}: {e}")
                time.sleep(2)
        time.sleep(0.4)

    # 去重（按 pk）
    seen, uniq = set(), []
    for r in rows:
        k = r.get("pk") or r.get("code")
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)

    with open(os.path.join(out_dir, "standards_raw.json"), "w", encoding="utf-8") as f:
        json.dump({"total_reported": total, "collected": len(uniq), "records": uniq},
                  f, ensure_ascii=False, indent=1)

    cols = ["code", "chName", "industry", "chargeDept", "status",
            "issueDate", "actDate", "recordNo", "pk"]
    with open(os.path.join(out_dir, "ly_standards_raw.csv"), "w",
              encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in uniq:
            w.writerow({c: r.get(c, "") for c in cols})

    print(f"done. collected={len(uniq)} -> {out_dir}")


if __name__ == "__main__":
    main()
