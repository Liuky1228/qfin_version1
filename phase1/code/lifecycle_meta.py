#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公司名与上市日期（交易所官方列表，带本地缓存）。"""
import os, sys
import pandas as pd
import akshare as ak

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)                       # phase1/
CACHE = os.path.join(P1, "data_raw", "meta_list_date.csv")


def _build():
    sh = ak.stock_info_sh_name_code()[["证券代码", "证券简称", "上市日期"]]
    sh["bare"] = sh["证券代码"].astype(str).str.zfill(6)
    sh["name"] = sh["证券简称"]
    sh["上市日期"] = pd.to_datetime(sh["上市日期"], errors="coerce")

    sz = ak.stock_info_sz_name_code()[["A股代码", "A股简称", "A股上市日期"]]
    sz["bare"] = sz["A股代码"].astype(str).str.zfill(6)
    sz["name"] = sz["A股简称"]
    sz["上市日期"] = pd.to_datetime(sz["A股上市日期"], errors="coerce")

    m = pd.concat([sh[["bare", "name", "上市日期"]], sz[["bare", "name", "上市日期"]]])
    m = m.dropna(subset=["上市日期"]).drop_duplicates("bare", keep="first")
    m.to_csv(CACHE, index=False)
    return m


def load():
    if os.path.exists(CACHE):
        return pd.read_csv(CACHE, dtype={"bare": str}, parse_dates=["上市日期"])
    return _build()


def bare(ts_code):
    return ts_code[-6:]


def name_map():
    m = load()
    return dict(zip(m["bare"], m["name"]))


def list_year_map():
    m = load()
    return dict(zip(m["bare"], m["上市日期"].dt.year))


if __name__ == "__main__":
    m = load()
    print("上市日期记录:", len(m), " 覆盖", m["上市日期"].dt.year.min(), "-",
          m["上市日期"].dt.year.max())
