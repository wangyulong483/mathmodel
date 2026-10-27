# -*- coding: utf-8 -*-
"""共享几何工具：极坐标/笛卡尔互转、测向线、交会定位、直径/最小包围圆、三角格。

极坐标 (r, φ) 为主坐标，φ 与示向度同轴（自 +x 逆时针）；笛卡尔 (x, y) 为等价形式。
"""
from __future__ import annotations

import math

import numpy as np
from scipy.spatial import ConvexHull

# 常量
# 目标圆域半径 R_TARGET：干扰源只出现在以原点为中心、半径 1800 m 的圆盘内
R_TARGET = 1800.0      # 目标圆域半径 / m
# 有效接收半径下界 R_EFF_MIN：源能被机器狗探测到的最小距离（1000 m）
R_EFF_MIN = 1000.0     # 有效接收半径下界 / m
# 有效接收半径上界 R_EFF_MAX：源能被机器狗探测到的最大距离（1500 m）
R_EFF_MAX = 1500.0     # 有效接收半径上界 / m
# 常数 DEG：度与弧度的换算系数（π/180），用于把角度统一为弧度制
DEG = math.pi / 180.0  # 度 -> 弧度
# 示向度误差上界 BEARING_ERR：每次测量的示向度最多偏差 ±1°
BEARING_ERR = 1.0      # 示向度误差上界 / °
# 机器狗移动速度 SPEED：5 m/s，用于把移动距离换算成移动耗时
SPEED = 5.0            # 机器狗移动速度 / m·s⁻¹
# 频道总数 N_CHANNELS：干扰源随机占用 1~20 频道
N_CHANNELS = 20        # 频道数
# 清除半径 CLEAR_R：机器狗靠近源 20 m 以内即可清除该频道源
CLEAR_R = 20.0         # 清除半径 / m
# 近距离阈值 NEAR_R：距源 5 m 以内方位角不可靠，检测直接判定为 near
NEAR_R = 5.0           # 近距离阈值 / m


# 把笛卡尔坐标 (x, y) 转为极坐标 (r, φ/°)，供按距离、方位判断使用
def polar(xy):
    """笛卡尔 -> 极坐标 (r, φ/°)"""
    # 把输入拆成 x、y 两个分量（兼容 list/tuple/numpy 数组输入）
    x, y = np.asarray(xy)
    # 返回半径 r=hypot(x,y) 与方位角 φ=degrees(arctan2(y,x))，φ 与示向度同轴
    return float(np.hypot(x, y)), float(np.degrees(np.arctan2(y, x)))


# 把极坐标 (r, φ/°) 转为笛卡尔坐标 (x, y)，用于生成网格点或已知半径方位的位置
def to_xy(r, phi_deg):
    """极坐标 -> 笛卡尔"""
    # 先把角度 φ 从度转为弧度，供 cos/sin 使用
    p = math.radians(phi_deg)
    # 按 x=r·cosφ、y=r·sinφ 还原直角坐标向量
    return np.array([r * math.cos(p), r * math.sin(p)])


# 计算 S 指向 G 的真实示向度（方位角，度），范围 [0, 360)
def bearing(S, G):
    """S 指向 G 的真实示向度（方位角）/°"""
    # 求从检测点 S 到目标点 G 的方向向量 d
    d = np.asarray(G) - np.asarray(S)
    # 用 arctan2 求 d 的方位角并转度，再取模 360 归一到 [0, 360)
    return float(np.degrees(np.arctan2(d[1], d[0])) % 360.0)


# 计算带符号最小角度差 a-b 并归一化到 [-180, 180)，用于判断两个示向度是否一致
def angle_difference(a, b):
    """Signed smallest angle a-b in degrees, in [-180, 180)."""
    # 先做差再加 180 取模 360，最后减 180，得到最小带符号角度差
    return (float(a) - float(b) + 180.0) % 360.0 - 180.0


# 计算两点 a、b 之间的欧氏距离，用于移动耗时与覆盖判定
def dist(a, b):
    """欧氏距离"""
    # 用 numpy 向量范数求差向量的长度，即两点距离
    return float(np.linalg.norm(np.asarray(a) - np.asarray(b)))


