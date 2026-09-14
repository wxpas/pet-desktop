# -*- coding: utf-8 -*-
"""
桌面电子宠物 · Kivy 版
============================================================
一只沿着屏幕边缘爬行的透明置顶小宠物，不干扰正常操作。

功能：
  1. 沿屏幕边缘自由移动，到达角落时随机转弯或穿墙
  2. 动画循环：walk 4帧 / idle 2帧 / scared 2帧
  3. 点击宠物：受惊反应（加速 + 变向 + 气泡台词）
  4. 长按宠物：弹出操作菜单
  5. 状态系统：饱腹度、心情、等级、经验、金币、装备等
  6. 属性面板：查看详细属性

操作：
  左键单击   —— 惊吓反应
  长按       —— 弹出菜单
  运行方式   —— python main.py

依赖：
  Python 3.8+ / Kivy 2.0+
"""
import os
import sys
import json
import random
import time

# ========== 平台检测（必须放在最前面）==========
from kivy.utils import platform as kivy_platform
IS_ANDROID = kivy_platform == 'android'

# ========== Windows 高 DPI 感知（必须在 Kivy 建窗之前）==========
if not IS_ANDROID:
    try:
        import ctypes as _ctypes
        try:
            _ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                _ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
    except Exception:
        pass

# ========== Kivy 配置（必须放在 import kivy.uix 之前）==========
from kivy.config import Config

if not IS_ANDROID:
    # 桌面端：无边框小窗口模式
    Config.set('graphics', 'borderless', '1')      # 无边框
    Config.set('graphics', 'resizable', '0')       # 不可调整大小
    Config.set('graphics', 'window_state', 'visible')
else:
    # Android 端：全屏模式
    Config.set('graphics', 'window_state', 'maximized')
    Config.set('graphics', 'resizable', '0')

import kivy
from kivy.app import App
from kivy.core.window import Window
from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.progressbar import ProgressBar
from kivy.uix.spinner import Spinner
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle
from kivy.core.text import LabelBase
from kivy.metrics import dp, Metrics

# ========== 导入核心模块 ==========
from pet_core.constants import FRAMES, TICK_MS, MOOD_DECAY_MS, \
    AFFINITY_LEVELS, TITLES, RARITY_COLOR, SLOT_NAME, ACHIEVEMENTS, \
    DIFFS, SHOP_COST, SELL_PRICE, UPGRADE_COST, MAX_UPGRADE, INV_MAX, \
    SYNTH_COST, RECAST_COST
from pet_core.utils import load_pet_config, load_pet_library, \
    pet_display_name, get_pet_lines, resolve_pet, resource_dir, \
    get_unlocked_pets, save_pet_config, set_data_dir, get_data_dir, \
    IS_ANDROID as UTILS_IS_ANDROID
from pet_core.pet_state import PetState
from pet_core import game_logic

# ========== 基础常量 ==========
ANIM_FPS = 25                       # 动画帧率
MOVE_TICK_MS = 40                    # 移动更新间隔（约 25 FPS）
BASE_SPEED = 60.0                    # 基础速度（像素/秒）
SCARED_SPEED_MULT = 2.5              # 受惊时速度倍率
SCARED_DURATION = 1.5                # 受惊持续时间（秒）
IDLE_CHANCE_PER_SEC = 0.15           # 每秒进入 idle 的概率
IDLE_MIN_TIME = 1.0                  # 最短停顿时间（秒）
IDLE_MAX_TIME = 3.0                  # 最长停顿时间（秒）
LONG_PRESS_TIME = 0.5                # 长按判定时间（秒）
BUBBLE_DURATION = 2.0                # 气泡显示时长（秒）
BUBBLE_HEIGHT = 30                   # 气泡区域高度（像素）
HUNGER_DECAY_INTERVAL = 30           # 饱腹度衰减间隔（秒）
HUNGER_DECAY_AMOUNT = 1              # 每次衰减量
MOOD_DECAY_INTERVAL = 60             # 心情衰减间隔（秒）
MOOD_DECAY_AMOUNT = 1                # 每次衰减量
SAVE_INTERVAL = 30                   # 自动保存间隔（秒）

# ========== 多宠相关 ==========
MAX_PETS = 4                         # 最多同时同屏的宠物数量
DESKTOP_VIEWPORT = True              # 桌面端：整块屏幕作透明遮罩，多只宠物同在窗口内
SPECIAL_CD = 20.0                    # 专属操作冷却（秒，每只宠物各自计时）

# 每只宠物的专属操作：招式名 + 只结算到自己身上的奖励/速度
PET_SPECIAL = {
    "cockroach": {"name": "元气爆发", "gold": 40, "exp": 20, "mood": 8,
                  "speed_mult": 2.2, "duration": 2.0},
    "cat": {"name": "利爪连击", "gold": 55, "exp": 25, "mood": 6,
            "speed_mult": 2.6, "duration": 1.6},
    "dog": {"name": "忠犬猛扑", "gold": 50, "exp": 30, "mood": 6,
            "speed_mult": 2.4, "duration": 1.8},
    "rabbit": {"name": "飞踢弹跳", "gold": 45, "exp": 28, "mood": 9,
               "speed_mult": 2.8, "duration": 1.5},
    "hamster": {"name": "滚球冲击", "gold": 60, "exp": 24, "mood": 7,
                "speed_mult": 3.0, "duration": 1.4},
    "corgi": {"name": "短腿旋风", "gold": 65, "exp": 30, "mood": 7,
              "speed_mult": 2.5, "duration": 1.7},
    "penguin": {"name": "冰锋啄击", "gold": 58, "exp": 32, "mood": 6,
                "speed_mult": 2.3, "duration": 1.8},
    "panda": {"name": "泰山压顶", "gold": 70, "exp": 35, "mood": 5,
              "speed_mult": 2.1, "duration": 2.0},
}
PET_SPECIAL_DEFAULT = {"name": "元气爆发", "gold": 40, "exp": 20, "mood": 8,
                       "speed_mult": 2.2, "duration": 2.0}

# 边缘定义
EDGE_TOP = "top"
EDGE_RIGHT = "right"
EDGE_BOTTOM = "bottom"
EDGE_LEFT = "left"
EDGES = (EDGE_TOP, EDGE_RIGHT, EDGE_BOTTOM, EDGE_LEFT)


def get_screen_size():
    """获取主屏幕尺寸（物理像素）

    桌面端优先用 Windows 的 GetSystemMetrics（物理像素，最可靠）；
    拿不到时退回 Kivy 的 Window.system_size。
    """
    if not IS_ANDROID:
        try:
            import ctypes
            u = ctypes.windll.user32
            w = int(u.GetSystemMetrics(0))     # SM_CXSCREEN
            h = int(u.GetSystemMetrics(1))     # SM_CYSCREEN
            if w > 200 and h > 200:
                return float(w), float(h)
        except Exception:
            pass
    return Window.system_size


def register_cjk_font():
    """注册中文字体

    Kivy 自带的默认字体（Roboto）不含中文字形，不注册的话界面上
    所有中文都会显示成"口口口"方块。这里优先用项目自带的字体，
    其次用系统字体，并直接注册成 Kivy 的默认字体名，
    这样所有 Label 不用改一行代码就都能显示中文。

    返回:
        str | None: 实际使用的字体路径；没找到则返回 None（保持默认）。
    """
    cands = []
    fdir = os.path.join(resource_dir(), "fonts")
    for name in ("NotoSansSC-Regular.otf", "SourceHanSansSC-Regular.otf",
                 "DroidSansFallback.ttf", "cjk.ttf", "font.ttf"):
        cands.append(os.path.join(fdir, name))
    if IS_ANDROID:
        cands += [
            "/system/fonts/NotoSansCJK-Regular.ttc",
            "/system/fonts/NotoSansCJKsc-Regular.otf",
            "/system/fonts/NotoSansSC-Regular.otf",
            "/system/fonts/DroidSansFallback.ttf",
        ]
    else:
        windir = os.environ.get("WINDIR", r"C:\Windows")
        cands += [os.path.join(windir, "Fonts", n) for n in
                  ("msyh.ttc", "msyh.ttf", "simhei.ttf", "simsun.ttc",
                   "Deng.ttf", "msyhl.ttc")]
    for path in cands:
        if not os.path.exists(path):
            continue
        try:
            LabelBase.register(name="Roboto", fn_regular=path, fn_bold=path)
            return path
        except Exception:
            continue
    return None


def _find_own_sdl_hwnd():
    """找到本进程自己的 SDL 窗口句柄（Windows）"""
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        pid = ctypes.windll.kernel32.GetCurrentProcessId()
        found = []
        proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND,
                                  wintypes.LPARAM)
        cls = ctypes.create_unicode_buffer(64)

        def _cb(hwnd, _lparam):
            p = wintypes.DWORD()
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
            if p.value == pid:
                u.GetClassNameW(hwnd, cls, 64)
                if cls.value.startswith("SDL"):
                    found.append(hwnd)
            return True
        u.EnumWindows(proc(_cb), 0)
        return found[0] if found else 0
    except Exception:
        return 0


def enable_desktop_transparency(key=(255, 0, 255)):
    """桌面端整屏遮罩的透明处理（Windows）

    Kivy/SDL 的窗口默认不支持逐像素透明，光设 clearcolor 的 alpha=0
    是没用的——窗口会显示成一块纯色遮罩，把整个桌面盖住。
    这里用 Win32 的"色键透明"：把整窗底色设成 key 色，
    再给窗口加 WS_EX_LAYERED + LWA_COLORKEY，
    底色部分就变成全透明（而且鼠标点击会穿透到下层窗口），
    宠物自己照常显示、照常可点。

    返回:
        bool: 是否成功开启。
    """
    if IS_ANDROID:
        return False
    hwnd = _find_own_sdl_hwnd()
    if not hwnd:
        return False
    try:
        import ctypes
        u = ctypes.windll.user32
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        LWA_COLORKEY = 0x00000001
        ex = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
        u.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED)
        colorref = int(key[0]) | (int(key[1]) << 8) | (int(key[2]) << 16)
        ok = u.SetLayeredWindowAttributes(hwnd, ctypes.c_uint(colorref),
                                          0, LWA_COLORKEY)
        return bool(ok)
    except Exception:
        return False


