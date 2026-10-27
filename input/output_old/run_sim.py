# -*- coding: utf-8 -*-
"""问题三/四 真实模拟器验证脚本：/enter → 策略 → /exit，输出三个统计值。

用法（重要顺序）：
  1. 打开模拟器，联网登录（参赛队号 + 队员1姓名 + 手机号）。
  2. 进入"问题3演练测试"（或"问题4演练测试"），确认开始，等待界面显示"机器狗接口已就绪"。
  3. 命令行运行：
       python output/run_sim.py --robot-id <参赛队号> --problem 3
       python output/run_sim.py --robot-id <参赛队号> --problem 4
  4. 演练不限次数，测试结束后界面会显示本局干扰源总数/全向数/定向数，据此核对清除比例。
  5. 演练调参满意后，进入对应"正式测试"（各 3 次机会），记录表 1 所需的三项统计。

输出三个统计值：
  清除干扰源个数（= 成功清除次数）
  平均定位清除时间 = 定位清除总时间(虚拟) / 清除个数
  程序运行时间（现实墙钟，自 /enter 成功起）
"""
from __future__ import annotations

import argparse
import random
import time

import numpy as np

from sim import SimClient
from layout import q3_layout, q4_layout
from model_3 import run_strategy, run_strategy_rl
from log import Logger, summarize


