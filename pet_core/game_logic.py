# -*- coding: utf-8 -*-
"""
宠物核心模块 · RPG 游戏逻辑
============================================================
纯 Python 游戏逻辑函数集合，不含任何 UI / tkinter 依赖。
所有函数均为纯函数或操作 PetState 对象。
"""
import random
import time
from datetime import date

from .constants import (
    RARITY_STAT, RARITY_ORDER, RARITY_COLOR,
    GEAR_POOL, SLOT_NAME, SET_POOL, SET_BONUS,
    SHOP_COST, DIFFS, SELL_PRICE, MAX_UPGRADE, UPGRADE_COST,
    SIGNIN_BASE, BOSS_RATE, FORTUNES,
    ESSENCE_BY_RARITY, SYNTH_COST, SYNTH_RATES, RECAST_COST,
    ACHIEVEMENTS, QUESTS, QUEST_REWARD, INV_MAX,
)


# ============================================================
#  装备系统
# ============================================================

def roll_rarity(luck_bonus=0):
    """随机稀有度，带幸运加成

    基础概率：普通 50% / 优秀 30% / 精良 15% / 史诗 4% / 传说 1%
    幸运加成每点使各稀有度门槛向高稀有度偏移。

    参数:
        luck_bonus: 幸运加成（0~1 之间较合理，越大越容易出高稀有度）

    返回:
        str: 稀有度名称（普通/优秀/精良/史诗/传说）
    """
    r = random.random()
    # 基础概率阈值（累计）
    thresholds = [0.50, 0.80, 0.95, 0.99]
    # 幸运加成：压缩低稀有度区间，扩展高稀有度区间
    luck = max(0.0, min(0.5, luck_bonus))
    # 调整后的阈值（每个阈值向左移，即降低普通概率，提高高级概率）
    adjusted = [t - luck * (1 - t) for t in thresholds]
    if r < adjusted[0]:
        return "普通"
    elif r < adjusted[1]:
        return "优秀"
    elif r < adjusted[2]:
        return "精良"
    elif r < adjusted[3]:
        return "史诗"
    else:
        return "传说"


def roll_rarity_shop():
    """商店专属稀有度抽取（概率更优）

    返回:
        str: 稀有度名称
    """
    r = random.random()
    if r < 0.30:
        return "普通"
    elif r < 0.70:
        return "优秀"
    elif r < 0.90:
        return "精良"
    elif r < 0.98:
        return "史诗"
    else:
        return "传说"


def make_gear(slot=None, luck_bonus=0, shop=False):
    """生成一件随机装备

    参数:
        slot: 装备槽位（weapon/armor/trinket），为 None 时随机
        luck_bonus: 幸运加成，影响稀有度概率
        shop: 是否为商店购买（商店稀有度概率更优）

    返回:
        dict: 装备数据 {name, rarity, slot, set, upgrade}
    """
    if slot is None:
        slot = random.choice(("weapon", "armor", "trinket"))
    if shop:
        rarity = roll_rarity_shop()
    else:
        rarity = roll_rarity(luck_bonus)
    name = random.choice(GEAR_POOL[slot])
    return {
        "name": name,
        "rarity": rarity,
        "slot": slot,
        "set": random.choice(SET_POOL),
        "upgrade": 0,
    }


def set_bonus(gears_dict):
    """计算套装加成

    同主题 2 件：+3 攻防
    同主题 3 件：+6 攻防，副本金币 +20%

    参数:
        gears_dict: 装备字典 {weapon: gear|None, armor: gear|None, trinket: gear|None}

    返回:
        tuple: (atk_add, def_add, gold_mult)
    """
    sets = {}
    for slot in ("weapon", "armor", "trinket"):
        g = gears_dict.get(slot)
        if g and g.get("set"):
            sets[g["set"]] = sets.get(g["set"], 0) + 1
    n = max(sets.values()) if sets else 0
    return SET_BONUS.get(n, (0, 0, 0.0))