class PetWidget(object):
    """宠物显示件：精灵 + 气泡

    ★ 为什么不用"父控件里塞子控件"的写法
    Kivy 里只有 RelativeLayout 会给自己的画布加位移，普通 Widget / FloatLayout
    的 pos 并不会平移子控件的画布——子控件的局部坐标 (0, 0) 会直接落到屏幕
    左下角，多只宠物就全部叠在同一个角落（看起来"只有一只宠物能点"）。
    所以这里精灵用 root 画布上的 Rectangle（绝对坐标，且压在子控件之下）、
    气泡用 root 的直接子控件 Label（绝对坐标），位置全部由 PetUnit 自己算，
    每只宠物各画各的，互不干扰。
    """

    def __init__(self, pet_app, **kwargs):
        self.pet_app = pet_app
        # pet_app 可能是 PetUnit（弹窗上下文），也可能是 PetApp 本身
        app = getattr(pet_app, "app", pet_app) or pet_app
        self._app = app
        self._frame_w = 64.0
        self._frame_h = 64.0
        self._x = 0.0
        self._y = 0.0
        self._bubble_timer = None

        # ---- 精灵：画在 root 画布的 before 组里（绝对坐标，位于所有子控件之下）----
        canvas = app.root.canvas
        with canvas.before:
            self._sprite_color = Color(1, 1, 1, 1)
            self.sprite = Rectangle(pos=(0, 0), size=(0, 0))

        # ---- 气泡：root 的直接子控件（与计数 HUD 同一套写法）----
        self.bubble_label = Label(
            text="",
            size_hint=(None, None),
            font_size=dp(12),
            color=(0.2, 0.2, 0.2, 1),
            bold=True,
            padding=(dp(8), dp(4)),
            opacity=0,
        )
        # 气泡背景（桌面端是色键透明遮罩，半透明会混出底色，所以用不透明）
        with self.bubble_label.canvas.before:
            self._bubble_border_color = Color(0.55, 0.55, 0.6, 1)
            self._bubble_border = Rectangle(pos=(0, 0), size=(0, 0))
            self._bubble_bg_color = Color(1, 1, 1, 1)
            self._bubble_bg = Rectangle(pos=(0, 0), size=(0, 0))
        self.bubble_label.bind(pos=self._update_bubble_bg,
                               size=self._update_bubble_bg)
        app.root.add_widget(self.bubble_label)

    # ------------------------------------------------------------ 几何
    def set_frame_size(self, width, height):
        """设置精灵帧尺寸（精灵左下角就是 pos）"""
        self._frame_w = float(width)
        self._frame_h = float(height)
        self.sprite.size = (self._frame_w, self._frame_h)
        self.sprite.pos = (self._x, self._y)

    def set_pos(self, x, y):
        """移动精灵（绝对屏幕坐标，左下角）"""
        self._x, self._y = float(x), float(y)
        self.sprite.pos = (self._x, self._y)
        if self.bubble_label.opacity > 0:
            self._place_bubble()

    # pos / size / x / y：用法和普通控件一致
    pos = property(lambda self: (self._x, self._y),
                   lambda self, value: self.set_pos(value[0], value[1]))
    size = property(lambda self: (self._frame_w, self._frame_h))
    x = property(lambda self: self._x)
    y = property(lambda self: self._y)

    def _place_bubble(self):
        tw, th = self.bubble_label.size
        self.bubble_label.pos = (self._x + (self._frame_w - tw) / 2.0,
                                 self._y + self._frame_h + BUBBLE_HEIGHT - 4)

    def _update_bubble_bg(self, instance, value):
        """更新气泡背景矩形的位置和大小"""
        x, y = instance.pos
        w, h = instance.size
        self._bubble_bg.pos = (x + 1, y + 1)
        self._bubble_bg.size = (w - 2, h - 2)
        self._bubble_border.pos = (x, y)
        self._bubble_border.size = (w, h)

    # ------------------------------------------------------------ 显示
    def update_frame(self, texture):
        """更新精灵帧纹理"""
        self.sprite.texture = texture

    def show_bubble(self, text, duration=BUBBLE_DURATION):
        """显示气泡台词"""
        text_w = max(dp(60), len(text) * dp(14) + dp(16))
        text_h = dp(24)
        self.bubble_label.text = text
        self.bubble_label.size = (text_w, text_h)
        self._place_bubble()
        self.bubble_label.opacity = 1
        if self._bubble_timer:
            self._bubble_timer.cancel()
        self._bubble_timer = Clock.schedule_once(self._hide_bubble, duration)

    def _hide_bubble(self, dt):
        """隐藏气泡"""
        self.bubble_label.opacity = 0
        self._bubble_timer = None

    # ------------------------------------------------------------ 命中测试
    def is_point_on_pet(self, x, y):
        """判断屏幕坐标 (x, y) 是否落在精灵矩形内（绝对坐标直接比较）"""
        return (self._x <= x <= self._x + self._frame_w and
                self._y <= y <= self._y + self._frame_h)

    def hit_test(self, x, y):
        """每只宠物各自算自己的矩形，多宠互不干扰"""
        return self.is_point_on_pet(x, y)

    # ------------------------------------------------------------ 层级 / 清理
    def raise_me(self):
        """把这只宠物提到最上层（只动自己的画布，不碰其他宠物和 HUD）"""
        c = self._app.root.canvas.before
        for instr in (self._sprite_color, self.sprite):
            try:
                c.remove(instr)
            except Exception:
                pass
        c.add(self._sprite_color)
        c.add(self.sprite)

    def remove_me(self):
        """把自己从画布和控件树上摘掉（其他宠物照常活动）"""
        c = self._app.root.canvas.before
        for instr in (self._sprite_color, self.sprite):
            try:
                c.remove(instr)
            except Exception:
                pass
        if self._bubble_timer:
            self._bubble_timer.cancel()
            self._bubble_timer = None
        try:
            self._app.root.remove_widget(self.bubble_label)
        except Exception:
            pass


class PetMenuPopup(Popup):
    """宠物操作菜单弹窗（两列布局，支持滚动）"""

    def __init__(self, pet_app, **kwargs):
        super().__init__(**kwargs)
        self.pet_app = pet_app
        # 标题带上这只宠物自己的名字：多宠同屏时一眼分清在操作谁
        self.title = "%s 的菜单" % getattr(pet_app, "title", "宠物")
        self.size_hint = (None, None)
        self.size = (dp(300), dp(460))
        self.auto_dismiss = True
        self.title_size = dp(16)
        self.separator_height = dp(2)

        # 这只宠物自己的专属操作名（每只宠物不一样）
        sp_name = "专属技能"
        try:
            sp_name = "专属·%s" % pet_app.special_name()
        except Exception:
            pass

        # 外层布局
        outer = BoxLayout(orientation='vertical', padding=dp(6), spacing=dp(4))

        # 分组标题
        def make_section(title):
            return Label(text=title, size_hint_y=None, height=dp(22),
                         font_size=dp(11), bold=True, color=(0.8, 0.8, 0.8, 1),
                         halign='left')

        # 滚动区
        scroll = ScrollView(size_hint=(1, 1))
        scroll_layout = BoxLayout(orientation='vertical', spacing=dp(4),
                                  size_hint_y=None)
        scroll_layout.bind(minimum_height=scroll_layout.setter('height'))

        # —— 互动组 ——
        scroll_layout.add_widget(make_section("—— 互动 ——"))
        interact_grid = GridLayout(cols=3, spacing=dp(4),
                                    size_hint_y=None, height=dp(42))
        interact_items = [
            ("喂食", self.on_feed),
            ("摸摸头", self.on_pet),
            ("逗它玩", self.on_play),
        ]
        for text, callback in interact_items:
            btn = Button(text=text, font_size=dp(12))
            btn.bind(on_release=callback)
            interact_grid.add_widget(btn)
        scroll_layout.add_widget(interact_grid)

        # —— 专属操作组（每只宠物有自己的招式，只作用于它自己）——
        scroll_layout.add_widget(make_section("—— 专属 ——"))
        special_grid = GridLayout(cols=2, spacing=dp(4),
                                  size_hint_y=None, height=dp(42))
        special_items = [
            (sp_name, self.on_special),
            ("让它离场", self.on_leave),
        ]
        for text, callback in special_items:
            btn = Button(text=text, font_size=dp(11))
            btn.bind(on_release=callback)
            special_grid.add_widget(btn)
        scroll_layout.add_widget(special_grid)

        # —— RPG 组 ——
        scroll_layout.add_widget(make_section("—— RPG ——"))
        rpg_grid = GridLayout(cols=3, spacing=dp(4),
                              size_hint_y=None, height=dp(84))
        rpg_items = [
            ("冒险", self.on_adventure),
            ("商店", self.on_shop),
            ("背包", self.on_inventory),
            ("签到", self.on_signin),
            ("成就", self.on_achievement),
            ("属性", self.on_stats),
        ]
        for text, callback in rpg_items:
            btn = Button(text=text, font_size=dp(12))
            btn.bind(on_release=callback)
            rpg_grid.add_widget(btn)
        scroll_layout.add_widget(rpg_grid)

        # —— 设置组 ——
        scroll_layout.add_widget(make_section("—— 设置 ——"))
        setting_grid = GridLayout(cols=2, spacing=dp(4),
                                  size_hint_y=None, height=dp(42))
        setting_items = [
            ("更换宠物", self.on_change_pet),
            ("退出", self.on_quit),
        ]
        for text, callback in setting_items:
            btn = Button(text=text, font_size=dp(12))
            btn.bind(on_release=callback)
            setting_grid.add_widget(btn)
        scroll_layout.add_widget(setting_grid)

        scroll.add_widget(scroll_layout)
        outer.add_widget(scroll)

        self.content = outer

    def on_feed(self, instance):
        self.dismiss()
        self.pet_app.action_feed()

    def on_pet(self, instance):
        self.dismiss()
        self.pet_app.action_pet()

    def on_play(self, instance):
        self.dismiss()
        self.pet_app.action_play()

    def on_special(self, instance):
        """释放这只宠物的专属操作（只结算到它自己身上）"""
        self.dismiss()
        self.pet_app.action_special()

    def on_leave(self, instance):
        """让这只宠物离场（其他宠物继续活动）"""
        self.dismiss()
        app = getattr(self.pet_app, "app", None)
        if app is not None:
            app.remove_pet(self.pet_app)

    def on_adventure(self, instance):
        self.dismiss()
        self.pet_app.show_adventure()

    def on_shop(self, instance):
        self.dismiss()
        self.pet_app.show_shop()

    def on_inventory(self, instance):
        self.dismiss()
        self.pet_app.show_inventory()

    def on_signin(self, instance):
        self.dismiss()
        self.pet_app.show_signin()

    def on_achievement(self, instance):
        self.dismiss()
        self.pet_app.show_achievement()

    def on_stats(self, instance):
        self.dismiss()
        self.pet_app.show_stats_panel()

    def on_change_pet(self, instance):
        self.dismiss()
        self.pet_app.show_pet_select()

    def on_quit(self, instance):
        self.dismiss()
        self.pet_app.quit_app()


class StatsPanel(Popup):
    """属性面板弹窗"""

    def __init__(self, pet_app, **kwargs):
        super().__init__(**kwargs)
        self.pet_app = pet_app
        self.title = "宠物属性"
        self.size_hint = (None, None)
        self.size = (dp(340), dp(440))
        self.auto_dismiss = True
        self.title_size = dp(16)

        state = pet_app.pet_state
        pet_name = pet_app.pet_name
        nickname = state.nickname or pet_name

        # 等级称号
        title_name = "新手"
        for lv, name in TITLES:
            if state.level >= lv:
                title_name = name
                break

        # 好感度等级
        affinity_name = "陌生"
        for val, name in AFFINITY_LEVELS:
            if state.affinity >= val:
                affinity_name = name
                break

        # 装备信息
        def gear_text(gear):
            if not gear:
                return "无"
            return f"{gear.get('name', '?')}（{gear.get('rarity', '普通')}）"

        layout = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(4))

        info_lines = [
            f"名字：{nickname}",
            f"称号：{title_name}",
            f"等级：Lv.{state.level}    经验：{state.exp}",
            f"金币：{state.gold}",
            f"饱腹度：{state.hunger}/100",
            f"好感度：{state.affinity}/100（{affinity_name}）",
            f"心情值：{state.mood}/100",
            f"星级：{'★' * state.star_level}{'☆' * (5 - state.star_level)}",
            "",
            "—— 装 备 ——",
            f"武器：{gear_text(state.weapon)}",
            f"防具：{gear_text(state.armor)}",
            f"饰品：{gear_text(state.trinket)}",
            "",
            f"累计冒险：{state.adv_count} 次",
            f"成就达成：{len(state.achieves)} 项",
        ]

        for line in info_lines:
            label = Label(text=line, size_hint_y=None, height=dp(22),
                          font_size=dp(12), halign='left', valign='middle')
            label.bind(size=lambda l, v: setattr(l, 'text_size', v))
            layout.add_widget(label)

        close_btn = Button(text="关闭", size_hint_y=None, height=dp(38),
                           font_size=dp(14))
        close_btn.bind(on_release=lambda x: self.dismiss())
        layout.add_widget(close_btn)

        self.content = layout


# ============================================================
#  辅助函数
# ============================================================

def _hex_to_rgba(hex_color, alpha=1.0):
    """将十六进制颜色转换为 RGBA 元组

    参数:
        hex_color: "#RRGGBB" 格式的颜色字符串
        alpha: 透明度 (0-1)

    返回:
        tuple: (r, g, b, a) 各分量 0-1
    """
    hex_color = hex_color.lstrip('#')
    return (
        int(hex_color[0:2], 16) / 255.0,
        int(hex_color[2:4], 16) / 255.0,
        int(hex_color[4:6], 16) / 255.0,
        alpha,
    )


