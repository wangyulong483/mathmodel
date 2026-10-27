# -*- coding: utf-8 -*-
# 问题四离线布局搜索工具：在全视野（角度间隙≤180°）约束下筛选紧凑的定向听点布局。
"""Search compact directional listening layouts under the full-view test.

This is an offline design tool.  It samples the target disk densely, rejects
layouts whose nearby listening directions have an angular gap above 180
degrees, and ranks feasible candidates by an open nearest-neighbour tour.
The paper must treat its result as a numerical candidate until accompanied by
an analytic or interval-arithmetic certificate.
"""
from __future__ import annotations

import argparse
import json
import math

import numpy as np

from geo import R_EFF_MIN, R_TARGET, dist, triangular_lattice


def disk_samples(radial_step=45.0, angular_step_deg=2.0):
    # 以圆心作为第一个采样点
    points = [np.zeros(2)]
    # 按径向步长从内到外枚举半径环
    for radius in np.arange(radial_step, R_TARGET + 0.5 * radial_step,
                            radial_step):
        # 该半径环上的采样点个数，随半径增大而增多
        count = max(12, int(math.ceil(360.0 / angular_step_deg *
                                      radius / R_TARGET)))
        # 在当前半径环上按等角间隔生成采样点
        for angle in np.linspace(0.0, 2.0 * math.pi, count, endpoint=False):
            points.append(radius * np.array([math.cos(angle), math.sin(angle)]))
    # 返回整个目标圆域的稠密采样点集
    return points


def max_angular_gap(points, samples, reception=R_EFF_MIN):
    # 初始化最差角度间隙与对应位置
    worst = 0.0
    worst_at = None
    # 对每个采样源点计算其可接收听点的角度分布
    for source in samples:
        # 收集该源点有效接收范围内各听点的方位角并排序
        angles = sorted(
            math.atan2(q[1] - source[1], q[0] - source[0]) % (2.0 * math.pi)
            for q in points
            if dist(q, source) <= reception + 1e-7 and dist(q, source) > 1e-7
        )
        # 若有效听点少于 2 个，则无法形成交会，直接判为不可行
        if len(angles) < 2:
            return 360.0, source
        # 计算相邻方位角之间的角度差
        gaps = [angles[i + 1] - angles[i] for i in range(len(angles) - 1)]
        # 补充首尾跨越 2π 的间隙
        gaps.append(angles[0] + 2.0 * math.pi - angles[-1])
        # 取最大角度差并换算为度数
        gap = math.degrees(max(gaps))
        # 更新全局最差间隙及其位置
        if gap > worst:
            worst, worst_at = gap, source
    # 返回最差角度间隙与对应源点
    return worst, worst_at


def transform(points, angle_deg, offset):
    # 将角度换算为弧度
    angle = math.radians(angle_deg)
    # 构造二维旋转矩阵
    rotation = np.array([[math.cos(angle), -math.sin(angle)],
                         [math.sin(angle), math.cos(angle)]])
    # 对每个点先旋转再平移，返回变换后的点集
    return [rotation @ np.asarray(p) + np.asarray(offset) for p in points]


def open_nearest_length(points):
    # 初始化待访问点索引列表
    remaining = list(range(len(points)))
    # 路径起点设在原点
    current = np.zeros(2)
    # 初始化路径总长度
    length = 0.0
    # 贪心访问：每次取离当前点最近的下一个点
    while remaining:
        # 找出距离当前点最近的待访问点
        idx = min(remaining, key=lambda i: dist(current, points[i]))
        # 累加这段移动距离
        length += dist(current, points[idx])
        # 移动到该点
        current = points[idx]
        # 从待访问列表中移除该点
        remaining.remove(idx)
    # 返回贪心开环最近邻路径总长度
    return length


def search(spacings, radial_step=45.0, angular_step_deg=2.0):
    # 生成目标圆域的稠密采样点
    samples = disk_samples(radial_step, angular_step_deg)
    # 初始化候选布局结果列表
    rows = []
    # 枚举不同点间距
    for spacing in spacings:
        # 布局外扩范围：目标半径加上有效接收半径
        extent = R_TARGET + R_EFF_MIN
        # 生成足够大的三角格点作为候选基础
        base = triangular_lattice(spacing, extent + spacing)
        # 枚举三种平移偏移量
        offsets = [(0.0, 0.0), (spacing / 2.0, 0.0),
                   (0.0, spacing * math.sqrt(3.0) / 6.0)]
        # 枚举三种旋转角
        for angle in (0.0, 10.0, 20.0):
            # 枚举不同平移偏移
            for offset in offsets:
                # 对基础点集施加旋转与平移得到候选布局
                candidate = transform(base, angle, offset)
                # 只保留落在外扩范围内的点
                candidate = [p for p in candidate
                             if np.linalg.norm(p) <= extent + 1e-7]
                # 计算该候选布局的最差角度间隙
                gap, worst_at = max_angular_gap(candidate, samples)
                # 记录该候选布局的关键指标
                rows.append({
                    "spacing": spacing,
                    "rotation_deg": angle,
                    "offset": list(offset),
                    "points": len(candidate),
                    "worst_gap_deg": round(gap, 3),
                    "worst_at": ([round(float(x), 2) for x in worst_at]
                                 if worst_at is not None else None),
                    "open_nn_length_m": round(open_nearest_length(candidate), 1),
                    "feasible_on_samples": gap <= 180.0 + 1e-7,
                })
    # 优先可行布局，再按路径长度与点数升序排序
    return sorted(rows, key=lambda row: (
        not row["feasible_on_samples"], row["open_nn_length_m"], row["points"]
    ))


def main():
    # 解析布局搜索的命令行参数
    parser = argparse.ArgumentParser()
    # 最小点间距，默认 900 m
    parser.add_argument("--min-spacing", type=int, default=900)
    # 最大点间距，默认 1450 m
    parser.add_argument("--max-spacing", type=int, default=1450)
    # 点间距扫描步长，默认 50 m
    parser.add_argument("--step", type=int, default=50)
    # 输出前多少名候选，默认 20
    parser.add_argument("--top", type=int, default=20)
    # 解析得到实际参数
    args = parser.parse_args()
    # 在指定间距范围内搜索候选布局
    rows = search(range(args.min_spacing, args.max_spacing + 1, args.step))
    # 打印排名前若干的候选布局
    print(json.dumps(rows[:args.top], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # 作为脚本入口运行时调用主函数
    main()
