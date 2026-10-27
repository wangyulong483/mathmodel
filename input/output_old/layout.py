# -*- coding: utf-8 -*-
"""听点布局与其可验证覆盖证书（问题三 / 问题四）。

两套布局都由"检测保证"反推得到，而不是拍脑袋选的：

* 问题三（全向源）：源必被"半径 R≥1000 m 的圆盘"覆盖，故听点集的 R=1000 圆盘
  必须覆盖 1800 m 目标圆盘。覆盖圆盘数下界由圆盘覆盖表给出：
  r(6)=0.555905 → 6 点需 R≥1000.6 m > 1000，**7 点才是合法下界**。
  在 7 点约束下最小化"自原点的开行程"，最优为**正七边形环**：
  环半径 ρ* = D²/(2D·cos(π/7)) = 3240000/(3600·cos(π/7)) ≈ 998.93 m，
  此时最坏覆盖半径 = max(ρ, √(D²+ρ²-2Dρcos(π/7))) = ρ* < 1000，行程 6199 m。
  （中心+六边形族最小行程 6745 m，明显更差；见 README 的对比表。）

* 问题四（含定向源）：源的检测区是"半圆盘"，故要求**全视角覆盖**——对目标圆盘
  内任意点 p，落在 p 的 R=1000 圆盘内的听点不能全部位于 p 的某个开半平面内
  （等价：以其为心的最大角间隙 ≤ 180°）。三角格间距 s 满足 s ≤ R=1000 时，
  含 p 的基本三角形三顶点即构成 120° 环绕，故 s=1000 三角格外延至
  1800+1000=2800 m，得 31 点；其最坏角间隙 149.98° < 180°，证书成立。
  该 31 点集的单位边长哈密顿路径长 = 30×1000 m，是访问 31 点（两两距离≥1000）
  的开行程下界，故 30 km 是硬下界（贪心逐点删除验证：31 点为最小集）。
"""
from __future__ import annotations

import math

import numpy as np

from geo import R_TARGET, R_EFF_MIN, triangular_lattice

# ---------------------------------------------------------------------------
# 问题三：7 点正七边形环
# ---------------------------------------------------------------------------
# 问题三听点个数 Q3_N：7 点正七边形环
Q3_N = 7
# ρ* = D² / (2·D·cos(π/7))：使"环心方向"与"环间方向"的最坏覆盖半径相等的半径
# 最优环半径 Q3_RHO = D²/(2D·cos(π/7))：使环心方向与环间方向的最坏覆盖半径相等
Q3_RHO = R_TARGET ** 2 / (2.0 * R_TARGET * math.cos(math.pi / Q3_N))


# 生成 n 个等角间隔、半径 rho 的环上听点（自 +x 轴起逆时针）
def ring_layout(n=Q3_N, rho=Q3_RHO):
    """n 个等角间隔、半径 rho 的环上听点（自 +x 轴起逆时针）。"""
    # 第 k 个听点角度 2πk/n，用极坐标还原坐标
    return [np.array([rho * math.cos(2.0 * math.pi * k / n),
                      rho * math.sin(2.0 * math.pi * k / n)]) for k in range(n)]


# 问题三布局：返回正七边形环的 7 个听点
def q3_layout():
    # 用默认参数生成 7 点正七边形环
    return ring_layout()


# 环布局覆盖半径证书：目标圆盘内到最近听点的最大距离
def q3_cover_radius(rho=Q3_RHO, n=Q3_N):
    """环布局的覆盖半径证书：max over 目标圆盘 of 到最近听点的距离。

    两个候选极值点：(a) 圆心；(b) 半径 D、方位角落在两相邻听点中间的点。
    """
    # 候选极值点 (a)：圆心到最近听点的距离即环半径 rho
    d_center = rho
    # 相邻两听点夹角的一半，用于求最坏边界点
    half = math.pi / n
    # 候选极值点 (b)：半径 D、方位角落在相邻听点中间的点到听点距离
    d_rim = math.sqrt(R_TARGET ** 2 + rho ** 2
                      - 2.0 * R_TARGET * rho * math.cos(half))
    # 最坏覆盖半径取两个候选极值点的较大值
    return max(d_center, d_rim)