def _rarity_color_tuple(rarity, alpha=1.0):
    """获取稀有度对应的 RGBA 颜色元组"""
    hex_c = RARITY_COLOR.get(rarity, "#B0B0B0")
    return _hex_to_rgba(hex_c, alpha)


# ============================================================
#  冒险弹窗
# ============================================================

class AdventurePopup(Popup):
    """冒险弹窗：选择难度、显示进度、结算奖励"""

    def __init__(self, pet_app, **kwargs):
        super().__init__(**kwargs)
        self.pet_app = pet_app
        self.title = "冒险"
        self.size_hint = (None, None)
        self.size = (dp(380), dp(420))
        self.auto_dismiss = True
        self.title_size = dp(16)

        self._difficulty = None
        self._duration = 0
        self._progress_event = None
        self._start_time = 0

        self._build_ui()

    def _build_ui(self):
        """构建界面"""
        self.main_layout = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8))

        # 难度选择区
        self.diff_layout = BoxLayout(orientation='vertical', spacing=dp(6))
        diff_title = Label(text="选择难度", size_hint_y=None, height=dp(24),
                           font_size=dp(14), bold=True)
        self.diff_layout.add_widget(diff_title)

        diffs = [
            ("easy", "简单", "适合新手，收益较低"),
            ("normal", "普通", "标准难度，收益适中"),
            ("night", "噩梦", "高风险高回报，有首领"),
        ]
        for key, name, desc in diffs:
            btn = Button(
                text=f"{name}\n{desc}",
                size_hint_y=None, height=dp(56),
                font_size=dp(13),
                halign='center', valign='middle',
            )
            btn.bind(on_release=lambda inst, k=key: self._on_select_diff(k))
            self.diff_layout.add_widget(btn)

        self.main_layout.add_widget(self.diff_layout)

        # 进度区（初始隐藏）
        self.progress_layout = BoxLayout(orientation='vertical', spacing=dp(8))
        self.progress_label = Label(text="", size_hint_y=None, height=dp(28),
                                    font_size=dp(13))
        self.progress_bar = ProgressBar(max=100, value=0, size_hint_y=None,
                                        height=dp(20))
        self.progress_layout.add_widget(self.progress_label)
        self.progress_layout.add_widget(self.progress_bar)
        self.progress_layout.opacity = 0
        self.main_layout.add_widget(self.progress_layout)

        # 结算区（初始隐藏）
        self.result_layout = BoxLayout(orientation='vertical', spacing=dp(6))
        self.result_title = Label(text="", size_hint_y=None, height=dp(28),
                                  font_size=dp(15), bold=True)
        self.result_detail = Label(text="", size_hint_y=None, height=dp(60),
                                   font_size=dp(12), halign='left', valign='top')
        self.result_detail.bind(size=lambda l, v: setattr(l, 'text_size', v))
        self.result_layout.add_widget(self.result_title)
        self.result_layout.add_widget(self.result_detail)
        self.result_layout.opacity = 0
        self.main_layout.add_widget(self.result_layout)

        # 关闭按钮
        self.close_btn = Button(text="关闭", size_hint_y=None, height=dp(38),
                                font_size=dp(14))
        self.close_btn.bind(on_release=lambda x: self.dismiss())
        self.main_layout.add_widget(self.close_btn)

        self.content = self.main_layout

    def _on_select_diff(self, difficulty):
        """选择难度并开始冒险"""
        self._difficulty = difficulty
        state = self.pet_app.pet_state

        # 计算时长和预览
        dur, preview = game_logic.start_adventure(state, difficulty)
        self._duration = dur
        self._start_time = time.time()

        # 切换到进度界面
        self.diff_layout.opacity = 0
        self.diff_layout.disabled = True
        self.progress_layout.opacity = 1
        self.close_btn.disabled = True

        diff_name = DIFFS[difficulty][0]
        self.progress_label.text = f"【{diff_name}】冒险中…（约 {dur} 秒）"

        # 启动进度更新
        self._progress_event = Clock.schedule_interval(self._update_progress, 0.1)

    def _update_progress(self, dt):
        """更新进度条"""
        elapsed = time.time() - self._start_time
        progress = min(100, elapsed / self._duration * 100)
        self.progress_bar.value = progress

        if elapsed >= self._duration:
            self._progress_event.cancel()
            self._progress_event = None
            self._finish_adventure()

    def _finish_adventure(self):
        """冒险结束，显示结算"""
        state = self.pet_app.pet_state
        gold, exp, gear, is_boss, logs = game_logic.finish_adventure(state, self._difficulty)

        # 保存状态
        state.save(self.pet_app.pet_id)

        # 显示结算
        self.progress_layout.opacity = 0
        self.result_layout.opacity = 1
        self.close_btn.disabled = False

        if is_boss:
            self.result_title.text = "首领战结束！"
        else:
            self.result_title.text = "冒险归来！"

        detail = f"金币：+{gold}\n经验：+{exp}"
        if gear:
            detail += f"\n掉落：{gear['name']}·{gear['rarity']}"
        if logs:
            detail += "\n\n" + "\n".join(logs[:3])

        self.result_detail.text = detail

    def on_dismiss(self):
        """弹窗关闭时清理定时器"""
        if self._progress_event:
            self._progress_event.cancel()
            self._progress_event = None
        super().on_dismiss()


# ============================================================
#  商店弹窗
# ============================================================

class ShopPopup(Popup):
    """商店弹窗：购买装备"""

    def __init__(self, pet_app, **kwargs):
        super().__init__(**kwargs)
        self.pet_app = pet_app
        self.title = "商店"
        self.size_hint = (None, None)
        self.size = (dp(360), dp(360))
        self.auto_dismiss = True
        self.title_size = dp(16)

        self._build_ui()

    def _build_ui(self):
        """构建界面"""
        layout = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))

        # 金币显示
        self.gold_label = Label(
            text=f"金币：{self.pet_app.pet_state.gold}",
            size_hint_y=None, height=dp(28),
            font_size=dp(15), bold=True, color=(1, 0.8, 0.2, 1),
        )
        layout.add_widget(self.gold_label)

        # 商店介绍
        intro = Label(
            text="神秘商人的装备铺子\n每次抽取一件随机装备",
            size_hint_y=None, height=dp(48),
            font_size=dp(12), halign='center', valign='middle',
        )
        layout.add_widget(intro)

        # 购买按钮
        self.buy_btn = Button(
            text=f"购买装备（{SHOP_COST} 金币）",
            size_hint_y=None, height=dp(48),
            font_size=dp(15), bold=True,
            background_color=(0.2, 0.6, 1, 1),
        )
        self.buy_btn.bind(on_release=self._on_buy)
        layout.add_widget(self.buy_btn)

        # 结果显示
        self.result_box = BoxLayout(orientation='vertical', spacing=dp(4),
                                    size_hint_y=None, height=dp(80))
        self.result_name = Label(
            text="", size_hint_y=None, height=dp(28),
            font_size=dp(16), bold=True,
        )
        self.result_detail = Label(
            text="", size_hint_y=None, height=dp(44),
            font_size=dp(12),
        )
        self.result_box.add_widget(self.result_name)
        self.result_box.add_widget(self.result_detail)
        layout.add_widget(self.result_box)

        # 关闭按钮
        close_btn = Button(text="关闭", size_hint_y=None, height=dp(38),
                           font_size=dp(14))
        close_btn.bind(on_release=lambda x: self.dismiss())
        layout.add_widget(close_btn)

        self.content = layout

    def _on_buy(self, instance):
        """购买装备"""
        state = self.pet_app.pet_state
        success, gear, msg = game_logic.buy_gear(state)

        # 更新金币显示
        self.gold_label.text = f"金币：{state.gold}"

        if success and gear:
            # 显示获得的装备（稀有度颜色）
            self.result_name.text = f"{gear['name']}·{gear['rarity']}"
            self.result_name.color = _rarity_color_tuple(gear['rarity'])
            self.result_detail.text = (
                f"槽位：{SLOT_NAME.get(gear['slot'], '?')}\n"
                f"套装：{gear.get('set', '无')}"
            )
        else:
            self.result_name.text = "购买失败"
            self.result_name.color = (0.8, 0.2, 0.2, 1)
            self.result_detail.text = msg

        # 保存状态
        state.save(self.pet_app.pet_id)

    def on_dismiss(self):
        """关闭时刷新宠物状态显示"""
        super().on_dismiss()


# ============================================================
#  背包/装备弹窗
# ============================================================