# 生成过点 S、方向角为 beta 的测向线，返回系数 (a,b,d) 满足 a·x + b·y = d
def line_through(S, beta_deg):
    """过 S、方向角 beta 的测向线，返回 (a, b, d) 满足 a x + b y = d。"""
    # 把方向角 beta 从度转为弧度，作为测向线的法向角度使用
    b = math.radians(beta_deg)
    # 解包检测点 S 的 x、y 坐标
    xS, yS = S
    # 由方向角确定直线法向量 (sinβ, -cosβ)：该向量与测向线方向垂直
    a, bb = math.sin(b), -math.cos(b)
    # 代入点 S 求右端常数 d，得到直线方程 a·x + b·y = d 并返回系数
    return a, bb, a * xS + bb * yS


# 求两条直线 L1、L2 的交点，行列式近似为 0（平行）时返回 None
def intersect(L1, L2, tol=1e-9):
    """两直线求交，平行时返回 None。"""
    # 解包 L1 的直线系数 (a1, b1, d1)
    a1, b1, d1 = L1
    # 解包 L2 的直线系数 (a2, b2, d2)
    a2, b2, d2 = L2
    # 计算系数矩阵行列式 det，用于判断两直线是否平行/退化
    det = a1 * b2 - a2 * b1
    # 行列式绝对值小于容差说明近乎平行，无唯一交点
    if abs(det) < tol:
        # 平行时返回 None 表示无交点
        return None
    # 用克莱姆法则解方程组 a·x+b·y=d，返回交点坐标向量
    return np.array([(d1 * b2 - d2 * b1) / det, (a1 * d2 - a2 * d1) / det])


# 求过三点 a、b、c 的外接圆（圆心、半径），三点共线退化时返回 None
def circle_through(a, b, c):
    """三点外接圆（圆心、半径），退化时返回 None。"""
    # 解包 a 点坐标 (ax, ay)
    ax, ay = a
    # 解包 b 点坐标 (bx, by)
    bx, by = b
    # 解包 c 点坐标 (cx, cy)
    cx, cy = c
    # 计算三点有向面积的两倍 d，作为外接圆圆心公式的分母
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    # 三点共线时 d≈0，外接圆不存在
    if abs(d) < 1e-12:
        # 退化时返回 None
        return None
    # 用外接圆圆心公式求圆心 x 坐标 ux（标准解析解）
    ux = ((ax ** 2 + ay ** 2) * (by - cy) + (bx ** 2 + by ** 2) * (cy - ay)
          + (cx ** 2 + cy ** 2) * (ay - by)) / d
    # 用外接圆圆心公式求圆心 y 坐标 uy
    uy = ((ax ** 2 + ay ** 2) * (cx - bx) + (bx ** 2 + by ** 2) * (ax - cx)
          + (cx ** 2 + cy ** 2) * (bx - ax)) / d
    # 把圆心坐标组装成 numpy 数组 c0
    c0 = np.array([ux, uy])
    # 半径即圆心到任一点的距离，返回 (圆心, 半径)
    return c0, dist(c0, a)


# 精确求小规模点集的最小包围圆：枚举两点直径圆与三点外接圆取最小
def min_enclosing_circle(pts):
    """小规模点集最小包围圆（精确：遍历所有两点直径圆与三点外接圆）。"""
    # 统一把点集转成 numpy 数组列表，便于向量加减运算
    pts = [np.asarray(p) for p in pts]
    # best 记录当前最优 (半径, 圆心)，初值半径设为无穷大
    best = (math.inf, None)
    # 点集规模 n，供双层循环枚举点对使用
    n = len(pts)
    # 外层枚举第一个点 i
    for i in range(n):
        # 内层枚举第二个点 j（i<j 避免重复）
        for j in range(i + 1, n):
            # 以 i、j 两点为直径端点，圆心取两点中点
            c = (pts[i] + pts[j]) / 2.0
            # 半径即两点距离的一半
            r = dist(pts[i], pts[j]) / 2.0
            # 若该圆覆盖全部点且半径更小，则更新最优解
            if all(dist(p, c) <= r + 1e-9 for p in pts) and r < best[0]:
                # 记录更小的 (半径, 圆心)
                best = (r, c)
    # 三点外接圆枚举：第一层点 i
    for i in range(n):
        # 第二层点 j
        for j in range(i + 1, n):
            # 第三层点 k（严格递增避免重复）
            for k in range(j + 1, n):
                # 求 i、j、k 三点的外接圆（圆心、半径）
                cc = circle_through(pts[i], pts[j], pts[k])
                # 三点共线退化时跳过
                if cc is None:
                    # 跳过本次循环，尝试下一组三点
                    continue
                # 解包外接圆的圆心与半径
                c, r = cc
                # 若该外接圆覆盖全部点且半径更小，则更新最优解
                if all(dist(p, c) <= r + 1e-9 for p in pts) and r < best[0]:
                    # 记录更小的 (半径, 圆心)
                    best = (r, c)
    # 返回最小包围圆的半径与圆心
    return best[0], best[1]


