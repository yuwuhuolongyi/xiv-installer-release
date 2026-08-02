#!/usr/bin/env python3
# ///M XIVLAUNCHER PLUGIN INSTALLER — 闲鱼沉溺海豚亭
import os, sys, json, shutil, tkinter as tk, base64
from tkinter import ttk, filedialog, messagebox, Toplevel
from pathlib import Path

# watermark (base64 encoded to avoid plaintext in binary)
_WM = base64.b64decode('6Zey6bG85rKJ5rq65rW36LGa5Lqt').decode('utf-8')

C = {
    "canvas":"#000000","surface_card":"#1a1a1a","surface_elevated":"#262626",
    "surface_soft":"#0d0d0d","ink":"#ffffff","body":"#bbbbbb","muted":"#7e7e7e",
    "hairline":"#3c3c3c","m_blue_light":"#0066b1","m_blue_dark":"#1c69d4",
    "m_red":"#e22718","success":"#0fa336","warning":"#f4b400",
}
S = {"xxs":4,"xs":8,"sm":12,"md":16,"lg":24,"xl":40,"xxl":64}
F = "Segoe UI" if sys.platform == "win32" else "Helvetica"

# ═══════════ CORE LOGIC ═══════════

def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def scan_repos(app_dir):
    results = []
    for f in sorted(os.listdir(app_dir)):
        fp = os.path.join(app_dir, f)
        if not os.path.isfile(fp): continue
        if not (f.startswith("repo_") and f.endswith(".txt")): continue
        name = f[5:-4]
        try:
            with open(fp, "r", encoding="utf-8") as fh:
                urls = [l.strip() for l in fh if l.strip()]
        except Exception: urls = []
        if urls: results.append((fp, name, urls))
    return results

def find_plugin_pack(app_dir):
    """找插件包目录，排除 .app 等特殊目录"""
    for item in sorted(os.listdir(app_dir)):
        ip = os.path.join(app_dir, item)
        if not os.path.isdir(ip): continue
        # 排除各种非插件目录
        if item.startswith(".") or item.startswith("__"): continue
        if item in ("dist","build",".git"): continue
        if item.endswith(".app"): continue  # macOS app bundle
        files = list(Path(ip).rglob("*"))
        if any(f.suffix in (".dll",".json") for f in files if f.is_file()):
            return ip, sum(1 for f in files if f.is_file())
    # fallback: 任何非排除目录
    for item in sorted(os.listdir(app_dir)):
        ip = os.path.join(app_dir, item)
        if not os.path.isdir(ip): continue
        if item.startswith(".") or item.startswith("__"): continue
        if item in ("dist","build",".git"): continue
        if item.endswith(".app"): continue
        fc = sum(1 for _ in Path(ip).rglob("*") if _.is_file())
        if fc > 0: return ip, fc
    return None, 0

def infer_alias(path):
    """根据目录名推断端别：台服/国服/国际服"""
    up = os.path.basename(path).upper()
    if "TC" in up: return "台服"
    if "CN" in up: return "国服"
    return "国际服"

def find_xivlauncher():
    results = []
    appdata = os.environ.get("APPDATA", "")
    for name in ["XIVLauncherCN", "XIVLauncherTC", "XIVLauncher"]:
        d = os.path.join(appdata, name)
        if os.path.isdir(d) and os.path.isfile(os.path.join(d, "dalamudConfig.json")):
            results.append((d, infer_alias(name)))
    return results

def find_pack_server(app_dir):
    """根据安装器同目录的 XIVLauncherTC/CN/国际服 文件夹判定端别。
    分发场景下安装器就躺在插件包目录里，旁边的 XIVLauncherXX 文件夹即端别身份证。
    返回 (端目录名, alias, server) 或 None。"""
    for name, alias, server in (
        ("XIVLauncherTC", "台服", "tc"),
        ("XIVLauncherCN", "国服", "cn"),
        ("XIVLauncher", "国际服", "global"),
    ):
        if os.path.isdir(os.path.join(app_dir, name)):
            return (name, alias, server)
    return None

def resolve_target_dir(server_name):
    """端目录名 -> 用户机器上的卫月目录（%APPDATA%/name）"""
    appdata = os.environ.get("APPDATA", "")
    return os.path.join(appdata, server_name) if appdata else ""

def parse_repo_file(filepath):
    fname = os.path.basename(filepath)
    name = fname[5:-4] if fname.startswith("repo_") else os.path.splitext(fname)[0]
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            urls = [l.strip() for l in f if l.strip()]
    except Exception: urls = []
    return name, urls

def load_json(p):
    with open(p, "r", encoding="utf-8") as f: return json.load(f)

def save_json(p, data):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def ensure_third_repo(cfg):
    if "ThirdRepoList" not in cfg:
        cfg["ThirdRepoList"] = {
            "$type": "System.Collections.Generic.List`1[[Dalamud.Configuration.ThirdPartyRepoSettings, Dalamud]], System.Private.CoreLib",
            "$values": []}
    if "$values" not in cfg["ThirdRepoList"]:
        cfg["ThirdRepoList"]["$values"] = []

def get_existing_urls(cfg):
    ensure_third_repo(cfg)
    return {r.get("Url", "") for r in cfg["ThirdRepoList"]["$values"]}

def add_repos(cfg, url_list):
    ensure_third_repo(cfg)
    exist = get_existing_urls(cfg)
    vals = cfg["ThirdRepoList"]["$values"]; added = 0
    for url in url_list:
        if url in exist: continue
        obj = {"$type":"Dalamud.Configuration.ThirdPartyRepoSettings, Dalamud",
               "Url":url,"IsEnabled":True,"Name":None}
        vals.append(obj) if len(vals)==0 else vals.insert(len(vals)-1, obj)
        exist.add(url); added += 1
    return added

def backup_config(config_path):
    bak = config_path + ".bak"; shutil.copy2(config_path, bak); return bak

def copy_dir_merge(src, dst, progress_cb=None):
    if not os.path.exists(src): return
    os.makedirs(dst, exist_ok=True)
    items = os.listdir(src); total = len(items)
    for i, item in enumerate(items):
        s = os.path.join(src, item); d = os.path.join(dst, item)
        if os.path.isdir(s): copy_dir_merge(s, d, progress_cb)
        else: shutil.copy2(s, d)
        if progress_cb: progress_cb(i+1, total)

