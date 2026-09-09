# -*- coding: utf-8 -*-
"""
桌面电子宠物 · 蟑螂小强
============================================================
一只沿着屏幕边缘爬行的透明置顶小宠物，不干扰正常操作。

功能：
  1. 沿屏幕边缘自由移动，到达任意一侧端点时自动切换到相邻边缘继续移动
  2. 环绕效果：到角时随机选择「转弯到相邻边」或「从相对侧重新出现」
  3. 随机自主行为：随机变向 / 随机停顿 / 随机变速 / 偶尔飞走
  4. 左键点击交互：受惊加速逃窜 / 短暂停顿 / 反向逃跑（带气泡吐槽）
  5. 窗口始终置顶、无边框、透明，除蟑螂本体外点击全部穿透，不挡操作

操作：
  左键单击   —— 惊吓反应（随机触发加速 / 停顿 / 变向）
  右键单击   —— 菜单：暂停/继续、随机瞬移、退出
  运行方式   —— 双击「启动电子宠物.bat」，或执行：python cockroach_pet.py

依赖：
  Python 3.8+（仅标准库 tkinter；精灵帧由 make_sprites.py 预先生成）
"""
import os
import sys
import json
import math
import time
import random
import ctypes
import tkinter as tk
from datetime import date

try:
    from PIL import Image as PILImage, ImageTk
    _HAS_PIL = True
except Exception:
    _HAS_PIL = False

KEY = "#FF00FF"            # 透明键色（品红）
TICK_MS = 40               # 主循环间隔（毫秒），约 25 FPS
BUBBLE_MARGIN = 44         # 窗口顶部预留的透明气泡区高度（像素）
BUBBLES = ["呀！", "哇！", "救命！", "别点我！", "溜了溜了！", "吓死我了！", "哒哒哒哒！"]
ACHIEVE_GOLD = 8           # 达成 8 项成就解锁「荣耀金」皮肤


def tint_golden(img):
    """把 RGBA 图像染成荣耀金（保留白色高光与透明区）"""
    img = img.convert("RGBA")
    try:
        import numpy as np
        a = np.asarray(img).copy()
        alpha = a[:, :, 3]
        mask = alpha > 0
        white = (a[:, :, 0] > 245) & (a[:, :, 1] > 245) & (a[:, :, 2] > 245)
        t = mask & ~white
        a[t, 0] = (a[t, 0] * 0.82 + 250 * 0.18).astype(np.uint8)
        a[t, 1] = (a[t, 1] * 0.66 + 200 * 0.34).astype(np.uint8)
        a[t, 2] = (a[t, 2] * 0.40 + 40 * 0.60).astype(np.uint8)
        return PILImage.fromarray(a)
    except Exception:
        px = img.load()
        w, h = img.size
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a == 0 or (r > 245 and g > 245 and b > 245):
                    continue
                px[x, y] = (int(r * 0.82 + 250 * 0.18),
                            int(g * 0.66 + 200 * 0.34),
                            int(b * 0.40 + 40 * 0.60), a)
        return img


def _draw_heart(c, x, y, s, color):
    """在 canvas 上画一颗小心心"""
    c.create_oval(x - s, y - s * 0.6, x - s * 0.35, y + s * 0.5,
                  fill=color, outline="")
    c.create_oval(x + s * 0.35, y - s * 0.6, x + s, y + s * 0.5,
                  fill=color, outline="")
    c.create_polygon(x - s * 0.55, y, x + s * 0.55, y, x, y + s * 1.15,
                     fill=color, outline="")


def _star_points(cx, cy, R, r):
    """五角星顶点（用于饰品图标）"""
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = R if i % 2 == 0 else r
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    return pts

# 各宠物台词池（click 惊吓 / feed 进食 / pet 摸摸 / play 逗玩 / hungry 饥饿 / dizzy 眩晕 / greet 高好感 / sad 低落）
PET_LINES = {
    "cockroach": {
        "click": ["呀！", "别踩我！", "溜了溜了！", "吓死本强了！", "哒哒哒哒！", "我跑得可快了！"],
        "feed": ["咔嚓咔嚓～", "好吃！真香！", "饿死我了！", "再来一块！"],
        "pet": ["呼噜呼噜～", "嘿嘿，痒痒的", "够意思！", "最喜欢你了！"],
        "play": ["转圈圈！", "嘿咻嘿咻！", "看我凌波微步！"],
        "hungry": ["咕噜咕噜…", "好饿呀…", "找吃的去咯", "谁有面包屑？"],
        "dizzy": ["晕了晕了…", "星星在转…", "别戳了别戳了…"],
        "greet": ["你来啦！", "今天我心情超好！"],
        "sad": ["唉…", "有点无聊…", "想静静…"],
    },
    "cat": {
        "click": ["喵呜！", "吓我一跳！", "喵喵喵！", "朕还没准备好！", "别闹！"],
        "feed": ["喵～好吃！", "有鱼吗有鱼吗？", "满意地呼噜呼噜"],
        "pet": ["呼噜呼噜～", "喵呜～好舒服", "再摸一下嘛"],
        "play": ["喵！追尾巴！", "看我扑腾！"],
        "hungry": ["喵…饿了", "咕噜咕噜…", "罐头呢？"],
        "dizzy": ["喵…晕了", "转得找不着北…"],
        "greet": ["喵～你回来啦！", "朕今天准许你摸我"],
        "sad": ["喵…", "朕emo了…", "不想动…"],
    },
    "dog": {
        "click": ["汪！", "汪汪！", "吓我一跳！", "汪呜～", "尾巴都吓直了！"],
        "feed": ["汪汪！好吃！", "咔嚓咔嚓～", "再来一块嘛！"],
        "pet": ["汪～好舒服！", "尾巴摇成风扇！", "摸摸头最开心！"],
        "play": ["汪！转圈圈！", "看我蹦得多高！"],
        "hungry": ["汪…肚子叫了", "好饿呀…", "骨头呢？"],
        "dizzy": ["汪汪…晕了", "转圈转晕了…"],
        "greet": ["汪！你终于来啦！", "今天一起玩吗？"],
        "sad": ["呜…", "汪呜…", "有点低落…"],
    },
    "rabbit": {
        "click": ["呀！", "蹦蹦跳！", "吓到我的耳朵了！", "呜哇！", "胡萝卜吓掉了！"],
        "feed": ["咔嚓咔嚓～", "胡萝卜！最喜欢了！", "好吃到耳朵竖起来！"],
        "pet": ["呼噜～好舒服", "耳朵痒痒的～", "最喜欢摸摸头！"],
        "play": ["蹦蹦跳跳！", "看我跳得高不高！"],
        "hungry": ["咕噜…饿了", "胡萝卜呢？", "好想吃草…"],
        "dizzy": ["晕晕的…", "星星在转…"],
        "greet": ["你来啦！", "今天也要开心哦！"],
        "sad": ["耳朵垂下来了…", "好安静呀…", "有点想哭…"],
    },
}
LINES_FALLBACK = {
    "click": ["呀！", "吓我一跳！", "别点我！"],
    "feed": ["好吃！", "咔嚓咔嚓～"],
    "pet": ["呼噜呼噜～", "好舒服！"],
    "play": ["转圈圈！", "嘿咻嘿咻！"],
    "hungry": ["咕噜咕噜…", "好饿呀…"],
    "dizzy": ["晕了晕了…"],
    "greet": ["你来啦！"],
    "sad": ["唉…", "有点低落…"],
}
AFFINITY_LEVELS = ((90, "挚友"), (60, "亲密"), (25, "熟悉"), (0, "陌生"))
STATE_PATH = "pet_state.json"

# —— RPG 玩法：稀有度 / 装备 / 属性 ——
RARITY_STAT = {"普通": (1, 1), "优秀": (2, 2), "精良": (4, 3),
               "史诗": (7, 5), "传说": (12, 8)}
RARITY_ORDER = ("普通", "优秀", "精良", "史诗", "传说")
GEAR_POOL = {
    "weapon": ["胡萝卜大棒", "毛线球锤", "小鱼干剑", "骨头棒", "树枝棍",
               "闪闪发光的板砖", "卷心菜锤", "咬咬玩具刃"],
    "armor": ["树叶披风", "毛线围巾", "蛋壳盔甲", "纸箱护盾",
              "棉花肚兜", "树皮背心"],
    "trinket": ["幸运四叶草", "小铃铛", "玻璃珠", "蒲公英种子",
                "勇气徽章", "亮晶晶扣子"],
}
SHOP_COST = 100          # 商店抽装备价格（金币）
ADV_DUR = (8, 15)        # 副本时长范围（秒）
SKILL_CD = 90000         # 疾跑冷却（毫秒）
SKILL_RUN = 30000        # 疾跑持续（毫秒）

# 副本难度：名称 / 时长范围 / 基础经验 / 金币区间 / 掉率 / 强敌率 / 强敌奖励倍数
DIFFS = {
    "easy":   ("简单", (6, 10), 15, (8, 30), 0.25, 0.15, 1.0),
    "normal": ("普通", (8, 15), 20, (10, 40), 0.30, 0.25, 1.0),
    "night":  ("噩梦", (12, 20), 30, (20, 60), 0.40, 0.40, 3.0),
}
SELL_PRICE = {"普通": 20, "优秀": 40, "精良": 80, "史诗": 150, "传说": 300}
RARITY_COLOR = {"普通": "#B0B0B0", "优秀": "#6BCB77", "精良": "#4D96FF",
                "史诗": "#B388FF", "传说": "#FFC53D"}
MAX_UPGRADE = 9          # 装备强化上限
UPGRADE_COST = 100       # 强化基础费用（+等级×100）
SIGNIN_BASE = 20         # 每日签到基础金币
# 等级称号（取 ≤ 当前等级的最高档）
TITLES = ((20, "传说之兽"), (15, "英雄"), (10, "冒险家"), (5, "小机灵"), (0, "新手"))
MOOD_DECAY_MS = 60000    # 心情衰减周期（毫秒）
BOSS_RATE = 0.12         # 噩梦难度首领出现率
BOSS_ACHIEVE = ("boss_1", "首次击败首领", 300)
FAVORITE_FOOD = {"cockroach": "面包屑", "cat": "小鱼干", "dog": "大骨头", "rabbit": "胡萝卜"}
WEATHERS = ("晴", "多云", "雨", "雪")
WEATHER_TICK_MS = 600000  # 天气变化检查周期（10 分钟）
ULT_CD = 300000           # 必杀技冷却（毫秒，5 分钟）
ULT_DUR = 5000            # 必杀技持续（毫秒）
FORTUNES = (("大吉", 1.30), ("吉", 1.15), ("中", 1.00), ("凶", 0.90))
ESSENCE_BY_RARITY = {"普通": 5, "优秀": 10, "精良": 20, "史诗": 40, "传说": 80}
SYNTH_COST = 50          # 合成装备消耗精华
SYNTH_RATES = (("精良", 0.60), ("史诗", 0.30), ("传说", 0.10))
FIRE_COLORS = ("#FF6B6B", "#FFC53D", "#6BCB77", "#4D96FF", "#B388FF")
# 奇遇事件池：(文本, 效果)
ENCOUNTERS = (
    ("捡到一枚金币！", "gold"),
    ("心情突然超好！", "mood"),
    ("遇见旅行的同伴，学到了经验！", "exp"),
    ("神秘商人送了一件装备！", "gear"),
    ("打了个盹，有点迷糊…", "tired"),
)
INV_MAX = 12             # 背包上限
ARENA_CD = 60000         # 竞技场冷却（毫秒）
SLOT_NAME = {"weapon": "武器", "armor": "防具", "trinket": "饰品"}
SET_POOL = ["胡萝卜", "毛线", "树叶", "蛋壳", "纸箱", "小鱼干", "骨头", "星光"]
# 套装加成：件数 → (攻击, 防御, 副本金币加成)
SET_BONUS = {2: (3, 3, 0.0), 3: (6, 6, 0.20)}
QUESTS = (("adv", "冒险完成 2 次", 2), ("interact", "互动 10 次", 10))
QUEST_REWARD = 50        # 每日任务单条奖励
ACHIEVEMENTS = {
    "first_adv":  ("首次冒险", 30),
    "adv_10":     ("冒险达人（累计10次）", 100),
    "gold_500":   ("第一桶金（累计赚500）", 200),
    "gold_2000":  ("小富翁（累计赚2000）", 400),
    "lv5":        ("小有成就（达到5级）", 150),
    "lv10":       ("宠物大师（达到10级）", 300),
    "gear_epic":  ("史诗收藏家（获得史诗装备）", 100),
    "gear_legend":("传说收藏家（获得传说装备）", 300),
    "signin_7":   ("签到狂魔（连续签到7天）", 150),
    "boss_1":     ("屠龙者（首次击败首领）", 300),
    "mood_90":    ("阳光宠物（心情达到90）", 120),
    "collect_15": ("装备鉴赏家（收集15件装备）", 200),
    "survivor":   ("野外求生（连续7天不喂食）", 200),
    "fusion_5":   ("双子星（合体技发动5次）", 300),
    "fighter_3":  ("格斗大师（互搏连胜3场）", 300),
    "coop_10":    ("并肩作战（联手讨伐10次）", 300),
    "pokedex_6":  ("宠物收藏家（解锁6种宠物）", 300),
    "pokedex_8":  ("宠物大师（解锁全部8种宠物）", 500),
}
RECAST_COST = 30         # 重铸装备（洗主题）消耗精华
FUSION_CD = 300000       # 合体技冷却（毫秒，5 分钟）
FUSION_DUR = 3600        # 合体技持续（毫秒）
AUTO_BATTLE_DIST = 90    # 双宠随机游走碰撞自动打架的判定距离（中心距）
STAR_NEEDS = {2: 50, 3: 150, 4: 400, 5: 800}   # 宠物星级升级所需累计经验
DICE_COST = 10           # 猜点数参与费
DICE_WIN = 25            # 猜中奖励
SPECIAL_CD = 120000      # 专属技能冷却（秒级）
SPECIAL_REWARD = {       # 专属技能基础奖励（金币, 经验）；随星级升级 ×(1+0.2×(星级-1))
    "roll":  (40, 20),
    "spin":  (30, 15),
    "boost": (20, 10),
}


FRAMES = {
    "walk": ["walk_1", "walk_2", "walk_3", "walk_4"],
    "idle": ["idle_1", "idle_2"],
    "scared": ["scared_1", "scared_2"],
}

_single_mutex = None
_PET_INSTANCES = []      # 当前进程内所有宠物实例（双宠互搏用）


def ensure_single_instance():
    """单实例保护：用 Windows 命名互斥体（进程退出即自动释放，无 PID 复用问题）。
    已有实例在运行时，本实例直接退出。"""
    global _single_mutex
    ERROR_ALREADY_EXISTS = 183
    try:
        h = ctypes.windll.kernel32.CreateMutexW(None, False, "CockroachPet_SingleInstance")
        if not h:
            return  # 创建失败时不阻塞启动
        if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            print("已有宠物实例在运行，本实例退出。", file=sys.stderr)
            sys.exit(0)
        _single_mutex = h  # 保持句柄存活，进程存活期间互斥体有效
    except Exception:
        pass


def script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def load_pet_config():
    """读取当前选中的宠物与皮肤（pet_config.json），不存在时回退到小强·经典棕"""
    pet, skin = "cockroach", "default"
    try:
        with open(os.path.join(script_dir(), "pet_config.json"), "r", encoding="utf-8") as f:
            cfg = json.load(f)
        pet = str(cfg.get("pet", pet))
        skin = str(cfg.get("skin", skin))
    except Exception:
        pass
    return pet, skin


def pet_display_name(pet):
    """宠物中文名（pet_library.json），查不到时用 id"""
    try:
        with open(os.path.join(script_dir(), "pet_library.json"), "r", encoding="utf-8") as f:
            lib = json.load(f)
        info = lib.get("pets", {}).get(pet, {})
        return info.get("name", pet)
    except Exception:
        return pet


def load_pet_library():
    """宠物库 {id: {name, sheet, unlock, skins}}"""
    try:
        with open(os.path.join(script_dir(), "pet_library.json"), "r",
                  encoding="utf-8") as f:
            return json.load(f).get("pets", {})
    except Exception:
        return {}


def get_unlocked_pets():
    """已解锁宠物集合：unlock==0 的初始拥有 + pet_state.json 顶层 _unlocked"""
    unlocked = {"cockroach"}
    try:
        for pid, info in load_pet_library().items():
            if int(info.get("unlock", 0)) == 0:
                unlocked.add(pid)
        with open(os.path.join(script_dir(), STATE_PATH), "r",
                  encoding="utf-8") as f:
            d = json.load(f)
        unlocked |= set(d.get("_unlocked", []))
    except Exception:
        pass
    return unlocked


def resolve_pet(pet):
    """配置的宠物未解锁时，回退到第一个已解锁宠物（防配置被绕过）"""
    if pet in get_unlocked_pets():
        return pet
    for pid in load_pet_library():
        if pid in get_unlocked_pets():
            return pid
    return "cockroach"


