# -*- coding: utf-8 -*-
"""
SwiftHUD - PC Swift & Gaming HUD
Author : SoslticeDeveloper
License: MIT
"""
import os, sys, glob, json, shutil, ctypes, threading, subprocess, platform, winreg
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import psutil
import customtkinter as ctk
import datetime
import requests
import keyboard  # للتحكم في الميديا
try:
    import GPUtil
except ImportError:
    GPUtil = None

APP_NAME = "SwiftHUD"
VERSION = "1.1.0"
AUTHOR = "SoslticeDeveloper"
NOWIN = 0x08000000

# ----------------------------------------------------------------- helpers
def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def relaunch_as_admin():
    if getattr(sys, "frozen", False):
        exe, params = sys.executable, ""
    else:
        exe = sys.executable
        params = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, None, 1)

def ps(cmd, timeout=15):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                           capture_output=True, text=True, timeout=timeout, creationflags=NOWIN)
        return r.stdout.strip()
    except Exception:
        return ""

def fmt_size(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024: return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"

def is_reparse(path):
    try: return bool(os.lstat(path).st_file_attributes & 0x400)
    except Exception: return False

def dir_size(path):
    total = 0
    stack = [path]
    while stack:
        p = stack.pop()
        try:
            with os.scandir(p) as it:
                for e in it:
                    try:
                        if e.is_symlink() or is_reparse(e.path): continue
                        if e.is_dir(follow_symlinks=False): stack.append(e.path)
                        else: total += e.stat(follow_symlinks=False).st_size
                    except Exception: pass
        except Exception: pass
    return total

# ----------------------------------------------------------------- hardware
def cpu_name():
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
    except Exception: return platform.processor() or "Unknown CPU"

def disks_info():
    out = ps("Get-PhysicalDisk | Select-Object FriendlyName,MediaType,Size | ConvertTo-Json")
    try:
        data = json.loads(out)
        if isinstance(data, dict): data = [data]
        return [(d.get("FriendlyName", "?"), str(d.get("MediaType", "Unknown")), int(d.get("Size") or 0)) for d in data]
    except Exception: return []

def gpu_name():
    out = ps("(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join ' | '")
    return out or "Unknown GPU"

def get_gpu_usage():
    if not GPUtil: return 0
    try:
        gpus = GPUtil.getGPUs()
        return gpus[0].load * 100 if gpus else 0
    except Exception: return 0

def get_temperature():
    out = ps("Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature "
             "| Select-Object -ExpandProperty CurrentTemperature", timeout=6)
    temps = []
    for line in out.splitlines():
        try:
            c = int(line) / 10.0 - 273.15
            if 0 < c < 130: temps.append(c)
        except ValueError: pass
    return max(temps) if temps else None

def get_weather():
    # بيستخدم Open-Meteo API (مجاني وبدون مفاتيح) - القاهرة كمثال
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=30.0444&longitude=31.2357&current_weather=true"
        r = requests.get(url, timeout=5).json()
        temp = r['current_weather']['temperature']
        return f"{temp}°C"
    except Exception:
        return "--°C"

def os_advice(ram_gb, cores, has_ssd):
    lines = []
    if ram_gb < 4: best = "Windows 10 (lightweight/64-bit if possible). Windows 11 is NOT recommended."
    elif ram_gb < 8: best = "Windows 10 64-bit 22H2 is the sweet spot. Windows 11 runs but will feel tight."
    elif ram_gb < 16: best = "Windows 11 (or Windows 10) both run smoothly."
    else: best = "Any modern Windows (11 recommended). Your RAM is plenty."
    lines.append(f"Recommended OS: {best}")
    if cores <= 2: lines.append("Note: low core count, avoid heavy background apps while gaming.")
    if has_ssd is False: lines.append("Your system drive looks like an HDD: moving Windows to an SSD is the biggest speed upgrade you can make.")
    elif has_ssd is True: lines.append("SSD detected: good, boot and load times will be fast.")
    lines.append("Windows 11 also needs TPM 2.0 + Secure Boot + a supported CPU.")
    return "\n".join(lines)

# ----------------------------------------------------------------- cleaner
def temp_targets():
    local = os.environ.get("LOCALAPPDATA", "")
    win = os.environ.get("SystemRoot", r"C:\Windows")
    t = [os.environ.get("TEMP", ""), os.path.join(win, "Temp"), os.path.join(win, "Prefetch")]
    pats = [
        rf"{local}\Google\Chrome\User Data\*\Cache\Cache_Data", rf"{local}\Google\Chrome\User Data\*\Code Cache",
        rf"{local}\BraveSoftware\Brave-Browser\User Data\*\Cache\Cache_Data", rf"{local}\BraveSoftware\Brave-Browser\User Data\*\Code Cache",
        rf"{local}\Microsoft\Edge\User Data\*\Cache\Cache_Data", rf"{local}\Microsoft\Edge\User Data\*\Code Cache",
    ]
    for p in pats: t.extend(glob.glob(p))
    return [x for x in t if x and os.path.isdir(x)]

def wipe_folder(root):
    freed = 0
    for dirpath, dirs, files in os.walk(root, topdown=False):
        for f in files:
            fp = os.path.join(dirpath, f)
            try:
                sz = os.path.getsize(fp)
                os.remove(fp)
                freed += sz
            except Exception: pass
        for d in dirs:
            try: os.rmdir(os.path.join(dirpath, d))
            except Exception: pass
    return freed

def empty_recycle_bin():
    try: ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x1 | 0x2 | 0x4)
    except Exception: pass

