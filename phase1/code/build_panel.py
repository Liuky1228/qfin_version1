#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从本地缓存构建面板 → 分类 → 有效性验证。"""
import sys, os, glob, re
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pandas as pd, numpy as np
import lifecycle as L

CACHE = os.path.expanduser("~/life_cache")
P1 = os.path.dirname(HERE)                       # phase1/
OUT = os.path.join(P1, "data_derived", "panel_raw.csv")


def codes_from_cache():
    seen = {}
    for f in glob.glob(f"{CACHE}/*_现金流量表.csv"):
        m = re.match(r"(.+)_现金流量表\.csv$", os.path.basename(f))
        if m:
            code = m.group(1)
            if not os.path.exists(f"{CACHE}/{code}_资产负债表.csv"):
                continue
            seen[code] = code
    return sorted(seen.keys())


if __name__ == "__main__":
    codes = codes_from_cache()
    print("缓存可用公司数:", len(codes))
    p = L.build_panel([(c, c) for c in codes])
    p.to_csv(OUT, index=False)
    print("面板:", p.shape, "公司数:", p.ts_code.nunique())