class InventoryPopup(Popup):
    """背包/装备弹窗：查看装备、穿戴、强化、分解等"""

    def __init__(self, pet_app, **kwargs):
        super().__init__(**kwargs)
        self.pet_app = pet_app
        self.title = "背包 / 装备"
        self.size_hint = (None, None)
        self.size = (dp(420), dp(520))
        self.auto_dismiss = True
        self.title_size = dp(16)

        self._selected_idx = -1  # 选中的背包索引

        self._build_ui()

    def _build_ui(self):
        """构建界面"""
        main_layout = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(6))

        # 顶部：金币 + 精华
        top_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(28))
        self.gold_label = Label(
            text=f"金币：{self.pet_app.pet_state.gold}",
            font_size=dp(12), color=(1, 0.8, 0.2, 1),
        )
        self.essence_label = Label(
            text=f"精华：{self.pet_app.pet_state.essence}",
            font_size=dp(12), color=(0.6, 0.4, 1, 1),
        )
        top_bar.add_widget(self.gold_label)
        top_bar.add_widget(self.essence_label)
        main_layout.add_widget(top_bar)

        # 已装备区
        equip_title = Label(text="—— 已装备 ——", size_hint_y=None, height=dp(22),
                            font_size=dp(12), bold=True)
        main_layout.add_widget(equip_title)

        self.equip_layout = GridLayout(cols=3, spacing=dp(4),
                                       size_hint_y=None, height=dp(72))
        self._refresh_equipped()
        main_layout.add_widget(self.equip_layout)

        # 背包区
        inv_title = Label(
            text=f"—— 背包（{len(self.pet_app.pet_state.inventory)}/{INV_MAX}）——",
            size_hint_y=None, height=dp(22),
            font_size=dp(12), bold=True,
        )
        main_layout.add_widget(inv_title)

        # 背包滚动区
        inv_scroll = ScrollView(size_hint=(1, 1))
        self.inv_grid = GridLayout(cols=3, spacing=dp(4),
                                   size_hint_y=None)
        self.inv_grid.bind(minimum_height=self.inv_grid.setter('height'))
        self._refresh_inventory()
        inv_scroll.add_widget(self.inv_grid)
        main_layout.add_widget(inv_scroll)

        # 操作按钮区
        self.action_layout = BoxLayout(orientation='horizontal', spacing=dp(4),
                                       size_hint_y=None, height=dp(36))
        self._build_action_buttons()
        main_layout.add_widget(self.action_layout)

        # 提示信息
        self.tip_label = Label(text="选择背包装备后可进行操作",
                               size_hint_y=None, height=dp(22),
                               font_size=dp(11), color=(0.6, 0.6, 0.6, 1))
        main_layout.add_widget(self.tip_label)

        # 关闭按钮
        close_btn = Button(text="关闭", size_hint_y=None, height=dp(36),
                           font_size=dp(13))
        close_btn.bind(on_release=lambda x: self.dismiss())
        main_layout.add_widget(close_btn)

        self.content = main_layout

    def _build_action_buttons(self):
        """构建操作按钮"""
        actions = [
            ("装备", self._on_equip),
            ("强化", self._on_upgrade),
            ("分解", self._on_dismantle),
            ("出售", self._on_sell),
            ("重铸", self._on_recast),
            ("合成", self._on_synthesize),
        ]
        for name, cb in actions:
            btn = Button(text=name, font_size=dp(11))
            btn.bind(on_release=cb)
            self.action_layout.add_widget(btn)

    def _refresh_equipped(self):
        """刷新已装备显示"""
        self.equip_layout.clear_widgets()
        state = self.pet_app.pet_state
        for slot in ("weapon", "armor", "trinket"):
            gear = getattr(state, slot)
            box = BoxLayout(orientation='vertical', spacing=dp(2))
            slot_label = Label(text=SLOT_NAME[slot], size_hint_y=None, height=dp(18),
                               font_size=dp(10), color=(0.5, 0.5, 0.5, 1))
            box.add_widget(slot_label)

            if gear:
                gear_btn = Button(
                    text=f"{gear['name']}\n+{gear.get('upgrade', 0)}",
                    font_size=dp(10),
                    background_color=_rarity_color_tuple(gear['rarity'], 0.7),
                )
                gear_btn.bind(on_release=lambda inst, s=slot: self._on_unequip(s))
            else:
                gear_btn = Button(text="空", font_size=dp(10),
                                  background_color=(0.3, 0.3, 0.3, 0.5))
            box.add_widget(gear_btn)
            self.equip_layout.add_widget(box)

    def _refresh_inventory(self):
        """刷新背包显示"""
        self.inv_grid.clear_widgets()
        state = self.pet_app.pet_state
        for i, gear in enumerate(state.inventory):
            if not isinstance(gear, dict):
                continue
            btn = Button(
                text=f"{gear['name']}\n+{gear.get('upgrade', 0)} {gear['rarity']}",
                size_hint_y=None, height=dp(56),
                font_size=dp(10),
                background_color=_rarity_color_tuple(gear['rarity'], 0.5),
            )
            if i == self._selected_idx:
                # 选中状态
                btn.background_color = _rarity_color_tuple(gear['rarity'], 1.0)
            btn.bind(on_release=lambda inst, idx=i: self._on_select_gear(idx))
            self.inv_grid.add_widget(btn)

        # 填充空格子
        remaining = INV_MAX - len(state.inventory)
        for _ in range(remaining):
            btn = Button(text="空", size_hint_y=None, height=dp(56),
                         font_size=dp(10), background_color=(0.2, 0.2, 0.2, 0.3))
            btn.disabled = True
            self.inv_grid.add_widget(btn)

    def _refresh_all(self):
        """刷新全部显示"""
        state = self.pet_app.pet_state
        self.gold_label.text = f"金币：{state.gold}"
        self.essence_label.text = f"精华：{state.essence}"
        self._refresh_equipped()
        self._refresh_inventory()
        # 保存
        state.save(self.pet_app.pet_id)

    def _on_select_gear(self, idx):
        """选中背包中的装备"""
        self._selected_idx = idx
        state = self.pet_app.pet_state
        gear = state.inventory[idx] if idx < len(state.inventory) else None
        if gear:
            self.tip_label.text = (
                f"已选：{gear['name']}·{gear['rarity']} "
                f"（{SLOT_NAME.get(gear['slot'], '?')}，{gear.get('set', '无')}套装）"
            )
            self.tip_label.color = _rarity_color_tuple(gear['rarity'])
        self._refresh_inventory()

    def _on_equip(self, instance):
        """装备选中的背包装备"""
        if self._selected_idx < 0:
            self.tip_label.text = "请先选择背包装备"
            return
        state = self.pet_app.pet_state
        gear = state.inventory[self._selected_idx]
        # 先从背包移除
        state.inventory.pop(self._selected_idx)
        success, msg = game_logic.equip_gear(state, gear)
        self.tip_label.text = msg
        self._selected_idx = -1
        self._refresh_all()

    def _on_unequip(self, slot):
        """卸下已装备的装备"""
        state = self.pet_app.pet_state
        success, gear, msg = game_logic.unequip_gear(state, slot)
        self.tip_label.text = msg
        self._refresh_all()

    def _on_upgrade(self, instance):
        """强化选中的装备"""
        if self._selected_idx < 0:
            self.tip_label.text = "请先选择背包装备"
            return
        state = self.pet_app.pet_state
        gear = state.inventory[self._selected_idx]
        lv = gear.get("upgrade", 0)
        cost = UPGRADE_COST + lv * 100

        if state.gold < cost:
            self.tip_label.text = f"金币不足（需 {cost} 金币）"
            return

        new_gear, cost_actual, msg = game_logic.upgrade_gear(gear)
        state.gold -= cost_actual
        state.inventory[self._selected_idx] = new_gear
        self.tip_label.text = msg
        self._refresh_all()

    def _on_dismantle(self, instance):
        """分解选中的装备"""
        if self._selected_idx < 0:
            self.tip_label.text = "请先选择背包装备"
            return
        state = self.pet_app.pet_state
        gear = state.inventory.pop(self._selected_idx)
        essence = game_logic.dismantle_gear(gear)
        state.essence += essence
        self.tip_label.text = f"分解成功！获得 {essence} 精华"
        self._selected_idx = -1
        self._refresh_all()

    def _on_sell(self, instance):
        """出售选中的装备"""
        if self._selected_idx < 0:
            self.tip_label.text = "请先选择背包装备"
            return
        state = self.pet_app.pet_state
        success, gold, msg = game_logic.sell_inventory_gear(state, self._selected_idx)
        self.tip_label.text = msg
        self._selected_idx = -1
        self._refresh_all()

    def _on_recast(self, instance):
        """重铸选中的装备（洗套装）"""
        if self._selected_idx < 0:
            self.tip_label.text = "请先选择背包装备"
            return
        state = self.pet_app.pet_state
        gear = state.inventory[self._selected_idx]
        if state.essence < RECAST_COST:
            self.tip_label.text = f"精华不足（需 {RECAST_COST} 精华）"
            return
        new_gear, cost = game_logic.recast_gear(gear)
        state.essence -= cost
        state.inventory[self._selected_idx] = new_gear
        self.tip_label.text = f"重铸成功！新套装：{new_gear['set']}"
        self._refresh_all()

    def _on_synthesize(self, instance):
        """合成装备（消耗精华）"""
        state = self.pet_app.pet_state
        if state.essence < SYNTH_COST:
            self.tip_label.text = f"精华不足（需 {SYNTH_COST} 精华）"
            return
        if len(state.inventory) >= INV_MAX:
            self.tip_label.text = "背包已满，无法合成"
            return
        gear, cost, msg = game_logic.synthesize_gear(state.essence)
        state.essence -= cost
        if gear:
            state.inventory.append(gear)
            game_logic.collect_gear(state, gear)
        self.tip_label.text = msg
        self._refresh_all()


# ============================================================
#  签到弹窗
# ============================================================

class SigninPopup(Popup):
    """签到弹窗：每日签到"""

    def __init__(self, pet_app, **kwargs):
        super().__init__(**kwargs)
        self.pet_app = pet_app
        self.title = "每日签到"
        self.size_hint = (None, None)
        self.size = (dp(340), dp(320))
        self.auto_dismiss = True
        self.title_size = dp(16)

        self._build_ui()

    def _build_ui(self):
        """构建界面"""
        state = self.pet_app.pet_state
        import time as _time
        today = _time.strftime("%Y-%m-%d")
        signed = state.last_signin == today

        layout = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))

        # 日期显示
        date_label = Label(
            text=f"日期：{today}",
            size_hint_y=None, height=dp(24),
            font_size=dp(13),
        )
        layout.add_widget(date_label)

        # 连续签到
        self.streak_label = Label(
            text=f"连续签到：{state.signin_streak} 天",
            size_hint_y=None, height=dp(28),
            font_size=dp(15), bold=True,
            color=(1, 0.7, 0.2, 1),
        )
        layout.add_widget(self.streak_label)

        # 签到状态
        self.status_label = Label(
            text="今日已签到" if signed else "今日未签到",
            size_hint_y=None, height=dp(24),
            font_size=dp(13),
            color=(0.3, 0.8, 0.3, 1) if signed else (0.8, 0.3, 0.3, 1),
        )
        layout.add_widget(self.status_label)

        # 奖励说明
        reward_text = (
            f"基础奖励：{SIGNIN_BASE} 金币\n"
            f"连续加成：+5 金币/天\n"
            f"当前可领：{SIGNIN_BASE + max(0, state.signin_streak) * 5} 金币"
        )
        reward_label = Label(
            text=reward_text,
            size_hint_y=None, height=dp(60),
            font_size=dp(12), halign='center', valign='middle',
        )
        layout.add_widget(reward_label)

        # 签到按钮
        self.signin_btn = Button(
            text="签到",
            size_hint_y=None, height=dp(44),
            font_size=dp(15), bold=True,
            background_color=(0.2, 0.7, 0.3, 1),
        )
        self.signin_btn.bind(on_release=self._on_signin)
        self.signin_btn.disabled = signed
        layout.add_widget(self.signin_btn)

        # 结果显示
        self.result_label = Label(
            text="",
            size_hint_y=None, height=dp(28),
            font_size=dp(12), color=(0.2, 0.7, 0.2, 1),
        )
        layout.add_widget(self.result_label)

        # 关闭按钮
        close_btn = Button(text="关闭", size_hint_y=None, height=dp(36),
                           font_size=dp(13))
        close_btn.bind(on_release=lambda x: self.dismiss())
        layout.add_widget(close_btn)

        self.content = layout

    def _on_signin(self, instance):
        """签到"""
        state = self.pet_app.pet_state
        success, reward, streak, msg = game_logic.daily_signin(state)

        if success:
            self.result_label.text = f"签到成功！金币 +{reward}"
            self.result_label.color = (0.2, 0.8, 0.3, 1)
            self.streak_label.text = f"连续签到：{streak} 天"
            self.status_label.text = "今日已签到"
            self.status_label.color = (0.3, 0.8, 0.3, 1)
            self.signin_btn.disabled = True
        else:
            self.result_label.text = msg
            self.result_label.color = (0.8, 0.3, 0.3, 1)

        # 保存
        state.save(self.pet_app.pet_id)


# ============================================================
#  成就弹窗
# ============================================================

class AchievementPopup(Popup):
    """成就弹窗：查看所有成就"""

    def __init__(self, pet_app, **kwargs):
        super().__init__(**kwargs)
        self.pet_app = pet_app
        self.title = "成就"
        self.size_hint = (None, None)
        self.size = (dp(380), dp(480))
        self.auto_dismiss = True
        self.title_size = dp(16)

        self._build_ui()

    def _build_ui(self):
        """构建界面"""
        state = self.pet_app.pet_state
        total = len(ACHIEVEMENTS)
        done = len(state.achieves)

        layout = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(6))

        # 顶部统计
        stats_label = Label(
            text=f"已达成：{done} / {total}",
            size_hint_y=None, height=dp(28),
            font_size=dp(14), bold=True,
            color=(1, 0.8, 0.2, 1),
        )
        layout.add_widget(stats_label)

        # 成就列表（滚动）
        scroll = ScrollView(size_hint=(1, 1))
        list_layout = GridLayout(cols=1, spacing=dp(4), size_hint_y=None)
        list_layout.bind(minimum_height=list_layout.setter('height'))

        for key, (name, reward) in ACHIEVEMENTS.items():
            achieved = key in state.achieves
            item = BoxLayout(orientation='horizontal', spacing=dp(6),
                             size_hint_y=None, height=dp(36))

            # 勾选标记
            check = Label(
                text="✓" if achieved else "○",
                size_hint_x=None, width=dp(32),
                font_size=dp(16), bold=True,
                color=(0.2, 0.8, 0.3, 1) if achieved else (0.6, 0.6, 0.6, 1),
            )
            item.add_widget(check)

            # 名称
            name_label = Label(
                text=name,
                font_size=dp(12),
                halign='left', valign='middle',
                color=(1, 1, 1, 1) if achieved else (0.7, 0.7, 0.7, 1),
            )
            name_label.bind(size=lambda l, v: setattr(l, 'text_size', v))
            item.add_widget(name_label)

            # 奖励
            reward_label = Label(
                text=f"{reward}金",
                size_hint_x=None, width=dp(50),
                font_size=dp(11),
                color=(1, 0.8, 0.2, 1) if not achieved else (0.5, 0.5, 0.5, 1),
            )
            item.add_widget(reward_label)

            list_layout.add_widget(item)

        scroll.add_widget(list_layout)
        layout.add_widget(scroll)

        # 关闭按钮
        close_btn = Button(text="关闭", size_hint_y=None, height=dp(38),
                           font_size=dp(14))
        close_btn.bind(on_release=lambda x: self.dismiss())
        layout.add_widget(close_btn)

        self.content = layout


