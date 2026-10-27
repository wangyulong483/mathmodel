# -*- coding: utf-8 -*-
"""定位误差诊断：Stansfield 估计误差、定位区域半径、交会角与 20m 清除半径的关系。"""
from __future__ import annotations

import argparse
import math
import statistics

import numpy as np

from geo import dist, localization_region, min_enclosing_circle
from sim import MockSimulator
from layout import q3_layout, q4_layout
from model_3 import (_order_listening, _listening_tour,
                     stansfield_localize, _single_bearing_estimate)


def main():
    # 解析诊断脚本的命令行参数
    ap = argparse.ArgumentParser()
    # 题目编号，默认问题三
    ap.add_argument("--problem", type=int, default=3)
    # 试验次数，默认 20
    ap.add_argument("--trials", type=int, default=20)
    # 随机种子，默认 1000
    ap.add_argument("--seed", type=int, default=1000)
    # 解析得到实际参数
    args = ap.parse_args()

    # 按题目编号选择听点集
    points = q3_layout() if args.problem == 3 else q4_layout()
    # 对听点集做顺序规划，得到听点巡游顺序
    listen = _order_listening(points)

    # 初始化各诊断指标的收集列表
    err_est, err_reg, err_center, nbear, cross, reg_r = [], [], [], [], [], []
    # 单测向（无法交会定位）的源计数
    n_single = 0
    # 对每个试验逐次模拟
    for trial in range(args.trials):
        # 源数在 10~16 间按试验号循环取值
        total = 10 + trial % 7
        # 构造固定种子的模拟环境，问题四含定向源
        sim = MockSimulator(n_sources=total, seed=args.seed + trial,
                            directional=(args.problem == 4))
        # 标记已进入模拟器，直接跑巡游
        sim.entered = True
        # 执行听点巡游，返回观测值与最近的听点
        obs, near = _listening_tour(sim, listen)
        # 建立频道到真实源位置的映射表
        truth = {s["channel"]: np.array(s["pos"]) for s in sim.sources}
        # 遍历每个频道的观测结果
        for ch, olist in obs.items():
            # 跳过无真实位置对应的频道
            if ch not in truth:
                continue
            # 取该频道的真实位置
            t = truth[ch]
            # 记录该源的测向次数
            nbear.append(len(olist))
            # 仅当测向次数≥2 时才可交会定位
            if len(olist) >= 2:
                # 用 Stansfield 法估计位置
                est = stansfield_localize([o[0] for o in olist], [o[1] for o in olist])
                # 记录估计位置到真实位置的误差
                err_est.append(dist(est, t))
                # 初始化最佳交会角
                best = 0.0
                # 遍历所有测向对
                for i in range(len(olist)):
                    # 与后续测向两两配对
                    for j in range(i + 1, len(olist)):
                        # 计算两测向角的最小夹角差（模 180°）
                        d = abs((olist[i][1] - olist[j][1]) % 180.0)
                        # 取与 180° 的较小夹角作为交会角候选
                        best = max(best, min(d, 180.0 - d))
                # 记录该源的最佳交会角
                cross.append(best)
                # 计算该源定位区域的多边形
                reg = localization_region([o[0] for o in olist], [o[1] for o in olist])
                # 仅当定位区域存在时继续
                if reg is not None:
                    # 求定位区域的最小包围圆半径与圆心
                    r, c = min_enclosing_circle(reg)
                    # 记录定位区域半径
                    reg_r.append(r)
                    # 圆心存在时记录圆心误差
                    if c is not None:
                        err_reg.append(dist(c, t))
            # 测向不足 2 次的源计入单测向
            else:
                n_single += 1

    # 定义打印统计指标的内嵌函数
    def stat(name, v):
        # 空列表则打印无数据
        if not v:
            print(f"{name}: (无)")
            return
        # 排序后计算各分位统计量
        v = sorted(v)
        # 打印样本数、均值、中位数、p90 与最大值
        print(f"{name}: n={len(v)} 均值={statistics.mean(v):6.1f} 中位={statistics.median(v):6.1f} "
              f"p90={v[int(0.9*(len(v)-1))]:7.1f} 最大={v[-1]:7.1f}")

    # 打印总源数与单测向占比
    print(f"总源数={len(nbear)}  单测向={n_single} ({100*n_single/max(1,len(nbear)):.1f}%)")
    # 打印测向次数分布
    print(f"测向数分布: {sorted((n, nbear.count(n)) for n in set(nbear))}")
    # 依次打印各项诊断指标
    stat("测向数", nbear)
    stat("最佳交会角/°", cross)
    stat("Stansfield 估计误差/m", err_est)
    stat("定位区域最小包围圆半径/m", reg_r)
    stat("区域圆心误差/m", err_reg)
    # 有估计误差时打印超过 20m 的比例
    if err_est:
        print(f"估计误差>20m 的比例: {100*sum(e > 20 for e in err_est)/len(err_est):.1f}%")
    # 有区域半径数据时打印超过阈值比例
    if reg_r:
        print(f"区域半径>20m 的比例: {100*sum(r > 20 for r in reg_r)/len(reg_r):.1f}%")
        print(f"区域半径>30m 的比例: {100*sum(r > 30 for r in reg_r)/len(reg_r):.1f}%")


if __name__ == "__main__":
    # 作为脚本入口运行时调用主函数
    main()
