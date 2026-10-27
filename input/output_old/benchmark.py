# -*- coding: utf-8 -*-
# 问题三/四 可复现离线基准测试：评估 RL 与固定路线基线在随机源下的清除性能。
"""Reproducible offline benchmark for Problems 3 and 4."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import time

import numpy as np

from geo import R_EFF_MIN
from layout import q3_layout, q4_layout, q3_cover_radius, q4_certificate
from model_3 import DETOUR_LIMIT, run_strategy, run_strategy_rl
from rl import SearchQAgent, train_q_search
from sim import MockSimulator

# 基准结果输出路径：tables 目录下的 JSON 文件
OUT = Path(__file__).resolve().parent / "tables" / "benchmark_results.json"


def _summary(rows):
    # 收集所有试验的虚拟定位清除总时间
    times = np.array([r["virtual_time_s"] for r in rows], dtype=float)
    # 计算每个源分摊的平均清除时间
    per_source = np.array([r["virtual_time_s"] / r["total"] for r in rows])
    # 返回包含清除率与时间分位数的统计摘要
    return {
        "trials": len(rows),
        "full_clear_rate": round(np.mean([r["cleared"] == r["total"]
                                           for r in rows]), 4),
        "total_time_s": {
            "min": round(float(times.min()), 1),
            "p10": round(float(np.percentile(times, 10)), 1),
            "median": round(float(np.median(times)), 1),
            "p90": round(float(np.percentile(times, 90)), 1),
            "max": round(float(times.max()), 1),
        },
        "per_source_time_s": {
            "p10": round(float(np.percentile(per_source, 10)), 1),
            "median": round(float(np.median(per_source)), 1),
            "p90": round(float(np.percentile(per_source, 90)), 1),
        },
    }


def _train(problem, points, episodes):
    # 构造固定种子的搜索智能体，保证训练可复现
    agent = SearchQAgent(points, seed=20260911 + problem)
    # 计数随机源用独立种子，与训练种子解耦
    count_rng = random.Random(8800 + problem)

    # 定义环境工厂：按局号生成对应种子与源数的模拟环境
    def factory(episode):
        # 返回一个随机 10~16 源的 Mock 环境，问题四含定向源
        return MockSimulator(
            n_sources=count_rng.randint(10, 16),
            seed=100000 * problem + episode,
            directional=(problem == 4),
        )

    # 执行 Q-learning 训练，得到收敛曲线
    curve = train_q_search(factory, agent, episodes=episodes, verbose=True)
    # 返回智能体及其训练统计（首末 100 局均值与学习状态数）
    return agent, {
        "episodes": episodes,
        "first_100_search_mean_s": round(float(np.mean(curve[:100])), 1),
        "last_100_search_mean_s": round(float(np.mean(curve[-100:])), 1),
        "learned_states": len(agent.Q),
    }


def _evaluate(problem, agent, trials, seed_base, all_directional=False):
    # 初始化用于收集各次试验结果的列表
    rows = []
    # 对每个试验逐次评估
    for trial in range(trials):
        # 源数在 10~16 间按试验号循环取值
        total = 10 + trial % 7
        # 构造固定种子的模拟环境，定向源概率可配置
        sim = MockSimulator(
            n_sources=total,
            seed=seed_base + trial,
            directional=(problem == 4),
            directional_probability=1.0 if all_directional else 0.65,
        )
        # 标记已进入模拟器，直接跑策略
        sim.entered = True
        # 以 RL 智能体运行策略并记录结果，问题四放宽顺路阈值
        result = run_strategy_rl(sim, agent, use_dp=True, verbose=False,
                                 detour_limit=(None if problem == 3 else float("inf")))
        # 追加本次试验的种子、源数与结果
        rows.append({"seed": seed_base + trial, "total": total, **result})
    # 返回所有试验的结果列表
    return rows


def _baseline_q3(trials, seed_base):
    # 初始化用于收集固定路线基线结果的列表
    rows = []
    # 对每个试验逐次评估
    for trial in range(trials):
        # 源数在 10~16 间按试验号循环取值
        total = 10 + trial % 7
        # 构造全向源的固定种子模拟环境
        sim = MockSimulator(n_sources=total, seed=seed_base + trial,
                            directional=False)
        # 标记已进入模拟器，直接跑策略
        sim.entered = True
        # 以固定听点集策略运行并记录结果
        result = run_strategy(sim, use_dp=True, verbose=False)
        # 追加本次试验的种子、源数与结果
        rows.append({"seed": seed_base + trial, "total": total, **result})
    # 返回固定路线基线结果列表
    return rows


def main():
    # 解析命令行参数，配置训练局数与评估次数
    parser = argparse.ArgumentParser()
    # 训练局数，默认 600
    parser.add_argument("--episodes", type=int, default=600)
    # 评估试验次数，默认 35
    parser.add_argument("--trials", type=int, default=35)
    # 解析得到实际参数
    args = parser.parse_args()

    # 记录基准测试开始的墙钟时间
    started = time.perf_counter()
    # 生成问题三的听点集
    q3_points = q3_layout()
    # 生成问题四的听点集
    q4_points = q4_layout()

    # 训练问题三的智能体并得到训练统计
    q3_agent, q3_train = _train(3, q3_points, args.episodes)
    # 训练问题四的智能体并得到训练统计
    q4_agent, q4_train = _train(4, q4_points, args.episodes)

    # 评估问题三 RL 表现
    q3_rows = _evaluate(3, q3_agent, args.trials, 31000)
    # 评估问题三固定路线基线
    q3_base = _baseline_q3(args.trials, 31000)
    # 评估问题四混合源 RL 表现
    q4_rows = _evaluate(4, q4_agent, args.trials, 41000)
    # 评估问题四全定向源压力测试
    q4_stress = _evaluate(4, q4_agent, args.trials, 51000,
                          all_directional=True)

    # 汇总证书、训练与评估结果为最终基准报告
    result = {
        "seed_policy": "fixed and disjoint train/evaluation seeds",
        "certificates": {
            "q3_n_points": len(q3_points),
            "q3_cover_radius_m": round(q3_cover_radius(), 2),
            "q3_cover_ok_under_1000m": q3_cover_radius() < R_EFF_MIN,
            "q4_n_points": len(q4_points),
            "q4_worst_angular_gap_deg": round(q4_certificate(q4_points), 2),
            "q4_full_view_ok": q4_certificate(q4_points) <= 180.0,
            "detour_limit_m": DETOUR_LIMIT,
        },
        "q3": {
            "training": q3_train,
            "rl": _summary(q3_rows),
            "fixed_route_baseline": _summary(q3_base),
        },
        "q4": {
            "training": q4_train,
            "rl_mixed_sources": _summary(q4_rows),
            "rl_all_directional_stress": _summary(q4_stress),
        },
        "wall_time_s": round(time.perf_counter() - started, 2),
    }
    # 确保输出目录存在
    OUT.parent.mkdir(parents=True, exist_ok=True)
    # 将结果以 UTF-8 缩进格式写入 JSON 文件
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    # 打印最终基准结果
    print(json.dumps(result, ensure_ascii=False, indent=2))
    # 返回结果对象
    return result


if __name__ == "__main__":
    # 作为脚本入口运行时调用主函数
    main()
