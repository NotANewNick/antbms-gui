"""
Local web dashboard for ANT BMS.

Launch with no arguments and do everything from the browser — scan, pick a
device, enter the unlock password, connect, or start a simulated demo:

    python -m antbms_tool dashboard
    # then open http://127.0.0.1:8765

A background thread runs an asyncio loop that owns the BLE connection and polls
realtime telemetry; a plain ``http.server`` serves the single-page UI + JSON
API (no extra dependencies beyond bleak, which is only needed for real devices).

API:
    GET  /api/state                       -> {mode, connected, address, telemetry, ...}
    POST /api/scan   {timeout}            -> [{address,name,rssi}, ...]
    POST /api/connect{address,password}   -> connect to a BMS
    POST /api/connect{demo:true,cells}    -> start the simulator
    POST /api/disconnect                  -> drop the connection
    GET  /api/settings                    -> {settings, groups}
    GET  /api/commands                    -> {groups, commands}
    POST /api/set    {key,value,save}     -> set one setting
    POST /api/save                        -> persist to flash
    POST /api/command{command}            -> send a control command
    POST /api/backup {path}               -> write a backup file
    POST /api/verify_restore {path}       -> compare a backup file to the device
    POST /api/restore{path,save}          -> restore from a backup file
                                             (writes, reads back, verifies;
                                             saves to flash only if clean)
"""
import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .backup import (
    build_backup,
    save_backup,
    load_backup,
    backup_to_register_writes,
    verify_backup,
)
from .web_assets import INDEX_HTML