def deep_clean():
    freed = 0
    for t in temp_targets(): freed += wipe_folder(t)
    empty_recycle_bin()
    return freed

# ----------------------------------------------------------------- RAM
def boost_ram():
    k32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    before = psutil.virtual_memory().available
    me = os.getpid()
    for p in psutil.process_iter(["pid"]):
        pid = p.info["pid"]
        if pid in (0, 4, me): continue
        h = k32.OpenProcess(0x0100 | 0x0400, False, pid)
        if h:
            try: psapi.EmptyWorkingSet(h)
            except Exception: pass
            k32.CloseHandle(h)
    after = psutil.virtual_memory().available
    return max(0, after - before)

# ----------------------------------------------------------------- junction mover
def candidate_folders():
    home = Path.home()
    pf = [os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]
    roots = []
    for p in pf: roots += [os.path.join(p, r"Steam\steamapps\common"), os.path.join(p, "Epic Games")]
    roots.append(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"))
    singles = [home / n for n in ("Downloads", "Videos", "Pictures", "Music")]
    running = set()
    for p in psutil.process_iter(["exe"]):
        try:
            if p.info["exe"]: running.add(p.info["exe"].lower())
        except Exception: pass
    items = []
    paths = [str(s) for s in singles]
    for r in roots:
        if os.path.isdir(r):
            for e in os.scandir(r):
                if e.is_dir(): paths.append(e.path)
    for p in paths:
        if not os.path.isdir(p) or is_reparse(p): continue
        busy = any(x.startswith(p.lower() + os.sep) for x in running)
        items.append((p, busy))
    return items

def move_with_junction(src, dst_root):
    name = os.path.basename(src.rstrip("\\/"))
    dst = os.path.join(dst_root, name)
    if os.path.exists(dst): return False, f"Destination already exists: {dst}"
    bak = src + ".swifthud_bak"
    try: shutil.copytree(src, dst, symlinks=True)
    except Exception as e:
        shutil.rmtree(dst, ignore_errors=True)
        return False, f"Copy failed: {e}"
    try: os.rename(src, bak)
    except Exception as e:
        shutil.rmtree(dst, ignore_errors=True)
        return False, f"Could not rename original (in use?): {e}"
    
    # إصلاح المسافات في المسار
    cmd_str = f'mklink /J "{src}" "{dst}"'
    r = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, creationflags=NOWIN)
    
    if r.returncode != 0:
        os.rename(bak, src)
        shutil.rmtree(dst, ignore_errors=True)
        return False, f"Junction failed (rolled back): {r.stderr or r.stdout}"
    shutil.rmtree(bak, ignore_errors=True)
    return True, dst