def atk_def(state):
    """计算总攻击力和防御力

    计算公式：
        基础 = 等级
        装备 = 各装备稀有度基础值 + 强化等级
        套装 = 套装加成
        铁壁（Lv8+）：防御 +4

    参数:
        state: PetState 状态对象

    返回:
        tuple: (attack, defense)
    """
    a = d = state.level
    for slot in ("weapon", "armor", "trinket"):
        g = getattr(state, slot, None)
        if g:
            r = RARITY_STAT[g["rarity"]]
            up = g.get("upgrade", 0)
            a += r[0] + up
            d += r[1] + up
    gears_dict = {
        "weapon": state.weapon,
        "armor": state.armor,
        "trinket": state.trinket,
    }
    sa, sd, _ = set_bonus(gears_dict)
    a += sa
    d += sd
    # 铁壁（Lv8）：防御 +4
    if state.level >= 8:
        d += 4
    return a, d


def upgrade_gear(gear):
    """强化装备（纯函数，不修改原装备）

    强化费用 = 基础费用 + 等级 × 100
    成功率 = max(0.2, 0.9 - 等级 × 0.1)
    失败时若等级 ≥ 3 则掉 1 级，否则保持不变

    参数:
        gear: 装备数据 dict

    返回:
        tuple: (new_gear, cost, success_msg)
            new_gear: 强化后的装备 dict（原装备不变）
            cost: 强化消耗的金币
            success_msg: 结果描述文本
    """
    lv = gear.get("upgrade", 0)
    cost = UPGRADE_COST + lv * 100

    if lv >= MAX_UPGRADE:
        # 已满级，无法强化
        new_gear = dict(gear)
        return new_gear, 0, "%s 已强化满 +%d！" % (gear["name"], MAX_UPGRADE)

    rate = max(0.2, 0.9 - lv * 0.1)
    new_gear = dict(gear)

    if random.random() < rate:
        new_gear["upgrade"] = lv + 1
        msg = "%s 强化成功 +%d！（花费 %d 金币）" % (gear["name"], lv + 1, cost)
        if new_gear["upgrade"] == MAX_UPGRADE:
            msg += " 满级金光闪闪！"
    else:
        if lv >= 3:
            new_gear["upgrade"] = lv - 1
            msg = "%s 强化失败…掉回 +%d（花费 %d 金币）" % (gear["name"], lv - 1, cost)
        else:
            msg = "%s 强化失败（低等级不降级，花费 %d 金币）" % (gear["name"], cost)

    return new_gear, cost, msg


def dismantle_gear(gear):
    """分解装备，获得精华

    参数:
        gear: 装备数据 dict

    返回:
        int: 获得的精华数量
    """
    if not gear:
        return 0
    return ESSENCE_BY_RARITY.get(gear.get("rarity", "普通"), 5)


def recast_gear(gear):
    """重铸装备（洗套装主题）

    随机更换套装主题，稀有度和强化等级保留。
    消耗精华数量由 RECAST_COST 常量定义。

    参数:
        gear: 装备数据 dict

    返回:
        tuple: (new_gear, cost_essence)
            new_gear: 重铸后的装备 dict
            cost_essence: 消耗的精华数量
    """
    if not gear:
        return None, 0
    new_gear = dict(gear)
    pool = [s for s in SET_POOL if s != gear.get("set")]
    new_set = random.choice(pool if pool else SET_POOL)
    new_gear["set"] = new_set
    return new_gear, RECAST_COST


