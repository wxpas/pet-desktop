# -*- coding: utf-8 -*-
"""
宠物核心模块 · 状态管理
============================================================
纯 Python 状态管理类，负责宠物游戏数据的加载、保存与默认值初始化。
不含任何 tkinter / UI 依赖。
"""
import os
import json

from .constants import STATE_PATH
from .utils import state_file_path


class PetState:
    """宠物游戏状态管理类

    封装所有游戏数据字段，提供加载 / 保存 / 重置等方法。
    所有字段均为纯 Python 类型，可直接序列化为 JSON。

    属性说明:
        hunger: 饱食度 (0-100)
        affinity: 好感度 (0-100)
        level: 等级
        exp: 当前经验
        gold: 金币
        weapon / armor / trinket: 装备 dict 或 None
        adv_count: 累计冒险次数
        total_gold: 累计获得金币
        achieves: 已达成成就 ID 集合
        last_signin: 上次签到日期字符串
        signin_streak: 连续签到天数
        quest: 每日任务进度 dict
        mood: 心情值 (0-100)
        stats: 统计数据 dict
        uptime_ms: 累计在线毫秒
        nickname: 宠物昵称
        alpha: 透明度 (0-1)
        collected: 已收集装备名称集合
        fortune: 今日运势 dict
        essence: 精华数量
        badge: 佩戴的勋章 ID
        inventory: 背包物品列表
        weekly: 周报数据 dict
        no_feed_streak: 连续未喂食天数
        no_feed_egg: 野外求生成就彩蛋标记
        fusion_count: 合体技发动次数
        midnight_day: 午夜特典日期标记
        win_streak: 互搏连胜场数
        best_streak: 历史最高连胜
        coop_count: 联手讨伐次数
        star_level: 宠物星级 (1-5)
        star_exp: 星级经验
    """

    # —— 字段名列表（用于批量操作）——
    FIELDS = (
        "hunger", "affinity", "level", "exp", "gold",
        "weapon", "armor", "trinket",
        "adv_count", "total_gold", "achieves",
        "last_signin", "signin_streak", "quest",
        "mood", "stats", "uptime_ms",
        "nickname", "alpha", "collected",
        "fortune", "essence", "badge", "inventory", "weekly",
        "no_feed_streak", "no_feed_egg",
        "fusion_count", "midnight_day",
        "win_streak", "best_streak",
        "coop_count", "star_level", "star_exp",
    )

    def __init__(self):
        """初始化所有字段为默认值"""
        # 基础属性
        self.hunger = 80
        self.affinity = 0
        self.level = 1
        self.exp = 0
        self.gold = 0

        # 装备槽（None 表示未装备）
        self.weapon = None
        self.armor = None
        self.trinket = None

        # 统计
        self.adv_count = 0
        self.total_gold = 0
        self.achieves = set()

        # 签到
        self.last_signin = ""
        self.signin_streak = 0

        # 每日任务
        self.quest = {"date": "", "adv": 0, "interact": 0, "done": []}

        # 心情 / 统计
        self.mood = 70
        self.stats = {"feed": 0, "pet": 0, "play": 0, "click": 0,
                      "adv": 0, "boss": 0, "faint": 0}
        self.uptime_ms = 0

        # 个性化
        self.nickname = ""
        self.alpha = 1.0

        # 收集
        self.collected = set()

        # 运势
        self.fortune = {"date": "", "val": "中"}

        # 精华 / 勋章 / 背包
        self.essence = 0
        self.badge = ""
        self.inventory = []

        # 周报
        self.weekly = {"week": "", "gold": 0, "exp": 0,
                       "adv": 0, "boss": 0, "feed": 0, "interact": 0}

        # 野外求生（不喂食成就）
        self.no_feed_streak = 0
        self.no_feed_egg = False

        # 合体技
        self.fusion_count = 0
        self.midnight_day = ""

        # 互搏
        self.win_streak = 0
        self.best_streak = 0

        # 联手讨伐
        self.coop_count = 0

        # 星级
        self.star_level = 1
        self.star_exp = 0

    # ------------------------------------------------------------ 加载 / 保存

    @classmethod
    def load(cls, pet_id, state_path=None):
        """从 JSON 文件加载宠物状态

        读取 state_path 文件中 pet_id 对应的状态数据，
        文件不存在或读取失败时返回默认状态。

        参数:
            pet_id: 宠物 ID
            state_path: 状态文件路径，为 None 时使用默认可写路径

        返回:
            PetState: 加载后的状态对象
        """
        if state_path is None:
            state_path = state_file_path()

        state = cls()
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            s = d.get(pet_id, {})
        except Exception:
            s = {}

        state.hunger = int(s.get("hunger", 80))
        state.affinity = int(s.get("affinity", 0))
        state.level = int(s.get("level", 1))
        state.exp = int(s.get("exp", 0))
        state.gold = int(s.get("gold", 0))
        state.weapon = s.get("weapon")
        state.armor = s.get("armor")
        state.trinket = s.get("trinket")
        state.adv_count = int(s.get("adv_count", 0))
        state.total_gold = int(s.get("total_gold", 0))
        state.achieves = set(s.get("achieves", []))
        state.last_signin = s.get("last_signin", "")
        state.signin_streak = int(s.get("signin_streak", 0))
        state.quest = s.get("quest") or {"date": "", "adv": 0, "interact": 0, "done": []}
        state.mood = s.get("mood", 70)
        state.stats = s.get("stats") or {"feed": 0, "pet": 0, "play": 0, "click": 0,
                                          "adv": 0, "boss": 0, "faint": 0}
        state.uptime_ms = int(s.get("uptime_ms", 0))
        state.nickname = s.get("nickname", "")
        state.alpha = float(s.get("alpha", 1.0))
        state.collected = set(s.get("collected", []))
        state.fortune = s.get("fortune") or {"date": "", "val": "中"}
        state.essence = int(s.get("essence", 0))
        state.badge = s.get("badge", "")
        state.inventory = s.get("inventory") or []
        state.weekly = s.get("weekly") or {"week": "", "gold": 0, "exp": 0,
                                            "adv": 0, "boss": 0, "feed": 0, "interact": 0}
        state.no_feed_streak = int(s.get("no_feed_streak", 0))
        state.no_feed_egg = bool(s.get("no_feed_egg", False))
        state.fusion_count = int(s.get("fusion_count", 0))
        state.midnight_day = str(s.get("midnight_day", ""))
        state.win_streak = int(s.get("win_streak", 0))
        state.best_streak = int(s.get("best_streak", 0))
        state.coop_count = int(s.get("coop_count", 0))
        state.star_level = int(s.get("star_level", 1))
        state.star_exp = int(s.get("star_exp", 0))

        return state

    def save(self, pet_id, state_path=None):
        """保存宠物状态到 JSON 文件

        将当前状态写入 state_path 文件中 pet_id 对应的键下，
        保留文件中其他宠物的状态数据。

        参数:
            pet_id: 宠物 ID
            state_path: 状态文件路径，为 None 时使用默认可写路径
        """
        if state_path is None:
            state_path = state_file_path()

        try:
            d = {}
            if os.path.exists(state_path):
                with open(state_path, "r", encoding="utf-8") as f:
                    d = json.load(f)

            d[pet_id] = self.to_dict()

            os.makedirs(os.path.dirname(state_path), exist_ok=True)
            with open(state_path, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------ 序列化

    def to_dict(self):
        """导出为可 JSON 序列化的字典

        返回:
            dict: 所有状态字段的字典表示
        """
        return {
            "hunger": self.hunger,
            "affinity": self.affinity,
            "level": self.level,
            "exp": self.exp,
            "gold": self.gold,
            "weapon": self.weapon,
            "armor": self.armor,
            "trinket": self.trinket,
            "adv_count": self.adv_count,
            "total_gold": self.total_gold,
            "achieves": sorted(self.achieves),
            "last_signin": self.last_signin,
            "signin_streak": self.signin_streak,
            "quest": self.quest,
            "mood": self.mood,
            "stats": self.stats,
            "uptime_ms": self.uptime_ms,
            "nickname": self.nickname,
            "alpha": self.alpha,
            "collected": sorted(self.collected),
            "fortune": self.fortune,
            "essence": self.essence,
            "badge": self.badge,
            "inventory": self.inventory,
            "weekly": self.weekly,
            "no_feed_streak": self.no_feed_streak,
            "no_feed_egg": self.no_feed_egg,
            "fusion_count": self.fusion_count,
            "midnight_day": self.midnight_day,
            "win_streak": self.win_streak,
            "best_streak": self.best_streak,
            "coop_count": self.coop_count,
            "star_level": self.star_level,
            "star_exp": self.star_exp,
        }

    def from_dict(self, data):
        """从字典加载状态

        参数:
            data: 状态数据字典
        """
        if not isinstance(data, dict):
            return

        self.hunger = int(data.get("hunger", self.hunger))
        self.affinity = int(data.get("affinity", self.affinity))
        self.level = int(data.get("level", self.level))
        self.exp = int(data.get("exp", self.exp))
        self.gold = int(data.get("gold", self.gold))
        self.weapon = data.get("weapon", self.weapon)
        self.armor = data.get("armor", self.armor)
        self.trinket = data.get("trinket", self.trinket)
        self.adv_count = int(data.get("adv_count", self.adv_count))
        self.total_gold = int(data.get("total_gold", self.total_gold))
        if "achieves" in data:
            self.achieves = set(data["achieves"])
        self.last_signin = data.get("last_signin", self.last_signin)
        self.signin_streak = int(data.get("signin_streak", self.signin_streak))
        if "quest" in data and data["quest"]:
            self.quest = data["quest"]
        self.mood = data.get("mood", self.mood)
        if "stats" in data and data["stats"]:
            self.stats = data["stats"]
        self.uptime_ms = int(data.get("uptime_ms", self.uptime_ms))
        self.nickname = data.get("nickname", self.nickname)
        self.alpha = float(data.get("alpha", self.alpha))
        if "collected" in data:
            self.collected = set(data["collected"])
        if "fortune" in data and data["fortune"]:
            self.fortune = data["fortune"]
        self.essence = int(data.get("essence", self.essence))
        self.badge = data.get("badge", self.badge)
        if "inventory" in data and data["inventory"] is not None:
            self.inventory = data["inventory"]
        if "weekly" in data and data["weekly"]:
            self.weekly = data["weekly"]
        self.no_feed_streak = int(data.get("no_feed_streak", self.no_feed_streak))
        self.no_feed_egg = bool(data.get("no_feed_egg", self.no_feed_egg))
        self.fusion_count = int(data.get("fusion_count", self.fusion_count))
        self.midnight_day = str(data.get("midnight_day", self.midnight_day))
        self.win_streak = int(data.get("win_streak", self.win_streak))
        self.best_streak = int(data.get("best_streak", self.best_streak))
        self.coop_count = int(data.get("coop_count", self.coop_count))
        self.star_level = int(data.get("star_level", self.star_level))
        self.star_exp = int(data.get("star_exp", self.star_exp))

    # ------------------------------------------------------------ 便捷方法

    def reset(self):
        """重置为默认状态"""
        self.__init__()

    def get_gear(self, slot):
        """获取指定槽位的装备

        参数:
            slot: 槽位名（weapon / armor / trinket）

        返回:
            dict or None: 装备数据
        """
        return getattr(self, slot, None)

    def set_gear(self, slot, gear):
        """设置指定槽位的装备

        参数:
            slot: 槽位名（weapon / armor / trinket）
            gear: 装备数据 dict，或 None 表示卸下
        """
        if hasattr(self, slot):
            setattr(self, slot, gear)