# ----------------------------------------------------------------- Mini HUD (النسخة المطورة)
class MiniHUD(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.85)
        self.geometry("220x140+50+50")
        self.configure(fg_color="#0d1117", border_width=1, border_color="#30363d")
        
        self.current_mode = 0 # 0: Stats, 1: Time/Weather, 2: Media
        self.title_lbl = ctk.CTkLabel(self, text="الإحصائيات", font=("Segoe UI", 12, "bold"), text_color="#58a6ff")
        self.title_lbl.pack(pady=(5, 0))
        
        # --- إطار الإحصائيات ---
        self.f_stats = ctk.CTkFrame(self, fg_color="transparent")
        self.cpu_l = ctk.CTkLabel(self.f_stats, text="CPU: 0% | GPU: 0%", font=("Consolas", 12))
        self.ram_l = ctk.CTkLabel(self.f_stats, text="RAM: 0% | Temp: --°C", font=("Consolas", 12))
        self.cpu_l.pack(); self.ram_l.pack()

        # --- إطار الساعة والطقس ---
        self.f_weather = ctk.CTkFrame(self, fg_color="transparent")
        self.clock_l = ctk.CTkLabel(self.f_weather, text="00:00", font=("Segoe UI", 24, "bold"))
        self.weather_l = ctk.CTkLabel(self.f_weather, text="الطقس: --°C", font=("Segoe UI", 14))
        self.clock_l.pack(pady=(5,0)); self.weather_l.pack()

        # --- إطار الميديا ---
        self.f_media = ctk.CTkFrame(self, fg_color="transparent")
        self.media_lbl = ctk.CTkLabel(self.f_media, text="Spotify / Media", font=("Segoe UI", 14, "bold"), text_color="#1DB954")
        self.media_lbl.pack(pady=(5,0))
        
        btn_frame = ctk.CTkFrame(self.f_media, fg_color="transparent")
        btn_frame.pack()
        ctk.CTkButton(btn_frame, text="⏮", width=40, command=lambda: keyboard.send('previous track')).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="⏯", width=40, command=lambda: keyboard.send('play/pause media')).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="⏭", width=40, command=lambda: keyboard.send('next track')).pack(side="left", padx=2)

        # --- أزرار التحكم العلوية ---
        top_bar = ctk.CTkFrame(self, fg_color="transparent", height=20)
        top_bar.pack(fill="x", side="bottom")
        ctk.CTkButton(top_bar, text="⚙", width=25, height=20, command=self.switch_mode, fg_color="transparent", hover_color="#30363d").pack(side="right", padx=2)
        ctk.CTkButton(top_bar, text="✖", width=25, height=20, command=self.close, fg_color="transparent", hover_color="#da3633").pack(side="right", padx=2)

        # ربط الأحداث للتحريك
        for w in [self, self.title_lbl, self.f_stats, self.f_weather, self.f_media]:
            w.bind("<Button-1>", self._start)
            w.bind("<B1-Motion>", self._drag)

        self.switch_mode() # لضبط العرض الأول
        psutil.cpu_percent(None)
        self._tick()

    def switch_mode(self):
        self.f_stats.pack_forget(); self.f_weather.pack_forget(); self.f_media.pack_forget()
        if self.current_mode == 0:
            self.title_lbl.configure(text="إحصائيات النظام")
            self.f_stats.pack()
        elif self.current_mode == 1:
            self.title_lbl.configure(text="الوقت والطقس")
            self.f_weather.pack()
        else:
            self.title_lbl.configure(text="مشغل الميديا")
            self.f_media.pack()
        self.current_mode = (self.current_mode + 1) % 3

    def _start(self, e):
        self._ox, self._oy = e.x_root - self.winfo_x(), e.y_root - self.winfo_y()

    def _drag(self, e):
        self.geometry(f"+{e.x_root - self._ox}+{e.y_root - self._oy}")

    def _tick(self):
        if not self.winfo_exists(): return
        
        # تحديث الإحصائيات
        c = psutil.cpu_percent(None)
        r = psutil.virtual_memory().percent
        g = get_gpu_usage()
        temp = get_temperature()
        temp_str = f"{temp:.0f}°C" if temp else "--°C"
        self.cpu_l.configure(text=f"CPU: {c:.0f}% | GPU: {g:.0f}%")
        self.ram_l.configure(text=f"RAM: {r:.0f}% | Temp: {temp_str}")

        # تحديث الساعة والطقس (كل ثانية للساعة)
        now = datetime.datetime.now().strftime("%I:%M %p")
        self.clock_l.configure(text=now)
        
        # تحديث الطقس (كل 5 دقائق تقريباً - هنا بنعمله كل 10 ثواني عشان التجربة)
        if not hasattr(self, '_last_weather_update') or (datetime.datetime.now() - self._last_weather_update).seconds > 600:
            self._last_weather_update = datetime.datetime.now()
            threading.Thread(target=self._fetch_weather, daemon=True).start()

        self.after(1000, self._tick)

    def _fetch_weather(self):
        w = get_weather()
        self.after(0, lambda: self.weather_l.configure(text=f"القاهرة: {w}"))

    def close(self):
        self.app.hud = None
        self.destroy()
        self.app.deiconify()