def synthesize_gear(essence, rarity_target=None):
    """合成装备，消耗精华随机获得高稀有度装备

    消耗 SYNTH_COST 精华，按 SYNTH_RATES 概率获得精良/史诗/传说装备。
    若指定 rarity_target，则尝试定向合成（需更多精华，成功率更低）。

    参数:
        essence: 当前拥有的精华数量
        rarity_target: 目标稀有度（None 表示随机）

    返回:
        tuple: (gear_or_none, cost_essence, message)
            gear_or_none: 合成出的装备 dict，精华不足时为 None
            cost_essence: 消耗的精华数量
            message: 结果描述
    """
    if essence < SYNTH_COST:
        return None, 0, "精华不足（合成需 %d 精华）" % SYNTH_COST

    if rarity_target is None:
        # 随机合成
        r = random.random()
        acc = 0
        rarity = "精良"
        for name, prob in SYNTH_RATES:
            acc += prob
            if r < acc:
                rarity = name
                break
        gear = make_gear(luck_bonus=0)
        gear["rarity"] = rarity
        # 重新选择对应稀有度的装备（保持原有随机槽位和名称）
        return gear, SYNTH_COST, "合成成功！获得 %s·%s" % (gear["name"], rarity)
    else:
        # 定向合成（消耗双倍精华，成功率 50%）
        cost = SYNTH_COST * 2
        if essence < cost:
            return None, 0, "定向合成精华不足（需 %d 精华）" % cost
        if rarity_target not in RARITY_ORDER:
            return None, 0, "未知稀有度：%s" % rarity_target
        if random.random() < 0.5:
            gear = make_gear(luck_bonus=0)
            gear["rarity"] = rarity_target
            return gear, cost, "定向合成成功！获得 %s·%s" % (gear["name"], rarity_target)
        else:
            return None, cost, "定向合成失败…消耗了 %d 精华" % cost


# ============================================================
#  冒险 / 副本系统
# ============================================================

def _fortune_mult(state):
    """获取今日运势金币倍率"""
    fortune_val = state.fortune.get("val", "中")
    for name, mult in FORTUNES:
        if fortune_val == name:
            return mult
    return 1.0