def main():
    # 解析命令行参数，配置本脚本对真实模拟器的验证选项
    parser = argparse.ArgumentParser(description="问题三/四 真实模拟器验证")
    # 必填参数：参赛队号，作为模拟器登录账号
    parser.add_argument("--robot-id", required=True, help="参赛队号（模拟器登录账号）")
    # 模拟器 HTTP 服务地址，默认本机端口 2026
    parser.add_argument("--base-url", default="http://127.0.0.1:2026")
    # 指定题目编号（问题三或问题四），默认问题三
    parser.add_argument("--problem", type=int, choices=[3, 4], default=3)
    # 清除顺序采用 Held-Karp 精确动态规划求解
    parser.add_argument("--dp", action="store_true", default=True,
                        help="清除顺序用 Held-Karp 精确 DP")
    # 是否启用 Q-learning 搜索定位
    parser.add_argument("--rl", action="store_true",
                        help="用 Q-learning 搜索定位（先在离线 Mock 自我迭代训练，再贪心部署）")
    # 风险受控快速模式：分群扫描未知频道，不能作为严格不漏源模式
    parser.add_argument("--fast-risk", action="store_true",
                        help="风险受控快速模式：覆盖点分群扫描未知频道，不能作为严格不漏源模式")
    # Q-learning 离线训练局数
    parser.add_argument("--rl-episodes", type=int, default=600, help="Q-learning 训练局数")
    # 解析得到实际传入的命令行参数
    args = parser.parse_args()

    # 建立与模拟器交互的 HTTP 客户端
    client = SimClient(robot_id=args.robot_id, base_url=args.base_url)

    # 听点集：问题三 7 点正七边形环（覆盖半径证书 998.92 m）；问题四 31 点外推三角格
    listening = q3_layout() if args.problem == 3 else q4_layout()
    # 顺路清除阈值：环（问题三）需有限上限，铺满圆域的哈密顿路径（问题四）越松越好。
    detour_limit = None if args.problem == 3 else float("inf")

    # 0. （可选）离线训练 Q-learning（自我迭代，计数无关：每局 10~16 源随机）
    # 默认不启用 RL，智能体置空
    agent = None
    # 若传入 --rl 则先进行离线自训练
    if args.rl:
        from rl import SearchQAgent, train_q_search
        from sim import MockSimulator
        # 构造搜索智能体，快速模式下频道扫描比例取 0.9，否则全量扫描
        agent = SearchQAgent(
            listening,
            channel_scan_fraction=(0.9 if args.fast_risk else 1.0),
        )
        # 固定随机种子，保证离线训练可复现
        rng = random.Random(20260911)
        # 定义环境工厂：按局号生成一个 Mock 模拟器
        def factory(ep):
            # 每局随机 10~16 个干扰源，与最终计数无关
            n = rng.randint(10, 16)                      # 计数无关：随机 10~16 源
            # 返回对应局号与种子的模拟环境，问题四额外含定向源
            return MockSimulator(n_sources=n, seed=7000 + ep,
                                 directional=(args.problem == 4))
        # 打印离线训练开始提示
        print(f"离线 Mock 训练 Q-learning {args.rl_episodes} 局（计数无关，10~16 源随机）...")
        # 执行 Q-learning 自我迭代训练
        train_q_search(factory, agent, episodes=args.rl_episodes, verbose=True)

    # 1. 进入
    # 尝试进入模拟器测试
    try:
        # 调用 /enter 进入并获取剩余时长信息
        enter = client.enter()
    # 捕获连接失败异常
    except ConnectionError as exc:
        # 打印连接失败原因
        print(f"[失败] 无法连接模拟器：{exc}")
        # 提示用户检查模拟器登录与测试状态
        print("  请确认：模拟器已登录、已启动测试、界面显示'机器狗接口已就绪'。")
        # 连接失败则直接终止主流程
        return
    # 打印进入成功信息（剩余现实时间与虚拟限时）
    print(f"进入成功：剩余现实时间 {enter.get('remaining_real_duration_s')} s，"
          f"虚拟限时 {enter.get('max_virtual_duration_s')} s")

    # 2. 运行策略（串行 /measure、/clear，已含 accepted 校验），全程记录结构化日志
    # 创建结构化日志记录器
    logger = Logger()
    # 记录策略运行前的墙钟起点
    t0 = time.time()
    # 尝试运行策略并捕获运行期异常
    try:
        # 若已训练出 RL 智能体，则走 RL 搜索定位流程
        if agent is not None:
            # 以 RL 智能体运行策略，串行执行 /measure 与 /clear
            result = run_strategy_rl(client, agent, use_dp=args.dp,
                                     verbose=True, logger=logger,
                                     fast=args.fast_risk,
                                     detour_limit=detour_limit)
        # 否则走固定听点集策略
        else:
            # 以固定听点集运行策略
            result = run_strategy(client, listening_points=listening, use_dp=args.dp,
                                  verbose=True, logger=logger,
                                  detour_limit=detour_limit)
    # 捕获连接或运行异常
    except (ConnectionError, RuntimeError) as exc:
        # 打印中止原因
        print(f"[中止] {exc}")
        # 出现异常则终止主流程
        return
    # 计算策略实际墙钟耗时
    wall = time.time() - t0

    # 3. 退出
    # 尝试退出模拟器
    try:
        # 调用 /exit 结束本局测试
        client.exit()
    # 忽略退出阶段的任何异常
    except Exception:
        pass

    # 4. 报告（对应题目表 1 三项）
    # 取出虚拟定位清除总时间
    virtual = result["virtual_time_s"]
    # 取出成功清除的干扰源个数
    cleared = result["cleared"]
    # 计算平均定位清除时间，清除数为零时记作无穷大
    avg = virtual / cleared if cleared else float("inf")
    # 打印验证结果标题
    print("\n=== 问题%d 验证结果 ===" % args.problem)
    # 打印清除干扰源个数
    print(f"清除干扰源个数：{cleared}")
    # 打印虚拟定位清除总时间
    print(f"定位清除总时间（虚拟）：{virtual:.1f} s")
    # 打印平均定位清除时间
    print(f"平均定位清除时间：{avg:.1f} s/个")
    # 打印现实墙钟运行时间
    print(f"程序运行时间（现实）：{wall:.1f} s")

    # 5. 落日志 + 打印结构化摘要
    # 将结构化日志写入输出目录
    log_path = logger.dump(f"output/logs/q{args.problem}_{int(time.time())}.json")
    # 打印结构化日志标题
    print(f"\n=== 结构化日志 ===")
    # 打印日志文件路径
    print(f"日志文件：{log_path}")
    # 打印结构化摘要
    print(summarize(logger))


if __name__ == "__main__":
    # 作为脚本入口运行时调用主函数
    main()
