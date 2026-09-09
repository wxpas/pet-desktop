# -*- coding: utf-8 -*-
"""
宠物控制台 · 启动 / 停止 / 开机自启 / 选择宠物皮肤
================================================
- 「启动宠物」：后台启动宠物（无控制台黑窗）
- 「停止宠物」：结束正在运行的宠物
- 「宠物 / 皮肤」：自由选择宠物与配色皮肤，切换后自动重启宠物生效
- 「开机自启」：登录 Windows 时自动启动宠物
  （写入当前用户的注册表 Run 项，无需管理员权限）

运行方式：
  双击 宠物控制台.bat （推荐，无黑窗）
  或执行：python 宠物控制台.py

注意：若之后移动了整个项目文件夹，自启指向的路径会失效，
     重新打开控制台勾选一次「开机自启」即可。
"""
import os
import sys
import json
import subprocess
import winreg
import tkinter as tk
from tkinter import ttk

APP_NAME = "CockroachPet"                      # 注册表自启项名称
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
BASE = os.path.dirname(os.path.abspath(__file__))
PET_SCRIPT = os.path.join(BASE, "cockroach_pet.py")
BAT_SCRIPT = os.path.join(BASE, "启动电子宠物.bat")
AUTOSTART_VBS = os.path.join(BASE, "开机自启.vbs")
LIB_JSON = os.path.join(BASE, "pet_library.json")
CFG_JSON = os.path.join(BASE, "pet_config.json")

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
STATE_JSON = os.path.join(BASE, "pet_state.json")


def load_pet_library():
    """宠物库：{id: {"name": 中文名, "skins": [...], "unlock": 价格}}"""
    try:
        with open(LIB_JSON, "r", encoding="utf-8") as f:
            return json.load(f).get("pets", {})
    except Exception:
        return {}


def load_unlocked():
    """已解锁宠物集合：unlock==0 初始拥有 + pet_state.json 顶层 _unlocked"""
    unlocked = {"cockroach"}
    try:
        for pid, info in load_pet_library().items():
            if int(info.get("unlock", 0)) == 0:
                unlocked.add(pid)
        with open(STATE_JSON, "r", encoding="utf-8") as f:
            d = json.load(f)
        unlocked |= set(d.get("_unlocked", []))
    except Exception:
        pass
    return unlocked


