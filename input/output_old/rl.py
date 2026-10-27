# -*- coding: utf-8 -*-
"""受限 Q-learning：为"保证覆盖听点"求最优访问顺序。

状态编码为 (当前位置, 已访问掩码, 已发现源数, 待测源数, 当前频道)；
动作受硬覆盖约束与合法动作掩码限制；奖励含扫描时间、发现/二次定位奖励与漏检惩罚。
"""
from __future__ import annotations

from collections import defaultdict
import math

import numpy as np

from geo import N_CHANNELS, SPEED, dist, optimized_open_order

# 双测定位源的清除标称时间（秒）：两条测向线交叉角足够时可直接定位清除
CLEAR_DOUBLE = 180.0
# The single-bearing clearer now tries a short homing pass before the finite
# wedge sweep.  Its expected cost is therefore closer to a few hundred seconds
# than to the old worst-case 950 s estimate; this lets Q-learning stop after
# the seven certified Q3 coverage points when extra bearings have low value.
# 单测向源的清除时间（秒）：需先短程寻的再做有限楔形扫描，期望代价约几百秒
CLEAR_SINGLE = 220.0
# 近场命中（已进入源附近）时的清除时间（秒），几乎可忽略不计
CLEAR_NEAR = 25.0


def _cov_idxs(points):
    """强制覆盖点集合。

    当前两套布局的听点集**本身就是**最小保证覆盖集（问题三 7 点环、问题四 31 点格），
    故全部听点都是强制点，安全屏蔽禁止在覆盖完成前停止。
    """
    # 返回全体听点索引的冻结集合：每个听点都是必须访问的强制覆盖点
    return frozenset(range(len(points)))


def _best_crossing_angle(observations):
    # 初始化最大测向线交叉角为 0
    best = 0.0
    # 遍历所有两两不同的观测组合，寻找最大的交叉角
    for i in range(len(observations)):
        # 对每一对观测 (i, j)，比较其测向线方向角
        for j in range(i + 1, len(observations)):
            # 两方向角之差对 180° 取模，得到夹角的主值
            delta = abs((observations[i][1] - observations[j][1]) % 180.0)
            # 取 delta 与其补角中的较小者，并更新历史最大交叉角
            best = max(best, min(delta, 180.0 - delta))
    # 返回所有观测对之间的最大交叉角（用于判断几何是否足够）
    return best


def needs_measurement(observations):
    """Two well-separated bearings are enough; poor pairs need refinement."""
    # 观测不足 2 条、或最大交叉角 < 35° 时，几何太差仍需补充测量
    return len(observations) < 2 or _best_crossing_angle(observations) < 35.0


