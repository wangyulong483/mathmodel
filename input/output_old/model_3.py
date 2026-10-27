# -*- coding: utf-8 -*-
"""问题三：多全向源自动搜索定位清除。

理论：源视角圆盘覆盖。r(6)=0.555905 → 6 点需 R≥1000.6 m > 1000，故**7 点是合法下界**；
  在 7 点约束下最小化"自原点的开行程"，最优解是半径 ρ*=998.92 m 的**正七边形环**
  （覆盖半径证书 998.92 m < R_min=1000 m，开行程 6199 m；13 点双环为 12362 m）。
算法（确定性基线）：7 点环听巡（Held-Karp 最优开路径）→ 交会定位（Stansfield 加权
  最小二乘）→ **在线交织清除**（最廉插入把已知源排进剩余行程，增量里程超 300 m 者
  留到收尾巡回，收尾用开路径 2-opt + Or-opt）→ 兜底为"定位区域网格"（问题 1 的
  可行域，保证收敛）。探满 16 个频道即证明其余频道为空，可提前收工。
算法（RL 主线）：`rl.py` 表格 Q-learning 学习听点访问策略（计数无关 + 覆盖感知 + 二次测向
  奖励），详见 run_strategy_rl。
离线：对 MockSimulator 自测，输出清除比例 / 平均定位清除时间 / 虚拟时间。

运行：python output/model_3.py [--mock] [--n-sources 12] [--seed 2026]
"""
from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

import matplotlib
# 指定 matplotlib 使用无界面后端 Agg，保证无图形环境的服务器上也能绘图
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from geo import (R_TARGET, R_EFF_MIN, R_EFF_MAX, NEAR_R, DEG, dist, bearing,
                 line_through, intersect, triangular_lattice,
                 optimized_open_order, localization_region,
                 min_enclosing_circle)
from layout import (q3_layout, q4_layout, ring_layout, Q3_RHO,
                     q3_cover_radius)
from sim import MockSimulator, SimClient, CHANNELS

# 图片输出目录：定位到本脚本所在目录下的 figures 子目录
FIG_DIR = Path(__file__).resolve().parent / "figures"
# 若 figures 目录不存在则创建，避免后续 savefig 因路径缺失报错
FIG_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# 理论：圆盘覆盖
# ---------------------------------------------------------------------------
# 圆盘覆盖系数表：(点数 k, k 个等半径圆盘覆盖单位圆的最小归一化半径 r(k))
COVER_TABLE = [(3, 0.866025), (4, 0.707107), (5, 0.609382),
               (6, 0.555905), (7, 0.500000)]


# 由源可测半径 R 反推覆盖整个目标圆盘所需的最少听点数
def min_points(R):
    # 将半径 R 归一化到单位圆（除以目标圆半径 R_TARGET）
    r = R / R_TARGET
    # 顺序遍历覆盖表，找第一个归一化覆盖半径 <= r 的点数
    for k, rk in COVER_TABLE:
        # 加 1e-9 容差吸收浮点舍入误差，避免边界值漏判
        if rk <= r + 1e-9:
            # 返回满足覆盖的最少点数 k
            return k
    # 兜底：超过表内最大点数时固定返回 7（正七边形环）
    return 7


# 构造 7 听点布局：中心 + 外接圆半径 sqrt(3)*R 的正六边形 6 顶点
def hex_layout(R):
    """7 听点：中心 + 6 顶点正六边形（外接圆半径 √3·R）。"""
    # 六边形外接圆半径 s = sqrt(3)*R（保证覆盖所需的几何关系）
    s = math.sqrt(3.0) * R
    # 先放入位于原点的中心听点
    pts = [np.array([0.0, 0.0])]
    # 依次生成 6 个顶点，相邻顶点夹角 60 度
    for k in range(6):
        # 第 k 个顶点的极角（弧度）
        a = math.radians(k * 60.0)
        # 由极坐标 (s, a) 计算顶点直角坐标并加入听点列表
        pts.append(np.array([s * math.cos(a), s * math.sin(a)]))
    # 返回 7 个听点坐标
    return pts


# 构造 13 听点双环布局：中心 + 内环 R + 外环 sqrt(3)*R 各 6 顶点
def hex_layout_2ring(R):
    """13 听点：中心 + 内环(R) + 外环(√3·R) 各 6 点。

    内环消除中心盲区的"单测向"源（只被圆心测到的那类），使多数源双测向交会，
    定位误差 48m→~10m、总时间下降约 8%~15%。
    """
    # 先放入中心听点
    pts = [np.array([0.0, 0.0])]
    # 依次在半径 R 与 sqrt(3)*R 两条环上布置顶点
    for r in (R, math.sqrt(3.0) * R):
        # 每条环上均匀布置 6 个顶点，夹角 60 度
        for k in range(6):
            # 第 k 个顶点的极角（弧度）
            a = math.radians(k * 60.0)
            # 由极坐标 (r, a) 计算顶点坐标并加入列表
            pts.append(np.array([r * math.cos(a), r * math.sin(a)]))
    # 返回 13 个听点坐标
    return pts


# 返回默认覆盖布局（复用 7 点正六边形），默认半径取 R_EFF_MIN
def coverage_layout(R=R_EFF_MIN):
    """7 覆盖点：圆心 + 外环正六边形（半径 √3·R）。

    7 个半径 R 的检测圆盘覆盖整个 1800 m 目标圆盘（r(7)=0.5，R/1800=0.556>0.5），
    故访问完这 7 点后，**每个源都被至少一个点检测到**——由此既找全所有源，又反推出
    源总数（= 发现的不同频道数），化解题设"干扰源个数未知"。
    """
    # 直接复用 hex_layout 生成 7 点覆盖布局
    return hex_layout(R)


# 生成 6 个内环细化点（半径 R），为中心附近单测向源补充第二测向
def refinement_layout(R=R_EFF_MIN):
    """6 内环点（半径 R）：为中心附近单测向源提供第二测向（交会角大）。"""
    # 空列表收集 6 个内环点
    pts = []
    # 内环上均匀布置 6 点，夹角 60 度
    for k in range(6):
        # 第 k 个点的极角（弧度）
        a = math.radians(k * 60.0)
        # 由极坐标 (R, a) 计算内环点坐标并加入列表
        pts.append(np.array([R * math.cos(a), R * math.sin(a)]))
    # 返回 6 个内环细化点
    return pts


# 生成 4 点十字布局（上下左右），用于 R 较大时的条件覆盖
def cross_layout():
    # 十字点到原点的距离 d = R_TARGET / sqrt(2)
    d = R_TARGET / math.sqrt(2.0)
    # 返回东、西、北、南四个方向上的听点
    return [np.array([d, 0.0]), np.array([-d, 0.0]),
            np.array([0.0, d]), np.array([0.0, -d])]