# 求凸多边形直径：两两顶点取最大距离，返回直径长度与对应端点下标对
def convex_diameter(pts):
    """凸多边形直径（顶点两两取最大，返回直径与端点下标对）。"""
    # best 存当前最大距离，pair 存对应端点下标对
    best, pair = 0.0, None
    # 枚举第一个顶点 i
    for i in range(len(pts)):
        # 枚举第二个顶点 j
        for j in range(i + 1, len(pts)):
            # 计算顶点 i、j 之间的距离 d
            d = dist(pts[i], pts[j])
            # 若发现更大距离则更新最优值
            if d > best:
                # 记录更大的直径与端点下标对
                best, pair = d, (i, j)
    # 返回直径长度与端点下标对
    return best, pair


# 交会定位：由多个检测点及其示向度(±err 容差)求源位置的可行凸多边形
def localization_region(S_list, beta_list, err=BEARING_ERR):
    """交会定位法：由检测点与示向度(±err)求定位凸多边形（源位置可行域）。"""
    # lines 收集每个检测点的两条误差边界测向线（±err）
    lines = []
    # 对每个检测点 S 与其示向度 beta 配对遍历
    for S, beta in zip(S_list, beta_list):
        # 加上左边界（beta-err）方向的测向线
        lines.append(line_through(S, beta - err))
        # 加上右边界（beta+err）方向的测向线
        lines.append(line_through(S, beta + err))
    # cand 收集所有通过校验的可行交点候选
    cand = []
    # 枚举第一条直线
    for i in range(len(lines)):
        # 枚举第二条直线（i<j 避免重复）
        for j in range(i + 1, len(lines)):
            # 求两条测向线的交点 P
            P = intersect(lines[i], lines[j])
            # 平行无交点则跳过
            if P is None:
                # 跳过本次循环
                continue
            # ok 标记 P 是否同时满足所有检测约束
            ok = True
            # 对每个检测点及其示向度校验 P 的方位是否落在 ±err 内
            for S, beta in zip(S_list, beta_list):
                # 计算检测点 S 指向 P 的方位角 bP
                bP = bearing(S, P)
                # 若 P 相对某检测点的方位偏差超过 err，说明不在可行域内
                if abs(angle_difference(bP, beta)) > err + 1e-9:
                    # 标记校验失败
                    ok = False
                    # 提前跳出内层校验循环
                    break
            # 通过全部校验才把 P 加入候选点
            if ok:
                # 加入可行交点 P
                cand.append(P)
    # 候选点少于 3 个时无法构成凸多边形
    if len(cand) < 3:
        # 定位失败返回 None
        return None
    # 对候选点求凸包，得到可行域边界
    hull = ConvexHull(np.array(cand))
    # 取出凸包顶点坐标（按 hull.vertices 顺序）
    verts = [np.array(cand[i]) for i in hull.vertices]
    # 计算凸包顶点几何中心，作为极角排序的参考原点
    center = np.mean(verts, axis=0)
    # 按相对中心的极角对顶点做逆时针排序
    verts.sort(key=lambda p: math.atan2(p[1] - center[1], p[0] - center[0]))
    # 返回有序的可行域多边形顶点
    return verts