# ----------------------------------------------------------------- main app
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title(f"{APP_NAME} v{VERSION} - by {AUTHOR}")
        self.geometry("850x650")
        self.hud = None
        self.mover_vars = []

        head = ctk.CTkLabel(self, text="SwiftHUD", font=("Segoe UI", 26, "bold"))
        head.pack(pady=(12, 0))
        ctk.CTkLabel(self, text="PC Swift & Gaming HUD | by SoslticeDeveloper", text_color="#8b949e").pack()

        self.tabs = ctk.CTkTabview(self)
        self.tabs.pack(fill="both", expand=True, padx=14, pady=10)
        
        self.t_specs = self.tabs.add("المواصفات (Specs)")
        self.t_clean = self.tabs.add("التنظيف (Clean)")
        self.t_move = self.tabs.add("نقل الملفات (Move)")
        self.t_settings = self.tabs.add("الإعدادات (Settings)")

        self.build_specs(); self.build_clean(); self.build_move(); self.build_settings()
        
        self.after(300, self.scan_specs)
        self.after(1000, self.live_footer)

        self.footer = ctk.CTkLabel(self, text="", text_color="#8b949e")
        self.footer.pack(pady=(0, 8))

    # --- specs tab
    def build_specs(self):
        self.specs_box = ctk.CTkTextbox(self.t_specs, font=("Consolas", 13), wrap="word")
        self.specs_box.pack(fill="both", expand=True, padx=6, pady=6)
        ctk.CTkButton(self.t_specs, text="إعادة الفحص (Rescan)", command=self.scan_specs).pack(pady=4)

    def scan_specs(self):
        self.specs_box.delete("1.0", "end")
        self.specs_box.insert("end", "Scanning hardware...\n")
        def work():
            vm = psutil.virtual_memory()
            ram = vm.total / 1024 ** 3
            cores = psutil.cpu_count(logical=False) or 1
            threads = psutil.cpu_count(logical=True) or 1
            ds = disks_info()
            has_ssd = any("SSD" in d[1].upper() for d in ds) if ds else None
            txt = [f"OS      : {platform.system()} {platform.release()} ({platform.version()})",
                   f"CPU     : {cpu_name()}  ({cores} cores / {threads} threads)",
                   f"GPU     : {gpu_name()}",
                   f"RAM     : {ram:.1f} GB"]
            for n, m, s in ds: txt.append(f"Disk    : {n} - {m} - {fmt_size(s)}")
            txt += ["", "-" * 50, os_advice(ram, cores, has_ssd)]
            self.after(0, lambda: (self.specs_box.delete("1.0", "end"), self.specs_box.insert("end", "\n".join(txt))))
        threading.Thread(target=work, daemon=True).start()

    # --- clean tab
    def build_clean(self):
        self.log = ctk.CTkTextbox(self.t_clean, height=260, font=("Consolas", 12))
        self.log.pack(fill="both", expand=True, padx=6, pady=6)
        row = ctk.CTkFrame(self.t_clean, fg_color="transparent"); row.pack(pady=4)
        ctk.CTkButton(row, text="تنظيف عميق (Deep Clean)", width=160, command=self.do_clean).grid(row=0, column=0, padx=6)
        ctk.CTkButton(row, text="تحسين الرام (RAM Boost)", width=160, command=self.do_boost).grid(row=0, column=1, padx=6)
        ctk.CTkButton(row, text="تنظيف + تحسين", width=160, fg_color="#238636", command=self.do_both).grid(row=0, column=2, padx=6)
        ctk.CTkButton(self.t_clean, text="فتح النافذة العائمة (Mini-HUD)", fg_color="#8957e5", command=self.open_hud).pack(pady=8)

    def say(self, s): self.after(0, lambda: (self.log.insert("end", s + "\n"), self.log.see("end")))
    def do_clean(self):
        def w():
            self.say("Cleaning temp, Prefetch, browser caches...")
            self.say(f"Freed about {fmt_size(deep_clean())}")
        threading.Thread(target=w, daemon=True).start()
    def do_boost(self):
        def w(): self.say(f"RAM trimmed. Reclaimed about {fmt_size(boost_ram())}.")
        threading.Thread(target=w, daemon=True).start()
    def do_both(self):
        def w():
            self.say("Running full Clean + Boost...")
            f = deep_clean(); r = boost_ram()
            self.say(f"Done: disk freed {fmt_size(f)}, RAM reclaimed {fmt_size(r)}")
        threading.Thread(target=w, daemon=True).start()
    def open_hud(self):
        if self.hud is None:
            self.hud = MiniHUD(self)
            self.withdraw()

    # --- mover tab
    def build_move(self):
        top = ctk.CTkFrame(self.t_move, fg_color="transparent"); top.pack(fill="x")
        ctk.CTkButton(top, text="فحص المجلدات القابلة للنقل", command=self.scan_movable).pack(side="left", padx=6, pady=6)
        ctk.CTkButton(top, text="نقل المحدد...", fg_color="#238636", command=self.move_selected).pack(side="left", padx=6)
        self.mv_status = ctk.CTkLabel(top, text="", text_color="#8b949e"); self.mv_status.pack(side="left", padx=8)
        self.mv_list = ctk.CTkScrollableFrame(self.t_move)
        self.mv_list.pack(fill="both", expand=True, padx=6, pady=6)
        ctk.CTkLabel(self.t_move, text="يستخدم Directory Junctions: الويندوز هيفضل شايف المسار القديم. اقفل اللعبة/البرنامج قبل النقل.", text_color="#8b949e").pack(pady=2)

    def scan_movable(self):
        for w in self.mv_list.winfo_children(): w.destroy()
        self.mover_vars.clear()
        self.mv_status.configure(text="جاري فحص الأحجام...")
        def work():
            rows = []
            for p, busy in candidate_folders():
                sz = dir_size(p)
                if sz >= 50 * 1024 ** 2: rows.append((sz, p, busy))
            rows.sort(reverse=True)
            self.after(0, lambda: self.fill_movable(rows))
        threading.Thread(target=work, daemon=True).start()

    def fill_movable(self, rows):
        self.mv_status.configure(text=f"تم العثور على {len(rows)} مجلد")
        for sz, p, busy in rows:
            v = tk.BooleanVar()
            label = f"{fmt_size(sz):>10}   {p}" + ("   [قيد التشغيل]" if busy else "")
            cb = ctk.CTkCheckBox(self.mv_list, text=label, variable=v, font=("Consolas", 12), state="disabled" if busy else "normal")
            cb.pack(anchor="w", pady=2)
            self.mover_vars.append((v, p))

    def move_selected(self):
        sel = [p for v, p in self.mover_vars if v.get()]
        if not sel: return messagebox.showinfo(APP_NAME, "اختر مجلد واحد على الأقل.")
        dst = filedialog.askdirectory(title="اختر مجلد الوجهة في درايف آخر")
        if not dst: return
        if os.path.splitdrive(dst)[0].upper() == os.path.splitdrive(sel[0])[0].upper():
            if not messagebox.askyesno(APP_NAME, "ده نفس الدرايف! هل تريد الاستمرار؟"): return
        def work():
            for p in sel:
                self.after(0, lambda p=p: self.mv_status.configure(text=f"جاري نقل {os.path.basename(p)}..."))
                ok, msg = move_with_junction(p, dst)
                self.after(0, lambda ok=ok, msg=msg, p=p: messagebox.showinfo(APP_NAME, (f"تم النقل: {p}\n-> {msg}" if ok else f"فشل: {p}\n{msg}")))
            self.after(0, lambda: (self.mv_status.configure(text="انتهى"), self.scan_movable()))
        threading.Thread(target=work, daemon=True).start()

    # --- Settings Tab
    def build_settings(self):
        frame = ctk.CTkFrame(self.t_settings, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(frame, text="المظهر (Theme):", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 10))
        
        theme_var = tk.StringVar(value=ctk.get_appearance_mode())
        def change_theme(choice):
            ctk.set_appearance_mode(choice)
            
        ctk.CTkOptionMenu(frame, values=["Dark", "Light", "System"], command=change_theme, variable=theme_var).pack(anchor="w", pady=5)
        
        ctk.CTkLabel(frame, text="\n\nمعلومات:", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(20, 10))
        ctk.CTkLabel(frame, text="SwiftHUD v1.1.0\nيدعم النافذة العائمة، الطقس، والتحكم في الميديا.", justify="left").pack(anchor="w")

    # --- footer
    def live_footer(self):
        def w():
            t = get_temperature()
            s = f"درجة حرارة المعالج: {t:.0f} C" if t else "الحرارة: غير متاحة على هذا الجهاز"
            self.after(0, lambda: self.footer.configure(text=s))
        threading.Thread(target=w, daemon=True).start()
        self.after(5000, self.live_footer)

if __name__ == "__main__":
    if platform.system() != "Windows":
        print("SwiftHUD is a Windows application.")
        sys.exit(1)
    if not is_admin():
        relaunch_as_admin()
        sys.exit(0)
    App().mainloop()