# -*- coding: utf-8 -*-
"""结构化日志：记录每条指令、每个源的定位/清除详情，用于复盘与论文证据。

对应附件 2 要求"机器狗程序应自行记录指令序列、响应信息"。
"""
from __future__ import annotations

import json
from pathlib import Path


# 结构化日志容器：累积每条指令与每个源的定位/清除详情
class Logger:
    """累积结构化日志：actions（每条指令）+ sources（每个源的定位/清除详情）。"""

    # 初始化：指令列表与源详情字典
    def __init__(self):
        # actions 累积每条指令的日志条目
        self.actions = []
        # sources 以频道为键累积每个源的定位/清除详情
        self.sources = {}

    # 记录一条指令：操作、坐标、频道、结果、示向度、虚拟时刻
    def action(self, op, x, y, ch, result=None, svd=None, t=None):
        # 把该条指令信息（含舍入后的坐标/示向度/时间）追加到 actions
        self.actions.append({
            "op": op,
            "x": round(x, 1), "y": round(y, 1), "ch": ch,
            "result": result,
            "svd": round(svd, 2) if svd is not None else None,
            "t": round(t, 2) if t is not None else None,
        })

    # 用关键字参数更新频道 ch 对应的源详情
    def source(self, ch, **kw):
        # 若该频道尚无记录则先建空字典，再用 kw 更新其详情
        self.sources.setdefault(ch, {}).update(kw)

    # 把全部日志序列化成 JSON 写入 path 文件，返回文件路径
    def dump(self, path):
        # 递归创建父目录（已存在则忽略）
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # 把 {动作数, 动作列表, 源详情} 转成 UTF-8 JSON 缩进文本写入文件
        Path(path).write_text(json.dumps(
            {"n_actions": len(self.actions), "actions": self.actions,
             "sources": self.sources},
            ensure_ascii=False, indent=2), encoding="utf-8")
        # 返回文件路径字符串
        return str(path)


# 包装 sim：记录每条 measure/clear 指令，其余属性透传给底层模拟器
class LoggedSim:
    """包装 sim，记录每条 measure/clear 指令（含结果、示向度、虚拟时刻）；其余属性透传。"""

    # 保存被包装的模拟器、日志对象与当前阶段名
    def __init__(self, sim, log: Logger, phase: str = "?"):
        # 保存底层模拟器引用
        self._sim = sim
        # 保存日志对象引用
        self._log = log
        # 保存阶段名（如 Q1/Q3/Q4），用于复盘区分
        self.phase = phase

    # 包装 measure：先调用底层检测，再把结果记入日志后返回
    def measure(self, x, y, ch):
        # 调用底层模拟器的 measure 并拿到响应
        r = self._sim.measure(x, y, ch)
        # 把检测指令连同结果、示向度、虚拟时间记入日志
        self._log.action("measure", x, y, ch, r.get("measure_result"),
                         r.get("svd_deg"), r.get("virtual_time_s"))
        # 返回响应给调用方
        return r

    # 包装 clear：先调用底层清除，再把结果记入日志后返回
    def clear(self, x, y, ch):
        # 调用底层模拟器的 clear 并拿到响应
        r = self._sim.clear(x, y, ch)
        # 把清除指令连同结果与虚拟时间记入日志
        self._log.action("clear", x, y, ch, r.get("clear_result"),
                         None, r.get("virtual_time_s"))
        # 返回响应给调用方
        return r

    # 把未显式定义的方法/属性透传给底层模拟器（如 enter、exit 等）
    def __getattr__(self, name):
        # 从底层模拟器取对应属性并返回
        return getattr(self._sim, name)


# 把日志归纳成可读多行摘要（指令统计 + 定位误差 + 各阶段耗时）
def summarize(log: Logger) -> str:
    """把日志归纳成可读的多行摘要（按源 + 指令统计 + 定位误差 + 各阶段耗时）。"""
    from collections import Counter
    import math

    # 取出指令列表，便于统计
    acts = log.actions
    # 取出源详情字典，便于统计定位/清除情况
    srcs = log.sources
    # 首行输出指令总数
    lines = [f"指令总数：{len(acts)}"]

    # 统计各操作类型（measure/clear）的次数
    c_op = Counter(a["op"] for a in acts)
    # 统计各检测结果（direction/near/no_signal）次数
    c_meas = Counter(a["result"] for a in acts if a["op"] == "measure")
    # 统计各清除结果（success/no_target）次数
    c_clear = Counter(a["result"] for a in acts if a["op"] == "clear")
    # 追加指令类型分布一行
    lines.append(f"  指令类型：{dict(c_op)}")
    # 追加检测结果分布一行
    lines.append(f"  检测结果：{dict(c_meas)}")
    # 追加清除结果分布一行
    lines.append(f"  清除结果：{dict(c_clear)}")

    # 统计被成功清除的源个数
    n_cleared = sum(1 for d in srcs.values() if d.get("cleared"))
    # 追加发现源与清除成功数一行
    lines.append(f"发现源（有信号）频道数：{len(srcs)}，清除成功：{n_cleared}")

    # 统计各源的定位方式（如 LSQ/交会）次数
    c_method = Counter(d.get("method") for d in srcs.values())
    # 追加定位方式分布一行
    lines.append(f"  定位方式：{dict(c_method)}")
    # 统计各源定位用到的测向次数分布
    c_bear = Counter(d.get("bearings") for d in srcs.values() if d.get("bearings") is not None)
    # 追加定位测向数分布一行（按键排序）
    lines.append(f"  定位测向数分布：{dict(sorted(c_bear.items()))}")

    # 定位误差（估计 vs 真实，仅离线 Mock 可得）
    # errs 累积每个源的定位误差（估计 vs 真实）
    errs = []
    # 遍历每个源详情
    for d in srcs.values():
        # 同时有估计值与真实值时才可计算误差（仅离线 Mock 有真实值）
        if "estimate" in d and "true" in d:
            # 解包估计位置 (ex, ey)
            ex, ey = d["estimate"]
            # 解包真实位置 (tx, ty)
            tx, ty = d["true"]
            # 用欧氏距离计算该源定位误差并加入列表
            errs.append(math.hypot(ex - tx, ey - ty))
    # 有误差数据时输出统计
    if errs:
        # 追加定位误差的均值与最大值统计一行
        lines.append(f"  定位误差（LSQ 估计-真实）：均值 {sum(errs)/len(errs):.1f} m，"
                     f"最大 {max(errs):.1f} m，n={len(errs)}")

    # t_first/t_last 记录虚拟时间的最小/最大值
    t_first = t_last = None
    # 遍历每条指令
    for a in acts:
        # 只统计带时间戳的指令
        if a["t"] is not None:
            # 更新最早虚拟时间
            t_first = a["t"] if t_first is None else min(t_first, a["t"])
            # 更新最晚虚拟时间
            t_last = a["t"] if t_last is None else max(t_last, a["t"])
    # 存在时间戳时输出时间跨度
    if t_last is not None:
        # 追加虚拟时间跨度一行（起止与总时长）
        lines.append(f"虚拟时间跨度：{t_first:.1f}s → {t_last:.1f}s（总 {t_last - t_first:.1f}s）")
    # 把全部摘要行用换行连接返回
    return "\n".join(lines)
