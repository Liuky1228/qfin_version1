#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务 1：ST 污染检验
目的：检验「整合期 ≈ 被 ST 的公司」这个断言是否成立。
输出：各阶段 ST 占比对比 + 剔除 ST 后的分布变化。
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)                       # phase1/
RAW = os.path.join(P1, "data_raw")
DER = os.path.join(P1, "data_derived")
sys.path.insert(0, HERE)
import pandas as pd, numpy as np
import lifecycle as L
import lifecycle_meta as M

CN = L.STAGE_CN


def load_st_yearly():
    """日频 ST 宽表 → 公司-年 ST 标记（任一天 ST 则该年记为 1）"""
    d = pd.read_csv(os.path.join(RAW, "stock_st_flag_20260630.csv"),
                    index_col=0, engine="python", dtype=str)
    d = d.replace({"True": True, "False": False})
    d.index = pd.to_datetime(d.index)
    d = d.astype("boolean")
    # 年内任一天为 True → 该公司该年 ST
    byyear = d.groupby(d.index.year).max().T          # index=代码, columns=年
    byyear = byyear.astype("float")
    byyear.columns = byyear.columns.astype(int)
    byyear.index = [c.split(".")[0] for c in byyear.index]   # 000001.SZ -> 000001
    return byyear


def main():
    panel = pd.read_csv(os.path.join(DER, "panel_raw.csv"))
    panel["bare"] = panel["ts_code"].str[-6:]
    panel["name"] = panel["bare"].map(M.name_map()).fillna(panel["ts_code"])
    panel["age"] = panel["year"] - panel["bare"].map(M.list_year_map())
    d = L.add_features(panel).sort_values(["ts_code", "year"]).reset_index(drop=True)

    st = load_st_yearly()
    print(f"ST 表: {st.shape[0]} 只 × {st.shape[1]} 年 ({st.index.min() if False else st.columns.min()}-{st.columns.max()})")

    d["st"] = np.nan
    for b, g in d.groupby("bare"):
        if b in st.index:
            d.loc[g.index, "st"] = g["year"].map(st.loc[b])
    print(f"ST 标记可匹配公司-年: {d['st'].notna().mean():.3f}")

    x = L.classify(d, use="cfi_core")
    v = x[x.stage.notna() & x.st.notna()].copy()

    print("\n" + "=" * 68)
    print("【任务1-A】各阶段 ST 占比  ← 核心检验")
    print("=" * 68)
    t = v.groupby("stage").agg(n=("st", "size"), ST占比=("st", "mean"),
                              中位年龄=("age", "median"), 中位ROA=("cfo_s", "median"))
    t = t.reindex(["import", "growth", "mature", "restruct"])
    t.index = [CN[i] for i in t.index]
    t["ST占比"] = (t["ST占比"] * 100).round(2)
    print(t.round(3).to_string())
    base = v.st.mean()
    print(f"\n全样本 ST 占比基准: {base*100:.2f}%")
    print("\n★ 倍数关系（阶段 ST 占比 / 全样本）:")
    for s, cn in t.iterrows():
        print(f"    {s}  {cn['ST占比']:5.2f}%   = 基准的 {cn['ST占比']/(base*100):.2f} 倍")

    print("\n" + "=" * 68)
    print("【任务1-B】★ 我的断言是否成立")
    print("=" * 68)
    r_st = t.loc["整合期", "ST占比"]
    i_st = t.loc["导入期", "ST占比"]
    print(f"断言原文: '衰退期/整合期公司几乎必然被 ST'")
    print(f"实测: 整合期 ST 占比 {r_st:.2f}%, 导入期 {i_st:.2f}%, 全样本 {base*100:.2f}%")
    if r_st > base * 3:
        print(f"→ ★ 成立（整合期 ST 占比是基准的 {r_st/(base*100):.1f} 倍）")
    else:
        print(f"→ ★ 不成立！整合期 ST 占比仅为基准的 {r_st/(base*100):.1f} 倍，")
        print(f"   文档中'衰退期几乎必然被 ST'的说法在 A 股站不住，需修改。")

    print("\n" + "=" * 68)
    print("【任务1-C】剔除 ST 后的阶段分布变化")
    print("=" * 68)
    allc = x.stage.value_counts(normalize=True).mul(100).round(1)
    cln = x[x.st == 0].stage.value_counts(normalize=True).mul(100).round(1)
    cmp = pd.DataFrame({"全样本": allc, "剔除ST后": cln}).fillna(0)
    cmp.index = [CN.get(i, i) for i in cmp.index]
    cmp["变化"] = (cmp["剔除ST后"] - cmp["全样本"]).round(1)
    print(cmp.reindex(["导入期", "成长期", "成熟期", "整合期"]).to_string())

    print("\n" + "=" * 68)
    print("【任务1-D】ST 公司的阶段分布（ST 公司都落在哪）")
    print("=" * 68)
    only = x[x.st == 1].stage.value_counts(normalize=True).mul(100).round(1)
    print(only.rename(index=CN).to_string())
    print(f"\n★ ST 公司共 {int((x.st==1).sum())} 个公司-年，占已分类样本 "
          f"{(x.st==1).sum()/x.stage.notna().sum():.1%}")

    v.to_csv(os.path.join(DER, "st_pollution_check.csv"), index=False)
    t.to_csv(os.path.join(DER, "st_stage_table.csv"))
    print(f"\n输出: st_pollution_check.csv, st_stage_table.csv")


if __name__ == "__main__":
    main()