# ═══════════ CANVAS HELPERS ═══════════

def draw_m_stripe(cv, x, y, w, h=4):
    """在 Canvas 上画 M 三色条"""
    seg_w = [w*0.33, w*0.34, w*0.33]
    colors = [C["m_blue_light"], C["m_blue_dark"], C["m_red"]]
    cx = x
    for i in range(3):
        cv.create_rectangle(cx, y, cx+seg_w[i], y+h, fill=colors[i], outline="")
        cx += seg_w[i]

def blink_text(cv, item_id, count=[0]):
    """闪烁文字效果"""
    count[0] += 1
    if count[0] > 20: return
    cv.itemconfig(item_id, fill=C["m_blue_dark"] if count[0]%2==0 else C["ink"])
    cv.after(150, lambda: blink_text(cv, item_id, count))

def draw_watermark(cv, w, h):
    """满铺背景水印 — 闲鱼沉溺海豚亭"""
    wm = _WM
    step_x, step_y = 130, 60
    color = "#222222"  # 深灰，融入背景但可见
    for row in range(-1, int(h / step_y) + 2):
        for col in range(-2, int(w / step_x) + 2):
            x = col * step_x + (row % 3) * 20  # 行交错偏移
            y = row * step_y
            cv.create_text(x, y, text=wm, anchor="nw",
                          font=(F, 10, "bold"), fill=color)

# ═══════════ DIALOGS ═══════════

def msg_error(parent, title, desc, causes, suggests):
    msg = f"{desc}\n\n可能原因:\n"
    for c in causes: msg += f"  • {c}\n"
    msg += "\n操作建议:\n"
    for s in suggests: msg += f"  • {s}\n"
    messagebox.showerror(title, msg, parent=parent)

def show_preview(parent, app):
    
    pv = Toplevel(parent); pv.title("安装预览"); pv.geometry("560x580")
    pv.resizable(False, False); pv.configure(bg=C["canvas"])
    pv.transient(parent); pv.grab_set()
    pv.update_idletasks()
    x = parent.winfo_x()+(parent.winfo_width()-560)//2
    y = parent.winfo_y()+(parent.winfo_height()-580)//2
    pv.geometry(f"+{x}+{y}")
    confirmed = [False]

    # M stripe canvas
    sc = tk.Canvas(pv, height=4, bg=C["canvas"], highlightthickness=0)
    sc.pack(fill=tk.X); draw_m_stripe(sc, 0, 0, 540, 4)
    pv.update(); sc.configure(width=540)

    hdr = tk.Frame(pv, bg=C["canvas"])
    hdr.pack(fill=tk.X, padx=S["lg"], pady=(S["lg"], S["sm"]))
    tk.Label(hdr, text="确 认 安 装",
             font=(F,14,"bold"), fg=C["ink"], bg=C["canvas"]).pack(anchor="w")

    ctn = tk.Frame(pv, bg=C["canvas"])
    ctn.pack(fill=tk.BOTH, expand=True, padx=S["lg"], pady=(0,S["md"]))

    tk.Label(ctn, text="目标目录", font=(F,10,"bold"),
             fg=C["muted"], bg=C["canvas"]).pack(anchor="w")
    tk.Label(ctn, text=app.target_dir, font=(F,10),
             fg=C["body"], bg=C["canvas"], anchor="w").pack(fill=tk.X)
    tk.Frame(ctn, bg=C["hairline"], height=1).pack(fill=tk.X, pady=S["md"])

    tk.Label(ctn, text="仓库地址", font=(F,10,"bold"),
             fg=C["muted"], bg=C["canvas"]).pack(anchor="w")
    exist_set = set()
    cfg_path = os.path.join(app.target_dir, "dalamudConfig.json")
    if os.path.isfile(cfg_path):
        try: exist_set = get_existing_urls(load_json(cfg_path))
        except: pass

    new_list, exist_list = [], []
    for _, pname, urls in app.repo_files:
        for u in urls:
            (new_list if u not in exist_set else exist_list).append((pname, u))

    txt_frame = tk.Frame(ctn, bg=C["canvas"])
    txt_frame.pack(fill=tk.X, pady=(S["xs"],S["md"]))
    txt = tk.Text(txt_frame, height=5, bg=C["surface_card"], fg=C["body"],
                  font=(F,9), relief="flat", padx=S["sm"], pady=S["sm"],
                  highlightbackground=C["hairline"], highlightthickness=1, wrap="word", bd=0)
    txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb = tk.Scrollbar(txt_frame, command=txt.yview)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    txt.configure(yscrollcommand=sb.set)
    txt.tag_configure("new", foreground=C["success"])
    txt.tag_configure("old", foreground=C["muted"])
    txt.tag_configure("plug", foreground=C["m_blue_dark"])
    txt.insert("end", f"新增 ({len(new_list)})\n", ("new",))
    for pn, url in new_list:
        txt.insert("end", f"  [{pn}]  ", ("plug",)); txt.insert("end", f"{url}\n")
    if exist_list:
        txt.insert("end", f"\n已存在 ({len(exist_list)})\n", ("old",))
        for pn, url in exist_list:
            txt.insert("end", f"  [{pn}]  ", ("plug",)); txt.insert("end", f"{url}\n")
    elif not new_list:
        txt.insert("end", "(没有新仓库)")
    txt.configure(state="disabled")

    tk.Frame(ctn, bg=C["hairline"], height=1).pack(fill=tk.X, pady=S["md"])
    tk.Label(ctn, text="插件包", font=(F,10,"bold"),
             fg=C["muted"], bg=C["canvas"]).pack(anchor="w")
    if app.plugin_pack_dir:
        tk.Label(ctn, text=f"{app.plugin_pack_dir}  [{app.plugin_pack_count} 个文件]",
                 font=(F,10), fg=C["body"], bg=C["canvas"], anchor="w").pack(fill=tk.X)
    else:
        tk.Label(ctn, text="(未找到)", font=(F,10),
                 fg=C["warning"], bg=C["canvas"], anchor="w").pack(fill=tk.X)

    tk.Frame(ctn, bg=C["hairline"], height=1).pack(fill=tk.X, pady=S["md"])
    tk.Label(ctn, text="备份", font=(F,10,"bold"),
             fg=C["muted"], bg=C["canvas"]).pack(anchor="w")
    tk.Label(ctn, text="dalamudConfig.json → .bak (自动备份)",
             font=(F,10), fg=C["body"], bg=C["canvas"], anchor="w").pack(fill=tk.X)

    bf = tk.Frame(pv, bg=C["canvas"])
    bf.pack(fill=tk.X, padx=S["lg"], pady=(0,S["lg"]))

    def on_cancel(): pv.destroy()
    def on_confirm(): confirmed[0]=True; pv.destroy()

    cb = tk.Canvas(bf, height=40, bg=C["canvas"], highlightthickness=0, cursor="hand2")
    cb.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,S["xs"]))
    def cdn(e=None):
        cb.delete("all");w,h=cb.winfo_width(),cb.winfo_height()
        cb.create_rectangle(2,2,w-2,h-2,fill=C["surface_card"],outline=C["hairline"])
        cb.create_text(w/2,h/2,text="取 消",font=(F,11,"bold"),fill=C["ink"])
    def cdh(e=None):
        cb.delete("all");w,h=cb.winfo_width(),cb.winfo_height()
        cb.create_rectangle(0,0,w,h,fill=C["surface_elevated"],outline=C["ink"])
        cb.create_text(w/2,h/2,text="取 消",font=(F,11,"bold"),fill=C["ink"])
    cb.bind("<Configure>",cdn);cb.bind("<Enter>",cdh);cb.bind("<Leave>",cdn)
    cb.bind("<Button-1>",lambda e:on_cancel())

    ok = tk.Canvas(bf, height=40, bg=C["canvas"], highlightthickness=0, cursor="hand2")
    ok.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(S["xs"],0))
    def odn(e=None):
        ok.delete("all");w,h=ok.winfo_width(),ok.winfo_height()
        ok.create_rectangle(0,0,w,h,fill=C["m_blue_dark"],outline=C["m_blue_dark"])
        ok.create_text(w/2,h/2,text="确 认",font=(F,11,"bold"),fill=C["ink"])
    def odh(e=None):
        ok.delete("all");w,h=ok.winfo_width(),ok.winfo_height()
        ok.create_rectangle(0,0,w,h,fill="#1e7de3",outline="#1e7de3")
        ok.create_text(w/2,h/2,text="确 认",font=(F,11,"bold"),fill=C["ink"])
    ok.bind("<Configure>",odn);ok.bind("<Enter>",odh);ok.bind("<Leave>",odn)
    ok.bind("<Button-1>",lambda e:on_confirm())

    pv.wait_window()
    return confirmed[0]

