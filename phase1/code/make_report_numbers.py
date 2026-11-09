#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成汇报所需的所有数字（统一主设定口径，避免各章节口径不一致）
主设定: CFI_core + override(年龄>10, RE中位数) + 3年平滑 + 剔除金融
样本: 在市690 + 退市360 = 1050 只
输出: report_numbers.json
"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)                       # phase1/
RAW = os.path.join(P1, "data_raw")
DER = os.path.join(P1, "data_derived")
NUMBERS = os.path.join(P1, "numbers")
sys.path.insert(0, HERE)
import pandas as pd, numpy as np
import lifecycle as L
import lifecycle_meta as M

CN = L.STAGE_CN
FIN_RE = "银行|保险|证券|信托|期货|租赁|理财|金融|资产管理|资本"
S = ["import", "growth", "mature", "restruct"]
R = {}
PANEL_MODE = "sample"
OUT_JSON = "report_numbers.json"


def board_of(x):
    """按证券代码前缀判定上市板块"""
    if x[:2] == "60":
        return "上交所主板"
    if x[:2] == "68":
        return "科创板"
    if x[:2] in ["30"]:
        return "创业板"
    if x[:2] == "00":
        return "深交所主板"
    if x[:2] == "20":
        return "深交所B股"
    if x[:2] in ["43", "83", "87", "88", "92"]:
        return "北交所"
    return "其他"


def _listed_codes():
    f = os.path.join(RAW, "a_code_name.csv")
    if not os.path.exists(f):
        return set()
    return set(pd.read_csv(f, dtype=str).iloc[:, 0].str.zfill(6))


def _enrich(p, inb):
    """补全 name / list_year / age / is_fin / delisted / board"""
    m = M.name_map()
    p["name"] = p["bare"].map(m).fillna(p["name"])
    p["list_year"] = p["bare"].map(M.list_year_map())
    p["age_src"] = np.where(p["bare"].map(M.list_year_map()).notna(), "交易所上市日", "财报起始年(代理)")
    p["list_year"] = p["list_year"].fillna(p["bare"].map(p.groupby("bare").year.min()))
    p["age"] = p["year"] - p["list_year"]
    p["is_fin"] = p["name"].astype(str).str.contains(FIN_RE, regex=True)
    p["delisted"] = ~p["bare"].isin(inb)
    p["board"] = p["bare"].map(board_of)
    return p


def load_panel():
    full = os.path.join(DER, "panel_full.csv")
    if os.path.exists(full) and PANEL_MODE == "full":
        p = pd.read_csv(full, dtype={"bare": str})
        p["bare"] = p["bare"].astype(str).str.zfill(6)
        return _enrich(p, _listed_codes())
    a = pd.read_csv(os.path.join(DER, "panel_raw.csv"))
    b = pd.read_csv(os.path.join(DER, "panel_delisted.csv"))
    a["bare"] = a["ts_code"].str[-6:]
    b["bare"] = b["ts_code"].str[-6:]
    inb = set(a["bare"])
    p = pd.concat([a, b], ignore_index=True).drop_duplicates(["ts_code", "year"])
    p["name"] = p["bare"].map(M.name_map()).fillna(p["bare"])
    p["list_year"] = p["bare"].map(M.list_year_map())
    p["age_src"] = np.where(p["bare"].map(M.list_year_map()).notna(), "交易所上市日", "财报起始年(代理)")
    p["list_year"] = p["list_year"].fillna(p["bare"].map(p.groupby("bare").year.min()))
    p["age"] = p["year"] - p["list_year"]
    p["is_fin"] = p["name"].astype(str).str.contains(FIN_RE, regex=True)
    p["delisted"] = ~p["bare"].isin(inb)
    p["board"] = p["bare"].map(board_of)
    return p


