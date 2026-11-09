#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSMAR(国泰安)  ->  本项目面板 schema 的映射/清洗脚本

输入：CSMAR「中国上市公司财务报表数据库」导出的三张表（可放在任意子目录）
      FS_Combas  资产负债表
      FS_Comins  利润表
      FS_Comscfd 现金流量表(直接法)   ← 只有它有"投资支付的现金"等明细行
输出：phase1/data_derived/panel_csmar.csv（字段与 akshare 版 panel_full.csv 一致）

处理逻辑：
  - 只保留【合并报表 Typrep=A】、【年报 Accper=..-12-31】
  - 按 (Stkcd, year) 去重（keep=last）
  - 字段代码 → 项目字段（代码来自 CSMAR 官方字段说明文件）
用法：
  python3 csmar_map.py --dir ../data_raw/csmar
  python3 csmar_map.py --inspect            # 只打印找到的文件与列名
"""
import os
import glob
import argparse
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)
OUT = os.path.join(P1, "data_derived", "panel_csmar.csv")

# ---------------- 字段映射（代码来自 CSMAR 官方 [DES] 说明文件）-----------------
CF_MAP = {                                     # FS_Comscfd 现金流量表(直接法)
    "cfo":         ["C001000000"],             # 经营活动产生的现金流量净额
    "cfi":         ["C002000000"],             # 投资活动产生的现金流量净额
    "cff":         ["C003000000"],             # 筹资活动产生的现金流量净额
    "cfin_invest": ["C002007000"],             # 投资支付的现金
    "cfin_recov":  ["C002001000"],             # 收回投资收到的现金
    "cfin_income": ["C002002000"],             # 取得投资收益收到的现金
    "capex":       ["C002006000"],             # 购建固定资产、无形资产和其他长期资产支付的现金
}
BS_MAP = {                                     # FS_Combas 资产负债表
    "ta":         ["A001000000"],              # 资产总计
    "re":         ["A003105000"],              # 未分配利润
    "eq":         ["A003000000"],              # 所有者权益合计
    "eq2":        ["A003100000"],              # 归属于母公司所有者权益合计
    "cur_assets": ["A001100000"],              # 流动资产合计
    "cur_liab":   ["A002100000"],              # 流动负债合计
}
IS_MAP = {                                     # FS_Comins 利润表
    "revenue":  ["B001100000", "B001101000"],  # 营业总收入(优先) / 营业收入
    "n_income": ["B002000101"],                # 归属于母公司所有者的净利润
}

CODE_COL = "Stkcd"
DATE_COL = "Accper"
TYPE_COL = "Typrep"
NAME_COL = "ShortName"

# 各表文件名前缀（CSMAR 固定）
TABLES = {"BS": "FS_Combas", "IS": "FS_Comins", "CF": "FS_Comscfd"}


def read_any(path):
    if path.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(path, dtype=str)
    else:
        last = None
        for enc in ("utf-8-sig", "gbk", "utf-8"):
            try:
                df = pd.read_csv(path, dtype=str, encoding=enc)
                break
            except Exception as e:
                last = e
        else:
            raise RuntimeError(f"读取失败：{path}（{last}）")
    # 清理列名里可能残留的 BOM/空白（GBK 误读 UTF-8-BOM 会污染首列名）
    df.columns = [str(c).replace("\ufeff", "").strip() for c in df.columns]
    return df


def find_tables(dirpath, prefix):
    """递归找文件名以 prefix 开头的所有数据文件（排除说明/版权）。
    返回全部命中：支持按年份分段下载的多个分片，后续自动合并去重。"""
    hits = []
    for p in glob.glob(os.path.join(dirpath, "**", "*"), recursive=True):
        base = os.path.basename(p).upper()
        if not base.startswith(prefix.upper()):
            continue
        if p.endswith((".txt", ".pdf", ".zip")):
            continue
        if p.lower().endswith((".csv", ".xlsx", ".xls")):
            hits.append(p)
    if not hits:
        raise FileNotFoundError(f"找不到 {prefix}（在 {dirpath} 递归）")
    return sorted(hits)


def normalize(df):
    """过滤 合并报表 + 年报 + 去重；返回带 code/year 的标准 df。"""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    if CODE_COL not in df.columns:
        raise RuntimeError(f"缺少代码列 {CODE_COL}；现有列 {list(df.columns)}")
    df["code"] = df[CODE_COL].astype(str).str.strip().str.zfill(6)
    df["accper"] = df[DATE_COL].astype(str).str.strip()
    # 只保留年报 12-31（同时自动丢掉 xlsx 顶部的中文名/单位说明行）
    df = df[df["accper"].str.match(r"^\d{4}-12-31$")].copy()
    df["year"] = df["accper"].str[:4].astype(int)
    if TYPE_COL in df.columns:
        df = df[df[TYPE_COL].astype(str).str.strip().str.upper() == "A"].copy()
    df = df.sort_values(["code", "year"]).drop_duplicates(["code", "year"], keep="last")
    return df


def map_fields(df, mapping, table):
    out = {}
    missing = []
    for target, cands in mapping.items():
        col = next((c for c in cands if c in df.columns), None)
        if col is None:
            missing.append(target)
            out[target] = np.nan
        else:
            out[target] = pd.to_numeric(
                df[col].astype(str).str.replace(",", ""), errors="coerce")
    if missing:
        print(f"  ! [{table}] 缺字段 {missing}（现有列示例 {list(df.columns)[:8]}）")
    return pd.DataFrame(out, index=df.index)


def build_one(dirpath, table_key, mapping):
    paths = find_tables(dirpath, TABLES[table_key])
    print(f"  {table_key}: {len(paths)} 个文件")
    for p in paths:
        print(f"        {os.path.relpath(p, dirpath)}")
    # 多分片（按年份分段/重复下载）→ 纵向合并后统一清洗去重（keep=last）
    raw = pd.concat([read_any(p) for p in paths], ignore_index=True)
    raw = normalize(raw)
    d = map_fields(raw, mapping, table_key)
    d["bare"] = raw["code"].values
    d["year"] = raw["year"].values
    if NAME_COL in raw.columns:
        d["name"] = raw[NAME_COL].values
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=os.path.join(P1, "data_raw", "csmar"))
    ap.add_argument("--inspect", action="store_true")
    args = ap.parse_args()

    if args.inspect:
        for k, pre in TABLES.items():
            try:
                paths = find_tables(args.dir, pre)
                print(f"\n=== {k}: {len(paths)} 个文件 ===")
                for p in paths:
                    d = read_any(p)
                    print(f"  - {os.path.relpath(p, args.dir)}  行{len(d)}")
                    print(f"    列: {list(d.columns)}")
            except Exception as e:
                print(f"\n=== {k} 未找到: {e}")
        return

    print("读取 CSMAR 三表：")
    bs = build_one(args.dir, "BS", BS_MAP)
    isf = build_one(args.dir, "IS", IS_MAP)
    cf = build_one(args.dir, "CF", CF_MAP)
    for tag, d in (("BS", bs), ("IS", isf), ("CF", cf)):
        print(f"    {tag}: {len(d)} 行 / {d.bare.nunique()} 家")

    def drop_name(d):
        return d.drop(columns=["name"]) if "name" in d.columns else d

    panel = drop_name(cf).merge(drop_name(bs), on=["bare", "year"], how="outer")
    panel = panel.merge(drop_name(isf), on=["bare", "year"], how="outer")

    # name 单独取（优先级 BS > IS > CF），按 bare 唯一，避免多表 name 冲突
    name_tbl = next((d[["bare", "name"]].dropna(subset=["name"]).drop_duplicates("bare")
                     for d in (bs, isf, cf) if "name" in d.columns), None)
    if name_tbl is not None:
        panel = panel.merge(name_tbl, on="bare", how="left")

    panel["ts_code"] = panel["bare"]
    panel["name"] = panel.get("name", panel["bare"]).fillna(panel["bare"])
    panel["src"] = "csmar"
    cols = ["year", "cfo", "cfi", "cff", "cfin_invest", "cfin_recov", "cfin_income",
            "capex", "ta", "re", "revenue", "ts_code", "bare", "name", "src",
            "eq", "eq2", "cur_assets", "cur_liab", "n_income"]
    cols = [c for c in cols if c in panel.columns]
    panel = panel[cols].sort_values(["bare", "year"]).reset_index(drop=True)
    panel.to_csv(OUT, index=False)

    print(f"\n输出 → {OUT}")
    print(f"  {panel.shape}  |  {panel.bare.nunique()} 家  |  "
          f"{int(panel.year.min())}-{int(panel.year.max())}")
    print("  各字段非空率：")
    for c in ["cfo", "cfi", "cff", "cfin_invest", "cfin_recov", "cfin_income",
              "capex", "ta", "re", "revenue"]:
        if c in panel:
            print(f"    {c:12s} {panel[c].notna().mean():.1%}")


if __name__ == "__main__":
    main()
