#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务 4：参数稳健性扫描
  - override 年龄阈值：8/10/12/15 年
  - RE/TA 分界：中位数 / 均值 / 25% 分位 / 75% 分位
  - 平滑窗口：2/3/5 年
  - 金融企业过滤：有/无
统一在「剔除金融企业」的主样本上扫描（另单列对照）。
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)                       # phase1/
DER = os.path.join(P1, "data_derived")
sys.path.insert(0, HERE)
import pandas as pd, numpy as np
import lifecycle as L
import lifecycle_meta as M

CN = L.STAGE_CN
FIN_RE = "银行|保险|证券|信托|期货|租赁|理财|金融|资产管理|资本"


def load():
    mode = sys.argv[1] if len(sys.argv) > 1 else "sample"
    if mode == "full" and os.path.exists(os.path.join(DER, "panel_full.csv")):
        p = pd.read_csv(os.path.join(DER, "panel_full.csv"), dtype={"bare": str})
        p["bare"] = p["bare"].astype(str).str.zfill(6)
        p["ts_code"] = np.where(p["bare"].map(M.list_year_map()).index == p["bare"], p["bare"], p["bare"])
        return _finish(p)
    a = pd.read_csv(os.path.join(DER, "panel_raw.csv"))
    b = pd.read_csv(os.path.join(DER, "panel_delisted.csv"))
    p = pd.concat([a, b], ignore_index=True).drop_duplicates(["ts_code", "year"])
    p["bare"] = p["ts_code"].str[-6:]
    nm = M.name_map()
    p["name"] = p["bare"].map(nm)
    p["name"] = p["name"].fillna(p.get("name", pd.Series(index=p.index, dtype=object)))
    p["list_year"] = p["bare"].map(M.list_year_map())
    p["list_year"] = p["list_year"].fillna(p["bare"].map(p.groupby("bare").year.min()))
    p["age"] = p["year"] - p["list_year"]
    p["is_fin"] = p["name"].astype(str).str.contains(FIN_RE, regex=True)
    return p


def _finish(p):
    nm = M.name_map()
    p["name"] = p["bare"].map(nm).fillna(p["bare"])
    p["list_year"] = p["bare"].map(M.list_year_map())
    p["list_year"] = p["list_year"].fillna(p["bare"].map(p.groupby("bare").year.min()))
    p["age"] = p["year"] - p["list_year"]
    p["is_fin"] = p["name"].astype(str).str.contains(FIN_RE, regex=True)
    return p


def classify_flex(p, age_t=10, re_cut="median", smooth_win=3, use="cfi_core"):
    """可调参分类：直接复用 lifecycle.classify（主设定口径 CFI_core），仅外露可调参数。

    ★ 曾经这里自带一套符号映射，但用的是原始 cfi 而非 cfi_core，
      导致「稳健性表的主设定行」与「报告第 6 章主设定」对不上。现改为统一调用。
    """
    d = p.copy()
    for c in ["revenue", "eq", "eq2", "cur_assets", "cur_liab", "capex"]:
        if c not in d.columns:
            d[c] = np.nan
    d = L.add_features(d)
    d = d.sort_values(["ts_code", "year"]).reset_index(drop=True)
    x = L.classify(d, use=use)
    if re_cut == "median":
        cut = x["re_s"].median()
    elif re_cut == "mean":
        cut = x["re_s"].mean()
    else:
        cut = x["re_s"].quantile(float(re_cut[1:]) / 100)
    over = (x.stage == "import") & (x.age > age_t) & x.re_s.notna()
    x.loc[over & (x.re_s > cut), "stage"] = "restruct"
    x.loc[over & (x.re_s <= cut), "stage"] = "growth"
    x = L.smooth(x, win=smooth_win)
    x["stage"] = x["stage_s"]
    x["stage"] = x["stage"].where(x["stage"].astype(str).isin(["import", "growth", "mature", "restruct"]))
    return x


def summarize(d):
    v = d[d.stage.notna() & (d.stage != "<NA>")]
    n = len(v)
    pct = v.stage.value_counts(normalize=True).mul(100)
    ages = {k: v[v.stage == k].age.median() for k in ["import", "growth", "mature", "restruct"]}
    # 跳变率
    jump = np.nan
    js = []
    for _, g in d.sort_values(["ts_code", "year"]).groupby("ts_code"):
        s = g.stage.dropna().astype(str)
        s = s[s != "<NA>"]
        if len(s) > 1:
            js.append((s.values[1:] != s.values[:-1]).mean())
    if js:
        jump = np.mean(js) * 100
    return dict(n_obs=n, n_firm=v.bare.nunique() if "bare" in v else v.ts_code.nunique(),
                imp=round(pct.get("import", 0), 1), gro=round(pct.get("growth", 0), 1),
                mat=round(pct.get("mature", 0), 1), res=round(pct.get("restruct", 0), 1),
                age_imp=ages["import"], age_gro=ages["growth"],
                age_mat=ages["mature"], age_res=ages["restruct"],
                jump=round(jump, 1) if jump == jump else np.nan)


