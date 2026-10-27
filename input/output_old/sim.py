# -*- coding: utf-8 -*-
"""模拟器接口客户端（HTTP+JSON，附件 1/2 协议）与离线 Mock 模拟器。

真实模拟器仅 4 条指令：POST /enter、/measure、/clear、/exit。
Mock 模拟器用于无真实模拟器时的离线联调与策略测试（问题 3/4 演练前自测）。
"""
from __future__ import annotations

import json
import math
import random
import uuid
from urllib.request import Request, urlopen

from geo import NEAR_R, CLEAR_R, SPEED, bearing as _bearing, dist as _dist

# 频道范围
# 把 20 个频道号 1~20 存成列表，供随机分配频道使用
CHANNELS = list(range(1, 21))


# ---------------------------------------------------------------------------
# 真实模拟器客户端
# ---------------------------------------------------------------------------
# 真实模拟器客户端：按附件 2 协议用 HTTP+JSON 访问 http://127.0.0.1:2026
class SimClient:
    """按附件 2 协议访问模拟器 http://127.0.0.1:2026 的串行客户端。"""

    # 构造客户端：记录机器人编号、服务地址与请求超时，并初始化本地状态
    def __init__(self, robot_id: str, base_url: str = "http://127.0.0.1:2026",
                 timeout: float = 5.0):
        # 去掉 base_url 末尾斜杠，避免拼接路径时出现双斜杠
        self.base_url = base_url.rstrip("/")
        # 保存参赛队/机器人编号，随每个请求发送
        self.robot_id = robot_id
        # 保存 HTTP 请求超时时间
        self.timeout = timeout
        # 请求序号计数器，用于生成唯一的 request_id
        self._seq = 0
        # 本地状态（真实模拟器在服务端计时，此处镜像一份供算法读取）
        # 本地镜像位置，初始在原点 (0,0)（真实模拟器在服务端计时，这里只镜像一份供算法读取）
        self.position = (0.0, 0.0)
        # 本地镜像当前频道，初始为 1
        self.channel = 1
        # 本地镜像虚拟时间，初始为 0
        self.virtual_time = 0.0

    # 生成唯一请求编号：前缀-序号-随机 hex，便于服务端区分各请求
    def _new_request_id(self, prefix: str) -> str:
        # 序号自增，保证同一客户端请求编号不重复
        self._seq += 1
        # 返回由前缀、序号、8 位随机 hex 拼接的 request_id
        return f"{prefix}-{self._seq}-{uuid.uuid4().hex[:8]}"

    # 构造请求体公共字段（arena_id、robot_id、request_id）
    def _base(self, request_id: str) -> dict:
        # 返回公共字段字典（含 arena_id 与 robot_id）
        return {"arena_id": "default", "robot_id": self.robot_id,
                "request_id": request_id}

    # 向指定路径发送 POST 请求并解析 JSON 响应；连接失败抛 ConnectionError
    def post(self, path: str, payload: dict) -> dict:
        """发送一次 POST；连接失败（无 JSON 体）抛 ConnectionError。"""
        # 构造 urllib 的 Request 对象（URL、JSON 体、头、POST 方法）
        req = Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # 用 try/except 捕获连接与解析异常，统一转成 ConnectionError
        try:
            # 带超时发送请求并读取响应
            with urlopen(req, timeout=self.timeout) as resp:
                # 把响应字节解码成 UTF-8 再解析为 JSON 字典返回
                return json.loads(resp.read().decode("utf-8"))
        # 捕获任何请求/解析异常
        except Exception as exc:
            # 包装成 ConnectionError 抛出，并保留原始异常链
            raise ConnectionError(f"{path} 连接失败（接口未开放/测试结束？）: {exc}") from exc

    # 校验响应是否被接受（accepted==True），否则抛 RuntimeError
    def _check(self, r: dict, action: str) -> dict:
        # accepted 不为 True 说明指令被拒绝
        if r.get("accepted") is not True:
            # 抛出带指令名与原因的错误
            raise RuntimeError(f"{action} 被拒绝 accepted={r.get('accepted')}: {r}")
        # 校验通过则原样返回响应
        return r

    # 更新本地镜像的位置与虚拟时间
    def _advance(self, r: dict, x: float, y: float) -> dict:
        """更新本地镜像状态（位置、虚拟时间）。"""
        # 把本地位置更新为本次指令的目标坐标
        self.position = (x, y)
        # 响应里带虚拟时间字段且非空时
        if "virtual_time_s" in r and r["virtual_time_s"]:
            # 用服务端返回的虚拟时间同步本地镜像
            self.virtual_time = r["virtual_time_s"]
        # 返回响应，便于链式使用
        return r

    # 发送 /enter 指令：登记机器人进入比赛场地
    def enter(self) -> dict:
        # 组装公共字段并 POST /enter，再校验响应
        return self._check(self.post("/enter", self._base(self._new_request_id("enter"))), "enter")

    # 发送 /measure 指令：在 (x,y) 检测指定频道的示向度
    def measure(self, x: float, y: float, channel: int) -> dict:
        # 先构造 measure 请求的公共字段
        payload = self._base(self._new_request_id("measure"))
        # 在请求体中填检测点坐标
        payload["position"] = {"x": x, "y": y}
        # 在请求体中填检测频道
        payload["channel"] = channel
        # POST /measure 并校验响应
        r = self._check(self.post("/measure", payload), "measure")
        # 把本地频道镜像更新为本次检测频道
        self.channel = channel
        # 更新本地位置/时间并返回响应
        return self._advance(r, x, y)

    # 发送 /clear 指令：在 (x,y) 清除指定频道的源
    def clear(self, x: float, y: float, channel: int) -> dict:
        # 构造 clear 请求的公共字段
        payload = self._base(self._new_request_id("clear"))
        # 在请求体中填清除点坐标
        payload["position"] = {"x": x, "y": y}
        # 在请求体中填清除频道
        payload["channel"] = channel
        # POST /clear 并校验响应
        r = self._check(self.post("/clear", payload), "clear")
        # 更新本地位置/时间并返回响应
        return self._advance(r, x, y)

    # 发送 /exit 指令：结束本次比赛并结算
    def exit(self) -> dict:
        # 组装公共字段并 POST /exit，再校验响应
        return self._check(self.post("/exit", self._base(self._new_request_id("exit"))), "exit")


