# -*- coding: utf-8 -*-
"""
桌面宠物 · 精灵图处理脚本（多宠物 + 多皮肤版）

功能：
  1. 从 pet_library.json 读取宠物库（每只宠物一张 2 行 x 4 列白底精灵图）
  2. 每款皮肤 = 程序化 HSV 染色（纯白高光像素保持不变，避免白点被染色）
  3. 按网格切出 8 帧动画（行走 x4 / 待机 x2 / 受惊 x2），自动抠除白底
  4. 输出【透明背景】PNG（含左右镜像版），可直接用于动画调用
  5. 另生成【品红键色底】版本，供 tkinter 透明窗口直接显示（程序运行时无需 Pillow）
  6. 生成总览预览图 sprite_preview_all.png（宠物 x 皮肤 网格）

用法：
  python make_sprites.py

输出：
  sprites/<宠物>/<皮肤>/          透明背景帧（含 _flip 镜像版）
  sprites_display/<宠物>/<皮肤>/  品红键色底帧（显示用）
  sprite_preview_all.png         总览预览图
"""
import os
import json
import shutil
import colorsys
from collections import deque
from PIL import Image, ImageOps, ImageFont, ImageDraw

BASE = os.path.dirname(os.path.abspath(__file__))
LIB_JSON = os.path.join(BASE, "pet_library.json")
OUT_TRANS = os.path.join(BASE, "sprites")
OUT_DISPLAY = os.path.join(BASE, "sprites_display")
ROWS, COLS = 2, 4
INSET = 0.015          # 每格四周向内收缩比例，避免切到相邻格
PAD = 14               # 内容外扩边距（像素）
CANVAS_MARGIN = 1.16   # 公共画布相对最大内容的倍率
DISPLAY_MAX = 220      # 显示用帧的最大边长（像素）
KEY = (255, 0, 255)    # 品红键色
WHITE_TH = 246         # 高于此值视为纯白高光，染色时保持不变

NAMES = [
    ["walk_1", "walk_2", "walk_3", "walk_4"],
    ["idle_1", "idle_2", "scared_1", "scared_2"],
]


def is_bg_px(r, g, b):
    """纯白背景判定（带容差）"""
    return r >= 236 and g >= 236 and b >= 236 and max(r, g, b) - min(r, g, b) <= 24


def bg_mask(img):
    """从四边向内 BFS，标记与边缘连通的白色背景区域（保留主体内部的白色高光）"""
    w, h = img.size
    px = img.load()
    mask = [[False] * w for _ in range(h)]
    dq = deque()
    for x in range(w):
        for y in (0, h - 1):
            if not mask[y][x] and is_bg_px(*px[x, y][:3]):
                mask[y][x] = True
                dq.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if not mask[y][x] and is_bg_px(*px[x, y][:3]):
                mask[y][x] = True
                dq.append((x, y))
    while dq:
        x, y = dq.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < w and 0 <= ny < h and not mask[ny][nx] and is_bg_px(*px[nx, ny][:3]):
                mask[ny][nx] = True
                dq.append((nx, ny))
    return mask


def cut_frame(img, mask):
    """把一格抠成透明 RGBA：背景 alpha=0，边缘一圈半透明柔化，并按内容裁剪+外扩"""
    w, h = img.size
    px = img.load()
    alpha = [[255] * w for _ in range(h)]

    for y in range(h):
        for x in range(w):
            if mask[y][x]:
                alpha[y][x] = 0

    # 第一圈：紧贴背景的像素——近白的是抠图残留白边/光晕，直接清掉；其余设为半透明
    for y in range(h):
        for x in range(w):
            if alpha[y][x] != 255:
                continue
            for ny in range(max(0, y - 1), min(h, y + 2)):
                for nx in range(max(0, x - 1), min(w, x + 2)):
                    if mask[ny][nx]:
                        r, g, b = px[x, y][:3]
                        alpha[y][x] = 0 if min(r, g, b) > 215 else 110
                        break
                if alpha[y][x] != 255:
                    break
    # 第二圈：再柔化一层
    for y in range(h):
        for x in range(w):
            if alpha[y][x] != 255:
                continue
            for ny in range(max(0, y - 2), min(h, y + 3)):
                for nx in range(max(0, x - 2), min(w, x + 3)):
                    if 0 <= ny < h and 0 <= nx < w and alpha[ny][nx] == 110:
                        alpha[y][x] = 200
                        break
                if alpha[y][x] == 200:
                    break

    # 内容包围盒
    min_x, min_y, max_x, max_y = w, h, -1, -1
    for y in range(h):
        row = alpha[y]
        for x in range(w):
            if row[x] > 0:
                if x < min_x: min_x = x
                if x > max_x: max_x = x
                if y < min_y: min_y = y
                if y > max_y: max_y = y
    if max_x < 0:
        return None
    min_x = max(0, min_x - PAD)
    min_y = max(0, min_y - PAD)
    max_x = min(w - 1, max_x + PAD)
    max_y = min(h - 1, max_y + PAD)

    rgba = img.crop((min_x, min_y, max_x + 1, max_y + 1)).convert("RGBA")
    a_layer = Image.new("L", (max_x - min_x + 1, max_y - min_y + 1))
    a_layer.putdata([alpha[y][x] for y in range(min_y, max_y + 1) for x in range(min_x, max_x + 1)])
    rgba.putalpha(a_layer)
    return rgba


