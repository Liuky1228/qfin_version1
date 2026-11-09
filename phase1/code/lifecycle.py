#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股生命周期分类（Dickinson 现金流符号法 A 股改良版）
数据源：新浪财经现金流量表（免费、无需 token），回溯至 2000 年
"""
import akshare as ak
import pandas as pd
import numpy as np
import time, os, sys, json

CF_COLS = {
    "cfo": ["经营活动产生的现金流量净额"],
    "cfi": ["投资活动产生的现金流量净额"],
    "cff": ["筹资活动产生的现金流量净额"],
    "cfin_invest": ["投资支付的现金", "投资所支付的现金"],
    "cfin_recov": ["收回投资收到的现金", "收回投资所收到的现金"],
    "cfin_income": ["取得投资收益收到的现金", "取得投资收益所收到的现金"],
    "capex": ["购建固定资产、无形资产和其他长期资产支付的现金",
              "购建固定资产、无形资产和其他长期资产所支付的现金"],
}
BS_COLS = {
    "ta": ["资产总计"],
    "eq": ["股东权益合计", "所有者权益合计"],
    "eq2": ["归属于母公司股东权益合计", "归属于母公司所有者权益合计"],
    "re": ["未分配利润", "未分配利润(或亏损)"],
    "cur_assets": ["流动资产合计"],
    "cur_liab": ["流动负债合计"],
}
REV_COLS = ["营业总收入", "营业收入", "其中：营业收入"]

CACHE = os.path.expanduser("~/life_cache")
os.makedirs(CACHE, exist_ok=True)


# ---------------- 取数（带磁盘缓存） ----------------
def fetch(code, symbol):
    """code=sh600000, symbol=现金流量表|资产负债表|利润表"""
    f = f"{CACHE}/{code}_{symbol}.csv"
    if os.path.exists(f):
        return pd.read_csv(f, parse_dates=["报告日"])
    df = ak.stock_financial_report_sina(stock=code, symbol=symbol)
    df.to_csv(f, index=False)
    return df


def fetch_bs(code):
    df = fetch(code, "资产负债表")
    df["报告日"] = pd.to_datetime(df["报告日"])
    return df.sort_values("报告日")


def fetch_cf(code):
    df = fetch(code, "现金流量表")
    df["报告日"] = pd.to_datetime(df["报告日"])
    return df.sort_values("报告日")


def fetch_is(code):
    df = fetch(code, "利润表")
    df["报告日"] = pd.to_datetime(df["报告日"])
    return df.sort_values("报告日")


def first_col(df, candidates):
    """新浪表列名随年份变动，取第一个存在的"""
    for c in candidates:
        if c in df.columns:
            return c
    return None


def num(s):
    return pd.to_numeric(s, errors="coerce")


# ---------------- 构造分类所需面板 ----------------
def build_panel(codes):
    """codes: list of (ts_code, name)。返回逐年面板。"""
    rows = []
    for i, (code, name) in enumerate(codes):
        try:
            cf = fetch_cf(code)
            bs = fetch_bs(code)
        except Exception as e:
            print(f"  [{i+1}/{len(codes)}] {code} {name} 取数失败 {type(e).__name__}", flush=True)
            continue

        # --- 只取年报 (12-31)，已是全年累计口径 ---
        cfa = cf[cf["报告日"].dt.month == 12].copy()
        bsa = bs[bs["报告日"].dt.month == 12].copy()
        if len(cfa) == 0 or len(bsa) == 0:
            continue

        cfa["year"] = cfa["报告日"].dt.year
        bsa["year"] = bsa["报告日"].dt.year

        cfa = cfa.drop_duplicates("year", keep="first").reset_index(drop=True)
        bsa = bsa.drop_duplicates("year", keep="first").reset_index(drop=True)

        # CF 列名逐股不同，逐科目解析；关键三科目缺一则放弃该公司
        cf_map, miss = {}, []
        for k, cands in CF_COLS.items():
            c = first_col(cfa, cands)
            if c:
                cf_map[k] = num(cfa[c])
            elif k in ("cfo", "cfi", "cff"):
                miss.append(k)
        if miss:
            print(f"  [{code}] 缺关键科目 {miss}，跳过", flush=True)
            continue

        d = pd.DataFrame({"year": cfa["year"].values})
        for k, v in cf_map.items():
            d[k] = np.asarray(v)
        # 剔除项缺失 → 保留 NaN，后面判定是否可用
        for k in ["cfin_invest", "cfin_recov", "cfin_income"]:
            if k not in cf_map:
                d[k] = np.nan

        bs_map = {}
        for k, cands in BS_COLS.items():
            c = first_col(bsa, cands)
            if c:
                bs_map[k] = dict(zip(bsa["year"].values, num(bsa[c]).values))
        for k, mp in bs_map.items():
            d[k] = d["year"].map(mp)

        # 营收
        try:
            isd = fetch_is(code)
            isa = isd[isd["报告日"].dt.month == 12].copy()
            isa["year"] = isa["报告日"].dt.year
            isa = isa.drop_duplicates("year", keep="first")
            rc = first_col(isa, REV_COLS)
            if rc:
                d["revenue"] = d["year"].map(
                    dict(zip(isa["year"].values, num(isa[rc]).values)))
            else:
                d["revenue"] = np.nan
        except Exception as e:
            print(f"  [{code}] 利润表解析失败 {type(e).__name__}: {e}", flush=True)
            d["revenue"] = np.nan

        d["ts_code"] = code
        d["name"] = name
        rows.append(d)
        print(f"  [{i+1}/{len(codes)}] {code} {name} 年报 {len(d)} 期 "
              f"({d.year.min()}-{d.year.max()})", flush=True)
        time.sleep(0.25)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


# ---------------- 分类核心 ----------------
def add_features(panel):
    d = panel.copy().sort_values(["ts_code", "year"])
    d["ta"] = d["ta"].where(d["ta"] > 0)

    # 缩放
    for k in ["cfo", "cfi", "cff", "capex", "re"]:
        d[k + "_s"] = d[k] / d["ta"]
    # ★ capex 在新浪表中是「正值量纲」的现金流出，统一转为负号口径
    d["capex_s_neg"] = -d["capex_s"]

    # 核心投资现金流：剔除买理财/赎理财/收利息
    #   CFI 已是净额；买入是流出(使CFI偏低)→加回；赎回/收益是流入(使CFI偏高)→减掉
    d["cfi_core"] = d["cfi"] + d["cfin_invest"] - d["cfin_recov"] - d["cfin_income"]
    d["cfi_core_s"] = d["cfi_core"] / d["ta"]

    # 营收增长（用上一年，需 shift）
    d = d.sort_values(["ts_code", "year"])
    d["rev_growth"] = d.groupby("ts_code")["revenue"].pct_change()

    # 速动比率、杠杆（验证用）
    d["quick_ratio"] = d["cur_assets"] / d["cur_liab"].replace(0, np.nan)
    eqcol = None
    for cand in ("eq2", "eq"):
        if cand in d.columns:
            eqcol = cand
            break
    d["lev"] = d["ta"] / d[eqcol] if eqcol else np.nan

    return d


def classify(d, use="cfi_core", zero_neg=False):
    """Dickinson 符号法。use: 'cfi_core' | 'cfi' | 'capex'
    zero_neg=True 时 0 归负侧。返回带 stage / valid 的副本。

    ★ 关键：任一必需变量缺失 → stage=NaN（不可分类），绝不静默落到 else 分支。
    """
    d = d.copy()
    sgn = lambda s: (s <= 0) if zero_neg else (s < 0)
    inv_col = "capex_s_neg" if use == "capex" else (use + "_s")
    inv = d[inv_col]

    need = ["cfo_s", "cff_s", inv_col]
    valid = d["ta"].notna() & (d["ta"] > 0)
    for c in need:
        valid &= d[c].notna()

    stage = pd.Series(pd.NA, index=d.index, dtype="object")
    neg_i = sgn(inv)              # 投资现金流为负 = 真实投资扩张
    pos_o = ~sgn(d["cfo_s"])       # 经营现金流为正 = 自身造血
    pos_f = ~sgn(d["cff_s"])       # 筹资现金流为正 = 外部融资

    # ★ Dickinson (2011) Table 1 原始映射
    stage[neg_i & ~pos_o & pos_f] = "import"    # CFO<0, CFI<0, CFF>0 → 导入期
    stage[neg_i & pos_o & pos_f] = "growth"     # CFO>0, CFI<0, CFF>0 → 成长期
    stage[neg_i & pos_o & ~pos_f] = "mature"    # CFO>0, CFI<0, CFF<0 → 成熟期
    stage[neg_i & ~pos_o & ~pos_f] = "restruct"  # CFO<0, CFI<0, CFF<0 → 摇摇欲坠(归整合)
    stage[~neg_i] = "restruct"                  # CFI>0 → 衰退/出售资产(归整合)

    stage[~valid] = pd.NA
    d["stage"] = stage
    d["valid"] = valid
    return d


def add_age_override(d, age):
    """age: DataFrame[ts_code, list_date] 或 Series。导入期 + 年龄>10 → 拆分"""
    d = d.copy()
    d["age"] = d["ts_code"].map(age) if isinstance(age, dict) else np.nan
    med_re = d["re_s"].median()
    over = (d["stage"] == "import") & (d["age"] > 10) & d["re_s"].notna()
    d.loc[over & (d["re_s"] > med_re), "stage"] = "restruct"
    d.loc[over & (d["re_s"] <= med_re), "stage"] = "growth"
    return d


def smooth(d, win=3, min_valid=2):
    """对分类做时间平滑：近 win 年多数票。
    动机：实测逐年跳变率 40%-59%，直接用单年标签噪声极大。"""
    out = []
    for _, g in d.groupby("ts_code", sort=False):
        g = g.sort_values("year")
        vals = g["stage"].tolist()
        sm = []
        for i in range(len(vals)):
            w = [v for v in vals[max(0, i - win + 1): i + 1] if isinstance(v, str)]
            if len(w) >= min_valid:
                sm.append(pd.Series(w).mode().iloc[0])
            else:
                sm.append(pd.NA)
        g = g.copy()
        g["stage_s"] = sm
        out.append(g)
    return pd.concat(out, ignore_index=True)


STAGE_CN = {"import": "导入期", "growth": "成长期", "mature": "成熟期", "restruct": "整合期"}


if __name__ == "__main__":
    print("此文件是模块。用 build_lifecycle.py 驱动。")