# ============================================================
#  宠物选择弹窗
# ============================================================

class PetSelectPopup(Popup):
    """宠物选择弹窗：选择宠物和皮肤"""

    def __init__(self, pet_app, **kwargs):
        super().__init__(**kwargs)
        self.pet_app = pet_app
        self.title = "更换宠物"
        self.size_hint = (None, None)
        self.size = (dp(400), dp(480))
        self.auto_dismiss = True
        self.title_size = dp(16)

        self._pet_library = load_pet_library()
        self._unlocked = get_unlocked_pets()
        self._selected_pet = pet_app.pet_id
        self._selected_skin = pet_app.pet_skin

        self._build_ui()

    def _build_ui(self):
        """构建界面"""
        layout = BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(6))

        # 当前选择
        current_name = pet_display_name(self._selected_pet)
        self.current_label = Label(
            text=f"当前：{current_name}",
            size_hint_y=None, height=dp(26),
            font_size=dp(13), bold=True,
        )
        layout.add_widget(self.current_label)

        # 可选宠物数量（实时计数，随解锁/同屏增减立即变化）
        self.count_label = Label(
            text="",
            size_hint_y=None, height=dp(22),
            font_size=dp(11), color=(0.30, 0.52, 0.92, 1),
        )
        layout.add_widget(self.count_label)
        self._refresh_count_label()

        # 宠物列表（滚动）
        scroll = ScrollView(size_hint=(1, 1))
        self.pet_grid = GridLayout(cols=2, spacing=dp(6), size_hint_y=None)
        self.pet_grid.bind(minimum_height=self.pet_grid.setter('height'))
        self._refresh_pet_list()
        scroll.add_widget(self.pet_grid)
        layout.add_widget(scroll)

        # 皮肤选择
        skin_bar = BoxLayout(orientation='horizontal', size_hint_y=None,
                             height=dp(36), spacing=dp(6))
        skin_label = Label(text="皮肤：", size_hint_x=None, width=dp(50),
                           font_size=dp(12))
        self.skin_spinner = Spinner(
            text="请先选择宠物",
            font_size=dp(12),
        )
        self.skin_spinner.bind(text=self._on_skin_select)
        skin_bar.add_widget(skin_label)
        skin_bar.add_widget(self.skin_spinner)
        layout.add_widget(skin_bar)

        # 初始加载皮肤
        self._refresh_skin_spinner()

        # 确认按钮
        self.confirm_btn = Button(
            text="确认更换",
            size_hint_y=None, height=dp(40),
            font_size=dp(14), bold=True,
            background_color=(0.2, 0.6, 1, 1),
        )
        self.confirm_btn.bind(on_release=self._on_confirm)
        layout.add_widget(self.confirm_btn)

        # 加入同屏：把选中的宠物再放一只上场（多宠并存）
        self.add_btn = Button(
            text="加入同屏（再来一只）",
            size_hint_y=None, height=dp(36),
            font_size=dp(13), bold=True,
            background_color=(0.24, 0.68, 0.42, 1),
        )
        self.add_btn.bind(on_release=self._on_add)
        layout.add_widget(self.add_btn)

        # 关闭按钮
        close_btn = Button(text="取消", size_hint_y=None, height=dp(36),
                           font_size=dp(13))
        close_btn.bind(on_release=lambda x: self.dismiss())
        layout.add_widget(close_btn)

        self.content = layout

    def _refresh_pet_list(self):
        """刷新宠物列表"""
        self.pet_grid.clear_widgets()
        for pet_id, info in self._pet_library.items():
            unlocked = pet_id in self._unlocked
            name = info.get("name", pet_id)
            unlock_cost = int(info.get("unlock", 0))
            achieve_req = info.get("achieve", "")

            box = BoxLayout(orientation='vertical', spacing=dp(2),
                            size_hint_y=None, height=dp(70))

            if unlocked:
                btn_text = name
                btn_color = (0.2, 0.6, 0.3, 1) if pet_id == self._selected_pet \
                    else (0.3, 0.3, 0.3, 0.8)
                btn = Button(text=btn_text, font_size=dp(12),
                             background_color=btn_color)
                btn.bind(on_release=lambda inst, pid=pet_id: self._on_select_pet(pid))
            else:
                # 未解锁
                cost_text = f"{unlock_cost}金币解锁"
                if achieve_req:
                    achieve_name = ACHIEVEMENTS.get(achieve_req, ("成就", 0))[0]
                    cost_text = f"需成就：{achieve_name}"
                btn_text = f"{name}\n[未解锁] {cost_text}"
                btn = Button(text=btn_text, font_size=dp(10),
                             background_color=(0.4, 0.4, 0.4, 0.5))
                btn.disabled = True

            box.add_widget(btn)
            self.pet_grid.add_widget(box)

    def _refresh_skin_spinner(self):
        """刷新皮肤下拉框"""
        info = self._pet_library.get(self._selected_pet, {})
        skins = info.get("skins", [])
        skin_names = [s.get("name", s.get("id", "")) for s in skins]
        skin_ids = [s.get("id", "default") for s in skins]

        self._skin_id_map = dict(zip(skin_names, skin_ids))

        if skin_names:
            self.skin_spinner.values = skin_names
            # 找到当前皮肤的名称
            current_name = "经典"
            for s in skins:
                if s.get("id") == self._selected_skin:
                    current_name = s.get("name", current_name)
                    break
            self.skin_spinner.text = current_name
        else:
            self.skin_spinner.values = []
            self.skin_spinner.text = "无可用皮肤"

    def _on_select_pet(self, pet_id):
        """选择宠物"""
        if pet_id not in self._unlocked:
            return
        self._selected_pet = pet_id
        # 默认皮肤
        info = self._pet_library.get(pet_id, {})
        skins = info.get("skins", [])
        if skins:
            self._selected_skin = skins[0].get("id", "default")
        self._refresh_pet_list()
        self._refresh_skin_spinner()

        current_name = pet_display_name(pet_id)
        self.current_label.text = f"当前选择：{current_name}"

    def _on_skin_select(self, spinner, text):
        """选择皮肤"""
        skin_id = self._skin_id_map.get(text, "default")
        self._selected_skin = skin_id

    def _refresh_count_label(self):
        """刷新「可选宠物数量」：已解锁可选总数 + 当前同屏可点击数量"""
        try:
            app = getattr(self.pet_app, "app", self.pet_app)
            on_screen = app.onscreen_count()
        except Exception:
            on_screen = 1
        self.count_label.text = "可选宠物数量：%d　·　同屏可点击：%d 只" % (
            len(self._unlocked), on_screen)

    def _on_add(self, instance):
        """加入同屏：把选中的宠物再放一只上场，各自独立操作"""
        app = getattr(self.pet_app, "app", self.pet_app)
        name = pet_display_name(self._selected_pet)
        if len(app.pets) >= MAX_PETS:
            self.current_label.text = "最多同时养 %d 只啦" % MAX_PETS
            return
        if any(p.pet_id == self._selected_pet for p in app.pets):
            self.current_label.text = "「%s」已经在屏幕上啦" % name
            return
        app.spawn_pet(self._selected_pet, self._selected_skin, slot="extra")
        app._save_config()
        self._refresh_count_label()
        self.current_label.text = "已加入同屏：%s" % name

    def _on_confirm(self, instance):
        """确认更换：只把「被长按的那只」换成选中的宠物/皮肤"""
        pet = self.pet_app
        app = getattr(pet, "app", pet)
        pet.apply_pet(self._selected_pet, self._selected_skin)
        try:
            app._save_config()
        except Exception:
            pass
        try:
            app._sync_window_size()
        except Exception:
            pass
        self.dismiss()
        pet.show_bubble("换了个新形象！")


