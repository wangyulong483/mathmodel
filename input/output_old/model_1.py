# -*- coding: utf-8 -*-
"""问题一：交会定位法求源位置可行域直径 + 直径圆覆盖判定。

极坐标测向线 -> 半平面约束 -> 有界性 -> 直径与最小包围圆判定。
运行：python output/model_1.py
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import geo
from geo import (R_TARGET, BEARING_ERR, to_xy, bearing, line_through,
                 localization_region, convex_diameter, min_enclosing_circle)

# 定义图片输出目录（本脚本同级的 figures 目录）
FIG_DIR = Path(__file__).resolve().parent / "figures"
# 创建 figures 目录（若已存在则忽略）
FIG_DIR.mkdir(exist_ok=True)

# 固定随机种子的生成器，保证蒙特卡洛 Jung 界实验可复现
_rng = np.random.default_rng(2026)


# 辅助绘图函数：在坐标轴 ax 上画出直线 a*x + b*y = d（b≈0 时画竖直线）
def _draw_line(ax, a, b, d, xmin=-1900, xmax=1900, **kw):
    # 若 b 接近 0，直线退化为竖直线 x = d/a
    if abs(b) < 1e-12:
        # 直接绘制竖直线
        ax.axvline(d / a, **kw)
    else:
        # 否则在 [xmin, xmax] 内取两个采样点，按 y = (d - a*x)/b 画出斜线
        xs = np.linspace(xmin, xmax, 2)
        # 绘制由两点确定的直线段
        ax.plot(xs, (d - a * xs) / b, **kw)


# 辅助函数：设置坐标轴范围到覆盖目标区域（R_TARGET）并加上 pad 余量
def _limits(ax, pad=200):
    # 设置 x 轴显示范围为 [-R_TARGET-pad, R_TARGET+pad]
    ax.set_xlim(-R_TARGET - pad, R_TARGET + pad)
    # 设置 y 轴显示范围与 x 轴一致
    ax.set_ylim(-R_TARGET - pad, R_TARGET + pad)
    # 设置 x 轴标签（单位：米）
    ax.set_xlabel("x / m")
    # 设置 y 轴标签（单位：米）
    ax.set_ylabel("y / m")


# 将检测点 S 的示向度区间 [β-Δ, β+Δ] 转化为两条半平面约束 a*x + b*y ≤ d
def _wedge_halfplanes(S, beta):
    """检测点 S 的示向度区间 [β-Δ, β+Δ] = 两个半平面（a x + b y ≤ d）。"""
    # 存储两条半平面约束的列表
    out = []
    # 遍历区间两个边界：左边界 β-Δ（法向取 +1）与右边界 β+Δ（法向取 -1）
    for b0, sense in ((beta - BEARING_ERR, 1.0), (beta + BEARING_ERR, -1.0)):
        # 计算边界角 b0 的正弦、余弦，用于构造半平面法向量
        cb, sb = math.cos(math.radians(b0)), math.sin(math.radians(b0))
        # 由法向量与符号得到半平面系数 a、b（法向量取 -sense*sin, sense*cos）
        a, b = -sense * sb, sense * cb
        # 常数项 d 由检测点 S 落在边界上确定：d = a*x_S + b*y_S
        out.append((a, b, a * S[0] + b * S[1]))
    # 返回两条半平面约束的系数 (a, b, d)
    return out


# 问题一主求解：定位可行域、直径、最小包围圆及覆盖判定，并绘图与蒙特卡洛验证
def problem1():
    # 检测点 S1（坐标原点）
    S1 = np.array([0.0, 0.0])
    # 检测点 S2（x 轴上 1200 m 处）
    S2 = np.array([1200.0, 0.0])
    # 干扰源真实位置 G（用于产生“真值”示向度）
    G = np.array([600.0, 400.0])
    # 计算 S1 指向 G 的真实方位角 beta1
    beta1 = bearing(S1, G)
    # 计算 S2 指向 G 的真实方位角 beta2
    beta2 = bearing(S2, G)
    # 两测向线夹角（交会角）的绝对值
    cut = abs(beta2 - beta1)
    # 若夹角大于 180°，取其补角（360 - cut）作为较小的交会角
    if cut > 180.0:
        cut = 360.0 - cut

    # 由两测向线及其误差区间求定位可行区域（凸多边形顶点 verts）
    verts = localization_region([S1, S2], [beta1, beta2], BEARING_ERR)
    # 计算凸多边形直径 D 及其两个端点下标 (i, j)
    D, (i, j) = convex_diameter(verts)
    # 计算凸多边形的最小包围圆：半径 Rstar 与圆心 cstar
    Rstar, cstar = min_enclosing_circle(verts)
    # 直径圆的半径 D/2 与 Jung 界的理论半径 D/√3
    D_half, D_jung = D / 2.0, D / math.sqrt(3.0)

    # 汇总 S1、S2 两楔形的全部半平面约束（用于记录/展示）
    hp = _wedge_halfplanes(S1, beta1) + _wedge_halfplanes(S2, beta2)

    # 有界性：近平行测向线 → 纯楔形交无界
    # 构造近平行测向线的第二组检测点与源，检验定位区域是否退化为无界
    S1p, S2p, Gp = np.array([0.0, 0.0]), np.array([100.0, 0.0]), np.array([1800.0, 10.0])
    # 计算近平行情形下两检测点对 Gp 的方位角
    bp1, bp2 = bearing(S1p, Gp), bearing(S2p, Gp)
    # 求近平行情形下的定位区域（若无界则返回 None）
    verts_par = localization_region([S1p, S2p], [bp1, bp2], BEARING_ERR)

    # 汇总问题一的全部数值结果到 results 字典的 "q1" 键下
    results = {"q1": {
        "S1": S1.tolist(), "S2": S2.tolist(), "G": G.tolist(),
        "beta1_true_deg": round(beta1, 4), "beta2_true_deg": round(beta2, 4),
        "cut_angle_deg": round(cut, 4),
        "region_vertices": [v.tolist() for v in verts],
        "diameter_D": round(D, 4), "diameter_pair": (int(i), int(j)),
        "mec_radius_Rstar": round(Rstar, 4),
        "D_over_2": round(D_half, 4), "D_over_sqrt3": round(D_jung, 4),
        "ratio_Rstar_over_Dhalf": round(Rstar / D_half, 4),
        "diameter_circle_covers": Rstar <= D_half + 1e-9,
        "halfplane_constraints": [[round(c, 4) for c in h] for h in hp],
        "near_parallel": {
            "S1": S1p.tolist(), "S2": S2p.tolist(), "G": Gp.tolist(),
            "beta1_deg": round(bp1, 4), "beta2_deg": round(bp2, 4),
            "cut_angle_deg": round(abs(bp2 - bp1), 4),
            "region_bounded": verts_par is not None,
        },
        "equilateral_triangle_Rstar_over_Dhalf": round(2.0 / math.sqrt(3.0), 4),
    }}

    # 图 1：测向线与定位四边形
    # 创建单子图用于绘制测向线、定位四边形与源位置
    fig, ax = plt.subplots(figsize=(6.2, 5.6))
    # 画出半径为 R_TARGET 的目标区域边界虚线圆
    ax.add_patch(plt.Circle((0, 0), R_TARGET, fill=False, ls="--", lw=1, color="0.6"))
    # 遍历两个检测点，分别绘制其测向线
    for S, beta in [(S1, beta1), (S2, beta2)]:
        # 对每个检测点画出三条线：真实测向线（db=0）与正负误差边界线（db=±BEARING_ERR）
        for db in (-BEARING_ERR, 0, BEARING_ERR):
            # 计算以方位角 beta+db 过检测点 S 的直线系数 (a, b, d)
            a, b, d = line_through(S, beta + db)
            # 用不同线型/颜色/粗细区分真实测向线与误差边界线
            _draw_line(ax, a, b, d, ls=":" if db else "-",
                       color="tab:red" if db == 0 else "tab:gray",
                       lw=1.4 if db == 0 else 0.9)
    # 将定位区域顶点首尾闭合，构成多边形轮廓
    poly = np.array(verts + [verts[0]])
    # 用半透明红色填充定位四边形
    ax.fill(poly[:, 0], poly[:, 1], color="tab:red", alpha=0.25)
    # 绘制定位四边形边界
    ax.plot(poly[:, 0], poly[:, 1], color="tab:red", lw=1.6)
    # 分别用黑色上三角、上三角、蓝色星标绘制 S1、S2、G 三点
    ax.plot(*S1, "k^", ms=8); ax.plot(*S2, "k^", ms=8); ax.plot(*G, "b*", ms=14)
    # 在 S1 点旁标注 "$S_1$"
    ax.annotate("$S_1$", S1, textcoords="offset points", xytext=(-14, -14))
    # 在 S2 点旁标注 "$S_2$"
    ax.annotate("$S_2$", S2, textcoords="offset points", xytext=(6, -14))
    # 在 G 点旁标注 "$G$"
    ax.annotate("$G$", G, textcoords="offset points", xytext=(6, 6))
    # 设置图题：显示交会角 cut 与可行域直径 D
    ax.set_title(f"Bearing intersection: cut angle $\\phi$={cut:.1f}°, "
                 f"diameter $D$={D:.1f} m")
    # 设置坐标轴等比例并开启网格
    ax.set_aspect("equal"); ax.grid(alpha=0.3)
    # 设置坐标轴显示范围与标签
    _limits(ax)
    # 压缩布局、保存图 1 并关闭图形释放内存
    fig.tight_layout(); fig.savefig(FIG_DIR / "q1_quadrilateral.png", dpi=150); plt.close(fig)

    # 图 2：本例恰能覆盖，但一般凸定位多边形不能保证覆盖。
    # 创建 1 行 2 列双子图，左图展示对称例（直径圆能覆盖），右图展示一般凸集（直径圆未必覆盖）
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.2))
    # 取左子图
    ax = axes[0]
    # 重新构造定位区域闭合多边形
    poly = np.array(verts + [verts[0]])
    # 绘制定位区域多边形边界并标注图例
    ax.plot(poly[:, 0], poly[:, 1], color="tab:red", lw=1.6, label="localization region")
    # 绘制干扰源位置 G
    ax.plot(*G, "b*", ms=13)
    # 取直径两个端点 verts[i]、verts[j]
    vi, vj = verts[i], verts[j]
    # 计算直径中点 c_d（直径圆的圆心）
    c_d = (vi + vj) / 2.0
    # 绘制直径线段（黑色虚线）并标注图例
    ax.plot([vi[0], vj[0]], [vi[1], vj[1]], "k--", lw=1.0, label="diameter $D$")
    # 以 c_d 为圆心、D_half 为半径画直径圆（蓝色虚线）并标注图例
    ax.add_patch(plt.Circle(c_d, D_half, fill=False, ls="--", color="tab:blue",
                            label=f"diameter circle ($D/2$={D_half:.1f} m)"))
    # 以 cstar 为圆心、Rstar 为半径画最小包围圆（绿色实线）并标注图例
    ax.add_patch(plt.Circle(cstar, Rstar, fill=False, ls="-", color="tab:green",
                            label=f"MEC ($R^*$={Rstar:.1f} m)"))
    # 设置左子图标题（对称例：直径圆能覆盖定位区域）
    ax.set_title("Symmetric example: diameter circle covers")
    # 设置坐标轴等比例、网格与图例
    ax.set_aspect("equal"); ax.grid(alpha=0.3); ax.legend(loc="best", fontsize=7)
    # 设置左子图显示范围
    _limits(ax)

    # 取右子图
    ax = axes[1]
    # 定义等边三角形边长 L
    L = 1000.0
    # 构造边长为 L 的等边三角形三个顶点（底边在 x 轴上）
    tri = [np.array([0.0, 0.0]), np.array([L, 0.0]), np.array([L / 2.0, L * math.sqrt(3) / 2.0])]
    # 将三角形顶点首尾闭合为多边形
    tp = np.array(tri + [tri[0]])
    # 用半透明红色填充等边三角形
    ax.fill(tp[:, 0], tp[:, 1], color="tab:red", alpha=0.2)
    # 绘制等边三角形边界并标注图例
    ax.plot(tp[:, 0], tp[:, 1], color="tab:red", lw=1.6, label="equilateral triangle")
    # 等边三角形最小包围圆半径 R_tri = L/√3（Jung 界极端情形）
    R_tri = L / math.sqrt(3.0)
    # 画底边中点为圆心、L/2 为半径的直径圆（蓝色虚线）
    ax.add_patch(plt.Circle((L / 2.0, 0.0), L / 2.0, fill=False, ls="--", color="tab:blue",
                            label=f"diameter circle ($D/2$={L/2:.0f} m)"))
    # 画三角形重心（均值点）为圆心、R_tri 为半径的最小包围圆（绿色实线）
    ax.add_patch(plt.Circle(np.mean(tri, axis=0), R_tri, fill=False, ls="-", color="tab:green",
                            label=f"MEC ($D/\\sqrt{{3}}$={R_tri:.1f} m)"))
    # 绘制三角形底边作为参考（黑色虚线）
    ax.plot([0, L], [0, 0], "k--", lw=1.0)
    # 设置右子图标题（一般凸集：直径圆未必能覆盖）
    ax.set_title("General convex set: diameter circle may not cover")
    # 设置坐标轴等比例、网格与图例
    ax.set_aspect("equal"); ax.grid(alpha=0.3); ax.legend(loc="best", fontsize=7)
    # 设置右子图显示范围
    _limits(ax)
    # 压缩布局、保存图 2 并关闭图形
    fig.tight_layout(); fig.savefig(FIG_DIR / "q1_jung.png", dpi=150); plt.close(fig)

    # 蒙特卡洛：Jung 界 R*/(D/2) ∈ [1, 2/√3]
    # 存储每次随机四边形半径比的列表
    ratios = []
    # 进行 4000 次随机实验，验证 Jung 界上下限
    for _ in range(4000):
        # 随机生成 4 个方位角并排序（构造凸四边形顶点顺序）
        ang = sorted(_rng.uniform(0, 360, 4))
        # 随机生成 4 个极径（距离 200~1600 m）
        rad = _rng.uniform(200, 1600, 4)
        # 由极径、方位角转成 4 个平面点坐标
        pts = [to_xy(rad[k], ang[k]) for k in range(4)]
        # 计算这 4 点的凸包直径 Dm
        Dm, _ = convex_diameter(pts)
        # 计算这 4 点的最小包围圆半径 Rm
        Rm, _ = min_enclosing_circle(pts)
        # 记录半径比 Rm/(Dm/2)，用于统计 Jung 界范围
        ratios.append(Rm / (Dm / 2.0))
    # 记录蒙特卡洛得到的半径比最小值（应 ≥ 1）
    results["q1"]["jung_ratio_min"] = round(min(ratios), 4)
    # 记录蒙特卡洛得到的半径比最大值（应 ≤ 2/√3）
    results["q1"]["jung_ratio_max"] = round(max(ratios), 4)
    # 记录 Jung 界的理论最大值 2/√3
    results["q1"]["jung_ratio_theoretical_max"] = round(2.0 / math.sqrt(3.0), 4)

    # 打印问题一的关键数值诊断信息
    print(f"[Q1] beta1={beta1:.3f}° beta2={beta2:.3f}° cut={cut:.3f}° "
          f"D={D:.2f} m R*={Rstar:.2f} m covers={Rstar <= D_half+1e-9} "
          f"near_parallel_bounded={verts_par is not None}")
    # 返回问题一的全部结果
    return results


# 问题一的对外入口：供 model.py 等调用
def main():
    # 直接执行问题一求解并返回结果
    return problem1()


# 命令行直接运行入口：打印问题一结果的 JSON
if __name__ == "__main__":
    import json
    # 以 UTF-8、两空格缩进的美化 JSON 打印问题一结果
    print(json.dumps(main(), ensure_ascii=False, indent=2))