class DemoEngine:
    """Simulated battery so the UI works with no hardware / no bleak."""

    def __init__(self, push, cells=8, interval=1.0):
        import math
        self._sin = math.sin
        self._push = push
        self.cells = cells
        self.interval = interval
        self._running = False
        self._t = 0
        self._soc = 64.0
        self._mos = {"charge_mos": ("on", 1), "discharge_mos": ("on", 1)}
        self._settings = self._demo_settings()

    def start(self):
        self._running = True
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self):
        self._running = False

    def _demo_settings(self):
        from .registers import REGISTERS, CAPACITY_HIGH_WORD_ADDRESSES, group_for_address
        from .codec import decode_value
        defaults = {
            "cell_overvoltage_protection": 3.65, "cell_overvoltage_recovery": 3.50,
            "cell_undervoltage_protection": 2.80, "cell_undervoltage_recovery": 3.00,
            "balance_limit_voltage": 3.40, "balance_start_voltage_diff": 0.005,
            "charge_overcurrent_protection": 100.0, "discharge_overcurrent_protection": 120.0,
            "configured_cell_count_series": self.cells,
        }
        out = {}
        for r in REGISTERS:
            if r.address in CAPACITY_HIGH_WORD_ADDRESSES:
                continue
            val = defaults.get(r.key, decode_value(r, 0))
            out[r.key] = {"id": r.id, "address": r.address, "name": r.name,
                          "raw": int(round(float(val) * r.scale)), "value": val, "unit": r.unit,
                          "group": group_for_address(r.address)}
        return out

    def _run(self):
        sin = self._sin
        while self._running:
            self._t += 1
            ph = self._t / 6.0
            current = round(22 * sin(ph) + 4 * sin(ph * 2.7), 2)   # +charge / -discharge
            self._soc = min(100.0, max(2.0, self._soc + current * 0.02))
            base = 3.30 + 0.05 * sin(ph / 3)
            cells = [round(base + 0.012 * sin(ph + i) + (0.004 if i == 3 else 0), 3)
                     for i in range(self.cells)]
            vmax, vmin = max(cells), min(cells)
            pack = round(sum(cells), 2)
            balancing = [i + 1 for i, v in enumerate(cells) if v > vmax - 0.003]
            state = "charging" if current > 0.5 else "discharging" if current < -0.5 else "idle"
            warnings = []
            if current > 0.5: warnings += ["charging", "charge MOS on"]
            if current < -0.5: warnings += ["discharging", "discharge MOS on"]
            if balancing: warnings.append("balancing on")
            self._push({
                "permission": 1, "state_code": 2, "state": state,
                "cell_count": self.cells, "temp_count": 2,
                "cells": cells, "temperatures": [round(24 + 3 * sin(ph / 4)), round(23 + 2 * sin(ph / 5))],
                "temp_mos": round(28 + 4 * sin(ph / 3)), "temp_balance": round(27 + 2 * sin(ph / 6)),
                "pack_voltage": pack, "current": current, "power": round(pack * current),
                "soc": round(self._soc), "soh": 99,
                "physical_capacity_ah": 100.0,
                "remaining_capacity_ah": round(self._soc, 1),
                "cycle_capacity_ah": 412.5, "runtime_s": 86400 * 3 + self._t,
                "cell_v_max": vmax, "cell_v_max_pos": cells.index(vmax) + 1,
                "cell_v_min": vmin, "cell_v_min_pos": cells.index(vmin) + 1,
                "cell_v_diff": round(vmax - vmin, 3),
                "cell_v_avg": round(sum(cells) / len(cells), 3),
                "charge_mos": self._mos["charge_mos"][0], "charge_mos_code": self._mos["charge_mos"][1],
                "discharge_mos": self._mos["discharge_mos"][0], "discharge_mos_code": self._mos["discharge_mos"][1],
                "balance": "auto balancing" if balancing else "off",
                "balance_code": 4 if balancing else 0,
                "balancing_cells": balancing,
                "protection_mask": 0, "warning_mask": 0,
                "protections": [], "warnings": warnings,
            })
            time.sleep(self.interval)

    # actions
    def get_settings(self):
        return self._settings

    def set_value(self, key, value, save=False):
        if key in self._settings:
            self._settings[key]["value"] = float(value)

    def save(self):
        pass

    def backup(self, path):
        data = {"format": "antbms-settings-backup", "version": 1, "device": {"address": "DEMO"},
                "settings": {k: {"value": v["value"], "raw": v["raw"], "name": v["name"], "unit": v["unit"]}
                             for k, v in self._settings.items()}}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        return path

    def restore(self, path, save=True):
        bk = load_backup(path)
        for k, item in bk.get("settings", {}).items():
            if k in self._settings:
                self._settings[k]["value"] = item["value"]
        return len(bk.get("settings", {}))

    def send_command(self, id_or_key):
        from . import commands as cmds
        cmd = cmds.resolve(id_or_key)
        eff = {"charge_mos_on": ("charge_mos", "on", 1),
               "charge_mos_off": ("charge_mos", "manual off", 15),
               "discharge_mos_on": ("discharge_mos", "on", 1),
               "discharge_mos_off": ("discharge_mos", "manual off", 15)}
        if cmd.key in eff:
            which, lbl, code = eff[cmd.key]
            self._mos[which] = (lbl, code)
        return cmd.label