class PetUnit:
    """单只宠物：独立的状态、精灵、移动与交互。

    每只宠物都是独立的 PetUnit 实例——各自一份存档、各自一套精灵帧、
    各自的位置/朝向/状态机、各自的长按计时器与操作菜单。
    点谁就操作谁，彼此不干扰。

    PetUnit 同时充当各弹窗的上下文（弹窗第一个参数）：弹窗里读到的
    ``pet_app.pet_state`` 就是这只宠物自己的存档，
    ``pet_app.show_inventory()`` 打开的也是这只宠物自己的面板。
    """

    def __init__(self, app, pet_id, skin, slot="primary", index=0):
        self.app = app
        self.slot = slot              # primary / second / extra
        self.index = index            # 同屏序号（用于出生错位摆放）
        self.pet_id = pet_id
        self.pet_skin = skin or "default"
        self.pet_name = pet_display_name(self.pet_id)

        # ===== 状态存档（每只宠物一份，互不影响）=====
        self.pet_state = PetState.load(self.pet_id)

        # ===== 精灵帧 =====
        self.frames = self._load_frames()
        self.frame_w, self.frame_h = self._get_frame_size()
        self.win_w = self.frame_w
        self.win_h = self.frame_h + BUBBLE_HEIGHT

        # ===== 屏幕尺寸（跟随 App，屏幕变化时统一刷新）=====
        self.screen_w = app.screen_w
        self.screen_h = app.screen_h

        # ===== 移动状态 =====
        self.edge = EDGE_TOP          # 当前所在边缘
        self.dir = 1                  # +1 顺时针 / -1 逆时针
        self.facing_right = True      # 朝向（True=右，False=左）
        self.move_state = "walk"      # walk / idle / scared
        self.state_time_left = 0      # 状态剩余时间（秒）
        self.speed = BASE_SPEED       # 当前移动速度
        self.anim_index = 0           # 动画帧索引
        self.anim_time = 0            # 动画计时器

        # ===== 内部桌面坐标（左上角，x 从左往右、y 从上往下）=====
        self.win_x = 0.0
        self.win_y = 0.0

        # ===== 交互状态 =====
        self._press_time = 0
        self._long_press_triggered = False
        self._long_press_event = None

        # ===== 专属操作冷却（每只宠物各自计时）=====
        self.special_cd = 0.0

        # ===== 显示控件 =====
        self.pet_widget = PetWidget(self)
        self.pet_widget.set_frame_size(self.frame_w, self.frame_h)
        self.pet_widget.set_pos(0, 0)
        self.reset_place()

    @property
    def title(self):
        """显示名（有昵称优先，与桌面板一致）"""
        nick = getattr(self.pet_state, "nickname", "") or ""
        return nick or self.pet_name

    # ------------------------------------------------------------ 摆位 / 存档
    def reset_place(self):
        """按同屏序号把宠物错开摆在不同边缘，避免重叠导致只有一只点得到"""
        max_x = max(1.0, self.screen_w - self.win_w)
        max_y = max(1.0, self.screen_h - self.win_h)
        n = max(1, int(getattr(self.app, "max_spawn", MAX_PETS)))
        seg = self.screen_w / float(n + 1)
        self.win_x = min(max_x, seg * (self.index + 1) - self.win_w / 2.0)
        if self.index % 2 == 0:
            self.edge = EDGE_TOP
            self.win_y = 0.0
        else:
            self.edge = EDGE_BOTTOM
            self.win_y = float(max_y)
        self.move_state = "walk"
        self.state_time_left = 0
        self.speed = BASE_SPEED
        self.dir = 1 if self.index % 2 == 0 else -1
        self.facing_right = True
        self._update_position()

    def set_screen_size(self, width, height):
        """屏幕尺寸变化时重新夹取位置"""
        self.screen_w = width
        self.screen_h = height
        max_x = max(0.0, self.screen_w - self.win_w)
        max_y = max(0.0, self.screen_h - self.win_h)
        self.win_x = max(0.0, min(self.win_x, max_x))
        self.win_y = max(0.0, min(self.win_y, max_y))
        self._update_position()

    def save(self):
        """保存这只宠物的存档"""
        try:
            self.pet_state.save(self.pet_id)
        except Exception:
            pass

    def apply_pet(self, pet_id, skin):
        """换成另一只宠物/皮肤（只影响本实例，其他宠物不动）"""
        self.save()
        self.pet_id = pet_id
        self.pet_skin = skin or "default"
        self.pet_name = pet_display_name(pet_id)
        self.pet_state = PetState.load(pet_id)
        self.frames = self._load_frames()
        self.frame_w, self.frame_h = self._get_frame_size()
        self.win_w = self.frame_w
        self.win_h = self.frame_h + BUBBLE_HEIGHT
        self.pet_widget.set_frame_size(self.frame_w, self.frame_h)
        self._update_sprite_frame()
        self.set_screen_size(self.screen_w, self.screen_h)

    # ------------------------------------------------------------ 弹窗（主体都是"自己"）
    def show_stats_panel(self):
        StatsPanel(self).open()

    def show_adventure(self):
        AdventurePopup(self).open()

    def show_shop(self):
        ShopPopup(self).open()

    def show_inventory(self):
        InventoryPopup(self).open()

    def show_signin(self):
        SigninPopup(self).open()

    def show_achievement(self):
        AchievementPopup(self).open()

    def show_pet_select(self):
        PetSelectPopup(self).open()

    def quit_app(self):
        """退出整个应用（所有宠物共用一个进程）"""
        self.app.quit_app()

    # ============================================================
    # 精灵帧加载
    # ============================================================
    def _load_frames(self):
        """加载所有精灵帧纹理

        返回 dict: {
            "walk":   ( [normal_textures...], [flip_textures...] ),
            "idle":   ...,
            "scared": ...,
        }
        """
        from kivy.core.image import Image as CoreImage

        base_dir = os.path.join(resource_dir(), "sprites",
                                self.pet_id, self.pet_skin)
        base_dir = os.path.abspath(base_dir)

        # 目录不存在时回退
        if not os.path.isdir(base_dir):
            base_dir = os.path.join(resource_dir(), "sprites",
                                    self.pet_id, "default")
            base_dir = os.path.abspath(base_dir)
            if not os.path.isdir(base_dir):
                base_dir = os.path.join(resource_dir(), "sprites",
                                        "cockroach", "default")
                base_dir = os.path.abspath(base_dir)

        loaded = {}
        for state, frame_names in FRAMES.items():
            normal_frames = []
            flip_frames = []
            for name in frame_names:
                normal_path = os.path.join(base_dir, f"{name}.png")
                flip_path = os.path.join(base_dir, f"{name}_flip.png")

                if os.path.exists(normal_path):
                    ci = CoreImage(normal_path)
                    normal_frames.append(ci.texture)

                if os.path.exists(flip_path):
                    ci = CoreImage(flip_path)
                    flip_frames.append(ci.texture)

            # 确保至少有一帧
            if not normal_frames and not flip_frames:
                # 跳过该状态
                continue
            if not normal_frames:
                normal_frames = flip_frames[:]
            if not flip_frames:
                flip_frames = normal_frames[:]

            loaded[state] = (normal_frames, flip_frames)

        # 确保 walk 状态存在（作为默认）
        if "walk" not in loaded and loaded:
            first_key = list(loaded.keys())[0]
            loaded["walk"] = loaded[first_key]
        if not loaded:
            # 极端情况：什么都没加载到
            loaded = {"walk": ([], []), "idle": ([], []), "scared": ([], [])}

        return loaded

    def _get_frame_size(self):
        """获取精灵帧尺寸（像素）"""
        for state in ("walk", "idle", "scared"):
            if state in self.frames:
                normal, _ = self.frames[state]
                if normal:
                    tex = normal[0]
                    return tex.width, tex.height
        return 64, 64

    # ============================================================
    # 动画系统
    # ============================================================
    def _update_animation(self, dt):
        """动画帧更新回调（约 25 FPS 调用）"""
        self.anim_time += dt
        # 每 4 个 tick 切换一帧（约 6 FPS 的动画播放速度）
        frame_interval = 1.0 / ANIM_FPS * 4

        if self.anim_time >= frame_interval:
            self.anim_time = 0
            self.anim_index += 1

            state_frames = self.frames.get(self.move_state,
                                           self.frames.get("walk", ([], [])))
            normal_frames, flip_frames = state_frames
            frame_list = normal_frames if self.facing_right else flip_frames

            if frame_list:
                self.anim_index %= len(frame_list)

            self._update_sprite_frame()

    def _update_sprite_frame(self):
        """更新精灵显示的当前帧"""
        state_frames = self.frames.get(self.move_state,
                                       self.frames.get("walk", ([], [])))
        normal_frames, flip_frames = state_frames
        frame_list = normal_frames if self.facing_right else flip_frames

        if frame_list:
            idx = self.anim_index % len(frame_list)
            self.pet_widget.update_frame(frame_list[idx])

    # ============================================================
    # 移动系统（沿屏幕边缘行走）
    # ============================================================
    def _update_movement(self, dt):
        """移动逻辑更新回调"""
        # 状态计时
        if self.move_state == "scared":
            self.state_time_left -= dt
            if self.state_time_left <= 0:
                self.move_state = "walk"
                self.speed = BASE_SPEED
                self.anim_index = 0

        if self.move_state == "idle":
            self.state_time_left -= dt
            if self.state_time_left <= 0:
                self.move_state = "walk"
                self.anim_index = 0
            return  # idle 状态不移动

        # 计算位移
        ds = self.speed * dt * self.dir

        # 根据当前边缘更新位置和朝向
        if self.edge == EDGE_TOP:
            self.win_x += ds
            self.facing_right = self.dir > 0
        elif self.edge == EDGE_BOTTOM:
            self.win_x -= ds
            self.facing_right = self.dir < 0
        elif self.edge == EDGE_LEFT:
            self.win_y += ds
            # 上下移动时保持当前朝向
        elif self.edge == EDGE_RIGHT:
            self.win_y -= ds
            # 上下移动时保持当前朝向

        # 检查是否到达边缘端点（转角 / 穿墙）
        self._check_edge_boundary()

        # 随机进入 idle 状态
        if self.move_state == "walk":
            if random.random() < IDLE_CHANCE_PER_SEC * dt:
                self.move_state = "idle"
                self.state_time_left = random.uniform(IDLE_MIN_TIME, IDLE_MAX_TIME)
                self.anim_index = 0

        self._update_position()

    def _check_edge_boundary(self):
        """检查是否到达当前边缘的端点，处理转角或穿墙"""
        max_x = self.screen_w - self.win_w
        max_y = self.screen_h - self.win_h

        if self.edge == EDGE_TOP:
            if self.dir > 0 and self.win_x >= max_x:
                # 右上角
                self.win_x = max_x
                self._handle_corner(from_edge=EDGE_TOP,
                                    cw_edge=EDGE_RIGHT, ccw_edge=EDGE_LEFT)
            elif self.dir < 0 and self.win_x <= 0:
                # 左上角
                self.win_x = 0
                self._handle_corner(from_edge=EDGE_TOP,
                                    cw_edge=EDGE_LEFT, ccw_edge=EDGE_RIGHT)

        elif self.edge == EDGE_BOTTOM:
            # bottom 上 dir>0 是向左走（x 减小）
            if self.dir > 0 and self.win_x <= 0:
                self.win_x = 0
                self._handle_corner(from_edge=EDGE_BOTTOM,
                                    cw_edge=EDGE_LEFT, ccw_edge=EDGE_RIGHT)
            elif self.dir < 0 and self.win_x >= max_x:
                self.win_x = max_x
                self._handle_corner(from_edge=EDGE_BOTTOM,
                                    cw_edge=EDGE_RIGHT, ccw_edge=EDGE_LEFT)

        elif self.edge == EDGE_LEFT:
            if self.dir > 0 and self.win_y >= max_y:
                # 左下角
                self.win_y = max_y
                self._handle_corner(from_edge=EDGE_LEFT,
                                    cw_edge=EDGE_BOTTOM, ccw_edge=EDGE_TOP)
            elif self.dir < 0 and self.win_y <= 0:
                # 左上角
                self.win_y = 0
                self._handle_corner(from_edge=EDGE_LEFT,
                                    cw_edge=EDGE_TOP, ccw_edge=EDGE_BOTTOM)

        elif self.edge == EDGE_RIGHT:
            if self.dir > 0 and self.win_y <= 0:
                # 右上角
                self.win_y = 0
                self._handle_corner(from_edge=EDGE_RIGHT,
                                    cw_edge=EDGE_TOP, ccw_edge=EDGE_BOTTOM)
            elif self.dir < 0 and self.win_y >= max_y:
                # 右下角
                self.win_y = max_y
                self._handle_corner(from_edge=EDGE_RIGHT,
                                    cw_edge=EDGE_BOTTOM, ccw_edge=EDGE_TOP)

    def _handle_corner(self, from_edge, cw_edge, ccw_edge):
        """处理到达角落

        参数:
            from_edge: 来自哪条边
            cw_edge: 顺时针方向下一条边
            ccw_edge: 逆时针方向边（穿墙到对面）
        """
        if random.random() < 0.7:
            # 70% 概率：转弯（沿当前方向继续走）
            self.edge = cw_edge
            self.dir = 1
        else:
            # 30% 概率：穿墙到对面边缘
            self._wrap_around(from_edge)

    def _wrap_around(self, from_edge):
        """穿墙：从一条边消失，从对面边的随机位置出现"""
        max_x = self.screen_w - self.win_w
        max_y = self.screen_h - self.win_h

        if from_edge == EDGE_TOP:
            self.edge = EDGE_BOTTOM
            self.win_y = max_y
            self.win_x = random.uniform(0, max_x)
            self.dir = random.choice([-1, 1])
        elif from_edge == EDGE_BOTTOM:
            self.edge = EDGE_TOP
            self.win_y = 0
            self.win_x = random.uniform(0, max_x)
            self.dir = random.choice([-1, 1])
        elif from_edge == EDGE_LEFT:
            self.edge = EDGE_RIGHT
            self.win_x = max_x
            self.win_y = random.uniform(0, max_y)
            self.dir = random.choice([-1, 1])
        elif from_edge == EDGE_RIGHT:
            self.edge = EDGE_LEFT
            self.win_x = 0
            self.win_y = random.uniform(0, max_y)
            self.dir = random.choice([-1, 1])


    def _update_position(self):
        """把宠物按内部桌面坐标摆到屏幕上

        视口模式（Android / 桌面全屏遮罩）：宠物是布局里的控件，直接改 pos；
        窗口模式（桌面单宠小窗）：整块窗口跟着宠物移动。
        """
        if self.app.viewport_mode:
            kivy_x = int(self.win_x)
            kivy_y = int(self.app.screen_h - self.win_y - self.win_h)
            self.pet_widget.pos = (kivy_x, kivy_y)
        else:
            Window.left = int(self.win_x)
            Window.top = int(self.win_y)

    # ------------------------------------------------------------ 交互
    def hit_test(self, widget, touch):
        """这次点击是否落在这只宠物身上（每只宠物各自命中测试）

        直接用窗口坐标判定精灵矩形，不依赖控件布局是否已完成，
        所以多只宠物各自独立、互不干扰。
        """
        try:
            return self.pet_widget.hit_test(touch.x, touch.y)
        except Exception:
            return False

    def begin_press(self):
        """按下：开始这只宠物自己的长按计时"""
        self._press_time = time.time()
        self._long_press_triggered = False
        if self._long_press_event:
            self._long_press_event.cancel()
        self._long_press_event = Clock.schedule_once(
            self._on_long_press, LONG_PRESS_TIME)

    def cancel_press(self):
        """取消按下状态"""
        if self._long_press_event:
            self._long_press_event.cancel()
            self._long_press_event = None

    def finish_press(self, widget, touch):
        """松手：长按已弹菜单就忽略，否则算一次点击"""
        self.cancel_press()
        if self._long_press_triggered:
            self._long_press_triggered = False
            return True
        if time.time() - self._press_time < LONG_PRESS_TIME:
            if self.hit_test(widget, touch):
                self.on_click()
                return True
        return False

    def on_click(self):
        """点击：只有被点的这只受惊，其他宠物不受影响"""
        self.move_state = "scared"
        self.state_time_left = SCARED_DURATION
        self.speed = BASE_SPEED * SCARED_SPEED_MULT
        self.dir = -self.dir          # 反向逃跑
        self.anim_index = 0
        lines = get_pet_lines(self.pet_id, "click")
        if lines:
            self.show_bubble(random.choice(lines))
        self.pet_state.stats["click"] = self.pet_state.stats.get("click", 0) + 1
        self.pet_state.quest["interact"] = \
            self.pet_state.quest.get("interact", 0) + 1

    def _on_long_press(self, dt):
        """长按：只弹这只宠物自己的操作菜单"""
        self._long_press_triggered = True
        self.show_menu()

    def show_menu(self):
        """这只宠物的操作菜单（菜单里的操作全部作用于它自己）"""
        menu = PetMenuPopup(self)
        menu.open()

    # ============================================================
    # 互动动作
    # ============================================================
    def action_feed(self):
        """喂食动作"""
        state = self.pet_state
        state.hunger = min(100, state.hunger + 20)
        state.stats["feed"] = state.stats.get("feed", 0) + 1
        state.quest["interact"] = state.quest.get("interact", 0) + 1

        # 低饱腹度时好感度提升更多
        if state.hunger < 80:
            state.affinity = min(100, state.affinity + 2)
        else:
            state.affinity = min(100, state.affinity + 1)

        state.mood = min(100, state.mood + 5)

        lines = get_pet_lines(self.pet_id, "feed")
        if lines:
            self.show_bubble(random.choice(lines))

        self._add_exp(3)
        self._check_level_up()

    def action_pet(self):
        """摸头动作"""
        state = self.pet_state
        state.affinity = min(100, state.affinity + 3)
        state.mood = min(100, state.mood + 10)
        state.stats["pet"] = state.stats.get("pet", 0) + 1
        state.quest["interact"] = state.quest.get("interact", 0) + 1

        lines = get_pet_lines(self.pet_id, "pet")
        if lines:
            self.show_bubble(random.choice(lines))

        self._add_exp(3)

    def action_play(self):
        """逗玩动作"""
        state = self.pet_state
        state.mood = min(100, state.mood + 15)
        state.hunger = max(0, state.hunger - 5)  # 玩耍消耗体力
        state.affinity = min(100, state.affinity + 2)
        state.stats["play"] = state.stats.get("play", 0) + 1
        state.quest["interact"] = state.quest.get("interact", 0) + 1

        lines = get_pet_lines(self.pet_id, "play")
        if lines:
            self.show_bubble(random.choice(lines))

        self._add_exp(5)

    def _add_exp(self, amount):
        """增加经验值"""
        self.pet_state.exp += amount
        self._check_level_up()

    def _check_level_up(self):
        """检查是否升级"""
        state = self.pet_state
        while True:
            exp_needed = state.level * 50
            if state.exp < exp_needed or state.level >= 100:
                break
            state.exp -= exp_needed
            state.level += 1
            self.show_bubble(f"升级了！Lv.{state.level}")

    # ============================================================
    # 气泡显示
    # ============================================================
    def show_bubble(self, text, duration=BUBBLE_DURATION):
        """在宠物头顶显示气泡台词"""
        self.pet_widget.show_bubble(text, duration)

    # ============================================================
    # 属性面板
    # ============================================================
    def show_stats_panel(self):
        """显示属性面板弹窗"""
        panel = StatsPanel(self)
        panel.open()

    def show_adventure(self):
        """显示冒险弹窗"""
        popup = AdventurePopup(self)
        popup.open()

    def show_shop(self):
        """显示商店弹窗"""
        popup = ShopPopup(self)
        popup.open()

    def show_inventory(self):
        """显示背包/装备弹窗"""
        popup = InventoryPopup(self)
        popup.open()

    def show_signin(self):
        """显示签到弹窗"""
        popup = SigninPopup(self)
        popup.open()

    def show_achievement(self):
        """显示成就弹窗"""
        popup = AchievementPopup(self)
        popup.open()

    def show_pet_select(self):
        """显示宠物选择弹窗"""
        popup = PetSelectPopup(self)
        popup.open()

    # ============================================================
    # 状态衰减与自动保存
    # ============================================================
    def _decay_hunger(self, dt):
        """饱腹度定时衰减"""
        state = self.pet_state
        state.hunger = max(0, state.hunger - HUNGER_DECAY_AMOUNT)
        state.uptime_ms += int(HUNGER_DECAY_INTERVAL * 1000)

        # 饥饿时偶尔抱怨
        if state.hunger < 20 and random.random() < 0.3:
            lines = get_pet_lines(self.pet_id, "hungry")
            if lines:
                self.show_bubble(random.choice(lines), 1.5)

    def _decay_mood(self, dt):
        """心情定时衰减"""
        state = self.pet_state
        if state.hunger < 30:
            # 饿着的时候心情掉得更快
            state.mood = max(0, state.mood - MOOD_DECAY_AMOUNT * 2)
        else:
            state.mood = max(0, state.mood - MOOD_DECAY_AMOUNT)

        # 心情低落时
        if state.mood < 20 and random.random() < 0.2:
            lines = get_pet_lines(self.pet_id, "sad")
            if lines:
                self.show_bubble(random.choice(lines), 1.5)

    def _auto_save(self, dt):
        """自动保存状态到文件"""
        self.pet_state.save(self.pet_id)


    # ------------------------------------------------------------ 专属操作
    def special_name(self):
        """本宠物的专属操作名（菜单/界面显示用）"""
        return PET_SPECIAL.get(self.pet_id, PET_SPECIAL_DEFAULT)["name"]

    def _update_special(self, dt):
        """专属操作冷却计时（每只宠物各自递减）"""
        if self.special_cd > 0:
            self.special_cd = max(0.0, self.special_cd - dt)

    def action_special(self):
        """释放本宠物的专属操作

        每只宠物有自己的招式名与效果数值，而且只结算到自己身上：
        只加自己的金币/经验/心情、只让自己冲刺，其他宠物完全不受影响。
        """
        info = PET_SPECIAL.get(self.pet_id, PET_SPECIAL_DEFAULT)
        name = info["name"]
        if self.special_cd > 0:
            self.show_bubble("「%s」冷却中（%.1fs）" % (name, self.special_cd))
            return False
        self.special_cd = SPECIAL_CD
        self.move_state = "scared"
        self.state_time_left = info["duration"]
        self.speed = BASE_SPEED * info["speed_mult"]
        self.pet_state.mood = min(100, self.pet_state.mood + info["mood"])
        self.pet_state.gold = self.pet_state.gold + info["gold"]
        self.pet_state.total_gold = self.pet_state.total_gold + info["gold"]
        self._add_exp(info["exp"])
        self.show_bubble("%s·%s！" % (self.pet_name, name))
        return True


