# -*- coding: utf-8 -*-
"""
宠物核心模块 · 工具函数
============================================================
纯 Python 工具函数集合，不含任何 tkinter / UI 依赖。
图像相关函数依赖 PIL（可选）。
"""
import os
import sys
import json
import math
import random

from .constants import STATE_PATH, PET_LINES, LINES_FALLBACK

# ========== 平台检测 ==========
# 检测当前运行平台，用于区分桌面端和 Android 端
try:
    from kivy.utils import platform as _kivy_platform
    IS_ANDROID = _kivy_platform == 'android'
except Exception:
    # Kivy 不可用时，根据 sys.platform 判断
    IS_ANDROID = False

# ========== 路径管理 ==========
# 可写数据目录（Android 上使用 App.user_data_dir，桌面端默认为脚本目录）
_data_dir = None


def set_data_dir(path):
    """设置可写数据目录（Android 上应在 App.build() 中调用）

    参数:
        path: 可写数据目录的绝对路径
    """
    global _data_dir
    _data_dir = path


def get_data_dir():
    """获取可写数据目录路径

    Android 上需要先通过 set_data_dir() 设置，否则回退到资源目录。
    桌面端默认返回脚本上级目录（与旧行为一致）。

    返回:
        str: 可写数据目录的绝对路径
    """
    global _data_dir
    if _data_dir is not None:
        return _data_dir
    # 桌面端默认：脚本目录的上级（项目根目录）
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def script_dir():
    """返回脚本所在目录的绝对路径（pet_core 目录）

    返回:
        str: 脚本目录路径
    """
    return os.path.dirname(os.path.abspath(__file__))


def resource_dir():
    """返回资源文件根目录（只读资源，如 sprites/、pet_library.json 等）

    桌面端：项目根目录（script_dir 的上级）
    Android 端：APK 资源目录，即项目根目录（与脚本同级打包）

    返回:
        str: 资源根目录的绝对路径
    """
    # 资源文件始终跟随代码包，即项目根目录
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def state_file_path():
    """获取 pet_state.json 的完整路径（可写文件）

    返回:
        str: 状态文件路径
    """
    return os.path.join(get_data_dir(), STATE_PATH)


def tint_golden(img):
    """把 RGBA 图像染成荣耀金（保留白色高光与透明区）

    参数:
        img: PIL.Image 对象（RGBA 或可转为 RGBA 的图像）

    返回:
        PIL.Image: 染色后的 RGBA 图像
    """
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
        from PIL import Image as PILImage
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


def heart_points(cx, cy, size):
    """计算心形轮廓点列表（多边形顶点，不绘制）

    由两个上半圆 + 下方三角组合而成，近似经典爱心形状。
    返回按顺序排列的 (x, y) 坐标点列表，可直接用于绘制多边形。

    参数:
        cx: 心形中心 x 坐标
        cy: 心形中心 y 坐标
        size: 心形大小（半径）

    返回:
        list[tuple[float, float]]: 心形多边形顶点列表
    """
    pts = []
    # 左半圆弧（顶部左半圆，从底部到顶部）
    left_cx = cx - size * 0.675
    left_cy = cy - size * 0.05
    r = size * 0.325
    for i in range(12, -1, -1):
        ang = math.pi + i * math.pi / 12  # 从 π 到 2π（下半圆？不，左半边用 0 到 π）
        # 左半圆：从最下点到最上点，角度从 π 到 0
        ang = i * math.pi / 12  # 0 → π，顺时针
        pts.append((left_cx + r * math.cos(ang),
                    left_cy - r * math.sin(ang)))
    # 右半圆弧（顶部右半圆，从顶部到底部）
    right_cx = cx + size * 0.675
    right_cy = cy - size * 0.05
    for i in range(1, 13):
        ang = math.pi - i * math.pi / 12  # π → 0？不对，应该是 π → 2π
        # 右半圆：从顶部到底部，角度从 π 到 2π（即 0 到 π 取负 y）
        ang = i * math.pi / 12
        pts.append((right_cx + r * math.cos(math.pi - ang),
                    right_cy - r * math.sin(math.pi - ang)))
    # 底部尖点
    pts.append((cx, cy + size * 1.15))
    return pts