class DashboardBridge:
    """Owns the asyncio/BLE loop; connection is controlled at runtime via the UI.

    mode is one of: 'idle', 'live' (connected to a BMS), 'demo'.
    """

    def __init__(self, interval=1.0):
        self.interval = interval
        self.lock = threading.Lock()
        self.mode = "idle"
        self.address = None
        self.password = None
        self.telemetry = None
        self.connected = False
        self.error = None
        self.ts = 0
        self._loop = None
        self._client = None
        self._stream_task = None
        self._demo = None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)

    def start(self):
        self._thread.start()
        self._ready.wait(5)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.call_soon(self._ready.set)
        self._loop.run_forever()

    def _submit(self, coro, timeout=30):
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout)

    def _push(self, tele):
        with self.lock:
            self.telemetry = tele
            self.ts = time.time()
            self.connected = True

    # ---- connection control (called from HTTP thread) ----
    def scan(self, timeout=6.0):
        return self._submit(self._scan(timeout), timeout=timeout + 8)

    async def _scan(self, timeout):
        from .client import scan
        devs = await scan(timeout=timeout, all_devices=False)
        return [{"address": a, "name": n, "rssi": r} for a, n, r in devs]

    def connect(self, address, password=None):
        return self._submit(self._connect(address, password), timeout=30)

    async def _connect(self, address, password):
        await self._teardown()
        from .client import AntBmsClient
        self.address = address
        self.password = password or None
        self._client = AntBmsClient(address)
        await self._client.connect()
        self.mode = "live"
        self.connected = True
        self.error = None
        self._stream_task = asyncio.ensure_future(self._stream())
        return {"mode": "live", "address": address}

    async def _stream(self):
        try:
            async for tele in self._client.stream_realtime(self.interval):
                if tele is not None:
                    self._push(tele)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.connected = False
            self.error = f"{type(exc).__name__}: {exc}"

    def start_demo(self, cells=8):
        return self._submit(self._start_demo(cells))

    async def _start_demo(self, cells):
        await self._teardown()
        self._demo = DemoEngine(self._push, cells=cells, interval=self.interval)
        self._demo.start()
        self.mode = "demo"
        self.address = "DEMO"
        self.connected = True
        self.error = None
        return {"mode": "demo"}

    def disconnect(self):
        return self._submit(self._teardown())

    async def _teardown(self):
        if self._stream_task:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except (asyncio.CancelledError, Exception):
                pass
            self._stream_task = None
        if self._client:
            try:
                await self._client.disconnect()
            except Exception:
                pass
            self._client = None
        if self._demo:
            self._demo.stop()
            self._demo = None
        with self.lock:
            self.mode = "idle"
            self.connected = False
            self.telemetry = None
            self.ts = 0
        return {"mode": "idle"}

    # ---- state / actions ----
    def snapshot(self):
        with self.lock:
            return {
                "mode": self.mode,
                "connected": self.connected,
                "address": self.address,
                "error": self.error,
                "ts": self.ts,
                "age": time.time() - self.ts if self.ts else None,
                "telemetry": self.telemetry,
            }

    def _require_live(self):
        if self.mode != "live" or self._client is None:
            raise RuntimeError("not connected to a BMS")

    def get_settings(self):
        if self.mode == "demo":
            return self._demo.get_settings()
        self._require_live()
        return self._submit(self._client.read_all_settings())

    def set_value(self, key, value, save=False):
        if self.mode == "demo":
            return self._demo.set_value(key, value, save=save)
        self._require_live()

        async def go():
            if self.password is not None:
                await self._client.unlock(self.password)
            await self._client.set_value(key, float(value), save=save)
        return self._submit(go())

    def save(self):
        if self.mode == "demo":
            return self._demo.save()
        self._require_live()

        async def go():
            if self.password is not None:
                await self._client.unlock(self.password)
            await self._client.save()
        return self._submit(go())

    def send_command(self, id_or_key):
        if self.mode == "demo":
            return self._demo.send_command(id_or_key)
        self._require_live()
        cmd = self._submit(self._client.send_command(id_or_key, password=self.password))
        return cmd.label

    def backup(self, path):
        if self.mode == "demo":
            return self._demo.backup(path)
        self._require_live()

        async def go():
            chunks = await self._client.read_all_chunks()
            save_backup(path, build_backup(chunks, {"address": self.address}))
        self._submit(go())
        return path

    def verify_restore(self, path):
        """Pre-flight: compare a backup file against the connected device."""
        backup = load_backup(path)
        if self.mode == "demo":
            return verify_backup(backup, self._demo.get_settings(), "DEMO")
        self._require_live()
        device = self._submit(self._client.read_all_settings())
        return verify_backup(backup, device, self.address)

    def restore(self, path, save=True):
        """Write all registers from a backup, read back and verify; saves to
        flash only if the read-back matches. Returns the result dict."""
        if self.mode == "demo":
            n = self._demo.restore(path, save=save)
            return {"planned": n, "written": n, "verified": True,
                    "saved": bool(save), "mismatches": [],
                    "volatile_mismatches": [], "rolled_back": False,
                    "rollback_ok": None, "error": None}
        self._require_live()
        backup = load_backup(path)
        writes = backup_to_register_writes(backup)

        async def go():
            if self.password is not None:
                await self._client.unlock(self.password)
            return await self._client.restore_verified(writes, save=save)
        # ~130 writes interleaved with the realtime stream take a while
        return self._submit(go(), timeout=120)