def start_adventure(state, difficulty="normal"):
    """开始冒险，计算时长和奖励预览

    参数:
        state: PetState 状态对象
        difficulty: 难度（easy/normal/night）

    返回:
        tuple: (duration_seconds, reward_preview)
            duration_seconds: 冒险时长（秒）
            reward_preview: 奖励预览文本描述
    """
    if difficulty not in DIFFS:
        difficulty = "normal"
    info = DIFFS[difficulty]
    name = info[0]
    dur_range = info[1]
    base_exp = info[2]
    gold_rng = info[3]

    # 计算时长（等级技能加成）
    dur = random.randint(*dur_range)
    if state.level >= 6:
        dur = max(5, dur // 2)          # 寻宝雷达：副本时间减半
    if state.level >= 12:
        dur = max(3, int(dur * 0.7))    # 疾风（Lv12）：时间再减 30%

    # 预估奖励
    gold_min = gold_rng[0] + state.level * 2
    gold_max = gold_rng[1] + state.level * 2
    exp_est = base_exp + state.level * 2

    # 套装金币加成
    gears_dict = {
        "weapon": state.weapon,
        "armor": state.armor,
        "trinket": state.trinket,
    }
    _, _, gold_mult = set_bonus(gears_dict)
    gold_min = int(gold_min * (1.0 + gold_mult))
    gold_max = int(gold_max * (1.0 + gold_mult))

    # 运势加成
    fmult = _fortune_mult(state)
    gold_min = int(gold_min * fmult)
    gold_max = int(gold_max * fmult)

    # 聚宝（Lv10）
    if state.level >= 10:
        gold_min = int(gold_min * 1.25)
        gold_max = int(gold_max * 1.25)

    drop_rate = info[4]
    boss_rate = info[5]

    preview = "【%s】约 %d 秒 | 金币 %d~%d | 经验 +%d | 掉率 %.0f%%" % (
        name, dur, gold_min, gold_max, exp_est, drop_rate * 100)
    if difficulty == "night":
        preview += " | 首领概率 %.0f%%" % (boss_rate * 100)

    return dur, preview


def finish_adventure(state, difficulty="normal"):
    """完成冒险，结算奖励

    有概率遇到首领（噩梦难度更高）。
    首领战根据攻防计算胜负，失败则收益减半。

    参数:
        state: PetState 状态对象（会被修改：增加统计、经验、金币等）
        difficulty: 难度（easy/normal/night）

    返回:
        tuple: (gold, exp, gear_or_none, is_boss, log_messages_list)
            gold: 获得的金币
            exp: 获得的经验
            gear_or_none: 掉落的装备 dict，没有则为 None
            is_boss: 是否遇到首领
            log_messages_list: 日志消息列表（list of str）
    """
    logs = []

    if difficulty not in DIFFS:
        difficulty = "normal"
    info = DIFFS[difficulty]
    name = info[0]
    base_exp = info[2]
    gold_rng = info[3]
    drop_rate = info[4]
    boss_rate = info[5]
    boss_mult = info[6]

    # 统计计数
    state.adv_count += 1
    state.stats["adv"] = state.stats.get("adv", 0) + 1
    state.weekly["adv"] = state.weekly.get("adv", 0) + 1

    # 每日任务进度
    _quest_act(state, "adv")

    # 噩梦难度首领战
    is_boss = False
    if difficulty == "night" and random.random() < BOSS_RATE:
        is_boss = True
        state.stats["boss"] = state.stats.get("boss", 0) + 1
        state.weekly["boss"] = state.weekly.get("boss", 0) + 1

        # 计算首领战胜负（基于攻防）
        my_atk, my_def = atk_def(state)
        boss_lv = max(state.level + 2, 5)
        boss_atk = boss_lv + random.randint(3, 8)
        boss_def = boss_lv + random.randint(3, 8)
        my_power = my_atk + my_def
        boss_power = boss_atk + boss_def

        # 胜率基于双方战力比
        win_rate = my_power / (my_power + boss_power)
        boss_win = random.random() < win_rate

        if boss_win:
            # 胜利：5倍奖励
            exp = (base_exp + state.level * 2) * 5
            gold = (random.randint(25, 80) + state.level * 3) * 5
            gold = int(gold * _fortune_mult(state))

            # 保底史诗/传说
            gear = make_gear()
            gear["rarity"] = "史诗" if random.random() < 0.5 else "传说"
            slot = gear["slot"]
            gear_name = random.choice(GEAR_POOL[slot])
            gear["name"] = gear_name

            logs.append("首领出现！大战三百回合！")
            logs.append("击败首领！经验 +%d，金币 +%d" % (exp, gold))
            logs.append("战利品：%s·%s" % (gear["name"], gear["rarity"]))

            add_exp(state, exp)
            add_gold(state, gold)
            collect_gear(state, gear)

            # 检查成就
            check_achievements(state, ["boss_1", "gear_epic", "gear_legend"])

            return gold, exp, gear, True, logs
        else:
            # 失败：收益减半，受惊
            exp = (base_exp + state.level * 2) // 2
            gold = (random.randint(10, 30) + state.level) // 2
            gold = int(gold * _fortune_mult(state))

            logs.append("首领出现！不敌首领…狼狈撤退")
            logs.append("险胜逃脱！经验 +%d，金币 +%d" % (exp, gold))

            add_exp(state, exp)
            add_gold(state, gold)

            return gold, exp, None, True, logs

    # 常规冒险结算
    gold = random.randint(*gold_rng) + state.level * 2
    gold = int(gold * _fortune_mult(state))

    # 套装金币加成
    gears_dict = {
        "weapon": state.weapon,
        "armor": state.armor,
        "trinket": state.trinket,
    }
    _, _, gold_seth_mult = set_bonus(gears_dict)
    gold = int(gold * (1.0 + gold_seth_mult))

    # 聚宝（Lv10）
    if state.level >= 10:
        gold = int(gold * 1.25)

    exp = base_exp + state.level * 2

    # 好运（Lv4）：掉率翻倍
    actual_drop_rate = drop_rate
    if state.level >= 4:
        actual_drop_rate = min(0.85, drop_rate * 2)

    # 强敌遭遇
    if random.random() < boss_rate:
        gold = int(gold * boss_mult)
        exp = int(exp * boss_mult)
        logs.append("遭遇强敌！惊险获胜！")

    # 装备掉落
    gear = None
    if random.random() < actual_drop_rate:
        gear = make_gear()
        collect_gear(state, gear)
        logs.append("掉落装备：%s·%s" % (gear["name"], gear["rarity"]))

    add_exp(state, exp)
    add_gold(state, gold)

    log_msg = "冒险归来！经验 +%d，金币 +%d" % (exp, gold)
    if gear:
        log_msg += "，掉落 %s·%s" % (gear["name"], gear["rarity"])
    logs.insert(0, log_msg) if logs else logs.append(log_msg)

    # 检查成就
    check_achievements(state, ["first_adv", "adv_10", "gear_epic", "gear_legend",
                                "gold_500", "gold_2000", "lv5", "lv10"])

    return gold, exp, gear, False, logs


# ============================================================
#  商店系统
# ============================================================

def buy_gear(state):
    """购买一件随机装备，消耗 100 金币

    参数:
        state: PetState 状态对象（会被修改）

    返回:
        tuple: (success, gear_or_none, message)
            success: 是否购买成功
            gear_or_none: 买到的装备 dict，失败时为 None
            message: 结果描述
    """
    if state.gold < SHOP_COST:
        return False, None, "金币不够（%d/次），先去冒险吧！" % SHOP_COST

    state.gold -= SHOP_COST
    gear = make_gear(shop=True)
    collect_gear(state, gear)

    # 检查成就
    check_achievements(state, ["gear_epic", "gear_legend", "collect_15"])

    msg = "商店入手：%s·%s（%s套装）" % (gear["name"], gear["rarity"], gear["set"])
    return True, gear, msg


# ============================================================
#  签到系统
# ============================================================

def daily_signin(state):
    """每日签到

    连续签到有额外奖励，基础 20 金币，每多连续 1 天 +5 金币。

    参数:
        state: PetState 状态对象（会被修改）

    返回:
        tuple: (success, reward_gold, streak_days, message)
            success: 是否签到成功
            reward_gold: 获得的金币
            streak_days: 当前连续签到天数
            message: 结果描述
    """
    today = time.strftime("%Y-%m-%d")
    if state.last_signin == today:
        return False, 0, state.signin_streak, "今天已经签过啦！"

    try:
        last = date.fromisoformat(state.last_signin) if state.last_signin else None
        if last and (date.today() - last).days == 1:
            state.signin_streak += 1
        else:
            state.signin_streak = 1
    except Exception:
        state.signin_streak = 1

    state.last_signin = today
    reward = SIGNIN_BASE + (state.signin_streak - 1) * 5
    add_gold(state, reward)

    # 检查成就
    check_achievements(state, ["signin_7"])

    fortune_val = state.fortune.get("val", "中")
    msg = "签到成功！金币 +%d（连续 %d 天）今日运势：%s" % (
        reward, state.signin_streak, fortune_val)
    return True, reward, state.signin_streak, msg


# ============================================================
#  成就系统
# ============================================================

def check_achievements(state, keys=None):
    """检查并触发新成就

    参数:
        state: PetState 状态对象（会被修改）
        keys: 要检查的成就 ID 列表，为 None 时检查所有成就

    返回:
        list: 新达成的成就列表 [(achieve_id, name, reward_gold), ...]
    """
    newly_achieved = []

    if keys is None:
        keys = list(ACHIEVEMENTS.keys())

    for key in keys:
        if key in state.achieves:
            continue
        if key not in ACHIEVEMENTS:
            continue

        achieved = False

        # 按成就类型检查条件
        if key == "first_adv":
            achieved = state.adv_count >= 1
        elif key == "adv_10":
            achieved = state.adv_count >= 10
        elif key == "gold_500":
            achieved = state.total_gold >= 500
        elif key == "gold_2000":
            achieved = state.total_gold >= 2000
        elif key == "lv5":
            achieved = state.level >= 5
        elif key == "lv10":
            achieved = state.level >= 10
        elif key == "gear_epic":
            # 检查是否曾获得过史诗装备（通过图鉴收集）
            achieved = any(
                _rarity_from_collected_name(state, name) in ("史诗", "传说")
                for name in state.collected
            )
            # 也检查当前装备和背包
            if not achieved:
                for slot in ("weapon", "armor", "trinket"):
                    g = getattr(state, slot, None)
                    if g and g.get("rarity") in ("史诗", "传说"):
                        achieved = True
                        break
            if not achieved:
                for g in state.inventory:
                    if isinstance(g, dict) and g.get("rarity") in ("史诗", "传说"):
                        achieved = True
                        break
        elif key == "gear_legend":
            achieved = any(
                _rarity_from_collected_name(state, name) == "传说"
                for name in state.collected
            )
            if not achieved:
                for slot in ("weapon", "armor", "trinket"):
                    g = getattr(state, slot, None)
                    if g and g.get("rarity") == "传说":
                        achieved = True
                        break
            if not achieved:
                for g in state.inventory:
                    if isinstance(g, dict) and g.get("rarity") == "传说":
                        achieved = True
                        break
        elif key == "signin_7":
            achieved = state.signin_streak >= 7
        elif key == "boss_1":
            achieved = state.stats.get("boss", 0) >= 1
        elif key == "mood_90":
            achieved = state.mood >= 90
        elif key == "collect_15":
            achieved = len(state.collected) >= 15
        elif key == "survivor":
            achieved = state.no_feed_streak >= 7
        elif key == "fusion_5":
            achieved = state.fusion_count >= 5
        elif key == "fighter_3":
            achieved = state.best_streak >= 3
        elif key == "coop_10":
            achieved = state.coop_count >= 10
        elif key == "pokedex_6":
            # 需要外部解锁信息，此处仅做占位检查
            achieved = False
        elif key == "pokedex_8":
            achieved = False
        else:
            achieved = False

        if achieved:
            title, reward = ACHIEVEMENTS[key]
            state.achieves.add(key)
            add_gold(state, reward)
            newly_achieved.append((key, title, reward))

    return newly_achieved


def _rarity_from_collected_name(state, name):
    """根据装备名推断稀有度（辅助函数，用于成就检查）

    实际上 collected 只存名字，无法直接判断稀有度。
    这里做近似判断：名字出现在 GEAR_POOL 中即返回普通。
    更准确的做法需要在 collected 中存储稀有度信息。
    """
    # 简化处理：只通过当前装备/背包判断，此函数返回空
    return ""


# ============================================================
#  经验 / 等级
# ============================================================

def exp_needed(level):
    """升级所需经验

    参数:
        level: 当前等级

    返回:
        int: 升级到下一级所需经验
    """
    return level * 30


def add_exp(state, amount):
    """增加经验，自动处理升级

    参数:
        state: PetState 状态对象（会被修改）
        amount: 增加的经验值

    返回:
        tuple: (new_level, levels_gained)
            new_level: 升级后的等级
            levels_gained: 本次增加的等级数
    """
    if amount <= 0:
        return state.level, 0

    state.exp += amount
    state.weekly["exp"] = state.weekly.get("exp", 0) + amount

    levels_gained = 0
    while state.exp >= exp_needed(state.level):
        state.exp -= exp_needed(state.level)
        state.level += 1
        levels_gained += 1

    # 星级经验（经验也会增加星级经验的一部分）
    _add_star_exp(state, amount // 2)

    return state.level, levels_gained


def _add_star_exp(state, n):
    """增加星级经验（内部函数）"""
    from .constants import STAR_NEEDS
    if state.star_level >= 5:
        return
    state.star_exp += n
    need = STAR_NEEDS.get(state.star_level + 1)
    while need and state.star_exp >= need:
        state.star_exp -= need
        state.star_level += 1
        add_gold(state, 50 * state.star_level)
        if state.star_level >= 5:
            break
        need = STAR_NEEDS.get(state.star_level + 1)


# ============================================================
#  金币
# ============================================================

def add_gold(state, amount):
    """增加金币（含累计统计）

    参数:
        state: PetState 状态对象（会被修改）
        amount: 增加的金币数（可为负表示扣除）
    """
    state.gold += amount
    if amount > 0:
        state.total_gold += amount
        state.weekly["gold"] = state.weekly.get("gold", 0) + amount


# ============================================================
#  每日任务
# ============================================================

def _quest_act(state, key, n=1):
    """每日任务计数（内部函数，跨天自动重置）"""
    today = time.strftime("%Y-%m-%d")
    if state.quest.get("date") != today:
        state.quest = {"date": today, "adv": 0, "interact": 0, "done": []}
    state.quest[key] = state.quest.get(key, 0) + n


def quest_check(state):
    """检查每日任务完成情况，发放奖励

    参数:
        state: PetState 状态对象（会被修改）

    返回:
        list: 新完成的任务列表 [(quest_key, reward, message), ...]
    """
    # 确保日期正确
    today = time.strftime("%Y-%m-%d")
    if state.quest.get("date") != today:
        state.quest = {"date": today, "adv": 0, "interact": 0, "done": []}
        return []

    newly_done = []
    for key, title, need in QUESTS:
        if state.quest.get(key, 0) >= need and key not in state.quest.get("done", []):
            state.quest["done"].append(key)
            add_gold(state, QUEST_REWARD)
            newly_done.append((key, QUEST_REWARD, "每日任务「%s」完成！金币 +%d" % (title, QUEST_REWARD)))

    return newly_done


# ============================================================
#  装备收集 / 背包辅助
# ============================================================

def collect_gear(state, gear):
    """记录装备到图鉴收集

    参数:
        state: PetState 状态对象
        gear: 装备数据 dict
    """
    if not gear:
        return
    key = "%s_%s" % (gear.get("slot", ""), gear.get("name", ""))
    state.collected.add(key)


def equip_gear(state, gear):
    """装备到对应槽位，旧装备回背包

    参数:
        state: PetState 状态对象
        gear: 要装备的 dict

    返回:
        tuple: (success, message)
    """
    if not gear:
        return False, "装备无效"
    slot = gear.get("slot")
    if slot not in ("weapon", "armor", "trinket"):
        return False, "未知装备槽位：%s" % slot

    old_gear = getattr(state, slot)
    setattr(state, slot, gear)

    # 旧装备进背包
    if old_gear:
        if len(state.inventory) < INV_MAX:
            state.inventory.append(old_gear)
            msg = "已装备 %s·%s，旧装备入背包" % (gear["name"], gear["rarity"])
        else:
            # 背包满则折现
            add_gold(state, SELL_PRICE[old_gear["rarity"]])
            msg = "已装备 %s·%s，旧装备折现 +%d 金币" % (
                gear["name"], gear["rarity"], SELL_PRICE[old_gear["rarity"]])
    else:
        msg = "已装备 %s·%s" % (gear["name"], gear["rarity"])

    return True, msg


def unequip_gear(state, slot):
    """卸下装备到背包

    参数:
        state: PetState 状态对象
        slot: 装备槽位

    返回:
        tuple: (success, gear_or_none, message)
    """
    gear = getattr(state, slot, None)
    if not gear:
        return False, None, "该槽位没有装备"

    if len(state.inventory) < INV_MAX:
        state.inventory.append(gear)
        setattr(state, slot, None)
        return True, gear, "已卸下 %s·%s，放入背包" % (gear["name"], gear["rarity"])
    else:
        # 背包满则折现
        add_gold(state, SELL_PRICE[gear["rarity"]])
        setattr(state, slot, None)
        return True, None, "背包已满，%s·%s 折现 +%d 金币" % (
            gear["name"], gear["rarity"], SELL_PRICE[gear["rarity"]])


def sell_inventory_gear(state, index):
    """出售背包中的装备

    参数:
        state: PetState 状态对象
        index: 背包索引

    返回:
        tuple: (success, gold, message)
    """
    if index < 0 or index >= len(state.inventory):
        return False, 0, "索引越界"

    gear = state.inventory.pop(index)
    gold = SELL_PRICE.get(gear.get("rarity", "普通"), 20)
    add_gold(state, gold)
    return True, gold, "出售 %s·%s，获得 %d 金币" % (gear["name"], gear["rarity"], gold)


# ============================================================
#  互动计数（用于每日任务）
# ============================================================

def log_interaction(state, kind):
    """记录一次互动（feed/pet/play/click）

    参数:
        state: PetState 状态对象
        kind: 互动类型
    """
    state.stats[kind] = state.stats.get(kind, 0) + 1
    state.weekly["interact"] = state.weekly.get("interact", 0) + 1
    _quest_act(state, "interact")

    # 重置不喂食天数（如果是喂食）
    if kind == "feed":
        state.no_feed_streak = 0
