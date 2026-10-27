# -*- coding: utf-8 -*-
"""问题二：第二检测点选择策略（Fisher 信息 / 最优交会角 90° / 候选区域）。

运行：python output/model_2.py
"""
from __future__ import annotations

import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from geo import R_TARGET, R_EFF_MIN, BEARING_ERR, bearing, dist, line_through

# 定义图片输出目录（本脚本同级的 figures 目录）
FIG_DIR = Path(__file__).resolve().parent / "figures"
# 创建 figures 目录（若已存在则忽略）
FIG_DIR.mkdir(exist_ok=True)


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


# 辅助绘图函数：从 origin 沿角度 angle_deg 画一条长度为 length 的射线
def _ray(ax, origin, angle_deg, length=2600, **kw):
    # 将角度从度转换为弧度
    a = math.radians(angle_deg)
    # 计算射线终点：起点 + length*(cos a, sin a)
    end = np.array(origin) + length * np.array([math.cos(a), math.sin(a)])
    # 绘制从起点到终点的射线
    ax.plot([origin[0], end[0]], [origin[1], end[1]], **kw)


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


# 问题二主求解：给出第二检测点 S2 的候选区域与最优交会角，并绘制 GDOP 图
def problem2():
    # 第一检测点 S1（坐标原点）
    S1 = np.array([0.0, 0.0])
    # 干扰源真实位置 G
    G = np.array([600.0, 400.0])
    # 计算 S1 指向 G 的真实方位角 beta1
    beta1 = bearing(S1, G)
    # 计算 S1 到 G 的距离 t1（用于定位精度分析）
    t1 = dist(S1, G)
    # 拆出 G 的横、纵坐标 XG、YG
    XG, YG = G

    # 计算从 G 指向 S1 的反方位角 aGS1（用于确定 S2 相对 G 的交会角）
    aGS1 = (math.degrees(math.atan2(S1[1] - YG, S1[0] - XG))) % 360.0
    # 生成候选区域内 x 方向的采样点
    xs = np.linspace(-1900, 1900, 320)
    # 生成候选区域内 y 方向的采样点
    ys = np.linspace(-1900, 1900, 320)
    # 构造网格坐标矩阵 XX、YY（用于向量化评估整个候选平面）
    XX, YY = np.meshgrid(xs, ys)
    # 计算每个网格点到 G 的距离 T2
    T2 = np.hypot(XX - XG, YY - YG)
    # 计算每个网格点到原点 S1 的距离 R2
    R2 = np.hypot(XX, YY)
    # 计算每个网格点相对 G 的方位角 aGS2（度，取模 360）
    aGS2 = np.degrees(np.arctan2(YY - YG, XX - XG)) % 360.0
    # 计算 S1、S2 对 G 的交会角绝对值
    cut = np.abs(aGS2 - aGS1)
    # 将交会角折算到 [0,180] 区间（取补角），得到真实交会角
    cut = np.minimum(cut, 360.0 - cut)
    # 候选区域判定：在目标区域内、距 G 有效范围内、且交会角落在 60°~120° 的网格点
    good = (R2 <= R_TARGET) & (T2 > 5.0) & (T2 <= R_EFF_MIN) & (cut >= 60.0) & (cut <= 120.0)

    # 生成交会角 φ 的采样序列（1°~179°）
    phis = np.linspace(1.0, 179.0, 400)
    # 计算定位误差放大系数 1/sin(φ)（φ=90° 时最小，为 1）
    amp = 1.0 / np.sin(np.radians(phis))

    # 汇总问题二的数值结果到 results 字典的 "q2" 键下
    results = {"q2": {
        "S1": S1.tolist(), "G": G.tolist(), "beta1_deg": round(beta1, 4),
        "t1": round(t1, 2), "optimal_cut_deg": 90.0,
        "candidate_cut_range_deg": [60.0, 120.0],
        "amp_60deg": round(1.0 / math.sin(math.radians(60.0)), 3),
        "amp_90deg": round(1.0 / math.sin(math.radians(90.0)), 3),
        "amp_120deg": round(1.0 / math.sin(math.radians(120.0)), 3),
    }}

    # 创建 1 行 2 列双子图：左图为 S2 候选区域，右图为误差放大系数曲线
    fig, axes = plt.subplots(1, 2, figsize=(12.0, 5.2))
    # 取左子图
    ax = axes[0]
    # 用橙色等高线填充候选区域（good 布尔矩阵转为浮点后按 [0.5,1.5] 分界）
    ax.contourf(XX, YY, good.astype(float), levels=[0.5, 1.5],
                colors=["tab:orange"], alpha=0.35)
    # 画出半径为 R_TARGET 的目标区域边界虚线圆
    ax.add_patch(plt.Circle((0, 0), R_TARGET, fill=False, ls="--", lw=1, color="0.3"))
    # 画出 S1 的三条测向线：真实测向线与正负误差边界线
    for db in (-BEARING_ERR, 0, BEARING_ERR):
        # 计算以方位角 beta1+db 过 S1 的直线系数 (a, b, d)
        a, b, d = line_through(S1, beta1 + db)
        # 用不同线型/颜色/粗细区分真实测向线与误差边界线
        _draw_line(ax, a, b, d, ls=":" if db else "-",
                   color="tab:gray" if db else "tab:red", lw=1.6 if db == 0 else 0.9)
    # 遍历候选交会角边界 60° 与 120°
    for c0 in (60.0, 120.0):
        # 对每个边界角取正负两个方向，画出对应的两条边界射线
        for sgn in (+1, -1):
            # 从 G 沿 aGS1 ± c0 方向画射线，标出候选区域角边界
            _ray(ax, G, aGS1 + sgn * c0, color="k", lw=0.9, ls="--")
    # 绘制 S1 与 G 两点
    ax.plot(*S1, "k^", ms=9); ax.plot(*G, "b*", ms=14)
    # 在 S1 点旁标注 "$S_1$"
    ax.annotate("$S_1$", S1, textcoords="offset points", xytext=(-14, -14))
    # 在 G 点旁标注 "$G$"
    ax.annotate("$G$", G, textcoords="offset points", xytext=(6, 6))
    # 设置左子图标题（S2 候选区域：交会角 60°~120°）
    ax.set_title("Candidate region for $S_2$ (cut angle 60°–120°)")
    # 设置左子图坐标轴等比例、网格与显示范围
    ax.set_aspect("equal"); ax.grid(alpha=0.25); _limits(ax)

    # 取右子图
    ax = axes[1]
    # 绘制误差放大系数 1/sin(φ) 随交会角 φ 的变化曲线
    ax.plot(phis, amp, "b-", lw=1.8)
    # 在 60°、90°、120° 三个关键交会角处画红色虚线竖线
    for c0 in (60.0, 90.0, 120.0):
        ax.axvline(c0, color="tab:red", ls="--", lw=0.9)
    # 用橙色半透明带标出 60°~120° 的候选交会角区间
    ax.axvspan(60.0, 120.0, color="tab:orange", alpha=0.15)
    # 设置 x 轴标签：交会角 φ / °
    ax.set_xlabel("cut angle φ / °")
    # 设置 y 轴标签：误差放大系数 1/sin φ
    ax.set_ylabel("error amplification 1/sin φ")
    # 设置右子图标题（定位误差在 φ=90° 时最小）
    ax.set_title("Localization error vs cut angle (min at φ=90°)")
    # 设置 y 轴范围并开启网格
    ax.set_ylim(0.9, 4.0); ax.grid(alpha=0.3)

    # 压缩布局、保存图并关闭图形
    fig.tight_layout(); fig.savefig(FIG_DIR / "q2_gdop.png", dpi=150); plt.close(fig)
    # 打印问题二的关键数值诊断信息
    print(f"[Q2] beta1={beta1:.3f}° t1={t1:.1f} m optimal cut=90° "
          f"amp(60/90/120)=1.15/1.00/1.15")
    # 返回问题二的全部结果
    return results


# 问题二的对外入口：供 model.py 等调用
def main():
    # 直接执行问题二求解并返回结果
    return problem2()


# 命令行直接运行入口：打印问题二结果的 JSON
if __name__ == "__main__":
    import json
    # 以 UTF-8、两空格缩进的美化 JSON 打印问题二结果
    print(json.dumps(main(), ensure_ascii=False, indent=2))