# ---------------------------------------------------------------------------
# 问题四：31 点全视角三角格
# ---------------------------------------------------------------------------
# 问题四三角格间距 Q4_SPACING = 1000 m（取有效接收半径下界，保证覆盖）
Q4_SPACING = R_EFF_MIN
# 三角格外延半径 Q4_EXTENT = 2800 m（目标圆盘半径 + 检测半径）
Q4_EXTENT = R_TARGET + R_EFF_MIN


# 问题四布局：间距 1000 m 的三角格点，半径 2800 m 内共 31 点
def q4_layout():
    # 调用三角格生成器并把结果转为 numpy 数组列表
    return [np.array(p) for p in triangular_lattice(Q4_SPACING, Q4_EXTENT)]


# 求 p 处半径 radius 内听点的最大角间隙（度），>180 表示有探测盲扇区
def max_angular_gap(points, p, radius=Q4_SPACING):
    """p 处、半径 radius 内听点的最大角间隙（度）。>180 表示存在探测盲扇区。"""
    # 收集 p 半径内所有听点相对 p 的方位角并按升序排序
    angs = sorted(math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) % 360.0
                  for q in points if math.hypot(q[0] - p[0], q[1] - p[1]) <= radius + 1e-9)
    # 听点少于 2 个时无法形成环绕
    if len(angs) < 2:
        # 返回 360 表示全盲区（无环绕保证）
        return 360.0
    # 求相邻方位角之间的夹角差
    gaps = [angs[i + 1] - angs[i] for i in range(len(angs) - 1)]
    # 补上首尾跨越 0° 的夹角差
    gaps.append(angs[0] + 360.0 - angs[-1])
    # 返回最大角间隙，作为该点的盲区度量
    return max(gaps)


# 全局采样求最坏角间隙证书：网格采样目标圆盘内各点取最大角间隙
def q4_certificate(points=None, n_ang=360, n_rad=30):
    """最坏角间隙证书（全局采样）。"""
    # 未指定点集时默认用 31 点三角格布局
    pts = q4_layout() if points is None else points
    # worst 记录采样到的最大角间隙
    worst = 0.0
    # 按角度方向采样 n_ang 个方位
    for i in range(n_ang):
        # 第 i 个采样方向的方位角 th（0~2π 均匀）
        th = 2.0 * math.pi * i / n_ang
        # 沿每个方向按半径采样 n_rad 层
        for j in range(n_rad):
            # 第 j 层的采样半径 r（0~R_TARGET 均匀分布）
            r = R_TARGET * j / (n_rad - 1.0)
            # 由极坐标 (r, th) 还原采样点 p
            p = np.array([r * math.cos(th), r * math.sin(th)])
            # 更新全局最坏角间隙
            worst = max(worst, max_angular_gap(pts, p))
    # 返回全局最坏角间隙证书值
    return worst


# 作为脚本直接运行时，打印问题三/四布局的证书验证结果
if __name__ == "__main__":
    # 打印问题三点数、环半径与覆盖半径证书，并判断是否小于 1000 m
    print(f"Q3: n={Q3_N} rho={Q3_RHO:.2f} m  覆盖半径证书={q3_cover_radius():.2f} m "
          f"(< {R_EFF_MIN:.0f} m: {q3_cover_radius() < R_EFF_MIN})")
    # 生成问题四的 31 点三角格布局
    q4 = q4_layout()
    # 打印问题四点数、间距与最坏角间隙，并判断是否 ≤180°
    print(f"Q4: n={len(q4)} spacing={Q4_SPACING:.0f} m 最坏角间隙={q4_certificate(q4):.2f}° "
          f"(<=180: {q4_certificate(q4) <= 180.0})")
