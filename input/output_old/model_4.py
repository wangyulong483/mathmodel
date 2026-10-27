# -*- coding: utf-8 -*-
"""问题四：含定向源（180° 扇区、方向未知）的检测与清除。

理论：定向源检测区 = 半圆盘 → 需"空间+角度"（全视角）覆盖。
  - 判据：源位置 p 附近听点的最大角间隙不超过 180°。
  - 构造：三角格 s=R_min=1000 外推至 2800，共 31 点。包含 p 的基本
    三角形三个顶点距 p 均不超过 1000 m，且不在 p 的同一开半平面内。
算法：复用问题三的定位/清除与 RL 部署，听点集换为 31 点外推格。

运行：python output/model_4.py [--mock] [--n-sources 12] [--seed 2026]
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib
# 指定 matplotlib 无界面后端（Agg），避免在无显示环境绘图报错
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from geo import R_TARGET, R_EFF_MIN, dist, triangular_lattice
from layout import q4_layout as _q4_points, max_angular_gap, q4_certificate
from sim import MockSimulator
from model_3 import run_strategy, run_strategy_rl

# 图片输出目录：本文件所在目录下的 figures/ 子目录
FIG_DIR = Path(__file__).resolve().parent / "figures"
# 若该目录不存在则创建（exist_ok 避免重复创建时报错）
FIG_DIR.mkdir(exist_ok=True)


def directional_layout():
    """31 点外推三角格 + 全视角覆盖判据检验（布局定义见 layout.q4_layout）。"""
    # 听点间距取最小有效半径 R_EFF_MIN（=1000 m）
    spacing = R_EFF_MIN
    # 覆盖外推半径 = 目标区半径 + 最小有效半径（=2800 m）
    ext = R_TARGET + R_EFF_MIN          # 2800
    # 生成问题四的 31 点外推三角格听点集
    pts = _q4_points()

    # 用全视角覆盖判据检验该听点集的最差角间隙（720 角度切片 × 40 径向切片）
    worst = q4_certificate(pts, n_ang=720, n_rad=40)

    # 由三角格密度公式估算所需听点总数（供论文引用）
    density_est = (2.0 * math.pi / math.sqrt(3.0)) * ((R_TARGET / R_EFF_MIN) + 1.0) ** 2

    # 新建绘图坐标系
    fig, ax = plt.subplots(figsize=(6.6, 6.2))
    # 画出目标区边界圆（虚线）
    ax.add_patch(plt.Circle((0, 0), R_TARGET, fill=False, ls="--", lw=1.4, color="0.2"))
    # 遍历每个听点，画出其有效覆盖圆
    for p in pts:
        ax.add_patch(plt.Circle(p, spacing, fill=False, ls="-", lw=0.3, color="tab:green", alpha=0.5))
    # 画出全部听点位置（红点）
    ax.plot([p[0] for p in pts], [p[1] for p in pts], "r.", ms=5)
    # 构造一个边界上的定向源示例坐标（用于示意图）
    demo = np.array([1800.0, 0.0])
    # 取距该示例源最近的两个听点（用于说明其被覆盖）
    near = sorted(pts, key=lambda q: dist(q, demo))[:2]
    # 标出该边界定向源（蓝星）
    ax.plot(*demo, "b*", ms=14, label="boundary directional source")
    # 画出示例源到最近两个听点的连线（洋红）
    for q in near:
        ax.plot([demo[0], q[0]], [demo[1], q[1]], "m-", lw=1.2)
    # 设置标题：展示间距、外推半径、点数与最差角间隙
    ax.set_title(f"Space+angle (full-view) covering: s={int(spacing)} m, extent {int(ext)} m, "
                 f"n={len(pts)}, worst gap {worst:.0f}°")
    # 等比例坐标轴；加网格；显示图例
    ax.set_aspect("equal"); ax.grid(alpha=0.25); ax.legend(loc="best", fontsize=8)
    # 设置 x/y 轴显示范围
    ax.set_xlim(-2900, 2900); ax.set_ylim(-2900, 2900)
    # 紧凑排版；保存图片；关闭图形释放内存
    fig.tight_layout(); fig.savefig(FIG_DIR / "q4_covering.png", dpi=150); plt.close(fig)

    # 返回问题四布局的诊断结果字典
    return {
        "spacing": spacing, "extent_radius": ext, "n_points": len(pts),
        "points": [p.tolist() for p in pts],
        "worst_angular_gap_deg": round(worst, 2),
        "double_direction_ok": worst <= 180.0 + 1e-6,
        "certificate_vertices": 3,
        "density_estimate_N": round(density_est, 1),
    }


def problem4(args):
    # 生成 31 点外推格布局并做覆盖判据检验
    layout = directional_layout()
    # 记录相对问题三 7 点布局的听点增量（31 - 7）
    layout["vs_q3_n"] = layout["n_points"] - 7

    # 初始化离线自测的局数结果列表
    trials = []
    # 初始化累计清除源数与累计源总数
    cleared = total = 0
    # 运行多局（默认 3 局）离线自测
    for seed in range(getattr(args, "trials", 3)):
        # 构造含定向源的模拟器（固定种子保证可复现）
        sim = MockSimulator(n_sources=args.n_sources, seed=3000 + seed, directional=True)
        # 标记已进入目标区
        sim.entered = True
        # 把布局听点坐标转为 numpy 数组
        pts = [np.array(p) for p in layout["points"]]
        # 复用问题三的确定性策略在 31 点格上运行（首局打印日志，绕行不设上限）
        st = run_strategy(sim, listening_points=pts, use_dp=args.dp, verbose=(seed == 0),
                          detour_limit=float("inf"))
        # 记录本局结果
        trials.append(st)
        # 累加清除源数
        cleared += st["cleared"]
        # 累加真实源总数
        total += sim.total_sources()
    # 计算离线自测的清除比例（保留 4 位小数，无源时置 0）
    layout["offline_clear_ratio"] = round(cleared / total, 4) if total else 0.0
    # 计算离线自测的平均虚拟时间（秒，保留 1 位小数）
    layout["offline_avg_time_s"] = round(sum(t["virtual_time_s"] for t in trials) / len(trials), 1)

    # The unified entry point can request a short RL pass so its default
    # output reflects the paper's RL main line.  benchmark.py remains the
    # source for the larger 600-episode/35-trial results.
    # 统一入口可请求一次简短 RL 训练，使默认输出体现论文 RL 主线；
    # 大规模 600 局/35 次结果仍以 benchmark.py 为准。
    rl_episodes = int(getattr(args, "rl_episodes", 0))
    # 仅当请求的 RL 训练局数 > 0 时执行 RL 分支
    if rl_episodes > 0:
        from rl import SearchQAgent, train_q_search

        # 准备 RL 训练用的听点坐标（numpy 数组）
        rl_points = [np.array(p) for p in layout["points"]]
        # 创建带覆盖约束的 Q 学习智能体（固定种子）
        agent = SearchQAgent(rl_points, seed=20260915)
        # 独立随机数生成器用于生成训练场景的源数（固定种子）
        rng = np.random.default_rng(20260915)

        def factory(ep):
            # 训练场景工厂：每局随机源数 10~16，均为方向源，固定种子
            return MockSimulator(
                n_sources=int(rng.integers(10, 17)),
                seed=92000 + ep,
                directional=True,
            )

        # 训练 Q 智能体，返回每局搜索时间曲线
        curve = train_q_search(factory, agent, episodes=rl_episodes,
                               max_steps=40, verbose=False)
        # 构造评估用模拟器（与离线自测相同源数，不同种子）
        eval_sim = MockSimulator(n_sources=args.n_sources, seed=args.seed + 9000,
                                 directional=True)
        # 标记已进入目标区
        eval_sim.entered = True
        # 用训练好的智能体在评估场景上部署运行（RL 部署）
        eval_result = run_strategy_rl(eval_sim, agent, use_dp=args.dp,
                                      verbose=False, detour_limit=float("inf"))
        # 记录 RL 训练局数
        layout["rl_episodes"] = rl_episodes
        # 记录 RL 首局训练时间（无曲线时为 None）
        layout["rl_training_first_time_s"] = round(float(curve[0]), 1) if curve else None
        # 记录 RL 末局训练时间（无曲线时为 None）
        layout["rl_training_last_time_s"] = round(float(curve[-1]), 1) if curve else None
        # 计算 RL 部署的清除比例
        layout["rl_clear_ratio"] = round(
            eval_result["cleared"] / eval_sim.total_sources(), 4)
        # 记录 RL 部署的虚拟时间
        layout["rl_virtual_time_s"] = eval_result["virtual_time_s"]
    # 打印问题四布局摘要（间距、外推半径、点数、最差角间隙与是否合格）
    print(f"[Q4] s={int(layout['spacing'])} m extent={int(layout['extent_radius'])} m "
          f"-> {layout['n_points']} points, worst gap {layout['worst_angular_gap_deg']}° "
          f"(ok: {layout['double_direction_ok']})")
    # 打印离线自测统计（清除比例与平均时间）
    print(f"[Q4] 离线自测({len(trials)}局): 清除比例={layout['offline_clear_ratio']:.2%} "
          f"平均时间={layout['offline_avg_time_s']}s")
    # 返回问题四的完整结果字典
    return {"q4": layout}


def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser()
    # --mock 开关：使用模拟器（默认开启）
    parser.add_argument("--mock", action="store_true", default=True)
    # --n-sources：源数量，默认 12
    parser.add_argument("--n-sources", type=int, default=12)
    # --seed：随机种子，默认 2026
    parser.add_argument("--seed", type=int, default=2026)
    # --trials：离线自测局数，默认 3
    parser.add_argument("--trials", type=int, default=3)
    # --dp：是否启用动态规划定位（默认开启）
    parser.add_argument("--dp", action="store_true", default=True)
    # --rl-episodes：离线 Q 学习训练局数，0 表示只做确定性诊断
    parser.add_argument("--rl-episodes", type=int, default=0,
                        help="离线 Q-learning 训练局数；0 表示只运行确定性诊断")
    # 解析命令行参数并运行问题四求解流程
    return problem4(parser.parse_args())


if __name__ == "__main__":
    import json
    # 运行主流程并把结果以 JSON（含中文，缩进 2）打印
    print(json.dumps(main(), ensure_ascii=False, indent=2))