# 生成间距为 spacing 的三角格点，只保留半径 r_max 圆盘内的点
def triangular_lattice(spacing, r_max):
    """三角格点（间距 spacing）在半径 r_max 内的坐标集合。"""
    # h 是三角格的行间距（等边三角形的高 = spacing·√3/2）
    h = spacing * math.sqrt(3.0) / 2.0
    # seen 用舍入后的坐标键去重，避免浮点重复点
    seen = set()
    # ring 控制向外扩展的搜索环，逐圈扩张直到没有新点
    ring = 1
    # 逐圈扩张，直到一圈没有新增点为止
    while True:
        # added 统计本圈新增的格点数
        added = 0
        # 遍历本环的行下标 iy（从 -ring 到 ring）
        for iy in range(-ring, ring + 1):
            # 遍历本环的列下标 ix
            for ix in range(-ring, ring + 1):
                # 计算格点横坐标 x：相邻行错位半个间距形成三角格
                x = ix * spacing + (iy % 2) * spacing / 2.0
                # 计算格点纵坐标 y：行号乘行间距 h
                y = iy * h
                # 只保留落在半径 r_max 圆盘内的格点（加 1e-6 容差）
                if math.hypot(x, y) <= r_max + 1e-6:
                    # 用舍入到 3 位小数的坐标作去重键
                    key = (round(x, 3), round(y, 3))
                    # 未出现过的新点才加入
                    if key not in seen:
                        # 记录该格点坐标键
                        seen.add(key)
                        # 本圈新增点数加一
                        added += 1
        # 本圈无新增点说明圆盘已全部覆盖
        if added == 0:
            # 停止扩张
            break
        # 扩大搜索环继续向外找
        ring += 1
    # 把去重后的坐标键还原成 numpy 坐标数组并返回
    return [np.array([k[0], k[1]]) for k in seen]