def show(tag, d):
    s = summarize(d)
    mono = s["age_imp"] < s["age_gro"] < s["age_mat"]
    print(f"{tag:22s} 导入{s['imp']:5.1f}% 成长{s['gro']:5.1f}% 成熟{s['mat']:5.1f}% "
          f"整合{s['res']:5.1f}% | 年龄 {s['age_imp']:.0f}/{s['age_gro']:.0f}/"
          f"{s['age_mat']:.0f}/{s['age_res']:.0f} | 跳变{s['jump']:.1f}% | "
          f"单调{'✓' if mono else '✗'}")
    return s


def main():
    p = load()
    pf = p[~p.is_fin].copy()
    print(f"全样本 {p.bare.nunique()} 只 / {len(p)} 公司-年")
    print(f"剔除金融 {pf.bare.nunique()} 只 / {len(pf)} 公司-年  (剔掉 {p.is_fin.sum()} 行)\n")
    rows = []

    base = classify_flex(pf)
    print("=" * 92)
    print("【主设定】age>10, RE 中位数, 3 年平滑, 剔除金融")
    print("=" * 92)
    s = show("主设定", base)
    rows.append({"test": "base", "param": "10/median/3/exFin", **s})

    print("\n" + "=" * 92)
    print("【4-A】override 年龄阈值")
    print("=" * 92)
    for t in [8, 10, 12, 15]:
        rows.append({"test": "age_threshold", "param": t, **show(f"age>{t}", classify_flex(pf, age_t=t))})

    print("\n" + "=" * 92)
    print("【4-B】RE/TA 分界")
    print("=" * 92)
    for m in ["median", "mean", "q25", "q75"]:
        rows.append({"test": "re_cut", "param": m, **show(f"RE {m}", classify_flex(pf, re_cut=m))})

    print("\n" + "=" * 92)
    print("【4-C】平滑窗口")
    print("=" * 92)
    for w in [2, 3, 5]:
        rows.append({"test": "smooth_win", "param": w, **show(f"win={w}", classify_flex(pf, smooth_win=w))})

    print("\n" + "=" * 92)
    print("【4-D】是否剔除金融企业")
    print("=" * 92)
    rows.append({"test": "fin_filter", "param": "keep", **show("保留金融", classify_flex(p, age_t=10))})
    rows.append({"test": "fin_filter", "param": "drop", **show("剔除金融", classify_flex(pf, age_t=10))})

    df = pd.DataFrame(rows)
    _mode = sys.argv[1] if len(sys.argv) > 1 else "sample"
    df.to_csv(os.path.join(DER, f"robustness_scan_{_mode}.csv" if _mode == "full" else "robustness_scan.csv"), index=False)

    print("\n" + "=" * 92)
    print("【4-E】★ 汇总：各参数下阶段占比的波动区间")
    print("=" * 92)
    g = df.groupby("test")[["imp", "gro", "mat", "res"]].agg(["min", "max"])
    for t in df.test.unique():
        sub = df[df.test == t]
        print(f"\n{t}:")
        for k, cn in [("imp", "导入"), ("gro", "成长"), ("mat", "成熟"), ("res", "整合")]:
            lo, hi = sub[k].min(), sub[k].max()
            print(f"    {cn} {lo:5.1f}% ~ {hi:5.1f}%   跨度 {hi-lo:4.1f}pp")

    print("\n" + "=" * 92)
    print("【4-F】★ 稳健性判据")
    print("=" * 92)
    worst = max((df[k].max() - df[k].min(), k) for k in ["imp", "gro", "mat", "res"])
    print(f"全参数扫描中最大波动: {worst[1]} 跨度 {worst[0]:.1f}pp")
    if worst[0] <= 8:
        print("→ ★ 结论: 阶段占比对所有参数都不敏感（跨度 ≤8pp），分类稳健。")
    else:
        print(f"→ ★ 结论: {worst[1]} 对参数敏感（跨度 {worst[0]:.1f}pp），需在论文中报告该敏感性。")
    print(f"\n跳变率范围: {df.jump.min():.1f}% ~ {df.jump.max():.1f}%（平滑有效抑制）")
    print(f"年龄单调性通过的设定: {int((df.age_imp<df.age_gro).sum())}/{len(df)} 个设定满足 导入<成长，"
          f"{int((df.age_gro<df.age_mat).sum())}/{len(df)} 满足 成长<成熟")

    print("\n输出: robustness_scan.csv")


if __name__ == "__main__":
    main()