# 稀疏表格型 Q 学习智能体：带硬覆盖约束与合法动作掩码
class SearchQAgent:
    """Sparse tabular Q learner with hard coverage and legal-action masks."""

    def __init__(self, listening_points, coverage_idxs=None, alpha=0.18,
                 gamma=0.96, eps=0.22, found_bonus=130.0,
                 second_bonus=210.0, miss_penalty=1e6,
                 clear_double=CLEAR_DOUBLE, clear_single=CLEAR_SINGLE,
                 clear_near=CLEAR_NEAR, candidate_width=6,
                 first_hit_only=False, channel_scan_fraction=1.0,
                 seed=20260911):
        # 把每个听点坐标转为 float 型 numpy 数组，作为候选动作位置
        self.points = [np.asarray(p, dtype=float) for p in listening_points]
        # K = 听点总数；停止动作的索引取为 K（超出听点范围，代表结束扫描）
        self.K = len(self.points)
        # 若未显式指定覆盖点，则默认全部听点都是强制覆盖点
        self.coverage_idxs = (_cov_idxs(self.points) if coverage_idxs is None
                              else frozenset(coverage_idxs))
        # 学习率：控制 Q 值每次更新的步长
        self.alpha = alpha
        # 折扣因子：权衡未来回报相对当前回报的重要性
        self.gamma = gamma
        # 探索率：ε-greedy 策略中随机探索的概率
        self.eps = eps
        # 发现一个新源的正向奖励
        self.found_bonus = found_bonus
        # 二次定位奖励：把一个单测向源补测成可定位几何的额外奖励
        self.second_bonus = second_bonus
        # 漏检惩罚：存在未清除源时的巨额代价
        self.miss_penalty = miss_penalty
        # 双测定位源的清除时间
        self.clear_double = clear_double
        # 单测向源的清除时间
        self.clear_single = clear_single
        # 近场命中源的清除时间
        self.clear_near = clear_near
        # 每步候选动作的宽度（近似最近邻候选个数）
        self.candidate_width = candidate_width
        # 是否只对首次命中做二次测量（节省时间）
        self.first_hit_only = first_hit_only
        # 频道扫描比例：限制单步实际扫描的频道子集（快速风险模式用）
        self.channel_scan_fraction = float(np.clip(channel_scan_fraction, 0.0, 1.0))
        # 停止动作编号 = K，用于让智能体主动结束扫描
        self.stop_action = self.K
        # Q 表：嵌套字典 {状态: {动作: Q 值}}
        self.Q = defaultdict(dict)
        # 缓存：精确开路径尾代价的备忘录
        self._tail_cache = {}
        # 2-opt 开路径的引导访问顺序（从原点出发）
        self.guide_order = optimized_open_order(self.points, start=np.zeros(2))
        # 引导顺序中每个听点索引对应的排名（用于确定性部署）
        self.guide_rank = {point_idx: rank
                           for rank, point_idx in enumerate(self.guide_order)}
        # 固定种子的随机数生成器，保证实验可复现
        self.rng = np.random.default_rng(seed)

    @staticmethod
    def _mask(visited):
        # 把已访问听点索引集合编码成一个整数位掩码
        mask = 0
        # 对每个已访问听点，把其索引对应的二进制位置 1
        for j in visited:
            mask |= 1 << int(j)
        # 返回位掩码
        return mask

    @staticmethod
    def counts(obs, near):
        # 已发现源总数 = 有方向观测的源数 + 近场命中的源数
        n_found = len(obs) + len(near)
        # 单测向源数 = 仍需补充测量的源个数
        n_single = sum(needs_measurement(v) for v in obs.values())
        # 返回 (已发现源数, 单测向源数)
        return n_found, n_single

    def encode(self, p_idx, visited, obs, near, current_channel):
        # 统计已发现与单测向源数量，作为状态的两个分量
        n_found, n_single = self.counts(obs, near)
        # 返回五元组状态：当前位置、已访问掩码、已发现数、单测向数、当前频道
        return (int(p_idx), self._mask(visited), n_found, n_single,
                int(current_channel))

    def cov_done(self, visited):
        # 判断是否所有强制覆盖点都已访问（即覆盖完成）
        return self.coverage_idxs.issubset(visited)

    def _position(self, p_idx):
        # p_idx<0 表示起点（原点），否则返回对应听点坐标
        return np.zeros(2) if p_idx < 0 else self.points[p_idx]

    def valid_actions(self, p_idx, visited):
        # 未访问的听点构成候选动作集合
        unvisited = [j for j in range(self.K) if j not in visited]
        # 若无未访问点，只允许"停止"动作
        if not unvisited:
            return [self.stop_action]
        # 当前所在位置坐标
        cur = self._position(p_idx)
        # 按距当前位置的欧氏距离从小到大排序未访问点（就近优先）
        unvisited.sort(key=lambda j: dist(cur, self.points[j]))
        # 强制覆盖点中尚未访问的部分（必须优先访问）
        mandatory = [j for j in unvisited if j in self.coverage_idxs]
        # 非强制（可选）听点中尚未访问的部分（用于改善几何）
        optional = [j for j in unvisited if j not in self.coverage_idxs]
        # 从强制点中最多取 candidate_width-2 个（至少 1 个）纳入候选
        n_mandatory = min(len(mandatory), max(1, self.candidate_width - 2))
        actions = mandatory[:n_mandatory]
        # 用可选点补齐候选列表到 candidate_width 个
        actions += optional[:self.candidate_width - len(actions)]
        # 若候选仍为空（防御性回退），则取就近的未访问点
        if not actions:
            actions = unvisited[:self.candidate_width]
        # 取 2-opt 引导顺序中第一个尚未访问的听点
        guide_next = next((j for j in self.guide_order if j in unvisited), None)
        # 若引导点不在候选中，用其替换候选列表末位，确保引导点可被选中
        if guide_next is not None and guide_next not in actions:
            actions[-1] = guide_next
        # 覆盖已完成时，把"停止"动作加入候选
        if self.cov_done(visited):
            actions.append(self.stop_action)
        # 返回合法动作列表
        return actions

    def _prior(self, state, action):
        # 若动作是停止动作，则代价对应"带着弱几何停止"所触发的高昂清除
        if action == self.stop_action:
            # Stopping with weak geometry triggers the expensive wedge sweep.
            # 单测向源越多停止代价越高：负值表示时间成本
            return -max(1.0, state[3] * self.clear_single)
        # 从当前位置移动到目标听点的旅行距离
        travel = dist(self._position(state[0]), self.points[action])
        # 模拟执行该动作后的已访问掩码
        visited_mask = state[1] | (1 << action)
        # 剩余尚未访问的强制覆盖点元组
        remaining = tuple(j for j in self.coverage_idxs
                          if not (visited_mask >> j) & 1)
        # 覆盖点≤8 时用精确尾代价，否则用 2-opt 引导尾代价
        tail = (self._coverage_tail(action, remaining)
                if len(self.coverage_idxs) <= 8
                else self._guide_tail(action, remaining))
        # 返回负的 (旅行+尾代价)/速度，即该动作的启发式先验 Q 值（时间代价）
        return -(travel + tail) / SPEED

    def _guide_tail(self, p_idx, remaining):
        """Open-route cost-to-go along the 2-opt guide, filtered by mask."""
        # 取引导顺序中仍属于剩余覆盖点的部分
        ordered = [j for j in self.guide_order if j in remaining]
        # 若已无剩余点，尾代价为 0
        if not ordered:
            return 0.0
        # 尾代价 = 当前位置到第一个引导点的距离
        total = dist(self.points[p_idx], self.points[ordered[0]])
        # 累加引导顺序上相邻两点的距离
        total += sum(dist(self.points[a], self.points[b])
                     for a, b in zip(ordered, ordered[1:]))
        # 返回沿引导顺序的剩余开路径总长
        return total

    def _coverage_tail(self, p_idx, remaining):
        """Exact open-path cost-to-go for the seven-point Q3 safety set."""
        # 无剩余点或覆盖点过多时，退化为 0（不做精确 DP）
        if not remaining or len(self.coverage_idxs) > 8:
            return 0.0
        # 状态键 = (当前位置, 剩余覆盖点元组)
        key = (p_idx, remaining)
        # 若未缓存，则穷举求"从 p_idx 出发访问完 remaining"的最短开路径
        if key not in self._tail_cache:
            self._tail_cache[key] = min(
                dist(self.points[p_idx], self.points[j])
                + self._coverage_tail(j, tuple(k for k in remaining if k != j))
                for j in remaining
            )
        # 返回缓存的最短尾代价
        return self._tail_cache[key]

    def value(self, state, action):
        # 查 Q 表；若无记录则回退到启发式先验代价 _prior
        return self.Q[state].get(action, self._prior(state, action))

    def act(self, state, p_idx, visited, greedy=False):
        # 先获取当前状态的合法动作列表
        candidates = self.valid_actions(p_idx, visited)
        # Problem 4 has no optional refinement points: every listening point
        # is part of the certified full-view cover.  Once exploration is
        # finished, the open 2-opt route is the deterministic shortest-route
        # prior; letting a noisy learned Q value reorder those mandatory
        # points only increases travel time without adding information.
        # 问题四没有可选细化点：全部听点都是认证覆盖点；探索结束后用 2-opt 最短
        # 开路径作为确定性先验，避免噪声 Q 值打乱强制点顺序而徒增旅行时间。
        if greedy and self.coverage_idxs == frozenset(range(self.K)):
            # 贪心/部署模式下，直接取引导顺序中第一个未访问点作为动作
            guide_next = next((j for j in self.guide_order if j not in visited), None)
            # 若存在引导点则返回它
            if guide_next is not None:
                return int(guide_next)
        # ε-greedy：以概率 eps 随机探索候选动作
        if not greedy and self.rng.random() < self.eps:
            # 随机选择候选动作
            return int(self.rng.choice(candidates))
        # 否则贪心选择 Q 值（value）最大的动作
        return max(candidates, key=lambda a: self.value(state, a))

    def update(self, state, action, reward, next_state, next_actions, done):
        # 当前状态-动作对的旧 Q 值
        old = self.value(state, action)
        # 未来价值：终止时为 0，否则取下一状态所有合法动作的最大 Q 值
        future = 0.0 if done else max(self.value(next_state, a)
                                      for a in next_actions)
        # Q-learning 更新目标 = 即时奖励 + 折扣 × 未来最大价值
        target = reward + self.gamma * future
        # Q-learning 更新公式：Q ← Q + α (target − Q)
        self.Q[state][action] = old + self.alpha * (target - old)

    def scan(self, sim, action, obs, near):
        """在听点 action 扫频道，就地更新 obs/near，返回发现的统计量。

        未知频道必须在**认证覆盖点**上扫；细化点只用于改善已发现源的几何，
        在那里扫未知频道纯属浪费（曾是 Q3 的主要开销）。
        `scan` 与 `step` 分离，使部署阶段可以与"在线清除调度"交织执行。
        """
        # 目标听点的坐标
        point = self.points[action]
        # 本次扫描新发现源数、新增二次定位源数，初始为 0
        new_found = new_second = 0
        # 判断该动作是否为认证覆盖点（允许扫未知频道）
        is_coverage_action = action in self.coverage_idxs
        # 遍历全部频道（1..N_CHANNELS）
        for channel in range(1, N_CHANNELS + 1):
            # 该频道已近场命中则跳过
            if channel in near:
                continue
            # 获取该频道已有的方向观测列表（可能为空）
            observations = obs.get(channel, [])
            # 非覆盖点且尚无观测时，不在此处扫未知频道（纯属浪费）
            if not is_coverage_action and not observations:
                continue
            # 快速风险模式下，按确定性频道队列抽样，跳过未排到的频道
            if (not observations and self.channel_scan_fraction < 1.0
                    and not self._scheduled_channel(action, channel)):
                continue
            # first_hit_only 模式：覆盖点上只做首次命中，不再重复测同一频道
            if observations and self.first_hit_only and is_coverage_action:
                continue
            # 已有观测且几何已足够好（交叉角≥35°），无需再测
            if observations and not needs_measurement(observations):
                continue
            # 在该听点对该频道执行一次测量
            result = sim.measure(point[0], point[1], channel)
            # 若返回的是方向测量结果
            if result["measure_result"] == "direction":
                # 取回该频道的观测列表（首次会创建空列表）
                observations = obs.setdefault(channel, [])
                # 记录测量前的几何状态：是否需要补充测量
                was_single = needs_measurement(observations)
                # 若此前该频道无观测，说明这是新发现的源
                if not observations:
                    new_found += 1
                # 把本次方向观测（听点坐标 + 测向角）追加进列表
                observations.append((point.copy(), result["svd_deg"]))
                # 若测量后几何由"不足"变"足够"，则新增一个二次定位
                if was_single and not needs_measurement(observations):
                    new_second += 1
            # 若返回的是近场命中结果
            elif result["measure_result"] == "near":
                # 若该频道此前既无方向也无近场记录，则视为新发现
                if channel not in obs and channel not in near:
                    new_found += 1
                # 移除该频道的方向观测（近场命中取代方向信息）
                obs.pop(channel, None)
                # 记录近场命中位置
                near[channel] = point.copy()
        # 返回 (新发现源数, 新增二次定位源数)
        return new_found, new_second

    def step(self, sim, action, obs, near, total_sources=None):
        # 若动作是访问某个听点（而非停止）
        if action < self.K:
            # 记录扫描前的虚拟时间
            t0 = sim.virtual_time
            # 执行扫描，更新 obs/near，返回新发现统计
            new_found, new_second = self.scan(sim, action, obs, near)
            # 本次扫描耗时 = 扫描后的虚拟时间 - 扫描前
            cost = sim.virtual_time - t0
            # 奖励 = 负扫描耗时 + 发现奖励×新发现数 + 二次定位奖励×新增二次定位数
            reward = (-cost + self.found_bonus * new_found
                      + self.second_bonus * new_second)
            # 返回奖励，未终止
            return reward, False

        # 停止动作：统计当前所有观测
        n_found, n_single = self.counts(obs, near)
        # 双测定位源数 = 已发现数 - 近场命中数 - 单测向数
        n_double = n_found - len(near) - n_single
        # 估计总清除时间 = 双测清除×双测数 + 单测清除×单测数 + 近场清除×近场数
        estimated_clear = (self.clear_double * n_double
                           + self.clear_single * n_single
                           + self.clear_near * len(near))
        # 漏检数 = 真实源总数 - 已发现数（未知总数时为 0）
        missing = max(0, total_sources - n_found) if total_sources is not None else 0
        # 返回 (负估计清除时间 - 漏检惩罚) 作为终态奖励，并标记 done=True
        return -estimated_clear - self.miss_penalty * bool(missing), True

    def _scheduled_channel(self, point_idx, channel):
        """Deterministic channel cohort used only by the fast-risk mode."""
        # 计算本轮实际要扫描的频道配额（20 个频道中按比例向下取整）
        quota = int(math.floor(20.0 * self.channel_scan_fraction + 1e-9))
        # 配额 ≥ 20 即全频道扫描
        if quota >= 20:
            return True
        # Relatively prime strides spread every channel over the route.
        # 用与 20 互质的步长 (13,7) 把每个频道均匀散布到访问路线上
        return ((13 * int(point_idx) + 7 * int(channel)) % 20) < quota


