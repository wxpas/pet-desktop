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
import random
import time

# ========== 平台检测（必须放在最前面）==========
from kivy.utils import platform as kivy_platform
IS_ANDROID = kivy_platform == 'android'

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
from kivy.metrics import dp

# ========== 导入核心模块 ==========
from pet_core.constants import FRAMES, TICK_MS, MOOD_DECAY_MS, \
    AFFINITY_LEVELS, TITLES, RARITY_COLOR, SLOT_NAME, ACHIEVEMENTS, \
    DIFFS, SHOP_COST, SELL_PRICE, UPGRADE_COST, MAX_UPGRADE, INV_MAX, \
    SYNTH_COST, RECAST_COST
from pet_core.utils import load_pet_config, load_pet_library, \
    pet_display_name, get_pet_lines, resolve_pet, resource_dir, \
    get_unlocked_pets, save_pet_config, set_data_dir, IS_ANDROID as UTILS_IS_ANDROID
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

# 边缘定义
EDGE_TOP = "top"
EDGE_RIGHT = "right"
EDGE_BOTTOM = "bottom"
EDGE_LEFT = "left"
EDGES = (EDGE_TOP, EDGE_RIGHT, EDGE_BOTTOM, EDGE_LEFT)


def get_screen_size():
    """获取主屏幕尺寸（像素）"""
    return Window.system_size


class PetWidget(FloatLayout):
    """宠物显示控件（精灵 + 气泡）"""

    def __init__(self, pet_app, **kwargs):
        super().__init__(**kwargs)
        self.pet_app = pet_app
        self.size_hint = (None, None)

        # 宠物精灵
        self.sprite = Image(size_hint=(None, None), fit_mode='contain')
        self.add_widget(self.sprite)

        # 气泡标签
        self.bubble_label = Label(
            text="",
            size_hint=(None, None),
            font_size=dp(12),
            color=(0.2, 0.2, 0.2, 1),
            bold=True,
            padding=(dp(8), dp(4)),
            opacity=0,
        )
        # 气泡背景
        with self.bubble_label.canvas.before:
            self._bubble_border_color = Color(0.6, 0.6, 0.6, 0.9)
            self._bubble_border = Rectangle(pos=(0, 0), size=(0, 0))
            self._bubble_bg_color = Color(1, 1, 1, 0.95)
            self._bubble_bg = Rectangle(pos=(0, 0), size=(0, 0))
        self.bubble_label.bind(pos=self._update_bubble_bg,
                               size=self._update_bubble_bg)
        self.add_widget(self.bubble_label)

        self._bubble_timer = None
        self._frame_w = 64
        self._frame_h = 64

    def _update_bubble_bg(self, instance, value):
        """更新气泡背景矩形的位置和大小"""
        x, y = instance.pos
        w, h = instance.size
        self._bubble_bg.pos = (x + 1, y + 1)
        self._bubble_bg.size = (w - 2, h - 2)
        self._bubble_border.pos = (x, y)
        self._bubble_border.size = (w, h)

    def set_frame_size(self, width, height):
        """设置精灵帧尺寸，并调整整体控件大小"""
        self._frame_w = width
        self._frame_h = height
        self.sprite.size = (width, height)
        self.sprite.pos = (0, BUBBLE_HEIGHT)  # 精灵在底部，上方留气泡空间
        self.size = (width, height + BUBBLE_HEIGHT)

    def update_frame(self, texture):
        """更新精灵帧纹理"""
        self.sprite.texture = texture

    def show_bubble(self, text, duration=BUBBLE_DURATION):
        """显示气泡台词"""
        # 估算文本宽度
        text_w = max(dp(60), len(text) * dp(14) + dp(16))
        text_h = dp(24)
        self.bubble_label.text = text
        self.bubble_label.size = (text_w, text_h)
        self.bubble_label.pos = (
            (self._frame_w - text_w) / 2,
            self._frame_h + BUBBLE_HEIGHT - 4
        )
        self.bubble_label.opacity = 1

        if self._bubble_timer:
            self._bubble_timer.cancel()
        self._bubble_timer = Clock.schedule_once(self._hide_bubble, duration)

    def _hide_bubble(self, dt):
        """隐藏气泡"""
        self.bubble_label.opacity = 0
        self._bubble_timer = None

    def is_point_on_pet(self, x, y):
        """判断点 (x, y) 是否在宠物精灵区域内"""
        # 控件坐标：原点在左下角
        sprite_x0 = self.sprite.x
        sprite_y0 = self.sprite.y
        sprite_x1 = sprite_x0 + self._frame_w
        sprite_y1 = sprite_y0 + self._frame_h
        return sprite_x0 <= x <= sprite_x1 and sprite_y0 <= y <= sprite_y1