def make_handler(bridge: DashboardBridge):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _json(self, code, obj):
            self._send(code, json.dumps(obj, ensure_ascii=False))

        def _body(self):
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n) or b"{}")

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._send(200, INDEX_HTML, "text/html; charset=utf-8")
            elif self.path == "/api/state":
                self._json(200, bridge.snapshot())
            elif self.path == "/api/settings":
                try:
                    from .registers import SETTING_GROUPS
                    groups = [{"key": g["key"], "label": g["label"], "desc": g["desc"]}
                              for g in SETTING_GROUPS]
                    self._json(200, {"settings": bridge.get_settings(), "groups": groups})
                except Exception as exc:
                    self._json(500, {"error": str(exc)})
            elif self.path == "/api/commands":
                from . import commands as cmds
                groups = [{"key": k, "label": l} for k, l in cmds.COMMAND_GROUPS]
                items = [{"id": c.id, "key": c.key, "label": c.label,
                          "group": c.group, "confirm": c.confirm} for c in cmds.COMMANDS]
                self._json(200, {"groups": groups, "commands": items})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            try:
                b = self._body()
                if self.path == "/api/scan":
                    self._json(200, {"devices": bridge.scan(float(b.get("timeout", 6)))})
                elif self.path == "/api/connect":
                    if b.get("demo"):
                        self._json(200, bridge.start_demo(int(b.get("cells", 8))))
                    else:
                        self._json(200, bridge.connect(b["address"], b.get("password") or None))
                elif self.path == "/api/disconnect":
                    self._json(200, bridge.disconnect())
                elif self.path == "/api/set":
                    bridge.set_value(b["key"], b["value"], save=b.get("save", False))
                    self._json(200, {"ok": True})
                elif self.path == "/api/save":
                    bridge.save()
                    self._json(200, {"ok": True})
                elif self.path == "/api/command":
                    self._json(200, {"ok": True, "label": bridge.send_command(b["command"])})
                elif self.path == "/api/backup":
                    self._json(200, {"ok": True, "path": bridge.backup(b.get("path", "antbms_backup.json"))})
                elif self.path == "/api/verify_restore":
                    self._json(200, {"ok": True, "report": bridge.verify_restore(b["path"])})
                elif self.path == "/api/restore":
                    r = bridge.restore(b["path"], save=b.get("save", True))
                    self._json(200, {"ok": True, "registers": r["written"], **r})
                else:
                    self._json(404, {"error": "not found"})
            except Exception as exc:
                self._json(500, {"error": f"{type(exc).__name__}: {exc}"})

    return Handler


def serve(host="127.0.0.1", port=8765, interval=1.0,
          address=None, password=None, demo=False):
    """Start the dashboard. Connection is normally chosen in the browser, but
    ``address`` or ``demo`` may be given to auto-connect on startup."""
    bridge = DashboardBridge(interval=interval)
    bridge.start()
    if demo:
        bridge.start_demo()
    elif address:
        try:
            bridge.connect(address, password)
        except Exception as exc:
            print(f"(auto-connect failed: {exc} — connect from the browser)")
    httpd = ThreadingHTTPServer((host, port), make_handler(bridge))
    print(f"ANT BMS dashboard:  http://{host}:{port}   (Ctrl+C to stop)")
    print("Open the URL, then Scan & Connect — or click Demo.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
        httpd.shutdown()