# 绘制覆盖示意图：左图保证覆盖（7 点环），右图条件覆盖（4 点十字）
def covering_layouts():
    """图：保证覆盖（7 点正七边形环，覆盖半径 998.92 m）与条件覆盖（4 点十字）。"""
    # 问题三的 7 点正七边形环布局
    ring = q3_layout()
    # 创建 1 行 2 列的两个子图用于并排展示
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.3))
    # 左右两个面板：(坐标轴, 听点集, 检测半径, 颜色, 标题)
    panels = [
        (axes[0], ring, R_EFF_MIN, "tab:blue",
         f"guaranteed: worst-case $R$=1000 m → {len(ring)} points on a ring, "
         f"covering radius {q3_cover_radius():.1f} m"),
        (axes[1], cross_layout(), 1273.0, "tab:orange",
         f"conditional: if all $R$≥1273 m → {len(cross_layout())} points (radius 1273)"),
    ]
    # 逐面板绘制覆盖图
    for ax, pts, R, color, title in panels:
        # 绘制目标圆盘边界（1800 m，虚线）
        ax.add_patch(plt.Circle((0, 0), R_TARGET, fill=False, ls="--", lw=1.4, color="0.2"))
        # 绘制布局环半径 Q3_RHO（点线）
        ax.add_patch(plt.Circle((0, 0), Q3_RHO, fill=False, ls=":", lw=0.9, color="0.45"))
        # 逐个听点绘制半径为 R 的检测圆盘
        for p in pts:
            # 画出当前听点的检测圆盘（实线、半透明）
            ax.add_patch(plt.Circle(p, R, fill=False, ls="-", lw=0.5, color=color, alpha=0.7))
        # 用红点标出所有听点位置
        ax.plot([p[0] for p in pts], [p[1] for p in pts], "r.", ms=7)
        # 设置子图标题、等比例坐标轴与浅色网格
        ax.set_title(title); ax.set_aspect("equal"); ax.grid(alpha=0.25)
        # 固定坐标轴范围为 +-2000 m
        ax.set_xlim(-2000, 2000); ax.set_ylim(-2000, 2000)
    # 设置整图标题
    fig.suptitle("Spatial coverage: detection disks cover the 1800 m target disk")
    # 紧凑布局、保存 PNG 到 figures 目录、关闭图形释放内存
    fig.tight_layout(); fig.savefig(FIG_DIR / "q3_covering.png", dpi=150); plt.close(fig)


# ---------------------------------------------------------------------------
# 位置估计（线性最小二乘：到各测向线垂直距离平方和最小）
# ---------------------------------------------------------------------------
# 线性最小二乘定位：最小化源到各测向线垂直距离的平方和
def lsq_localize(points, bearings_deg):
    """A x ≈ d，其中第 i 行 = [sinθᵢ, -cosθᵢ]，dᵢ = pᵢ·(sinθᵢ, -cosθᵢ)。"""
    # 初始化法方程系数矩阵 A 与右端向量 d
    A, d = [], []
    # 逐测向线构造线性方程行
    for p, th in zip(points, bearings_deg):
        # 测向方向向量法向分量 sin(theta)
        a = math.sin(math.radians(th))
        # 测向方向向量法向分量 -cos(theta)
        c = -math.cos(math.radians(th))
        # 记录系数行 [a, c]
        A.append([a, c])
        # 记录右端 p 点乘 (a,c)，即听点在法向上的投影
        d.append(a * p[0] + c * p[1])
    # 转成 numpy 数组供 lstsq 求解
    A = np.array(A); d = np.array(d)
    # 最小二乘求解 A x ~= d，取解向量 x（忽略残差等其余返回值）
    x, *_ = np.linalg.lstsq(A, d, rcond=None)
    # 返回源位置估计
    return x


# Stansfield 加权最小二乘定位：先等权初估，再按 1/r^2 重加权逼近极大似然
def stansfield_localize(points, bearings_deg):
    """Stansfield 加权最小二乘：先等权求初值，再按 1/r² 重加权（近似极大似然）。

    线性化残差是"垂直距离"（米），其标准差 ∝ r·σ，故权重 1/(σ²r²) 白化；
    σ 相同可略，仅用 1/r²。扫满后源是超定（≥3 测向），加权可提升精度。
    """
    # 先用等权最小二乘求源位置的初值
    x1 = lsq_localize(points, bearings_deg)
    # 初始化加权后的系数矩阵与右端向量
    A, d = [], []
    # 逐测向线按与初值的距离重新加权
    for p, th in zip(points, bearings_deg):
        # 测向方向法向分量 sin(theta)
        a = math.sin(math.radians(th))
        # 测向方向法向分量 -cos(theta)
        c = -math.cos(math.radians(th))
        # 初值到该听点的距离 r（下限 1 m 防除零）
        r = max(math.hypot(x1[0] - p[0], x1[1] - p[1]), 1.0)
        # WLS weight is 1/r^2, hence the least-squares row scale is 1/r.
        # 权重 1/r^2 对应行缩放因子 1/r，用于白化测距残差
        scale = 1.0 / r
        # 记录按 scale 缩放后的系数行
        A.append([a * scale, c * scale])
        # 记录按 scale 缩放后的右端
        d.append((a * p[0] + c * p[1]) * scale)
    # 转成 numpy 数组
    A = np.array(A); d = np.array(d)
    # 加权最小二乘求解并返回源位置估计
    x, *_ = np.linalg.lstsq(A, d, rcond=None)
    # 返回源位置估计
    return x


# 几何基准定位：两两测向线求交并取平均，作为对比基线
def geometric_localize(points, bearings_deg):
    """几何基准：两两测向线求交，取平均。"""
    # 收集两两测向线的交点
    pts = []
    # 外层循环枚举第一条测向线
    for i in range(len(points)):
        # 内层循环枚举第二条测向线（i<j 避免重复）
        for j in range(i + 1, len(points)):
            # 第 i 条测向线（由听点与示向度确定）
            L1 = line_through(points[i], bearings_deg[i])
            # 第 j 条测向线
            L2 = line_through(points[j], bearings_deg[j])
            # 解包两条线的标准形式参数 (a,b,d)
            a1, b1, d1 = L1; a2, b2, d2 = L2
            # 两线系数矩阵行列式，用于判断是否平行
            det = a1 * b2 - a2 * b1
            # 近平行（行列式约等于0）时交点不稳定，跳过
            if abs(det) < 1e-9:
                # 跳过该对测向线
                continue
            # 用克拉默法则求两线交点坐标并收集
            pts.append(np.array([(d1 * b2 - d2 * b1) / det, (a1 * d2 - a2 * d1) / det]))
    # 有交点则取平均作为定位结果，否则返回 None
    return np.mean(pts, axis=0) if pts else None


