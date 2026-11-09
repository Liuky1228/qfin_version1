#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生命周期分类有效性验证：分布 / 画像 / 时间趋势 / 稳健性。"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pandas as pd, numpy as np
import lifecycle as L

CN = {"import": "导入期", "growth": "成长期", "mature": "成熟期", "restruct": "整合期"}

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)                       # phase1/
import lifecycle_meta
d = L.add_features(pd.read_csv(os.path.join(P1, "data_derived", "panel_raw.csv")))
d = d.sort_values(["ts_code", "year"]).reset_index(drop=True)

# 真实公司名 + 真实上市日期（交易所官方）
# ★ ts_code 带 sh/sz 前缀，而交易所表用裸 6 位代码 → 必须取后 6 位再映射
d["bare"] = d["ts_code"].str[-6:]
d["name"] = d["bare"].map(lifecycle_meta.name_map()).fillna(d["ts_code"])
d["list_year"] = d["bare"].map(lifecycle_meta.list_year_map())
d["age"] = d["year"] - d["list_year"]
print("公司名有效: %.3f   上市年限有效: %.3f  中位年龄: %.1f"
      % ((d["name"] != d["ts_code"]).mean(), d["age"].notna().mean(), d["age"].median()))

print("=" * 72)
print("数据基础: 公司 %d, 公司-年 %d, 年份 %d-%d" % (
    d.ts_code.nunique(), len(d), d.year.min(), d.year.max()))

# ---------- 1. 覆盖与缺失 ----------
print("\n[1] 关键变量可用率")
for c in ["cfo_s", "cfi_s", "cff_s", "capex_s_neg", "cfi_core_s", "re_s", "rev_growth"]:
    print(f"    {c:12s} {d[c].notna().mean():.3f}")

d["cfi_usable"] = d["cfi_core_s"].notna()
print(f"    CFI_core 可构造年份占比: {d.cfi_usable.mean():.3f}")

# ---------- 2. 四种口径分类分布 ----------
print("\n[2] 阶段分布对比（★ V1/V2/V3 稳健性）")
# ★ 公平比较：只在 CFI_core 可构造的年份上比较三种口径
sub = d[d["cfi_core_s"].notna()].copy()
print(f"    （三种口径限定在同一子样本 n={len(sub)} 上比较）")
res = {}
for tag, kw in [("V0 原始CFI", dict(use="cfi")),
                ("V2 剔除理财CFI_core", dict(use="cfi_core")),
                ("V3 Capex口径", dict(use="capex"))]:
    x = L.classify(sub, **kw)
    res[tag] = x.stage.value_counts(normalize=True).mul(100).round(1)
dist = pd.DataFrame(res).fillna(0).reindex(["import", "growth", "mature", "restruct"])
dist.index = [CN[i] for i in dist.index]
print(dist.to_string())

# ---------- 3. 阶段画像（★ 核心验证）----------
print("\n[3] 各阶段画像（美股基准：导入ROIC为负、成熟最老且盈利最好、整合最差）")
x = L.classify(d, use="cfi_core")
v = x[x.stage.notna()].copy()
v["ROA"] = v["cfo_s"]          # 现金流/总资产，盈利代理
prof = v.groupby("stage").agg(
    n=("ROA", "size"),
    中位ROA=("ROA", "median"),
    中位CFI=("cfi_core_s", "median"),
    中位RE_TA=("re_s", "median"),
    中位营收增速=("rev_growth", "median"),
    中位杠杆=("lev", "median"),
).reindex(["import", "growth", "mature", "restruct"])
prof.index = [CN[i] for i in prof.index]
print(prof.round(3).to_string())