def _star_points(cx, cy, R, r):
    """五角星顶点坐标计算（用于饰品图标等）

    参数:
        cx: 中心 x 坐标
        cy: 中心 y 坐标
        R: 外接圆半径（外顶点）
        r: 内接圆半径（内顶点）

    返回:
        list[tuple[float, float]]: 10 个顶点的坐标列表（外内交替）
    """
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rad = R if i % 2 == 0 else r
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    return pts


def script_dir():
    """返回脚本所在目录的绝对路径

    返回:
        str: 脚本目录路径
    """
    return os.path.dirname(os.path.abspath(__file__))


def load_pet_library():
    """加载宠物库 {id: {name, sheet, unlock, skins}}

    读取 pet_library.json 文件（只读资源），返回所有宠物的定义信息。
    文件不存在或读取失败时返回空字典。

    返回:
        dict: 宠物 ID → 宠物信息 的字典
    """
    try:
        with open(os.path.join(resource_dir(), "pet_library.json"), "r",
                  encoding="utf-8") as f:
            return json.load(f).get("pets", {})
    except Exception:
        return {}


def load_pet_config():
    """读取当前选中的宠物与皮肤（pet_config.json）

    优先从可写数据目录读取（用户配置），
    不存在时从资源目录读取默认配置。
    配置文件不存在或读取失败时，回退到默认值 "cockroach" / "default"。

    返回:
        tuple[str, str]: (宠物 ID, 皮肤 ID)
    """
    pet, skin = "cockroach", "default"
    # 优先读取用户配置（可写目录）
    config_path = os.path.join(get_data_dir(), "pet_config.json")
    if not os.path.exists(config_path):
        # 回退到资源目录中的默认配置
        config_path = os.path.join(resource_dir(), "pet_config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        pet = str(cfg.get("pet", pet))
        skin = str(cfg.get("skin", skin))
    except Exception:
        pass
    return pet, skin


def save_pet_config(pet_id, skin_id):
    """保存宠物配置到可写数据目录

    参数:
        pet_id: 宠物 ID
        skin_id: 皮肤 ID
    """
    try:
        config_path = os.path.join(get_data_dir(), "pet_config.json")
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"pet": pet_id, "skin": skin_id}, f,
                      ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_unlocked_pets():
    """获取已解锁宠物集合

    包含两类：
    1. 宠物库中 unlock == 0 的初始拥有宠物
    2. pet_state.json 顶层 _unlocked 列表中的宠物

    返回:
        set[str]: 已解锁宠物 ID 的集合
    """
    unlocked = {"cockroach"}
    try:
        for pid, info in load_pet_library().items():
            if int(info.get("unlock", 0)) == 0:
                unlocked.add(pid)
        with open(state_file_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
        unlocked |= set(d.get("_unlocked", []))
    except Exception:
        pass
    return unlocked


def resolve_pet(pet):
    """配置的宠物未解锁时，回退到第一个已解锁宠物

    用于防止配置被绕过时显示未解锁宠物。

    参数:
        pet: 配置的宠物 ID

    返回:
        str: 实际可用的宠物 ID，都不可用时返回 "cockroach"
    """
    if pet in get_unlocked_pets():
        return pet
    for pid in load_pet_library():
        if pid in get_unlocked_pets():
            return pid
    return "cockroach"


def pet_display_name(pet):
    """获取宠物中文名（从 pet_library.json 中查询）

    查不到时直接返回宠物 ID 本身。

    参数:
        pet: 宠物 ID

    返回:
        str: 宠物中文名
    """
    try:
        with open(os.path.join(resource_dir(), "pet_library.json"), "r", encoding="utf-8") as f:
            lib = json.load(f)
        info = lib.get("pets", {}).get(pet, {})
        return info.get("name", pet)
    except Exception:
        return pet


def get_pet_lines(pet_id, category):
    """获取指定宠物某类别的台词列表

    参数:
        pet_id: 宠物 ID
        category: 台词类别（click / feed / pet / play / hungry / dizzy / greet / sad）

    返回:
        list[str]: 台词列表，找不到时使用回退池
    """
    lines = PET_LINES.get(pet_id, {})
    return lines.get(category, LINES_FALLBACK.get(category, []))
