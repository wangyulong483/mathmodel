# -*- coding: utf-8 -*-
"""生成 RL Q-learning 收敛曲线图（问题三/四），曲线由真实训练过程产生。

每个面板画 3 条独立训练曲线（不同随机种子）+ 其滑动平均。纵轴是训练回合的
**搜索阶段虚拟时间**（`train_q_search` 直接返回的量，即访遍听点与频道扫描的耗时），
它正是 Q-learning 奖励里被优化的那一项。
"""
from pathlib import Path
import random

import matplotlib
# 使用非交互式后端，便于在无显示环境批量出图
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from layout import q3_layout, q4_layout
from rl import SearchQAgent, train_q_search
from sim import MockSimulator

# 配置中文字体，保证图中中文标签正常显示
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
# 关闭负号 Unicode 减号，避免中文环境下显示异常
plt.rcParams["axes.unicode_minus"] = False

# 图片输出目录
FIG_DIR = Path(__file__).resolve().parent / "figures"
# 确保图片输出目录存在
FIG_DIR.mkdir(exist_ok=True)

# 每个问题的训练局数
EPISODES = 600
# 三个独立训练用的随机种子
SEEDS = [20260911, 20260912, 20260913]


def curves(problem, points):
    # 初始化收集多条训练曲线的列表
    out = []
    # 用不同种子各训练一条独立曲线
    for s in SEEDS:
        # 以当前种子构造搜索智能体
        agent = SearchQAgent(points, seed=s)
        # 用当前种子构造环境随机源
        rng = random.Random(s)
        # 训练并收集该种子的搜索阶段虚拟时间曲线
        out.append(train_q_search(
            lambda ep, rng=rng: MockSimulator(
                n_sources=rng.randint(10, 16), seed=100000 * problem + ep,
                directional=(problem == 4)),
            agent, episodes=EPISODES, verbose=False))
    # 返回多条曲线构成的浮点数组
    return np.array(out, dtype=float)


def smooth(y, w=25):
    # 构造长度为 w 的等权滑动窗口核
    k = np.ones(w) / w
    # 用有效卷积实现滑动平均
    return np.convolve(y, k, mode="valid")


def _panel(ax, data, title, color):
    # 逐条绘制原始训练曲线（半透明细线）
    for row in data:
        ax.plot(np.arange(len(row)), row, ls="-", lw=0.7, alpha=0.35, color=color)
    # 求所有种子的平均曲线
    m = data.mean(axis=0)
    # 对平均曲线做 40 局滑动平均
    sm = smooth(m, 40)
    # 绘制滑动平均主曲线并添加图例
    ax.plot(np.arange(len(sm)) + 20, sm, ls="-", lw=2.2, color=color,
            label=f"{title} 40 局滑动平均")
    # 设置横轴标签
    ax.set_xlabel("训练局数 episode")
    # 设置纵轴标签
    ax.set_ylabel("搜索阶段虚拟时间 / s")
    # 添加网格线
    ax.grid(alpha=0.3)
    # 添加图例
    ax.legend(fontsize=8, loc="upper right")
    # 返回平均曲线供后续统计
    return m


# 创建 1 行 2 列的子图布局
fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.4))
# 绘制问题三的收敛曲线面板
m3 = _panel(axes[0], curves(3, q3_layout()), "问题三（全向源）", "tab:blue")
# 绘制问题四的收敛曲线面板
m4 = _panel(axes[1], curves(4, q4_layout()), "问题四（含定向源）", "tab:red")
# 自动调整子图间距
fig.tight_layout()
# 保存收敛曲线图为 PNG
fig.savefig(FIG_DIR / "q_rl_convergence.png", dpi=150)
# 关闭图形释放内存
plt.close(fig)

# 打印保存路径
print("saved:", FIG_DIR / "q_rl_convergence.png")
# 打印问题三首末 100 局搜索均值对比
print(f"Q3 首/末 100 局搜索均值: {m3[:100].mean():.1f} -> {m3[-100:].mean():.1f} s")
# 打印问题四首末 100 局搜索均值对比
print(f"Q4 首/末 100 局搜索均值: {m4[:100].mean():.1f} -> {m4[-100:].mean():.1f} s")
