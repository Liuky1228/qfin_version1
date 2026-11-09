#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务 3：行业分类 + 分板块检验
目的：
  (a) 用「独立于现金流数据」的第三方信息交叉验证分类有效性
  (b) 检验国泰海通的可证伪预期：主板成熟期占比最高 / 创业板成长为主 / 科创板导入为主
  (c) 诊断整合期年龄偏高是否由行业构成（周期性行业）造成
"""
import sys, os, time, json
HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)                       # phase1/
RAW = os.path.join(P1, "data_raw")
DER = os.path.join(P1, "data_derived")
sys.path.insert(0, HERE)
import pandas as pd, numpy as np
import akshare as ak
import lifecycle as L
import lifecycle_meta as M

CN = L.STAGE_CN
IND_FILE = os.path.join(RAW, "industry_map.csv")


def board_of(bare):
    b = str(bare)
    if b.startswith("60"):
        return "上交所主板"
    if b.startswith("68"):
        return "科创板"
    if b.startswith("00"):
        return "深交所主板" if b[2] in "0123" else "其他(00开头)"
    if b.startswith("30"):
        return "创业板"
    if b.startswith(("83", "87", "43", "92")):
        return "北交所"
    return "其他"


def get_industry_map():
    """申万一级行业。优先本地缓存。"""
    if os.path.exists(IND_FILE):
        m = pd.read_csv(IND_FILE, dtype={"bare": str})
        print(f"[本地] 行业表 {len(m)} 只")
        return dict(zip(m["bare"], m["industry"]))

    out = {}
    tries = [
        ("stock_industry_category_cninfo", "证监会行业"),
        ("stock_board_industry_name_em", "东财行业"),
    ]
    for fn, tag in tries:
        try:
            f = getattr(ak, fn)
            print(f"尝试 {fn} ({tag}) ...", flush=True)
            df = f() if fn == "stock_industry_category_cninfo" else f()
            print(f"  返回 {df.shape} 列={list(df.columns)[:6]}", flush=True)
            break
        except Exception as e:
            print(f"  失败 {type(e).__name__}", flush=True)
    return out


def board_industry_from_sw():
    """行业映射（优先证监会，失败则回退申万指数成分）"""
    res = {}
    # 1) 证监会行业（按股票维度，最稳健，一次性）
    try:
        df = ak.stock_industry_category_cninfo()
        c_code = [c for c in df.columns if "代码" in c][0]
        c_ind  = [c for c in df.columns if "行业" in c][0]
        for code, ind in zip(df[c_code].astype(str).str.zfill(6), df[c_ind]):
            res[code] = ind
        print(f"[cninfo] 行业覆盖 {len(res)} 只")
        if len(res) > 2000:
            return res
    except Exception as e:
        print(f"cninfo 失败 {type(e).__name__}", flush=True)

    # 2) 申万一级指数成分（回退）
    try:
        levels = ak.sw_index_first_info()
        # 行业代码形如 '801010.SI'，接口需要 '801010' 前缀
        codes = dict(zip(levels["行业代码"].astype(str).str[:6], levels["行业名称"]))
    except Exception as e:
        print(f"申万一级失败 {type(e).__name__}", flush=True)
        return res

    for i, (sw_code, sw_name) in enumerate(codes.items(), 1):
        try:
            cons = ak.index_component_sw(symbol=sw_code)
            if cons is None or len(cons) == 0:
                continue
            col = next((c for c in cons.columns if "代码" in c), cons.columns[1])
            for code in cons[col].astype(str).str.zfill(6):
                res[code] = sw_name
        except Exception:
            time.sleep(0.3)
        if i % 10 == 0:
            print(f"  {i}/{len(codes)} 个行业, 已覆盖 {len(res)} 只", flush=True)
    print(f"[SW] 行业覆盖 {len(res)} 只")
    return res


def main():
    panel = pd.read_csv(os.path.join(DER, "panel_raw.csv"))
    dl = pd.read_csv(os.path.join(DER, "panel_delisted.csv"))
    panel = pd.concat([panel, dl], ignore_index=True)
    panel["bare"] = panel["ts_code"].str[-6:]
    panel = panel.drop_duplicates(["ts_code", "year"])

    # 年龄：在市用交易所上市年；退市用「财报数据起始年」代理
    panel["list_year"] = panel["bare"].map(M.list_year_map())
    first_data = panel.groupby("bare").year.min()
    panel["list_year"] = panel["list_year"].fillna(panel["bare"].map(first_data))
    panel["age"] = panel["year"] - panel["list_year"]
    panel["age_src"] = np.where(panel["bare"].map(M.list_year_map()).notna(),
                                "交易所上市日", "财报起始年(代理)")
    print(f"年龄有效 {panel.age.notna().mean():.3f}  "
          f"(交易所口径 {(panel.age_src=='交易所上市日').mean():.1%}, "
          f"代理口径 {(panel.age_src!='交易所上市日').mean():.1%})")

    d = L.add_features(panel)
    d["board"] = d.bare.map(board_of)

    ind = board_industry_from_sw()
    if ind:
        pd.DataFrame({"bare": list(ind), "industry": list(ind.values())}).to_csv(IND_FILE, index=False)
        d["industry"] = d.bare.map(ind)
        print(f"行业匹配率 {d.industry.notna().mean():.3f}")
    else:
        d["industry"] = np.nan

    x = L.classify(d, use="cfi_core")
    v = x[x.stage.notna()].copy()

    print("\n" + "=" * 72)
    print("【3-A】★ 分板块阶段构成（国泰海通预期：主板成熟 / 创业板成长 / 科创板导入）")
    print("=" * 72)
    ct = pd.crosstab(v.board, v.stage, normalize="index").mul(100).round(1)
    ct = ct.reindex(columns=["import", "growth", "mature", "restruct"]).fillna(0)
    ct.columns = [CN[c] for c in ct.columns]
    ct.insert(0, "n", v.board.value_counts())
    print(ct.to_string())
    print("\n预期: 主板『成熟期』占比最高；创业板『成长期』为主；科创板『导入期』为主")
    for b in ["上交所主板", "深交所主板", "创业板", "科创板"]:
        if b in ct.index:
            top = ct.loc[b, [c for c in cn_cols(ct)]].idxmax()
            print(f"  {b:8s} 占比最高 = {top}")

    print("\n" + "=" * 72)
    print("【3-B】★ 行业阶段构成：整合期是否集中在周期性行业")
    print("=" * 72)
    if d.industry.notna().any():
        ci = pd.crosstab(v.industry, v.stage, normalize="index").mul(100).round(1)
        ci = ci.reindex(columns=["import", "growth", "mature", "restruct"]).fillna(0)
        ci.columns = [CN[c] for c in ci.columns]
        ci["n"] = v.industry.value_counts()
        print("★ 整合期占比最高的 12 个行业:")
        print(ci.sort_values("整合期", ascending=False).head(12).to_string())
        print("\n★ 成熟期占比最高的 8 个行业:")
        print(ci.sort_values("成熟期", ascending=False).head(8)[["n", "成熟期"]].to_string())

        print("\n★ 各行业的整合期中位年龄 vs 全样本 %.0f 岁:" % v[v.stage=="restruct"].age.median())
        ra = v[v.stage == "restruct"].groupby("industry").age.median().sort_values(ascending=False)
        print(ra.head(8).to_string())

    print("\n" + "=" * 72)
    print("【3-C】年龄单调性（用修复后的年龄，含退市公司代理口径）")
    print("=" * 72)
    g = v.groupby("stage").age.median().reindex(["import", "growth", "mature", "restruct"])
    g.index = [CN[i] for i in g.index]
    print("  " + "  ".join(f"{i}={g[i]:.0f}岁" for i in g.index))
    print(f"  单调递增(导入<成长<成熟): {'✓' if g['导入期']<g['成长期']<g['成熟期'] else '✗'}")

    v.to_csv(os.path.join(DER, "industry_board_check.csv"), index=False)
    print("\n输出: industry_map.csv, industry_board_check.csv")


def cn_cols(ct):
    return [c for c in ct.columns if c != "n"]


if __name__ == "__main__":
    main()
