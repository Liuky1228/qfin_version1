#!/usr/bin/env python3
import pickle
import sys
import os

def load_pkl(path):
    """读取任意 pickle 文件并返回内容"""
    with open(path, "rb") as f:
        return pickle.load(f)

def main():
    if len(sys.argv) < 2:
        print("用法: python open_pkl.py <pkl文件路径>")
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"文件不存在: {path}")
        sys.exit(1)

    print(f"正在读取: {path} (大小: {os.path.getsize(path) / 1024 / 1024:.1f} MB)\n")
    data = load_pkl(path)

    print(f"数据类型: {type(data)}")

    # 如果数据是 pandas DataFrame / Series
    try:
        import pandas as pd
        if isinstance(data, (pd.DataFrame, pd.Series)):
            print(f"形状 (行, 列): {data.shape}")
            print(f"列名: {list(data.columns) if hasattr(data, 'columns') else 'N/A'}\n")
            print(data.head(10))
            print("\n...\n")
            print(data.tail(5))
            return
    except ImportError:
        pass

    # 字典
    if isinstance(data, dict):
        print(f"键数量: {len(data)}")
        print(f"键列表 (前20个): {list(data.keys())[:20]}\n")
        for k in list(data.keys())[:3]:
            v = data[k]
            print(f"  {k}: type={type(v)}, shape={getattr(v, 'shape', None) if hasattr(v, 'shape') else 'N/A'}")
        return

    # 列表 / 元组
    if isinstance(data, (list, tuple)):
        print(f"元素数量: {len(data)}")
        print("前3个元素:")
        for item in data[:3]:
            print(f"  type={type(item)}, value={item}")
        return

    # Numpy 数组
    if hasattr(data, "shape"):
        print(f"形状: {data.shape}, dtype: {getattr(data, 'dtype', 'N/A')}\n")
        print(data)
        return

    # 其他类型直接打印
    print(data)

if __name__ == "__main__":
    main()