class PetApp(App):
    """电子宠物主应用

    负责窗口、宠物集合的编排与调度；每只宠物的行为都在 PetUnit 里。
    支持多只宠物同屏：各自独立点击、独立菜单、独立专属操作、互不干扰。
    """

    def build(self):
        # ===== 设置可写数据目录（Android 上必须）=====
        set_data_dir(self.user_data_dir)

        # ===== 中文字体（必须在建任何 Label 之前）=====
        register_cjk_font()

        # ===== 屏幕尺寸 / 窗口尺寸（摆位要用，先拿到）=====
        # 关键：Windows 高 DPI 下 Kivy 把 Window.size 当"逻辑尺寸"，
        # 写进去的值会被 Metrics.density 放大成物理像素（本机 200% 缩放，
        # 写 3072 实际得到 6144 的窗口 → 窗口变成屏幕两倍大，
        # 宠物全被摆到屏幕外）。而精灵帧尺寸本身就是物理像素，
        # 所以这里统一按物理像素算，窗口尺寸再除回 density，
        # 保证「窗口正好铺满屏幕」且「控件坐标 == 物理像素」。
        self.viewport_mode = IS_ANDROID or DESKTOP_VIEWPORT
        density = max(1.0, float(getattr(Metrics, "density", 1.0) or 1.0))
        self.transparent = False

        if not IS_ANDROID:
            Window.borderless = True
            try:
                Window.topmost = True
            except Exception:
                pass
            if self.viewport_mode:
                phys_w, phys_h = get_screen_size()
                Window.size = (max(1, int(phys_w / density)),
                               max(1, int(phys_h / density)))
                try:
                    Window.left = 0
                    Window.top = 0
                except Exception:
                    pass
                # 整屏遮罩 + 色键透明（否则整块窗口会把桌面盖黑）
                Window.clearcolor = (1, 0, 1, 1)      # 色键底色（洋红）
                self.transparent = enable_desktop_transparency((255, 0, 255))
                if not self.transparent:
                    # 透明没挂上就退化成深色底，至少不会是一屏洋红
                    Window.clearcolor = (0.06, 0.06, 0.09, 1)
            else:
                Window.clearcolor = (0, 0, 0, 0)
                Window.size = (int(dp(160)), int(dp(160)))
            self.screen_w, self.screen_h = self._current_screen_size()
        else:
            Window.clearcolor = (0.1, 0.1, 0.15, 1)
            Window.fullscreen = 'auto'
            self.screen_w, self.screen_h = self._current_screen_size()

        # ===== 根控件 =====
        # 用纯 Widget：根控件不参与布局，子控件（每只宠物、HUD）的 pos
        # 完全由我们自己控制，不会被布局系统重置。
        self.root = Widget(size_hint=(1, 1))

        # ===== 装配宠物集合 =====
        self.pets = []                 # 同屏宠物（后创建的在上层）
        self.max_spawn = MAX_PETS      # 摆位参考值
        self._pressed_pet = None       # 当前被按住的宠物（保证松手正确收尾）
        self.hud = None

        for i, (pet_id, skin, slot) in enumerate(self._load_pet_entries()):
            self.spawn_pet(pet_id, skin, slot=slot, index=i, silent=True)

        # ===== 计数 HUD：可选宠物数量 =====
        self._build_hud()

        # ===== 触摸绑定（统一分发给命中的那只宠物）=====
        self.root.bind(on_touch_down=self._on_touch_down)
        self.root.bind(on_touch_up=self._on_touch_up)
        Window.bind(on_resize=self._on_window_resize)

        # ===== 定时器：统一驱动所有宠物 =====
        Clock.schedule_interval(self._tick_animation, 1.0 / ANIM_FPS)
        Clock.schedule_interval(self._tick_movement, MOVE_TICK_MS / 1000.0)
        Clock.schedule_interval(self._tick_hunger, HUNGER_DECAY_INTERVAL)
        Clock.schedule_interval(self._tick_mood, MOOD_DECAY_INTERVAL)
        Clock.schedule_interval(self._auto_save, SAVE_INTERVAL)
        Clock.schedule_interval(self._refresh_hud, 1.0)

        if not self.viewport_mode:
            self._sync_window_size()
        for pet in self.pets:
            pet._update_sprite_frame()
            pet._update_position()

        Clock.schedule_once(lambda dt: self.show_bubble("点我试试！"), 1.0)
        self._refresh_hud()

        # ===== 窗口尺寸稳定后再校准一次（并重挂透明）=====
        Clock.schedule_once(self._settle_window, 0.4)
        return self.root

    # ------------------------------------------------------------ 窗口
    def _current_screen_size(self):
        """当前可用的活动区域尺寸（控件坐标口径 = 物理像素）

        桌面端以 Windows 报告的物理像素为准（窗口正好铺满屏幕，
        所以两者一致）；Android 端用 Kivy 自己的窗口尺寸。
        """
        if not IS_ANDROID:
            w, h = get_screen_size()
            if w > 200 and h > 200:
                return float(w), float(h)
        try:
            w, h = Window.size
            if w > 200 and h > 200:
                return float(w), float(h)
        except Exception:
            pass
        return float(self.screen_w or 800), float(self.screen_h or 600)

    def _settle_window(self, dt=0):
        """窗口尺寸稳定后重新校准屏幕尺寸、宠物位置与透明色键"""
        w, h = self._current_screen_size()
        if abs(w - self.screen_w) > 2 or abs(h - self.screen_h) > 2:
            self.screen_w, self.screen_h = w, h
            for pet in self.pets:
                pet.set_screen_size(w, h)
        if self.hud is not None and self.viewport_mode:
            self.hud.pos = (dp(10), self.screen_h - dp(58))
            self._raise_hud()
        for pet in self.pets:
            pet._update_position()
        # 窗口尺寸变化会丢掉 WS_EX_LAYERED，这里重挂一次
        if not IS_ANDROID and self.viewport_mode:
            self.transparent = enable_desktop_transparency((255, 0, 255))
            if not self.transparent:
                Window.clearcolor = (0.06, 0.06, 0.09, 1)

    # ============================================================
    # 宠物集合：装配 / 增删 / 计数
    # ============================================================
    def _load_pet_entries(self):
        """读配置得到同屏宠物列表 [(pet_id, skin, slot), ...]

        来源 pet_config.json：
          - "pet" / "skin"           主宠（slot=primary）
          - "second_pet" {pet,skin}  第二只（slot=second）
          - "extra_pets" [{..}, ..]  更多只（slot=extra）
        未解锁的回退到已解锁宠物；同一只宠物只出现一次。
        """
        cfg = {}
        cfg_path = os.path.join(get_data_dir(), "pet_config.json")
        if not os.path.exists(cfg_path):
            cfg_path = os.path.join(resource_dir(), "pet_config.json")
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}

        raw = [(resolve_pet(str(cfg.get("pet", "cockroach"))),
                str(cfg.get("skin", "default")), "primary")]
        sp = cfg.get("second_pet") or {}
        if isinstance(sp, dict) and sp.get("pet"):
            raw.append((resolve_pet(str(sp["pet"])),
                        str(sp.get("skin", "default")), "second"))
        for extra in (cfg.get("extra_pets") or []):
            if isinstance(extra, dict) and extra.get("pet"):
                raw.append((resolve_pet(str(extra["pet"])),
                            str(extra.get("skin", "default")), "extra"))

        entries, seen = [], set()
        for pet_id, skin, slot in raw:
            if pet_id in seen:
                continue          # 同一只宠物不重复同屏
            seen.add(pet_id)
            entries.append((pet_id, skin, slot))
            if len(entries) >= MAX_PETS:
                break
        if not entries:
            entries.append(("cockroach", "default", "primary"))
        return entries

    def spawn_pet(self, pet_id, skin, slot="extra", index=None, silent=False):
        """新增一只宠物到屏幕（各自独立实例）"""
        if len(self.pets) >= MAX_PETS:
            if not silent:
                self.show_bubble("最多同时养 %d 只哦" % MAX_PETS)
            return None
        if index is None:
            index = len(self.pets)
        self.max_spawn = max(self.max_spawn, index + 1)
        pet = PetUnit(self, resolve_pet(pet_id), skin, slot=slot, index=index)
        self.pets.append(pet)
        self._refresh_hud()
        if not silent:
            pet.show_bubble("我来啦！")
        return pet

    def remove_pet(self, pet):
        """让一只宠物离场（只移除它自己，其他宠物照常活动）"""
        if pet not in self.pets:
            return False
        if len(self.pets) <= 1:
            self.show_bubble("至少留一只陪你呀")
            return False
        pet.save()
        pet.cancel_press()
        pet.pet_widget.remove_me()
        self.pets.remove(pet)
        self._refresh_hud()
        return True

    def available_count(self):
        """当前可选宠物总数（已解锁、可被选中上场的宠物）"""
        try:
            lib = load_pet_library()
            unlocked = get_unlocked_pets()
            return len([p for p in lib if p in unlocked])
        except Exception:
            return len(self.pets)

    def onscreen_count(self):
        """当前同屏、可独立点击操作的宠物数量"""
        return len(self.pets)

    def _save_config(self):
        """把同屏宠物写回 pet_config.json（主宠 + 第二只 + 更多只）"""
        try:
            path = os.path.join(get_data_dir(), "pet_config.json")
            cfg = {}
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                except Exception:
                    cfg = {}
            if self.pets:
                cfg["pet"] = self.pets[0].pet_id
                cfg["skin"] = self.pets[0].pet_skin
            if len(self.pets) >= 2:
                cfg["second_pet"] = {"pet": self.pets[1].pet_id,
                                     "skin": self.pets[1].pet_skin}
            else:
                cfg.pop("second_pet", None)
            extras = [{"pet": p.pet_id, "skin": p.pet_skin}
                      for p in self.pets[2:]]
            if extras:
                cfg["extra_pets"] = extras
            else:
                cfg.pop("extra_pets", None)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ============================================================
    # 计数 HUD：可选宠物数量（实时）
    # ============================================================
    def _build_hud(self):
        """左上角计数标签：可选宠物数量 + 同屏可点击数量"""
        self.hud = Label(
            text="",
            size_hint=(None, None),
            size=(dp(196), dp(46)),
            font_size=dp(12),
            bold=True,
            halign="left",
            valign="middle",
            color=(1, 1, 1, 1) if (IS_ANDROID or self.viewport_mode)
            else (0.12, 0.12, 0.14, 1),
            padding=(dp(8), dp(4)),
        )
        with self.hud.canvas.before:
            # 桌面端是色键透明遮罩，半透明背景会混出底色，所以用不透明
            self._hud_bg_color = Color(0.10, 0.11, 0.16, 1)                 if (IS_ANDROID or self.viewport_mode) else Color(1, 1, 1, 1)
            self._hud_bg = Rectangle(pos=(0, 0), size=(0, 0))
        self.hud.bind(pos=self._sync_hud_bg, size=self._sync_hud_bg)
        if self.viewport_mode:
            self.hud.pos = (dp(10), self.screen_h - dp(58))
        else:
            self.hud.pos = (dp(4), dp(4))
            self.hud.size = (dp(150), dp(34))
        self.root.add_widget(self.hud)
        self._refresh_hud()

    def _sync_hud_bg(self, instance, value):
        self._hud_bg.pos = instance.pos
        self._hud_bg.size = instance.size

    def _raise_hud(self):
        """HUD 始终压在最上层"""
        if self.hud is None:
            return
        try:
            self.root.remove_widget(self.hud)
            self.root.add_widget(self.hud)
        except Exception:
            pass

    def _refresh_hud(self, dt=0):
        """刷新「可选宠物数量」（宠物增减/解锁后立刻反映）

        第一行就是"可选宠物数量"这个计数本身（当前可选/可上场的宠物总数），
        第二行补充同屏可点的数量，方便一眼看出多宠是否都生效。
        """
        if self.hud is None:
            return
        self.hud.text = "可选宠物数量：%d\n同屏可点 %d 只（最多 %d 只）" % (
            self.available_count(), self.onscreen_count(), MAX_PETS)

    # ============================================================
    # 触摸分发：点谁操作谁
    # ============================================================
    def _on_touch_down(self, widget, touch):
        """把点击分发给命中的那只宠物（上层优先）"""
        for pet in reversed(self.pets):
            if pet.hit_test(widget, touch):
                self._raise_pet(pet)          # 点中的宠物提到最上层
                self._pressed_pet = pet
                pet.begin_press()
                return True
        return False

    def _on_touch_up(self, widget, touch):
        """松手：交回给按下的那只宠物处理（多宠之间不串台）"""
        pet = self._pressed_pet
        self._pressed_pet = None
        if pet is None:
            for p in self.pets:
                p.cancel_press()
            return False
        return pet.finish_press(widget, touch)

    def _raise_pet(self, pet):
        """把某只宠物提到最上层（不改动其他宠物的状态）"""
        try:
            pet.pet_widget.raise_me()
        except Exception:
            pass
        self._raise_hud()

    def _on_window_resize(self, instance, width, height):
        """窗口尺寸变化：所有宠物一起重新夹取位置

        桌面整屏遮罩下窗口尺寸就是屏幕尺寸；窗口刚创建时的中间态尺寸
        （比如 160x160）不能拿来当屏幕用，小于 200 的一律忽略。
        """
        if width < 200 or height < 200:
            return
        if not IS_ANDROID and self.viewport_mode:
            sw, sh = get_screen_size()
            if sw > 200 and sh > 200:
                # 桌面端始终以物理屏幕为准，防止高 DPI 的中途事件把尺寸带偏
                width, height = sw, sh
        self.screen_w, self.screen_h = float(width), float(height)
        for pet in self.pets:
            pet.set_screen_size(width, height)
        if self.hud is not None and self.viewport_mode:
            self.hud.pos = (dp(10), height - dp(58))
            self._raise_hud()

    # ============================================================
    # 定时调度：统一驱动所有宠物
    # ============================================================
    def _tick_animation(self, dt):
        for pet in list(self.pets):
            pet._update_animation(dt)

    def _tick_movement(self, dt):
        for pet in list(self.pets):
            pet._update_movement(dt)
            pet._update_special(dt)

    def _tick_hunger(self, dt):
        for pet in list(self.pets):
            pet._decay_hunger(dt)

    def _tick_mood(self, dt):
        for pet in list(self.pets):
            pet._decay_mood(dt)

    def _auto_save(self, dt):
        for pet in list(self.pets):
            pet.save()

    # ============================================================
    # 便捷代理：默认作用于"最近被按住的那只"
    # ============================================================
    def active_pet(self):
        return self._pressed_pet or (self.pets[0] if self.pets else None)

    def show_bubble(self, text, duration=BUBBLE_DURATION):
        pet = self.active_pet()
        if pet is not None:
            pet.show_bubble(text, duration)

    def _sync_window_size(self):
        """（仅桌面小窗模式）让窗口尺寸跟上当前宠物"""
        if self.viewport_mode:
            return
        pet = self.active_pet()
        if pet is None:
            return
        Window.size = (pet.win_w, pet.win_h)
        try:
            self.root.size = (pet.win_w, pet.win_h)
        except Exception:
            pass

    def show_stats_panel(self):
        pet = self.active_pet()
        if pet:
            StatsPanel(pet).open()

    def show_adventure(self):
        pet = self.active_pet()
        if pet:
            AdventurePopup(pet).open()

    def show_shop(self):
        pet = self.active_pet()
        if pet:
            ShopPopup(pet).open()

    def show_inventory(self):
        pet = self.active_pet()
        if pet:
            InventoryPopup(pet).open()

    def show_signin(self):
        pet = self.active_pet()
        if pet:
            SigninPopup(pet).open()

    def show_achievement(self):
        pet = self.active_pet()
        if pet:
            AchievementPopup(pet).open()

    def show_pet_select(self):
        pet = self.active_pet()
        if pet:
            PetSelectPopup(pet).open()

    # ============================================================
    # 退出
    # ============================================================
    def quit_app(self):
        """退出应用：保存所有宠物的存档"""
        self.save_all()
        self.stop()

    def save_all(self):
        for pet in list(self.pets):
            pet.save()

    def on_stop(self):
        self.save_all()
        super().on_stop()


def main():
    """程序入口"""
    PetApp().run()


if __name__ == "__main__":
    main()
