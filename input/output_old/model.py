# -*- coding: utf-8 -*-
"""统一入口：依次运行 model_1~4，合并结果写入 tables/results.json。

四个问题代码分文件：model_1.py（交会定位/直径）、model_2.py（第二检测点选择）、
model_3.py（多全向源搜索清除 + Held-Karp DP）、model_4.py（含定向源 + 全视角覆盖）。
默认对问题三、四执行短程离线 Q-learning；更大批量评估由 benchmark.py 完成。
本文件仅做编排，供 `python scripts/build_paper.py` 与手动运行调用。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import model_1
import model_2
import model_3
import model_4

# 定义汇总结果文件的输出路径：本脚本同级的 tables/results.json
OUT = Path(__file__).resolve().parent / "tables" / "results.json"


# 主编排入口：用默认参数构造输入，依次调用四个问题的求解函数并合并结果后落盘
def main() -> dict:
    # 构造统一的参数命名空间，作为问题三（DP/RL）与问题四（定向源覆盖）的输入
    args = SimpleNamespace(
        mock=True, n_sources=12, seed=2026, trials=3, dp=True,
        rl_episodes=150,
        robot_id="<参赛队号>", base_url="http://127.0.0.1:2026",
    )
    # 初始化汇总结果字典，用于收集四个问题的输出
    results: dict = {}
    # 调用问题一（model_1）：交会定位法求可行域直径与最小包围圆
    results.update(model_1.main())
    # 调用问题二（model_2）：第二检测点选择策略（最优交会角/候选区域）
    results.update(model_2.main())
    # 调用问题三（model_3）：多全向干扰源搜索清除（Held-Karp DP 或离线 Q-learning）
    results.update(model_3.problem3(args))
    # 调用问题四（model_4）：含定向源的搜索清除（全视角覆盖）
    results.update(model_4.problem4(args))

    # 确保 tables 输出目录存在（不存在则递归创建）
    OUT.parent.mkdir(exist_ok=True)
    # 将汇总结果以 UTF-8 编码、两空格缩进的美化 JSON 写入结果文件
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    # 打印完成提示与结果文件路径
    print(f"[DONE] 结果写入 {OUT}")
    # 返回结果字典，供 build_paper.py 等调用方进一步处理
    return results


# 命令行直接运行时的入口：解析命令行参数后执行与 main 相同的编排流程
if __name__ == "__main__":
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser()
    # 添加 --mock 开关：是否使用模拟模式，默认开启
    parser.add_argument("--mock", action="store_true", default=True)
    # 添加 --n-sources 参数：干扰源数量，默认 12 个
    parser.add_argument("--n-sources", type=int, default=12)
    # 添加 --seed 参数：随机种子，默认 2026（保证结果可复现）
    parser.add_argument("--seed", type=int, default=2026)
    # 添加 --trials 参数：蒙特卡洛试验次数，默认 3
    parser.add_argument("--trials", type=int, default=3)
    # 添加 --dp 开关：是否启用 Held-Karp 动态规划求最优清除路径
    parser.add_argument("--dp", action="store_true", default=True)
    # 添加 --rl-episodes 参数：问题三、四离线 Q-learning 训练局数，0 表示只做确定性诊断
    parser.add_argument("--rl-episodes", type=int, default=150,
                        help="问题三、四离线 Q-learning 训练局数；0 表示只运行确定性诊断")
    # 解析命令行参数，得到用户覆盖后的参数对象 args
    args = parser.parse_args()
    from types import SimpleNamespace
    # 将解析出的参数字典转换为 SimpleNamespace，便于用属性方式访问各参数
    ns = SimpleNamespace(**vars(args))
    # 初始化汇总结果字典
    results = {}
    # 依次调用四个问题的求解函数并合并结果（与 main 函数中的编排逻辑一致）
    results.update(model_1.main())
    results.update(model_2.main())
    results.update(model_3.problem3(ns))
    results.update(model_4.problem4(ns))
    # 确保输出目录存在
    OUT.parent.mkdir(exist_ok=True)
    # 将结果以 UTF-8 编码写入 JSON 文件
    OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    # 打印完成提示
    print(f"[DONE] 结果写入 {OUT}")