def show_completion(parent, plugin_names, repo_count):
    
    d = Toplevel(parent); d.title("安装完成"); d.geometry("420x300")
    d.resizable(False,False); d.configure(bg=C["canvas"])
    d.transient(parent); d.grab_set()
    d.update_idletasks()
    x = parent.winfo_x()+(parent.winfo_width()-420)//2
    y = parent.winfo_y()+(parent.winfo_height()-300)//2
    d.geometry(f"+{x}+{y}")

    cv = tk.Canvas(d, height=4, bg=C["canvas"], highlightthickness=0)
    cv.pack(fill=tk.X); draw_m_stripe(cv, 0, 0, 420, 4)

    ctn = tk.Frame(d, bg=C["canvas"])
    ctn.pack(fill=tk.BOTH, expand=True, padx=S["xl"], pady=S["xl"])

    # Animated checkmark
    chk = tk.Canvas(ctn, width=80, height=80, bg=C["canvas"], highlightthickness=0)
    chk.pack()
    chk.create_oval(8,8,72,72,outline=C["success"],width=3)
    chk.create_text(40,40,text="M",font=(F,28,"bold"),fill=C["success"])

    tk.Label(ctn, text="安 装 完 成",
             font=(F,16,"bold"),fg=C["ink"],bg=C["canvas"]).pack(pady=(S["md"],S["xs"]))
    tk.Label(ctn, text="、".join(plugin_names),
             font=(F,11),fg=C["body"],bg=C["canvas"]).pack(pady=(0,S["sm"]))
    tk.Label(ctn, text=f"新增 {repo_count} 个仓库\n请打开卫月启用插件",
             font=(F,9),fg=C["muted"],bg=C["canvas"],justify="center").pack(pady=(0,S["md"]))

    def close_dlg():
        d.destroy()
    okb = tk.Canvas(ctn, height=36, width=140, bg=C["canvas"],
                    highlightthickness=0, cursor="hand2"); okb.pack()
    def odn(e=None):
        w,h=okb.winfo_width(),okb.winfo_height();okb.delete("all")
        okb.create_rectangle(2,2,w-2,h-2,fill=C["surface_card"],outline=C["hairline"])
        okb.create_text(w/2,h/2,text="关 闭",font=(F,11,"bold"),fill=C["ink"])
    def odh(e=None):
        w,h=okb.winfo_width(),okb.winfo_height();okb.delete("all")
        okb.create_rectangle(0,0,w,h,fill=C["surface_elevated"],outline=C["ink"])
        okb.create_text(w/2,h/2,text="关 闭",font=(F,11,"bold"),fill=C["ink"])
    okb.bind("<Configure>",odn);okb.bind("<Enter>",odh);okb.bind("<Leave>",odn)
    okb.bind("<Button-1>",lambda e:close_dlg())
    d.wait_window()

# ═══════════ MAIN APP ═══════════

