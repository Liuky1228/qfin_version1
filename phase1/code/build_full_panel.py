#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建全量面板（本地缓存 → panel_full.csv）
与旧版 build_panel.py 的三处区别：
  1. 兼容两套文件命名：sh600001_现金流量表.csv 与 000001_现金流量表.csv
  2. 缓存命中时不 sleep、不逐家打印（5856 家会白等 24 分钟并刷屏 5856 行）
  3. 同时并入 ~/life_cache_delisted 的 360 家退市公司
"""
import sys, os, glob, re, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pandas as pd, numpy as np
import lifecycle as L

CACHE = os.path.expanduser("~/life_cache")
DELISTED = os.path.expanduser("~/life_cache_delisted")
P1 = os.path.dirname(HERE)                       # phase1/
OUT = os.path.join(P1, "data_derived", "panel_full.csv")


def scan_full(cache):
    per = {}
    for suf in ["_现金流量表.csv", "_资产负债表.csv", "_利润表.csv"]:
        for f in glob.glob(f"{cache}/*{suf}"):
            stem = os.path.basename(f)[:-len(suf)]
            per.setdefault(stem[-6:], {"raw": stem, "has": set()})["has"].add(suf)
    return per


def build_from_cache(cache, tag, verbose_every=0):
    per = scan_full(cache)
    ok = {b: v["raw"] for b, v in per.items() if len(v["has"]) == 3}
    print(f"[{tag}] 发现 {len(per)} 个代码，三表齐全 {len(ok)} 个", flush=True)
    t0 = time.time()
    rows, skipped = [], []
    for i, (bare, key) in enumerate(sorted(ok.items()), 1):
        try:
            cf = pd.read_csv(f"{cache}/{key}_现金流量表.csv", parse_dates=["报告日"])
            bs = pd.read_csv(f"{cache}/{key}_资产负债表.csv", parse_dates=["报告日"])
        except Exception as e:
            skipped.append((key, f"读取失败 {type(e).__name__}"))
            continue
        cfa = cf[cf["报告日"].dt.month == 12].copy()
        bsa = bs[bs["报告日"].dt.month == 12].copy()
        if len(cfa) == 0 or len(bsa) == 0:
            skipped.append((key, "无 12-31 报告期"))
            continue
        cfa["year"] = cfa["报告日"].dt.year
        bsa["year"] = bsa["报告日"].dt.year
        cfa = cfa.drop_duplicates("year", keep="first").reset_index(drop=True)
        bsa = bsa.drop_duplicates("year", keep="first").reset_index(drop=True)

        cf_map, miss = {}, []
        for k, cands in L.CF_COLS.items():
            c = L.first_col(cfa, cands)
            if c is not None:
                cf_map[k] = L.num(cfa[c])
            elif k in ("cfo", "cfi", "cff"):
                miss.append(k)
        if miss:
            skipped.append((key, f"缺关键科目 {miss}"))
            continue
        d = pd.DataFrame({"year": cfa["year"].values})
        for k, v in cf_map.items():
            d[k] = np.asarray(v)
        for k in ["cfin_invest", "cfin_recov", "cfin_income"]:
            if k not in cf_map:
                d[k] = np.nan
        for k, cands in L.BS_COLS.items():
            c = L.first_col(bsa, cands)
            if c is not None:
                mp = dict(zip(bsa["year"].values, L.num(bsa[c]).values))
                d[k] = d["year"].map(mp)

        # 利润表（营收）
        f = f"{cache}/{key}_利润表.csv"
        try:
            isd = pd.read_csv(f, parse_dates=["报告日"])
            isa = isd[isd["报告日"].dt.month == 12].copy()
            isa["year"] = isa["报告日"].dt.year
            isa = isa.drop_duplicates("year", keep="first")
            rc = L.first_col(isa, L.REV_COLS)
            if rc is not None:
                d["revenue"] = d["year"].map(dict(zip(isa["year"].values, L.num(isa[rc]).values)))
            else:
                d["revenue"] = np.nan
        except Exception:
            d["revenue"] = np.nan

        d["ts_code"] = key          # 保留原始前缀，兼容 sh600001 / 000001 两种
        d["bare"] = bare
        d["name"] = bare
        d["src"] = tag
        rows.append(d)
        if verbose_every and i % verbose_every == 0:
            print(f"  [{i}/{len(ok)}] {key} 年报 {len(d)} 期", flush=True)

    p = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    print(f"[{tag}] 完成 {len(rows)}/{len(ok)} 家，{len(p)} 行，"
          f"耗时 {time.time()-t0:.0f}s，跳过 {len(skipped)} 家", flush=True)
    if skipped:
        for k, why in skipped[:15]:
            print(f"    跳过 {k}: {why}", flush=True)
        if len(skipped) > 15:
            print(f"    …另有 {len(skipped)-15} 家", flush=True)
    return p


def main():
    a = build_from_cache(CACHE, "在市")
    b = build_from_cache(DELISTED, "退市") if os.path.isdir(DELISTED) else pd.DataFrame()
    if len(b):
        overlap = set(a.get("bare", [])) & set(b.get("bare", []))
        if overlap:
            print(f"在市/退市重复 {len(overlap)} 家，按在市优先保留", flush=True)
            b = b[~b.bare.isin(overlap)]
        p = pd.concat([a, b], ignore_index=True)
    else:
        p = a
    p = p.drop_duplicates(["ts_code", "year"])
    p.to_csv(OUT, index=False)
    print(f"\n面板 {p.shape}：{p.ts_code.nunique()} 家 / "
          f"{p.bare.nunique()} 个裸码 / {p.year.min()}-{p.year.max()} 年")
    print(f"输出 → {OUT}  ({os.path.getsize(OUT)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