class PetMenuPopup(Popup):
    """宠物操作菜单弹窗（两列布局，支持滚动）"""

    def __init__(self, pet_app, **kwargs):
        super().__init__(**kwargs)
        self.pet_app = pet_app
        self.title = "宠物菜单"
        self.size_hint = (None, None)
        self.size = (dp(300), dp(420))
        self.auto_dismiss = True
        self.title_size = dp(16)
        self.separator_height = dp(2)

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

    def _on_confirm(self, instance):
        """确认更换宠物"""
        pet_app = self.pet_app
        pet_id = self._selected_pet
        skin = self._selected_skin

        # 保存当前宠物状态
        pet_app.pet_state.save(pet_app.pet_id)

        # 保存配置到可写数据目录
        save_pet_config(pet_id, skin)

        # 加载新宠物状态
        pet_app.pet_id = pet_id
        pet_app.pet_skin = skin
        pet_app.pet_name = pet_display_name(pet_id)
        pet_app.pet_state = PetState.load(pet_id)

        # 重新加载精灵帧
        pet_app.frames = pet_app._load_frames()
        pet_app.frame_w, pet_app.frame_h = pet_app._get_frame_size()
        pet_app.win_w = pet_app.frame_w
        pet_app.win_h = pet_app.frame_h + BUBBLE_HEIGHT

        if not IS_ANDROID:
            # 桌面端：更新窗口大小
            Window.size = (pet_app.win_w, pet_app.win_h)
            pet_app.root.size = (pet_app.win_w, pet_app.win_h)

        pet_app.pet_widget.set_frame_size(pet_app.frame_w, pet_app.frame_h)
        pet_app._update_sprite_frame()
        pet_app._update_position()

        self.dismiss()
        pet_app.show_bubble("换了个新形象！")


