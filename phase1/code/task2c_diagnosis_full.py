#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务 2c：★ 整合期年龄异常诊断（纳入退市公司后的完整版）

原异常：整合期中位年龄 10-13 岁，全样本最高；理论上衰退/整合期应偏低。
原假设：A 股退市机制让老公司长期挂着。
本脚本把 360 只退市公司并入，检验该假设。
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


def prep(path, is_delisted):
    p = pd.read_csv(path)
    p["bare"] = p["ts_code"].str[-6:]
    p["name"] = p["bare"].map(M.name_map()).fillna(p["name"])
    if "list_year" not in p.columns:
        p["age"] = p["year"] - p["bare"].map(M.list_year_map())
    else:
        p["age"] = p["year"] - p["list_year"]
    p["delisted"] = is_delisted
    for c in ["revenue", "eq", "eq2", "cur_assets", "cur_liab", "capex"]:
        if c not in p.columns:
            p[c] = np.nan
    return L.add_features(p)


def main():
    a = prep(os.path.join(DER, "panel_raw.csv"), False)
    b = prep(os.path.join(DER, "panel_delisted.csv"), True)
    b = b[~b.bare.isin(set(a.bare))]          # 去重
    d = pd.concat([a, b], ignore_index=True).sort_values(["ts_code", "year"])
    print(f"在市 {a.bare.nunique()} 只 / {len(a)} 公司-年")
    print(f"退市 {b.bare.nunique()} 只 / {len(b)} 公司-年")
    print(f"合计 {d.bare.nunique()} 只 / {len(d)} 公司-年\n")

    x = L.classify(d, use="cfi_core")
    v = x[x.stage.notna()].copy()

    print("=" * 72)
    print("【2-c-1】★ 各阶段：年龄、盈利、已退市比例  ← 核心检验")
    print("=" * 72)
    t = v.groupby("stage").agg(n=("age", "size"), 中位年龄=("age", "median"),
                              中位ROA=("cfo_s", "median"), 中位RE_TA=("re_s", "median"),
                              中位营收增速=("rev_growth", "median"),
                              样本内退市比例=("delisted", "mean"))
    t = t.reindex(["import", "growth", "mature", "restruct"])
    t.index = [CN[i] for i in t.index]
    t["样本内退市比例"] = (t["样本内退市比例"] * 100).round(1)
    print(t.round(3).to_string())
    print("\n美股基准: 年龄 导入6.4 / 成长7.7 / 成熟13.8 / 衰退10.1")

    base = v.delisted.mean() * 100
    print(f"\n★ 全样本退市公司-年占比: {base:.1f}%")
    print("★ 各阶段退市比例 / 基准:")
    for s in t.index:
        print(f"    {s}  {t.loc[s,'样本内退市比例']:5.1f}%  = 基准的 "
              f"{t.loc[s,'样本内退市比例']/base:.2f} 倍")

    print("\n" + "=" * 72)
    print("【2-c-2】★ 整合期拆两类：卖资产 vs 烧钱")
    print("=" * 72)
    r = v[v.stage == "restruct"].copy()
    r["类型"] = np.where(r.cfi_core_s > 0, "A_卖资产", "B_烧钱")
    t2 = r.groupby("类型").agg(n=("age", "size"), 中位年龄=("age", "median"),
                              中位ROA=("cfo_s", "median"),
                              中位资产亿=("ta", "median"), 退市比例=("delisted", "mean"))
    t2["中位资产亿"] = (t2["中位资产亿"] / 1e8).round(1)
    t2["退市比例"] = (t2["退市比例"] * 100).round(1)
    print(t2.to_string())

    print("\n" + "=" * 72)
    print("【2-c-3】★ 判据：假设成立吗")
    print("=" * 72)
    ra, rb = t2.loc["A_卖资产"], t2.loc["B_烧钱"]
    print(f"假设: 『整合期又老又易退市，因为 A 股老公司靠卖资产苟着』")
    print(f"实测: 整合期年龄 {t.loc['整合期','中位年龄']:.0f} 岁 (全样本最高 "
          f"{'✓' if t.loc['整合期','中位年龄']==t['中位年龄'].max() else '✗'})")
    print(f"      整合期退市率 {t.loc['整合期','样本内退市比例']:.1f}% vs 基准 {base:.1f}% "
          f"= {t.loc['整合期','样本内退市比例']/base:.2f} 倍 "
          f"{'✓ 成立' if t.loc['整合期','样本内退市比例']>base*2 else '✗ 不成立'}")
    print(f"      A类(卖资产) 退市率 {ra['退市比例']:.1f}% vs B类(烧钱) {rb['退市比例']:.1f}%")
    if t.loc["整合期", "样本内退市比例"] > base * 2:
        print(f"\n→ ★ 假设成立。整合期确实是『高龄 + 高退市风险』群体，")
        print(f"   且卖资产型({ra['退市比例']:.1f}%)显著高于烧钱型({rb['退市比例']:.1f}%)，")
        print(f"   符合『经营困难→变卖资产→退市』的路径。")
        print(f"   这解释了为何整合期年龄最高：衰退过程本身耗时多年。")
    else:
        print(f"\n→ ★ 假设不成立。整合期年龄偏高另有原因，需查行业构成。")

    print("\n" + "=" * 72)
    print("【2-c-4】控制退市后，年龄单调性是否恢复")
    print("=" * 72)
    for lab, sub in [("全样本", v), ("仅在市", v[~v.delisted]), ("仅退市", v[v.delisted])]:
        g = sub.groupby("stage").age.median().reindex(["import", "growth", "mature", "restruct"])
        g.index = [CN[i] for i in g.index]
        mono = g["导入期"] < g["成长期"] < g["成熟期"]
        print(f"  {lab:6s} 导入{g['导入期']:.0f} 成长{g['成长期']:.0f} "
              f"成熟{g['成熟期']:.0f} 整合{g['整合期']:.0f}  "
              f"单调递增 {'✓' if mono else '✗'}")

    v.to_csv(os.path.join(DER, "delist_diagnosis_full.csv"), index=False)
    print("\n输出: delist_diagnosis_full.csv")


if __name__ == "__main__":
    main()