def train_q_search(sim_factory, agent, episodes=600, max_steps=None,
                   verbose=True):
    """Train on random fields; the returned curve is search time per episode."""
    # 每局搜索时间曲线与每局是否全部发现的成功标记
    curve, success = [], []
    # 记录初始探索率
    eps0 = agent.eps
    # 每局步数上限 = 指定最大步数或听点数+2（允许一次停止动作）
    limit = max_steps or agent.K + 2
    # 逐局训练
    for episode in range(episodes):
        # 探索率线性退火：从 eps0 逐步降到下限 0.025
        agent.eps = max(0.025, eps0 * (1.0 - episode / max(episodes, 1)))
        # 用工厂函数生成该局的随机场景模拟器
        sim = sim_factory(episode)
        # 标记模拟器已进入目标区域
        sim.entered = True
        # 初始化观测、近场、已访问集合与当前位置（-1 表示原点）
        obs, near, visited = {}, {}, set()
        p_idx = -1
        # 读取该局真实源总数（用于终态漏检判断）
        total = sim.total_sources()
        # 在该局步数限制内迭代
        for _ in range(limit):
            # 编码当前状态
            state = agent.encode(p_idx, visited, obs, near,
                                 getattr(sim, "channel", 1))
            # 依据策略选择动作
            action = agent.act(state, p_idx, visited)
            # 执行动作，得到奖励与是否终止
            reward, done = agent.step(sim, action, obs, near, total)
            # 若动作是访问听点，则更新已访问集合与当前位置
            if action < agent.K:
                visited.add(action)
                p_idx = action
            # 编码执行后的下一状态
            next_state = agent.encode(p_idx, visited, obs, near,
                                      getattr(sim, "channel", 1))
            # 计算下一状态的合法动作（用于 Q 更新取 max）
            next_actions = agent.valid_actions(p_idx, visited)
            # Q-learning 更新
            agent.update(state, action, reward, next_state, next_actions, done)
            # 若终止则提前结束本局
            if done:
                break
        # 记录本局搜索耗时（虚拟时间）
        curve.append(float(sim.virtual_time))
        # 记录本局是否全部源都被发现
        success.append(len(obs) + len(near) == total)
        # 每 100 局或最后一局打印滚动统计
        if verbose and (episode % 100 == 0 or episode == episodes - 1):
            print(f"  [RL] ep {episode:4d} search_avg={np.mean(curve[-100:]):.1f}s "
                  f"detect_rate={np.mean(success[-100:]):.1%} states={len(agent.Q)}",
                  flush=True)
    # 训练结束后关闭探索（纯贪心用于部署）
    agent.eps = 0.0
    # 返回搜索时间曲线
    return curve