# ---------------------------------------------------------------------------
# 动态规划：Held-Karp 精确 TSP（O(n²2ⁿ)），用于清除顺序
# ---------------------------------------------------------------------------
# Held-Karp 精确求解最短路径（开路径或闭回路），用于清除顺序优化
def held_karp(dist_matrix, start=0, closed=True):
    """dp[mask][j] = 从 start 出发访问 mask 各点恰好一次、终点 j 的最短路径长。"""
    # 点数 n
    n = len(dist_matrix)
    # 无穷大常量，表示不可达
    INF = float("inf")
    # dp[mask][j] 初始化为无穷大：访问集合 mask 且终点 j 的最短长度
    dp = [[INF] * n for _ in range(1 << n)]
    # 基础情形：只访问点 j 时代价为 start 到 j 的直接距离
    for j in range(n):
        # 记录只含单个点 j 的最短路径代价
        dp[1 << j][j] = dist_matrix[start][j]
    # parent[mask][j] 记录到达 (mask,j) 的前驱点，用于回溯路径
    parent = [[-1] * n for _ in range(1 << n)]
    # 按集合递增顺序枚举所有子集 mask
    for mask in range(1 << n):
        # 枚举子集 mask 的终点 j
        for j in range(n):
            # 若 j 不在 mask 中则跳过
            if not (mask >> j) & 1:
                # 跳过不含 j 的子集
                continue
            # prev = mask 去掉 j 后的前驱子集
            prev = mask & ~(1 << j)
            # 空集时无前驱，跳过（已由基础情形处理）
            if prev == 0:
                # 跳过空集情形
                continue
            # best/pk 记录 prev 子集下最优代价与前驱点
            best, pk = INF, -1
            # 枚举 prev 子集中的前驱终点 k
            for k in range(n):
                # 只考虑 prev 中存在的点 k
                if (prev >> k) & 1:
                    # 经 k 到 j 的代价 = dp[prev][k] + 距离(k,j)
                    v = dp[prev][k] + dist_matrix[k][j]
                    # 保留更小代价及其前驱 k
                    if v < best:
                        # 更新最优代价与前驱点
                        best, pk = v, k
            # 记录 (mask,j) 的最优代价
            dp[mask][j] = best
            # 记录 (mask,j) 的前驱点
            parent[mask][j] = pk
    # 全集 mask = 2^n - 1
    full = (1 << n) - 1
    # 闭回路：终点需回到 start
    if closed:
        # 选择使总代价最小的终点 end（含回 start 的距离）
        end = min(range(n), key=lambda j: dp[full][j] + dist_matrix[j][start])
        # 闭回路总代价 = 到达 end 加回到 start 的距离
        cost = dp[full][end] + dist_matrix[end][start]
    # 开路径分支：无需回到 start
    else:
        # 开路径：直接选 dp[full][j] 最小的终点
        end = min(range(n), key=lambda j: dp[full][j])
        # 开路径总代价 = dp[full][end]
        cost = dp[full][end]
    # 回溯顺序（不含 start）
    # 从终点 end 沿 parent 反向回溯，收集访问顺序
    order, mask, j = [], full, end
    # 反复剥离终点直到 mask 为空
    while mask:
        # 当前终点 j 加入顺序
        order.append(j)
        # 取 (mask,j) 的前驱点
        k = parent[mask][j]
        # 从 mask 中移除 j
        mask &= ~(1 << j)
        # 前驱成为新的终点
        j = k
    # 返回总代价与反向还原后的访问顺序（不含 start）
    return cost, list(reversed(order))


# 贪心最近邻顺序：作为与 DP 对比的启发式
def nearest_neighbor_order(points, start):
    """贪心最近邻（与 DP 对比的启发式）。"""
    # 剩余未访问点列表
    pts = list(points)
    # 当前位置初始化为起点 start
    cur = start
    # 访问顺序（存的是相对 pts 的下标）
    order = []
    # 直到所有点都被访问
    while pts:
        # 在剩余点中选择距当前位置最近的点的下标
        i = min(range(len(pts)), key=lambda i: dist(cur, pts[i]))
        # 记录该下标
        order.append(i)
        # 弹出该点作为新当前位置
        cur = pts.pop(i)
    # 返回贪心访问顺序
    return order


# ---------------------------------------------------------------------------
# 问题三算法：听巡 → 交会定位 → Held-Karp 清除
# ---------------------------------------------------------------------------
# 逼近清除：从估计点出发，沿最新示向度步进逼近并尝试清除
def _approach_clear(sim, ch, point, max_iter=20, step=400.0):
    """逼近清除（场强逼近 / bearing-only homing）：从估计点出发，沿最新示向度逼近。

    每轮先尝试清除（若已在 20 m 清除半径内则直接成功），否则测向、沿最新示向度前进 step；
    示向度翻转（≈180°）说明已越过源，减半步长回折。步长由调用方按定位精度给定：
    双测向 Stansfield 估计（误差≈10 m）传 20 m 小步；单测向场强逼近传 300 m 大步。
    """
    # 当前位置初始化为估计点（浮点数组）
    cur = np.array(point, dtype=float)
    # 上一轮的示向度，用于检测是否已越过源
    prev_svd = None
    # 最多迭代 max_iter 轮
    for _ in range(max_iter):
        # 先尝试直接清除：若在清除半径内则成功返回
        if sim.clear(cur[0], cur[1], ch)["clear_result"] == "success":
            # 清除成功立即返回 True
            return True
        # 测量当前位置该频道的场强/示向度
        m = sim.measure(cur[0], cur[1], ch)
        # 若已进入近距命中范围，立即清除并返回结果
        if m["measure_result"] == "near":
            # 近距命中后立即清除并返回是否成功
            return sim.clear(cur[0], cur[1], ch)["clear_result"] == "success"
        # 既非近距也非方向（超出测向范围）说明估计点严重偏离
        if m["measure_result"] != "direction":
            # 估计点严重偏离（>R），源不可达，返回失败
            return False                          # 估计点严重偏离（>R），源不可达
        # 取本次示向度
        svd = m["svd_deg"]
        # 示向度相对上轮翻转约 180 度说明已越过源，需回折
        if prev_svd is not None and abs((svd - prev_svd) % 360.0 - 180.0) < 30.0:
            # 已越过源，减半步长（下限 20 m）回折
            step = max(step / 2.0, 20.0)          # 已越过源，减半步长回折
        # 示向度转弧度
        a = math.radians(svd)
        # 沿示向度方向前进一步
        cur = cur + step * np.array([math.cos(a), math.sin(a)])
        # 更新上一轮示向度
        prev_svd = svd
    # 迭代耗尽仍未清除则返回失败
    return False


# 在不确定圆盘上生成蛇形方格网覆盖点，用于扫盘清除
def _disk_cover_points(center, radius=112.0, spacing=28.0):
    """Serpentine square grid covering the local uncertainty disk.

    The grid is generated on the whole bounding square, rather than clipped
    to the disk.  Clipping would leave boundary points more than 20 m from
    the nearest grid point and would invalidate the clear-radius certificate.
    """
    # 中心点转成浮点数组
    center = np.asarray(center, dtype=float)
    # 收集所有网格点坐标
    rows = []
    # 沿 y 方向从 -radius 到 +radius 以 spacing 步长生成坐标值
    values = np.arange(-radius, radius + 0.5 * spacing, spacing)
    # 逐行（y 值）生成网格点
    for row_no, y in enumerate(values):
        # 复制 x 方向坐标值（与 y 相同的等距序列）
        x_values = values.copy()
        # 奇数行反转 x 顺序，形成蛇形路径减少往返里程
        if row_no % 2:
            # 反转该行 x 顺序实现蛇形扫描
            x_values = x_values[::-1]
        # 把该行所有 (x,y) 网格点平移到 center 并加入结果
        rows.extend(center + np.array([x, y]) for x in x_values)
    # 返回全部网格点
    return rows