class XIVPluginInstaller:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("///M  卫月插件安装器")
        self.root.geometry("600x660")
        self.root.resizable(True, True)
        self.root.minsize(520, 580)
        self.root.configure(bg=C["canvas"])

        # State
        app_dir = get_app_dir()
        self.repo_files = scan_repos(app_dir)
        self.plugin_pack_dir, self.plugin_pack_count = find_plugin_pack(app_dir)
        pack = find_pack_server(app_dir)
        if pack:
            _name, self.target_alias, self.server = pack
            self.target_dir = resolve_target_dir(_name)
        else:
            self.target_dir = ""
            self.target_alias = ""
            self.server = "global"
        self.detected_targets = [(self.target_dir, self.target_alias)] if self.target_dir else []
        self.can_install = bool(self.repo_files and self.plugin_pack_dir and self._target_ready())
        self.phase = "scanning"

        # Simple full-window canvas (no scroll)
        self.cv = tk.Canvas(self.root, bg=C["canvas"], highlightthickness=0, bd=0)
        self.cv.pack(fill=tk.BOTH, expand=True)

        # Footer status line
        self.status_line = tk.Label(self.root, text="", font=(F,9,"bold"),
                                     fg=C["muted"], bg=C["surface_soft"], anchor="w")
        self.status_line.pack(fill=tk.X, side=tk.BOTTOM)

        self.cv.bind("<Configure>", self._on_resize)
        self._start_sequence()

    def _on_resize(self, e):
        if self.phase == "revealed":
            self._draw_revealed(e.width, e.height)
        else:
            self._draw_scanning()

    def _start_sequence(self):
        """仪式感启动序列"""
        # 强制 tkinter 完成布局计算，否则 Canvas 尺寸为 1x1
        self.root.update_idletasks()
        self.root.update()
        self._draw_boot_screen()

        # Staggered animation timeline
        self.root.after(800, self._phase_scanning)

    def _get_dims(self):
        """获取当前 Canvas 真实尺寸"""
        w = self.cv.winfo_width()
        h = self.cv.winfo_height()
        if w < 50: w = 600
        if h < 50: h = 660
        return w, h

    def _draw_boot_screen(self):
        w, h = self._get_dims()
        self.cv.delete("all")
        draw_m_stripe(self.cv, 0, 0, w, 4)
        draw_watermark(self.cv, w, h)

        # Center: M logo area
        cx, cy = w//2, h//2 - 60
        self.cv.create_rectangle(cx-40, cy-40, cx+40, cy+40,
                                 outline=C["m_blue_dark"], width=3)
        self.cv.create_text(cx, cy, text="M", font=(F, 36, "bold"),
                           fill=C["m_blue_dark"], tags="logo_m")

        # Title
        self.cv.create_text(cx, cy+80, text="X I V L A U N C H E R",
                           font=(F, 12, "bold"), fill=C["muted"])
        self.cv.create_text(cx, cy+110, text="卫 月 插 件 安 装 器",
                           font=(F, 22, "bold"), fill=C["ink"])

        # Bottom: status dots
        self.cv.create_text(cx, h-40, text="启 动 中",
                           font=(F, 9), fill=C["muted"], tags="status_text")

    def _phase_scanning(self):
        """扫描动画阶段 — 反映真实检测结果"""
        w, h = self._get_dims()
        self.cv.delete("all")
        cx = w//2

        # M stripe
        draw_m_stripe(self.cv, 0, 0, w, 4)
        draw_watermark(self.cv, w, h)

        # Title
        self.cv.create_text(cx, 80, text="系 统 检 测 中",
                           font=(F, 16, "bold"), fill=C["ink"], tags="scan_title")

        # Divider
        self.cv.create_line(S["xl"], 110, w-S["xl"], 110,
                           fill=C["hairline"], width=1)

        # 真实检测结果
        statuses = [
            {"label": "仓 库 文 件", "found": bool(self.repo_files),
             "detail": f"{len(self.repo_files)} 个仓库" if self.repo_files else "未找到"},
            {"label": "插 件 包", "found": bool(self.plugin_pack_dir),
             "detail": f"{os.path.basename(self.plugin_pack_dir)}" if self.plugin_pack_dir else "未找到"},
            {"label": "卫月启动器", "found": bool(self.target_dir),
             "detail": f"{os.path.basename(self.target_dir)}" if self.target_dir else "未找到 · 请先启动卫月一次"},
        ]

        y_start = 150
        line_h = 60
        for i, st in enumerate(statuses):
            y = y_start + i * (line_h + 30)
            self.cv.create_text(cx - 180, y, text=st["label"], anchor="w",
                               font=(F, 11, "bold"), fill=C["muted"],
                               tags=f"label_{i}")
            bar_x = cx - 160; bar_w = 340; bar_h = 20
            self.cv.create_rectangle(bar_x, y+16, bar_x+bar_w, y+16+bar_h,
                                     fill=C["surface_card"], outline="",
                                     tags=f"bar_bg_{i}")
            st.update({"bar_x": bar_x, "bar_w": bar_w, "bar_y": y+16, "bar_h": bar_h})

        def reveal_step(step):
            if step >= 3:
                self.root.after(600, self._phase_reveal)
                return
            st = statuses[step]
            end_color = C["success"] if st["found"] else C["warning"]
            end_icon = "✓" if st["found"] else "✗"
            end_fill = C["success"] if st["found"] else C["warning"]

            def animate_bar(p=0):
                if p > 100:
                    self.cv.create_rectangle(
                        st["bar_x"], st["bar_y"],
                        st["bar_x"]+st["bar_w"], st["bar_y"]+st["bar_h"],
                        fill=end_fill, outline="", tags=f"bar_done_{step}")
                    self.cv.itemconfig(f"label_{step}", fill=end_color)
                    self.cv.create_text(
                        st["bar_x"]+st["bar_w"]+20, st["bar_y"]+st["bar_h"]//2,
                        text=end_icon, font=(F, 12, "bold"),
                        fill=end_color, tags=f"check_{step}")
                    # 显示具体结果文字
                    self.cv.create_text(
                        st["bar_x"]+st["bar_w"]//2, st["bar_y"]+st["bar_h"]+18,
                        text=st["detail"], font=(F, 9),
                        fill=end_color, tags=f"detail_{step}")
                    self.root.after(500, lambda: reveal_step(step+1))
                    return
                w_fill = st["bar_w"] * p / 100
                mid = C["m_blue_dark"] if p < 70 else end_fill
                self.cv.create_rectangle(
                    st["bar_x"], st["bar_y"],
                    st["bar_x"]+w_fill, st["bar_y"]+st["bar_h"],
                    fill=mid, outline="", tags=f"bar_fill_{step}")
                self.root.after(20, lambda: animate_bar(p+3))

            animate_bar(0)

        self.root.after(400, lambda: reveal_step(0))

    def _phase_reveal(self):
        """扫描完成，展示结果"""
        self.phase = "revealed"
        w, h = self._get_dims()
        self._draw_revealed(w, h)
        # 多端共存时让用户选择要把插件装到哪个端
        if len(self.detected_targets) > 1:
            self.root.after(400, self._choose_target)

    def _draw_revealed(self, w, h):
        self.cv.delete("all")
        cx = w//2

        # M stripe
        draw_m_stripe(self.cv, 0, 0, w, 4)
        draw_watermark(self.cv, w, h)

        # Title area with pulse
        result_text = "全 部 就 绪" if self.can_install else "需 要 操 作"
        result_color = C["success"] if self.can_install else C["warning"]
        title_id = self.cv.create_text(
            cx, 60, text=result_text,
            font=(F, 16, "bold"), fill=result_color, tags="ready_title")

        # Pulsing glow on title
        def pulse_title(count=[0]):
            if self.phase != "revealed": return
            count[0] += 1
            size = 16 + (count[0]%6)/2.0 if count[0]%12 < 6 else 16
            self.cv.itemconfig("ready_title", font=(F, int(size), "bold"))
            self.root.after(1500, pulse_title)

        self.root.after(800, pulse_title)

        # Hairline
        self.cv.create_line(S["xl"], 85, w-S["xl"], 85,
                           fill=C["hairline"], width=1)

        # Card background
        card_x = S["xl"]
        card_w = w - 2*S["xl"]
        card_y = 105
        section_h = 55

        # Repos
        cy1 = card_y
        self.cv.create_rectangle(card_x, cy1, card_x+card_w, cy1+section_h,
                                 fill=C["surface_card"], outline=C["hairline"], width=1)
        bx1, by1 = card_x+S["md"], cy1+S["md"]
        if self.repo_files:
            pnames = ", ".join(pn for _, pn, _ in self.repo_files)
            total_urls = sum(len(urls) for _, _, urls in self.repo_files)
            txt = f"仓库文件  ·  {len(self.repo_files)} 个仓库, {total_urls} 个链接"
            detail = pnames
        else:
            txt = "仓库文件  ·  未找到"
            detail = ""
        self.cv.create_text(bx1, by1+6, text=txt, anchor="w",
                           font=(F, 11, "bold"),
                           fill=C["success"] if self.repo_files else C["warning"],
                           tags="repos_line1")
        if detail:
            self.cv.create_text(bx1, by1+26, text=detail, anchor="w",
                               font=(F, 9), fill=C["muted"], tags="repos_line2")

        # Plugin Pack
        cy2 = cy1 + section_h + S["sm"]
        self.cv.create_rectangle(card_x, cy2, card_x+card_w, cy2+section_h,
                                 fill=C["surface_card"], outline=C["hairline"], width=1)
        bx2, by2 = card_x+S["md"], cy2+S["md"]
        if self.plugin_pack_dir:
            txt = f"插件包  ·  {os.path.basename(self.plugin_pack_dir)} ({self.plugin_pack_count} 个文件)"
            detail = self.plugin_pack_dir
        else:
            txt = "插件包  ·  未找到"
            detail = ""
        self.cv.create_text(bx2, by2+6, text=txt, anchor="w",
                           font=(F, 11, "bold"),
                           fill=C["success"] if self.plugin_pack_dir else C["warning"],
                           tags="pack_line1")
        if detail:
            self.cv.create_text(bx2, by2+26, text=detail, anchor="w",
                               font=(F, 9), fill=C["muted"], tags="pack_line2")

        # Target —— 多端可点选切换
        cy3 = cy2 + section_h + S["sm"]
        self.cv.create_rectangle(card_x, cy3, card_x+card_w, cy3+section_h,
                                 fill=C["surface_card"], outline=C["hairline"], width=1,
                                 tags="target_card")
        bx3, by3 = card_x+S["md"], cy3+S["md"]
        multi = len(self.detected_targets) > 1
        if self.target_dir:
            txt = f"卫月目录  ·  {os.path.basename(self.target_dir)}"
            if self.target_alias:
                txt += f"  ·  {self.target_alias}"
            if not os.path.isfile(os.path.join(self.target_dir, "dalamudConfig.json")):
                txt += "  ·  未启动(请先运行卫月一次)"
        else:
            txt = "卫月目录  ·  未找到(插件包未含 XIVLauncher 目录)"
        self.cv.create_text(bx3, by3+6, text=txt, anchor="w",
                           font=(F, 11, "bold"),
                           fill=C["success"] if self.target_dir else C["warning"],
                           tags="target_line1")
        if self.target_dir:
            self.cv.create_text(bx3, by3+26, text=self.target_dir, anchor="w",
                               font=(F, 9), fill=C["muted"], tags="target_line2")
        else:
            self.cv.create_text(bx3, by3+26, text="请先至少启动一次卫月以生成配置文件",
                               anchor="w", font=(F, 9), fill=C["muted"], tags="target_line2")

        # 绑定切换端（先解绑再绑定，避免反复重绘叠加回调）
        for t in ("target_card", "target_line1", "target_line2"):
            self.cv.tag_unbind(t, "<Button-1>")
            self.cv.tag_bind(t, "<Button-1>", lambda e: self._choose_target())
        if multi:
            self.cv.tag_bind("target_card", "<Enter>",
                lambda e: self.cv.itemconfig("target_card", fill=C["surface_elevated"], outline=C["ink"]))
            self.cv.tag_bind("target_card", "<Leave>",
                lambda e: self.cv.itemconfig("target_card", fill=C["surface_card"], outline=C["hairline"]))

        # Status verdict
        verdict_y = cy3 + section_h + S["lg"]
        if self.can_install:
            verdict_txt = "✔  一 切 就 绪  可 以 安 装"
            verdict_color = C["success"]
        else:
            missing = []
            if not self.repo_files: missing.append("仓库文件")
            if not self.plugin_pack_dir: missing.append("插件包")
            if not self._target_ready(): missing.append("卫月目录(请先运行卫月)")
            verdict_txt = f"⚠  缺 少 : {' / '.join(missing)}"
            verdict_color = C["warning"]
        self.cv.create_text(cx, verdict_y, text=verdict_txt,
                           font=(F, 12, "bold"), fill=verdict_color,
                           tags="verdict")

        # Divider
        div_y = verdict_y + S["lg"]
        self.cv.create_line(card_x, div_y, card_x+card_w, div_y,
                           fill=C["hairline"], width=1)

        # Buttons area
        btn_y = div_y + S["lg"]
        btn_w = (card_w - S["sm"]) // 2
        btn_h = 40

        # 重新检测 (左)
        rx1, ry1 = card_x, btn_y
        self.cv.create_rectangle(rx1, ry1, rx1+btn_w, ry1+btn_h,
                                 fill=C["surface_card"], outline=C["hairline"],
                                 tags="rescan_btn")
        self.cv.create_text(rx1+btn_w//2, ry1+btn_h//2,
                           text="重新检测", font=(F, 10, "bold"),
                           fill=C["muted"], tags="rescan_text")
        self.cv.tag_bind("rescan_text", "<Button-1>", lambda e: self._re_scan())
        self.cv.tag_bind("rescan_btn", "<Button-1>", lambda e: self._re_scan())
        self.cv.tag_bind("rescan_btn", "<Enter>",
            lambda e: self.cv.itemconfig("rescan_btn", fill=C["surface_elevated"], outline=C["ink"]))
        self.cv.tag_bind("rescan_btn", "<Leave>",
            lambda e: self.cv.itemconfig("rescan_btn", fill=C["surface_card"], outline=C["hairline"]))

        # 安装 (右)
        ix1, iy1 = card_x+btn_w+S["sm"], btn_y
        if self.can_install:
            btn_bg = C["m_blue_dark"]
            btn_fg = C["ink"]
        else:
            btn_bg = C["surface_soft"]
            btn_fg = C["muted"]
        self.cv.create_rectangle(ix1, iy1, ix1+btn_w, iy1+btn_h,
                                 fill=btn_bg, outline=btn_bg,
                                 tags="install_btn")
        self.cv.create_text(ix1+btn_w//2, iy1+btn_h//2,
                           text="安 装", font=(F, 11, "bold"),
                           fill=btn_fg, tags="install_text")
        self.cv.create_text(ix1+btn_w//2, iy1-S["xs"],
                           text=">>>", font=(F, 14, "bold"),
                           fill=C["m_red"] if self.can_install else C["muted"],
                           tags="install_arrow")

        self.cv.tag_bind("install_text", "<Button-1>",
            lambda e: self._on_install())
        self.cv.tag_bind("install_btn", "<Button-1>",
            lambda e: self._on_install())
        self.cv.tag_bind("install_arrow", "<Button-1>",
            lambda e: self._on_install())
        if self.can_install:
            self.cv.tag_bind("install_btn", "<Enter>",
                lambda e: self._btn_hover("install", ix1, iy1, btn_w, btn_h, True))
            self.cv.tag_bind("install_btn", "<Leave>",
                lambda e: self._btn_hover("install", ix1, iy1, btn_w, btn_h, False))

        # Missing fix buttons
        if not self.can_install:
            fy = btn_y + btn_h + S["md"]
            fix_w = (card_w - S["sm"]*2) // 3

            rbx = card_x
            self._draw_fix_btn("仓库", rbx, fy, fix_w, 32, self._pick_repos)
            rbx += fix_w + S["sm"]
            self._draw_fix_btn("插件包", rbx, fy, fix_w, 32, self._pick_plugin)
            rbx += fix_w + S["sm"]
            self._draw_fix_btn("卫月", rbx, fy, fix_w, 32, self._pick_target)

        # Update status line
        self.status_line.configure(
            text="POWERED BY ///M  ·  就绪待命" if self.can_install
            else "POWERED BY ///M  ·  ")

    def _btn_hover(self, name, x, y, w, h, enter):
        tag = f"{name}_btn"
        if enter:
            self.cv.itemconfig(tag, fill=C["surface_elevated"], outline=C["ink"])
        else:
            self.cv.itemconfig(tag, fill=C["surface_card"], outline=C["hairline"])

    def _draw_fix_btn(self, label, x, y, w, h, cmd):
        self.cv.create_rectangle(x, y, x+w, y+h,
                                 fill=C["surface_elevated"], outline=C["hairline"],
                                 tags=f"fix_{label}")
        self.cv.create_text(x+w//2, y+h//2,
                           text=f"选择{label}", font=(F, 9, "bold"),
                           fill=C["warning"], tags=f"fix_{label}_text")
        self.cv.tag_bind(f"fix_{label}", "<Button-1>", lambda e: cmd())
        self.cv.tag_bind(f"fix_{label}_text", "<Button-1>", lambda e: cmd())
        self.cv.tag_bind(f"fix_{label}", "<Enter>",
            lambda e: self.cv.itemconfig(f"fix_{label}", fill=C["surface_card"], outline=C["ink"]))
        self.cv.tag_bind(f"fix_{label}", "<Leave>",
            lambda e: self.cv.itemconfig(f"fix_{label}", fill=C["surface_elevated"], outline=C["hairline"]))

    def _pick_repos(self):
        paths = filedialog.askopenfilenames(
            title="Select repo_*.txt",
            filetypes=[("Repo files","repo_*.txt"),("Text","*.txt")])
        if paths:
            self.repo_files = [(p, *parse_repo_file(p)) for p in paths]
            self._refresh_state()

    def _pick_plugin(self):
        d = filedialog.askdirectory(title="Select plugin pack folder")
        if d:
            self.plugin_pack_dir = d
            self.plugin_pack_count = sum(1 for _ in Path(d).rglob("*") if _.is_file())
            self._refresh_state()

    def _pick_target(self):
        d = filedialog.askdirectory(title="Select XIVLauncherCN / XIVLauncherTC / XIVLauncher")
        if d and os.path.isfile(os.path.join(d, "dalamudConfig.json")):
            self._set_target(d)

    def _set_target(self, d):
        """设置安装目标并更新状态"""
        self.target_dir = d
        self.target_alias = infer_alias(d)
        up = d.upper()
        self.server = "tc" if "TC" in up else ("cn" if "CN" in up else "global")
        self._refresh_state()

    def _target_ready(self):
        """目标卫月目录是否已就绪（存在 dalamudConfig.json）"""
        return bool(self.target_dir) and os.path.isfile(
            os.path.join(self.target_dir, "dalamudConfig.json"))

    def _choose_target(self):
        """多端时弹框让用户选择要把插件装到哪个端"""
        if getattr(self, "_choosing", False):
            return
        targets = self.detected_targets
        if not targets:
            messagebox.showinfo("未检测到卫月",
                "未自动找到任何卫月目录。\n请点「选择卫月」按钮手动指定。",
                parent=self.root)
            return
        if len(targets) == 1:
            self._set_target(targets[0][0])
            return

        self._choosing = True
        d = Toplevel(self.root); d.title("选择安装端"); d.geometry("480x380")
        d.resizable(False, False); d.configure(bg=C["canvas"])
        d.transient(self.root); d.grab_set()
        d.update_idletasks()
        x = self.root.winfo_x()+(self.root.winfo_width()-480)//2
        y = self.root.winfo_y()+(self.root.winfo_height()-380)//2
        d.geometry(f"+{x}+{y}")

        cv = tk.Canvas(d, height=4, bg=C["canvas"], highlightthickness=0)
        cv.pack(fill=tk.X); draw_m_stripe(cv, 0, 0, 480, 4)

        hdr = tk.Frame(d, bg=C["canvas"])
        hdr.pack(fill=tk.X, padx=S["lg"], pady=(S["lg"], S["sm"]))
        tk.Label(hdr, text="选 择 安 装 端", font=(F,14,"bold"),
                 fg=C["ink"], bg=C["canvas"]).pack(anchor="w")
        tk.Label(hdr, text="检测到多个卫月端，请选择要把插件装到哪里",
                 font=(F,9), fg=C["muted"], bg=C["canvas"]).pack(anchor="w", pady=(S["xs"],0))

        list_f = tk.Frame(d, bg=C["canvas"])
        list_f.pack(fill=tk.BOTH, expand=True, padx=S["lg"], pady=(S["md"], S["sm"]))

        chosen = [None]
        row_widgets = []
        def select(idx):
            chosen[0] = idx
            for i, row in enumerate(row_widgets):
                on = (i == idx)
                row.configure(fill=C["surface_elevated"] if on else C["surface_card"],
                              highlightbackground=C["ink"] if on else C["hairline"])
        def confirm():
            if chosen[0] is None:
                chosen[0] = 0
            self._set_target(targets[chosen[0]][0])
            self._choosing = False
            d.destroy()

        for idx, (path, alias) in enumerate(targets):
            row = tk.Frame(list_f, bg=C["surface_card"],
                           highlightbackground=C["hairline"], highlightthickness=1)
            row.pack(fill=tk.X, pady=(0, S["sm"]))
            info = tk.Frame(row, bg=C["surface_card"])
            info.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=S["md"], pady=S["sm"])
            tk.Label(info, text=f"{alias}  ·  {os.path.basename(path)}",
                     font=(F,11,"bold"), fg=C["ink"], bg=C["surface_card"],
                     anchor="w").pack(fill=tk.X)
            tk.Label(info, text=path, font=(F,8), fg=C["muted"],
                     bg=C["surface_card"], anchor="w").pack(fill=tk.X)
            def _bind_row(w, i):
                w.bind("<Button-1>", lambda e, i=i: select(i))
                for c in w.winfo_children():
                    _bind_row(c, i)
            _bind_row(row, idx)
            row_widgets.append(row)
            if path == self.target_dir:
                select(idx)
        if chosen[0] is None:
            select(0)

        bf = tk.Frame(d, bg=C["canvas"])
        bf.pack(fill=tk.X, padx=S["lg"], pady=(0, S["lg"]))
        ok = tk.Canvas(bf, height=40, bg=C["canvas"], highlightthickness=0, cursor="hand2")
        ok.pack(fill=tk.X)
        def odn(e=None):
            w,h=ok.winfo_width(),ok.winfo_height();ok.delete("all")
            ok.create_rectangle(0,0,w,h,fill=C["m_blue_dark"],outline=C["m_blue_dark"])
            ok.create_text(w/2,h/2,text="确 认 选 择",font=(F,11,"bold"),fill=C["ink"])
        def odh(e=None):
            w,h=ok.winfo_width(),ok.winfo_height();ok.delete("all")
            ok.create_rectangle(0,0,w,h,fill="#1e7de3",outline="#1e7de3")
            ok.create_text(w/2,h/2,text="确 认 选 择",font=(F,11,"bold"),fill=C["ink"])
        ok.bind("<Configure>",odn);ok.bind("<Enter>",odh);ok.bind("<Leave>",odn)
        ok.bind("<Button-1>", lambda e: confirm())

        d.protocol("WM_DELETE_WINDOW", lambda: confirm())
        d.wait_window()
        self._choosing = False

    def _auto_resolve_target(self):
        """重新检测：根据安装器同目录的插件包判定端别，目标指向 %APPDATA%/对应端"""
        app_dir = get_app_dir()
        pack = find_pack_server(app_dir)
        if pack:
            _name, self.target_alias, self.server = pack
            self.target_dir = resolve_target_dir(_name)
            self.detected_targets = [(self.target_dir, self.target_alias)]
        else:
            self.target_dir = ""
            self.target_alias = ""
            self.server = "global"
            self.detected_targets = []
        self._refresh_state()

    def _refresh_state(self):
        self.can_install = bool(self.repo_files and self.plugin_pack_dir and self._target_ready())
        self.phase = "revealed"
        w = self.cv.winfo_width()
        h = self.cv.winfo_height()
        self._draw_revealed(w, h)

    def _re_scan(self):
        """重新检测当前目录"""
        app_dir = get_app_dir()
        self.repo_files = scan_repos(app_dir)
        self.plugin_pack_dir, self.plugin_pack_count = find_plugin_pack(app_dir)
        self._auto_resolve_target()

    def _on_install(self):
        if not self.can_install:
            missing = []
            if not self.repo_files: missing.append("仓库文件")
            if not self.plugin_pack_dir: missing.append("插件包")
            if not self._target_ready(): missing.append("卫月目录(请先运行卫月)")
            msg_error(self.root, "未就绪", f"缺少: {'、'.join(missing)}。",
                       [f"当前目录未检测到完整的安装要素"],
                       ["将所需文件放入同一目录后点击「重新检测」"])
            return
        if not show_preview(self.root, self):
            return
        self._execute_install()

    def _execute_install(self):
        

        prog = Toplevel(self.root); prog.title("///M  安装中")
        prog.geometry("520x360"); prog.resizable(False, False)
        prog.configure(bg=C["canvas"])
        prog.transient(self.root); prog.grab_set()
        prog.update_idletasks()
        x = self.root.winfo_x()+(self.root.winfo_width()-520)//2
        y = self.root.winfo_y()+(self.root.winfo_height()-360)//2
        prog.geometry(f"+{x}+{y}")

        pcv = tk.Canvas(prog, height=3, bg=C["canvas"], highlightthickness=0)
        pcv.pack(fill=tk.X); draw_m_stripe(pcv, 0, 0, 520, 3)

        hdr = tk.Frame(prog, bg=C["canvas"])
        hdr.pack(fill=tk.X, padx=S["lg"], pady=(S["lg"],S["md"]))
        tk.Label(hdr, text="执 行 中 . . .",
                 font=(F,16,"bold"),fg=C["ink"],bg=C["canvas"]).pack(anchor="w")

        sf = tk.Frame(prog, bg=C["canvas"])
        sf.pack(fill=tk.X, padx=S["lg"], pady=(0,S["md"]))

        icons_map = {"pending":("○",C["muted"]),"running":("●",C["m_blue_dark"]),
                     "done":("✓",C["success"]),"error":("✗",C["m_red"])}
        step_labels = ["备份配置", "更新仓库", "复制插件", "验证完成"]
        step_widgets = []
        for i, label in enumerate(step_labels):
            row = tk.Frame(sf, bg=C["canvas"]); row.pack(fill=tk.X, pady=(0,S["xs"]))
            icon = tk.Label(row, text="○", font=(F,13), fg=C["muted"],
                           bg=C["canvas"], width=2); icon.pack(side=tk.LEFT)
            lb = tk.Label(row, text=f"第 {i+1} 步  {label}",
                         font=(F,11,"bold"), fg=C["muted"],
                         bg=C["canvas"], anchor="w")
            lb.pack(side=tk.LEFT, padx=(S["xs"],0))
            det = tk.Label(row, text="", font=(F,9), fg=C["muted"], bg=C["canvas"])
            det.pack(side=tk.RIGHT)
            step_widgets.append({"icon":icon,"label":lb,"detail":det})

        def set_step(i, status, detail=""):
            ico, clr = icons_map[status]
            step_widgets[i]["icon"].configure(text=ico, fg=clr)
            step_widgets[i]["label"].configure(
                fg=C["ink"] if status!="pending" else C["muted"])
            if detail:
                step_widgets[i]["detail"].configure(text=detail, fg=C["body"])
            prog.update_idletasks()

        op = tk.Canvas(prog, height=4, bg=C["surface_soft"], highlightthickness=0)
        op.pack(fill=tk.X, padx=S["lg"], pady=(S["md"],S["sm"]))
        fl = tk.Label(prog, text="", font=(F,9), fg=C["muted"], bg=C["canvas"])
        fl.pack(fill=tk.X, padx=S["lg"], pady=(0,S["lg"]))

        def uo(pct):
            w = op.winfo_width(); op.delete("all")
            op.create_rectangle(0, 0, w*pct, 4, fill=C["success"], outline="")
            prog.update_idletasks()

        success = False; error_msg = ""; total_added = 0
        plugin_names = [pn for _, pn, _ in self.repo_files]

        try:
            config_path = os.path.join(self.target_dir, "dalamudConfig.json")

            set_step(0, "running", "创建备份..."); uo(0.08)
            if os.path.isfile(config_path):
                backup_config(config_path)
                set_step(0, "done", "已备份")
            else:
                set_step(0, "done", "跳过")
            uo(0.20)

            set_step(1, "running", "读取配置...")
            if not os.path.isfile(config_path):
                raise FileNotFoundError(f"dalamudConfig.json missing:\n{config_path}")
            cfg = load_json(config_path)
            set_step(1, "running", "添加仓库..."); uo(0.30)
            for _, _, urls in self.repo_files:
                total_added += add_repos(cfg, urls)
            save_json(config_path, cfg)
            all_u = sum(len(urls) for _,_,urls in self.repo_files)
            d = f"+{total_added}"
            if all_u - total_added > 0: d += f" (跳过{all_u-total_added})"
            set_step(1, "done", d); uo(0.50)

            set_step(2, "running", "部署文件中..."); uo(0.55)
            if self.plugin_pack_dir and os.path.isdir(self.plugin_pack_dir):
                def cb(cur,tot):
                    uo(0.55+0.35*cur/tot)
                    fl.configure(text=f"复制中  {cur}/{tot}")
                copy_dir_merge(self.plugin_pack_dir, self.target_dir, cb)
            set_step(2, "done", f"{self.plugin_pack_count} 个文件"); uo(0.90)

            set_step(3, "running", "校验中...")
            set_step(3, "done", "完成"); uo(1.0); fl.configure(text="安装完毕")
            success = True

        except FileNotFoundError as e:
            error_msg = str(e); set_step(0 if "dalamudConfig"in error_msg else 2,"error","FAILED")
        except PermissionError:
            error_msg = "ACCESS DENIED"; set_step(2,"error","DENIED")
        except json.JSONDecodeError:
            error_msg = "CONFIG CORRUPT"; set_step(1,"error","INVALID")
        except Exception as e:
            error_msg = str(e)
            for i in range(4):
                if step_widgets[i]["icon"].cget("text") not in ("✓","✗"):
                    set_step(i,"error","错误"); break

        prog.destroy()

        if success:
            show_completion(self.root, plugin_names, total_added)
        else:
            causes = [error_msg]; suggests = ["检查路径和权限"]
            if "dalamudConfig" in error_msg:
                causes = ["未找到 dalamudConfig.json",f"目标: {self.target_dir}"]
                suggests = ["先运行一次 XIVLauncher","路径在 %APPDATA%\\XIVLauncherCN"]
            elif "Permission"in error_msg or "DENIED"in error_msg:
                causes = ["无写入权限","文件被占用"]
                suggests = ["关闭 XIVLauncher","以管理员运行"]
            msg_error(self.root, "FAILED","安装失败。",causes,suggests)

# ═══════════ ENTRY ═══════════
if __name__ == "__main__":
    XIVPluginInstaller().root.mainloop()
