#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ///M 点我开始插件安装引导 — 自动魔光键影 · 闲鱼沉溺海豚亭
"""
本程序仅做一件事：把「魔光键影」这个本地插件的安装过程，拆成客户能照着点的步骤。

为什么不用安装器自动装：
    魔光键影是作者自己编译的本地 DLL（无公共仓库源），卫月官方推荐的加载方式是
    「开发插件」——在 设置 → 实验性功能 → 开发插件位置 里指定 DLL 的完整路径。
    Dalamud 源码 PluginManager.LoadAllPlugins / ScanDevPluginsAsync 已确认：
        · DevPluginLoadLocations 存的是 DLL 文件路径（new FileInfo），不是文件夹
        · 整段扫描被 configuration.DevMode 包住，开发者模式不开就不加载
        · DLL 同目录必须有同名 .json（manifest），否则报 "has no manifest" 直接跳过

程序职责：
    1. 检测卫月装没装、启动过没有
    2. 把 DLL 复制到一个固定目录（避免客户挪动压缩包后路径失效）
    3. 顺手把配套的 YesAlready 装进卫月（标准仓库插件，可直接落位）
    4. 七步引导，每步点「做好了」往下走
"""

import os
import sys
import shutil
import subprocess
import tkinter as tk

APP_TITLE = "点我开始插件安装引导"
APP_SUB = "自动魔光键影 · 沉溺海豚亭"
VERSION = "1.0"

# ══════════════════════════ 主题 ══════════════════════════

C = {
    "bg":        "#0e1116",
    "sidebar":   "#131720",
    "card":      "#1a2029",
    "card2":     "#212a36",
    "line":      "#2b3542",
    "text":      "#e9eef6",
    "sub":       "#8e9aac",
    "muted":     "#5d6a7c",
    "accent":    "#3b82f6",
    "accent_hi": "#2f6fe0",
    "success":   "#22c55e",
    "warn":      "#f0a020",
    "danger":    "#ef4444",
}

F = "Microsoft YaHei UI" if sys.platform == "win32" else "PingFang SC"

SIDE_W = 268
WIN_W, WIN_H = 900, 700


# ══════════════════════════ 路径与检测 ══════════════════════════