# 生成单测向可行楔形走廊的覆盖点：+-1 度张角、0..1500 m 范围内
def _bearing_corridor_points(origin, beta_deg, max_range=R_EFF_MAX,
                             spacing=28.0):
    """Cover the full +/-1 degree, 0..1500 m single-bearing feasible wedge."""
    origin = np.asarray(origin, dtype=float)
    # 原点转成浮点数组
    angle = math.radians(beta_deg)
    # 示向度转弧度
    forward = np.array([math.cos(angle), math.sin(angle)])
    # 沿示向度的单位方向向量
    normal = np.array([-forward[1], forward[0]])
    # 垂直于示向度的单位法向量（横向）
    points = []
    # 收集覆盖点
    for column, along in enumerate(np.arange(spacing / 2.0,
                                              # 沿射线方向（along）从 spacing/2 到 max_range 逐列推进
                                              max_range + spacing / 2.0,
                                              spacing)):
        half_width = along * math.tan(math.radians(1.0)) + 1.0
        # 该列处 +-1 度张角对应的半宽（加 1 m 余量）
        lateral_allowance = math.sqrt(20.0 ** 2 - (spacing / 2.0) ** 2)
        # 横向允许覆盖半径：保证相邻点间距覆盖 20 m 清除半径
        n_side = int(math.ceil(max(0.0, half_width - lateral_allowance) /
                               # 该列每侧需要的横向偏移点数（至少 0）
                               spacing))
        # 横向偏移序号范围 -n_side..n_side
        offsets = list(range(-n_side, n_side + 1))
        # 奇数列反转横向顺序，形成蛇形扫描
        if column % 2:
            # 反转该列横向顺序
            offsets.reverse()
        # 按横向偏移生成该列所有覆盖点
        for offset in offsets:
            # 生成一个覆盖点并加入列表
            points.append(origin + along * forward + offset * spacing * normal)
    # 返回整个楔形走廊的覆盖点
    return points




# 依次尝试在给定点集上清除指定频道，任一成功即返回 True
def _clear_at_points(sim, ch, points):
    # 逐个候选点尝试清除
    for point in points:
        # 在候选点执行清除操作
        result = sim.clear(float(point[0]), float(point[1]), ch)
        # 清除成功立即返回 True
        if result["clear_result"] == "success":
            # 返回清除成功
            return True
    # 全部失败返回 False
    return False


# 定位区域网格间距（米），见下方覆盖保证注释
REGION_GRID_SPACING = 28.0
# 28 m 方格网：任一点到最近格点的距离 ≤ spacing/√2 = 19.80 m < 20 m（清除半径）。
# 网格最大覆盖半径阈值：可行域过大时改用逼近清除，避免网格规模爆炸
REGION_GRID_MAX_RADIUS = 160.0


# 由观测构造源位置的可行域（问题 1 的凸多边形交会区域）
def feasible_region(observations):
    """交会定位区域（问题 1 的凸多边形，即源位置可行域）。

    每条测向线两侧各 ±1° 构成误差边界；真实源必落在这些楔形的交内。
    返回按角度排序的顶点数组，退化时返回 None。
    """
    # 少于 2 个测向时无法构成区域，返回 None
    if len(observations) < 2:
        # 返回 None 表示无可行域
        return None
    # 调用 geo.localization_region 求交会区域顶点
    verts = localization_region([o[0] for o in observations],
                                [o[1] for o in observations])
    # 区域退化（无解或顶点不足 3 个）时返回 None
    if verts is None or len(verts) < 3:
        # 返回 None 表示区域退化
        return None
    # 转成浮点数组返回可行域顶点
    return np.asarray(verts, dtype=float)


# 在可行域外接矩形上打 28 m 方格网，并按离 anchor 由近及远排序
def _region_grid(verts, spacing=REGION_GRID_SPACING, anchor=None):
    """在可行域外接矩形上打方格网，按"离 anchor 由近及远"排序。

    网格覆盖整个外接矩形，故可行域内任一点都落在某个网格单元中，
    到该单元四个格点之一的距离 ≤ spacing/√2 < 20 m：遍历完必能清除。
    """
    # 顶点转成浮点数组
    V = np.asarray(verts, dtype=float)
    # 外接矩形左下角
    lo = V.min(axis=0)
    # 外接矩形右上角
    hi = V.max(axis=0)
    # 未指定 anchor 时默认取区域中心
    if anchor is None:
        # 默认 anchor 为顶点均值（区域中心）
        anchor = V.mean(axis=0)
    # anchor 转成浮点数组
    anchor = np.asarray(anchor, dtype=float)

    # 内部函数：在一维区间 [low, high] 上按 spacing 生成等距格点
    def axis(low, high):
        # 需要的等距段数
        n = int(math.ceil(max(0.0, high - low) / spacing))
        # 返回含端点在内的 n+1 个等距格点
        return low + spacing * np.arange(n + 1)

    # 分别在 x、y 方向生成一维格点
    xs, ys = axis(lo[0], hi[0]), axis(lo[1], hi[1])
    # 笛卡尔积生成完整矩形网格点
    pts = [np.array([x, y]) for y in ys for x in xs]
    # 有 anchor 时按距离由近及远排序
    if anchor is not None:
        # 保持**完整**网格：删掉估计点附近的格点会在该处留下 >20 m 的空洞，
        # 破坏"可行域内任一点到最近格点 ≤ 28/√2 = 19.80 m < 20 m"的覆盖保证。
        # 估计点本身在 robust_clear 第 (1) 步已经试过，重复一次只多 3 s，可以接受。
        # 按离 anchor 距离由近及远排序，让清除优先尝试近处点
        pts.sort(key=lambda p: float(np.hypot(p[0] - anchor[0], p[1] - anchor[1])))
    # 返回排序后的网格点
    return pts


# 保证性清除：先试加权最小二乘估计点，再退化到定位区域网格/逼近清除兜底
def robust_clear(sim, ch, estimate, observations, fast=False):
    """保证性清除：先用加权最小二乘估计点，再退化为**定位区域网格**。

    与旧版的最大差别：兜底不再遍历 224 m 见方的固定圆盘，也不遍历 1500 m 长的
    示向度走廊，而是只用问题 1 给出的**交会定位区域**——它的最小包围圆半径
    中位数仅 27 m（见 est_probe），因此网格规模小一个量级，且依然是"遍历完必中"
    的保证：真实源必在可行域内，可行域被 28 m 网格以 19.8 m 的半径覆盖。

    单测向（无可行域）时退化为沿示向度的场强逼近 + 有界楔形走廊扫描。
    """
    # estimate 转成浮点数组（可能为 None）
    est = None if estimate is None else np.asarray(estimate, dtype=float)

    # (1) 快速路径：加权最小二乘点命中（约 86% 的源误差已 ≤ 20 m）
    # 有估计点则先在其位置直接尝试清除（多数源误差已 <=20 m）
    if est is not None and _clear_at_points(sim, ch, [est]):
        # 快速路径命中即成功返回
        return True

    # (2) 多测向：定位区域网格（按离估计点由近及远），保证收敛
    # 由观测构造可行域
    region = feasible_region(observations)
    # 存在可行域时进入网格/逼近清除分支
    if region is not None:
        # 求可行域最小包围圆的圆心 center 与半径 radius
        _, center = min_enclosing_circle(region)
        # 实际半径取各顶点到圆心的最大距离
        radius = max(dist(p, center) for p in region) if center is not None else None
        # 半径在阈值内才走网格兜底（否则网格规模过大）
        if radius is not None and radius <= REGION_GRID_MAX_RADIUS:
            # 在可行域网格上按离估计点近远顺序逐个尝试清除
            if _clear_at_points(sim, ch, _region_grid(region, anchor=est)):
                # 网格遍历清除成功即返回
                return True
        # 可行域过大（交会角极差）：改由估计点短程逼近，避免网格爆炸
        # 可行域过大时改用逼近清除（步长按 fast 取小值）
        if est is not None and _approach_clear(
                sim, ch, est, max_iter=10 if fast else 14,
                step=45.0 if fast else 30.0):
            # 逼近清除成功即返回
            return True

    # (3) 单测向兜底：沿示向度射线步进逼近，最后才扫有界楔形走廊。
    # 注：试过"横向偏移取得第二示向度再交会跳转"，实测**更差**——源本来就在射线上
    # （横向偏差 ≤ r·tan1° ≤ 26 m），沿射线步进才是最短路径，横向偏移反而多走一段。
    # 取第一个测向的听点位置与示向度
    origin, beta_deg = observations[0]
    # 无估计点时用单测向中点估计构造初始估计
    if est is None:
        # 构造单测向中点估计
        est = _single_bearing_estimate(origin, beta_deg)
    # 沿示向度大步逼近清除（步长按 fast 取 450/300 m）
    if est is not None and _approach_clear(sim, ch, est, max_iter=8,
                                           step=450.0 if fast else 300.0):
        # 逼近清除成功即返回
        return True
    # 最后兜底：扫描整个有界楔形走廊覆盖点
    return _clear_at_points(sim, ch,
                            _bearing_corridor_points(origin, beta_deg))