# 用多起点最近邻 + 开路径 2-opt/Or-opt 求优化开路径（访问顺序），起点固定且无需回路
def optimized_open_order(points, start=None):
    """Multi-start nearest-neighbour route improved by open-path 2-opt.

    The start is fixed but the route has no required return edge.  This is a
    polynomial-time routing prior for layouts too large for Held-Karp.
    """
    # 统一把输入点转成浮点 numpy 数组列表
    pts = [np.asarray(p, dtype=float) for p in points]
    # 空点集直接返回空路径
    if not pts:
        # 返回空访问顺序
        return []
    # 起点 origin：未指定时默认原点 (0,0)
    origin = np.zeros(2) if start is None else np.asarray(start, dtype=float)

    # The 31-point directional layout is a finite triangular-lattice patch.
    # Its unit-edge graph has a Hamilton path beginning at the origin, which
    # is strictly better than a generic Euclidean 2-opt route.  Discover such
    # a path only for larger layouts; small layouts keep the generic routine.
    # 对较大布局（≥20 点）尝试寻找单位边图的哈密顿路径（比欧氏 2-opt 更短）
    if len(pts) >= 20:
        # 求点集之间的最小正距离 edge（单位边长度），用于识别三角格单位边
        edge = min(dist(pts[i], pts[j]) for i in range(len(pts))
                   for j in range(i + 1, len(pts))
                   if dist(pts[i], pts[j]) > 1e-6)
        # 存在正的最小边才继续构建邻接关系
        if edge > 0.0:
            # tol 是判断“两点相邻（单位边）”的容差，取相对小量
            tol = max(1e-5, edge * 2e-5)
            # 建立邻接表：两点距离等于单位边（容差内）即相邻
            adjacency = {
                i: [j for j in range(len(pts)) if i != j
                    and abs(dist(pts[i], pts[j]) - edge) <= tol]
                for i in range(len(pts))
            }
            # 每个点都有邻居时才进入哈密顿路径搜索（否则图不连通）
            if all(adjacency[i] for i in range(len(pts))):
                # 按到原点距离由近到远给起点排序，优先尝试靠近原点的起点
                starts = sorted(range(len(pts)),
                                key=lambda i: dist(origin, pts[i]))
                # path 存当前路径，used 存已访问点集
                path, used = [], set()
                # expansions 统计搜索展开次数，用于限制搜索规模
                expansions = 0
                # 展开次数上限，防止搜索爆炸
                expansion_limit = 250000

                # 深度优先搜索从顶点 v 出发的哈密顿路径
                def search(v):
                    # 声明 expansions 为外层变量，允许在闭包内累加
                    nonlocal expansions
                    # 每次搜索调用计数加一
                    expansions += 1
                    # 超过展开上限则放弃本分支
                    if expansions > expansion_limit:
                        # 返回搜索失败
                        return False
                    # 把顶点 v 加入当前路径并标记已访问
                    path.append(v); used.add(v)
                    # 路径已覆盖全部点，说明找到哈密顿路径
                    if len(path) == len(pts):
                        # 返回搜索成功
                        return True
                    # 候选是 v 的邻居中尚未访问的点
                    candidates = [j for j in adjacency[v] if j not in used]
                    # 按“未访问邻居数少者优先”排序，先走约束紧的顶点（Warnsdorff 规则）
                    candidates.sort(key=lambda j: sum(k not in used
                                                       for k in adjacency[j]))
                    # 依次尝试每个候选邻居
                    for nxt in candidates:
                        # 递归搜索下一个顶点，成功则返回
                        if search(nxt):
                            # 找到哈密顿路径，层层返回成功
                            return True
                    # 回溯：撤销 v 的访问标记并从路径中弹出
                    used.remove(v); path.pop()
                    # 该分支失败
                    return False

                # 依次尝试每个候选起点
                for first in starts:
                    # 每次尝试前清空路径与已访问集
                    path.clear(); used.clear()
                    # 从该起点搜索哈密顿路径，成功即返回
                    if search(first):
                        # 返回找到的哈密顿路径（顶点下标顺序）
                        return list(path)
                    # 展开次数超限则终止后续起点尝试
                    if expansions > expansion_limit:
                        # 跳出起点循环
                        break

    # 计算访问顺序 order 从原点出发的行程总长度
    def length(order):
        # current 从原点开始
        current = origin
        # total 累计行程长度
        total = 0.0
        # 依次累加相邻两个访问点之间的距离
        for idx in order:
            # 累加当前点到下一访问点的距离
            total += dist(current, pts[idx])
            # 把当前点更新为刚访问的点
            current = pts[idx]
        # 返回总行程
        return total

    # 从 first 点出发做贪心最近邻，返回访问顺序
    def nearest(first):
        # order 以 first 为首个访问点
        order = [first]
        # remaining 是除 first 外尚未访问的点集
        remaining = set(range(len(pts))) - {first}
        # current 记录当前所在点
        current = pts[first]
        # 只要还有未访问点就继续贪心选择
        while remaining:
            # 选距离当前点最近的下一个点 nxt
            nxt = min(remaining, key=lambda idx: dist(current, pts[idx]))
            # 把 nxt 加入访问顺序
            order.append(nxt)
            # 从未访问集中移除 nxt
            remaining.remove(nxt)
            # 更新当前所在点为 nxt
            current = pts[nxt]
        # 返回贪心访问顺序
        return order

    # 以每个点为起点各跑一次最近邻，取总行程最短的一条作为初始解 best
    best = min((nearest(first) for first in range(len(pts))), key=length)
    # improved 标志：本轮是否还有改进，用于外层循环
    improved = True
    # 反复做局部搜索，直到一轮内没有任何改进
    while improved:
        # 先假设本轮无改进
        improved = False
        # 记录当前最优解的总长度
        best_length = length(best)
        # 2-opt：反转子路径
        # 枚举反转子路径的左端点 left
        for left in range(len(best) - 1):
            # 枚举反转子路径的右端点 right
            for right in range(left + 1, len(best)):
                # 构造候选路径：把 best[left:right+1] 反转后插回原位置
                candidate = best[:left] + list(reversed(best[left:right + 1])) + best[right + 1:]
                # 计算候选路径总长度
                candidate_length = length(candidate)
                # 若候选更短（加容差）则接受
                if candidate_length + 1e-7 < best_length:
                    # 更新最优路径与其长度
                    best, best_length = candidate, candidate_length
                    # 标记本轮有改进
                    improved = True
        # Or-opt：把长度 ≤3 的连续片段搬到别处（2-opt 单独做不到的邻域）
        # 枚举要搬移片段的长度 seg（1、2、3，Or-opt）
        for seg in (1, 2, 3):
            # 枚举片段的起始位置 start
            for start in range(len(best) - seg + 1):
                # 取出长度为 seg 的连续片段 piece
                piece = best[start:start + seg]
                # rest 是去掉该片段后的剩余路径
                rest = best[:start] + best[start + seg:]
                # 枚举片段插入到 rest 的各个位置 pos
                for pos in range(len(rest) + 1):
                    # 构造把 piece 插到 pos 位置后的候选路径
                    candidate = rest[:pos] + piece + rest[pos:]
                    # 计算候选路径总长度
                    candidate_length = length(candidate)
                    # 若候选更短则接受
                    if candidate_length + 1e-7 < best_length:
                        # 更新最优路径与其长度
                        best, best_length = candidate, candidate_length
                        # 标记本轮有改进
                        improved = True
                        # 接受一次改进后跳出插入位置循环，重新开始扫描
                        break
    # 返回最终优化后的访问顺序
    return best