def enable_dpi_awareness():
    """让窗口坐标按物理像素计算，避免高分屏上显示偏差"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class Rect:
    __slots__ = ("x0", "y0", "x1", "y1")

    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1


def get_virtual_rect():
    """整个虚拟桌面（跨所有显示器）的范围"""
    u = ctypes.windll.user32
    x0 = u.GetSystemMetrics(76)          # SM_XVIRTUALSCREEN
    y0 = u.GetSystemMetrics(77)          # SM_YVIRTUALSCREEN
    return Rect(x0, y0,
                x0 + u.GetSystemMetrics(78),   # SM_CXVIRTUALSCREEN
                y0 + u.GetSystemMetrics(79))   # SM_CYVIRTUALSCREEN


def get_work_area(x, y):
    """获取点 (x, y) 所在显示器的工作区（自动避开任务栏）；失败回退到整个虚拟屏"""
    try:
        import ctypes.wintypes

        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_long), ("rcMonitor", RECT),
                        ("rcWork", RECT), ("dwFlags", ctypes.c_long)]

        u = ctypes.windll.user32
        hmon = u.MonitorFromPoint(ctypes.wintypes.POINT(int(x), int(y)), 2)
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if u.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            return Rect(mi.rcWork.left, mi.rcWork.top, mi.rcWork.right, mi.rcWork.bottom)
    except Exception:
        pass
    return get_virtual_rect()


class CockroachPet:
    EDGES = ("top", "right", "bottom", "left")
    _hk_installed = False      # F8 全局热键只装一次
    _hk_proc = None            # 保持钩子回调引用防 GC

    def __init__(self, root, pet_id=None, skin=None):
        self.root = root
        if pet_id is None:
            self.pet_id, self.pet_skin = load_pet_config()
        else:
            self.pet_id, self.pet_skin = pet_id, skin or "default"
        self.pet_name = pet_display_name(self.pet_id)
        self.frames = self.load_frames()
        self.fw, self.fh = self.display_size
        self.vrect = get_virtual_rect()

        self.edge = "top"          # 当前贴着哪条边
        self.dir = 1               # +1 顺时针绕屏幕，-1 逆时针
        self.wrapping = False      # 穿墙环绕中（允许出屏，从相对边回来）
        self.facing = 0            # 0=朝右(原图) 1=朝左(镜像)
        self.state = "walk"        # walk / idle / scared / spin / dizzy / chase
        self.state_left = 0        # 状态剩余时间（毫秒）
        self.fly_target = None     # 飞走目标点
        self.paused = False
        self.tick_count = 0
        self.anim_idx = 0
        self.anim_timer = 0
        self._current_img = None
        self._bubble_job = None
        # —— 互动与玩法状态 ——
        self.dragging = False      # 拖拽中
        self._drag_off = (0, 0)
        self.chase_left = 0        # 跟随鼠标剩余毫秒
        self.hunger, self.affinity, self.level, self.exp, self.gold, \
            self.weapon, self.armor, self.trinket, \
            self.adv_count, self.total_gold, self.achieves, \
            self.last_signin, self.signin_streak, self.quest, \
            self.mood, self.stats, self.uptime_ms, \
            self.nickname, self.alpha, \
            self.collected, self.fortune, \
            self.essence, self.badge, self.inventory, self.weekly, \
            self.no_feed_streak, self._no_feed_egg, \
            self.fusion_count, self._midnight_day, \
            self.win_streak, self.best_streak, \
            self.coop_count, self.star_level, self.star_exp = self.load_state()
        self.adventuring = False   # 副本冒险中
        self.skill_cd = 0          # 疾跑冷却（毫秒）
        self._skill_job = None
        self._adv_job = None
        self._hunger_timer = 0
        self._mood_timer = 0       # 心情衰减计时
        self._fainted = False      # 饿晕标记（避免重复计数）
        self.weather = random.choice(WEATHERS)   # 模拟天气
        self._weather_timer = 0
        self._game = None          # 小游戏窗口
        self.ult_cd = 0            # 必杀技冷却（毫秒）
        self.ulting = False        # 必杀技释放中
        self._ult_job = None
        self._pop_mode = False     # 点泡泡小游戏进行中
        self._pop_score = 0
        self._pop_bubbles = []     # [x, y, r, born]
        self._pop_t0 = 0.0
        self._pop_job = None
        self._fireworks = 0        # 升级烟花剩余帧
        self._week_timer = 0       # 周报切换检查计时
        self.inventory = getattr(self, "inventory", None) or []
        self.arena_cd = 0          # 竞技场冷却（毫秒）
        self.sleeping = False      # 睡眠模式
        self.click_count = 0       # 连续点击计数（彩蛋）
        self._last_click = 0.0
        self.battle_cd = 0         # 双宠互搏冷却
        self._battle_other = None  # 对战对象
        self._battle_t = 0         # 对冲剩余毫秒
        self._battle_owner = False # 是否是结算发起者
        self._battle_dmg_taken = 0 # 互殴累计受击伤害
        self._battle_fight = False # 互殴阶段
        self._battle_fight_t = 0
        self._fight_punch = 0      # 出拳特效剩余毫秒
        self._fight_hurt = 0       # 受击闪光剩余毫秒
        self._fight_job = None     # 互殴打击计时
        self._fusion = False       # 合体技进行中
        self._fusion_t = 0
        self._fusion_target = None
        self._fusion_owner = None  # 结算伙伴
        self._fusion_done = False  # 合体结算标记
        self.no_feed_streak = getattr(self, "no_feed_streak", 0)
        self._no_feed_egg = getattr(self, "_no_feed_egg", False)
        self._check_day = date.today()
        self._last_feed_day = date.today()
        self._whack_game = None    # 打地鼠小游戏窗口
        self.fusion_count = getattr(self, "fusion_count", 0)
        self._midnight_day = getattr(self, "_midnight_day", "")
        self.win_streak = getattr(self, "win_streak", 0)   # 互搏连胜场数
        self.best_streak = getattr(self, "best_streak", 0) # 历史最高连胜
        self.coop_count = getattr(self, "coop_count", 0)   # 联手讨伐次数
        self.star_level = getattr(self, "star_level", 1)   # 宠物星级 1~5
        self.star_exp = getattr(self, "star_exp", 0)       # 星级经验
        self._hover_speed = None                            # 悬停暂停前的速度
        self._follow_target = None                          # 跟随模式目标宠物
        self.special_kind = None                            # 专属技能：roll/spin/boost
        self.special_t = 0                                  # 专属技能剩余毫秒
        self.special_cd = 0                                 # 专属技能冷却毫秒
        self._pokedex_timer = 0                             # 图鉴成就检查计时
        self._follow_form = "line"                          # 跟随队形 line/side
        self._coop_partner = None                           # 联手讨伐对象
        self._coop_done = False                             # 合作结算标记
        self._auto_check = 0       # 自动打架检测计时
        self._egg_timer = 0        # 午夜特典检测计时
        _PET_INSTANCES.append(self)
        self._bubble_top = None    # 浮动气泡窗口
        self._bubble_top_label = None
        self._bubble_visible = False
        self._food = None          # 食物画布

        # 初始位置：上边缘中部
        self.x = self.vrect.x0 + (self.vrect.x1 - self.vrect.x0 - self.fw) // 2
        self.y = self.vrect.y0
        self.speed = self.base_speed()

        self.build_ui()
        # 荣耀金皮肤解锁检查（达成 8 项成就）
        if self.pet_skin == "gold" and len(self.achieves) < ACHIEVE_GOLD:
            self.pet_skin = "default"
            self.frames = self.load_frames()
            self.fw, self.fh = self.display_size
            self.sprite.config(image=self.frames["walk"][0][0])
            self.show_bubble("「荣耀金」皮肤需达成 %d 项成就解锁！" % ACHIEVE_GOLD, 2800)
        self.schedule_random()
        self.root.after(TICK_MS, self.tick)
        self.root.after(1600, lambda: self.show_bubble("点我试试！"))
        self.root.after(3000, lambda: self.daily_signin(auto=True))   # 自动签到

    # ------------------------------------------------------------ UI
    def build_ui(self):
        r = self.root
        r.title("桌面宠物 · %s" % self.display_name())
        r.overrideredirect(True)
        r.wm_attributes("-topmost", True)
        r.wm_attributes("-transparentcolor", KEY)
        if self.alpha < 1.0:
            r.wm_attributes("-alpha", self.alpha)
        r.configure(bg=KEY)

        self.sprite = tk.Label(r, image=self.frames["walk"][0][0], bg=KEY, cursor="hand2")
        self.sprite.place(x=0, y=BUBBLE_MARGIN)
        # 稀有度光效：宠物脚下光环（按最高稀有度装备着色）
        self._glow = tk.Canvas(r, width=self.fw, height=self.fh, bg=KEY,
                               highlightthickness=0)
        self._glow.place(x=0, y=0)
        self._glow_phase = 0
        self.sprite.lift()

        self.bubble = tk.Label(r, text="", bg="#FFFFFF", fg="#3A3A3A",
                               font=("Microsoft YaHei UI", 11, "bold"),
                               bd=2, relief="ridge", padx=8, pady=2)
        self.bubble.place_forget()

        self.sprite.bind("<Button-1>", self.on_click)
        self.sprite.bind("<Double-Button-1>", self.on_double_click)
        self.sprite.bind("<B1-Motion>", self.on_drag_move)
        self.sprite.bind("<ButtonRelease-1>", self.on_drag_end)
        self.sprite.bind("<Button-3>", self.on_right_click)
        self.root.bind("<Enter>", self.on_hover_enter)
        self.root.bind("<Leave>", self.on_hover_leave)
        r.bind("<Button-3>", self.on_right_click)

        self.menu = tk.Menu(r, tearoff=0)
        self.menu.add_command(label="喂食", command=self.feed)
        self.menu.add_command(label="摸摸头", command=self.pet_head)
        self.menu.add_command(label="逗它玩", command=self.play_with)
        self.menu.add_separator()
        adv = tk.Menu(self.menu, tearoff=0)
        for key in ("easy", "normal", "night"):
            adv.add_command(label=DIFFS[key][0],
                            command=lambda k=key: self.start_adventure(k))
        self.menu.add_cascade(label="去冒险（副本）", menu=adv)
        self.menu.add_command(label="装备商店（100金币）", command=self.buy_gear)
        upg = tk.Menu(self.menu, tearoff=0)
        for slot, label in (("weapon", "武器"), ("armor", "防具"), ("trinket", "饰品")):
            upg.add_command(label=label, command=lambda s=slot: self.upgrade_gear(s))
        self.menu.add_cascade(label="强化装备", menu=upg)
        dism = tk.Menu(self.menu, tearoff=0)
        for slot, label in (("weapon", "武器"), ("armor", "防具"), ("trinket", "饰品")):
            dism.add_command(label=label, command=lambda s=slot: self.dismantle(s))
        self.menu.add_cascade(label="分解装备（得精华）", menu=dism)
        self.menu.add_command(label="合成装备（50精华）", command=self.synthesize)
        rec = tk.Menu(self.menu, tearoff=0)
        for slot, label in (("weapon", "武器"), ("armor", "防具"), ("trinket", "饰品")):
            rec.add_command(label=label, command=lambda s=slot: self.recast(s))
        self.menu.add_cascade(label="重铸装备（30精华洗主题）", menu=rec)
        badge = tk.Menu(self.menu, tearoff=0)
        badge.add_command(label="取消佩戴", command=lambda: self.wear_badge(""))
        for key, (title, _r) in ACHIEVEMENTS.items():
            badge.add_command(label=title, command=lambda k=key: self.wear_badge(k))
        self.menu.add_cascade(label="佩戴勋章", menu=badge)
        self.menu.add_command(label="使用技能：疾跑", command=self.use_skill)
        self.menu.add_command(label="必杀技：宠物风暴", command=self.use_ultimate)
        self.menu.add_command(label="专属技能：%s" % self.special_skill_name(),
                              command=self.special_skill)
        self.menu.add_command(label="竞技场（对战）", command=self.arena_fight)
        self.menu.add_command(label="找同伴打架", command=self.pet_battle)
        self.menu.add_command(label="合体技：双子风暴", command=self.fusion_skill)
        self.menu.add_command(label="背包", command=self.show_inventory)
        self.menu.add_separator()
        self.menu.add_command(label="每日签到", command=self.daily_signin)
        self.menu.add_command(label="成就图鉴", command=self.show_achievements)
        self.menu.add_command(label="宠物图鉴", command=self.show_pokedex)
        self.menu.add_command(label="装备图鉴", command=self.show_collection)
        self.menu.add_command(label="宠物日志", command=self.show_log)
        self.menu.add_command(label="宠物周报", command=self.show_weekly)
        self.menu.add_command(label="给它起名字", command=self.rename_pet)
        self.menu.add_command(label="接住食物（小游戏）", command=self.start_game)
        self.menu.add_command(label="点泡泡（小游戏）", command=self.start_pop_game)
        self.menu.add_command(label="猜盒子（小游戏）", command=self.start_box_game)
        self.menu.add_command(label="打地鼠（小游戏）", command=self.start_whack_game)
        self.menu.add_command(label="猜点数（小游戏）", command=self.start_dice_game)
        self.menu.add_command(label="石头剪刀布（小游戏）", command=self.start_rps_game)
        une = tk.Menu(self.menu, tearoff=0)
        for slot, label in (("weapon", "武器"), ("armor", "防具"), ("trinket", "饰品")):
            une.add_command(label=label, command=lambda s=slot: self.unequip(s))
        self.menu.add_cascade(label="卸下装备", menu=une)
        self.menu.add_command(label="属性面板详情", command=self.show_profile)
        app = tk.Menu(self.menu, tearoff=0)
        for v in (1.0, 0.85, 0.70, 0.55):
            app.add_command(label=str(int(v * 100)) + "%",
                            command=lambda x=v: self.set_alpha(x))
        self.menu.add_cascade(label="外观（透明度）", menu=app)
        self.menu.add_command(label="跟随我", command=self.start_chase)
        fol = tk.Menu(self.menu, tearoff=0)
        fol.add_command(label="排成一列", command=lambda: self.follow_companion("line"))
        fol.add_command(label="并排走", command=lambda: self.follow_companion("side"))
        self.menu.add_cascade(label="跟随同伴", menu=fol)
        self.menu.add_command(label="联手讨伐首领", command=self.coop_boss)
        self.menu.add_command(label="查看状态", command=self.show_status)
        self.menu.add_separator()
        self.menu.add_command(label="暂停移动", command=self.toggle_pause)
        self.menu.add_command(label="随机瞬移", command=self.teleport)
        self.menu.add_separator()
        self.menu.add_command(label="退出宠物", command=self.quit)
        self.root.update_idletasks()   # 让 tk 完成首轮布局，之后位置由 SetWindowPos 接管
        self.apply_geometry()
        self._install_hotkey_once()    # F8 全局热键：切换跟随队形

    def load_frames(self):
        pet, skin = self.pet_id, self.pet_skin
        d = os.path.join(script_dir(), "sprites_display", pet, skin)
        if not os.path.isdir(d):
            # 「荣耀金」皮肤：无预生成目录时运行时染金（以 default 为基底）
            if skin == "gold" and _HAS_PIL:
                base = os.path.join(script_dir(), "sprites_display", pet, "default")
                if os.path.isdir(base):
                    return self._load_tinted(base, tint_golden)
            # 回退：旧版单宠物目录
            alt = os.path.join(script_dir(), "sprites_display")
            if pet == "cockroach" and skin == "default" and os.path.isdir(alt) \
                    and os.path.exists(os.path.join(alt, "walk_1.png")):
                d = alt
            else:
                print("未找到精灵帧目录 %s\n请先运行：python make_sprites.py" % d, file=sys.stderr)
                sys.exit(1)
        loaded = {}
        for state, names in FRAMES.items():
            pairs = []
            for n in names:
                p, pf = os.path.join(d, n + ".png"), os.path.join(d, n + "_flip.png")
                if not (os.path.exists(p) and os.path.exists(pf)):
                    print("缺少帧文件：%s，请重新运行 make_sprites.py" % p, file=sys.stderr)
                    sys.exit(1)
                pairs.append((tk.PhotoImage(file=p), tk.PhotoImage(file=pf)))
            loaded[state] = pairs
        img = loaded["walk"][0][0]
        self.display_size = (img.width(), img.height())
        return loaded

    def _load_tinted(self, base_dir, tint_fn):
        """加载目录帧并逐帧运行时染色（用于「荣耀金」皮肤）"""
        loaded = {}
        for state, names in FRAMES.items():
            pairs = []
            for n in names:
                p, pf = os.path.join(base_dir, n + ".png"), \
                        os.path.join(base_dir, n + "_flip.png")
                im = tint_fn(PILImage.open(p))
                imf = tint_fn(PILImage.open(pf))
                pairs.append((ImageTk.PhotoImage(im), ImageTk.PhotoImage(imf)))
            loaded[state] = pairs
        img = loaded["walk"][0][0]
        self.display_size = (img.width(), img.height())
        return loaded

    # ------------------------------------------------------------ 移动
    def base_speed(self):
        """基础速度：按屏幕大小缩放，约 55-130 像素/秒"""
        span = max(self.vrect.x1 - self.vrect.x0, self.vrect.y1 - self.vrect.y0)
        return min(130.0, max(55.0, span / 25.0)) * random.uniform(0.8, 1.2)

    def bounds(self):
        """当前所在显示器的工作区（底边避开任务栏）"""
        return get_work_area(self.x + self.fw / 2, self.y + self.fh / 2)

    def step_along(self, b):
        """沿当前边缘走一步（+1 为顺时针：上→右→下→左）"""
        ds = self.speed * TICK_MS / 1000.0 * self.dir
        if self.edge == "top":
            self.x += ds
            self.facing = 1 if self.dir < 0 else 0
        elif self.edge == "bottom":
            self.x -= ds
            self.facing = 1 if self.dir > 0 else 0
        elif self.edge == "left":
            self.y += ds
        else:  # right
            self.y += ds

    def check_corner(self, b):
        """到达端点：随机选择 转弯(相邻边) / 环绕(相对侧重现) / 反向"""
        w, h = self.fw, self.fh
        corner = None
        if self.edge == "top":
            if self.dir > 0 and self.x + w >= b.x1 - 1: corner = "right"
            elif self.dir < 0 and self.x <= b.x0 + 1: corner = "left"
        elif self.edge == "right":
            if self.dir > 0 and self.y + h >= b.y1 - 1: corner = "bottom"
            elif self.dir < 0 and self.y <= b.y0 + 1: corner = "top"
        elif self.edge == "bottom":
            if self.dir > 0 and self.x <= b.x0 + 1: corner = "left"
            elif self.dir < 0 and self.x + w >= b.x1 - 1: corner = "right"
        else:  # left
            if self.dir > 0 and self.y + h >= b.y1 - 1: corner = "bottom"
            elif self.dir < 0 and self.y <= b.y0 + 1: corner = "top"
        if corner is None:
            return
        self.on_corner(b, corner)

    def on_corner(self, b, corner):
        w, h = self.fw, self.fh
        roll = random.random()
        if roll < 0.45:
            # 转弯到相邻边缘，继续顺时针/逆时针（优先保持绕屏方向）
            self.edge = corner
            if corner == "top": self.y = b.y0
            elif corner == "bottom": self.y = b.y1 - h
            elif corner == "left": self.x = b.x0
            else: self.x = b.x1 - w
        elif roll < 0.85:
            # 穿墙环绕：保持方向继续走，穿出屏幕从相对边出现（有完整
            # 出屏→回屏过程，不再瞬移）。例如右边缘 → 从左边走进来。
            self.wrapping = True
        else:
            # 反向折返
            self.dir *= -1

    def move_to_target(self):
        """飞走：直线冲向目标点，到达后贴边继续爬"""
        tx, ty = self.fly_target
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        step = self.speed * TICK_MS / 1000.0
        if dist <= step:
            self.x, self.y = tx, ty
            self.fly_target = None
            self.state = "walk"
            self.speed = self.base_speed()
            self.snap_to_edge()
        else:
            self.x += dx / dist * step
            self.y += dy / dist * step
            # 飞行时始终按水平方向决定朝向，避免横穿时背面朝前
            self.facing = 1 if dx < 0 else 0

    def snap_to_edge(self):
        """到达后吸附到最近的边缘，恢复绕屏爬行"""
        b = self.bounds()
        w, h = self.fw, self.fh
        cx, cy = self.x + w / 2, self.y + h / 2
        dl, dr = cx - b.x0, b.x1 - cx
        dt, db = cy - b.y0, b.y1 - cy
        m = min(dl, dr, dt, db)
        if m == dl:
            self.edge, self.x = "left", b.x0
        elif m == dr:
            self.edge, self.x = "right", b.x1 - w
        elif m == dt:
            self.edge, self.y = "top", b.y0
        else:
            self.edge, self.y = "bottom", b.y1 - h
        self.dir = 1

    def clamp_pos(self, b):
        w, h = self.fw, self.fh
        if self.x < b.x0: self.x = b.x0
        if self.y < b.y0: self.y = b.y0
        if self.x + w > b.x1: self.x = b.x1 - w
        if self.y + h > b.y1: self.y = b.y1 - h

    def move(self):
        if self.paused or self.dragging:
            return
        if self.state in ("idle", "spin", "dizzy"):
            return
        if self.state == "chase":
            self.chase_step()
            return
        b = self.bounds()
        if self.wrapping:
            self.wrap_move(b)
            return
        if self.state in ("scared", "fly") and self.fly_target is not None:
            self.move_to_target()
            return
        self.step_along(b)
        self.check_corner(b)

    def chase_step(self):
        """跟随鼠标：朝光标爬，到达后原地转圈结束"""
        x, y = self.get_cursor()
        w, h = self.fw, self.fh
        dx = x - (self.x + w / 2)
        dy = y - (self.y + h / 2)
        dist = math.hypot(dx, dy)
        step = self.speed * TICK_MS / 1000.0
        if dist < 80 or dist <= step:
            self.state = "spin"
            self.state_left = 1200
            self.facing = 0
            return
        self.x += dx / dist * step
        self.y += dy / dist * step
        self.facing = 1 if dx < 0 else 0

    def wrap_move(self, b):
        """穿墙环绕：沿当前方向继续走，允许出屏；完全出屏后从相对边屏外
        回来，回到屏内即恢复贴边爬行。"""
        w, h = self.fw, self.fh
        ds = self.speed * TICK_MS / 1000.0 * self.dir
        if self.edge in ("top", "right"):
            if self.edge == "top":
                self.x += ds
            else:
                self.y += ds
        else:
            if self.edge == "bottom":
                self.x -= ds
            else:
                self.y += ds
        # 完全出屏 → 传送到相对边屏外（方向不变，继续走回屏内）
        if self.x + w < b.x0:            # 完全出左屏
            self.x = b.x1 + 8
        elif self.x > b.x1 + w:          # 完全出右屏
            self.x = b.x0 - w - 8
        elif self.y + h < b.y0:          # 完全出上屏
            self.y = b.y1 + 8
        elif self.y > b.y1 + h:          # 完全出下屏
            self.y = b.y0 - h - 8
        # 回到屏内 → 结束穿墙，恢复贴边
        if (b.x0 <= self.x and self.x + w <= b.x1 and
                b.y0 <= self.y and self.y + h <= b.y1):
            self.wrapping = False

    # ------------------------------------------------------------ 随机行为
    def schedule_random(self):
        # 心情好 → 更活泼（随机行为更频繁）；夜晚 → 更困倦（间隔拉长）
        h = time.localtime().tm_hour
        if h >= 22 or h < 7:
            lo, hi = 2200, 4600
        elif self.mood >= 70:
            lo, hi = 1000, 2800
        else:
            lo, hi = 1400, 3400
        self.root.after(random.randint(lo, hi), self.random_act)

    def random_act(self):
        self.schedule_random()
        if self.paused or self.state != "walk" or self.adventuring or self.ulting:
            return
        h = time.localtime().tm_hour
        night = (h >= 22 or h < 7)
        roll = random.random()
        if roll < 0.12:
            self.dir *= -1                                   # 随机变向（低频，保持绕圈顺畅）
        elif roll < (0.52 if night else 0.42):
            self.state = "idle"                              # 随机停顿（夜晚更容易困）
            self.state_left = random.randint(700, 2400)
            self.anim_idx = 0
        elif roll < (0.87 if self.mood >= 70 else 0.85):
            self.speed = self.base_speed()                   # 随机变速
        elif roll < 0.97:
            self.fly_to_random_edge()                        # 飞走/穿越到另一条边
        else:
            self.encounter_event()                           # 奇遇事件（3%）

    def fly_to_random_edge(self):
        b = self.bounds()
        w, h = self.fw, self.fh
        opp = {"top": "bottom", "bottom": "top",
               "left": "right", "right": "left"}[self.edge]
        if random.random() < 0.7:
            edge = opp          # 优先穿越到相对边（穿过整屏）
        else:
            others = [e for e in self.EDGES if e not in (self.edge, opp)]
            edge = random.choice(others)
        t = random.uniform(0.2, 0.8)
        if edge == "top":
            tx, ty = b.x0 + (b.x1 - b.x0 - w) * t, b.y0
        elif edge == "bottom":
            tx, ty = b.x0 + (b.x1 - b.x0 - w) * t, b.y1 - h
        elif edge == "left":
            tx, ty = b.x0, b.y0 + (b.y1 - b.y0 - h) * t
        else:
            tx, ty = b.x1 - w, b.y0 + (b.y1 - b.y0 - h) * t
        self.fly_target = (tx, ty)
        self.state = "scared"
        self.speed = self.base_speed() * random.uniform(8, 12)

    # ------------------------------------------------------------ 互动
    def on_hover_enter(self, _event):
        """鼠标悬停：宠物停止移动（QQ 宠物式），离开恢复"""
        if self.dragging or self.sleeping:
            return
        if self._battle_t > 0 or self._battle_fight or self._fusion_t > 0 \
                or self.adventuring or self._follow_target is not None:
            return
        if self._hover_speed is None:
            self._hover_speed = self.speed
            self.state = "idle"
            self.state_left = 0
            self.speed = 0

    def on_hover_leave(self, _event):
        """鼠标离开：恢复移动"""
        if self._hover_speed is not None:
            self.speed = self._hover_speed
            self._hover_speed = None
            self.state = "walk"
            self.state_left = 0

    def on_click(self, _event):
        # 点泡泡小游戏期间，点击交给泡泡判定
        if self._pop_mode:
            return
        self._stop_follow()
        if self.sleeping:
            self._wake()
        # 连续点击彩蛋：1.5 秒内连击 8 次 → 眩晕
        now = time.monotonic()
        if now - self._last_click > 1.5:
            self.click_count = 0
        self.click_count += 1
        self._last_click = now
        if self.click_count >= 8:
            self.click_count = 0
            self.state = "dizzy"
            self.state_left = 2200
            self.show_bubble(self.lines("dizzy"))
            return
        self.add_affinity(1)
        self.add_mood(2)
        self.add_star_exp(3)          # 互动积累星级经验
        self.stats["click"] += 1
        self.weekly["interact"] += 1
        self._quest_act("interact")
        roll = random.random()
        if roll < 0.55:
            # 受惊加速逃窜
            self.state = "scared"
            self.state_left = 950
            self.speed = self.base_speed() * random.uniform(4.5, 6.5)
            self.fly_target = None
            if random.random() < 0.45:
                self.dir *= -1
        elif roll < 0.85:
            # 反向逃跑
            self.dir *= -1
            self.state = "scared"
            self.state_left = 450
            self.speed = self.base_speed() * 2.0
            self.fly_target = None
        else:
            # 吓到僵住
            self.state = "idle"
            self.state_left = random.randint(900, 1600)
            self.anim_idx = 0
        self.show_bubble(self.lines("click"))

    def on_double_click(self, _event):
        """双击：原地转圈 + 好感度"""
        if self.sleeping:
            self._wake()
        self.add_affinity(1)
        self.add_mood(2)
        self.stats["click"] += 1
        self._quest_act("interact")
        self.state = "spin"
        self.state_left = 1300
        self.fly_target = None
        self.show_bubble(self.lines("play"))

    def on_drag_start(self, event):
        """按下开始拖拽（记录偏移）"""
        self.dragging = True
        self.wrapping = False
        self._drag_off = (event.x_root - self.x,
                          event.y_root - (self.y - BUBBLE_MARGIN))

    def on_drag_move(self, event):
        if not self.dragging:
            self.on_drag_start(event)
            return
        self.x = event.x_root - self._drag_off[0]
        self.y = event.y_root - self._drag_off[1] + BUBBLE_MARGIN
        self.apply_geometry()

    def on_drag_end(self, _event):
        if not self.dragging:
            return
        self.dragging = False
        # 松手：受惊逃窜一小段
        self.state = "scared"
        self.state_left = 600
        self.speed = self.base_speed() * 3.0
        self.fly_target = None
        self.dir = random.choice((1, -1))
        self.show_bubble(self.lines("click"))

    def on_right_click(self, _event):
        self._stop_follow()
        self.refresh_gear_menu()
        self.menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())

    # ------------------------------------------------------------ 玩法
    def feed(self):
        """喂食：喂它最爱的食物（饱腹+60 好感+5 心情+8）；饿晕时唤醒"""
        self._stop_follow()
        if self._food is not None:
            return
        if self.sleeping:
            self._wake()
        fav = FAVORITE_FOOD.get(self.pet_id, "美食")
        self._last_feed_day = date.today()
        self.no_feed_streak = 0        # 喂食重置连续不喂天数
        self.add_star_exp(10)          # 喂食积累星级经验
        self.add_hunger(60)
        self.add_affinity(5)
        self.add_mood(8)
        self.stats["feed"] += 1
        self.weekly["feed"] += 1
        self._quest_act("interact")
        if self.hunger > 0 and self.state == "idle" and self.speed == 0:
            # 饿晕唤醒
            self.state = "walk"
            self.state_left = 0
            self.speed = self.base_speed()
            self.show_bubble("活过来啦！%s真香！" % fav, 2200)
        else:
            self.show_bubble("最爱！%s！%s" % (fav, self.lines("feed")), 2000)
        c = tk.Canvas(self.root, width=36, height=36, bg=KEY, highlightthickness=0)
        c.create_oval(10, 15, 28, 32, fill="#F4A261", outline="#E76F51")
        c.create_polygon(12, 17, 19, 3, 26, 17, fill="#52B788", outline="")
        c.place(x=self.fw - 10, y=BUBBLE_MARGIN + 8)
        self._food = c
        self.root.after(1700, self._clear_food)
        self.show_bubble(self.lines("feed"))

    def _clear_food(self):
        if self._food is not None:
            try:
                self._food.place_forget()
                self._food.destroy()
            except Exception:
                pass
            self._food = None

    def pet_head(self):
        """摸摸头：好感 +2、冒爱心气泡"""
        if self.sleeping:
            self._wake()
        self.add_affinity(2)
        self.add_mood(4)
        self.stats["pet"] += 1
        self.weekly["interact"] += 1
        self._quest_act("interact")
        self.state = "spin"
        self.state_left = 900
        self.fly_target = None
        self.show_bubble(self.lines("pet"))

    def play_with(self):
        """逗它玩：转圈 + 好感 +1"""
        self._stop_follow()
        if self.sleeping:
            self._wake()
        self.add_affinity(1)
        self.add_mood(3)
        self.add_star_exp(3)          # 互动积累星级经验
        self.stats["play"] += 1
        self.weekly["interact"] += 1
        self._quest_act("interact")
        self.state = "spin"
        self.state_left = 1600
        self.fly_target = None
        self.show_bubble(self.lines("play"))

    # —— 每日任务 ——
    def _quest_act(self, key, n=1):
        """每日任务计数；跨天自动重置"""
        if self.quest.get("date") != time.strftime("%Y-%m-%d"):
            self.quest = {"date": time.strftime("%Y-%m-%d"), "adv": 0,
                          "interact": 0, "done": []}
        self.quest[key] = self.quest.get(key, 0) + n
        self._quest_check()

    def _quest_check(self):
        for key, title, need in QUESTS:
            if self.quest.get(key, 0) >= need and key not in self.quest.get("done", []):
                self.quest["done"].append(key)
                self.add_gold(QUEST_REWARD)
                self.show_bubble("每日任务「%s」完成！金币+%d" % (title, QUEST_REWARD), 2600)
        self.save_state()

    def start_chase(self):
        """跟随我：朝鼠标爬 8 秒，到达后转圈"""
        self._stop_follow()
        self.state = "chase"
        self.chase_left = 8000
        self.speed = self.base_speed() * 1.8
        self.fly_target = None
        self.show_bubble(self.lines("play"))

    def follow_companion(self, form="line"):
        """双宠跟随模式：一宠跟着另一宠（form=line 排成一列 / side 并排走）"""
        others = [p for p in _PET_INSTANCES
                  if p is not self and p.root.winfo_exists()]
        if not others:
            self.show_bubble("没有同伴可以跟随…（控制台开启第二只宠物）", 2400)
            return
        self._follow_target = random.choice(others)
        self._follow_form = form
        self.state = "walk"
        self.state_left = 0
        self.speed = self.base_speed() * 1.15
        self.show_bubble("跟上你了！%s" % ("（排成一列）" if form == "line" else "（并排走）"), 1500)

    def _follow_tick(self):
        """跟随模式移动：line 尾随 / side 并排，保持距离待命"""
        o = self._follow_target
        if o is None or not o.root.winfo_exists():
            self._follow_target = None
            self.show_bubble("跟丢了…", 1200)
            return
        if o._battle_t > 0 or o._battle_fight or o._fusion_t > 0 or o.sleeping:
            self._follow_target = None
            self.show_bubble("它忙去了，我先自己逛", 1500)
            return
        if self._follow_form == "side":
            tx, ty = o.x - 70, o.y      # 并排：保持在目标左侧 70px
        else:
            tx, ty = o.x, o.y           # 排成一列：尾随目标位置
        dx = tx - self.x
        dy = ty - self.y
        dist = math.hypot(dx, dy) or 1
        if dist > 40:
            self.facing = 1 if dx < 0 else 0
            ds = self.speed * TICK_MS / 1000.0
            self.x += dx / dist * ds
            self.y += dy / dist * ds
            if self.state != "walk":
                self.state = "walk"
                self.state_left = 0
        elif dist < 24:
            ds = self.speed * TICK_MS / 1000.0
            self.x -= dx / dist * ds
            self.y -= dy / dist * ds
        else:
            if self.state != "idle":
                self.state = "idle"
                self.state_left = 0
                self.speed = 0

    def _stop_follow(self):
        """互动打断跟随"""
        if self._follow_target is not None:
            self._follow_target = None
            if self.state == "walk":
                self.speed = self.base_speed()

    def show_achievements(self):
        """成就图鉴：列出全部成就与达成状态"""
        lines = ["成就图鉴 %d/%d" % (len(self.achieves), len(ACHIEVEMENTS))]
        for key, (title, reward) in ACHIEVEMENTS.items():
            mark = "✓" if key in self.achieves else "✗"
            lines.append("%s %s（+%d）" % (mark, title, reward))
        self.show_bubble("\n".join(lines), 6000)

    def show_status(self):
        """查看状态：等级/经验/金币 + 饱腹/好感 + 装备/套装 + 技能 + 任务/成就"""
        atk, dfs = self.atk_def()
        title_line = "%s「%s」Lv.%d  经验 %d/%d" % (
            self.display_name(), self.title(), self.level, self.exp, self.exp_needed())
        if self.badge:
            title_line += "  勋章：%s" % ACHIEVEMENTS[self.badge][0]
        if self.sleeping:
            title_line += "  💤 睡觉中"
        lines = [title_line,
                 "金币 %d | 精华 %d | 背包 %d/%d" % (
                     self.gold, self.essence, len(self.inventory), INV_MAX),
                 "心情 %d（%s）| 天气 %s" % (self.mood, self.mood_title(), self.weather),
                 "饱腹 %d | 好感 %d（%s）| 运势 %s" % (
                     self.hunger, self.affinity, self.affinity_level(),
                     self.fortune_today()),
                 "攻击 %d | 防御 %d | 冒险 %d 次" % (atk, dfs, self.adv_count)]
        for slot, label in (("weapon", "武器"), ("armor", "防具"), ("trinket", "饰品")):
            g = getattr(self, slot)
            if g:
                extra = ("·%s" % g.get("set")) if g.get("set") else ""
                lines.append("%s：%s·%s+%d%s" % (
                    label, g["name"], g["rarity"], g.get("upgrade", 0), extra))
            else:
                lines.append("%s：无" % label)
        # 套装
        sets = {}
        for slot in ("weapon", "armor", "trinket"):
            g = getattr(self, slot)
            if g and g.get("set"):
                sets[g["set"]] = sets.get(g["set"], 0) + 1
        if sets:
            sname = max(sets, key=sets.get)
            n = sets[sname]
            sa, sd, sb = self.set_bonus()
            lines.append("套装：%s×%d（+%d攻 +%d防%s）" % (
                sname, n, sa, sd, " 金币+20%%" if sb else ""))
        else:
            lines.append("套装：无（收集同主题3件激活）")
        sk = []
        if self.level >= 2:
            sk.append("疾跑" + ("冷却%d秒" % (self.skill_cd // 1000) if self.skill_cd > 0 else "可用"))
        if self.level >= 4:
            sk.append("好运")
        if self.level >= 6:
            sk.append("寻宝雷达")
        if self.level >= 8:
            sk.append("铁壁")
        if self.level >= 10:
            sk.append("聚宝")
            sk.append("必杀" + ("冷却%d分%d秒" % divmod(self.ult_cd // 1000, 60)
                                if self.ult_cd > 0 else "可用"))
        if self.level >= 12:
            sk.append("疾风")
        if self.level >= 14:
            sk.append("好胃口")
        lines.append("技能：" + ("、".join(sk) if sk else "Lv2 解锁疾跑"))
        if self.quest.get("date") == time.strftime("%Y-%m-%d"):
            qadv = min(self.quest.get("adv", 0), 2)
            qin = min(self.quest.get("interact", 0), 10)
            lines.append("今日任务：冒险 %d/2 互动 %d/10" % (qadv, qin))
        else:
            lines.append("今日任务：冒险 0/2 互动 0/10")
        lines.append("成就 %d/%d | 签到连续 %d 天" % (len(self.achieves),
                                                   len(ACHIEVEMENTS), self.signin_streak))
        self.show_bubble("\n".join(lines), 6000)

    def show_profile(self):
        """属性面板详情页：完整养成信息（Toplevel 窗口）"""
        if getattr(self, "_profile_win", None) is not None:
            try:
                self._profile_win.destroy()
            except Exception:
                pass
        top = tk.Toplevel(self.root)
        self._profile_win = top
        top.title("宠物属性面板")
        top.configure(bg="#F7F5F0")
        top.attributes("-topmost", True)
        atk, dfs = self.atk_def()
        sets = {}
        for slot in ("weapon", "armor", "trinket"):
            g = getattr(self, slot)
            if g and g.get("set"):
                sets[g["set"]] = sets.get(g["set"], 0) + 1
        sname = max(sets, key=sets.get) if sets else None
        sa, sd, sb = self.set_bonus()
        rows = [
            ("基础信息", [
                ("昵称", self.display_name()),
                ("宠物", "%s · %s皮肤" % (pet_display_name(self.pet_id), self.pet_skin)),
                ("等级 / 称号", "Lv.%d「%s」" % (self.level, self.title())),
                ("经验", "%d / %d" % (self.exp, self.exp_needed())),
                ("心情 / 饱腹 / 好感", "%d（%s） / %d / %d（%s）" % (
                    self.mood, self.mood_title(), self.hunger,
                    self.affinity, self.affinity_level())),
                ("天气 / 运势", "%s / %s" % (self.weather, self.fortune_today())),
            ]),
            ("战斗属性", [
                ("攻击", "%d（等级基础 + 装备）" % atk),
                ("防御", "%d" % dfs),
                ("冒险 / 首领", "%d 次 / %d 次" % (self.adv_count, self.stats.get("boss", 0))),
                ("竞技场", "CD %d 秒" % (self.arena_cd // 1000) if self.arena_cd > 0 else "可用"),
            ]),
            ("资源", [
                ("金币", "%d" % self.gold),
                ("精华", "%d" % self.essence),
                ("背包", "%d / %d" % (len(self.inventory), INV_MAX)),
                ("签到连续", "%d 天" % self.signin_streak),
                ("合体技", "已发动 %d 次" % self.fusion_count),
                ("互搏连胜", "当前 %d 连胜（最高 %d）" % (self.win_streak, self.best_streak)),
            ]),
            ("装备", [
                ("武器", "%s·%s+%d%s" % (self.weapon["name"], self.weapon["rarity"],
                                         self.weapon.get("upgrade", 0),
                                         "·%s" % self.weapon["set"]) if self.weapon else "无"),
                ("防具", "%s·%s+%d%s" % (self.armor["name"], self.armor["rarity"],
                                         self.armor.get("upgrade", 0),
                                         "·%s" % self.armor["set"]) if self.armor else "无"),
                ("饰品", "%s·%s+%d%s" % (self.trinket["name"], self.trinket["rarity"],
                                         self.trinket.get("upgrade", 0),
                                         "·%s" % self.trinket["set"]) if self.trinket else "无"),
                ("套装", "%s×%d（+%d攻 +%d防%s）" % (sname, sets[sname], sa, sd,
                                                  " 金币+20%%" if sb else "")
                 if sname else "未激活（同主题 3 件成套）"),
            ]),
            ("成长", [
                ("成就", "%d / %d 项" % (len(self.achieves), len(ACHIEVEMENTS))),
                ("勋章", ACHIEVEMENTS[self.badge][0] if self.badge else "无"),
                ("宠物星级", self.star_display()),
                ("相伴时长", "%d 小时 %d 分" % divmod(self.uptime_ms // 60000, 60)),
                ("饿晕次数", "%d" % self.stats.get("faint", 0)),
                ("连续不喂食", "%d 天" % self.no_feed_streak),
            ]),
        ]
        tk.Label(top, text="宠物属性面板", font=("Microsoft YaHei UI", 13, "bold"),
                 bg="#F7F5F0", fg="#1A1B1C").pack(pady=(10, 2))
        tk.Label(top, text="右键宠物菜单也可查看简要状态", font=("Microsoft YaHei UI", 9),
                 bg="#F7F5F0", fg="#8A8F98").pack()
        for title, items in rows:
            fr = tk.Frame(top, bg="#F7F5F0")
            fr.pack(fill="x", padx=14, pady=(8, 0))
            tk.Label(fr, text=title, font=("Microsoft YaHei UI", 10, "bold"),
                     bg="#F7F5F0", fg="#C0392B").pack(anchor="w")
            for k, v in items:
                line = tk.Frame(fr, bg="#FFFFFF")
                line.pack(fill="x", pady=1)
                tk.Label(line, text=k, width=14, anchor="w", padx=8,
                         font=("Microsoft YaHei UI", 10), bg="#FFFFFF", fg="#6B7280"
                         ).pack(side="left")
                tk.Label(line, text=v, anchor="w", padx=8,
                         font=("Microsoft YaHei UI", 10), bg="#FFFFFF", fg="#1A1B1C"
                         ).pack(side="left", fill="x", expand=True)

    # —— RPG：经验 / 等级 / 金币 ——
    def exp_needed(self):
        return self.level * 30

    def add_exp(self, n):
        self.exp += n
        self.weekly["exp"] += n
        while self.exp >= self.exp_needed():
            self.exp -= self.exp_needed()
            self.level += 1
            self._fireworks = 70            # 升级烟花
            self.show_bubble("升级啦！Lv.%d「%s」" % (self.level, self.title()), 2500)
            self.check_achievements("lv5" if self.level == 5
                                    else "lv10" if self.level == 10 else None)
        self.save_state()

    def add_gold(self, n):
        self.gold += n
        if n > 0:
            self.total_gold += n
            self.weekly["gold"] += n
            self.check_achievements("gold_500" if self.total_gold >= 500
                                    else "gold_2000" if self.total_gold >= 2000 else None)
        self.save_state()

    # —— RPG：装备 ——
    def roll_rarity(self, shop=False):
        if shop:
            r = random.random()
            if r < 0.30: return "普通"
            if r < 0.70: return "优秀"
            if r < 0.90: return "精良"
            if r < 0.98: return "史诗"
            return "传说"
        r = random.random()
        if r < 0.50: return "普通"
        if r < 0.80: return "优秀"
        if r < 0.95: return "精良"
        if r < 0.99: return "史诗"
        return "传说"

    def make_gear(self, rarity):
        slot = random.choice(("weapon", "armor", "trinket"))
        name = random.choice(GEAR_POOL[slot])
        return {"name": name, "rarity": rarity, "slot": slot,
                "set": random.choice(SET_POOL), "upgrade": 0}

    def set_bonus(self):
        """套装加成：同主题 2 件 +3攻防，3 件 +6攻防且副本金币+20%"""
        sets = {}
        for slot in ("weapon", "armor", "trinket"):
            g = getattr(self, slot)
            if g and g.get("set"):
                sets[g["set"]] = sets.get(g["set"], 0) + 1
        n = max(sets.values()) if sets else 0
        return SET_BONUS.get(n, (0, 0, 0.0))

    def atk_def(self):
        a = d = self.level
        for slot in ("weapon", "armor", "trinket"):
            g = getattr(self, slot)
            if g:
                r = RARITY_STAT[g["rarity"]]
                up = g.get("upgrade", 0)
                a += r[0] + up
                d += r[1] + up
        sa, sd, _ = self.set_bonus()
        a += sa
        d += sd
        if self.level >= 8:
            d += 4                             # 铁壁（Lv8）：防御 +4
        return a, d

    # —— RPG：副本冒险 ——
    def start_adventure(self, diff="normal"):
        self._stop_follow()
        if self.adventuring:
            self.show_bubble("已经在冒险啦！", 1600)
            return
        info = DIFFS[diff]
        self.adventuring = True
        self._adv_diff = diff
        dur = random.randint(*info[1])
        if self.level >= 6:
            dur = max(5, dur // 2)          # 寻宝雷达：副本时间减半
        if self.level >= 12:
            dur = max(3, int(dur * 0.7))    # 疾风（Lv12）：时间再减 30%
        self._adv_job = self.root.after(dur * 1000, self.finish_adventure)
        self.state = "walk"
        self.state_left = 0
        self.speed = self.base_speed() * 3.0   # 冒险中疾走绕屏
        self.show_bubble("【%s】出发！%d 秒后归来" % (info[0], dur), 2200)

    def finish_adventure(self):
        self.adventuring = False
        self._adv_job = None
        self.speed = self.base_speed()
        self.adv_count += 1
        self.stats["adv"] += 1
        self.weekly["adv"] += 1
        self._quest_act("adv")
        name, _dur, base_exp, gold_rng, rate, boss_rate, boss_mult = \
            DIFFS.get(self._adv_diff, DIFFS["normal"])
        gold = random.randint(*gold_rng) + self.level * 2
        gold = int(gold * self.fortune_mult())               # 今日运势
        gold = int(gold * (1.0 + self.set_bonus()[2]))   # 套装金币加成
        if self.level >= 10:
            gold = int(gold * 1.25)          # 聚宝（Lv10）：金币 +25%
        exp = base_exp + self.level * 2
        if self.level >= 4:
            rate = min(0.85, rate * 2)          # 好运（Lv4）：掉率翻倍
        # 噩梦难度首领战
        if self._adv_diff == "night" and random.random() < BOSS_RATE:
            self._boss_fight()
            return
        drop = None
        drop_ok = False
        if random.random() < rate:
            drop = self.make_gear(self.roll_rarity(shop=False))
            drop_ok = self._equip_or_sell(drop)
            self.check_achievements("gear_epic" if drop["rarity"] == "史诗"
                                    else "gear_legend" if drop["rarity"] == "传说" else None)
        if random.random() < boss_rate:
            # 遭遇强敌：奖励×倍数，受惊逃窜
            gold = int(gold * boss_mult)
            exp = int(exp * boss_mult)
            self.state = "scared"
            self.state_left = 900
            self.speed = self.base_speed() * 4.0
            self.show_bubble("遭遇强敌！打赢啦！经验+%d 金币+%d" % (exp, gold), 3000)
            self.add_exp(exp)
            self.add_gold(gold)
            self.check_achievements("first_adv" if self.adv_count == 1
                                    else "adv_10" if self.adv_count >= 10 else None)
            return
        self.add_exp(exp)
        self.add_gold(gold)
        self.check_achievements("first_adv" if self.adv_count == 1
                                else "adv_10" if self.adv_count >= 10 else None)
        msg = "冒险归来！经验+%d 金币+%d" % (exp, gold)
        if drop:
            msg += " 掉落：%s·%s（%s）" % (
                drop["name"], drop["rarity"],
                "已入背包" if drop_ok
                else "折现+%d" % SELL_PRICE[drop["rarity"]])
        self.show_bubble(msg, 3600)

    def _boss_fight(self):
        """首领战：噩梦难度专属，受惊逃窜后结算"""
        self.stats["boss"] += 1
        self.weekly["boss"] += 1
        self.state = "scared"
        self.state_left = 1500
        self.speed = self.base_speed() * 5.0
        self.show_bubble("⚠️ 首领出现！大战三百回合！", 2200)
        self._boss_job = self.root.after(2200, self._boss_reward)

    def _boss_reward(self):
        exp = (DIFFS["night"][2] + self.level * 2) * 5
        gold = (random.randint(25, 80) + self.level * 3) * 5
        self.add_exp(exp)
        self.add_gold(gold)
        self.add_mood(10)
        # 保底史诗/传说
        g = self.make_gear("史诗" if random.random() < 0.5 else "传说")
        self._equip_or_sell(g)
        self.check_achievements("gear_epic" if g["rarity"] == "史诗"
                                else "gear_legend" if g["rarity"] == "传说" else None)
        self.check_achievements("boss_1")
        msg = "击败首领！经验+%d 金币+%d" % (exp, gold)
        msg += " 战利品：%s·%s（%s）" % (
            g["name"], g["rarity"],
            "已入背包" if g in self.inventory
            else "折现+%d" % SELL_PRICE[g["rarity"]])
        self.show_bubble(msg, 4000)

    # —— 联手讨伐首领（双宠合作） ——
    def coop_boss(self):
        """联手讨伐首领：双宠合作副本，40% 首领战，双方共享加成"""
        self._stop_follow()
        if self.adventuring or self._coop_partner is not None:
            self.show_bubble("已经在讨伐中啦！", 1600)
            return
        others = [p for p in _PET_INSTANCES
                  if p is not self and p.root.winfo_exists()]
        if not others:
            self.show_bubble("需要第二只宠物联手讨伐！（控制台开启）", 2400)
            return
        o = random.choice(others)
        if o.adventuring or o._coop_partner is not None or \
                o._battle_t > 0 or o._fusion_t > 0 or o.sleeping:
            self.show_bubble("同伴正在忙，等它闲下来再联手", 1800)
            return
        dur = random.randint(8, 12)
        self._coop_partner = o
        self._coop_done = False
        self.adventuring = True
        self._adv_diff = "normal"
        self._adv_job = self.root.after(dur * 1000, self._coop_finish)
        self.state = "scared"
        self.state_left = 0
        self.speed = self.base_speed() * 3.5
        self.show_bubble("联手讨伐开始！%d 秒后凯旋" % dur, 2200)
        o._coop_partner = self
        o._coop_done = False
        o.adventuring = True
        o._adv_diff = "normal"
        o._adv_job = o.root.after(dur * 1000, o._coop_finish)
        o.state = "scared"
        o.state_left = 0
        o.speed = o.base_speed() * 3.5
        o.show_bubble("一起上！", 1600)

    def _coop_finish(self):
        """联手讨伐结算（双方各自结算一次）"""
        if self._coop_done:
            return
        self._coop_done = True
        o = self._coop_partner
        self._coop_partner = None
        self.adventuring = False
        self._adv_job = None
        self.speed = self.base_speed()
        self.adv_count += 1
        self.stats["adv"] += 1
        self.weekly["adv"] += 1
        self._quest_act("adv")
        self.coop_count += 1
        self.check_achievements("coop_10")
        if random.random() < 0.4:
            # 合作首领战：奖励 ×5，保底史诗/传说
            self.stats["boss"] += 1
            self.weekly["boss"] += 1
            exp = (DIFFS["normal"][2] + self.level * 2) * 5
            gold = (random.randint(20, 60) + self.level * 3) * 5
            g = self.make_gear("史诗" if random.random() < 0.5 else "传说")
            ok = self._equip_or_sell(g)
            self.add_exp(exp)
            self.add_gold(gold)
            self.add_mood(10)
            self.check_achievements("first_adv" if self.adv_count == 1
                                    else "adv_10" if self.adv_count >= 10 else None)
            self.check_achievements("gear_epic" if g["rarity"] == "史诗"
                                    else "gear_legend" if g["rarity"] == "传说" else None)
            self.check_achievements("boss_1")
            self.show_bubble("联手讨伐成功！击败首领！经验+%d 金币+%d「%s」%s" % (
                exp, gold, g["name"],
                "已入背包" if ok else "折现+%d" % SELL_PRICE[g["rarity"]]), 4200)
        else:
            # 常规讨伐：合作加成 30%
            gold = random.randint(15, 45) + self.level * 3
            gold = int(gold * 1.3)
            exp = DIFFS["normal"][2] + self.level * 3
            self.add_exp(exp)
            self.add_gold(gold)
            self.check_achievements("first_adv" if self.adv_count == 1
                                    else "adv_10" if self.adv_count >= 10 else None)
            self.show_bubble("联手讨伐归来！经验+%d 金币+%d（合作加成30%%）" % (exp, gold), 3200)
        if o is not None:
            o._coop_done = True
            o._coop_partner = None
            o.adventuring = False
            o._adv_job = None
            o.speed = o.base_speed()

    def _equip_or_sell(self, g):
        """获得装备：进背包（满则折现）；均计入图鉴"""
        self.collect_gear(g)
        if len(self.inventory) < INV_MAX:
            self.inventory.append(g)
            return True
        self.add_gold(SELL_PRICE[g["rarity"]])
        return False

    # —— 竞技场 ——
    def arena_fight(self):
        """竞技场：攻防属性实战，回合制模拟"""
        self._stop_follow()
        if self.arena_cd > 0:
            self.show_bubble("竞技场冷却中（%d 秒）" % (self.arena_cd // 1000), 1800)
            return
        self.arena_cd = ARENA_CD
        my_atk, my_def = self.atk_def()
        o_lv = max(1, self.level + random.randint(-2, 2))
        o_atk = o_lv + random.randint(2, 8)
        o_def = o_lv + random.randint(2, 8)
        my_hp = 50 + self.level * 10
        o_hp = 50 + o_lv * 10
        turns = []
        while my_hp > 0 and o_hp > 0:
            d = max(1, my_atk - int(o_def * 0.6))
            if random.random() < 0.15:
                d *= 2                                # 暴击
            o_hp -= d
            turns.append("你造成 %d 伤害" % d)
            if o_hp <= 0:
                break
            d2 = max(1, o_atk - int(my_def * 0.6))
            if random.random() < 0.15:
                d2 *= 2
            my_hp -= d2
            turns.append("对手造成 %d 伤害" % d2)
        if my_hp > 0:
            gold = 30 + self.level * 3
            exp = 15 + self.level * 2
            self.add_gold(gold)
            self.add_exp(exp)
            self.add_mood(5)
            head = "竞技场胜利！金币+%d 经验+%d" % (gold, exp)
        else:
            exp = 5
            self.add_exp(exp)
            head = "惜败…获得经验+%d" % exp
        summary = "对手 Lv.%d | %s" % (o_lv, "、".join(turns[:6]) +
                                       ("…" if len(turns) > 6 else ""))
        self.show_bubble(head + "\n" + summary, 4200)

    # —— 背包 ——
    def show_inventory(self):
        if not self.inventory:
            self.show_bubble("背包空的…去冒险或商店搞点装备吧！", 2200)
            return
        lines = ["背包 %d/%d" % (len(self.inventory), INV_MAX)]
        for i, g in enumerate(self.inventory[:INV_MAX]):
            lines.append("%d. %s·%s·%s+%d" % (
                i + 1, SLOT_NAME[g["slot"]], g["name"], g["rarity"],
                g.get("upgrade", 0)))
        self.show_bubble("\n".join(lines), 5500)

    def wear_from_inv(self, idx):
        """从背包穿戴：同槽旧装备回背包"""
        if idx < 0 or idx >= len(self.inventory):
            return
        g = self.inventory.pop(idx)
        old = getattr(self, g["slot"])
        if old:
            self.inventory.append(old)
        setattr(self, g["slot"], g)
        self.save_state()
        self.show_bubble("穿上：%s·%s+%d" % (g["name"], g["rarity"],
                                            g.get("upgrade", 0)), 2200)

    def refresh_gear_menu(self):
        """每次右键重建「穿戴装备」子菜单（背包内容动态）"""
        try:
            self.menu.delete("穿戴装备")
        except Exception:
            pass
        sub = tk.Menu(self.menu, tearoff=0)
        if not self.inventory:
            sub.add_command(label="（背包是空的）", command=lambda: None)
        for i, g in enumerate(self.inventory[:INV_MAX]):
            label = "%s·%s·%s+%d" % (SLOT_NAME[g["slot"]], g["name"],
                                      g["rarity"], g.get("upgrade", 0))
            sub.add_command(label=label, command=lambda idx=i: self.wear_from_inv(idx))
        self.menu.add_cascade(label="穿戴装备（背包 %d）" % len(self.inventory), menu=sub)

    # —— 睡眠模式 ——
    def _wake(self):
        if self.sleeping:
            self.sleeping = False
            self.state = "walk"
            self.state_left = 0
            self.speed = self.base_speed()

    def _midnight_bonus(self):
        """午夜 0 点特典：每天 0:00~0:09 随机触发一种变体，一天一次"""
        today = date.today().isoformat()
        if self._midnight_day == today:
            return
        self._midnight_day = today
        v = random.choice(["fortune", "gear", "train", "alchemy", "cheer"])
        if v == "fortune":
            # 财运特典：金币大礼
            self.add_gold(166)
            self.add_mood(5)
            self.show_bubble("【午夜特典·财运】福星高照！金币+166，心情也好了", 4000)
        elif v == "gear":
            # 装备特典：赠精良/史诗装备
            gear = self.make_gear(random.choice(["精良", "史诗"]))
            ok = self._equip_or_sell(gear)
            self.add_gold(66)
            self.add_exp(33)
            self.add_mood(10)
            self.show_bubble(
                "【午夜特典·装备】0 点福星高照！金币+66 经验+33，"
                "「%s」%s！" % (gear["name"],
                              "已入背包" if ok else "折现+%d" % SELL_PRICE[gear["rarity"]]),
                4200)
        elif v == "train":
            # 修炼特典：经验大礼
            self.add_exp(99)
            self.add_gold(66)
            self.show_bubble("【午夜特典·修炼】夜半苦修！经验+99 金币+66", 4000)
        elif v == "alchemy":
            # 炼金特典：精华礼
            self.essence += 30
            self.add_gold(66)
            self.show_bubble("【午夜特典·炼金】炼金炉启动！精华+30 金币+66", 4000)
        else:
            # 心情特典：好心情大礼
            self.add_mood(20)
            self.add_gold(66)
            self.add_hunger(20)
            self.show_bubble("【午夜特典·好心情】元气满满！心情+20 饱腹+20 金币+66", 4000)
        self.save_state()

    # —— 双宠互搏 ——
    def pet_battle(self, auto=False):
        """找同伴打架：双方对冲，按攻防结算（auto=随机游走碰撞自动触发）"""
        if self._battle_t > 0 or self._battle_fight or self._fusion:
            return
        self._stop_follow()
        others = [p for p in _PET_INSTANCES
                  if p is not self and p.root.winfo_exists()]
        if not others:
            if not auto:
                self.show_bubble("没有同伴可以打架…（控制台开启第二只宠物）", 2400)
            return
        if self.battle_cd > 0:
            if not auto:
                self.show_bubble("打架冷却中（%d 秒）" % (self.battle_cd // 1000), 1800)
            return
        self.battle_cd = 60000
        o = random.choice(others)
        o.battle_cd = max(o.battle_cd, 60000)
        self._battle_other = o
        self._battle_t = 3000
        self._battle_owner = True
        self._battle_dmg_taken = 0
        self.state = "scared"
        self.state_left = 0
        self.speed = self.base_speed() * 4.5
        self.show_bubble("我来啦！决斗吧！", 1600)
        o._battle_other = self
        o._battle_t = 3000
        o._battle_owner = False
        o._battle_dmg_taken = 0
        o.state = "scared"
        o.state_left = 0
        o.speed = o.base_speed() * 4.5
        o.show_bubble("放马过来！", 1600)

    def _battle_clash(self):
        """撞上：进入互殴阶段（交替出拳 + 伤害结算）"""
        o = self._battle_other
        for p in (self, o):
            if p is None:
                continue
            p._battle_t = 0
            p._battle_fight = True
            p._battle_fight_t = 2000
            p.state = "spin"
            p.state_left = 0
            p.speed = 0
            p.show_bubble("打起来了！", 1200)
        self._battle_hits = 0
        self._fight_job = self.root.after(320, self._fight_hit)

    def _skill_name_for(self, pid):
        """互搏时按宠物类型触发的专属招式名"""
        return {"cockroach": "铁壳冲撞", "cat": "利爪连击", "dog": "忠犬猛扑",
                "rabbit": "飞踢弹跳", "hamster": "滚球撞击", "corgi": "旋风反击",
                "penguin": "冰锋啄击", "panda": "泰山压顶"}.get(pid, "元气重击")

    def _fight_hit(self):
        """互殴一轮：交替出拳（发起方先手），25% 概率发动专属招式"""
        if not self._battle_fight or self._battle_other is None:
            return
        o = self._battle_other
        self._battle_hits += 1
        if self._battle_hits % 2 == 1:
            attacker, defender = self, o
        else:
            attacker, defender = o, self
        dmg = max(1, attacker.atk_def()[0] - int(defender.atk_def()[1] * 0.6))
        if random.random() < 0.15:
            dmg *= 2
        use_skill = random.random() < 0.25
        if use_skill:
            # 专属招式：额外 +80% 伤害，更长的受击闪光
            dmg += max(1, int(dmg * 0.8))
            defender._battle_dmg_taken += dmg
            defender._fight_hurt = 600
            attacker._fight_punch = 500
            defender.show_bubble("%s！%d 伤害！" % (
                self._skill_name_for(attacker.pet_id), dmg), 900)
        else:
            defender._battle_dmg_taken += dmg
            defender._fight_hurt = 400
            attacker._fight_punch = 300
            defender.show_bubble("唔！%d 伤害" % dmg, 600)
        if self._battle_hits < 8:
            self._fight_job = self.root.after(300, self._fight_hit)
        else:
            self._battle_resolve()

    def _battle_resolve(self, timeout=False):
        """结算（只由发起者执行一次）：按互殴累计伤害判定"""
        o = self._battle_other
        self._battle_other = None
        self._battle_t = 0
        self._battle_owner = False
        self._battle_fight = False
        self._fight_punch = 0
        self._fight_hurt = 0
        if self._fight_job:
            try:
                self.root.after_cancel(self._fight_job)
            except Exception:
                pass
            self._fight_job = None
        if o is not None:
            o._battle_other = None
            o._battle_t = 0
            o._battle_owner = False
            o._battle_fight = False
            o._fight_punch = 0
            o._fight_hurt = 0
            if o._fight_job:
                try:
                    o.root.after_cancel(o._fight_job)
                except Exception:
                    pass
                o._fight_job = None
        if timeout:
            self.show_bubble("没追上…平局收场", 1800)
            return
        my_d, o_d = self._battle_dmg_taken, o._battle_dmg_taken
        if my_d < o_d:
            gold = 20 + self.level * 2
            exp = 10 + self.level * 2
            self.add_gold(gold)
            self.add_exp(exp)
            self.add_mood(5)
            o.add_mood(-5)
            self.win_streak += 1
            self.best_streak = max(self.best_streak, self.win_streak)
            o.win_streak = 0
            if self.win_streak >= 3:
                self.check_achievements("fighter_3")
                self.show_bubble("赢了！金币+%d 经验+%d　【三连胜！格斗大师！】" % (gold, exp), 3200)
            else:
                self.show_bubble("赢了！金币+%d 经验+%d（连胜 %d）" % (gold, exp, self.win_streak), 2600)
            o.show_bubble("呜…输了…", 1800)
        elif my_d > o_d:
            exp = 5
            self.add_exp(exp)
            self.win_streak = 0
            o.win_streak += 1
            if o.win_streak >= 3:
                o.check_achievements("fighter_3")
            self.show_bubble("惜败…经验+%d" % exp, 2000)
            o.show_bubble("哈哈我赢啦！", 1800)
        else:
            self.win_streak = 0
            o.win_streak = 0
            self.show_bubble("势均力敌，平局！", 1800)
            o.show_bubble("势均力敌，平局！", 1800)

    def _battle_tick(self):
        """对冲移动；撞上进入互殴，超时平局"""
        if self._battle_t <= 0:
            if self._battle_other is not None and self._battle_owner:
                self._battle_resolve(timeout=True)
            return
        self._battle_t -= TICK_MS
        o = self._battle_other
        if o is None:
            self._battle_t = 0
            return
        dx, dy = o.x - self.x, o.y - self.y
        dist = math.hypot(dx, dy) or 1
        self.facing = 1 if dx < 0 else 0
        ds = self.speed * TICK_MS / 1000.0
        self.x += dx / dist * ds
        self.y += dy / dist * ds
        if dist < 34:
            if self._battle_owner:
                self._battle_clash()
            else:
                self._battle_t = 0
                if o is not None:
                    o._battle_t = 0

    # —— 合体技：双子风暴 ——
    def fusion_skill(self):
        """双宠合体必杀：冲向屏幕中心合体，金色风暴，双方大奖励"""
        self._stop_follow()
        others = [p for p in _PET_INSTANCES
                  if p is not self and p.root.winfo_exists()]
        if not others:
            self.show_bubble("需要第二只宠物才能合体！（控制台开启）", 2400)
            return
        if self.ult_cd > 0:
            self.show_bubble("大招冷却中（%d 秒）" % (self.ult_cd // 1000), 1800)
            return
        o = random.choice(others)
        b = self.bounds()
        for p in (self, o):
            p.ult_cd = FUSION_CD
            p._fusion = True
            p._fusion_t = FUSION_DUR
            p._fusion_done = False
            p.state = "scared"
            p.state_left = 0
            p.speed = p.base_speed() * 6
            p._fusion_target = ((b.x0 + b.x1) / 2 - p.fw / 2,
                                (b.y0 + b.y1) / 2 - p.fh / 2)
            p.show_bubble("合体技！双子风暴！！", 2200)
        self._fusion_owner = o
        o._fusion_owner = self

    def _fusion_tick(self):
        """合体技：飞向屏幕中心"""
        if self._fusion_t <= 0:
            if self._fusion_done:
                return
            self._fusion_end()
            return
        self._fusion_t -= TICK_MS
        tx, ty = self._fusion_target
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy) or 1
        self.facing = 1 if dx < 0 else 0
        ds = self.speed * TICK_MS / 1000.0
        if dist < ds * 2:
            self.x, self.y = tx, ty
            self.speed = 0
        else:
            self.x += dx / dist * ds
            self.y += dy / dist * ds
        if self._fusion_t <= 0:
            self._fusion_end()

    def _fusion_end(self):
        """合体结算（双方各自只结算一次）"""
        if self._fusion_done:
            return
        self._fusion_done = True
        o = self._fusion_owner
        for p in (self, o):
            if p is None:
                continue
            p._fusion = False
            p._fusion_t = 0
            p._fusion_target = None
            p.state = "walk"
            p.state_left = 0
            p.speed = p.base_speed()
            gold = 150 + p.level * 10
            exp = 80 + p.level * 5
            p.add_gold(gold)
            p.add_exp(exp)
            p.add_mood(10)
            p.fusion_count += 1
            p.check_achievements("fusion_5")
            p.show_bubble("双子风暴！金币+%d 经验+%d" % (gold, exp), 3200)

    # —— 专属技能 ——
    def special_skill_name(self):
        """当前宠物的专属技能名"""
        if self.pet_id == "hamster":
            return "滚球冲击"
        if self.pet_id == "corgi":
            return "短腿旋风"
        return "元气爆发"

    def special_skill(self):
        """专属技能：仓鼠滚球冲击（高速绕屏）/ 柯基短腿旋风（原地旋转）/
        其他宠物元气爆发（高速冲刺）"""
        if self.special_cd > 0:
            self.show_bubble("%s 冷却中…还需 %d 秒" % (
                self.special_skill_name(), self.special_cd // 1000), 1800)
            return
        if self._battle_t > 0 or self._battle_fight or self._fusion_t > 0 \
                or self.adventuring or self.sleeping or self._follow_target is not None \
                or self._fainted:
            self.show_bubble("现在不方便施展！", 1600)
            return
        self.special_cd = SPECIAL_CD
        if self.pet_id == "hamster":
            self.special_kind = "roll"
            self.special_t = 2600
            self.speed = self.base_speed() * 9
            self.state = "walk"
            self.state_left = 0
            self.wrapping = False
            self.show_bubble("滚球冲击！！", 2000)
        elif self.pet_id == "corgi":
            self.special_kind = "spin"
            self.special_t = 1500
            self.state = "spin"
            self.state_left = 1500
            self.speed = 0
            self.show_bubble("短腿旋风！！", 2000)
        else:
            self.special_kind = "boost"
            self.special_t = 1200
            self.speed = self.base_speed() * 5
            self.state = "walk"
            self.state_left = 0
            self.wrapping = False
            self.show_bubble("元气爆发！！", 2000)

    def _special_tick(self):
        """专属技能进行中：倒计时，结束时按星级结算奖励"""
        if self.special_t <= 0:
            return
        self.special_t -= TICK_MS
        if self.special_t <= 0:
            kind = self.special_kind
            self.special_kind = None
            self.state = "walk"
            self.state_left = 0
            self.speed = self.base_speed()
            base_gold, base_exp = SPECIAL_REWARD.get(kind, (0, 0))
            lv = max(1, self.star_level)
            mult = 1 + 0.2 * (lv - 1)          # 星级越高技能越强（最高 ×1.8）
            gold = int(base_gold * mult)
            exp = int(base_exp * mult)
            self.add_gold(gold)
            self.add_exp(exp)
            self.show_bubble("%s Lv.%d！金币+%d 经验+%d" % (
                self.special_skill_name(), lv, gold, exp), 2600)
            self.save_state()

    # —— RPG：强化 ——
    def upgrade_gear(self, slot):
        if self.adventuring:
            self.show_bubble("冒险中，回来再强化！", 1600)
            return
        g = getattr(self, slot)
        if not g:
            self.show_bubble("还没有%s，先去打一件吧！" %
                             {"weapon": "武器", "armor": "防具", "trinket": "饰品"}[slot], 2000)
            return
        lv = g.get("upgrade", 0)
        if lv >= MAX_UPGRADE:
            self.show_bubble("%s 已强化满 +%d！" % (g["name"], MAX_UPGRADE), 1800)
            return
        cost = UPGRADE_COST + lv * 100
        if self.gold < cost:
            self.show_bubble("金币不够（强化需 %d）" % cost, 1800)
            return
        self.gold -= cost
        rate = max(0.2, 0.9 - lv * 0.1)
        if random.random() < rate:
            g["upgrade"] = lv + 1
            msg = "%s 强化成功 +%d！（花费 %d）" % (g["name"], lv + 1, cost)
            if g["upgrade"] == MAX_UPGRADE:
                msg += " 满级金光闪闪！"
        else:
            if lv >= 3:
                g["upgrade"] = lv - 1
                msg = "%s 强化失败…掉回 +%d" % (g["name"], lv - 1)
            else:
                msg = "%s 强化失败（低等级不降级）" % g["name"]
        self.save_state()
        self.show_bubble(msg, 2600)

    # —— RPG：签到 / 成就 ——
    def add_star_exp(self, n):
        """宠物星级经验：喂食/互动累计，满级升星"""
        if self.star_level >= 5:
            return
        self.star_exp += n
        need = STAR_NEEDS.get(self.star_level + 1)
        while need and self.star_exp >= need:
            self.star_exp -= need
            self.star_level += 1
            self.add_gold(50 * self.star_level)
            self.add_mood(10)
            self.show_bubble("升星啦！★×%d 金币+%d" % (self.star_level, 50 * self.star_level), 3200)
            if self.star_level >= 5:
                self.show_bubble("五星满星！传说之兽，所向披靡！", 3600)
                break
            need = STAR_NEEDS.get(self.star_level + 1)
        self.save_state()

    def star_display(self):
        """星级显示：★×N（升星进度）"""
        if self.star_level >= 5:
            return "★×5（满星）"
        need = STAR_NEEDS.get(self.star_level + 1, 1)
        return "★×%d（%d/%d）" % (self.star_level, self.star_exp, need)

    def daily_signin(self, auto=False):
        today = time.strftime("%Y-%m-%d")
        if self.last_signin == today:
            if not auto:
                self.show_bubble("今天已经签过啦！", 1600)
            return
        try:
            last = date.fromisoformat(self.last_signin) if self.last_signin else None
            self.signin_streak = self.signin_streak + 1 if (
                last and (date.today() - last).days == 1) else 1
        except Exception:
            self.signin_streak = 1
        self.last_signin = today
        reward = SIGNIN_BASE + (self.signin_streak - 1) * 5
        self.add_gold(reward)
        if self.signin_streak >= 7:
            self.check_achievements("signin_7")
        f = self.fortune_today()
        self.show_bubble("签到成功！金币+%d（连续 %d 天）今日运势：%s" % (
            reward, self.signin_streak, f), 2600)

    def check_achievements(self, key):
        if not key or key in self.achieves:
            return
        title, reward = ACHIEVEMENTS[key]
        self.achieves.add(key)
        self.add_gold(reward)
        self.show_bubble("成就达成「%s」金币+%d" % (title, reward), 3000)
        self.save_state()

    # —— RPG：商店 / 技能 ——
    def buy_gear(self):
        if self.adventuring:
            self.show_bubble("冒险中，回来再买吧！", 1600)
            return
        if self.gold < SHOP_COST:
            self.show_bubble("金币不够（%d/次），先去冒险吧！" % SHOP_COST, 2200)
            return
        self.gold -= SHOP_COST
        g = self.make_gear(self.roll_rarity(shop=True))
        ok = self._equip_or_sell(g)
        self.check_achievements("gear_epic" if g["rarity"] == "史诗"
                                else "gear_legend" if g["rarity"] == "传说" else None)
        self.save_state()
        self.show_bubble("商店入手：%s·%s（%s）" % (
            g["name"], g["rarity"],
            "已入背包" if ok else "折现+%d" % SELL_PRICE[g["rarity"]]), 2600)

    def use_skill(self):
        if self.level < 2:
            self.show_bubble("达到 Lv.2 解锁「疾跑」", 2000)
            return
        if self.skill_cd > 0:
            self.show_bubble("疾跑冷却中（%d 秒）" % (self.skill_cd // 1000), 1800)
            return
        self.skill_cd = SKILL_CD
        self.speed = self.base_speed() * 2.0
        self._skill_job = self.root.after(SKILL_RUN, self._skill_end)
        self.show_bubble("疾跑发动！速度翻倍 30 秒！", 2200)

    def _skill_end(self):
        self._skill_job = None
        if not self.adventuring:
            self.speed = self.base_speed()

    def enter_dizzy(self):
        self.state = "dizzy"
        self.state_left = 2200
        self.show_bubble(self.lines("dizzy"))

    def lines(self, key):
        """按宠物取台词，缺省回退通用池；好感高时优先亲昵台词"""
        pool = PET_LINES.get(self.pet_id, LINES_FALLBACK)
        arr = pool.get(key) or LINES_FALLBACK.get(key) or ["……"]
        if key == "click" and self.affinity >= 60 and random.random() < 0.3:
            arr = pool.get("greet") or arr
        return random.choice(arr)

    def add_hunger(self, delta):
        self.hunger = max(0, min(100, self.hunger + delta))
        self.save_state()

    def add_affinity(self, delta):
        self.affinity = max(0, min(100, self.affinity + delta))
        self.save_state()

    def add_mood(self, delta):
        self.mood = max(0, min(100, self.mood + delta))
        if self.mood >= 90:
            self.check_achievements("mood_90")
        self.save_state()

    def mood_title(self):
        if self.mood >= 70:
            return "开心"
        if self.mood >= 40:
            return "一般"
        return "低落"

    def title(self):
        for lv, t in TITLES:
            if self.level >= lv:
                return t
        return "新手"

    def display_name(self):
        return self.nickname or self.pet_name

    def rename_pet(self):
        """给它起名字（留空恢复原名）"""
        import tkinter.simpledialog as sd
        name = sd.askstring("给它起名字", "给「%s」起个名字（留空恢复原名）：" % self.pet_name,
                            initialvalue=self.nickname or "")
        if name is None:
            return
        name = name.strip()
        self.nickname = name
        self.save_state()
        self.root.title("桌面宠物 · %s" % self.display_name())
        self.show_bubble("以后我叫「%s」啦！" % (name or self.pet_name), 2200)

    def set_alpha(self, v):
        """窗口透明度（100% / 85% / 70% / 55%）"""
        self.alpha = v
        self.save_state()
        try:
            self.root.wm_attributes("-alpha", v)
        except Exception:
            pass
        self.show_bubble("透明度已设为 %d%%" % int(v * 100), 1800)

    def start_game(self):
        """小游戏：接住食物（鼠标移动托盘，接住+1分，漏掉-1命，30秒限时）"""
        if self._game is not None:
            try:
                self._game.focus_force()
                self._game.lift()
            except Exception:
                pass
            return
        g = tk.Toplevel(self.root)
        g.title("接住食物 · %s" % self.display_name())
        g.geometry("260x340+%d+%d" % (self.x + 60, max(0, self.y - 40)))
        g.attributes("-topmost", True)
        g.configure(bg="#FFF8E7")
        info = tk.Label(g, text="得分 0 | 生命 3 | 剩余 30 秒",
                        bg="#FFF8E7", fg="#5D4037", font=("Microsoft YaHei UI", 11, "bold"))
        info.pack(pady=4)
        c = tk.Canvas(g, width=260, height=290, bg="#FFF8E7", highlightthickness=0)
        c.pack()
        self._game = g
        st = {"score": 0, "lives": 3, "t": 30.0, "foods": [], "pad_x": 130, "over": False}
        c.create_rectangle(0, 272, 260, 292, fill="#8BC34A", outline="")
        pad = c.create_rectangle(102, 262, 158, 284, fill="#E76F51", outline="#5D4037")

        def on_move(ev):
            st["pad_x"] = ev.x
            c.coords(pad, ev.x - 28, 262, ev.x + 28, 284)

        c.bind("<Motion>", on_move)

        def over(reason):
            if st["over"]:
                return
            st["over"] = True
            reward = st["score"] * 10
            self.add_gold(reward)
            self.add_mood(5)
            info.config(text="%s 得分 %d → 金币+%d" % (reason, st["score"], reward))

        def tick():
            if st["over"] or not g.winfo_exists():
                return
            st["t"] -= 0.08
            if st["t"] <= 0:
                over("时间到！")
                g.after(2200, g.destroy)
                self._game = None
                return
            if random.random() < 0.10:
                x = random.randint(18, 242)
                st["foods"].append([x, 0, c.create_oval(x - 8, 0, x + 8, 16,
                                                        fill="#F4A261", outline="#E76F51")])
            for f in list(st["foods"]):
                f[1] += 8
                c.move(f[2], 0, 8)
                if f[1] >= 256 and abs(f[0] - st["pad_x"]) < 30:
                    c.delete(f[2])
                    st["foods"].remove(f)
                    st["score"] += 1
                elif f[1] > 278:
                    c.delete(f[2])
                    st["foods"].remove(f)
                    st["lives"] -= 1
                    if st["lives"] <= 0:
                        over("游戏结束！")
                        g.after(2200, g.destroy)
                        self._game = None
                        return
            info.config(text="得分 %d | 生命 %d | 剩余 %d 秒" % (
                st["score"], st["lives"], max(0, int(st["t"]))))
            g.after(80, tick)

        def on_close():
            self._game = None
            try:
                g.destroy()
            except Exception:
                pass

        g.protocol("WM_DELETE_WINDOW", on_close)
        g.after(80, tick)

    # —— 必杀技：宠物风暴 ——
    def use_ultimate(self):
        if self.level < 10:
            self.show_bubble("达到 Lv.10 解锁必杀技「宠物风暴」", 2200)
            return
        if self.ult_cd > 0:
            m, s = divmod(self.ult_cd // 1000, 60)
            self.show_bubble("必杀技冷却中（%d 分 %d 秒）" % (m, s), 2000)
            return
        self.ult_cd = ULT_CD
        self.ulting = True
        self.state = "walk"
        self.state_left = 0
        self.speed = self.base_speed() * 6.0
        self.show_bubble("必杀技·宠物风暴！！", 1800)
        self._ult_job = self.root.after(ULT_DUR, self._ult_end)

    def _ult_end(self):
        self.ulting = False
        self.speed = self.base_speed()
        gold = 100 + self.level * 5
        exp = 50 + self.level * 3
        self.add_gold(gold)
        self.add_exp(exp)
        self.add_mood(10)
        self.show_bubble("风暴平息！金币+%d 经验+%d" % (gold, exp), 3000)

    # —— 小游戏：点泡泡 ——
    def start_pop_game(self):
        if self._pop_mode:
            return
        self._pop_mode = True
        self._pop_score = 0
        self._pop_t0 = time.monotonic()
        self._pop_bubbles = []
        self.root.bind("<Button-1>", self._pop_click, add="+")
        self.show_bubble("点泡泡！30 秒，每分 +5 金币！", 2000)
        self._pop_job = self.root.after(30000, self._pop_end)

    def _pop_click(self, event):
        if not self._pop_mode:
            return
        x, y = event.x, event.y
        for b in list(self._pop_bubbles):
            if (x - b[0]) ** 2 + (y - b[1]) ** 2 <= (b[2] + 6) ** 2:
                self._pop_bubbles.remove(b)
                self._pop_score += 1
                return

    def _pop_end(self):
        self._pop_mode = False
        self._pop_bubbles = []
        try:
            self.root.unbind("<Button-1>")
        except Exception:
            pass
        reward = self._pop_score * 5
        if reward > 0:
            self.add_gold(reward)
            self.add_mood(5)
            self.show_bubble("泡泡结束！%d 分 → 金币+%d" % (self._pop_score, reward), 2500)
        else:
            self.show_bubble("一个都没点到…再来一次？", 2000)

    # —— 小游戏：猜盒子 ——
    def start_box_game(self):
        """猜盒子：三盒一食，猜中 +15 金币，猜错 +5 安慰"""
        if self._box_game is not None:
            try:
                self._box_game.destroy()
            except Exception:
                pass
        top = tk.Toplevel(self.root)
        self._box_game = top
        top.title("猜盒子")
        top.attributes("-topmost", True)
        top.configure(bg="#FFF8E7")
        c = tk.Canvas(top, width=320, height=170, bg="#FFF8E7", highlightthickness=0)
        c.pack(padx=10, pady=(10, 0))
        info = tk.Label(top, text="看好了，食物藏在哪个盒子里？",
                        font=("Microsoft YaHei UI", 10), bg="#FFF8E7")
        info.pack(pady=(2, 0))
        btns = tk.Frame(top, bg="#FFF8E7")
        btns.pack(pady=6)
        boxes = [(60, 95), (160, 95), (260, 95)]   # 盒子中心
        st = {"ans": random.randrange(3), "reveal": True, "over": False}
        btn_list = []

        def draw(reveal, show_ans=False):
            c.delete("all")
            for i, (bx, by) in enumerate(boxes):
                c.create_rectangle(bx - 30, by - 42, bx + 30, by + 42,
                                   fill="#F4A261", outline="#E76F51", width=2)
                c.create_rectangle(bx - 24, by + 30, bx + 24, by + 44,
                                   fill="#E9C46A", outline="")
                c.create_arc(bx - 20, by - 42, bx + 20, by - 24,
                             start=0, extent=180, fill="#F4A261", outline="")
                if (reveal or show_ans) and i == st["ans"]:
                    c.create_oval(bx - 8, by - 14, bx + 8, by + 2,
                                  fill="#FF6B6B", outline="")
                    c.create_line(bx - 4, by - 7, bx + 4, by - 7,
                                  fill="#FFD93D", width=2)
                    c.create_polygon(bx - 4, by - 7, bx - 7, by - 2,
                                     bx - 1, by - 5, fill="#FFD93D")

        def hide():
            st["reveal"] = False
            draw(False)
            info.configure(text="食物藏起来了…点你猜的盒子！")
            for b in btn_list:
                b.configure(state="normal")

        def guess(i):
            if st["reveal"] or st["over"]:
                return
            st["over"] = True
            for b in btn_list:
                b.configure(state="disabled")
            if i == st["ans"]:
                self.add_gold(15)
                self.show_bubble("猜盒子：猜中啦！金币+15", 2000)
                info.configure(text="猜对啦！金币+15")
            else:
                self.add_gold(5)
                self.show_bubble("猜盒子：猜错啦…金币+5 安慰", 2000)
                draw(False, show_ans=True)
                info.configure(text="猜错啦，答案在 %d 号盒子…金币+5 安慰" % (st["ans"] + 1))

        def again():
            st["ans"] = random.randrange(3)
            st["reveal"] = True
            st["over"] = False
            draw(True)
            info.configure(text="看好了，食物藏在哪个盒子里？")
            for b in btn_list:
                b.configure(state="disabled")
            self._box_game.after(900, hide)

        for i in range(3):
            b = tk.Button(btns, text="盒子 %d" % (i + 1),
                          font=("Microsoft YaHei UI", 10), width=8, state="disabled",
                          command=lambda k=i: guess(k))
            b.pack(side="left", padx=6)
            btn_list.append(b)
        tk.Button(top, text="再来一局", font=("Microsoft YaHei UI", 10), width=10,
                  command=again).pack(pady=(0, 8))
        draw(True)
        top.after(900, hide)

    # —— 小游戏：打地鼠 ——
    def start_whack_game(self):
        """打地鼠：3×3 洞口随机冒头，30 秒限时，每只 +6 金币"""
        if self._whack_game is not None:
            try:
                self._whack_game.destroy()
            except Exception:
                pass
        top = tk.Toplevel(self.root)
        self._whack_game = top
        top.title("打地鼠")
        top.attributes("-topmost", True)
        top.configure(bg="#EFEBE4")
        c = tk.Canvas(top, width=300, height=300, bg="#EFEBE4", highlightthickness=0)
        c.pack(padx=10, pady=(10, 0))
        info = tk.Label(top, text="", font=("Microsoft YaHei UI", 10), bg="#EFEBE4")
        info.pack(pady=(2, 6))
        holes = [(50, 50), (150, 50), (250, 50),
                 (50, 150), (150, 150), (250, 150),
                 (50, 250), (150, 250), (250, 250)]
        st = {"score": 0, "t": 30.0, "over": False, "mole": None, "flash": 0}

        def draw():
            c.delete("all")
            for i, (hx, hy) in enumerate(holes):
                c.create_oval(hx - 26, hy - 14, hx + 26, hy + 22,
                              fill="#8D6E63", outline="#5D4037", width=2)
                if i == st["mole"]:
                    # 地鼠冒头
                    c.create_oval(hx - 20, hy - 34, hx + 20, hy + 2,
                                  fill="#A1887F", outline="#5D4037", width=2)
                    c.create_oval(hx - 11, hy - 22, hx - 5, hy - 16,
                                  fill="#3E2723", outline="")
                    c.create_oval(hx + 5, hy - 22, hx + 11, hy - 16,
                                  fill="#3E2723", outline="")
                    c.create_oval(hx - 3, hy - 12, hx + 3, hy - 8,
                                  fill="#3E2723", outline="")
            if st["flash"] > 0:
                hx, hy = holes[st["flash"] - 1]
                c.create_oval(hx - 32, hy - 40, hx + 32, hy + 30,
                              outline="#FFD93D", width=5)

        def spawn():
            if st["over"]:
                return
            st["mole"] = random.randrange(9)
            draw()
            top.after(650, despawn)

        def despawn():
            if st["over"]:
                return
            st["mole"] = None
            draw()
            if not st["over"]:
                top.after(450, spawn)

        def click(e):
            if st["over"] or st["mole"] is None:
                return
            hx, hy = holes[st["mole"]]
            if (e.x - hx) ** 2 + (e.y - hy) ** 2 <= 45 ** 2:
                st["score"] += 1
                st["flash"] = st["mole"] + 1
                st["mole"] = None
                draw()
                top.after(160, lambda: (st.__setitem__("flash", 0), draw()))
                top.after(320, spawn)

        def tick():
            if st["over"]:
                return
            st["t"] -= 0.1
            info.configure(text="得分 %d　·　剩余 %.1f 秒（点中 +6 金币）" % (st["score"], st["t"]))
            if st["t"] <= 0:
                st["over"] = True
                info.configure(text="时间到！得分 %d" % st["score"])
                st["mole"] = None
                draw()
                reward = st["score"] * 6
                if reward > 0:
                    self.add_gold(reward)
                    self.add_mood(5)
                    self.show_bubble("打地鼠：%d 只，金币+%d" % (st["score"], reward), 2600)
                else:
                    self.show_bubble("打地鼠：一只都没打到…", 1800)
                return
            top.after(100, tick)

        c.bind("<Button-1>", click)
        info.configure(text="打地鼠！点中 +6 金币")
        spawn()
        tick()

    # —— 小游戏：猜点数（骰子） ——
    def start_dice_game(self):
        """猜点数：押大/小/单/双，10 金币参与，猜中 +25"""
        if getattr(self, "_dice_game", None) is not None:
            try:
                self._dice_game.destroy()
            except Exception:
                pass
        if self.gold < DICE_COST:
            self.show_bubble("金币不够（猜点数需 %d）" % DICE_COST, 2000)
            return
        top = tk.Toplevel(self.root)
        self._dice_game = top
        top.title("猜点数")
        top.attributes("-topmost", True)
        top.configure(bg="#F7F5F0")
        c = tk.Canvas(top, width=120, height=120, bg="#FFFFFF",
                      highlightthickness=0, bd=2, relief="ridge")
        self._dice_canvas = c
        c.pack(padx=12, pady=(10, 6))
        info = tk.Label(top, text="押大/小/单/双（参与 10 金币，猜中 +25）",
                        font=("Microsoft YaHei UI", 10), bg="#F7F5F0")
        self._dice_info = info
        info.pack(pady=(0, 4))
        bar = tk.Frame(top, bg="#F7F5F0")
        bar.pack(pady=(0, 10))
        st = {"roll": 5, "busy": False, "bet": None}
        for label, bet in (("大", "big"), ("小", "small"), ("单", "odd"), ("双", "even")):
            tk.Button(bar, text=label, width=5,
                      command=lambda b=bet: self._dice_roll(top, c, info, st, b)
                      ).pack(side="left", padx=4)

        def draw():
            c.delete("all")
            v = st["roll"]
            cx0, cy0, S = 60, 60, 26
            pips = {1: [(0, 0)], 2: [(-1, -1), (1, 1)], 3: [(-1, -1), (0, 0), (1, 1)],
                    4: [(-1, -1), (1, -1), (-1, 1), (1, 1)],
                    5: [(-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)],
                    6: [(-1, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1)]}
            for (dx, dy) in pips.get(v, [(0, 0)]):
                c.create_oval(cx0 + dx * S - 6, cy0 + dy * S - 6,
                              cx0 + dx * S + 6, cy0 + dy * S + 6,
                              fill="#3A3A3A", outline="")

        draw()

    def _dice_roll(self, top, c, info, st, bet):
        """投骰动画 + 结算"""
        if st["busy"]:
            return
        if self.gold < DICE_COST:
            self.show_bubble("金币不够啦！", 1800)
            return
        st["busy"] = True
        st["bet"] = bet
        self.gold -= DICE_COST
        self.save_state()
        info.configure(text="投骰中…")
        seq = [random.randint(1, 6) for _ in range(8)]

        def draw(v):
            c.delete("all")
            cx0, cy0, S = 60, 60, 26
            pips = {1: [(0, 0)], 2: [(-1, -1), (1, 1)], 3: [(-1, -1), (0, 0), (1, 1)],
                    4: [(-1, -1), (1, -1), (-1, 1), (1, 1)],
                    5: [(-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)],
                    6: [(-1, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1)]}
            for (dx, dy) in pips.get(v, [(0, 0)]):
                c.create_oval(cx0 + dx * S - 6, cy0 + dy * S - 6,
                              cx0 + dx * S + 6, cy0 + dy * S + 6,
                              fill="#3A3A3A", outline="")

        def anim(i):
            if i < len(seq):
                draw(seq[i])
                top.after(90, lambda: anim(i + 1))
            else:
                settle(seq[-1])

        def settle(val):
            st["busy"] = False
            big = val >= 4
            odd = val % 2 == 1
            b = st["bet"]
            win = ((b == "big" and big) or (b == "small" and not big) or
                   (b == "odd" and odd) or (b == "even" and not odd))
            if win:
                self.add_gold(DICE_WIN)
                self.show_bubble("猜中啦！点数 %d，金币+%d" % (val, DICE_WIN), 2200)
                info.configure(text="点数 %d，猜中了！+%d（再来一局？）" % (val, DICE_WIN))
            else:
                self.show_bubble("点数 %d，猜错啦…" % val, 1600)
                info.configure(text="点数 %d，没中（再来一局？）" % val)

        anim(0)

    # —— 小游戏：石头剪刀布 ——
    def start_rps_game(self):
        """石头剪刀布：赢 +30 / 平 +10 / 输 +5 安慰"""
        if getattr(self, "_rps_game", None) is not None:
            try:
                self._rps_game.destroy()
            except Exception:
                pass
        top = tk.Toplevel(self.root)
        self._rps_game = top
        top.title("石头剪刀布")
        top.attributes("-topmost", True)
        top.configure(bg="#F7F5F0")
        tk.Label(top, text="和宠物一决胜负！（赢 +30 / 平 +10 / 输 +5）",
                 font=("Microsoft YaHei UI", 10), bg="#F7F5F0").pack(pady=(10, 2))
        c = tk.Canvas(top, width=240, height=90, bg="#FFFFFF",
                      highlightthickness=0, bd=2, relief="ridge")
        c.pack(padx=12, pady=6)
        info = tk.Label(top, text="请出招", font=("Microsoft YaHei UI", 10, "bold"),
                        bg="#F7F5F0", fg="#C0392B")
        info.pack(pady=(0, 4))
        bar = tk.Frame(top, bg="#F7F5F0")
        bar.pack(pady=(0, 10))

        def draw_pet(choice):
            c.delete("all")
            c.create_text(60, 45, text="宠物出：", font=("Microsoft YaHei UI", 11))
            c.create_text(200, 45, text=choice, font=("Microsoft YaHei UI", 16, "bold"),
                          fill="#C0392B")

        def play(me):
            pet = random.choice(["石头", "剪刀", "布"])
            draw_pet(pet)
            if me == pet:
                rlt, gold = "平局！", 10
            elif ((me == "石头" and pet == "剪刀") or
                  (me == "剪刀" and pet == "布") or
                  (me == "布" and pet == "石头")):
                rlt, gold = "你赢了！", 30
            else:
                rlt, gold = "宠物赢了！", 5
            self.add_gold(gold)
            self.show_bubble("石头剪刀布：%s 金币+%d" % (rlt, gold), 2400)
            info.configure(text="你出%s，宠物出%s → %s（金币+%d）" % (me, pet, rlt, gold))

        for label in ("石头", "剪刀", "布"):
            tk.Button(bar, text=label, width=5,
                      command=lambda x=label: play(x)).pack(side="left", padx=4)

    # —— 全局热键：Ctrl+F8 切换跟随队形 ——
    def _install_hotkey_once(self):
        """全局热键（RegisterHotKey 系统热键机制）：Ctrl+F8 在跟随模式下
        一键切换队形（排成一列 <-> 并排走）。只用系统热键消息，不安装任何
        键盘钩子，绝不拦截或延迟其他程序的键盘输入；全程序只装一次。"""
        if CockroachPet._hk_installed:
            return
        CockroachPet._hk_installed = True
        try:
            import threading
            user32 = ctypes.windll.user32
            hk_id = 0x4658   # 自定义热键 ID
            # MOD_CONTROL=0x2, MOD_NOREPEAT=0x4000；先试 Ctrl+F8，被占用则退而求其次只注册 F8
            ok = user32.RegisterHotKey(None, hk_id, 0x0002 | 0x4000, 0x77)
            if not ok:
                ok = user32.RegisterHotKey(None, hk_id, 0x4000, 0x77)
            if not ok:
                print("热键注册失败（可能被其他程序占用），队形切换改用右键菜单", file=sys.stderr)
                return

            def toggle_form():
                """主线程执行：切换所有处于跟随模式的宠物的队形"""
                for p in _PET_INSTANCES:
                    if p._follow_target is not None:
                        p._follow_form = ("line" if p._follow_form == "side"
                                          else "side")
                        p.show_bubble("队形切换：%s" % (
                            "排成一列" if p._follow_form == "line"
                            else "并排走"), 1200)

            class _MSG(ctypes.Structure):
                _fields_ = [("hwnd", ctypes.c_void_p), ("message", ctypes.c_uint),
                            ("wParam", ctypes.c_size_t), ("lParam", ctypes.c_ssize_t),
                            ("time", ctypes.c_uint), ("pt", ctypes.c_long * 2)]

            def pump():
                """独立线程收 WM_HOTKEY（0x0312），调度到 tk 主线程执行"""
                msg = _MSG()
                while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                    if msg.message == 0x0312 and msg.wParam == hk_id:
                        try:
                            self.root.after(0, toggle_form)
                        except Exception:
                            pass
                try:
                    user32.UnregisterHotKey(None, hk_id)
                except Exception:
                    pass

            threading.Thread(target=pump, daemon=True).start()
        except Exception as e:
            print("热键安装失败：%s" % e, file=sys.stderr)
            CockroachPet._hk_installed = False

    # —— 装备图鉴 ——
    def collect_gear(self, g):
        self.collected.add(g["name"])
        if len(self.collected) >= 15:
            self.check_achievements("collect_15")
        self.save_state()

    def show_collection(self):
        total = sum(len(v) for v in GEAR_POOL.values())
        lines = ["装备图鉴 %d/%d" % (len(self.collected), total)]
        for slot, label in (("weapon", "武器"), ("armor", "防具"), ("trinket", "饰品")):
            have = [n for n in GEAR_POOL[slot] if n in self.collected]
            lines.append("%s %d/%d" % (label, len(have), len(GEAR_POOL[slot])))
        have_all = [n for n in sum(GEAR_POOL.values(), []) if n in self.collected]
        if have_all:
            lines.append("已收集：" + "、".join(have_all[:7]) +
                         ("…" if len(have_all) > 7 else ""))
        self.show_bubble("\n".join(lines), 5000)

    # —— 宠物图鉴 ——
    def show_pokedex(self):
        """宠物图鉴：全部宠物立绘 + 解锁状态/条件 + 皮肤预览（含未解锁）"""
        if getattr(self, "_pokedex", None) is not None:
            try:
                self._pokedex.destroy()
            except Exception:
                pass
        lib = load_pet_library()
        unlocked = get_unlocked_pets()
        top = tk.Toplevel(self.root)
        self._pokedex = top
        top.title("宠物图鉴 · %d/%d" % (len(unlocked), len(lib)))
        top.attributes("-topmost", True)
        top.configure(bg="#FDFCF8")

        cols = 3
        cell_w, cell_h = 190, 170
        pad = 10
        grid = tk.Frame(top, bg="#FDFCF8")
        grid.pack(padx=12, pady=(10, 4))
        from PIL import Image as _PILImage, ImageTk as _PILTk
        for i, (pid, info) in enumerate(lib.items()):
            cell = tk.Frame(grid, bg="#FFFFFF", bd=1, relief="ridge",
                            width=cell_w, height=cell_h)
            cell.grid(row=i // cols, column=i % cols, padx=pad, pady=pad)
            cell.grid_propagate(False)
            # 立绘：优先透明帧，回退显示帧
            img = None
            for cand in (os.path.join(script_dir(), "sprites", pid, "default", "walk_1.png"),
                         os.path.join(script_dir(), "sprites_display", pid, "default", "walk_1.png")):
                if os.path.exists(cand):
                    try:
                        pil = _PILImage.open(cand).convert("RGBA")
                        pil.thumbnail((92, 92), _PILImage.LANCZOS)
                        img = _PILTk.PhotoImage(pil)
                    except Exception:
                        img = None
                    break
            if img:
                lbl = tk.Label(cell, image=img, bg="#FFFFFF")
                lbl.image = img
                lbl.pack(pady=(6, 0))
            tk.Label(cell, text=info.get("name", pid),
                     font=("Microsoft YaHei UI", 11, "bold"), bg="#FFFFFF",
                     fg="#1A1B1C").pack(pady=(2, 0))
            if pid in unlocked:
                nsk = len(info.get("skins", []))
                tk.Label(cell, text="已拥有 · %d 款皮肤" % nsk,
                         font=("Microsoft YaHei UI", 9), bg="#FFFFFF",
                         fg="#27AE60").pack()
            else:
                price = int(info.get("unlock", 0))
                if price > 0:
                    need_ach = info.get("achieve")
                    cond = "需 %d 金币" % price
                    if need_ach:
                        cond += " + 「%s」" % ACHIEVEMENTS.get(need_ach, (need_ach,))[0]
                    tk.Label(cell, text="未解锁 · " + cond,
                             font=("Microsoft YaHei UI", 9), bg="#FFFFFF",
                             fg="#C0392B", wraplength=170).pack(padx=6)
                else:
                    tk.Label(cell, text="未解锁", font=("Microsoft YaHei UI", 9),
                             bg="#FFFFFF", fg="#C0392B").pack()
            tk.Label(cell, text="皮肤：" + " / ".join(
                s.get("name", s["id"]) for s in info.get("skins", [])),
                font=("Microsoft YaHei UI", 8), bg="#FFFFFF", fg="#6B7280",
                wraplength=175).pack(padx=6, pady=(0, 4))
            if pid == "hamster" or pid == "corgi":
                tk.Label(cell, text="专属技：" + self._skill_name_for(pid),
                         font=("Microsoft YaHei UI", 8), bg="#FFFFFF",
                         fg="#C07B2B").pack(padx=6, pady=(0, 4))
        tk.Label(top, text="控制台里选中 🔒 的宠物 → 点「解锁」按钮购买",
                 font=("Microsoft YaHei UI", 9), bg="#FDFCF8", fg="#9AA0A6"
                 ).pack(pady=(0, 8))

    # —— 每日运势 ——
    def fortune_today(self):
        if self.fortune.get("date") != time.strftime("%Y-%m-%d"):
            self.fortune = {"date": time.strftime("%Y-%m-%d"),
                            "val": random.choice([f[0] for f in FORTUNES])}
            self.save_state()
        return self.fortune["val"]

    def fortune_mult(self):
        for name, mult in FORTUNES:
            if self.fortune_today() == name:
                return mult
        return 1.0

    # —— 分解 / 合成 ——
    def dismantle(self, slot):
        """分解装备：按稀有度换精华"""
        g = getattr(self, slot)
        if not g:
            self.show_bubble("没有可分解的%s" %
                             {"weapon": "武器", "armor": "防具", "trinket": "饰品"}[slot], 1800)
            return
        e = ESSENCE_BY_RARITY[g["rarity"]]
        self.essence += e
        setattr(self, slot, None)
        self.save_state()
        self.show_bubble("分解了「%s」获得精华 +%d（现有 %d）" % (g["name"], e, self.essence), 2400)

    def synthesize(self):
        """合成装备：50 精华随机精良以上"""
        if self.essence < SYNTH_COST:
            self.show_bubble("精华不够（%d/次），分解装备可得精华" % SYNTH_COST, 2000)
            return
        self.essence -= SYNTH_COST
        r = random.random()
        acc = 0
        rarity = "精良"
        for name, prob in SYNTH_RATES:
            acc += prob
            if r < acc:
                rarity = name
                break
        g = self.make_gear(rarity)
        ok = self._equip_or_sell(g)
        self.save_state()
        self.show_bubble("合成！%s·%s（%s）" % (
            g["name"], g["rarity"],
            "已入背包" if ok else "折现+%d" % SELL_PRICE[g["rarity"]]), 2600)

    def recast(self, slot):
        """重铸装备：30 精华随机更换套装主题（稀有度/强化保留）"""
        g = getattr(self, slot)
        if not g:
            self.show_bubble("没有可重铸的%s" % SLOT_NAME[slot], 1800)
            return
        if self.essence < RECAST_COST:
            self.show_bubble("精华不够（重铸需 %d）" % RECAST_COST, 2000)
            return
        self.essence -= RECAST_COST
        pool = [s for s in SET_POOL if s != g["set"]]
        new_set = random.choice(pool if pool else SET_POOL)
        g["set"] = new_set
        self.save_state()
        self.show_bubble("重铸完成：「%s」→ 主题「%s」" % (g["name"], new_set), 2200)

    def unequip(self, slot):
        """一键卸下：装备回背包（背包满则折现）"""
        g = getattr(self, slot)
        if not g:
            self.show_bubble("没有穿戴的%s" % SLOT_NAME[slot], 1800)
            return
        if len(self.inventory) < INV_MAX:
            self.inventory.append(g)
            setattr(self, slot, None)
            self.save_state()
            self.show_bubble("已卸下「%s」→ 回背包" % g["name"], 2000)
        else:
            price = SELL_PRICE[g["rarity"]]
            setattr(self, slot, None)
            self.add_gold(price)
            self.save_state()
            self.show_bubble("背包满了，「%s」折现 +%d 金币" % (g["name"], price), 2200)

    # —— 成就勋章 ——
    def wear_badge(self, key):
        if key and key not in self.achieves:
            self.show_bubble("还没达成这个成就哦！", 1800)
            return
        self.badge = key
        self.save_state()
        if key:
            self.show_bubble("已佩戴勋章「%s」！" % ACHIEVEMENTS[key][0], 2000)
        else:
            self.show_bubble("已取下勋章", 1500)

    # —— 奇遇事件 ——
    def encounter_event(self):
        text, effect = random.choice(ENCOUNTERS)
        if effect == "gold":
            n = random.randint(10, 30)
            self.add_gold(n)
            text = "奇遇：%s 金币+%d" % (text, n)
        elif effect == "mood":
            self.add_mood(8)
            text = "奇遇：%s 心情+8" % text
        elif effect == "exp":
            n = random.randint(10, 25)
            self.add_exp(n)
            text = "奇遇：%s 经验+%d" % (text, n)
        elif effect == "gear":
            g = self.make_gear("精良")
            ok = self._equip_or_sell(g)
            text = "奇遇：%s 获得 %s·%s（%s）" % (
                text, g["name"], g["rarity"],
                "已入背包" if ok else "折现+%d" % SELL_PRICE[g["rarity"]])
        else:
            self.add_mood(-5)
            text = "奇遇：%s 心情-5" % text
        self.show_bubble(text, 2600)

    def show_log(self):
        """宠物日志：陪伴统计"""
        sec = self.uptime_ms // 1000
        hh, mm = divmod(sec // 60, 60)
        lines = ["%s 的陪伴日志" % self.display_name(),
                 "相伴 %d 小时 %d 分" % (hh, mm),
                 "喂食 %d 次 | 摸摸 %d 次 | 逗玩 %d 次" % (
                     self.stats["feed"], self.stats["pet"], self.stats["play"]),
                 "点击互动 %d 次 | 冒险 %d 次（首领 %d）" % (
                     self.stats["click"], self.stats["adv"], self.stats["boss"]),
                 "饿晕 %d 次 | 达成成就 %d 项" % (self.stats["faint"], len(self.achieves))]
        self.show_bubble("\n".join(lines), 5000)

    def show_weekly(self):
        """宠物周报：本周数据"""
        w = self.weekly
        days = self.uptime_ms // 86400000
        lines = ["%s 本周周报" % self.display_name(),
                 "金币 +%d | 经验 +%d" % (w.get("gold", 0), w.get("exp", 0)),
                 "冒险 %d 次 | 首领 %d 次" % (w.get("adv", 0), w.get("boss", 0)),
                 "喂食 %d 次 | 互动 %d 次" % (w.get("feed", 0), w.get("interact", 0)),
                 "相伴 %d 天 %d 小时" % (
                     days, (self.uptime_ms // 3600000) % 24)]
        self.show_bubble("\n".join(lines), 4500)

    def affinity_level(self):
        for th, name in AFFINITY_LEVELS:
            if self.affinity >= th:
                return name
        return "陌生"

    def load_state(self):
        try:
            with open(os.path.join(script_dir(), STATE_PATH), "r", encoding="utf-8") as f:
                d = json.load(f)
            s = d.get(self.pet_id, {})
        except Exception:
            s = {}
        return (int(s.get("hunger", 80)), int(s.get("affinity", 0)),
                int(s.get("level", 1)), int(s.get("exp", 0)), int(s.get("gold", 0)),
                s.get("weapon"), s.get("armor"), s.get("trinket"),
                int(s.get("adv_count", 0)), int(s.get("total_gold", 0)),
                set(s.get("achieves", [])),
                s.get("last_signin", ""), int(s.get("signin_streak", 0)),
                s.get("quest") or {"date": "", "adv": 0, "interact": 0, "done": []},
                s.get("mood", 70),
                s.get("stats") or {"feed": 0, "pet": 0, "play": 0, "click": 0,
                                   "adv": 0, "boss": 0, "faint": 0},
                int(s.get("uptime_ms", 0)),
                s.get("nickname", ""), float(s.get("alpha", 1.0)),
                set(s.get("collected", [])),
                s.get("fortune") or {"date": "", "val": "中"},
                int(s.get("essence", 0)), s.get("badge", ""),
                s.get("inventory") or [],
                s.get("weekly") or {"week": "", "gold": 0, "exp": 0,
                                    "adv": 0, "boss": 0, "feed": 0, "interact": 0},
                int(s.get("no_feed_streak", 0)),
                bool(s.get("no_feed_egg", False)),
                int(s.get("fusion_count", 0)),
                str(s.get("midnight_day", "")),
                int(s.get("win_streak", 0)),
                int(s.get("best_streak", 0)),
                int(s.get("coop_count", 0)),
                int(s.get("star_level", 1)),
                int(s.get("star_exp", 0)))

    def save_state(self):
        try:
            path = os.path.join(script_dir(), STATE_PATH)
            d = {}
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    d = json.load(f)
            d[self.pet_id] = {"hunger": self.hunger, "affinity": self.affinity,
                              "level": self.level, "exp": self.exp, "gold": self.gold,
                              "weapon": self.weapon, "armor": self.armor,
                              "trinket": self.trinket,
                              "adv_count": self.adv_count,
                              "total_gold": self.total_gold,
                              "achieves": sorted(self.achieves),
                              "last_signin": self.last_signin,
                              "signin_streak": self.signin_streak,
                              "quest": self.quest,
                              "mood": self.mood, "stats": self.stats,
                              "uptime_ms": self.uptime_ms,
                              "nickname": self.nickname, "alpha": self.alpha,
                              "collected": sorted(self.collected),
                              "fortune": self.fortune,
                              "essence": self.essence, "badge": self.badge,
                              "inventory": self.inventory,
                              "weekly": self.weekly,
                              "no_feed_streak": self.no_feed_streak,
                              "no_feed_egg": self._no_feed_egg,
                              "fusion_count": self.fusion_count,
                              "midnight_day": self._midnight_day,
                              "win_streak": self.win_streak,
                              "best_streak": self.best_streak,
                              "coop_count": self.coop_count,
                              "star_level": self.star_level,
                              "star_exp": self.star_exp}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_cursor(self):
        pt = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def update_glow(self):
        """可视化层：天气 / 心情光效 / 装备光环+武器+饰品 / 彩虹 / 必杀 / 泡泡 / 烟花"""
        try:
            c = self._glow
            c.delete("all")
            self._glow_phase += 1
            self._draw_weather(c)
            # 心情光效：开心冒小心心 / 低落冒灰云
            if not self.ulting and not self._pop_mode:
                if self.mood >= 70:
                    ph = self._glow_phase
                    for k in range(2):
                        bx = self.fw / 2 + int(math.sin(ph * 0.05 + k * 2.1) * 8) \
                             + (k - 1) * 18
                        by = 4 + ((ph * 0.6 + k * 17) % 24)
                        _draw_heart(c, bx, by, 5, "#FF8FAB")
                elif self.mood < 30:
                    bx = self.fw / 2 + int(math.sin(self._glow_phase * 0.05) * 6)
                    by = 6
                    c.create_oval(bx - 10, by + 3, bx + 10, by + 8,
                                  fill="#90A4AE", outline="")
                    c.create_oval(bx - 8, by, bx + 8, by + 6,
                                  fill="#B0BEC5", outline="")
                    c.create_oval(bx - 4, by - 4, bx + 4, by + 2,
                                  fill="#CFD8DC", outline="")
            # 成就特效：≥8 头顶星光 / 12 全达成金色粒子
            if not self.ulting:
                n_ach = len(self.achieves)
                if n_ach >= 8:
                    ph = self._glow_phase
                    for k in range(2):
                        sx = self.fw / 2 + int(math.sin(ph * 0.06 + k * 3.14) * 10) \
                             + (k - 1) * 22
                        sy = 5 + ((ph * 0.9 + k * 23) % 26)
                        c.create_polygon(
                            _star_points(sx, sy, 5, 2),
                            fill="#FFD93D" if (ph // 8 + k) % 2 else "#FF9F43",
                            outline="")
                if n_ach >= len(ACHIEVEMENTS):
                    fcx, fcy = self.fw / 2.0, BUBBLE_MARGIN + self.fh / 2.0
                    for k in range(5):
                        ang = (ph * 0.06 + k * 1.256) % 6.283
                        dist = 34 + int(math.sin(ph * 0.05 + k) * 6)
                        px = fcx + math.cos(ang) * dist
                        py = fcy + math.sin(ang) * dist
                        c.create_oval(px - 2.5, py - 2.5, px + 2.5, py + 2.5,
                                      fill="#FFD93D", outline="")
            gear = [g for g in (self.weapon, self.armor, self.trinket) if g]
            if gear:
                top = max(gear, key=lambda g: RARITY_ORDER.index(g["rarity"]))
                color = RARITY_COLOR[top["rarity"]]
                up = max(g.get("upgrade", 0) for g in gear)
                cx, cy = self.fw / 2.0, BUBBLE_MARGIN + self.fh - 18
                r = 26 + RARITY_ORDER.index(top["rarity"]) * 4
                if up >= 5:
                    ph = (self._glow_phase // 6) % 2
                    r2 = r + (7 if ph else 3)
                    c.create_oval(cx - r2, cy - r2, cx + r2, cy + r2,
                                  outline=color, width=3)
                c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=2)
                if self.weapon:
                    self._draw_weapon(c, RARITY_COLOR[self.weapon["rarity"]])
                if self.trinket:
                    self._draw_trinket(c, RARITY_COLOR[self.trinket["rarity"]])
                # 全成就彩虹光环（12/12）
                if len(self.achieves) >= len(ACHIEVEMENTS):
                    import colorsys
                    hue = (self._glow_phase * 0.02) % 1.0
                    rc = "#%02X%02X%02X" % tuple(
                        int(v * 255) for v in colorsys.hsv_to_rgb(hue, 0.75, 0.95))
                    r3 = r + 8 + int(math.sin(self._glow_phase * 0.08) * 3)
                    c.create_oval(cx - r3, cy - r3, cx + r3, cy + r3,
                                  outline=rc, width=3)
            if self.ulting:
                # 必杀技特效：旋转光弧
                cx2, cy2 = self.fw / 2.0, BUBBLE_MARGIN + self.fh / 2.0
                for k in range(3):
                    a0 = (self._glow_phase * 0.15 + k * 2.09) % 6.283
                    c.create_arc(cx2 - 42, cy2 - 42, cx2 + 42, cy2 + 42,
                                 start=math.degrees(a0), extent=85, style="arc",
                                 outline="#FFC53D", width=3)
            if self._fusion:
                # 合体技特效：金色双环 + 星芒
                cx2, cy2 = self.fw / 2.0, BUBBLE_MARGIN + self.fh / 2.0
                ph = self._glow_phase
                for k in range(2):
                    rr = 30 + k * 14
                    a0 = (ph * 0.12 + k * 1.57) % 6.283
                    c.create_arc(cx2 - rr, cy2 - rr, cx2 + rr, cy2 + rr,
                                 start=math.degrees(a0), extent=220, style="arc",
                                 outline="#FFD93D" if k == 0 else "#FF9F43", width=3)
                for k in range(6):
                    ang = (ph * 0.1 + k * 1.047) % 6.283
                    px = cx2 + math.cos(ang) * (38 + int(math.sin(ph * 0.1) * 5))
                    py = cy2 + math.sin(ang) * (38 + int(math.sin(ph * 0.1) * 5))
                    c.create_oval(px - 3, py - 3, px + 3, py + 3,
                                  fill="#FFD93D", outline="")
            if self._fight_punch > 0:
                # 互殴出拳：拳头 + 速度线（朝对方方向）
                self._fight_punch -= TICK_MS
                o = self._battle_other
                if o is not None:
                    dx, dy = o.x - self.x, o.y - self.y
                    dist = math.hypot(dx, dy) or 1
                    ux, uy = dx / dist, dy / dist
                    px = self.fw / 2 + ux * 36
                    py = BUBBLE_MARGIN + self.fh / 2 + uy * 36
                    c.create_oval(px - 8, py - 8, px + 8, py + 8,
                                  fill="#FFC53D", outline="#E76F51", width=2)
                    c.create_line(px - ux * 18, py - uy * 18, px + ux * 8, py + uy * 8,
                                  fill="#FFC53D", width=3)
            if self._fight_hurt > 0:
                # 互殴受击：红色闪光圈
                self._fight_hurt -= TICK_MS
                cx2, cy2 = self.fw / 2, BUBBLE_MARGIN + self.fh / 2
                c.create_oval(cx2 - 24, cy2 - 24, cx2 + 24, cy2 + 24,
                              outline="#FF6B6B", width=4)
            if self.star_level >= 2:
                # 宠物星级：头顶金色小星（随星级增多）
                cx2, cy2 = self.fw / 2, BUBBLE_MARGIN - 4
                nstar = min(self.star_level, 5)
                for k in range(nstar):
                    sx = cx2 + (k - (nstar - 1) / 2) * 13
                    sy = cy2 - (8 if k % 2 == 0 else 2)
                    r0 = 5
                    pts = []
                    for j in range(10):
                        ang = -3.14159 / 2 + j * 3.14159 / 5
                        rr = r0 if j % 2 == 0 else r0 * 0.45
                        pts.extend((sx + math.cos(ang) * rr,
                                    sy + math.sin(ang) * rr))
                    c.create_polygon(pts, fill="#FFD93D", outline="#E6A817", width=1)
            if self._pop_mode:
                # 点泡泡：彩色泡泡
                for b in self._pop_bubbles:
                    c.create_oval(b[0] - b[2], b[1] - b[2], b[0] + b[2], b[1] + b[2],
                                  fill="#A0E7FF", outline="#4D96FF", width=2)
                    c.create_oval(b[0] - b[2] * 0.45, b[1] - b[2] * 0.5,
                                  b[0] + b[2] * 0.1, b[1] - b[2] * 0.1,
                                  fill="#FFFFFF", outline="")
            if self.special_t > 0 and self.special_kind:
                # 专属技能特效
                ph = self._glow_phase
                cx2, cy2 = self.fw / 2.0, BUBBLE_MARGIN + self.fh / 2.0
                if self.special_kind == "roll":
                    # 滚球冲击：金色球体光环 + 尾部轨迹
                    for k in range(3):
                        rr = 30 + k * 12
                        a0 = (ph * 0.15 + k * 2.09) % 6.283
                        c.create_arc(cx2 - rr, cy2 - rr, cx2 + rr, cy2 + rr,
                                     start=math.degrees(a0), extent=95, style="arc",
                                     outline="#FFC53D", width=3)
                    for k in range(5):
                        bx = cx2 - 30 - (ph * 1.2 + k * 12) % 44
                        by = cy2 + int(math.sin(ph * 0.2 + k) * 8)
                        c.create_oval(bx - 2, by - 2, bx + 2, by + 2,
                                      fill="#FFD93D", outline="")
                elif self.special_kind == "spin":
                    # 短腿旋风：旋转弧 + 外圈气流
                    for k in range(4):
                        rr = 22 + k * 10
                        a0 = (ph * 0.2 + k * 1.57) % 6.283
                        c.create_arc(cx2 - rr, cy2 - rr, cx2 + rr, cy2 + rr,
                                     start=math.degrees(a0), extent=150, style="arc",
                                     outline=("#FF9F43" if k % 2 else "#FFD93D"),
                                     width=3)
                    for k in range(4):
                        ang = (ph * 0.18 + k * 1.57) % 6.283
                        px = cx2 + math.cos(ang) * (56 + int(math.sin(ph * 0.15) * 5))
                        py = cy2 + math.sin(ang) * (56 + int(math.sin(ph * 0.15) * 5))
                        c.create_oval(px - 3, py - 3, px + 3, py + 3,
                                      fill="#FFB74D", outline="")
                else:
                    # 元气爆发：速度线
                    for k in range(4):
                        bx = cx2 - 34 + k * 8
                        by = cy2 - 22 + (ph * 0.8) % 16
                        c.create_line(bx, by, bx - 14, by - 6,
                                      fill="#FFC53D", width=2)
            if self._fireworks > 0:
                # 升级烟花：彩色粒子向四周散开
                self._fireworks -= 1
                f = self._fireworks
                fcx, fcy = self.fw / 2.0, BUBBLE_MARGIN + self.fh / 2.0
                for k in range(12):
                    ang = (self._glow_phase * 0.4 + k * 0.524) % 6.283
                    dist = 10 + (70 - f) * 1.3
                    px = fcx + math.cos(ang) * dist
                    py = fcy + math.sin(ang) * dist
                    c.create_oval(px - 3, py - 3, px + 3, py + 3,
                                  fill=random.choice(FIRE_COLORS), outline="")
        except Exception:
            pass

    def _draw_weather(self, c):
        """模拟天气：雨丝 / 雪花飘落"""
        ph = self._glow_phase
        if self.weather == "雨":
            for i in range(6):
                x = (ph * 3 + i * 23) % max(1, self.fw)
                y = BUBBLE_MARGIN + (ph * 8 + i * 41) % max(1, self.fh - 12)
                c.create_line(x, y, x - 2, y + 9, fill="#74B9FF", width=2)
        elif self.weather == "雪":
            for i in range(5):
                x = (ph * 2 + i * 29) % max(1, self.fw)
                y = BUBBLE_MARGIN + (ph * 5 + i * 47) % max(1, self.fh - 12)
                c.create_oval(x - 2, y - 2, x + 2, y + 2, fill="#FFFFFF", outline="#B0BEC5")

    def _draw_weapon(self, c, color):
        """身侧武器：剑形，随朝向镜像（facing=0 朝右，剑在右）"""
        bx = self.fw * 0.80
        if self.facing:
            bx = self.fw - bx
        by = BUBBLE_MARGIN + self.fh * 0.48
        s = 12
        c.create_polygon(bx + s, by, bx - s, by - 5, bx - s + 5, by,
                         bx - s, by + 5, fill=color, outline="#3A3A3A")
        c.create_line(bx - s, by - 9, bx - s, by + 9, fill="#8D6E63", width=3)
        c.create_oval(bx - s - 4, by - 9, bx - s + 4, by + 9, fill="#8D6E63", outline="")

    def _draw_trinket(self, c, color):
        """头顶饰品：五角星，随朝向微移"""
        sx = self.fw / 2.0 + (7 if self.facing == 0 else -7)
        sy = BUBBLE_MARGIN + 9
        pts = _star_points(sx, sy, 9, 4)
        c.create_polygon(pts, fill=color, outline="#3A3A3A")

    def follow_bubble(self):
        """浮动气泡窗口跟随宠物移动"""
        if self._bubble_visible and self._bubble_top is not None:
            try:
                hwnd = int(self._bubble_top.wm_frame(), 16)
                bw = self._bubble_top_label.winfo_reqwidth()
                bh = self._bubble_top_label.winfo_reqheight()
                bx = int(self.x + (self.fw - bw) / 2)
                by = int(self.y) - bh - 8
                bx = max(2, min(bx, self.vrect.x1 - bw - 2))
                by = max(2, by)
                ctypes.windll.user32.SetWindowPos(
                    hwnd, 0, bx, by, bw, bh, 0x0004 | 0x0010)
            except Exception:
                pass

    def show_bubble(self, text, duration=1300):
        """浮动气泡：独立小窗口显示在宠物上方，可多行、不受宠物窗口宽度限制"""
        if self._bubble_job:
            try:
                self.root.after_cancel(self._bubble_job)
            except Exception:
                pass
        self._ensure_bubble_top()
        self._bubble_top_label.configure(text=text)
        self._bubble_top_label.update_idletasks()
        self._bubble_visible = True
        try:
            self._bubble_top.deiconify()
            self._bubble_top.lift()
            self._bubble_top.wm_attributes("-topmost", True)
        except Exception:
            pass
        self.follow_bubble()
        self._bubble_job = self.root.after(duration, self.hide_bubble)

    def _ensure_bubble_top(self):
        if self._bubble_top is not None:
            return
        t = tk.Toplevel(self.root)
        t.overrideredirect(True)
        t.wm_attributes("-topmost", True)
        t.wm_attributes("-transparentcolor", KEY)
        t.configure(bg=KEY)
        lbl = tk.Label(t, bg="#FFFFFF", fg="#3A3A3A",
                       font=("Microsoft YaHei UI", 11, "bold"),
                       bd=2, relief="ridge", padx=8, pady=3, justify="left")
        lbl.pack()
        self._bubble_top = t
        self._bubble_top_label = lbl

    def hide_bubble(self):
        self._bubble_job = None
        self._bubble_visible = False
        if self._bubble_top is not None:
            try:
                self._bubble_top.withdraw()
            except Exception:
                pass

    # ------------------------------------------------------------ 菜单
    def toggle_pause(self):
        self.paused = not self.paused
        if not self.paused:
            self.state = "walk"
            self.state_left = 0
            self.speed = self.base_speed()
            self.fly_target = None
        self.menu.entryconfigure(0, label="继续移动" if self.paused else "暂停移动")

    def teleport(self):
        b = self.bounds()
        w, h = self.fw, self.fh
        edge = random.choice(self.EDGES)
        t = random.uniform(0.15, 0.85)
        if edge == "top":
            self.x, self.y = b.x0 + (b.x1 - b.x0 - w) * t, b.y0
        elif edge == "bottom":
            self.x, self.y = b.x0 + (b.x1 - b.x0 - w) * t, b.y1 - h
        elif edge == "left":
            self.x, self.y = b.x0, b.y0 + (b.y1 - b.y0 - h) * t
        else:
            self.x, self.y = b.x1 - w, b.y0 + (b.y1 - b.y0 - h) * t
        self.edge = edge
        self.dir = 1
        self.state = "walk"
        self.state_left = 0
        self.speed = self.base_speed()
        self.fly_target = None
        self.facing = 0
        self.apply_geometry()

    def quit(self):
        """彻底退出：销毁全部宠物实例并结束进程（手动一定退得掉）"""
        try:
            for p in list(_PET_INSTANCES):
                try:
                    p.root.destroy()
                except Exception:
                    pass
            _PET_INSTANCES.clear()
        except Exception:
            pass
        try:
            os._exit(0)      # 立即结束进程，不等待 tk/线程清理
        except Exception:
            pass
        sys.exit(0)

    # ------------------------------------------------------------ 主循环
    _swp_ready = False

    def apply_geometry(self):
        # 用 SetWindowPos 定位（物理像素），避开 tk geometry 对负坐标的
        # 特殊解析（-Y 会被当作「距底部对齐」，导致贴顶边时窗口错位）。
        # 窗口比精灵高出一个气泡区；气泡区是键色，呈透明。
        # 注意：必须声明 argtypes，否则 64 位窗口句柄会被截断、定位静默失败。
        try:
            # winfo_id() 返回的是 TkChild 子窗口，移动它会被 tk 布局管理
            # 重置；wm_frame() 返回顶层窗口句柄（十六进制字符串，需转 int）。
            hwnd = int(self.root.wm_frame(), 16)
            u = ctypes.windll.user32
            if not CockroachPet._swp_ready:
                u.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                           ctypes.c_int, ctypes.c_int,
                                           ctypes.c_int, ctypes.c_int, ctypes.c_uint]
                u.SetWindowPos.restype = ctypes.c_bool
                CockroachPet._swp_ready = True
            u.SetWindowPos(hwnd, 0,
                           int(self.x), int(self.y) - BUBBLE_MARGIN,
                           self.fw, self.fh + BUBBLE_MARGIN,
                           0x0004 | 0x0010)   # SWP_NOZORDER | SWP_NOACTIVATE
        except Exception:
            self.root.geometry("%dx%d+%d+%d" % (
                self.fw, self.fh + BUBBLE_MARGIN,
                max(0, int(self.x)), max(0, int(self.y) - BUBBLE_MARGIN)))

    def update_animation(self):
        self.anim_timer += TICK_MS
        if self.state == "walk":
            # 步频与速度联动：跑得越快、迈步越密
            spd = self.speed
            period = max(140, min(360, int(380 - spd * 1.5)))
        elif self.state in ("spin", "dizzy"):
            period = 100
        elif self.state == "idle":
            period = 1200
        else:
            period = 160
        if self.anim_timer >= period:
            self.anim_timer = 0
            frame_key = "walk" if self.state in ("spin", "dizzy") else self.state
            pairs = self.frames[frame_key]
            self.anim_idx = (self.anim_idx + 1) % len(pairs)
            if self.state in ("spin", "dizzy"):
                # 镜像交替快速切换 = 打转 / 眩晕
                self.facing = 1 - self.facing
        cur = self.frames["walk" if self.state in ("spin", "dizzy") else self.state][self.anim_idx][self.facing]
        if cur is not self._current_img:
            self._current_img = cur
            self.sprite.configure(image=cur)
        # 走路颠簸：随帧号上下跳动，强化四肢在动的观感（3px 起落节奏）
        if self.state == "walk":
            bounce = int(round(math.sin(self.anim_idx * 3.14159 / 2) * 3))
            self.sprite.place(x=0, y=BUBBLE_MARGIN + bounce)
        else:
            self.sprite.place(x=0, y=BUBBLE_MARGIN)

    def tick(self):
        try:
            self.tick_count += 1
            if not self.paused:
                if self.state_left > 0:
                    self.state_left -= TICK_MS
                    if self.state_left <= 0:
                        if self.state in ("idle", "scared", "spin", "dizzy", "chase"):
                            self.state = "walk"
                            self.speed = self.base_speed()
                # 饱腹度计时：每 90 秒 -3（Lv14 好胃口：每 180 秒 -3）
                hunger_period = 180000 if self.level >= 14 else 90000
                self._hunger_timer += TICK_MS
                if self._hunger_timer >= hunger_period:
                    self._hunger_timer = 0
                    self.add_hunger(-3)
                # 心情衰减：每 60 秒无互动 -1（雨天 -2）
                self._mood_timer += TICK_MS
                if self._mood_timer >= MOOD_DECAY_MS:
                    self._mood_timer = 0
                    self.add_mood(-2 if self.weather == "雨" else -1)
                # 天气：每 10 分钟 20% 概率变化
                self._weather_timer += TICK_MS
                if self._weather_timer >= WEATHER_TICK_MS:
                    self._weather_timer = 0
                    if random.random() < 0.2:
                        self.weather = random.choice(WEATHERS)
                        if self.weather in ("雨", "雪"):
                            self.show_bubble("天气变了：%s！" % self.weather, 1800)
                        elif random.random() < 0.3:
                            self.show_bubble("今天%s，心情不错～" % self.weather, 1800)
                self.uptime_ms += TICK_MS
                # 隐藏彩蛋：连续 7 天不喂食
                today = date.today()
                if self._check_day != today:
                    self._check_day = today
                    try:
                        from datetime import timedelta
                        if self._last_feed_day == today - timedelta(days=1):
                            self.no_feed_streak = 0
                        else:
                            self.no_feed_streak += 1
                    except Exception:
                        pass
                    if self.no_feed_streak >= 7 and not self._no_feed_egg:
                        self._no_feed_egg = True
                        self.check_achievements("survivor")
                        self.add_gold(100)
                        self.show_bubble(
                            "【隐藏彩蛋】连续 7 天没喂也活得好好的！"
                            "「野外求生」成就 +100 金币", 3800)
                        self.save_state()
                # 周报：新的一周自动切换清零
                self._week_timer += TICK_MS
                if self._week_timer >= 30000:
                    self._week_timer = 0
                    wk = "%d-%d" % date.today().isocalendar()[:2]
                    if self.weekly.get("week") and self.weekly["week"] != wk:
                        self.show_bubble(
                            "新的一周！上周回顾：金币+%d 经验+%d 冒险%d次 首领%d次" % (
                                self.weekly["gold"], self.weekly["exp"],
                                self.weekly["adv"], self.weekly["boss"]), 3600)
                        self.weekly = {"week": wk, "gold": 0, "exp": 0,
                                       "adv": 0, "boss": 0, "feed": 0, "interact": 0}
                    elif not self.weekly.get("week"):
                        self.weekly["week"] = wk
                # 竞技场冷却倒计时
                if self.arena_cd > 0:
                    self.arena_cd = max(0, self.arena_cd - TICK_MS)
                if self.battle_cd > 0:
                    self.battle_cd = max(0, self.battle_cd - TICK_MS)
                # 自动打架：随机游走时双宠碰撞/进入范围自动开战（约每 1 秒检测一次）
                self._auto_check += TICK_MS
                if self._auto_check >= 1000:
                    self._auto_check = 0
                    if len(_PET_INSTANCES) >= 2 and self.pet_id == min(
                            p.pet_id for p in _PET_INSTANCES):
                        try:
                            for o in _PET_INSTANCES:
                                if o is self or not o.root.winfo_exists():
                                    continue
                                if o._battle_t > 0 or o._battle_fight or o._fusion:
                                    continue
                                if o.sleeping or self.sleeping or self._battle_fight:
                                    continue
                                # 与 _battle_tick 同口径（窗口左上角距离）
                                dx = self.x - o.x
                                dy = self.y - o.y
                                if math.hypot(dx, dy) < AUTO_BATTLE_DIST:
                                    self.show_bubble("咦？撞到同伴了！要打一架吗？", 1400)
                                    self.pet_battle(auto=True)
                                    break
                        except Exception as _e:
                            print("自动打架检测异常：%r" % _e, file=sys.stderr)
                # 午夜 0 点特典：0:00~0:09 触发一次
                self._egg_timer += TICK_MS
                if self._egg_timer >= 1000:
                    self._egg_timer = 0
                    tm = time.localtime()
                    if tm.tm_hour == 0 and tm.tm_min < 10:
                        self._midnight_bonus()
                # 睡眠模式：23 点~7 点入睡，白天/互动唤醒
                hh = time.localtime().tm_hour
                if self.sleeping:
                    if 7 <= hh < 23:
                        self._wake()
                    elif random.random() < 0.002:
                        self.show_bubble("Zzz…", 1500)
                elif (hh >= 23 or hh < 7) and self.state == "walk" \
                        and not self.dragging and not self.adventuring \
                        and not self.ulting and random.random() < 0.0015:
                    self.sleeping = True
                    self.state = "idle"
                    self.state_left = 0
                    self.speed = 0
                    self.show_bubble("困了…先睡啦 Zzz", 2000)
                # 技能冷却倒计时
                if self.skill_cd > 0:
                    self.skill_cd = max(0, self.skill_cd - TICK_MS)
                if self.ult_cd > 0:
                    self.ult_cd = max(0, self.ult_cd - TICK_MS)
                if self.special_cd > 0:
                    self.special_cd = max(0, self.special_cd - TICK_MS)
                self._special_tick()
                # 图鉴收集成就：每 5 秒检查一次解锁数量
                self._pokedex_timer += TICK_MS
                if self._pokedex_timer >= 5000:
                    self._pokedex_timer = 0
                    try:
                        n_unlock = len(get_unlocked_pets())
                        if n_unlock >= 8:
                            self.check_achievements("pokedex_8")
                        elif n_unlock >= 6:
                            self.check_achievements("pokedex_6")
                    except Exception:
                        pass
                # 点泡泡：冒新泡泡（上限 8，4 秒后消失）
                if self._pop_mode:
                    now = time.monotonic()
                    if len(self._pop_bubbles) < 8 and random.random() < 0.05:
                        self._pop_bubbles.append([
                            random.randint(16, max(17, self.fw - 16)),
                            BUBBLE_MARGIN + random.randint(12, max(13, self.fh - 12)),
                            random.randint(7, 14), now])
                    self._pop_bubbles = [b for b in self._pop_bubbles
                                         if now - b[3] < 4]
                # 饥饿/低落表现：走慢 + 偶尔冒气泡
                if (self.hunger < 30 or self.mood < 30) and \
                        self.state == "walk" and not self.dragging:
                    self.speed = min(self.speed, self.base_speed() * 0.7)
                    if random.random() < 0.008:
                        self.show_bubble(self.lines("hungry" if self.hunger < 30 else "sad"))
                # 跟随模式计时
                if self.state == "chase":
                    self.chase_left -= TICK_MS
                    if self.chase_left <= 0:
                        self.state = "walk"
                        self.state_left = 0
                        self.speed = self.base_speed()
                # 连续点击超时清零
                if self.click_count > 0 and time.monotonic() - self._last_click > 1.5:
                    self.click_count = 0
                # 饿晕机制：饱腹 0 时瘫倒不动，喂食唤醒
                if self.hunger <= 0 and not self.adventuring:
                    if self.state != "dizzy":
                        if not self._fainted:
                            self._fainted = True
                            self.stats["faint"] += 1
                            self.add_mood(-10)
                        self.state = "idle"
                        self.state_left = 0
                        self.speed = 0
                    if random.random() < 0.01:
                        self.show_bubble("饿晕了…快喂食…", 2000)
                else:
                    self._fainted = False
                if self._battle_t > 0:
                    self._battle_tick()          # 双宠互搏：直线对冲
                elif self._fusion_t > 0:
                    self._fusion_tick()          # 合体技：飞向中心
                elif self._follow_target is not None:
                    self._follow_tick()          # 双宠跟随模式
                else:
                    self.move()
                if not self.wrapping and self.state != "chase":
                    self.clamp_pos(self.bounds())
            self.apply_geometry()
            self.update_animation()
            self.update_glow()
            self.follow_bubble()
            if self.tick_count % 50 == 0:
                # 每隔约 2 秒重申置顶，防止被其他窗口顶掉
                self.root.lift()
                self.root.wm_attributes("-topmost", True)
        except Exception as e:
            print("运行异常：%s" % e, file=sys.stderr)
        self.root.after(TICK_MS, self.tick)


def main():
    enable_dpi_awareness()
    ensure_single_instance()
    root = tk.Tk()
    # 配置宠物未解锁时自动回退到已拥有宠物
    cfg_pet, cfg_skin = load_pet_config()
    cfg_pet = resolve_pet(cfg_pet)
    CockroachPet(root, pet_id=cfg_pet, skin=cfg_skin)
    # 双宠模式：pet_config.json 的 second_pet 非空时同屏第二只
    try:
        with open(os.path.join(script_dir(), "pet_config.json"), "r",
                  encoding="utf-8") as f:
            cfg = json.load(f)
        sp = cfg.get("second_pet")
        if sp and sp.get("pet"):
            top = tk.Toplevel(root)
            CockroachPet(top, pet_id=resolve_pet(sp["pet"]),
                         skin=sp.get("skin", "default"))
    except BaseException as e:
        # 第二只加载失败（如皮肤帧缺失）不拖垮主宠物
        print("第二只宠物启动失败：%s" % e, file=sys.stderr)
    root.mainloop()


if __name__ == "__main__":
    main()