# 在单个听点扫全部频道，就地更新 obs（方向观测）与 near（近距命中）
def _scan_channels(sim, point, obs, near, first_hit_only=False):
    """在单个听点扫频道，就地更新 obs / near。

    冗余削减：某频道已取得 ≥2 个稳定示向度（交会角 ≥35°）后，后续听点跳过该频道。
    未检测到的频道必须扫满全部听点——覆盖证书要求每个听点都被检查过，
    否则"某源只在最后一个听点可达"的情形会被漏掉。
    """
    from rl import needs_measurement

    # 遍历所有频道
    for ch in CHANNELS:
        # 已近距命中的频道直接跳过（无需再测向）
        if ch in near:
            # 跳过已近距命中的频道
            continue
        # 取该频道已累积的观测列表
        observations = obs.get(ch)
        # 已有稳定交会角（>=2 测向且角度足够）则跳过，减少冗余检测
        if observations is not None and not needs_measurement(observations):
            # 已有稳定交会角，跳过冗余检测
            continue                           # 已有稳定交会角，跳过冗余检测
        # 在当前听点测量该频道
        r = sim.measure(point[0], point[1], ch)
        # 测得方向：记录 (听点位置, 示向度) 到 obs
        if r["measure_result"] == "direction":
            # 把本次方向观测追加到该频道观测列表
            obs.setdefault(ch, []).append((np.asarray(point, dtype=float),
                                           r["svd_deg"]))
        # 近距命中：从 obs 移除该频道，登记到 near
        elif r["measure_result"] == "near":
            # 从 obs 移除该频道（已改为近距命中）
            obs.pop(ch, None)
            # 登记近距命中位置到 near
            near.setdefault(ch, np.asarray(point, dtype=float))


# 听巡：逐个听点扫频道，汇总返回 (obs, near)
def _listening_tour(sim, listening):
    """听巡：逐个听点扫频道，返回 (obs, near)。"""
    # 初始化观测与近距字典
    obs, near = {}, {}
    # 逐听点扫描频道并更新 obs/near
    for pt in listening:
        # 在单个听点扫全部频道
        _scan_channels(sim, pt, obs, near)
    # 返回观测结果
    return obs, near


# 求听点访问顺序的下标序列：小规模 Held-Karp 精确，大规模 2-opt 启发式
def _order_listening_idx(points):
    """听点访问顺序的**下标**序列：小规模 Held-Karp 精确解；大规模 2-opt 启发式。"""
    # 听点列表前补原点，构成含起点的完整停靠集
    pts = [np.array([0.0, 0.0])] + [np.array(p, dtype=float) for p in points]
    # 点数超过 18 时用启发式开路径优化，避免 DP 指数爆炸
    if len(pts) > 18:
        # 返回 2-opt 启发式开路径顺序下标
        return list(optimized_open_order(points, start=np.zeros(2)))
    # 小规模：构造欧氏距离矩阵
    dm = np.array([[dist(a, b) for b in pts] for a in pts])
    # Held-Karp 求从原点出发的最优开路径顺序
    _, order = held_karp(dm, start=0, closed=False)
    # 去掉原点并把其余下标减 1 映射回原 points 下标
    return [i - 1 for i in order if i > 0]


# 听点顺序（坐标列表版本，供旧接口使用）
def _order_listening(points):
    """听点顺序（返回坐标列表，供旧接口使用）。"""
    # 用下标序列映射回坐标列表
    return [points[i] for i in _order_listening_idx(points)]


# 单测向源的位置估计：取测向射线与目标圆盘交区间的中点
def _single_bearing_estimate(point, bearing_deg):
    """Midpoint of the feasible range along one bearing ray.

    A direction-only hit implies a positive range no larger than the
    effective-radius upper bound.  Intersecting that interval with the target
    disk gives a much better routing representative than the old fixed 750 m
    point, while the actual clear operation still uses the recorded bearing
    corridor as its guaranteed fallback.
    """
    # 听点位置转浮点数组
    p = np.asarray(point, dtype=float)
    # 测向射线的单位方向向量
    u = np.array([math.cos(math.radians(bearing_deg)),
                  math.sin(math.radians(bearing_deg))])
    # 听点在射线方向上的投影 b = p 点乘 u
    b = float(np.dot(p, u))
    # 一元二次方程判别式：求射线与目标圆盘交点
    disc = b * b + R_TARGET * R_TARGET - float(np.dot(p, p))
    # 判别式 <=0（射线与圆盘无交）时退化为取固定中点
    if disc <= 0.0:
        # 无交时取近距到最大有效半径的中点
        return p + 0.5 * (NEAR_R + R_EFF_MAX) * u
    # 判别式开方
    root = math.sqrt(disc)
    # The measured direction only implies that the source is outside the
    # near-clear threshold; R_EFF_MIN is not a lower bound on source range.
    # 沿射线方向的可达区间下限（至少近距半径）
    lo = max(NEAR_R, -b - root)
    # 可达区间上限（不超过最大有效半径）
    hi = min(R_EFF_MAX, -b + root)
    # 区间颠倒（数值异常）时重算并强制 clamp
    if hi < lo:
        # 重算下限
        lo = max(NEAR_R, -b - root)
        # 重算上限
        hi = min(R_EFF_MAX, -b + root)
    # 仍颠倒则退化为固定中点估计
    if hi < lo:
        # 区间无效时返回固定中点估计
        return p + 0.5 * (NEAR_R + R_EFF_MAX) * u
    # 返回可达区间中点作为估计位置
    return p + 0.5 * (lo + hi) * u


# ---------------------------------------------------------------------------
# 在线"搜索—清除"交织：最廉插入调度
# ---------------------------------------------------------------------------
# 把观测汇总成待清除目标字典 {频道: (点估计, 该频道观测列表)}
def target_estimates(obs, near, ready_only=False):
    """把观测转成待清除目标 {ch: (点估计, 该频道的观测)}。

    `ready_only=True` 时只返回**几何已足够好**的源（≥2 个稳定示向度或近距命中），
    供听巡途中顺路清除；听巡结束后再以 `ready_only=False` 收尾。
    这样单测向源会先继续听巡争取第二测向，而不是立刻触发昂贵的单测向兜底。
    """
    from rl import needs_measurement

    # 收集待清除目标
    targets = {}
    # 遍历所有有观测的频道
    for ch, olist in obs.items():
        # ready_only 且该频道仍需补测向时跳过（留给听巡争取第二测向）
        if ready_only and needs_measurement(olist):
            # 跳过仍需补测向的单测向频道
            continue
        # >=2 测向：用 Stansfield 加权最小二乘定位
        if len(olist) >= 2:
            # 计算 Stansfield 加权最小二乘估计
            pt = stansfield_localize([o[0] for o in olist], [o[1] for o in olist])
        # 仅 1 测向的分支
        else:
            # 单测向中点估计
            pt = _single_bearing_estimate(olist[0][0], olist[0][1])
        # 估计有效则登记目标
        if pt is not None:
            # 登记目标频道及其估计与观测
            targets[ch] = (np.asarray(pt, dtype=float), olist)
    # 遍历近距命中的频道
    for ch, pt in near.items():
        # 近距命中频道直接登记为可清除目标（观测记为 None）
        targets.setdefault(ch, (np.asarray(pt, dtype=float), None))
    # 返回目标字典
    return targets



