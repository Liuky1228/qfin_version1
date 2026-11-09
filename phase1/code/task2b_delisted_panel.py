#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务 2b：退市公司数据补全
问题：panel 只含「当前在市」公司（从 a_code_name.csv 抽样），退市公司一只都没有，
      结构上无法检验退市偏差。
解法：交易所官方退市名单（上交所 stock_info_sh_delist + 深交所 stock_info_sz_delist）
      → 抓取退市公司财报 → 单独分析。
"""
import sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)                       # phase1/
RAW = os.path.join(P1, "data_raw")
DER = os.path.join(P1, "data_derived")
sys.path.insert(0, HERE)
import pandas as pd, numpy as np
import akshare as ak
import lifecycle as L
import lifecycle_meta as M

CACHE = os.path.expanduser("~/life_cache_delisted")
os.makedirs(CACHE, exist_ok=True)
CN = L.STAGE_CN


def _retry(fn, need_cols, tries=5):
    """接口偶发返回空表/列名不符 → 重试"""
    for k in range(tries):
        try:
            d = fn()
            if d is not None and len(d) > 0 and all(c in d.columns for c in need_cols):
                return d
            print(f"    第{k+1}次返回异常 (shape={getattr(d,'shape',None)}), 重试", flush=True)
        except Exception as e:
            print(f"    第{k+1}次异常 {type(e).__name__}, 重试", flush=True)
        time.sleep(2 + 2 * k)
    raise RuntimeError(f"接口多次失败: {need_cols}")


def get_delist_universe():
    """优先读本地缓存（交易所接口在长时间抓取后会被限流超时）"""
    local = os.path.join(RAW, "delist_universe.csv")
    if os.path.exists(local):
        m = pd.read_csv(local, dtype={"bare": str}, parse_dates=["delist_date"])
        print(f"[本地缓存] 退市名单 {len(m)} 只 ({m.delist_year.min()}-{m.delist_year.max()})")
        return m
    sh = _retry(ak.stock_info_sh_delist, ["公司代码", "公司简称", "暂停上市日期"])
    sh = sh[["公司代码", "公司简称", "上市日期", "暂停上市日期"]]
    sh["bare"] = sh["公司代码"].astype(str).str.zfill(6)
    sh["name"] = sh["公司简称"]
    sh["delist_date"] = pd.to_datetime(sh["暂停上市日期"], errors="coerce")
    sh["market"] = "SH"

    sz = _retry(ak.stock_info_sz_delist, ["证券代码", "证券简称", "终止上市日期"])
    sz = sz[["证券代码", "证券简称", "上市日期", "终止上市日期"]]
    sz["bare"] = sz["证券代码"].astype(str).str.zfill(6)
    sz["name"] = sz["证券简称"]
    sz["delist_date"] = pd.to_datetime(sz["终止上市日期"], errors="coerce")
    sz["market"] = "SZ"

    m = pd.concat([sh[["bare", "name", "delist_date", "market"]],
                   sz[["bare", "name", "delist_date", "market"]]], ignore_index=True)
    m = m.dropna(subset=["delist_date"]).drop_duplicates("bare", keep="first")
    m["ts_code"] = np.where(m.market == "SH", "sh", "sz") + m.bare
    m["delist_year"] = m.delist_date.dt.year
    return m.reset_index(drop=True)


def fetch_delisted(todo):
    """新浪接口对退市公司用 delisted 前缀"""
    ok = 0
    for i, (code, bare) in enumerate(todo, 1):
        for symbol in ("现金流量表", "资产负债表", "利润表"):
            f = f"{CACHE}/{code}_{symbol}.csv"
            if os.path.exists(f):
                continue
            got = False
            for key in (f"delisted{code}", code):
                try:
                    df = ak.stock_financial_report_sina(stock=key, symbol=symbol)
                    if df is not None and len(df) > 0:
                        df.to_csv(f, index=False)
                        got = True
                        break
                except Exception:
                    time.sleep(0.3)
            time.sleep(0.15)
        ok += 1
        if ok % 20 == 0:
            print(f"  退市公司 {ok}/{len(todo)}", flush=True)
    return ok


def main():
    uni = get_delist_universe()
    uni.to_csv(os.path.join(RAW, "delist_universe.csv"), index=False)
    print(f"退市名单: {len(uni)} 只 (上交所 {sum(uni.market=='SH')} + 深交所 {sum(uni.market=='SZ')})")
    print(f"退市年份: {uni.delist_year.min()} - {uni.delist_year.max()}")
    print(uni.delist_year.value_counts().sort_index().tail(12).to_string())

    todo = [(r.ts_code, r.bare) for r in uni.itertuples()]
    print(f"\n开始抓取退市公司财报 {len(todo)} 只 ...")
    fetch_delisted(todo)
    n = len([f for f in os.listdir(CACHE) if f.endswith("_现金流量表.csv")])
    print(f"退市公司缓存: {n} 只")

    # 单独建面板
    rows = []
    for code, bare in todo:
        try:
            cf = L.fetch_cf(code) if os.path.exists(f"{CACHE}/{code}_现金流量表.csv") else None
        except Exception:
            cf = None
        if cf is None:
            continue
        try:
            bs = pd.read_csv(f"{CACHE}/{code}_资产负债表.csv", parse_dates=["报告日"])
            bs["报告日"] = pd.to_datetime(bs["报告日"])
        except Exception:
            continue
        cfa = cf[cf["报告日"].dt.month == 12].copy(); cfa["year"] = cfa["报告日"].dt.year
        bsa = bs[bs["报告日"].dt.month == 12].copy(); bsa["year"] = bsa["报告日"].dt.year
        if len(cfa) == 0 or len(bsa) == 0:
            continue
        cfa = cfa.drop_duplicates("year", keep="first").reset_index(drop=True)
        bsa = bsa.drop_duplicates("year", keep="first").reset_index(drop=True)
        cf_map, miss = {}, []
        for k, cands in L.CF_COLS.items():
            c = L.first_col(cfa, cands)
            if c: cf_map[k] = L.num(cfa[c])
            elif k in ("cfo", "cfi", "cff"): miss.append(k)
        if miss: continue
        dd = pd.DataFrame({"year": cfa["year"].values})
        for k, v in cf_map.items(): dd[k] = np.asarray(v)
        for k in ["cfin_invest", "cfin_recov", "cfin_income"]:
            if k not in cf_map: dd[k] = np.nan
        for k, cands in L.BS_COLS.items():
            c = L.first_col(bsa, cands)
            if c: dd[k] = dd["year"].map(dict(zip(bsa["year"].values, L.num(bsa[c]).values)))
        dd["ts_code"] = code; dd["bare"] = bare
        dd["name"] = uni.set_index("bare").loc[bare, "name"] if bare in set(uni.bare) else bare
        dd["delist_year"] = uni.set_index("bare").loc[bare, "delist_year"] if bare in set(uni.bare) else np.nan
        rows.append(dd)

    p = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if len(p) == 0:
        print("★ 退市公司财报无法从新浪取得 —— 该问题在此数据源下无法解决")
        return
    p.to_csv(os.path.join(DER, "panel_delisted.csv"), index=False)
    print(f"\n退市公司面板: {p.shape}, 公司 {p.bare.nunique()} 只, 年份 {p.year.min()}-{p.year.max()}")
    print(p.groupby("bare").size().describe().round(1).to_string())


if __name__ == "__main__":
    main()
