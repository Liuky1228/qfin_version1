#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
行业映射获取（多源回退，逐源单独存盘以便续跑）
免费接口普遍不稳定，故多源尝试 + 本地缓存。
"""
import os, time, sys
import pandas as pd
import akshare as ak

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "data_raw", "industry_map.csv")


def save(d):
    d = d.dropna(subset=["bare"]).drop_duplicates("bare")
    d.to_csv(OUT, index=False)
    print(f"  → 已保存 {len(d)} 只", flush=True)


def try_cninfo_cons():
    """巨潮按个股取行业：symbol=股票代码"""
    res = {}
    import lifecycle_meta as M
    codes = sorted(set(M.load()["bare"].astype(str).str.zfill(6)))
    print(f"cninfo 逐股: {len(codes)} 只", flush=True)
    for i, c in enumerate(codes, 1):
        try:
            d = ak.stock_industry_category_cninfo(symbol=c)
            if d is None or len(d) == 0:
                continue
            row = d[d["分级"] == 1]
            if len(row):
                res[c] = row["类目名称"].iloc[0]
        except Exception:
            pass
        if i % 300 == 0:
            print(f"    {i}/{len(codes)} 命中 {len(res)}", flush=True)
            save(pd.DataFrame({"bare": list(res), "industry": list(res.values())}))
        time.sleep(0.05)
    if res:
        save(pd.DataFrame({"bare": list(res), "industry": list(res.values())}))
    return res


def try_em_cons():
    """东财行业成分（按行业名逐个取）"""
    res = {}
    names = ak.stock_board_industry_name_ths()["name"].tolist()
    print(f"THS 行业 {len(names)} 个", flush=True)
    for i, n in enumerate(names, 1):
        for fn in ("stock_board_industry_cons_ths", "stock_board_industry_cons_em"):
            if not hasattr(ak, fn):
                continue
            try:
                d = getattr(ak, fn)(symbol=n)
                if d is None or len(d) == 0:
                    continue
                col = next((c for c in d.columns if "代码" in c), None)
                if not col:
                    continue
                for c in d[col].astype(str).str.zfill(6):
                    res[c] = n
                break
            except Exception:
                continue
        if i % 15 == 0:
            print(f"    {i}/{len(names)} 覆盖 {len(res)}", flush=True)
            save(pd.DataFrame({"bare": list(res), "industry": list(res.values())}))
    if res:
        save(pd.DataFrame({"bare": list(res), "industry": list(res.values())}))
    return res


if __name__ == "__main__":
    cur = pd.DataFrame(columns=["bare", "industry"])
    if os.path.exists(OUT):
        cur = pd.read_csv(OUT, dtype={"bare": str})
        print(f"已有 {len(cur)} 只")
    if len(cur) >= 3000:
        print("覆盖已足够，跳过")
        sys.exit(0)
    try:
        try_cninfo_cons()
    except Exception as e:
        print(f"cninfo 整体失败 {type(e).__name__}", flush=True)
    if len(pd.read_csv(OUT, dtype={"bare": str})) < 3000 if os.path.exists(OUT) else True:
        try:
            try_em_cons()
        except Exception as e:
            print(f"em/ths 整体失败 {type(e).__name__}", flush=True)
    print("完成")