# 顺路清除的"增量里程"上限：超过该值的源不在听巡途中清除，留到听巡结束后统一巡回。
# 依据（见 benchmark 的 detour_limit 灵敏度表）：听点集是**环**时（问题三），源分布在
# 环内外两侧，径向进出会把环走碎，需要上限；听点集是**铺满圆域的哈密顿路径**时
# （问题四），源多数紧贴路径，上限越松越好。500 m 是两者兼顾的取值。
# 顺路清除的增量里程阈值常量（米），供 schedule_clears 运行时读取
DETOUR_LIMIT = 300.0

# 题设源总数上界（频道互异，10–16 之间）。探满 16 个频道即可证明其余为空。
# 源总数上界常量：探满 16 个频道即可证明其余频道为空
MAX_SOURCES = 16


# 在线最廉插入调度：把已知源插到剩余行程中增量里程最小的位置
def schedule_clears(plan, start_pos, targets, done, limit=None):
    """在线最廉插入：把已知但尚未排程的源插到剩余行程中代价最小的位置。

    插入位置 i 的**增量里程** = d(prev, S) + d(S, next) - d(prev, next)，
    prev/next 取行程中该位置两侧停靠的实际位置。只有当最小增量 ≤ limit
    时才排入行程（"顺路清除"），否则推迟到听巡结束后的收尾巡回。
    行程是**持久**的，已排入的停靠不会因下一步重规划而丢失。
    """
    # 未显式给 limit 时用默认增量里程阈值
    if limit is None:
        # 运行期读取默认阈值，便于灵敏度实验调整
        limit = DETOUR_LIMIT                  # 运行期读取，便于灵敏度实验调整
    # 起始位置转浮点数组
    start_pos = np.asarray(start_pos, dtype=float)
    # 行程中已排程的清除频道集合
    planned = {s[1] for s in plan if s[0] == "clear"}
    # 遍历所有待清除目标频道
    for ch, (S, _ol) in targets.items():
        # 已清除或已排程的频道跳过
        if ch in done or ch in planned:
            # 跳过已处理频道
            continue
        # best_i/best_c 记录最优插入位置与最小增量
        best_i, best_c = len(plan), None
        # prev 初始为起始位置，逐停靠位置计算插入代价
        prev = start_pos
        # 枚举行程中每个插入位置 i
        for i, stop in enumerate(plan):
            # 该位置的下一停靠坐标
            nxt = stop[2]
            # 插入代价 = 绕行该源的新增里程
            c = dist(prev, S) + dist(S, nxt) - dist(prev, nxt)
            # 更新最小增量及其位置
            if best_c is None or c < best_c:
                # 记录最优插入位置与增量
                best_i, best_c = i, c
            # 更新 prev 为当前停靠
            prev = nxt
        # 追加到行程末尾的增量里程
        tail = dist(prev, S)
        # 若末尾插入更便宜，则选末尾
        if best_c is None or tail < best_c:
            # 末尾插入为最优时更新位置与增量
            best_i, best_c = len(plan), tail
        # 最小增量超过阈值：不顺路，留到收尾巡回
        if limit is not None and best_c > limit:
            # 不顺路，留到收尾巡回
            continue                            # 不顺路，留到收尾巡回
        # 在最优位置插入清除停靠 (clear, 频道, 坐标)
        plan.insert(best_i, ("clear", ch, S))


# 执行一个清除停靠：近距命中直接清除，否则走 robust_clear 保证性清除
def _execute_clear(sim, stop, targets, logger, fast):
    """执行一个清除停靠，返回是否成功。"""
    # 取该停靠的频道
    ch = stop[1]
    # 取该频道的点估计与观测列表
    pt, olist = targets[ch]
    # 观测为空表示近距命中，直接光学清除
    if olist is None:                          # 近距命中：可直接光学清除
        # 近距命中直接清除并记录结果
        ok = sim.clear(float(pt[0]), float(pt[1]), ch)["clear_result"] == "success"
    # 有观测的分支
    else:
        # 有观测则走保证性清除流程
        ok = robust_clear(sim, ch, pt, olist, fast=fast)
    # 有日志记录器时记录定位依据
    if logger:
        # 记录定位依据（论文与复盘需要"每个源用了几个测向、什么方式定的位"）
        # 有观测列表则按测向数记录定位方法与估计坐标
        if olist:
            # 记录测向数与定位方式及估计坐标
            logger.source(ch, bearings=len(olist),
                          method="stansfield" if len(olist) >= 2 else "single",
                          estimate=[round(float(pt[0]), 1), round(float(pt[1]), 1)])
        # 无观测（近距命中）的分支
        else:
            # 记录 0 测向与 near 方式及估计坐标
            logger.source(ch, bearings=0, method="near",
                          estimate=[round(float(pt[0]), 1), round(float(pt[1]), 1)])
        # 记录该源是否被清除
        logger.source(ch, cleared=ok)
    # 返回清除成功与否
    return bool(ok)


# 汇总报告：登记真实源信息并返回清除统计结果
def _finish_report(sim, obs, near, cleared, verbose, logger):
    # 有日志记录器时登记每个真实源的位置与类型
    if logger is not None:
        # 用 try 包裹，兼容没有 sources 属性的模拟器
        try:
            # 逐个真实源登记频道、真实坐标与类型
            for s in sim.sources:
                # 登记单个真实源信息
                logger.source(s["channel"],
                              true=[round(s["pos"][0], 1), round(s["pos"][1], 1)],
                              kind=s["kind"])
        # 属性不存在或类型不匹配时静默跳过
        except (AttributeError, TypeError):
            # 忽略异常继续
            pass
    # 冗长模式打印发现的源数与清除数
    if verbose:
        # 打印发现与清除统计
        print(f"  发现 {len(obs) + len(near)} 源，清除 {cleared}")
    # 返回统计字典：清除数、发现数、虚拟耗时
    return {"cleared": cleared, "detected": len(obs) + len(near),
            "virtual_time_s": round(sim.virtual_time, 1)}


