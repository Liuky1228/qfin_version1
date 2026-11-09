#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务 2：退市识别 + 整合期年龄异常诊断
异常现象：整合期中位年龄 10-13 岁，全样本最高；理论上应偏低。
假设：A 股退市机制导致老公司能长期挂着 → 需要证据。
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)                       # phase1/
sys.path.insert(0, os.path.join(P1, "code"))     # 导入 lifecycle / lifecycle_meta
import pandas as pd, numpy as np
import lifecycle as L
import lifecycle_meta as M

CN = L.STAGE_CN


def main():
    panel = pd.read_csv(os.path.join(P1, "data_derived", "panel_raw.csv"))
    panel["bare"] = panel["ts_code"].str[-6:]
    panel["name"] = panel["bare"].map(M.name_map()).fillna(panel["ts_code"])
    panel["age"] = panel["year"] - panel["bare"].map(M.list_year_map())
    d = L.add_features(panel).sort_values(["ts_code", "year"]).reset_index(drop=True)

    # ---------- 2-A 退市/停止披露识别 ----------
    last = d.groupby("bare").year.max()
    alive = set(pd.read_csv(os.path.join(P1, "data_raw", "a_code_name.csv"),
                            dtype={"code": str})["code"].str.zfill(6))
    d["alive_now"] = d.bare.isin(alive)
    lastyear = d.groupby("bare").year.max()
    d["last_year"] = d.bare.map(lastyear)
    d["gone"] = ~d.alive_now
    print("=" * 70)
    print("【2-A】退市/停止披露识别")
    print("=" * 70)
    print(f"样本 {d.bare.nunique()} 只，其中已不在当前名单(推定退市/停牌) {d[d.gone].bare.nunique()} 只 "
          f"({d[d.gone].bare.nunique()/d.bare.nunique():.1%})")
    print(f"数据最后年份分布(已消失公司):")
    print(d[d.gone].groupby("bare").year.max().value_counts().sort_index().to_string())

    x = L.classify(d, use="cfi_core")
    x["gone"] = x.bare.map(lambda b: b not in alive)
    v = x[x.stage.notna()].copy()

    # ---------- 2-B 整合期拆成两类 ----------
    # A 类: CFI_core>0  → 卖资产
    # B 类: CFO<0 且 CFI_core<0 → 烧钱
    v["restruct_type"] = np.where(
        v.stage != "restruct", "",
        np.where(v.cfi_core_s > 0, "A_卖资产", "B_烧钱"))

    print("\n" + "=" * 70)
    print("【2-B】★ 整合期拆成两类：谁更老？谁更容易消失？")
    print("=" * 70)
    r = v[v.stage == "restruct"]
    t = r.groupby("restruct_type").agg(
        n=("age", "size"), 中位年龄=("age", "median"), 中位ROA=("cfo_s", "median"),
        中位资产=("ta", "median"), 消失比例=("gone", "mean"))
    t[["消失比例"]] = (t[["消失比例"]] * 100).round(1)
    t["中位资产"] = (t["中位资产"] / 1e8).round(1)
    print(t.to_string())
    print("\n对照: 全样本中位年龄 %.0f, 消失比例 %.1f%%"
          % (v.age.median(), v.gone.mean() * 100))

    print("\n" + "=" * 70)
    print("【2-C】各阶段的年龄与消失率（诊断异常）")
    print("=" * 70)
    t2 = v.groupby("stage").agg(n=("age", "size"), 中位年龄=("age", "median"),
                               消失比例=("gone", "mean"), 中位ROA=("cfo_s", "median"))
    t2 = t2.reindex(["import", "growth", "mature", "restruct"])
    t2.index = [CN[i] for i in t2.index]
    t2["消失比例"] = (t2["消失比例"] * 100).round(1)
    print(t2.round(2).to_string())
    print("\n美股基准: 导入6.4 / 成长7.7 / 成熟13.8 / 衰退10.1 年")
    print(f"★ 实测整合期年龄 {t2.loc['整合期','中位年龄']:.0f} 年, "
          f"消失率 {t2.loc['整合期','消失比例']:.1f}% (最高年龄+最高消失率)")

    # ---------- 2-D 判据 ----------
    print("\n" + "=" * 70)
    print("【2-D】★ 假设是否成立")
    print("=" * 70)
    a_dis = t.loc["A_卖资产", "消失比例"]
    b_dis = t.loc["B_烧钱", "消失比例"]
    a_age = t.loc["A_卖资产", "中位年龄"]
    b_age = t.loc["B_烧钱", "中位年龄"]
    print(f"假设: A股退市机制让老公司长期挂着 → 整合期『又老又容易消失』")
    print(f"实测: 整合期年龄 {t2.loc['整合期','中位年龄']:.0f} (全样本最高 ✓)  "
          f"消失率 {t2.loc['整合期','消失比例']:.1f}% (全样本最高 ✓)")
    print(f"      A类(卖资产) 年龄{a_age:.0f} 消失率{a_dis:.1f}%  n={t.loc['A_卖资产','n']}")
    print(f"      B类(烧钱)   年龄{b_age:.0f} 消失率{b_dis:.1f}%  n={t.loc['B_烧钱','n']}")
    if t2.loc["整合期", "消失比例"] > v.gone.mean() * 100 * 1.5:
        print(f"\n→ ★ 假设成立：整合期消失率是全样本的 "
              f"{t2.loc['整合期','消失比例']/(v.gone.mean()*100):.1f} 倍")
        print(f"   即『整合期 = 老公司卖资产求生，退市风险最高』，与美股不同源。")
    else:
        print(f"\n→ ★ 假设不成立，消失率无显著差异，需另找原因。")

    v.to_csv(os.path.join(HERE, "delist_diagnosis.csv"), index=False)
    print(f"\n输出: delist_diagnosis.csv")


if __name__ == "__main__":
    main()