class PetApp(App):
    """电子宠物主应用"""

    def build(self):
        # ===== 设置可写数据目录（Android 上必须）=====
        # Android 上 App.user_data_dir 是应用私有的可写目录
        set_data_dir(self.user_data_dir)

        # ===== 窗口基础设置 =====
        if not IS_ANDROID:
            # 桌面端：透明背景 + 无边框 + 置顶
            Window.clearcolor = (0, 0, 0, 0)  # 透明背景
            Window.borderless = True
            # 尝试置顶（平台相关）
            try:
                Window.topmost = True
            except Exception:
                pass
        else:
            # Android 端：半透明深色背景，全屏显示
            # 透明背景在 Android 上不可行，使用深色半透明背景
            Window.clearcolor = (0.1, 0.1, 0.15, 0.95)
            # 全屏显示
            Window.fullscreen = 'auto'

        # ===== 加载宠物配置 =====
        self.pet_id, self.pet_skin = load_pet_config()
        self.pet_id = resolve_pet(self.pet_id)
        self.pet_name = pet_display_name(self.pet_id)

        # ===== 加载状态 =====
        self.pet_state = PetState.load(self.pet_id)

        # ===== 加载精灵帧 =====
        self.frames = self._load_frames()
        self.frame_w, self.frame_h = self._get_frame_size()
        self.win_w = self.frame_w
        self.win_h = self.frame_h + BUBBLE_HEIGHT

        # ===== 屏幕尺寸 =====
        self.screen_w, self.screen_h = get_screen_size()

        # ===== 移动状态 =====
        self.edge = EDGE_TOP          # 当前所在边缘
        self.dir = 1                  # 移动方向 +1 顺时针 / -1 逆时针
        self.facing_right = True      # 朝向（True=右，False=左）
        self.move_state = "walk"      # walk / idle / scared
        self.state_time_left = 0      # 状态剩余时间（秒）
        self.speed = BASE_SPEED       # 当前移动速度
        self.anim_index = 0           # 动画帧索引
        self.anim_time = 0            # 动画计时器

        # ===== 宠物位置（左上角坐标）=====
        # 内部统一使用"桌面坐标系"：win_x 从左往右，win_y 从上往下
        # 桌面端：直接对应 Window.left / Window.top
        # Android 端：在 _update_position 中转换为 Kivy 坐标（y 从下往上）
        self.win_x = (self.screen_w - self.win_w) / 2
        self.win_y = 0  # 顶部边缘

        # ===== 交互状态 =====
        self._press_time = 0
        self._long_press_triggered = False
        self._long_press_event = None

        # ===== 创建 UI =====
        if not IS_ANDROID:
            # 桌面端：小窗口模式，root 就是窗口大小
            self.root = FloatLayout(size=(self.win_w, self.win_h), size_hint=(None, None))
            self.pet_widget = PetWidget(self)
            self.pet_widget.set_frame_size(self.frame_w, self.frame_h)
            self.pet_widget.pos = (0, 0)
            self.root.add_widget(self.pet_widget)

            # 绑定触摸事件到 root widget
            self.root.bind(on_touch_down=self._on_touch_down)
            self.root.bind(on_touch_up=self._on_touch_up)

            # 设置窗口大小
            Window.size = (self.win_w, self.win_h)
        else:
            # Android 端：全屏模式，root 占满整个屏幕
            self.root = FloatLayout(size_hint=(1, 1))
            self.pet_widget = PetWidget(self)
            self.pet_widget.set_frame_size(self.frame_w, self.frame_h)
            # 设置初始位置
            self.pet_widget.pos = (self.win_x, self.win_y)
            self.root.add_widget(self.pet_widget)

            # 绑定触摸事件到 root widget（全屏都能响应）
            self.root.bind(on_touch_down=self._on_touch_down)
            self.root.bind(on_touch_up=self._on_touch_up)

            # 监听窗口大小变化（屏幕旋转等）
            Window.bind(on_resize=self._on_window_resize)

        # ===== 初始化显示 =====
        self._update_sprite_frame()
        self._update_position()

        # ===== 启动定时器 =====
        # 动画更新
        Clock.schedule_interval(self._update_animation, 1.0 / ANIM_FPS)
        # 移动更新
        Clock.schedule_interval(self._update_movement, MOVE_TICK_MS / 1000.0)
        # 饱腹度衰减
        Clock.schedule_interval(self._decay_hunger, HUNGER_DECAY_INTERVAL)
        # 心情衰减
        Clock.schedule_interval(self._decay_mood, MOOD_DECAY_INTERVAL)
        # 自动保存
        Clock.schedule_interval(self._auto_save, SAVE_INTERVAL)

        # 欢迎气泡
        Clock.schedule_once(lambda dt: self.show_bubble("点我试试！"), 1.0)

        return self.root

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
        """更新宠物位置

        桌面端：移动窗口位置（Window.left / Window.top）
        Android 端：移动 pet_widget 在全屏布局中的位置
        """
        if not IS_ANDROID:
            # 桌面端：Window.left / Window.top 控制窗口位置
            # Kivy 的坐标：top 是从屏幕顶部往下的距离
            Window.left = int(self.win_x)
            Window.top = int(self.win_y)
        else:
            # Android 端：修改 pet_widget 的 pos 属性
            # 内部坐标：win_y 从上往下（桌面坐标系）
            # Kivy 坐标：y 从下往上
            # 转换公式：kivy_y = screen_h - win_y - win_h
            kivy_x = int(self.win_x)
            kivy_y = int(self.screen_h - self.win_y - self.win_h)
            self.pet_widget.pos = (kivy_x, kivy_y)

    def _on_window_resize(self, instance, width, height):
        """窗口大小变化回调（Android 屏幕旋转时触发）

        重新计算屏幕尺寸，并将宠物位置限制在屏幕内。
        """
        self.screen_w = width
        self.screen_h = height
        # 确保宠物在屏幕范围内（内部坐标系）
        max_x = self.screen_w - self.win_w
        max_y = self.screen_h - self.win_h
        self.win_x = max(0, min(self.win_x, max_x))
        self.win_y = max(0, min(self.win_y, max_y))
        self._update_position()

    # ============================================================
    # 交互系统
    # ============================================================
    def _on_touch_down(self, widget, touch):
        """触摸按下事件"""
        if not widget.collide_point(*touch.pos):
            return False
        # 将触摸坐标转换为 pet_widget 本地坐标
        local = self.pet_widget.to_widget(touch.x, touch.y)
        if not self.pet_widget.is_point_on_pet(local[0], local[1]):
            return False

        self._press_time = time.time()
        self._long_press_triggered = False

        # 启动长按计时器
        if self._long_press_event:
            self._long_press_event.cancel()
        self._long_press_event = Clock.schedule_once(
            self._on_long_press, LONG_PRESS_TIME
        )
        return True

    def _on_touch_up(self, widget, touch):
        """触摸释放事件"""
        if self._long_press_event:
            self._long_press_event.cancel()
            self._long_press_event = None

        # 长按已触发则不处理点击
        if self._long_press_triggered:
            self._long_press_triggered = False
            return True

        # 短按 = 点击
        press_duration = time.time() - self._press_time
        if press_duration < LONG_PRESS_TIME:
            if widget.collide_point(*touch.pos):
                local = self.pet_widget.to_widget(touch.x, touch.y)
                if self.pet_widget.is_point_on_pet(local[0], local[1]):
                    self._on_pet_click()
                    return True

        return False

    def _on_pet_click(self):
        """点击宠物：受惊反应"""
        self.move_state = "scared"
        self.state_time_left = SCARED_DURATION
        self.speed = BASE_SPEED * SCARED_SPEED_MULT
        self.dir = -self.dir  # 反向逃跑
        self.anim_index = 0

        # 显示气泡台词
        lines = get_pet_lines(self.pet_id, "click")
        if lines:
            self.show_bubble(random.choice(lines))

        # 统计
        self.pet_state.stats["click"] = self.pet_state.stats.get("click", 0) + 1
        self.pet_state.quest["interact"] = self.pet_state.quest.get("interact", 0) + 1

    def _on_long_press(self, dt):
        """长按宠物：弹出菜单"""
        self._long_press_triggered = True
        self.show_menu()

    def show_menu(self):
        """显示操作菜单"""
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

    # ============================================================
    # 退出
    # ============================================================
    def quit_app(self):
        """退出应用"""
        self.pet_state.save(self.pet_id)
        self.stop()

    def on_stop(self):
        """应用停止回调"""
        if hasattr(self, 'pet_state') and hasattr(self, 'pet_id'):
            try:
                self.pet_state.save(self.pet_id)
            except Exception:
                pass
        super().on_stop()


def main():
    """程序入口"""
    app = PetApp()
    app.run()


if __name__ == "__main__":
    main()
