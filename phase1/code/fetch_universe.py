#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A 股全市场财务数据抓取器（可断点续传 + 限速退避 + 进度/ETA 日志）

设计要点：
1. 断点续传：每只股票抓完立即落盘 CSV，重跑自动跳过已存在的
2. 限速退避：失败自动重试，指数退避，避免触发新浪限流
3. 进度可观测：持续写 status.json，可随时查看完成度与 ETA
4. 内存安全：逐只处理，不累积原始表
"""
import sys, os, time, json, re, glob, random
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(os.path.dirname(HERE), "data_raw")   # phase1/data_raw
sys.path.insert(0, HERE)
import akshare as ak
import pandas as pd

CACHE = os.path.expanduser("~/life_cache")
LOGDIR = os.path.expanduser("~/life_fetch_logs")
os.makedirs(CACHE, exist_ok=True)
os.makedirs(LOGDIR, exist_ok=True)

STATUS = os.path.join(LOGDIR, "status.json")
EXCLUDE_RE = re.compile(r"银行|保险|证券|信托|期货|租赁|理财")   # 金融业另作处理，不进主分类


def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(os.path.join(LOGDIR, "fetch.log"), "a") as f:
        f.write(line + "\n")


def write_status(**kw):
    kw["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tmp = STATUS + ".tmp"
    with open(tmp, "w") as f:
        json.dump(kw, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATUS)


def have(code, symbol):
    return os.path.exists(f"{CACHE}/{code}_{symbol}.csv")


def fetch_one(code, max_retry=4):
    """抓一只股票的三张表。返回成功张数。"""
    got = 0
    for symbol in ("现金流量表", "资产负债表", "利润表"):
        if have(code, symbol):
            got += 1
            continue
        for attempt in range(max_retry):
            try:
                df = ak.stock_financial_report_sina(stock=code, symbol=symbol)
                if df is None or len(df) == 0:
                    break
                df.to_csv(f"{CACHE}/{code}_{symbol}.csv", index=False)
                got += 1
                break
            except Exception as e:
                wait = min(60, (2 ** attempt) * 3) + random.uniform(0, 2)
                if attempt == max_retry - 1:
                    log(f"    ! {code} {symbol} 最终失败: {type(e).__name__}")
                else:
                    log(f"    . {code} {symbol} 第{attempt+1}次失败({type(e).__name__})，{wait:.0f}s 后重试")
                    time.sleep(wait)
    return got


def get_universe(stride):
    """取代码表，并用名称剔除金融业。"""
    src = os.path.join(RAW, "a_code_name.csv")
    if not os.path.exists(src):
        lst = ak.stock_info_a_code_name()
        lst.to_csv(src, index=False)
    else:
        lst = pd.read_csv(src, dtype={"code": str})
    lst = lst.copy()
    lst["ts_code"] = np.where(lst["code"].str.startswith(("6", "9")), "sh", "sz") + lst["code"]
    lst = lst[~lst["name"].str.contains(EXCLUDE_RE, na=False)]
    samp = lst.iloc[::stride].reset_index(drop=True)
    return list(zip(samp["ts_code"], samp["name"]))


import numpy as np


def main():
    stride = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    pause = float(sys.argv[2]) if len(sys.argv) > 2 else 0.35
    codes = get_universe(stride)
    total = len(codes)
    log(f"=== 开始抓取：每 {stride} 只取 1 只，共 {total} 只（已剔除金融业）===")

    todo = [(c, n) for c, n in codes
            if not (have(c, "现金流量表") and have(c, "资产负债表"))]
    log(f"待抓 {len(todo)} 只，已在缓存 {total-len(todo)} 只")

    t_start = time.time()
    for i, (code, name) in enumerate(todo, 1):
        t0 = time.time()
        n = fetch_one(code)
        el = time.time() - t0
        done = i
        eta = (time.time() - t_start) / done * (len(todo) - done) if done else 0
        if done % 10 == 0 or done <= 3:
            log(f"  {done}/{len(todo)} {code} {name} 取得{n}表 {el:.1f}s "
                f"| 已用 {(time.time()-t_start)/60:.0f}min 剩余约 {eta/60:.0f}min")
            write_status(total=len(todo), done=done, current=f"{code} {name}",
                         eta_minutes=round(eta / 60, 1),
                         elapsed_minutes=round((time.time() - t_start) / 60, 1))
        time.sleep(pause)

    log("=== 全部完成 ===")
    write_status(total=len(todo), done=len(todo), current="DONE", eta_minutes=0,
                 elapsed_minutes=round((time.time() - t_start) / 60, 1))


if __name__ == "__main__":
    main()