# ---------------------------------------------------------------------------
# 离线 Mock 模拟器
# ---------------------------------------------------------------------------
# 离线 Mock 模拟器：按附件 1/2 规则模拟 /measure 与 /clear，用于无真实模拟器时自测
class MockSimulator:
    """离线 Mock：生成随机源，按附件 1/2 规则模拟 /measure 与 /clear，并累计虚拟时间。

    误差模型：同一 (频道, 检测点) 重复检测误差固定（与题设"同地点误差固定"一致）。
    """

    # 构造 Mock：设置随机源参数、覆盖半径区间、定向源比例，并生成随机源
    def __init__(self, n_sources: int = 12, seed: int = 2026,
                 directional: bool = False, r_target: float = 1800.0,
                 r_eff: tuple = (1000.0, 1500.0),
                 directional_probability: float = 0.65):
        # 用固定种子创建随机数生成器，保证实验可复现
        self.rng = random.Random(seed)
        # 保存目标圆域半径（源分布范围）
        self.r_target = r_target
        # 保存有效接收半径区间 (Rmin, Rmax)
        self.r_eff = r_eff
        # 保存是否启用定向源标志
        self.directional = directional
        # 保存每个源成为定向源的概率
        self.directional_probability = directional_probability
        # 保存源的总个数
        self.n_sources = n_sources
        # 按参数生成随机源列表（频道、位置、覆盖半径、类型、方向）
        self.sources = self._gen_sources(n_sources, directional)
        # 运行状态
        # 初始化机器狗位置为原点
        self.position = (0.0, 0.0)
        # 初始化当前频道为 1
        self.channel = 1
        # 初始化虚拟时间为 0
        self.virtual_time = 0.0
        # 初始化未进入场地标志，检测/清除前必须先 /enter
        self.entered = False
        # 误差缓存：同一 (频道, 检测点) 的检测误差固定不变（与题设一致）
        self._err_cache = {}

    # 在半径 r_target 的圆盘内均匀采样一个随机位置
    def _rand_pos(self):
        # 圆盘内均匀采样
        # 开方修正保证半径在圆盘内均匀分布（避免中心过密）
        r = self.r_target * math.sqrt(self.rng.random())
        # 随机采样方位角 a（0~2π 均匀）
        a = self.rng.uniform(0, 2 * math.pi)
        # 由极坐标 (r,a) 还原直角坐标位置
        return (r * math.cos(a), r * math.sin(a))

    # 生成 n 个随机源（不重复频道、随机位置与覆盖半径、类型与方向）
    def _gen_sources(self, n, directional):
        # 从 20 个频道中无放回随机抽 n 个，保证频道唯一
        channels = self.rng.sample(CHANNELS, n)
        # srcs 累积生成的源字典列表
        srcs = []
        # 逐个频道生成对应的源
        for c in channels:
            # 在圆盘内随机采样该源的位置
            pos = self._rand_pos()
            # 在 [Rmin, Rmax] 内随机采样该源的有效接收半径 R
            R = self.rng.uniform(*self.r_eff)
            # 按概率决定源类型：定向或全向（三元表达式跨两行）
            kind = ("directional" if directional and
                    self.rng.random() < self.directional_probability else "omni")
            # 定向源随机一个指向角度（度），全向源则为 None
            direction = self.rng.uniform(0, 360) if directional else None
            # 把该源的频道、位置、半径、类型、方向与未清除标志存入列表
            srcs.append({"channel": c, "pos": pos, "R": R,
                         "kind": kind, "direction": direction, "cleared": False})
        # 返回生成的源列表
        return srcs

    # 按频道查找尚未被清除的源，找不到返回 None
    def _find(self, channel):
        # 遍历所有源
        for s in self.sources:
            # 匹配频道且未清除的源即目标
            if s["channel"] == channel and not s["cleared"]:
                # 返回找到的源
                return s
        # 没有匹配源时返回 None
        return None

    # 判断检测点 point 是否落在源 s 的有效覆盖角内（全向恒真，定向 ±90°）
    def _in_sector(self, s, point):
        """point 是否在源 s 的有效覆盖角（全向恒真，定向 ±90°）内。"""
        # 全向源对所有方向都有效
        if s["kind"] == "omni":
            # 全向源直接返回 True
            return True
        # 计算源指向检测点的方位角 ang（定向源的主方向基准）
        ang = _bearing(s["pos"], point)  # 源指向检测点的方位角
        # 求检测方位与源主方向的夹角并归一到 [0,360)
        delta = (ang - s["direction"]) % 360
        # 取较小夹角，得到与主方向的绝对偏差（0~180°）
        delta = min(delta, 360 - delta)
        # 偏差不超过 90° 说明点落在定向源的半盘覆盖内
        return delta <= 90.0

    # 返回 (频道, 检测点) 的固定检测误差（缓存，同地点误差不变）
    def _error(self, channel, point):
        # 用频道与舍入到 0.1 m 的坐标构成缓存键，模拟“同地点误差固定”
        key = (channel, round(point[0], 1), round(point[1], 1))
        # 该位置首次检测时才生成误差
        if key not in self._err_cache:
            # 在 [-1,1] 度内随机生成并缓存该点的误差
            self._err_cache[key] = self.rng.uniform(-1.0, 1.0)
        # 返回该点固定的检测误差
        return self._err_cache[key]

    # 按移动距离、换频耗时与动作耗时累计虚拟时间
    def _advance(self, move_dist, switch, action_time):
        # 虚拟时间 += 移动时间(距离/速度) + 换频时间 + 动作固定耗时
        self.virtual_time += move_dist / SPEED + switch + action_time

    # -- 检测 --
    # 模拟 /measure：返回 no_signal/near/direction 三种结果之一并累计时间
    def measure(self, x, y, channel):
        # 未先 /enter 则不允许检测
        if not self.entered:
            # 抛错提示必须先进入场地
            raise RuntimeError("必须先 /enter")
        # 查找该频道当前是否有未清除的源
        s = self._find(channel)
        # 换频道才计 1 s 换频耗时，同频道则为 0
        switch = 1.0 if channel != self.channel else 0.0
        # 累计移动时间 + 换频时间 + 检测固定耗时 5 s
        self._advance(_dist(self.position, (x, y)), switch, 5.0)
        # 更新机器狗位置为检测点
        self.position = (x, y)
        # 更新当前频道
        self.channel = channel

        # 该频道没有源时
        if s is None:
            # 返回无信号结果
            return {"measure_result": "no_signal"}
        # 计算检测点到源的距离 d
        d = _dist((x, y), s["pos"])
        # 超出有效接收半径或不在定向覆盖角内，均视为无信号
        if d > s["R"] or not self._in_sector(s, (x, y)):
            # 返回无信号结果
            return {"measure_result": "no_signal"}
        # 距离足够近（≤5 m）时方位角不可靠
        if d <= NEAR_R:
            # 返回 near 结果（表示很近但方向未知）
            return {"measure_result": "near"}
        # 示向度 = 真实方位角 + 该点固定误差，取模 360 并保留两位小数
        svd = round((_bearing((x, y), s["pos"]) + self._error(channel, (x, y))) % 360, 2)
        # 返回含示向度 svd 的检测结果
        return {"measure_result": "direction", "svd_deg": svd}

    # -- 清除 --
    # 模拟 /clear：靠近源 20 m 内才能清除，否则返回未发现目标
    def clear(self, x, y, channel):
        # 未先 /enter 则不允许清除
        if not self.entered:
            # 抛错提示必须先进入场地
            raise RuntimeError("必须先 /enter")
        # 查找该频道当前是否有未清除的源
        s = self._find(channel)
        # 累计移动时间；命中源则动作耗时 5 s，未命中 3 s
        self._advance(_dist(self.position, (x, y)), 0.0, 5.0 if s and _dist((x, y), s["pos"]) <= CLEAR_R else 3.0)
        # 更新机器狗位置为清除点
        self.position = (x, y)
        # 没有源或距离超过清除半径 20 m 时无法清除
        if s is None or _dist((x, y), s["pos"]) > CLEAR_R:
            # 返回范围内无目标结果
            return {"clear_result": "no_target_in_range"}
        # 标记该源已被清除
        s["cleared"] = True
        # 返回清除成功结果
        return {"clear_result": "success"}

    # -- 状态 --
    # 返回已被清除的源个数，用于统计进度
    def cleared_count(self):
        # 对已清除的源计数并返回
        return sum(1 for s in self.sources if s["cleared"])

    # 返回源的总个数
    def total_sources(self):
        # 返回源列表长度
        return len(self.sources)


# 根据命令行参数选择真实客户端或离线 Mock
def build_client_or_mock(args) -> object:
    """根据命令行参数选择真实客户端或 Mock。"""
    # 默认（mock=True 或缺省）使用离线 Mock
    if getattr(args, "mock", True):
        # 用命令行参数构造 MockSimulator（源数、种子、是否定向）
        return MockSimulator(
            n_sources=getattr(args, "n_sources", 12),
            seed=getattr(args, "seed", 2026),
            directional=getattr(args, "directional", False),
        )
    # 否则构造真实 SimClient（队伍编号、服务地址）
    return SimClient(robot_id=getattr(args, "robot_id", "<参赛队号>"),
                     base_url=getattr(args, "base_url", "http://127.0.0.1:2026"))