def classify_main(d, age_t=10, re_cut="median", win=3, use="cfi_core"):
    x = L.classify(d, use=use)
    if re_cut == "median":
        cut = x["re_s"].median()
    elif re_cut == "mean":
        cut = x["re_s"].mean()
    else:
        cut = x["re_s"].quantile(float(re_cut[1:]) / 100)
    over = (x.stage == "import") & (x.age > age_t) & x.re_s.notna()
    x.loc[over & (x.re_s > cut), "stage"] = "restruct"
    x.loc[over & (x.re_s <= cut), "stage"] = "growth"
    raw = x.stage.copy()
    xs = L.smooth(x, win=win)
    xs["stage_raw"] = raw.values
    xs["stage"] = xs["stage_s"].where(xs["stage_s"].astype(str).isin(S))
    return xs


def jump_rate(d, col="stage"):
    js = [(g[col].values[1:] != g[col].values[:-1]).mean()
          for _, g in d.sort_values(["ts_code", "year"]).groupby("ts_code") if len(g) > 1]
    return round(np.mean(js) * 100, 1) if js else None


def main():
    p = load_panel()
    R["样本_总公司数"] = int(p.ts_code.nunique())
    R["样本_总公司年数"] = int(len(p))
    R["样本_在市公司数"] = int(p[~p.delisted].ts_code.nunique())
    R["样本_退市公司数"] = int(p[p.delisted].ts_code.nunique())
    R["样本_年份范围"] = [int(p.year.min()), int(p.year.max())]
    _codes = _listed_codes()
    R["名单_在市总数"] = int(len(_codes))
    R["名单_未抓取金融业数"] = int(len(_codes) - R["样本_在市公司数"])
    R["样本_金融企业行数"] = int(p.is_fin.sum())
    R["样本_金融企业数"] = int(p[p.is_fin].ts_code.nunique())
    R["样本_年龄用交易所口径比例"] = round(float((p.age_src == "交易所上市日").mean()), 3)

    pf = p[~p.is_fin].copy()
    d = L.add_features(pf)

    # ---- 数据可用率 ----
    R["可用率"] = {c: round(float(d[c].notna().mean()), 4)
                   for c in ["cfo", "cfi", "cff", "re", "ta", "revenue", "cfi_core", "capex"]}
    R["可用率_按年份_cfi_core"] = {}
    for y in [1997, 2000, 2003, 2006, 2009, 2012, 2015, 2018, 2021, 2024, 2025]:
        s = d[d.year == y]
        if len(s):
            R["可用率_按年份_cfi_core"][str(y)] = round(float(s.cfi_core.notna().mean()), 3)

    # ---- 三口径可分类量 ----
    R["可分类行数"] = {}
    for u in ["cfi_core", "cfi", "capex"]:
        xx = L.classify(d, use=u)
        R["可分类行数"][u] = {"行数": int(xx.stage.notna().sum()),
                            "公司数": int(xx[xx.stage.notna()].ts_code.nunique()),
                            "覆盖率": round(float(xx.stage.notna().mean()), 3)}

    # ---- 三口径阶段分布（未做年龄修正与平滑，隔离口径影响）----
    R["口径对比"] = {}
    for u in ["cfi_core", "cfi", "capex"]:
        xu = L.classify(d, use=u)
        yu = xu[xu.stage.notna()]
        R["口径对比"][u] = {
            "标签行数": int(len(yu)),
            "各阶段占比": {CN[k]: round(float((yu.stage == k).mean() * 100), 1) for k in S},
            "中位年龄": {CN[k]: (None if pd.isna(yu[yu.stage == k].age.median()) else float(yu[yu.stage == k].age.median())) for k in S},
        }

    # ---- 主结果 ----
    x = classify_main(d)
    v = x[x.stage.notna()].copy()
    R["主设定"] = {
        "口径": "CFI_core + override(年龄>10年, RE/TA中位数) + 3年平滑 + 剔除金融",
        "标签行数": int(len(v)), "覆盖公司数": int(v.ts_code.nunique()),
        "年份范围": [int(v.year.min()), int(v.year.max())],
        "各阶段占比": {CN[k]: round(float((v.stage == k).mean() * 100), 1) for k in S},
        "各阶段行数": {CN[k]: int((v.stage == k).sum()) for k in S},
        "各阶段公司数": {CN[k]: int(v[v.stage == k].ts_code.nunique()) for k in S},
        "中位年龄": {CN[k]: (None if pd.isna(v[v.stage == k].age.median()) else float(v[v.stage == k].age.median())) for k in S},
        "中位CFO/TA": {CN[k]: round(float(v[v.stage == k].cfo_s.median()), 4) for k in S},
        "中位RE/TA": {CN[k]: round(float(v[v.stage == k].re_s.median()), 4) for k in S},
        "中位营收增速": {CN[k]: round(float(v[v.stage == k].rev_growth.median()), 4) for k in S},
        "中位总资产亿元": {CN[k]: round(float(v[v.stage == k].ta.median() / 1e8), 1) for k in S},
        "退市公司占比": {CN[k]: round(float(v[v.stage == k].delisted.mean() * 100), 1) for k in S},
        "平滑后跳变率": jump_rate(v),
        "平滑前跳变率": jump_rate(x, "stage_raw"),
        "年龄单调递增": bool(v[v.stage == "import"].age.median() < v[v.stage == "growth"].age.median() < v[v.stage == "mature"].age.median()),
    }
    base_del = float(v.delisted.mean() * 100)
    R["主设定"]["全样本退市占比"] = round(base_del, 1)
    R["主设定"]["退市倍数"] = {CN[k]: round(float(v[v.stage == k].delisted.mean() * 100) / base_del, 2) for k in S}
    R["主设定"]["预设门槛"] = 2.0
    R["主设定"]["门槛达成"] = bool(R["主设定"]["退市倍数"][CN["restruct"]] >= 2.0)

    # ---- 整合期内部拆分（卖资产型 vs 烧钱型）----
    rv = v[v.stage == "restruct"]
    t1 = rv[rv.cfi_core_s > 0] if "cfi_core_s" in rv else pd.DataFrame(columns=rv.columns)
    t2 = rv[(rv.cfo_s < 0) & (rv.cfi_core_s < 0)] if "cfi_core_s" in rv else pd.DataFrame(columns=rv.columns)
    R["整合期拆分"] = {}
    for tag, g in [("卖资产型", t1), ("烧钱型", t2)]:
        if len(g) == 0:
            R["整合期拆分"][tag] = {"n": 0}
            continue
        R["整合期拆分"][tag] = {
            "n": int(len(g)),
            "退市比例": round(float(g.delisted.mean() * 100), 1),
            "中位年龄": (None if pd.isna(g.age.median()) else float(g.age.median())),
            "ST比例": None,
        }
    R["整合期拆分"]["占整合期比重"] = {
        "卖资产型": round(float(len(t1) / max(len(rv), 1)) * 100, 1),
        "烧钱型": round(float(len(t2) / max(len(rv), 1)) * 100, 1),
    }

    # ---- ST ----
    st = pd.read_csv(os.path.join(RAW, "stock_st_flag_20260630.csv"), index_col=0,
                     engine="python", dtype=str).replace({"True": True, "False": False})
    st.index = pd.to_datetime(st.index)
    sty = st.groupby(st.index.year).max().T.astype("float")
    sty.index = [c.split(".")[0] for c in sty.index]
    v["st"] = np.nan
    for bb, g in v.groupby("bare"):
        if bb in sty.index:
            v.loc[g.index, "st"] = g["year"].map(sty.loc[bb])
    vv = v[v.st.notna()]
    R["ST检验"] = {
        "ST表_交易日数": int(len(st)), "ST表_股票数": int(st.shape[1]),
        "ST表_年份范围": [int(st.index.year.min()), int(st.index.year.max())],
        "ST整体占比": round(float(np.nanmean(sty.values) * 100), 2),
        "样本_ST匹配率": round(float(v.st.notna().mean()), 3),
        "各阶段ST占比": {CN[k]: round(float(vv[vv.stage == k].st.mean() * 100), 2) for k in S},
        "各阶段n": {CN[k]: int((vv.stage == k).sum()) for k in S},
        "样本ST占比基准": round(float(vv.st.mean() * 100), 2),
        "各阶段ST倍数": {CN[k]: round(float(vv[vv.stage == k].st.mean() * 100) / (vv.st.mean() * 100), 2) for k in S},
        "ST公司落阶段分布": {CN[k]: round(float((vv[vv.st == 1].stage == k).mean() * 100), 1) for k in S},
        "整合期未被ST比例": round(float((vv[vv.stage == "restruct"].st == 0).mean() * 100), 1),
    }
    for tag, g in [("卖资产型", t1), ("烧钱型", t2)]:
        gv = v.loc[g.index.intersection(v.index)]
        if len(gv) and gv.st.notna().any():
            R["整合期拆分"][tag]["ST比例"] = round(float(gv.st.mean() * 100), 2)

    # 剔除ST后分布
    allp = v.stage.value_counts(normalize=True).mul(100).round(1)
    clnp = vv[vv.st == 0].stage.value_counts(normalize=True).mul(100).round(1)
    R["ST检验"]["剔除ST后分布变化"] = {CN[k]: round(float(clnp.get(k, 0) - allp.get(k, 0)), 1) for k in S}

    # ---- 板块 ----
    ct = pd.crosstab(vv.board, vv.stage, normalize="index").mul(100).round(1)
    ct = ct.reindex(columns=S).fillna(0)
    R["板块检验"] = {
        b: {"n": int((vv.board == b).sum()), **{CN[k]: float(ct.loc[b, k]) for k in S},
            "占比最高": CN[ct.loc[b].idxmax()]}
        for b in ct.index if (vv.board == b).sum() >= 100
    }

    # ---- 行业 ----
    ind = pd.read_csv(os.path.join(RAW, "industry_map.csv"), dtype={"bare": str})
    v["industry"] = v.bare.map(dict(zip(ind.bare, ind.industry)))
    vi = v[v.industry.notna()]
    ci = pd.crosstab(vi.industry, vi.stage, normalize="index").mul(100).round(1).reindex(columns=S).fillna(0)
    ci.columns = [CN[c] for c in ci.columns]
    ci["n"] = vi.industry.value_counts()
    R["行业检验"] = {
        "行业数": int(len(ci)), "行业匹配率": round(float(v.industry.notna().mean()), 3),
        "整合期占比最高": {k: [float(ci.loc[k, "整合期"]), int(ci.loc[k, "n"])]
                     for k in ci.sort_values("整合期", ascending=False).head(6).index},
        "成熟期占比最高": {k: [float(ci.loc[k, "成熟期"]), int(ci.loc[k, "n"])]
                     for k in ci.sort_values("成熟期", ascending=False).head(6).index},
    }

    # ---- 稳健性（复用 task4 结果表）----
    rb = pd.read_csv(os.path.join(DER, "robustness_scan_full.csv" if PANEL_MODE == "full" else "robustness_scan.csv"))
    R["稳健性"] = {
        "设定数": int(len(rb)),
        "年龄阈值跨度": {c: round(float(rb[rb.test == "age_threshold"][c].max() - rb[rb.test == "age_threshold"][c].min()), 1)
                    for c in ["imp", "gro", "mat", "res"]},
        "RE分界跨度": {c: round(float(rb[rb.test == "re_cut"][c].max() - rb[rb.test == "re_cut"][c].min()), 1)
                   for c in ["imp", "gro", "mat", "res"]},
        "平滑窗口跨度": {c: round(float(rb[rb.test == "smooth_win"][c].max() - rb[rb.test == "smooth_win"][c].min()), 1)
                   for c in ["imp", "gro", "mat", "res"]},
        "金融过滤跨度": {c: round(float(rb[rb.test == "fin_filter"][c].max() - rb[rb.test == "fin_filter"][c].min()), 1)
                   for c in ["imp", "gro", "mat", "res"]},
        "跳变率范围": [float(rb.jump.min()), float(rb.jump.max())],
        "单调递增通过数": int(sum(1 for r in rb.itertuples() if r.age_imp < r.age_gro < r.age_mat)),
        "单调递增失败设定": [f"{r.test}/{r.param}" for r in rb.itertuples() if not (r.age_imp < r.age_gro < r.age_mat)],
        "基准行": {"导入": float(rb[rb.test == "base"].imp.iloc[0]), "成长": float(rb[rb.test == "base"].gro.iloc[0]),
                "成熟": float(rb[rb.test == "base"].mat.iloc[0]), "整合": float(rb[rb.test == "base"].res.iloc[0])},
        "RE均值下成长期": float(rb[(rb.test == "re_cut") & (rb.param == "mean")].gro.iloc[0]),
        "RE均值下整合期": float(rb[(rb.test == "re_cut") & (rb.param == "mean")].res.iloc[0]),
        "RE中位数下成长期": float(rb[(rb.test == "re_cut") & (rb.param == "median")].gro.iloc[0]),
        "RE中位数下整合期": float(rb[(rb.test == "re_cut") & (rb.param == "median")].res.iloc[0]),
        "平滑2年整合期": float(rb[(rb.test == "smooth_win") & (rb.param.astype(str) == "2")].res.iloc[0]),
        "平滑5年整合期": float(rb[(rb.test == "smooth_win") & (rb.param.astype(str) == "5")].res.iloc[0]),
        "年龄阈值最大跨度": round(float(max(rb[rb.test == "age_threshold"][c].max() - rb[rb.test == "age_threshold"][c].min() for c in ["imp", "gro", "mat", "res"])), 1),
        "成长期最大跨度": round(float(max(rb[rb.test == t].gro.max() - rb[rb.test == t].gro.min() for t in rb.test.unique())), 1),
        "各设定": [{"参数组": f"{r.test}/{r.param}", "导入": r.imp, "成长": r.gro, "成熟": r.mat,
                 "整合": r.res, "跳变率": r.jump,
                 "单调": bool(r.age_imp < r.age_gro < r.age_mat)} for r in rb.itertuples()],
    }

    # ---- 趋势 ----
    yr = v.groupby("year").stage.value_counts(normalize=True).unstack() * 100
    R["趋势"] = {
        "成熟期占比_2012前": round(float(yr.loc[yr.index <= 2012, "mature"].mean()), 1),
        "成熟期占比_2018后": round(float(yr.loc[yr.index >= 2018, "mature"].mean()), 1),
        "各年成熟期占比": {str(int(y)): (None if pd.isna(yr.loc[y, "mature"]) else round(float(yr.loc[y, "mature"]), 1))
                      for y in yr.index},
    }

    # 导出标签
    out = v[["ts_code", "bare", "name", "year", "age", "age_src", "stage", "board", "delisted"]].copy()
    out["stage_cn"] = out.stage.map(CN)
    out.to_csv(os.path.join(DER, "labels_main_full.csv" if PANEL_MODE == "full" else "labels_main_1050.csv"), index=False)

    with open(os.path.join(NUMBERS, OUT_JSON), "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=2)
    print(f"输出 → {OUT_JSON}")
    print(json.dumps(R, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _mode = sys.argv[1] if len(sys.argv) > 1 else "sample"
    PANEL_MODE = _mode
    OUT_JSON = f"report_numbers_{_mode}.json" if _mode == "full" else "report_numbers.json"
    if _mode == "sample" and os.path.exists(os.path.join(NUMBERS, "report_numbers.json")):
        OUT_JSON = "report_numbers.json"
    main()
