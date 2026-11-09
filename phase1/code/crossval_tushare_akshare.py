#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小样本对照：Tushare Pro  vs  现有 akshare 面板（panel_full.csv）

目的：在换数据源之前，先验证同一个 (股票, 年报) 下，Tushare 的关键财务口径
      与已抓的 akshare 数据是否一致（口径/单位/报表类型是否对得上）。

token 读取顺序：环境变量 TUSHARE_TOKEN  ->  ~/.tushare_token
用法：  python3 crossval_tushare_akshare.py
输出：
  phase1/data_derived/crossval_tushare_detail.csv   逐行对照明细
  phase1/data_derived/crossval_tushare_summary.csv  逐字段汇总
"""
import os
import sys
import time
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)
PANEL = os.path.join(P1, "data_derived", "panel_full.csv")
OUT_DETAIL = os.path.join(P1, "data_derived", "crossval_tushare_detail.csv")
OUT_SUMMARY = os.path.join(P1, "data_derived", "crossval_tushare_summary.csv")

# 30 家非金融、跨市场跨年代的样本（含 1 家已退市，测早期年份）
SAMPLE_BARE = [
    "600519", "000651", "000333", "002415", "300750", "600276", "000858",
    "600887", "002594", "600028", "601857", "600585", "000002", "600048",
    "000063", "600050", "600009", "000039", "600019", "601088", "600900",
    "000100", "002304", "600690", "601899", "600309", "000725", "600031",
    "002027", "600001",
]

# akshare 面板列  ->  Tushare 字段
CF_MAP = {                       # pro.cashflow
    "cfo": "c_ncf_from_oa",
    "cfi": "c_ncf_from_invest",
    "cff": "c_ncf_from_finance",
    "cfin_invest": "c_paid_invest",
    "cfin_recov": "c_disp_withdrwl_invest",
    "cfin_income": "c_recp_return_invest",
    "capex": "c_pay_acq_const_fiolta",
}
BS_MAP = {                       # pro.balancesheet
    "ta": "total_assets",
    "re": "undistr_porfit",              # 注意官方拼写
    "eq2": "total_hldr_eqy_exc_min_int",
    "eq": "total_hldr_eqy_inc_min_int",
    "cur_assets": "total_cur_assets",
    "cur_liab": "total_cur_liab",
}
IS_MAP = {                       # pro.income
    "revenue": "total_revenue",
}


def get_token():
    tok = os.environ.get("TUSHARE_TOKEN", "").strip()
    if tok:
        return tok
    f = os.path.expanduser("~/.tushare_token")
    if os.path.exists(f):
        return open(f).read().strip()
    return None


def to_ts_code(bare):
    if bare.startswith(("60", "68", "9")):
        return f"{bare}.SH"
    if bare.startswith(("43", "83", "87", "88", "4", "8")):
        return f"{bare}.BJ"
    return f"{bare}.SZ"


def pull(pro, bare, start="19990101", end="20251231"):
    code = to_ts_code(bare)
    out = {"bare": bare}
    try:
        cf = pro.cashflow(ts_code=code, start_date=start, end_date=end)
        if cf is not None and len(cf):
            cf = cf[cf["report_type"] == "1"].copy()
            cf["year"] = cf["end_date"].str[:4].astype(int)
            cf = cf[cf["end_date"].str.endswith("1231")]
            cf = cf.drop_duplicates("year", keep="first")
            out["cf"] = cf
    except Exception as e:
        print(f"  [{code}] cashflow 失败 {type(e).__name__}: {e}")
    try:
        bs = pro.balancesheet(ts_code=code, start_date=start, end_date=end)
        if bs is not None and len(bs):
            bs = bs[bs["report_type"] == "1"].copy()
            bs["year"] = bs["end_date"].str[:4].astype(int)
            bs = bs[bs["end_date"].str.endswith("1231")]
            bs = bs.drop_duplicates("year", keep="first")
            out["bs"] = bs
    except Exception as e:
        print(f"  [{code}] balancesheet 失败 {type(e).__name__}: {e}")
    try:
        inc = pro.income(ts_code=code, start_date=start, end_date=end)
        if inc is not None and len(inc):
            inc = inc[inc["report_type"] == "1"].copy()
            inc["year"] = inc["end_date"].str[:4].astype(int)
            inc = inc[inc["end_date"].str.endswith("1231")]
            inc = inc.drop_duplicates("year", keep="first")
            out["is"] = inc
    except Exception as e:
        print(f"  [{code}] income 失败 {type(e).__name__}: {e}")
    return out


def build_ts_frame(pulled):
    """把 Tushare 三表拼成与面板同名的列。"""
    frames = []
    if "cf" in pulled:
        d = pd.DataFrame({"year": pulled["cf"]["year"].values})
        for k, fld in CF_MAP.items():
            d[k] = pd.to_numeric(pulled["cf"].get(fld), errors="coerce")
        frames.append(d)
    if "bs" in pulled:
        d = pd.DataFrame({"year": pulled["bs"]["year"].values})
        for k, fld in BS_MAP.items():
            d[k] = pd.to_numeric(pulled["bs"].get(fld), errors="coerce")
        frames.append(d)
    if "is" in pulled:
        d = pd.DataFrame({"year": pulled["is"]["year"].values})
        for k, fld in IS_MAP.items():
            d[k] = pd.to_numeric(pulled["is"].get(fld), errors="coerce")
        frames.append(d)
    if not frames:
        return pd.DataFrame()
    out = frames[0]
    for f in frames[1:]:
        out = out.merge(f, on="year", how="outer")
    out["bare"] = pulled["bare"]
    return out


def rel_diff(a, b):
    denom = np.maximum(np.abs(b), 1.0)      # 资产动辄上亿，用绝对值做下限
    return np.abs(a - b) / denom


def main():
    tok = get_token()
    if not tok:
        print("!! 未找到 Tushare token。请把 token 写到 ~/.tushare_token 或设 TUSHARE_TOKEN。")
        sys.exit(2)
    try:
        import tushare as ts
    except Exception as e:
        print(f"!! 未安装 tushare：{e}\n   pip3 install tushare")
        sys.exit(2)
    ts.set_token(tok)
    pro = ts.pro_api()

    panel = pd.read_csv(PANEL)
    if "bare" not in panel.columns:
        panel["bare"] = panel["ts_code"].astype(str).str[-6:]
    panel = panel[panel["bare"].isin(SAMPLE_BARE)].copy()
    print(f"面板样本命中：{panel.bare.nunique()} 家 / {len(panel)} 行")

    rows = []
    for i, bare in enumerate(SAMPLE_BARE, 1):
        pulled = pull(pro, bare)
        tsf = build_ts_frame(pulled)
        ak = panel[panel["bare"] == bare]
        # 本平台无该股数据（如已退市）时跳过
        print(f"  [{i}/{len(SAMPLE_BARE)}] {bare}: Tushare 年报 {len(tsf)} 期 / akshare {len(ak)} 期", flush=True)
        if len(tsf) == 0 or len(ak) == 0:
            continue
        m = ak.merge(tsf, on=["bare", "year"], suffixes=("_ak", "_ts"))
        cols = set(CF_MAP) | set(BS_MAP) | set(IS_MAP)
        for _, r in m.iterrows():
            rec = {"bare": bare, "year": int(r["year"])}
            for c in cols:
                a, b = r.get(f"{c}_ak"), r.get(f"{c}_ts")
                rec[f"{c}_akshare"] = a
                rec[f"{c}_tushare"] = b
                if pd.notna(a) and pd.notna(b):
                    rec[f"{c}_reldiff"] = rel_diff(a, b)
            rows.append(rec)
        time.sleep(0.15)

    det = pd.DataFrame(rows)
    if det.empty:
        print("!! 无对照结果");return
    det.to_csv(OUT_DETAIL, index=False)
    print(f"\n明细已写 {OUT_DETAIL}  ({len(det)} 行)")

    cols = list(CF_MAP) + list(BS_MAP) + list(IS_MAP)
    summ = []
    for c in cols:
        rd = det.get(f"{c}_reldiff", pd.Series(dtype=float)).dropna()
        pair = det[[f"{c}_akshare", f"{c}_tushare"]].dropna()
        corr = pair.corr().iloc[0, 1] if len(pair) > 2 else np.nan
        summ.append({
            "字段": c,
            "可比期数": len(rd),
            "相关系数": round(float(corr), 4) if pd.notna(corr) else None,
            "中位相对偏差": round(float(rd.median()), 6) if len(rd) else None,
            "最大相对偏差": round(float(rd.max()), 6) if len(rd) else None,
            "偏差<1%占比": round(float((rd < 0.01).mean()), 4) if len(rd) else None,
        })
    s = pd.DataFrame(summ)
    s.to_csv(OUT_SUMMARY, index=False)
    print(f"汇总已写 {OUT_SUMMARY}\n")
    print(s.to_string(index=False))


if __name__ == "__main__":
    main()