def split_sheet(sheet_path):
    im = Image.open(sheet_path).convert("RGB")
    w, h = im.size
    cw, ch = w // COLS, h // ROWS
    frames = []
    for r in range(ROWS):
        row = []
        for c in range(COLS):
            x0 = int(c * cw + cw * INSET)
            y0 = int(r * ch + ch * INSET)
            x1 = int((c + 1) * cw - cw * INSET)
            y1 = int((r + 1) * ch - ch * INSET)
            cell = im.crop((x0, y0, x1, y1))
            mask = bg_mask(cell)
            frame = cut_frame(cell, mask)
            if frame is None:
                raise RuntimeError("%s 第 %d 行 %d 列未检测到内容" % (os.path.basename(sheet_path), r + 1, c + 1))
            row.append(frame)
        frames.append(row)
    return frames


def normalize(frames):
    """把所有帧放到同一大小的透明画布上（居中）"""
    sizes = [(f.width, f.height) for row in frames for f in row]
    max_w = max(s[0] for s in sizes)
    max_h = max(s[1] for s in sizes)
    cw = int(max_w * CANVAS_MARGIN)
    ch = int(max_h * CANVAS_MARGIN)
    result = []
    for row in frames:
        out_row = []
        for f in row:
            canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            canvas.paste(f, ((cw - f.width) // 2, (ch - f.height) // 2), f)
            out_row.append(canvas)
        result.append(out_row)
    return result


def recolor(frame, hue=0, sat=1.0, val=1.0, white_th=WHITE_TH):
    """HSV 染色皮肤：纯白高光像素保持原色，其余不透明像素做色相/饱和度/明度变换"""
    if abs(hue) < 0.5 and abs(sat - 1.0) < 0.01 and abs(val - 1.0) < 0.01:
        return frame
    rgba = frame.convert("RGBA")
    px = rgba.load()
    w, h = rgba.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            if r > white_th and g > white_th and b > white_th:
                continue  # 纯白高光保持白色
            hh, ss, vv = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            hh = (hh + hue / 360.0) % 1.0
            ss = min(1.0, ss * sat)
            vv = min(1.0, vv * val)
            nr, ng, nb = colorsys.hsv_to_rgb(hh, ss, vv)
            px[x, y] = (int(nr * 255 + 0.5), int(ng * 255 + 0.5), int(nb * 255 + 0.5), a)
    return rgba


def save_display(frame, path):
    """透明帧 -> 品红键色底显示帧（硬边缘方案，避免光圈）"""
    rgba = frame.convert("RGBA")
    w, h = rgba.size
    px = rgba.load()
    out = Image.new("RGB", (w, h), KEY)
    opx = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a > 128:
                opx[x, y] = (r, g, b)
    for y in range(h):
        for x in range(w):
            r, g, b = opx[x, y]
            if r > 150 and b > 150 and (r + b) / 2 - g > 60:
                opx[x, y] = KEY
    out.save(path)


def _load_font(size):
    for fp in (r"C:\Windows\Fonts\msyh.ttc",
               r"C:\Windows\Fonts\simhei.ttf",
               r"C:\Windows\Fonts\simsun.ttc"):
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return None


def build_preview_all(lib, thumb_cache):
    """总览预览图：行=宠物，列=皮肤，格子内显示 walk_1 帧 + 中文标注"""
    pets = list(lib["pets"].items())
    max_skins = max(len(info["skins"]) for _, info in pets)
    cell = 120
    label_h = 26
    top_h = 34
    pad = 8
    W = pad + max_skins * (cell + pad)
    H = top_h + len(pets) * (cell + label_h + pad) + pad
    preview = Image.new("RGB", (W, H), (245, 245, 245))
    draw = ImageDraw.Draw(preview)
    font = _load_font(16)

    for ci in range(max_skins):
        label = ""
        for pid, info in pets:
            if ci < len(info["skins"]):
                label = info["skins"][ci]["name"]
                break
        if font:
            draw.text((pad + ci * (cell + pad) + 2, 8), label, fill=(26, 27, 28), font=font)

    for ri, (pid, info) in enumerate(pets):
        y0 = top_h + ri * (cell + label_h + pad)
        if font:
            draw.text((pad, y0), info["name"], fill=(26, 27, 28), font=font)
        for ci, skin in enumerate(info["skins"]):
            x0 = pad + ci * (cell + pad)
            frame = thumb_cache[(pid, skin["id"])]
            pane = Image.new("RGBA", (cell, cell), (0, 0, 0, 0))
            f = frame.copy()
            f.thumbnail((cell, cell), Image.LANCZOS)
            pane.paste(f, ((cell - f.width) // 2, (cell - f.height) // 2), f)
            checker = Image.new("RGB", (cell // 2, cell // 2), (255, 255, 255))
            ck = Image.new("RGB", (cell // 2, cell // 2), (232, 232, 232))
            checker.paste(ck, (0, 0)); checker.paste(ck, (cell // 2, cell // 2))
            tile = checker.resize((cell, cell), Image.NEAREST)
            preview.paste(tile, (x0, y0))
            preview.paste(pane, (x0, y0), pane)
            if font:
                draw.text((x0 + 2, y0 + cell - 18), skin["name"],
                          fill=(26, 27, 28), font=_load_font(13))
    preview.save(os.path.join(BASE, "sprite_preview_all.png"))
    print("总览预览图：sprite_preview_all.png")


def main():
    with open(LIB_JSON, "r", encoding="utf-8") as f:
        lib = json.load(f)

    # 清空旧输出，重建新结构
    for d in (OUT_TRANS, OUT_DISPLAY):
        if os.path.isdir(d):
            shutil.rmtree(d)

    thumb_cache = {}
    for pid, info in lib["pets"].items():
        sheet = os.path.join(BASE, info["sheet"])
        print("== 宠物：%s（%s）==" % (info["name"], pid))
        frames = split_sheet(sheet)
        frames = normalize(frames)
        canvas = frames[0][0].size
        print("   帧画布：%dx%d" % canvas)

        for skin in info["skins"]:
            sid = skin["id"]
            # 传说幻彩皮肤：逐帧彩虹（hue 按帧序递进）
            s_frames = []
            for r in range(ROWS):
                row_out = []
                for c in range(COLS):
                    hue = ((r * COLS + c) * 45) if skin.get("rainbow") else skin["hue"]
                    row_out.append(recolor(frames[r][c], hue, skin["sat"], skin["val"]))
                s_frames.append(row_out)
            out_t = os.path.join(OUT_TRANS, pid, sid)
            out_d = os.path.join(OUT_DISPLAY, pid, sid)
            os.makedirs(out_t, exist_ok=True)
            os.makedirs(out_d, exist_ok=True)
            for r in range(ROWS):
                for c in range(COLS):
                    name = NAMES[r][c]
                    f = s_frames[r][c]
                    f.save(os.path.join(out_t, name + ".png"))
                    ImageOps.mirror(f).save(os.path.join(out_t, name + "_flip.png"))
                    display = f
                    if max(display.size) > DISPLAY_MAX:
                        ratio = DISPLAY_MAX / max(display.size)
                        display = display.resize(
                            (max(1, int(display.width * ratio)),
                             max(1, int(display.height * ratio))),
                            Image.LANCZOS)
                    save_display(display, os.path.join(out_d, name + ".png"))
                    save_display(ImageOps.mirror(display), os.path.join(out_d, name + "_flip.png"))
            # 缓存 walk_1 显示帧供总览预览使用
            thumb_cache[(pid, sid)] = s_frames[0][0]
            print("   - 皮肤「%s」生成 16 帧" % skin["name"])

    build_preview_all(lib, thumb_cache)
    print("完成：sprites/、sprites_display/ 已按 宠物/皮肤 目录生成")


if __name__ == "__main__":
    main()