# 统一的搜索-清除在线交织任务控制主循环
def run_mission(sim, listening, next_point, scan_point, verbose=False,
                logger=None, fast=False, detour_limit=None):
    """统一的"搜索—清除"在线交织任务控制。

    `next_point(visited, obs, near)` 给出下一个听点下标（-1 表示听巡结束）；
    `scan_point(idx, obs, near)` 在该听点扫频道并就地更新 obs/near。

    行程 `plan` 是**持久**的：每次执行完一个停靠后，把新就绪的源按最廉插入
    放到行程中代价最小的位置。因此清除发生在真正的"顺路"位置，而不是听巡
    结束后再补一趟专门的清除巡回（后者要多走约 2~5 km）。
    """
    # 初始化观测与近距字典
    obs, near = {}, {}
    # 已访问听点集合与已清除频道集合
    visited, done = set(), set()
    # 已清除源计数
    cleared = 0

    # 初始行程：按引导序排好的全部听点停靠 (listen, 下标, 坐标)
    plan = [("listen", j, np.asarray(listening[j], dtype=float))
            for j in _guide_order(listening)]
    # 听巡是否结束的标志
    listening_over = False

    # 主循环：反复弹出并执行行程队首停靠，直到行程为空
    while plan:
        # 题设源总数上界为 16（频道互异）。一旦探明 16 个不同频道，其余频道必为空，
        # 剩余听点与频道扫描都不必再做——这是**可严格证明**的提前收工，不是近似。
        # 探满 16 个频道即提前收工（其余频道必为空）
        if len(obs) + len(near) >= MAX_SOURCES:
            # 提前退出主循环
            break
        # 弹出队首停靠
        stop = plan.pop(0)
        # 听点停靠：执行扫描或调整顺序
        if stop[0] == "listen":
            # 听巡已结束则跳过剩余听点停靠
            if listening_over:
                # 跳过剩余听点
                continue
            # 策略给出的下一个听点若与引导序不同，把它换到当前位（保留清除停靠位置）
            # 由策略决定下一个要访问的听点下标（-1 表示听巡结束）
            idx = next_point(visited, obs, near)
            # 策略返回 -1：标记听巡结束并跳过
            if idx < 0:
                # 标记听巡结束
                listening_over = True
                # 跳过本次听点处理
                continue
            # 策略指定听点与当前队首不同则交换到队首
            if idx != stop[1]:
                # 在行程中查找策略指定的听点停靠
                for m, other in enumerate(plan):
                    # 找到指定听点停靠则交换到当前位
                    if other[0] == "listen" and other[1] == idx:
                        # 交换两个停靠位置
                        plan[m], stop = stop, other
                        # 交换完成，跳出查找
                        break
            # 在该听点扫频道并更新 obs/near
            scan_point(stop[1], obs, near)
            # 记录该听点已访问
            visited.add(stop[1])
        # 清除停靠的分支
        else:
            # 执行清除并累加成功计数
            cleared += _execute_clear(sim, stop, target_estimates(obs, near),
                                      logger, fast)
            # 记录该频道已清除
            done.add(stop[1])
        # 新就绪且顺路的源立刻排入行程
        # 重新汇总当前就绪目标并做最廉插入调度
        targets = target_estimates(obs, near, ready_only=True)
        # 按增量里程阈值把顺路源排入行程
        schedule_clears(plan, sim.position, targets, done,
                        detour_limit if detour_limit is not None else DETOUR_LIMIT)

    # 收尾：听巡结束后仍存活的已知源（含仅单测向者）。
    # 这些源被"顺路阈值"推迟到这里，此时它们的位置全部已知，故按**开路径 2-opt**
    # 统一巡回（而非贪心最近邻），这是最后一段可优化的里程。
    # 汇总全部已就绪目标（含单测向源）
    targets = target_estimates(obs, near)
    # 剩余未清除的频道列表
    rest = [ch for ch in targets if ch not in done]
    # 有剩余源则按开路径 2-opt 统一巡回清除
    if rest:
        # 收集剩余源的估计坐标
        pts = [targets[ch][0] for ch in rest]
        # 用 2-opt 求从当前位置出发的开路径访问顺序
        order = optimized_open_order(pts, start=np.asarray(sim.position, dtype=float))
        # 按顺序逐个清除
        for i in order:
            # 取第 i 个剩余源频道
            ch = rest[i]
            # 构造清除停靠
            stop = ("clear", ch, targets[ch][0])
            # 执行清除并累加成功计数
            cleared += _execute_clear(sim, stop, targets, logger, fast)
            done.add(ch)
# 记录该频道已清除

    # 返回最终统计报告
    return _finish_report(sim, obs, near, cleared, verbose, logger)


# 返回剩余听点的确定性引导访问顺序（下标）
def _guide_order(listening):
    """剩余听点的确定性引导序（下标）。"""
    # 直接调用听点顺序下标函数
    return _order_listening_idx(listening)


# 确定性搜索策略类：按 Held-Karp 最优顺序依次访问听点
class DeterministicSearch:
    """确定性听点序（Held-Karp 开路径最优序），供 run_mission 调用。"""

    # 构造器：保存模拟器、听点列表与访问顺序
    def __init__(self, sim, listening, seq):
        # 保存模拟器引用
        self.sim = sim
        # 保存听点坐标列表
        self.listening = listening
        # 保存访问顺序
        self.seq = seq

    # 给出下一个未访问的听点下标
    def next_point(self, visited, obs, near):
        # 按预定顺序找第一个未访问的听点
        for p in self.seq:
            # 返回第一个未访问的听点下标
            if p not in visited:
                # 返回该听点下标
                return p
        # 全部访问完返回 -1
        return -1

    # 在指定听点扫频道
    def scan_point(self, idx, obs, near):
        # 调用 _scan_channels 在该听点扫全部频道
        _scan_channels(self.sim, self.listening[idx], obs, near)


# 确定性策略入口：听巡（Held-Karp 最优顺序）+ 在线交织清除
def run_strategy(sim, listening_points=None, use_dp=True, verbose=False,
                 logger=None, fast=False, detour_limit=None):
    """确定性：听巡（Held-Karp 最优顺序）+ 在线交织清除。

    默认 7 点正七边形环（layout.q3_layout）：覆盖半径证书 998.92 m < R_min=1000 m，
    且自原点开行程仅 6199 m（13 点双环为 12362 m）。七边形环同时把"环心方向的
    单测向源"变成被 7 点同时观测的多测向源，故无需再补内环细化点。

    `detour_limit`：顺路清除的增量里程上限。听点集是**环**时（问题三）源分布在环
    内外两侧，径向进出会把环走碎，需有限上限（默认 300 m）；听点集是**铺满圆域的
    哈密顿路径**时（问题四）源多数紧贴路径，上限越松越好（传 inf 等价于全部顺路清除）。
    """
    # 听点坐标列表：用传入的或默认 q3_layout 布局
    listening = [np.asarray(p, dtype=float) for p in
                 (listening_points if listening_points is not None else q3_layout())]
    # 有日志记录器时用 LoggedSim 包装，记录听巡阶段日志
    if logger is not None:
        from log import LoggedSim
        # 包装模拟器以记录日志
        sim = LoggedSim(sim, logger, phase="listen")
    # 构造确定性搜索策略（Held-Karp 开路径顺序）
    search = DeterministicSearch(sim, listening, _order_listening_idx(listening))
    # 交给 run_mission 执行主循环
    return run_mission(sim, listening, search.next_point, search.scan_point,
                       verbose, logger, fast, detour_limit)


# RL 搜索策略类：Q-learning 智能体选择下一个听点
class RLSearch:
    """Q-learning 听点选择策略，供 run_mission 调用。"""

    # 构造器：保存模拟器与智能体，last 记录上一个听点下标
    def __init__(self, sim, agent):
        # 保存模拟器引用
        self.sim = sim
        # 保存 Q-learning 智能体
        self.agent = agent
        # 初始化上一个听点下标为 -1
        self.last = -1

    # 由智能体决定下一个听点下标
    def next_point(self, visited, obs, near):
        # 编码当前状态（上一个听点、已访问集合、观测、近距、频道）
        state = self.agent.encode(self.last, visited, obs, near,
                                  getattr(self.sim, "channel", 1))
        # 智能体以贪心策略选择动作
        action = self.agent.act(state, self.last, visited, greedy=True)
        # 停止动作返回 -1，否则返回动作对应的听点下标
        return -1 if action == self.agent.stop_action else int(action)

    # 在指定听点执行扫描并更新 last
    def scan_point(self, idx, obs, near):
        # 调用智能体的扫描逻辑（含 Q-learning 更新）
        self.agent.scan(self.sim, idx, obs, near)
        # 记录当前听点为上一个听点
        self.last = idx


