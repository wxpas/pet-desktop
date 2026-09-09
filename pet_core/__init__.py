# -*- coding: utf-8 -*-
"""
宠物核心模块 pet_core
============================================================
纯 Python 核心逻辑模块，不含任何 UI / tkinter 依赖。

模块结构:
    constants    — 游戏常量定义
    utils        — 工具函数集合
    pet_state    — PetState 状态管理类
    game_logic   — RPG 游戏逻辑函数（装备/冒险/商店/签到/成就等）
"""

# —— 状态管理 ——
from .pet_state import PetState

# —— 装备系统 ——
from .game_logic import (
    roll_rarity,
    make_gear,
    set_bonus,
    atk_def,
    upgrade_gear,
    dismantle_gear,
    recast_gear,
    synthesize_gear,
)

# —— 冒险 / 副本系统 ——
from .game_logic import (
    start_adventure,
    finish_adventure,
)

# —— 商店系统 ——
from .game_logic import buy_gear

# —— 签到系统 ——
from .game_logic import daily_signin

# —— 成就系统 ——
from .game_logic import check_achievements

# —— 经验 / 等级 ——
from .game_logic import exp_needed, add_exp

# —— 金币 ——
from .game_logic import add_gold

# —— 每日任务 ——
from .game_logic import quest_check

# —— 装备收集 / 背包辅助 ——
from .game_logic import (
    collect_gear,
    equip_gear,
    unequip_gear,
    sell_inventory_gear,
)

# —— 互动记录 ——
from .game_logic import log_interaction

# —— 常量 ——
from . import constants

# —— 工具函数 ——
from . import utils

__all__ = [
    # 状态
    "PetState",
    # 装备
    "roll_rarity", "make_gear", "set_bonus", "atk_def",
    "upgrade_gear", "dismantle_gear", "recast_gear", "synthesize_gear",
    # 冒险
    "start_adventure", "finish_adventure",
    # 商店
    "buy_gear",
    # 签到
    "daily_signin",
    # 成就
    "check_achievements",
    # 经验 / 等级
    "exp_needed", "add_exp",
    # 金币
    "add_gold",
    # 每日任务
    "quest_check",
    # 装备 / 背包
    "collect_gear", "equip_gear", "unequip_gear", "sell_inventory_gear",
    # 互动
    "log_interaction",
    # 子模块
    "constants", "utils",
]