print("\n    画像单调性检验（★ 是否呈 Dickinson 预期的形态）")
roa = prof["中位ROA"]
print(f"      成熟期 ROA 最高?      {roa['成熟期'] == roa.max()}  (值 {roa['成熟期']:.3f})")
print(f"      导入期 ROA 最低?      {roa['导入期'] == roa.min()}  (值 {roa['导入期']:.3f})")
print(f"      整合期 ROA < 成熟期?  {roa['整合期'] < roa['成熟期']}")
re_rank = prof["中位RE_TA"]
print("    RE/TA 单调递增(导入<成长<成熟)? "
      f"{re_rank['导入期'] < re_rank['成长期'] < re_rank['成熟期']}")
print("    ★ 整合期 ROA 最低?      "
      f"{roa['整合期'] == roa.min()}  (值 {roa['整合期']:.3f})")

# ---------- 4. 时间趋势（★ 最强的免费检验）----------
print("\n[4] ★ 阶段占比时间趋势（成熟期占比必须随时间上升）")
tt = pd.crosstab(x[x.stage.notna()].year, x[x.stage.notna()].stage, normalize="index").mul(100)
tt = tt.reindex(columns=["import", "growth", "mature", "restruct"]).round(1)
tt.columns = [CN[c] for c in tt.columns]
print(tt.loc[[y for y in [2005, 2010, 2015, 2020, 2023] if y in tt.index]].to_string())
early = tt["成熟期"].loc[tt.index <= 2012].mean()
late = tt["成熟期"].loc[tt.index >= 2018].mean()
print(f"    成熟期占比: 早期(<=2012) {early:.1f}% → 近期(>=2018) {late:.1f}%  "
      f"→ {'★ 通过' if late > early else '★ 未通过'}")

# ---------- 5. 标签稳定性（★ 我发现的核心问题）----------
print("\n[5] ★ 标签稳定性：逐年跳变率")
def flip_rate(s):
    s = s.dropna()
    return (s.values[1:] != s.values[:-1]).mean() if len(s) > 1 else np.nan

for tag, kw in [("原始CFI", dict(use="cfi")), ("CFI_core", dict(use="cfi_core"))]:
    y = L.classify(d, **kw).sort_values(["ts_code", "year"])
    fl = y.groupby("ts_code").stage.apply(flip_rate)
    print(f"    {tag:10s} 平均跳变率 {fl.mean():.3f}")

ys = L.smooth(L.classify(d, use="cfi_core"), win=3).sort_values(["ts_code", "year"])
fl2 = ys.groupby("ts_code").stage_s.apply(flip_rate)
print(f"    {'3年平滑':10s} 平均跳变率 {fl2.mean():.3f}  "
      f"(降幅 {(1-fl2.mean()/fl.mean())*100:.0f}%)")
print("    ★ 含义：单年现金流符号噪声极大，直接用单年标签会让组合频繁换手")

# ---------- 6. CFI_core 是否真的改变结论 ----------
print("\n[6] CFI_core 相对原始 CFI 的影响（方法论增量是否成立）")
a = L.classify(d, use="cfi").stage
b = L.classify(d, use="cfi_core").stage
both = a.notna() & b.notna()
print(f"    可比样本 {both.sum()} 个公司-年, 改判 {(a[both] != b[both]).sum()} 个 "
      f"({(a[both] != b[both]).mean():.3f})")
xt = pd.crosstab(a[both], b[both])
print(xt.to_string())

# ---------- 7. 财务业污染检查 ----------
print("\n[7] 金融股识别（工行/招行等 CFI 恒正，应集中于整合期）")
fin = d[d.name.str.contains("银行|证券|保险|信托", na=False)]
if len(fin):
    f = L.classify(fin, use="cfi_core")
    print(f"    金融股 {fin.ts_code.nunique()} 只, 阶段分布 "
          f"{f.stage.value_counts(normalize=True).mul(100).round(1).to_dict()}")
nonf = d[~d.name.str.contains("银行|证券|保险|信托", na=False)]
f2 = L.classify(nonf, use="cfi_core")
print(f"    非金融股阶段分布 {f2.stage.value_counts(normalize=True).mul(100).round(1).to_dict()}")
