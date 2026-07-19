"""
Tkinter desktop GUI for ANT BMS — no browser, no extra dependencies.

    python -m antbms_tool gui
    python -m antbms_tool gui --fullscreen           # kiosk mode (Esc exits)
    python -m antbms_tool gui --demo                 # start with the simulator
    python -m antbms_tool gui --address AA:BB:...    # auto-connect on startup

Everything is done from the window: Scan for nearby ANT devices, pick one,
optionally enter the unlock password, Connect — or press Demo to explore with
a simulated battery. Tabs mirror the web dashboard:

  * Dashboard — SOC ring, pack V / current / power, per-cell bars with
    balancing markers, temperatures, MOS & balance state, protections
  * Settings  — read, edit (double-click), save-to-flash, backup & restore
  * Control   — the app's control commands, with confirmation for the
    destructive ones

Reuses ``webui.DashboardBridge``: a background thread owns the asyncio/BLE
loop, this module only ever talks to it through its thread-safe sync methods.
Tk widgets are touched exclusively from the Tk mainloop; worker threads hand
results back through a queue.
"""
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from . import protocol as p
from .webui import DashboardBridge


# ---------------------------------------------------------------------------
# palette (works on the Pi's default light theme)
# ---------------------------------------------------------------------------
BG = "#1b1f24"
PANEL = "#242a31"
FG = "#e6e9ec"
DIM = "#8a939d"
ACCENT = "#4aa3ff"
GOOD = "#3ecf6e"
WARN = "#f5a623"
BAD = "#ff5d5d"
BAR_BG = "#2f3740"

CELL_ROW_H = 26          # px per cell row in the cells canvas
POLL_MS = 400            # UI refresh cadence (telemetry itself arrives ~1/s)