# RL 主线入口：Q-learning 选听点 + 在线最廉插入交织清除
def run_strategy_rl(sim, agent, use_dp=True, verbose=False, logger=None,
                    fast=False, detour_limit=None):
    """RL 主线：Q-learning 选听点 + 在线最廉插入交织清除。"""
    # 有日志记录器时用 LoggedSim 包装，记录 RL 搜索阶段日志
    if logger is not None:
        from log import LoggedSim
        # 包装模拟器以记录 RL 阶段日志
        sim = LoggedSim(sim, logger, phase="rl_search")
    # 构造 RL 搜索策略
    search = RLSearch(sim, agent)
    # 交给 run_mission 执行主循环（听点集由 agent.points 提供）
    return run_mission(sim, agent.points, search.next_point, search.scan_point,
                       verbose, logger, fast, detour_limit)


# 问题三入口：绘制覆盖图、离线自测、RL 训练与部署，返回结果字典
def problem3(args):
    # 生成覆盖示意图
    covering_layouts()
    # 问题三默认的 7 点正七边形环布局
    ring = q3_layout()
    # 汇总理论指标与布局参数
    theory = {
        "target_radius": R_TARGET,
        "disk_covering_table_n": [t[0] for t in COVER_TABLE],
        "disk_covering_table_r": [t[1] for t in COVER_TABLE],
        "min_points_R1000": min_points(1000.0),
        "min_points_R1097": min_points(1097.0),
        "min_points_R1273": min_points(1273.0),
        "min_points_R1500": min_points(1500.0),
        "layout": "7-point regular heptagon ring",
        "layout_n_points": len(ring),
        "layout_ring_radius_m": round(Q3_RHO, 2),
        "layout_cover_radius_m": round(q3_cover_radius(), 2),
        "layout_cover_certified": q3_cover_radius() < R_EFF_MIN,
        "detour_limit_m": DETOUR_LIMIT,
    }
    # 离线自测（演练）
    # 收集每次自测的结果
    trials = []
    # 累计清除数与总源数
    cleared = total = 0
    # 运行 args.trials 次自测
    for seed in range(getattr(args, "trials", 3)):
        # 构造确定性（directional=False）模拟器，种子随局变化
        sim = MockSimulator(n_sources=args.n_sources, seed=2026 + seed, directional=False)
        # 标记模拟器已进入（虚拟时间开始计时）
        sim.entered = True
        # 运行确定性策略，第一局开启冗长输出
        st = run_strategy(sim, use_dp=args.dp, verbose=(seed == 0))
        # 记录本局结果
        trials.append(st)
        # 累加清除数
        cleared += st["cleared"]
        # 累加总源数
        total += sim.total_sources()
    # 记录离线清除比例（总源数为 0 时记为 0）
    theory["offline_clear_ratio"] = round(cleared / total, 4) if total else 0.0
    # 记录离线平均虚拟耗时
    theory["offline_avg_time_s"] = round(sum(t["virtual_time_s"] for t in trials) / len(trials), 1)
    # 打印各半径下最少听点数
    print(f"[Q3] min_points: R=1000->{min_points(1000.0)} R=1097->{min_points(1097.0)} "
          f"R=1273->{min_points(1273.0)} R=1500->{min_points(1500.0)}")
    # 打印离线自测汇总
    print(f"[Q3] 离线自测({len(trials)}局): 清除比例={theory['offline_clear_ratio']:.2%} "
          f"平均时间={theory['offline_avg_time_s']}s")

    # RL：表格 Q-learning 训练（计数无关，自我迭代收敛）+ 部署对比（--rl-episodes 0 时跳过）
    # 配置了训练局数才进行 RL 训练与部署
    if getattr(args, "rl_episodes", 0) > 0:
        from rl import SearchQAgent, train_q_search
        # 用 7 点布局构造智能体
        agent = SearchQAgent(q3_layout())
        # 固定种子随机数生成器，保证训练可复现
        rng = random.Random(20260911)

        # 内联工厂：为第 ep 局生成随机源数的模拟器
        def sim_factory(ep):
            # 生成随机 10~16 源的模拟器
            return MockSimulator(n_sources=rng.randint(10, 16), seed=5000 + ep,
                                 directional=False)

        # 打印训练开始信息
        print(f"[Q3] Q-learning 训练 {args.rl_episodes} 局（计数无关，10~16 源随机）...")
        # 训练 Q-learning，返回每局耗时曲线
        curve = train_q_search(sim_factory, agent, episodes=args.rl_episodes,
                               max_steps=25, verbose=True)
        # 构造部署评估模拟器（固定种子 9999）
        rl_sim = MockSimulator(n_sources=args.n_sources, seed=9999, directional=False)
        # 标记已进入，开始计时
        rl_sim.entered = True
        # 用训练后的智能体部署运行
        rl_res = run_strategy_rl(rl_sim, agent, use_dp=args.dp, verbose=True)
        # 记录训练首局耗时（收敛起点）
        theory["rl_first_time_s"] = round(curve[0], 1) if curve else None
        # 记录训练末局耗时（收敛终点）
        theory["rl_last_time_s"] = round(curve[-1], 1) if curve else None
        # 记录 RL 部署清除比例
        theory["rl_clear_ratio"] = round(rl_res["cleared"] / rl_sim.total_sources(), 4)
        # 记录 RL 部署虚拟耗时
        theory["rl_avg_time_s"] = rl_res["virtual_time_s"]
        # 打印 RL 部署结果与训练收敛情况
        print(f"[Q3] RL 部署: 清除比例={theory['rl_clear_ratio']:.2%} "
              f"虚拟时间={theory['rl_avg_time_s']}s  训练收敛 "
              f"{curve[0]:.0f}s→{curve[-1]:.0f}s" if curve else "[Q3] RL 未产生全清局")
    # 返回问题三结果字典
    return {"q3": theory}


# 命令行入口：解析参数并调用 problem3
def main():
    # 创建参数解析器
    parser = argparse.ArgumentParser()
    # 参数 --mock：使用模拟器（默认开启）
    parser.add_argument("--mock", action="store_true", default=True)
    # 参数 --n-sources：干扰源数量（默认 12）
    parser.add_argument("--n-sources", type=int, default=12)
    # 参数 --seed：随机种子（默认 2026）
    parser.add_argument("--seed", type=int, default=2026)
    # 参数 --trials：离线自测局数（默认 3）
    parser.add_argument("--trials", type=int, default=3)
    # 参数 --dp：使用 DP 精确听点序（默认开启）
    parser.add_argument("--dp", action="store_true", default=True)
    # 参数 --rl-episodes：RL 训练局数（默认 150）
    parser.add_argument("--rl-episodes", type=int, default=150)
    # 解析参数并进入问题三流程
    return problem3(parser.parse_args())


# 脚本直接运行时的入口
if __name__ == "__main__":
    import json
    # 运行 main 并把结果以 JSON 格式（非 ASCII 不转义、缩进 2）打印
    print(json.dumps(main(), ensure_ascii=False, indent=2))