def unlock_pet(pid, pay_from_pet):
    """用指定宠物的金币解锁新宠物；返回 (ok, msg)"""
    lib = load_pet_library()
    info = lib.get(pid)
    if not info:
        return False, "宠物不存在"
    price = int(info.get("unlock", 0))
    if price <= 0:
        return False, "这只宠物初始就拥有，无需解锁"
    if pid in load_unlocked():
        return False, "「%s」已经解锁啦" % info["name"]
    try:
        with open(STATE_JSON, "r", encoding="utf-8") as f:
            d = json.load(f)
    except Exception:
        d = {}
    acc = dict(d.get(pay_from_pet, {}))
    gold = int(acc.get("gold", 0))
    if gold < price:
        return False, "金币不足：%s 现有 %d / 需 %d" % (
            load_pet_library().get(pay_from_pet, {}).get("name", pay_from_pet),
            gold, price)
    acc["gold"] = gold - price
    d[pay_from_pet] = acc
    unlocked = set(d.get("_unlocked", []))
    unlocked.add(pid)
    d["_unlocked"] = sorted(unlocked)
    with open(STATE_JSON, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    return True, "已解锁「%s」（花费 %d 金币）" % (info["name"], price)


def load_pet_config():
    try:
        with open(CFG_JSON, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return str(cfg.get("pet", "cockroach")), str(cfg.get("skin", "default"))
    except Exception:
        return "cockroach", "default"


def save_pet_config(pet, skin):
    try:
        with open(CFG_JSON, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    cfg["pet"], cfg["skin"] = pet, skin
    with open(CFG_JSON, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def load_second_pet_config():
    """第二只宠物配置：(启用, 宠物id, 皮肤id)"""
    try:
        with open(CFG_JSON, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        sp = cfg.get("second_pet")
        if sp and sp.get("pet"):
            return True, str(sp["pet"]), str(sp.get("skin", "default"))
    except Exception:
        pass
    return False, "", ""


def save_second_pet_config(enabled, pet, skin):
    try:
        with open(CFG_JSON, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    if enabled and pet:
        cfg["second_pet"] = {"pet": pet, "skin": skin or "default"}
    else:
        cfg.pop("second_pet", None)
    with open(CFG_JSON, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _ensure_autostart_vbs():
    """确保隐藏启动器存在且编码正确（VBScript 需按本地 ANSI/GBK 读取，
    若用 UTF-8 写入，中文路径会被解析成乱码）。每次写入以自修复。"""
    content = ("' \u5f00\u673a\u81ea\u542f\u9690\u85cf\u542f\u52a8\u5668\uff1a\u65e0\u7a97\u53e3\u540e\u53f0\u8fd0\u884c \u542f\u52a8\u7535\u5b50\u5ba0\u7269.bat\r\n"
               "Set ws = CreateObject(\"WScript.Shell\")\r\n"
               "ws.Run \"\"\"%s\"\"\", 0, False\r\n" % BAT_SCRIPT)
    with open(AUTOSTART_VBS, "w", encoding="gbk", errors="replace") as f:
        f.write(content)



def pythonw_path():
    """优先用 pythonw.exe（无控制台），退回 python.exe"""
    d = os.path.dirname(sys.executable)
    p = os.path.join(d, "pythonw.exe")
    return p if os.path.exists(p) else sys.executable


def _ps(cmd):
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
        capture_output=True, text=True, creationflags=NO_WINDOW)


def pet_pids():
    """返回正在运行的宠物进程 PID 列表"""
    r = _ps("Get-CimInstance Win32_Process | "
            "Where-Object { $_.CommandLine -like '*cockroach_pet.py*' } | "
            "Where-Object { $_.Name -eq 'pythonw.exe' -or $_.Name -eq 'python.exe' } | "
            "Select-Object -ExpandProperty ProcessId")
    pids = []
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def is_pet_running():
    return len(pet_pids()) > 0


def start_pet():
    if is_pet_running():
        return "已在运行"
    subprocess.Popen([pythonw_path(), PET_SCRIPT], cwd=BASE, creationflags=NO_WINDOW)
    return "已启动"


def stop_pet():
    pids = pet_pids()
    if not pids:
        return "未在运行"
    _ps("Stop-Process -Id %s -Force" % ",".join(str(p) for p in pids))
    return "已停止"


def get_autostart():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
        return True
    except FileNotFoundError:
        return False


def set_autostart(on):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
        if on:
            _ensure_autostart_vbs()
            wscript = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                                   "System32", "wscript.exe")
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ,
                              '"%s" "%s"' % (wscript, AUTOSTART_VBS))
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass


class Console:
    def __init__(self, root):
        self.root = root
        root.title("宠物控制台 · 蟑螂小强")
        root.resizable(False, False)
        root.configure(bg="#F7F6F2")

        f = ("Microsoft YaHei UI", 10)

        self.status = tk.Label(root, text="", font=f, bg="#F7F6F2", fg="#1A1B1C")
        self.status.pack(padx=16, pady=(14, 4), anchor="w")

        self.state = tk.Label(root, text="", font=("Microsoft YaHei UI", 9),
                              bg="#F7F6F2", fg="#6B7280")
        self.state.pack(padx=16, pady=(0, 10), anchor="w")

        btn_row = tk.Frame(root, bg="#F7F6F2")
        btn_row.pack(padx=16, pady=2)
        self.start_btn = tk.Button(btn_row, text="启动宠物", font=f,
                                   width=10, padx=6, pady=4,
                                   bg="#EAF3EC", activebackground="#D8EADB",
                                   relief="groove", bd=1,
                                   command=lambda: self.do(start_pet))
        self.start_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = tk.Button(btn_row, text="停止宠物", font=f,
                                  width=10, padx=6, pady=4,
                                  bg="#FBEAE5", activebackground="#F3D9D2",
                                  relief="groove", bd=1,
                                  command=lambda: self.do(stop_pet))
        self.stop_btn.pack(side="left")

        # ---- 宠物 / 皮肤选择 ----
        sel = tk.Frame(root, bg="#F7F6F2")
        sel.pack(padx=16, pady=(8, 2), fill="x")
        self.pet_ids = []      # 与下拉顺序对应的宠物 id
        self.skin_ids = []     # 当前宠物的皮肤 id（与下拉顺序对应）

        tk.Label(sel, text="宠物", font=f, bg="#F7F6F2", fg="#1A1B1C").pack(side="left")
        self.pet_combo = ttk.Combobox(sel, state="readonly", width=14, font=f)
        self.pet_combo.pack(side="left", padx=(6, 16))
        self.pet_combo.bind("<<ComboboxSelected>>", self.on_pet_change)

        tk.Label(sel, text="皮肤", font=f, bg="#F7F6F2", fg="#1A1B1C").pack(side="left")
        self.skin_combo = ttk.Combobox(sel, state="readonly", width=10, font=f)
        self.skin_combo.pack(side="left", padx=(6, 0))
        self.skin_combo.bind("<<ComboboxSelected>>", self.on_skin_change)

        # ---- 解锁新宠物 ----
        unlock_row = tk.Frame(root, bg="#F7F6F2")
        unlock_row.pack(padx=16, pady=(2, 0), fill="x")
        self.unlock_lbl = tk.Label(unlock_row, text="", font=("Microsoft YaHei UI", 9),
                                   bg="#F7F6F2", fg="#C0392B")
        self.unlock_lbl.pack(side="left")
        self.unlock_btn = tk.Button(unlock_row, text="解锁", font=f, padx=8, pady=1,
                                    relief="groove", bd=1, bg="#FFF3D6",
                                    activebackground="#F5E3B3",
                                    state="disabled", command=self.do_unlock)
        self.unlock_btn.pack(side="left", padx=(8, 0))

        # ---- 第二只宠物 ----
        sp2 = tk.Frame(root, bg="#F7F6F2")
        sp2.pack(padx=16, pady=(8, 2), fill="x")
        sp2_en, _sp2_pet, _sp2_skin = load_second_pet_config()
        self.second_var = tk.BooleanVar(value=sp2_en)
        self.second_chk = tk.Checkbutton(
            sp2, text="第二只宠物", variable=self.second_var, font=f,
            bg="#F7F6F2", activebackground="#F7F6F2",
            command=self.apply_selection)
        self.second_chk.pack(side="left")
        self.second_pet_combo = ttk.Combobox(sp2, state="readonly", width=9, font=f)
        self.second_pet_combo.pack(side="left", padx=(6, 8))
        self.second_pet_combo.bind("<<ComboboxSelected>>",
                                   self.on_second_pet_change)
        self.second_skin_combo = ttk.Combobox(sp2, state="readonly", width=9, font=f)
        self.second_skin_combo.pack(side="left", padx=(6, 0))
        self.second_skin_combo.bind("<<ComboboxSelected>>", self.apply_selection)

        self.auto_var = tk.BooleanVar(value=get_autostart())
        self.auto_chk = tk.Checkbutton(
            root, text="开机自启（登录时自动出现宠物）", variable=self.auto_var,
            font=f, bg="#F7F6F2", activebackground="#F7F6F2", anchor="w",
            command=self.on_auto_toggle)
        self.auto_chk.pack(padx=16, pady=(10, 2), anchor="w")

        hint = tk.Label(root, text="提示：启动后右键点宠物可暂停 / 瞬移 / 退出",
                        font=("Microsoft YaHei UI", 9), bg="#F7F6F2", fg="#9AA0A6")
        hint.pack(padx=16, pady=(2, 6), anchor="w")

        tk.Button(root, text="关闭窗口", font=f, width=14, padx=6, pady=3,
                  relief="groove", bd=1, bg="#FFFFFF", activebackground="#EFEDE8",
                  command=root.destroy).pack(pady=(4, 12))

        self.fill_pets()
        self.fill_second_pets()
        self.refresh()
        root.after(1200, self.auto_refresh)

    # ---- 宠物 / 皮肤选择逻辑 ----
    def fill_pets(self):
        """填充宠物下拉（保留当前选中项；未解锁显示 🔒+价格）"""
        cur_pet, cur_skin = load_pet_config()
        self.library = load_pet_library()
        self.unlocked = load_unlocked()
        names, self.pet_ids = [], []
        for pid, info in self.library.items():
            price = int(info.get("unlock", 0))
            nm = info.get("name", pid)
            if pid not in self.unlocked and price > 0:
                nm += "（🔒%d）" % price
            names.append(nm)
            self.pet_ids.append(pid)
        self.pet_combo["values"] = names
        if cur_pet in self.pet_ids:
            self.pet_combo.current(self.pet_ids.index(cur_pet))
        elif self.pet_ids:
            self.pet_combo.current(0)
        self.cur_skin = cur_skin
        self.fill_skins()
        self.refresh_unlock()

    def refresh_unlock(self):
        """选中未解锁宠物时显示价格和解锁按钮"""
        idx = self.pet_combo.current()
        pid = self.pet_ids[idx] if self.pet_ids and idx >= 0 else None
        if not pid:
            self.unlock_lbl.configure(text="")
            self.unlock_btn.configure(state="disabled")
            return
        if pid in self.unlocked:
            self.unlock_lbl.configure(text="")
            self.unlock_btn.configure(state="disabled")
            return
        price = int(self.library.get(pid, {}).get("unlock", 0))
        # 支付源：当前配置的主宠（已解锁）
        pay = load_pet_config()[0]
        if pay not in self.unlocked:
            pay = "cockroach"
        gold = 0
        try:
            with open(STATE_JSON, "r", encoding="utf-8") as f:
                d = json.load(f)
            gold = int(d.get(pay, {}).get("gold", 0))
        except Exception:
            pass
        name = self.library.get(pay, {}).get("name", pay)
        self.unlock_lbl.configure(text="「%s」未解锁：需 %d 金币（用 %s 的金币支付，现有 %d）"
                                       % (self.library[pid]["name"], price, name, gold))
        self.unlock_btn.configure(state="normal")

    def do_unlock(self):
        """解锁当前选中的未解锁宠物（用当前主宠的金币）"""
        idx = self.pet_combo.current()
        pid = self.pet_ids[idx] if self.pet_ids and idx >= 0 else None
        if not pid or pid in load_unlocked():
            self.refresh_unlock()
            return
        pay = load_pet_config()[0]
        if pay not in load_unlocked():
            pay = "cockroach"
        ok, msg = unlock_pet(pid, pay)
        self.status.configure(text="解锁：%s" % msg)
        if ok:
            self.fill_pets()
            # 自动选中刚解锁的宠物并应用（重启生效）
            self.pet_combo.current(self.pet_ids.index(pid))
            self.cur_skin = "default"
            self.fill_skins()
            self.apply_selection()
            self.refresh_unlock()
        else:
            self.refresh_unlock()
        self.root.after(2600, lambda: self.status.configure(text=""))

    def fill_skins(self):
        """按当前宠物填充皮肤下拉（保留当前皮肤，无效则取第一个）"""
        pid = self.pet_ids[self.pet_combo.current()] if self.pet_ids else None
        skins = self.library.get(pid, {}).get("skins", []) if pid else []
        self.skin_ids = [s["id"] for s in skins]
        names = [s.get("name", s["id"]) for s in skins]
        self.skin_combo["values"] = names
        cur = self.cur_skin if self.cur_skin in self.skin_ids else (self.skin_ids[0] if self.skin_ids else "")
        self.skin_combo.current(self.skin_ids.index(cur) if cur in self.skin_ids else 0)

    def on_pet_change(self, _event=None):
        self.cur_skin = load_pet_config()[1]
        self.fill_skins()
        self.apply_selection()

    def on_skin_change(self, _event=None):
        self.apply_selection()

    # ---- 第二只宠物逻辑 ----
    def fill_second_pets(self):
        sp_en, sp_pet, sp_skin = load_second_pet_config()
        names, self.second_pet_ids = [], []
        for pid, info in self.library.items():
            price = int(info.get("unlock", 0))
            nm = info.get("name", pid)
            if pid not in self.unlocked and price > 0:
                nm += "（🔒%d）" % price
            names.append(nm)
            self.second_pet_ids.append(pid)
        self.second_pet_combo["values"] = names
        if sp_pet in self.second_pet_ids:
            self.second_pet_combo.current(self.second_pet_ids.index(sp_pet))
        elif self.second_pet_ids:
            self.second_pet_combo.current(0)
        self.second_cur_skin = sp_skin
        self.fill_second_skins()

    def fill_second_skins(self):
        idx = self.second_pet_combo.current()
        pid = self.second_pet_ids[idx] if self.second_pet_ids and idx >= 0 else None
        skins = self.library.get(pid, {}).get("skins", []) if pid else []
        self.second_skin_ids = [s["id"] for s in skins]
        names = [s.get("name", s["id"]) for s in skins]
        self.second_skin_combo["values"] = names
        cur = self.second_cur_skin if self.second_cur_skin in self.second_skin_ids \
            else (self.second_skin_ids[0] if self.second_skin_ids else "")
        self.second_skin_combo.current(
            self.second_skin_ids.index(cur) if cur in self.second_skin_ids else 0)

    def on_second_pet_change(self, _event=None):
        idx = self.second_pet_combo.current()
        pid = self.second_pet_ids[idx] if (self.second_pet_ids and idx >= 0) else ""
        if pid and pid not in self.unlocked:
            self.status.configure(text="「%s」未解锁，请先解锁再选（看上面解锁栏）"
                                        % self.library.get(pid, {}).get("name", pid))
            self.root.after(2400, lambda: self.status.configure(text=""))
            sp_en, sp_pet, _ = load_second_pet_config()
            if sp_pet in self.second_pet_ids:
                self.second_pet_combo.current(self.second_pet_ids.index(sp_pet))
            return
        self.second_cur_skin = load_second_pet_config()[2]
        self.fill_second_skins()
        self.apply_selection()

    def apply_selection(self):
        if not self.pet_ids:
            return
        pet = self.pet_ids[self.pet_combo.current()]
        skin = self.skin_ids[self.skin_combo.current()] if self.skin_ids else "default"
        save_pet_config(pet, skin)
        en = self.second_var.get()
        sp_idx = self.second_pet_combo.current()
        sp_pet = self.second_pet_ids[sp_idx] if (self.second_pet_ids and sp_idx >= 0) else ""
        if sp_pet and sp_pet not in self.unlocked:
            sp_pet = ""   # 未解锁不写入配置
            en = False
        sp_skin = self.second_skin_ids[self.second_skin_combo.current()] \
            if (self.second_skin_ids and self.second_skin_combo.current() >= 0) else "default"
        save_second_pet_config(en and bool(sp_pet), sp_pet, sp_skin)
        label = "%s · %s" % (self.library[pet].get("name", pet),
                             self.skin_combo.get())
        if en and sp_pet:
            label += " + 第二只"
        if is_pet_running():
            stop_pet()
            start_pet()
            self.status.configure(text="已切换为 %s，宠物已重启" % label)
        else:
            self.status.configure(text="已保存选择：%s（点「启动宠物」生效）" % label)
        self.root.after(2200, lambda: self.status.configure(text=""))
        self.refresh()

    def do(self, fn):
        msg = fn()
        self.status.configure(text="操作：%s" % msg)
        self.root.after(2000, lambda: self.status.configure(text=""))

    def refresh(self):
        run = is_pet_running()
        auto = get_autostart()
        self.auto_var.set(auto)
        self.start_btn.configure(state="disabled" if run else "normal")
        self.stop_btn.configure(state="normal" if run else "disabled")
        self.state.configure(text="宠物状态：%s　·　自启状态：%s"
                              % ("运行中" if run else "未运行",
                                 "已开启" if auto else "未开启"))

    def auto_refresh(self):
        self.refresh()
        self.root.after(1200, self.auto_refresh)

    def on_auto_toggle(self):
        set_autostart(self.auto_var.get())
        self.refresh()


def main():
    root = tk.Tk()
    Console(root)
    root.mainloop()


if __name__ == "__main__":
    main()
