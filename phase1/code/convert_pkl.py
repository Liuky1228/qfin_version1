#!/usr/bin/env python3
"""把 pkl 数据转换成其他格式，便于查看或后续调用。

用法: python3 convert_pkl.py <pkl文件路径> [--csv] [--xlsx] [--parquet] [--subset 100]
默认会全部生成 csv / xlsx / parquet 三种。
"""
import pickle
import sys
import os
import argparse

def load_pkl(path):
    with open(path, "rb") as f:
        return pickle.load(f)

def main():
    parser = argparse.ArgumentParser(description="转换 pkl 为 csv / xlsx / parquet")
    parser.add_argument("path", help="pkl 文件路径")
    parser.add_argument("--csv", action="store_true", help="只导出 csv")
    parser.add_argument("--xlsx", action="store_true", help="只导出 xlsx")
    parser.add_argument("--parquet", action="store_true", help="只导出 parquet")
    parser.add_argument("--subset", type=int, default=0,
                        help="只导出前 N 只股票(列)，减少数据量方便查看，0 表示全部")
    args = parser.parse_args()

    if not os.path.exists(args.path):
        print(f"文件不存在: {args.path}")
        sys.exit(1)

    import pandas as pd
    print(f"正在读取 {args.path} ...")
    data = load_pkl(args.path)
    print(f"原始数据: type={type(data)}, shape={getattr(data, 'shape', None)}")

    df = data
    if isinstance(data, pd.Series):
        df = data.to_frame()
    if not isinstance(df, pd.DataFrame):
        print("不支持的数据类型，跳过")
        sys.exit(1)

    # 重置索引，让日期变成一列而不仅是索引，各格式都更直观
    df = df.reset_index()
    date_col = df.columns[0]
    print(f"日期列: {date_col}, 共 {len(df)} 行 x {df.shape[1] - 1} 列")

    if args.subset > 0:
        df = df[[date_col] + list(df.columns[1:1 + args.subset])]
        print(f"已截取前 {args.subset} 列")

    base = os.path.splitext(args.path)[0]
    modes = [m for m in (args.csv, args.xlsx, args.parquet) if m]
    do_all = not modes

    # Parquet (压缩率高、读取快，最适合后续用 python 调用)
    if do_all or args.parquet:
        out = base + ".parquet"
        df.to_parquet(out, index=False)
        print(f"已保存: {out} ({os.path.getsize(out)/1024/1024:.1f} MB)")

    # CSV (通用格式，可用 Excel/WPS 或 pandas 打开)
    if do_all or args.csv:
        out = base + ".csv"
        df.to_csv(out, index=False)
        print(f"已保存: {out} ({os.path.getsize(out)/1024/1024:.1f} MB)")

    # Excel (两列版本: 日期+股票代码，逐行展示，避免几千列)
    if do_all or args.xlsx:
        out = base + "_melt.xlsx"
        n = args.subset if args.subset > 0 else 100
        mel = df.iloc[:, :1 + n].melt(id_vars=date_col, var_name="order_book_id",
                                      value_name="adj_close").dropna()
        mel[date_col] = pd.to_datetime(mel[date_col]).dt.strftime("%Y-%m-%d")
        mel.to_excel(out, index=False, engine="xlsxwriter")
        print(f"已保存: {out} (前 {n} 只股票 × 日期 的长表, 共 {len(mel)} 行) "
              f"({os.path.getsize(out)/1024/1024:.1f} MB)")

if __name__ == "__main__":
    main()