class AntBmsGui(tk.Tk):
    def __init__(self, interval=1.0, address=None, password=None,
                 demo=False, fullscreen=False):
        super().__init__()
        self.title("ANT BMS")
        self.configure(bg=BG)
        self.geometry("900x600")
        self.minsize(640, 480)
        if fullscreen:
            self.attributes("-fullscreen", True)
            self.bind("<Escape>", lambda e: self.attributes("-fullscreen", False))

        self.bridge = DashboardBridge(interval=interval)
        self.bridge.start()

        self._q = queue.Queue()      # (callback, payload) from worker threads
        self._last_ts = 0            # last telemetry timestamp we rendered
        self._settings = {}          # key -> setting dict, as last read
        self._busy = False           # a blocking bridge call is in flight

        self._build_style()
        self._build_topbar()
        self._build_tabs()
        self._build_statusbar()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(POLL_MS, self._tick)

        if demo:
            self._do_demo()
        elif address:
            self.addr_var.set(address)
            if password is not None:
                self.pass_var.set(password)
            self._do_connect()

    # -- worker-thread plumbing ---------------------------------------------
    def _bg(self, label, fn, on_done=None):
        """Run a blocking bridge call in a thread; deliver the result (or the
        error) back to the Tk mainloop via the queue."""
        if self._busy:
            self._status(f"busy — wait for the current operation", WARN)
            return
        self._busy = True
        self._status(f"{label} …")

        def work():
            try:
                result = fn()
            except Exception as exc:
                self._q.put((self._on_bg_error, f"{label}: {type(exc).__name__}: {exc}"))
            else:
                self._q.put((self._on_bg_done, (label, on_done, result)))
        threading.Thread(target=work, daemon=True).start()

    def _on_bg_error(self, msg):
        self._busy = False
        self._status(msg, BAD)

    def _on_bg_done(self, payload):
        label, on_done, result = payload
        self._busy = False
        self._status(f"{label}: done", GOOD)
        if on_done:
            on_done(result)

    def _tick(self):
        """Mainloop heartbeat: drain the worker queue and repaint telemetry."""
        try:
            while True:
                cb, payload = self._q.get_nowait()
                cb(payload)
        except queue.Empty:
            pass
        snap = self.bridge.snapshot()
        self._render_connection(snap)
        tele = snap.get("telemetry")
        if tele and snap["ts"] != self._last_ts:
            self._last_ts = snap["ts"]
            self._render_telemetry(tele)
        self.after(POLL_MS, self._tick)

    # -- UI construction ----------------------------------------------------
    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", background=BG, foreground=FG, fieldbackground=PANEL)
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=FG,
                        padding=(16, 8))
        style.map("TNotebook.Tab", background=[("selected", ACCENT)],
                  foreground=[("selected", "#10151a")])
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("Panel.TLabel", background=PANEL, foreground=FG)
        style.configure("Dim.TLabel", background=BG, foreground=DIM)
        style.configure("TButton", background=PANEL, foreground=FG, padding=(10, 6))
        style.map("TButton", background=[("active", ACCENT)],
                  foreground=[("active", "#10151a")])
        style.configure("TEntry", insertcolor=FG)
        style.configure("TCombobox", arrowcolor=FG)
        style.configure("Treeview", background=PANEL, foreground=FG,
                        fieldbackground=PANEL, rowheight=24, borderwidth=0)
        style.configure("Treeview.Heading", background=BG, foreground=DIM)
        style.map("Treeview", background=[("selected", ACCENT)],
                  foreground=[("selected", "#10151a")])

    def _build_topbar(self):
        bar = ttk.Frame(self, style="Panel.TFrame", padding=8)
        bar.pack(fill="x")

        ttk.Button(bar, text="Scan", command=self._do_scan).pack(side="left")
        self.addr_var = tk.StringVar()
        self.addr_box = ttk.Combobox(bar, textvariable=self.addr_var, width=26)
        self.addr_box.pack(side="left", padx=(8, 0), fill="x", expand=True)

        ttk.Label(bar, text="password", style="Panel.TLabel").pack(side="left", padx=(12, 4))
        self.pass_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.pass_var, width=12, show="•").pack(side="left")

        ttk.Button(bar, text="Connect", command=self._do_connect).pack(side="left", padx=(12, 0))
        ttk.Button(bar, text="Demo", command=self._do_demo).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Disconnect", command=self._do_disconnect).pack(side="left", padx=(6, 0))

        self.conn_label = ttk.Label(bar, text="idle", style="Panel.TLabel")
        self.conn_label.pack(side="right")

    def _build_tabs(self):
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=8)
        self._build_dashboard_tab()
        self._build_settings_tab()
        self._build_control_tab()

    def _build_dashboard_tab(self):
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text="Dashboard")

        top = ttk.Frame(tab)
        top.pack(fill="x", pady=(8, 4))

        # SOC ring
        self.soc_canvas = tk.Canvas(top, width=130, height=130, bg=BG,
                                    highlightthickness=0)
        self.soc_canvas.pack(side="left", padx=(4, 16))

        # big numbers
        grid = ttk.Frame(top)
        grid.pack(side="left", fill="x", expand=True)
        big = ("TkDefaultFont", 22, "bold")
        small = ("TkDefaultFont", 9)
        self.stat_vars = {}
        for col, (key, label) in enumerate([
                ("pack_voltage", "PACK V"), ("current", "CURRENT A"),
                ("power", "POWER W"), ("state", "STATE")]):
            ttk.Label(grid, text=label, style="Dim.TLabel", font=small)\
                .grid(row=0, column=col, sticky="w", padx=12)
            var = tk.StringVar(value="—")
            lbl = tk.Label(grid, textvariable=var, font=big, bg=BG, fg=FG)
            lbl.grid(row=1, column=col, sticky="w", padx=12)
            self.stat_vars[key] = (var, lbl)

        info = ttk.Frame(top)
        info.pack(side="right", padx=8)
        self.info_var = tk.StringVar(value="")
        ttk.Label(info, textvariable=self.info_var, style="Dim.TLabel",
                  justify="right").pack(anchor="e")

        # per-cell bars
        wrap = ttk.Frame(tab)
        wrap.pack(fill="both", expand=True, pady=(4, 0))
        self.cells_canvas = tk.Canvas(wrap, bg=PANEL, highlightthickness=0)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.cells_canvas.yview)
        self.cells_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.cells_canvas.pack(side="left", fill="both", expand=True)

        # bottom status lines: temps / MOS / warnings
        self.temp_var = tk.StringVar(value="")
        self.mos_var = tk.StringVar(value="")
        self.warn_var = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.temp_var).pack(anchor="w", pady=(6, 0))
        ttk.Label(tab, textvariable=self.mos_var).pack(anchor="w")
        self.warn_label = tk.Label(tab, textvariable=self.warn_var, bg=BG, fg=WARN,
                                   anchor="w", justify="left")
        self.warn_label.pack(anchor="w", fill="x")

    def _build_settings_tab(self):
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text="Settings")

        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(8, 4))
        ttk.Button(bar, text="Read settings", command=self._do_read_settings).pack(side="left")
        ttk.Button(bar, text="Edit…", command=self._edit_selected).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Save to flash", command=self._do_save_flash).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Backup…", command=self._do_backup).pack(side="left", padx=(18, 0))
        ttk.Button(bar, text="Restore…", command=self._do_restore).pack(side="left", padx=(6, 0))

        cols = ("value", "unit", "name")
        self.tree = ttk.Treeview(tab, columns=cols, show="tree headings")
        self.tree.heading("#0", text="setting")
        self.tree.heading("value", text="value")
        self.tree.heading("unit", text="unit")
        self.tree.heading("name", text="description")
        self.tree.column("#0", width=280)
        self.tree.column("value", width=90, anchor="e")
        self.tree.column("unit", width=50)
        self.tree.column("name", width=320)
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda e: self._edit_selected())

    def _build_control_tab(self):
        from . import commands as cmds
        tab = ttk.Frame(self.tabs)
        self.tabs.add(tab, text="Control")

        canvas = tk.Canvas(tab, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        for gkey, glabel in cmds.COMMAND_GROUPS:
            ttk.Label(inner, text=glabel, style="Dim.TLabel",
                      font=("TkDefaultFont", 10, "bold")).pack(anchor="w", pady=(12, 4), padx=8)
            row = ttk.Frame(inner)
            row.pack(anchor="w", padx=8)
            n = 0
            for c in cmds.COMMANDS:
                if c.group != gkey or c.key == "save_settings":
                    continue
                ttk.Button(row, text=("⚠ " if c.confirm else "") + c.label,
                           command=lambda c=c: self._do_command(c))\
                    .grid(row=n // 3, column=n % 3, sticky="w", padx=4, pady=3)
                n += 1

    def _build_statusbar(self):
        self.status_label = tk.Label(self, text="ready", anchor="w",
                                     bg=PANEL, fg=DIM, padx=8, pady=4)
        self.status_label.pack(fill="x", side="bottom")

    def _status(self, msg, color=DIM):
        self.status_label.configure(text=msg, fg=color)

    # -- connection actions -------------------------------------------------
    def _do_scan(self):
        def done(devs):
            values = [f"{d['address']}  {d['name']}  ({d['rssi']} dBm)" for d in devs]
            self.addr_box["values"] = values
            if devs:
                self.addr_var.set(devs[0]["address"])
                self._status(f"scan: {len(devs)} ANT device(s) found", GOOD)
            else:
                self._status("scan: no ANT devices found", WARN)
        self._bg("scan", lambda: self.bridge.scan(6.0), done)

    def _address(self):
        # the combobox may hold "AA:BB:...  name  (rssi)" — take the first token
        return self.addr_var.get().split()[0] if self.addr_var.get().strip() else ""

    def _do_connect(self):
        addr = self._address()
        if not addr:
            self._status("enter or scan for a device address first", WARN)
            return
        pw = self.pass_var.get() or None
        self._bg(f"connect {addr}", lambda: self.bridge.connect(addr, pw))

    def _do_demo(self):
        self._bg("demo", lambda: self.bridge.start_demo(8))

    def _do_disconnect(self):
        self._bg("disconnect", self.bridge.disconnect)

    def _render_connection(self, snap):
        mode, err = snap["mode"], snap.get("error")
        if err and not snap["connected"]:
            self.conn_label.configure(text=f"error: {err}", foreground=BAD)
        elif mode == "live":
            age = snap.get("age")
            stale = age is not None and age > 5
            self.conn_label.configure(
                text=f"live · {snap['address']}" + ("  (stale)" if stale else ""),
                foreground=WARN if stale else GOOD)
        elif mode == "demo":
            self.conn_label.configure(text="demo battery", foreground=ACCENT)
        else:
            self.conn_label.configure(text="not connected", foreground=DIM)

    # -- dashboard rendering ------------------------------------------------
    def _render_telemetry(self, t):
        # SOC ring
        c = self.soc_canvas
        c.delete("all")
        soc = t.get("soc", 0)
        color = GOOD if soc > 40 else WARN if soc > 15 else BAD
        c.create_oval(8, 8, 122, 122, outline=BAR_BG, width=10)
        if soc:
            c.create_arc(8, 8, 122, 122, start=90, extent=-3.6 * soc,
                         style="arc", outline=color, width=10)
        c.create_text(65, 58, text=f"{soc}%", fill=FG,
                      font=("TkDefaultFont", 20, "bold"))
        c.create_text(65, 84, text="SOC", fill=DIM, font=("TkDefaultFont", 9))

        # big stats
        cur = t.get("current", 0)
        self.stat_vars["pack_voltage"][0].set(f"{t.get('pack_voltage', 0):.2f}")
        self.stat_vars["current"][0].set(f"{cur:+.2f}")
        self.stat_vars["current"][1].configure(
            fg=GOOD if cur > 0.05 else BAD if cur < -0.05 else FG)
        self.stat_vars["power"][0].set(f"{t.get('power', 0)}")
        self.stat_vars["state"][0].set(t.get("state", "—"))

        self.info_var.set(
            f"SOH {t.get('soh', '—')}%\n"
            f"remain {t.get('remaining_capacity_ah', '—')} / {t.get('physical_capacity_ah', '—')} Ah\n"
            f"cycled {t.get('cycle_capacity_ah', '—')} Ah\n"
            f"runtime {t.get('runtime_s', 0) // 3600} h")

        self._render_cells(t)

        temps = "   ".join(f"T{i + 1}: {v}°C" for i, v in enumerate(t.get("temperatures", [])))
        self.temp_var.set(f"Temps  {temps}   MOS: {t.get('temp_mos')}°C"
                          f"   Balance: {t.get('temp_balance')}°C")
        self.mos_var.set(f"Charge MOS: {t.get('charge_mos')}    "
                         f"Discharge MOS: {t.get('discharge_mos')}    "
                         f"Balance: {t.get('balance')}")
        prot, warn = t.get("protections", []), t.get("warnings", [])
        if prot:
            self.warn_label.configure(fg=BAD)
            self.warn_var.set("PROTECTION: " + ", ".join(prot))
        elif warn:
            self.warn_label.configure(fg=DIM)
            self.warn_var.set(", ".join(warn))
        else:
            self.warn_var.set("")

    def _render_cells(self, t):
        c = self.cells_canvas
        c.delete("all")
        cells = t.get("cells") or []
        if not cells:
            return
        width = max(c.winfo_width(), 300)
        vmin, vmax = min(cells), max(cells)
        lo = min(3.0, vmin - 0.02)
        hi = max(3.65, vmax + 0.02)
        bal = set(t.get("balancing_cells", []))
        x0, x1 = 120, width - 140
        for i, v in enumerate(cells, 1):
            y = 8 + (i - 1) * CELL_ROW_H
            frac = (v - lo) / (hi - lo)
            fill = WARN if i in bal else ACCENT
            c.create_text(8, y + 8, anchor="w", fill=DIM, text=f"Cell {i}")
            c.create_rectangle(x0, y, x1, y + 16, fill=BAR_BG, width=0)
            c.create_rectangle(x0, y, x0 + frac * (x1 - x0), y + 16, fill=fill, width=0)
            marks = []
            if v == vmax:
                marks.append("max")
            if v == vmin:
                marks.append("min")
            if i in bal:
                marks.append("BAL")
            c.create_text(x1 + 8, y + 8, anchor="w", fill=FG,
                          text=f"{v:.3f}V" + (f"  {' '.join(marks)}" if marks else ""))
        c.create_text(8, 8 + len(cells) * CELL_ROW_H + 6, anchor="w", fill=DIM,
                      text=f"Δ {t.get('cell_v_diff', 0) * 1000:.0f} mV   "
                           f"avg {t.get('cell_v_avg', 0)}V")
        c.configure(scrollregion=(0, 0, width, len(cells) * CELL_ROW_H + 40))

    # -- settings actions ---------------------------------------------------
    def _do_read_settings(self):
        def done(settings):
            self._settings = settings
            self._fill_tree(settings)
        self._bg("read settings", self.bridge.get_settings, done)

    def _fill_tree(self, settings):
        from .registers import SETTING_GROUPS
        self.tree.delete(*self.tree.get_children())
        for g in SETTING_GROUPS:
            members = [(k, v) for k, v in settings.items() if v.get("group") == g["key"]]
            if not members:
                continue
            parent = self.tree.insert("", "end", text=f"{g['label']} — {g['desc']}",
                                      open=True)
            for k, v in sorted(members, key=lambda kv: kv[1]["address"]):
                self.tree.insert(parent, "end", iid=k, text=k,
                                 values=(v["value"], v["unit"], v["name"]))
        ungrouped = [(k, v) for k, v in settings.items() if not v.get("group")]
        if ungrouped:
            parent = self.tree.insert("", "end", text="Other", open=True)
            for k, v in ungrouped:
                self.tree.insert(parent, "end", iid=k, text=k,
                                 values=(v["value"], v["unit"], v["name"]))

    def _edit_selected(self):
        sel = self.tree.selection()
        if not sel or sel[0] not in self._settings:
            self._status("select a setting row first (read settings if empty)", WARN)
            return
        key = sel[0]
        item = self._settings[key]
        self._edit_dialog(key, item)

    def _edit_dialog(self, key, item):
        dlg = tk.Toplevel(self)
        dlg.title(f"Edit {key}")
        dlg.configure(bg=BG)
        dlg.transient(self)
        dlg.grab_set()
        ttk.Label(dlg, text=f"{item['name']}").pack(padx=16, pady=(14, 2))
        unit = f" ({item['unit']})" if item["unit"] else ""
        ttk.Label(dlg, text=f"{key}{unit}", style="Dim.TLabel").pack(padx=16)
        var = tk.StringVar(value=str(item["value"]))
        entry = ttk.Entry(dlg, textvariable=var, width=16, justify="center")
        entry.pack(pady=10)
        entry.select_range(0, "end")
        entry.focus_set()
        save_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(dlg, text="save to flash", variable=save_var).pack()

        def ok(*_):
            try:
                value = float(var.get())
            except ValueError:
                self._status("value must be a number", WARN)
                return
            dlg.destroy()
            save = save_var.get()

            def done(_):
                item["value"] = value
                if self.tree.exists(key):
                    self.tree.set(key, "value", value)
            self._bg(f"set {key} = {value}" + (" (save)" if save else ""),
                     lambda: self.bridge.set_value(key, value, save=save), done)

        btns = ttk.Frame(dlg)
        btns.pack(pady=(8, 14))
        ttk.Button(btns, text="Write", command=ok).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="left", padx=4)
        entry.bind("<Return>", ok)

    def _do_save_flash(self):
        if messagebox.askyesno("Save to flash", "Persist current settings to flash?"):
            self._bg("save to flash", self.bridge.save)

    def _do_backup(self):
        path = filedialog.asksaveasfilename(
            title="Backup settings to…", defaultextension=".json",
            initialfile="antbms_backup.json",
            filetypes=[("JSON", "*.json"), ("All files", "*")])
        if path:
            self._bg(f"backup → {path}", lambda: self.bridge.backup(path))

    def _do_restore(self):
        path = filedialog.askopenfilename(
            title="Restore settings from…",
            filetypes=[("JSON", "*.json"), ("All files", "*")])
        if not path:
            return
        self._bg(f"verify ← {path}",
                 lambda: self.bridge.verify_restore(path),
                 lambda report: self._restore_dialog(path, report))

    def _restore_dialog(self, path, r):
        """Show the pre-flight verification report; restore only on confirm."""
        dlg = tk.Toplevel(self)
        dlg.title("Verify restore")
        dlg.configure(bg=BG)
        dlg.transient(self)
        dlg.grab_set()

        def row(text, ok=None):
            color = FG if ok is None else GOOD if ok else BAD
            tk.Label(dlg, text=text, bg=BG, fg=color, anchor="w",
                     justify="left").pack(fill="x", padx=16, pady=1)

        row(f"Backup: {path}")
        row(f"created {r.get('timestamp') or '?'}   "
            f"from device {r.get('backup_address') or '?'}")
        if r["address_match"] is False:
            row(f"⚠ backup is from a DIFFERENT device "
                f"(connected: {r['connected_address']})", ok=False)
        row(f"Items:  backup {r['backup_count']} / device {r['device_count']}",
            ok=r["backup_count"] == r["device_count"])
        nm = len(r["name_mismatches"])
        row(f"Names:  {r['backup_count'] - nm} matched, {nm} mismatched", ok=nm == 0)
        for label, keys in (("only in backup", r["only_in_backup"]),
                            ("missing from backup", r["only_on_device"]),
                            ("unknown to this tool", r["unknown_keys"]),
                            ("edited in file (raw data wins)",
                             r["inconsistent_with_chunks"])):
            if keys:
                row(f"⚠ {len(keys)} {label}: " + ", ".join(keys[:6])
                    + (" …" if len(keys) > 6 else ""), ok=False)

        diffs = r["differences"]
        row(f"Values: {len(diffs)} will change, {r['identical']} identical",
            ok=True if not diffs else None)
        if diffs:
            box = tk.Text(dlg, height=min(10, len(diffs)), width=68, bg=PANEL,
                          fg=FG, relief="flat", highlightthickness=0)
            for d in diffs:
                unit = f" {d['unit']}" if d["unit"] else ""
                note = "   (live counter)" if d["volatile"] else ""
                box.insert("end",
                           f"{d['key']}:  {d['device']} → {d['backup']}{unit}{note}\n")
            box.configure(state="disabled")
            box.pack(fill="both", expand=True, padx=16, pady=6)

        row("Backup matches this device." if r["ok"] else
            "Backup does NOT fully match this device — restoring may be unsafe.",
            ok=r["ok"])
        row("Restore writes the values, reads everything back, and saves to\n"
            "flash only if the read-back matches. On any failure the previous\n"
            "settings are written back; flash is never touched on failure.")

        save_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(dlg, text="save to flash after successful verify",
                        variable=save_var).pack(pady=(6, 0))

        def go():
            save = save_var.get()
            dlg.destroy()
            self._bg(f"restore ← {path}",
                     lambda: self.bridge.restore(path, save=save),
                     self._restore_done)

        btns = ttk.Frame(dlg)
        btns.pack(pady=(8, 14))
        ttk.Button(btns, text="Restore" if r["ok"] else "Restore anyway",
                   command=go).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancel", command=dlg.destroy).pack(side="left", padx=4)

    def _restore_done(self, res):
        planned = res.get("planned", res["written"])
        vol = res["volatile_mismatches"]
        vol_note = f" ({len(vol)} live counter(s) drifted)" if vol else ""
        if res.get("rollback_ok") is None:
            rollback = ""
        elif res["rollback_ok"]:
            rollback = "The previous settings were written back and verified."
        else:
            rollback = ("Rollback INCOMPLETE — power-cycle or restart the BMS "
                        "to return to the saved settings.")
        if res.get("error"):
            messagebox.showwarning(
                "Restore failed",
                f"Restore stopped after {res['written']} of {planned} "
                f"registers:\n{res['error']}\n\n{rollback}\n"
                "Flash was NOT modified.")
            self._status("restore failed — flash unchanged"
                         + (" (rolled back)" if res.get("rollback_ok") else ""),
                         BAD)
        elif res["mismatches"]:
            keys = ", ".join(m["key"] for m in res["mismatches"][:8])
            messagebox.showwarning(
                "Restore verification FAILED",
                f"{len(res['mismatches'])} register(s) did not read back as "
                f"written:\n{keys}\n\n{rollback}\nFlash was NOT modified.")
            self._status(f"restore: {len(res['mismatches'])} mismatch(es) — "
                         + ("rolled back, " if res.get("rollback_ok") else
                            "ROLLBACK INCOMPLETE, ") + "flash unchanged", BAD)
        elif res["saved"]:
            self._status(f"restored {res['written']} registers — read-back "
                         f"verified, saved to flash{vol_note}", GOOD)
        else:
            self._status(f"restored {res['written']} registers — read-back "
                         f"verified, not saved to flash{vol_note}", GOOD)

    # -- control actions ----------------------------------------------------
    def _do_command(self, cmd):
        if cmd.confirm and not messagebox.askyesno("Confirm", f"Send: {cmd.label}?"):
            return
        self._bg(cmd.label, lambda: self.bridge.send_command(cmd.key))

    # -- shutdown -----------------------------------------------------------
    def _on_close(self):
        try:
            self.bridge.disconnect()
        except Exception:
            pass
        self.destroy()


def run(interval=1.0, address=None, password=None, demo=False, fullscreen=False):
    app = AntBmsGui(interval=interval, address=address, password=password,
                    demo=demo, fullscreen=fullscreen)
    app.mainloop()


if __name__ == "__main__":
    run()