def app_dir():
    """程序所在目录（打包成 exe 后取 exe 所在目录）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _appdata():
    if sys.platform == "win32":
        return os.environ.get("APPDATA", "")
    return os.path.expanduser("~/Library/Application Support")


def _localappdata():
    if sys.platform == "win32":
        return os.environ.get("LOCALAPPDATA", "")
    return os.path.expanduser("~/Library/Application Support")


def dalamud_dirs():
    """返回卫月的配置目录与本地安装目录（国服端）。"""
    cfg = os.path.join(_appdata(), "XIVLauncherCN")
    local = os.path.join(_localappdata(), "XIVLauncherCN")
    return cfg, local


def dll_source():
    """包内自带 DLL 的位置：<exe目录>/魔光键影插件/KeyboundBrawler.dll"""
    return os.path.join(app_dir(), "魔光键影插件", "KeyboundBrawler.dll")


def managed_dir():
    """复制 DLL 的固定目录。用 LOCALAPPDATA 免管理员权限，客户挪包也不影响。"""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~/Library/Application Support")
    return os.path.join(base, "沉溺海豚亭", "魔光键影")


def managed_dll():
    return os.path.join(managed_dir(), "KeyboundBrawler.dll")


def yesalready_src():
    return os.path.join(app_dir(), "XIVLauncherCN", "installedPlugins", "YesAlready")


def detect():
    """检测三方状态，返回 dict。

    installed : 卫月本体是否装过（配置目录或本地目录存在）
    ready     : 是否启动过游戏（存在 dalamudConfig.json 才算卫月已就绪）
    """
    cfg, local = dalamud_dirs()
    cfg_file = os.path.join(cfg, "dalamudConfig.json")
    installed = os.path.isdir(cfg) or os.path.isdir(local)
    ready = os.path.isfile(cfg_file)
    return {
        "installed": installed,
        "ready": ready,
        "cfg_dir": cfg,
        "cfg_file": cfg_file,
        "local_dir": local,
        "has_dll": os.path.isfile(dll_source()),
    }


def open_path(path):
    """用系统默认方式打开文件或文件夹。"""
    try:
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False


def prepare(det):
    """落实文件：复制 DLL 到固定目录 + 装 YesAlready。返回 (ok, 说明)。"""
    log = []

    # ① 复制 DLL（连同 manifest 与 deps 一起，缺 manifest 卫月会拒载）
    src = dll_source()
    if os.path.isfile(src):
        try:
            os.makedirs(managed_dir(), exist_ok=True)
            sdir = os.path.dirname(src)
            for name in os.listdir(sdir):
                if name.startswith("KeyboundBrawler."):
                    shutil.copy2(os.path.join(sdir, name), os.path.join(managed_dir(), name))
            log.append("插件文件已就位")
        except Exception as e:
            return False, "复制插件文件失败：%s" % e
    else:
        return False, "包内找不到 魔光键影插件\\KeyboundBrawler.dll，请重新解压完整压缩包"

    # ② 装 YesAlready（标准插件，直接放进卫月插件目录；已有就覆盖为同版本）
    if det["ready"]:
        ips = os.path.join(det["cfg_dir"], "installedPlugins")
        src_ya = yesalready_src()
        if os.path.isdir(src_ya):
            try:
                os.makedirs(ips, exist_ok=True)
                dst = os.path.join(ips, "YesAlready")
                if os.path.isdir(dst):
                    shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(src_ya, dst)
                log.append("配套插件已安装")
            except Exception:
                log.append("配套插件复制失败（不影响主插件）")

    return True, "；".join(log) if log else "文件已就位"


# ══════════════════════════ 步骤内容 ══════════════════════════

STEPS = [
    {
        "title": "打开游戏，进到人物画面",
        "lead": "先把游戏开起来，后面所有设置都是在游戏里点的。",
        "body": [
            ("li", "双击卫月的启动器，等游戏窗口出来。"),
            ("li", "登录你的账号，进到游戏里，能走动就行。"),
            ("li", "游戏别关，卫月的设置窗口只能在游戏里打开。"),
        ],
        "ok": "看到自己的角色站在地图上 = 成功",
    },
    {
        "title": "在聊天框输入 /xlsettings",
        "lead": "这条命令会把卫月的设置窗口叫出来。",
        "body": [
            ("li", "在游戏里按一下回车键，左下角出现聊天的输入框。"),
            ("li", "输入 /xlsettings"),
            ("li", "再按一次回车。"),
            ("li", "屏幕上会弹出一个大窗口，这就是卫月设置。"),
        ],
        "ok": "看到设置窗口，左边竖着一列标签页 = 成功",
    },
    {
        "title": "打开「实验性功能」，勾上开发者模式",
        "lead": "这一步是开关，不勾后面根本看不到添加插件的地方。",
        "body": [
            ("k", "① 在设置窗口左边的标签里，点「实验性功能」"),
            ("sub", "英文版叫 Experimental，在标签列表靠下的位置。"),
            ("k", "② 页面第一行的勾选框：「启用开发者模式」"),
            ("sub", "英文版叫 Enable Developer Mode。"),
            ("k", "③ 点一下，把它勾上"),
            ("li", "勾上之后，下面会立刻多出一堆新的子选项。"),
        ],
        "ok": "勾上后页面内容变多 = 成功",
        "warn": "不勾这个，下一步的「开发插件位置」压根不会出现——这是最多人卡住的地方。",
    },
    {
        "title": "找到「开发插件位置」，选中 DLL",
        "lead": "这里要选的是文件，不是文件夹。选错了卫月认不到。",
        "body": [
            ("k", "① 同一个页面继续往下滑，找到「开发插件位置」"),
            ("sub", "英文版叫 Dev Plugin Locations，下面有一行灰色小字说明「必须是插件 DLL 的路径」。"),
            ("k", "② 点那个带文件夹图标的按钮「选择开发插件 DLL」"),
            ("sub", "英文版叫 Select Dev Plugin DLL。"),
            ("k", "③ 弹出文件选择框后，把下面这条路径粘进「文件名」栏，回车"),
            ("path", None),
        ],
        "ok": "设置页里多出一行路径，前面带勾 = 成功",
        "warn": "如果文件选择框里点不到文件：先把文件类型那一栏改成「所有文件」，或者直接把路径粘到文件名栏再回车。",
    },
    {
        "title": "确认那一行是「打勾」状态",
        "lead": "路径加上去了还不够，前面那个勾必须亮着，插件才会被加载。",
        "body": [
            ("li", "刚加完的那一行，最前面有个勾选框。"),
            ("li", "点一下确认它是勾上的状态。"),
            ("li", "后面的名字栏可以填「魔光键影」，方便你自己认，不填也不影响。"),
        ],
        "ok": "勾选框是亮的 = 成功",
        "warn": "勾取消掉 = 插件不加载，游戏里怎么找都找不到。",
    },
    {
        "title": "回到游戏，在插件列表里启用",
        "lead": "现在插件已经被卫月认到了，去列表里把它打开。",
        "body": [
            ("li", "关掉设置窗口（窗口右下角的 Close）。"),
            ("li", "聊天框输入 /xlplugins 回车，打开插件列表。"),
            ("li", "在列表里找「魔光键影」。"),
            ("sub", "找不到就往下拉，它在一个叫「开发插件」的分类里。"),
            ("li", "把它前面的勾点上。"),
        ],
        "ok": "「魔光键影」前面的勾是亮的 = 成功",
    },
    {
        "title": "装好了，去金碟开刷",
        "lead": "全部完成。以后每次开游戏它都会自动加载，不用再走这一遍。",
        "body": [
            ("k", "① 聊天框输入 /kb ，打开插件窗口"),
            ("k", "② 去金碟游乐场，走到魔光键影的报名登记员旁边"),
            ("sub", "要站到 4 米以内，站远了它进不去活动。"),
            ("k", "③ 点「启动」开始刷"),
            ("sub", "想刷固定局数，就在「次数」里填数字；填 0 = 一直刷。"),
        ],
        "ok": "角色自己走过去报名、进本、开始答题 = 成功",
        "warn": "自动答题属于自动化功能，有被官方检测的风险，建议人在电脑前看着跑。",
    },
]


# ══════════════════════════ 绘图小工具 ══════════════════════════

def round_rect(cv, x1, y1, x2, y2, r, **kw):
    """在 Canvas 上画圆角矩形，返回 item id。"""
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return cv.create_polygon(pts, smooth=True, **kw)


class Button(tk.Canvas):
    """圆角按钮。style: primary / ghost / subtle"""

    def __init__(self, master, text, command, style="primary", width=180, height=44, bg=None):
        self.style = style
        self.w, self.h = width, height
        self.bg = bg or C["bg"]
        super().__init__(master, width=width, height=height, bg=self.bg,
                         highlightthickness=0, bd=0, cursor="hand2")
        self._enabled = True
        self._label = text
        self._cmd = command
        self._hover = False
        self._draw()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _palette(self):
        s = self.style
        if not self._enabled:
            return C["card2"], C["muted"], C["line"]
        if s == "primary":
            return (C["accent_hi"] if self._hover else C["accent"]), "#ffffff", None
        if s == "ghost":
            return (C["card2"] if self._hover else C["card"]), C["text"], C["line"]
        return ("#1b222c" if self._hover else self.bg), C["sub"], None

    def _draw(self):
        self.delete("all")
        fill, fg, outline = self._palette()
        round_rect(self, 1, 1, self.w - 1, self.h - 1, 10,
                   fill=fill, outline=outline or fill)
        self.create_text(self.w / 2, self.h / 2, text=self._label, fill=fg,
                         font=(F, 11, "bold"))

    def set_text(self, text):
        self._label = text
        self._draw()

    def set_enabled(self, flag):
        self._enabled = flag
        self.configure(cursor="hand2" if flag else "arrow")
        self._draw()

    def _on_enter(self, _):
        self._hover = True
        self._draw()

    def _on_leave(self, _):
        self._hover = False
        self._draw()

    def _on_click(self, _):
        if self._enabled and self._cmd:
            self._cmd()


class StepRail(tk.Canvas):
    """左侧步骤时间轴。"""

    def __init__(self, master, steps):
        super().__init__(master, width=SIDE_W, bg=C["sidebar"], highlightthickness=0, bd=0)
        self.steps = steps
        self.current = -1

    def set_current(self, idx):
        self.current = idx
        self.redraw()

    def redraw(self):
        self.delete("all")
        top = 78
        gap = 68
        x = 54

        self.create_text(28, 30, text="安装步骤", fill=C["muted"], anchor="w",
                         font=(F, 9, "bold"))
        self.create_text(28, 50, text="跟着点，别跳步", fill=C["muted"], anchor="w",
                         font=(F, 9))
        self.create_line(0, 68, SIDE_W, 68, fill=C["line"])

        for i, s in enumerate(self.steps):
            cy = top + i * gap
            done = i < self.current
            active = i == self.current

            if i < len(self.steps) - 1:
                ny = top + (i + 1) * gap
                self.create_line(x, cy + 17, x, ny - 17,
                                 fill=C["success"] if done else C["line"], width=2)

            if done:
                self.create_oval(x - 16, cy - 16, x + 16, cy + 16,
                                 fill=C["success"], outline=C["success"])
                self.create_text(x, cy, text="✓", fill="#06240f", font=(F, 14, "bold"))
            elif active:
                self.create_oval(x - 20, cy - 20, x + 20, cy + 20,
                                 fill="", outline=C["accent"], width=2)
                self.create_oval(x - 16, cy - 16, x + 16, cy + 16,
                                 fill=C["accent"], outline=C["accent"])
                self.create_text(x, cy, text=str(i + 1), fill="#ffffff",
                                 font=(F, 13, "bold"))
            else:
                self.create_oval(x - 16, cy - 16, x + 16, cy + 16,
                                 fill=C["card2"], outline=C["line"])
                self.create_text(x, cy, text=str(i + 1), fill=C["muted"],
                                 font=(F, 13, "bold"))

            color = C["text"] if active else (C["sub"] if done else C["muted"])
            weight = "bold" if active else "normal"
            self.create_text(x + 32, cy, text=s["rail"], fill=color, anchor="w",
                             font=(F, 11, weight), width=SIDE_W - x - 46)

        bot = 700 - 84 - 46
        self.create_line(24, bot, SIDE_W - 24, bot, fill=C["line"])
        self.create_text(28, bot + 16, text="沉溺海豚亭 · 闲鱼同名店铺",
                         fill=C["muted"], anchor="w", font=(F, 9))
        self.create_text(28, bot + 32, text="卡住了直接来找我", fill=C["muted"],
                         anchor="w", font=(F, 9))


# ══════════════════════════ 主程序 ══════════════════════════

class Guide(tk.Tk):
    def __init__(self, demo=False):
        super().__init__()
        self.demo = demo
        self.title(APP_TITLE)
        self.configure(bg=C["bg"])
        self.geometry("%dx%d" % (WIN_W, WIN_H))
        self.minsize(WIN_W, WIN_H)
        self.resizable(False, False)
        self.attributes("-topmost", True)

        try:
            self.iconbitmap(default="")
        except Exception:
            pass

        self.det = detect()
        self.state_ok = False
        self.step = -1          # -1 = 欢迎页
        self.prepared = False

        self._build()
        self._show_welcome()

    # ---------- 骨架 ----------
    def _build(self):
        # 顶部条
        head = tk.Frame(self, bg=C["sidebar"], height=66)
        head.pack(side="top", fill="x")
        head.pack_propagate(False)

        tk.Label(head, text=APP_TITLE, bg=C["sidebar"], fg=C["text"],
                 font=(F, 14, "bold")).pack(side="left", padx=(24, 8), pady=(0, 2))
        tk.Label(head, text="v" + VERSION, bg=C["sidebar"], fg=C["muted"],
                 font=(F, 9)).pack(side="left", pady=(4, 0))
        # 置顶开关（边看游戏边操作时有用）
        self.pin_on = True
        self.pin_btn = Button(head, "置顶：开", self._toggle_pin, style="subtle",
                              width=88, height=32, bg=C["sidebar"])
        self.pin_btn.pack(side="right", padx=(0, 22), pady=17)
        tk.Label(head, text=APP_SUB, bg=C["sidebar"], fg=C["sub"],
                 font=(F, 10)).pack(side="right", padx=(0, 14))

        # 内容区
        body = tk.Frame(self, bg=C["bg"])
        body.pack(side="top", fill="both", expand=True)

        self.rail_steps = [{"rail": t} for t in [
            "打开游戏", "打开卫月设置", "开开发者模式",
            "添加 DLL", "确认勾选", "启用插件", "完成",
        ]]
        self.rail = StepRail(body, self.rail_steps)
        self.rail.pack(side="left", fill="y")

        self.right = tk.Frame(body, bg=C["bg"])
        self.right.pack(side="left", fill="both", expand=True)

        # 底部操作条
        self.foot = tk.Frame(self, bg=C["bg"], height=84)
        self.foot.pack(side="bottom", fill="x")
        self.foot.pack_propagate(False)

        self.btn_back = Button(self.foot, "← 上一步", self.on_back,
                               style="ghost", width=112, height=42, bg=C["bg"])
        self.btn_next = Button(self.foot, "我做好了，下一步 →", self.on_next,
                               style="primary", width=196, height=42, bg=C["bg"])
        self.btn_next.pack(side="right", padx=(0, 24), pady=16)
        self.btn_back.pack(side="right", padx=(0, 12), pady=16)

        self.hint = tk.Label(self.foot, text="", bg=C["bg"], fg=C["sub"], font=(F, 9))
        self.hint.pack(side="left", padx=24)

    def _clear_right(self):
        for w in self.right.winfo_children():
            w.destroy()

    def _text_block(self, parent, items, path_text=None):
        """渲染正文区（支持段落 / 列表 / 关键动作 / 路径块）。"""
        box = tk.Frame(parent, bg=C["card"])
        box.pack(fill="both", expand=True)

        txt = tk.Text(box, bg=C["card"], fg=C["text"], font=(F, 11),
                      wrap="word", bd=0, highlightthickness=0,
                      padx=22, pady=18, spacing1=5, spacing3=9,
                      cursor="arrow")
        txt.pack(fill="both", expand=True)

        txt.tag_configure("li", lmargin1=6, lmargin2=24, foreground=C["text"])
        txt.tag_configure("sub", lmargin1=24, lmargin2=46, foreground=C["sub"],
                          font=(F, 10))
        txt.tag_configure("k", lmargin1=6, lmargin2=6, foreground="#9dc0ff",
                          font=(F, 11, "bold"), spacing3=4)

        for kind, text in items:
            if kind == "li":
                txt.insert("end", "·  ", "sub")
                txt.insert("end", text + "\n", "li")
            elif kind == "sub":
                txt.insert("end", text + "\n", "sub")
            elif kind == "k":
                txt.insert("end", text + "\n", "k")
            elif kind == "path":
                continue
        txt.configure(state="disabled")
        return txt

    # ---------- 欢迎页 ----------
    def _show_welcome(self):
        self.step = -1
        self.rail.set_current(-1)
        self._clear_right()
        self.btn_back.set_enabled(False)
        self.btn_next.set_text("开始引导 →")
        self.btn_next.set_enabled(True)
        self.hint.configure(text="")

        wrap = tk.Frame(self.right, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=28, pady=(22, 8))

        tk.Label(wrap, text="先确认三件事", bg=C["bg"], fg=C["text"],
                 font=(F, 18, "bold"), anchor="w").pack(fill="x")
        tk.Label(wrap, text="下面三项会自动检测，都是绿的就能开始。",
                 bg=C["bg"], fg=C["sub"], font=(F, 10), anchor="w").pack(fill="x", pady=(4, 16))

        rows = tk.Frame(wrap, bg=C["bg"])
        rows.pack(fill="x")

        d = self.det
        self._check_row(rows, "卫月本体", d["installed"],
                        "已安装" if d["installed"] else "没检测到",
                        "先看《基础文件下载地址.txt》装卫月" if not d["installed"] else "")
        self._check_row(rows, "卫月配置", d["ready"],
                        "已就绪" if d["ready"] else "还没启动过游戏",
                        "开一次游戏到登录界面就会生成" if not d["ready"] else "")
        self._check_row(rows, "插件文件", d["has_dll"],
                        "已找到" if d["has_dll"] else "压缩包不完整",
                        "重新完整解压一遍压缩包" if not d["has_dll"] else "")

        # 分支提示
        tip = tk.Frame(wrap, bg=C["bg"])
        tip.pack(fill="x", pady=(18, 0))

        if not d["installed"]:
            self._notice(tip, C["danger"], "这台电脑上没找到卫月",
                         "先点下面的按钮打开《基础文件下载地址》，按里面的地址下载卫月本体和启动器。"
                         "装好并启动一次游戏，再回来点「重新检测」。")

        elif not d["ready"]:
            self._notice(tip, C["warn"], "卫月装了，但还没启动过",
                         "双击卫月启动器，把游戏开到登录界面就行，不用真的登录。"
                         "到了登录界面再关掉，然后回来点「重新检测」。")

        else:
            self._notice(tip, C["success"], "环境没问题，可以开始",
                         "接下来七步，每做完一步点右下角的按钮。全程照做，大约 5 分钟。")

        act = tk.Frame(wrap, bg=C["bg"])
        act.pack(fill="x", pady=(16, 0))
        Button(act, "打开基础文件下载地址", self._open_basic,
               style="ghost", width=210, height=40, bg=C["bg"]).pack(side="left")
        Button(act, "重新检测", self._recheck,
               style="subtle", width=112, height=40, bg=C["bg"]).pack(side="left", padx=10)

    def _check_row(self, parent, name, ok, status, hint):
        row = tk.Frame(parent, bg=C["card"], height=64)
        row.pack(fill="x", pady=3)
        row.pack_propagate(False)

        dot = "#22c55e" if ok else "#ef4444"
        mark = "✓" if ok else "!"
        cv = tk.Canvas(row, width=30, height=30, bg=C["card"], highlightthickness=0)
        cv.pack(side="left", padx=(18, 10))
        cv.create_oval(2, 2, 28, 28, fill=dot, outline=dot)
        cv.create_text(15, 15, text=mark, fill="#08120a" if ok else "#ffffff",
                       font=(F, 12, "bold"))

        col = tk.Frame(row, bg=C["card"])
        col.pack(side="left", fill="y", pady=11)
        tk.Label(col, text=name, bg=C["card"], fg=C["text"],
                 font=(F, 11, "bold"), anchor="w").pack(anchor="w")
        if hint:
            tk.Label(col, text=hint, bg=C["card"], fg=C["muted"],
                     font=(F, 9), anchor="w").pack(anchor="w", pady=(2, 0))

        tk.Label(row, text=status, bg=C["card"],
                 fg=C["success"] if ok else C["danger"],
                 font=(F, 10, "bold")).pack(side="right", padx=20)

    def _notice(self, parent, color, title, text):
        box = tk.Frame(parent, bg=C["card2"])
        box.pack(fill="x")
        strip = tk.Frame(box, bg=color, width=4)
        strip.pack(side="left", fill="y")
        inner = tk.Frame(box, bg=C["card2"])
        inner.pack(side="left", fill="both", expand=True, padx=16, pady=12)
        tk.Label(inner, text=title, bg=C["card2"], fg=color,
                 font=(F, 11, "bold"), anchor="w").pack(fill="x")
        tk.Label(inner, text=text, bg=C["card2"], fg=C["sub"], font=(F, 10),
                 anchor="w", justify="left", wraplength=520).pack(fill="x", pady=(3, 0))

    def _toggle_pin(self):
        self.pin_on = not self.pin_on
        self.attributes("-topmost", self.pin_on)
        self.pin_btn.set_text("置顶：开" if self.pin_on else "置顶：关")

    def _open_basic(self):
        p = os.path.join(app_dir(), "教程", "基础文件下载地址.txt")
        if not os.path.isfile(p):
            p = os.path.join(app_dir(), "基础文件下载地址.txt")
        if not open_path(p):
            self.hint.configure(text="找不到《基础文件下载地址.txt》，请到教程文件夹里手动打开")

    def _recheck(self):
        self.det = detect()
        self._show_welcome()

    # ---------- 步骤页 ----------
    def _show_step(self, idx):
        self.step = idx
        self.rail.set_current(idx)
        self._clear_right()

        s = STEPS[idx]
        self.btn_back.set_enabled(True)
        last = idx == len(STEPS) - 1
        self.btn_next.set_text("完成，关闭 →" if last else "我做好了，下一步 →")
        self.hint.configure(text="第 %d / %d 步" % (idx + 1, len(STEPS)))

        wrap = tk.Frame(self.right, bg=C["bg"])
        wrap.pack(fill="both", expand=True, padx=28, pady=(22, 8))

        tk.Label(wrap, text=s["title"], bg=C["bg"], fg=C["text"],
                 font=(F, 17, "bold"), anchor="w", wraplength=572,
                 justify="left").pack(fill="x")
        tk.Label(wrap, text=s["lead"], bg=C["bg"], fg=C["sub"], font=(F, 10),
                 anchor="w", wraplength=560, justify="left").pack(fill="x", pady=(6, 12))

        body = tk.Frame(wrap, bg=C["card"])
        body.pack(fill="x")
        pad = tk.Frame(body, bg=C["card"])
        pad.pack(fill="x", padx=20, pady=14)

        for kind, text in s["body"]:
            if kind == "path":
                continue
            if kind == "li":
                tk.Label(pad, text="·   " + text, bg=C["card"], fg=C["text"],
                         font=(F, 11), anchor="w", justify="left",
                         wraplength=500).pack(fill="x", pady=(0, 7))
            elif kind == "sub":
                tk.Label(pad, text=text, bg=C["card"], fg=C["sub"],
                         font=(F, 10), anchor="w", justify="left",
                         wraplength=468).pack(fill="x", padx=(20, 0), pady=(0, 9))
            elif kind == "k":
                tk.Label(pad, text=text, bg=C["card"], fg="#9dc0ff",
                         font=(F, 11, "bold"), anchor="w", justify="left",
                         wraplength=500).pack(fill="x", pady=(1, 3))

        # 路径块
        if any(k == "path" for k, _ in s["body"]):
            pbox = tk.Frame(body, bg=C["card2"])
            pbox.pack(fill="x", padx=18, pady=(0, 16))

            path = managed_dll()
            left = tk.Frame(pbox, bg=C["card2"])
            left.pack(side="left", fill="x", expand=True, padx=14, pady=10)
            tk.Label(left, text="复制这一整条路径", bg=C["card2"], fg=C["muted"],
                     font=(F, 9), anchor="w").pack(fill="x")
            tk.Label(left, text=path, bg=C["card2"], fg="#9dc0ff", font=(F, 10),
                     anchor="w", justify="left", wraplength=388).pack(fill="x", pady=(3, 0))

            Button(pbox, "复制路径", lambda: self._copy(path), style="primary",
                   width=104, height=36, bg=C["card2"]).pack(side="right", padx=(6, 12))

        # 成功标志
        ok = tk.Frame(wrap, bg=C["bg"])
        ok.pack(fill="x", pady=(10, 0))
        cv = tk.Canvas(ok, width=22, height=22, bg=C["bg"], highlightthickness=0)
        cv.pack(side="left", padx=(2, 8))
        cv.create_oval(2, 2, 20, 20, fill="", outline=C["success"], width=2)
        cv.create_text(11, 11, text="✓", fill=C["success"], font=(F, 9, "bold"))
        tk.Label(ok, text=s["ok"], bg=C["bg"], fg=C["success"], font=(F, 10, "bold"),
                 anchor="w", wraplength=520, justify="left").pack(side="left")

        # 警告
        if s.get("warn"):
            wbox = tk.Frame(wrap, bg=C["bg"])
            wbox.pack(fill="x", pady=(8, 0))
            card = tk.Frame(wbox, bg=C["card2"])
            card.pack(fill="x")
            stripe = tk.Frame(card, bg=C["warn"], width=4)
            stripe.pack(side="left", fill="y")
            tk.Label(card, text=s["warn"], bg=C["card2"], fg="#d9b06a", font=(F, 10),
                     anchor="w", justify="left", wraplength=520,
                     padx=14, pady=10).pack(side="left", fill="x", expand=True)

    def _copy(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.hint.configure(text="路径已复制，去卫月的文件选择框里按 Ctrl+V 粘贴")

    def _open_folder(self):
        d = managed_dir()
        if os.path.isdir(d):
            open_path(d)
        else:
            self.hint.configure(text="插件文件还没就位，请先回到欢迎页重新检测")

    # ---------- 导航 ----------
    def on_back(self):
        if self.step <= 0:
            self._show_welcome()
        else:
            self._show_step(self.step - 1)

    def on_next(self):
        if self.step == -1:
            ok, msg = self._prepare_once()
            if not ok:
                self.hint.configure(text=msg)
                return
            self.hint.configure(text=msg)
            self._show_step(0)
            return

        if self.step >= len(STEPS) - 1:
            self.destroy()
            return

        self._show_step(self.step + 1)

    def _prepare_once(self):
        if self.prepared:
            return True, ""
        if self.demo:
            self.prepared = True
            return True, "演示模式：跳过文件准备"
        ok, msg = prepare(self.det)
        self.prepared = ok
        if ok:
            self.det = detect()
        return ok, msg


def main():
    demo = "--demo" in sys.argv
    if sys.platform == "win32":
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    app = Guide(demo=demo)

    # 仅用于开发期预览指定步骤：--step 3
    if "--step" in sys.argv:
        try:
            idx = int(sys.argv[sys.argv.index("--step") + 1])
            app.prepared = True
            app.after(120, lambda: app._show_step(idx))
        except Exception:
            pass

    app.mainloop()


if __name__ == "__main__":
    main()
