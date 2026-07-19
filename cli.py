"""
Command-line interface for the ANT BMS tool.

    python -m antbms_tool scan
    python -m antbms_tool read    --address AA:BB:CC:DD:EE:FF
    python -m antbms_tool get     --address ... --key cell_overvoltage_protection
    python -m antbms_tool set     --address ... --key cell_overvoltage_protection --value 3.65 [--save]
    python -m antbms_tool backup  --address ... --out my_bms.json
    python -m antbms_tool restore --address ... --in my_bms.json [--save]
    python -m antbms_tool save    --address ...
    python -m antbms_tool registers           # list all known settings (offline)
"""
import argparse
import asyncio
import json
import sys

from . import protocol as p
from .registers import REGISTERS
from .backup import (
    build_backup,
    save_backup,
    load_backup,
    backup_to_register_writes,
    verify_backup,
)


def _print_settings(settings: dict):
    from .registers import SETTING_GROUPS
    width = max((len(k) for k in settings), default=10)

    def line(key, v):
        unit = f" {v['unit']}" if v["unit"] else ""
        print(f"  {key:<{width}}  {v['value']}{unit}   ({v['name']}, raw={v['raw']})")

    # group in app order; fall back to ungrouped if no group info present
    if settings and "group" in next(iter(settings.values())):
        for g in SETTING_GROUPS:
            members = [(k, v) for k, v in settings.items() if v.get("group") == g["key"]]
            if not members:
                continue
            print(f"\n[{g['label']}] — {g['desc']}  ({len(members)})")
            for k, v in sorted(members, key=lambda kv: kv[1]["address"]):
                line(k, v)
    else:
        for key, v in settings.items():
            line(key, v)


async def cmd_scan(args):
    from .client import scan
    print(f"Scanning {args.timeout:.0f}s ...")
    devices = await scan(timeout=args.timeout, all_devices=args.all)
    if not devices:
        print("No devices found.")
        return
    for addr, name, rssi in devices:
        print(f"  {addr}  rssi={rssi:>4}  {name!r}")


async def cmd_read(args):
    from .client import AntBmsClient
    async with AntBmsClient(args.address) as bms:
        settings = await bms.read_all_settings()
    if args.json:
        print(json.dumps(settings, ensure_ascii=False, indent=2))
    else:
        print(f"Read {len(settings)} settings from {args.address}:")
        _print_settings(settings)


async def cmd_get(args):
    from .client import AntBmsClient
    async with AntBmsClient(args.address) as bms:
        settings = await bms.read_all_settings()
    if args.key not in settings:
        print(f"Unknown/absent key: {args.key}", file=sys.stderr)
        sys.exit(2)
    _print_settings({args.key: settings[args.key]})


async def cmd_set(args):
    from .client import AntBmsClient
    async with AntBmsClient(args.address) as bms:
        if args.password is not None:
            await bms.unlock(args.password)
        await bms.set_value(args.key, args.value, save=args.save)
    print(f"Set {args.key} = {args.value}" + ("  (saved)" if args.save else ""))


async def cmd_backup(args):
    from .client import AntBmsClient
    async with AntBmsClient(args.address) as bms:
        chunks = await bms.read_all_chunks()
    backup = build_backup(chunks, device={"address": args.address})
    save_backup(args.out, backup)
    print(f"Backed up {len(backup['settings'])} settings to {args.out}")


def _print_verify_report(r):
    def flag(ok):
        return "OK " if ok else "!! "
    print(f"Verification of backup vs device:")
    print(f"  {flag(r['backup_count'] == r['device_count'])}items: "
          f"backup {r['backup_count']} / device {r['device_count']}")
    nm = len(r["name_mismatches"])
    print(f"  {flag(nm == 0)}names: {r['backup_count'] - nm} matched, {nm} mismatched")
    for label, keys in (("only in backup", r["only_in_backup"]),
                        ("missing from backup", r["only_on_device"]),
                        ("unknown to this tool", r["unknown_keys"]),
                        ("edited in file, raw data wins", r["inconsistent_with_chunks"])):
        if keys:
            print(f"  !! {len(keys)} {label}: " + ", ".join(keys[:8])
                  + (" ..." if len(keys) > 8 else ""))
    if r["address_match"] is False:
        print(f"  !! backup is from a DIFFERENT device "
              f"({r['backup_address']}, connected {r['connected_address']})")
    print(f"  values: {len(r['differences'])} will change, {r['identical']} identical")
    for d in r["differences"][:20]:
        unit = f" {d['unit']}" if d["unit"] else ""
        note = "  (live counter)" if d["volatile"] else ""
        print(f"    {d['key']}: {d['device']} -> {d['backup']}{unit}{note}")
    if len(r["differences"]) > 20:
        print(f"    ... and {len(r['differences']) - 20} more")
    print(f"  => backup {'MATCHES' if r['ok'] else 'does NOT match'} this device")


async def cmd_restore(args):
    backup = load_backup(args.infile)
    writes = backup_to_register_writes(backup)
    from .client import AntBmsClient
    async with AntBmsClient(args.address) as bms:
        report = verify_backup(backup, await bms.read_all_settings(), args.address)
        _print_verify_report(report)
        if not report["ok"] and not args.force:
            print("Aborting: backup does not match this device "
                  "(use --force to restore anyway).")
            sys.exit(3)
        if not args.yes:
            answer = input(f"Write {len(writes)} registers"
                           + (" and save to flash" if args.save else "") + "? [y/N] ")
            if answer.strip().lower() not in ("y", "yes"):
                print("Aborted.")
                return
        if args.password is not None:
            await bms.unlock(args.password)
        result = await bms.restore_verified(writes, save=args.save)
    print(f"Wrote {result['written']}/{result['planned']} registers "
          f"from {args.infile}")
    for m in result["volatile_mismatches"]:
        print(f"  note: live counter {m['key']} drifted "
              f"({m.get('wrote_value')} -> {m.get('read_back_value')})")
    if result.get("error") or result["mismatches"]:
        if result.get("error"):
            print(f"ERROR during restore: {result['error']}")
        for m in result["mismatches"]:
            print(f"  read-back mismatch {m['key']} (addr {m['address']}): "
                  f"wrote {m['wrote']}, read back {m['read_back']}")
        if result.get("rollback_ok"):
            print("Rolled back to the previous settings (verified). "
                  "Flash was not modified.")
        else:
            print("ROLLBACK INCOMPLETE"
                  + (f" ({result.get('rollback_error')})"
                     if result.get("rollback_error") else "")
                  + " — power-cycle or restart the BMS to return to the saved "
                    "settings. Flash was not modified.")
        sys.exit(4)
    print("Read-back verified" + ("  (saved to flash)" if result["saved"] else
                                  "  (not saved)"))


async def cmd_save(args):
    from .client import AntBmsClient
    async with AntBmsClient(args.address) as bms:
        if args.password is not None:
            await bms.unlock(args.password)
        await bms.save()
    print("Save-to-flash command sent.")


async def cmd_monitor(args):
    """Live terminal telemetry view (no extra dependencies)."""
    from .client import AntBmsClient

    def bar(v, lo=3.0, hi=3.65, width=18):
        frac = max(0.0, min(1.0, (v - lo) / (hi - lo)))
        n = int(frac * width)
        return "█" * n + "·" * (width - n)

    async with AntBmsClient(args.address) as bms:
        print("Connected. Polling… (Ctrl+C to stop)\n")
        async for t in bms.stream_realtime(args.interval):
            if t is None:
                print("… no reply"); continue
            sys.stdout.write("\x1b[2J\x1b[H")  # clear screen
            flow = "CHG" if t["current"] > 0.05 else "DIS" if t["current"] < -0.05 else "IDLE"
            print(f"ANT BMS  {args.address}")
            print(f"  State {t['state']:<10}  SOC {t['soc']:>3}%  SOH {t['soh']:>3}%   {flow}")
            print(f"  Pack {t['pack_voltage']:>7.2f} V   {t['current']:>8.2f} A   {t['power']:>6} W")
            print(f"  Capacity  remain {t['remaining_capacity_ah']} / {t['physical_capacity_ah']} Ah"
                  f"   cycled {t['cycle_capacity_ah']} Ah   runtime {t['runtime_s']//3600}h")
            print(f"  Cell Δ {t['cell_v_diff']*1000:.0f} mV  max {t['cell_v_max']}V(#{t['cell_v_max_pos']})"
                  f"  min {t['cell_v_min']}V(#{t['cell_v_min_pos']})  avg {t['cell_v_avg']}V")
            print()
            for i, v in enumerate(t["cells"], 1):
                marks = ""
                if i == t["cell_v_max_pos"]: marks += " max"
                if i == t["cell_v_min_pos"]: marks += " min"
                if i in t["balancing_cells"]: marks += " BAL"
                print(f"  Cell {i:>2} {v:.3f}V [{bar(v)}]{marks}")
            temps = "  ".join(f"T{i+1}:{v}°" for i, v in enumerate(t["temperatures"]))
            print(f"\n  Temps {temps}  MOS:{t['temp_mos']}°  Bal:{t['temp_balance']}°")
            print(f"  Charge MOS: {t['charge_mos']:<12}  Discharge MOS: {t['discharge_mos']:<12}  Balance: {t['balance']}")
            if t["protections"]:
                print("  PROTECTIONS: " + ", ".join(t["protections"]))
            if t["warnings"]:
                print("  warnings: " + ", ".join(t["warnings"]))


async def cmd_command(args):
    from .client import AntBmsClient
    async with AntBmsClient(args.address) as bms:
        cmd = await bms.send_command(args.command, password=args.password)
    print(f"Sent command: {cmd.label} (id {cmd.id})")


def cmd_commands(args):
    from . import commands as cmds
    print(f"{len(cmds.COMMANDS)} control commands (use with `command --command <id|key>`):")
    for gkey, glabel in cmds.COMMAND_GROUPS:
        members = [c for c in cmds.COMMANDS if c.group == gkey]
        print(f"\n[{glabel}]")
        for c in members:
            warn = "  ⚠ confirm" if c.confirm else ""
            print(f"  id={c.id:<3} {c.key:<28} {c.label}{warn}")


def cmd_dashboard(args):
    from . import webui
    webui.serve(host=args.host, port=args.port, interval=args.interval,
                address=args.address, password=args.password, demo=args.demo)


def cmd_gui(args):
    from . import gui
    gui.run(interval=args.interval, address=args.address,
            password=args.password, demo=args.demo, fullscreen=args.fullscreen)


def cmd_registers(args):
    from .registers import SETTING_GROUPS, group_for_address
    print(f"{len(REGISTERS)} known settings, grouped by app page:")
    for g in SETTING_GROUPS:
        members = [r for r in REGISTERS if group_for_address(r.address) == g["key"]]
        if not members:
            continue
        print(f"\n[{g['label']}] — {g['desc']}  ·  addr {g['lo']}–{g['hi'] - 1}  ·  {len(members)} settings")
        for r in members:
            unit = f" {r.unit}" if r.unit else ""
            print(f"  addr={r.address:<4} id={r.id:<4} x{r.scale:<8} {r.key:<42} {r.name}{unit}")


def build_parser():
    ap = argparse.ArgumentParser(prog="antbms_tool", description="ANT BMS BLE tool")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="scan for BLE devices")
    s.add_argument("--timeout", type=float, default=6.0)
    s.add_argument("--all", action="store_true", help="show non-ANT devices too")
    s.set_defaults(func=cmd_scan, is_async=True)

    s = sub.add_parser("read", help="read all settings")
    s.add_argument("--address", required=True)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_read, is_async=True)

    s = sub.add_parser("get", help="read one setting")
    s.add_argument("--address", required=True)
    s.add_argument("--key", required=True)
    s.set_defaults(func=cmd_get, is_async=True)

    s = sub.add_parser("set", help="set one setting")
    s.add_argument("--address", required=True)
    s.add_argument("--key", required=True)
    s.add_argument("--value", required=True, type=float)
    s.add_argument("--password", nargs="?", const=p.DEFAULT_PASSWORD, default=None,
                   help="unlock before writing (default 12345678 if flag given with no value)")
    s.add_argument("--save", action="store_true", help="persist to flash after setting")
    s.set_defaults(func=cmd_set, is_async=True)

    s = sub.add_parser("backup", help="back up all settings to a file")
    s.add_argument("--address", required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_backup, is_async=True)

    s = sub.add_parser("restore", help="restore all settings from a file "
                       "(verifies against the device before and after writing)")
    s.add_argument("--address", required=True)
    s.add_argument("--in", dest="infile", required=True)
    s.add_argument("--password", nargs="?", const=p.DEFAULT_PASSWORD, default=None)
    s.add_argument("--save", action="store_true",
                   help="persist to flash after restore (only if read-back verifies)")
    s.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    s.add_argument("--force", action="store_true",
                   help="restore even if the backup does not match the device")
    s.set_defaults(func=cmd_restore, is_async=True)

    s = sub.add_parser("save", help="persist current settings to flash")
    s.add_argument("--address", required=True)
    s.add_argument("--password", nargs="?", const=p.DEFAULT_PASSWORD, default=None)
    s.set_defaults(func=cmd_save, is_async=True)

    s = sub.add_parser("command", help="send a control/action command")
    s.add_argument("--address", required=True)
    s.add_argument("--command", required=True, help="command id or key (see `commands`)")
    s.add_argument("--password", nargs="?", const=p.DEFAULT_PASSWORD, default=None,
                   help="unlock before sending (default 12345678 if flag given)")
    s.set_defaults(func=cmd_command, is_async=True)

    s = sub.add_parser("commands", help="list control commands (offline)")
    s.set_defaults(func=cmd_commands, is_async=False)

    s = sub.add_parser("monitor", help="live telemetry in the terminal")
    s.add_argument("--address", required=True)
    s.add_argument("--interval", type=float, default=1.0)
    s.set_defaults(func=cmd_monitor, is_async=True)

    s = sub.add_parser("dashboard", help="serve the web dashboard UI (scan/connect from the browser)")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--interval", type=float, default=1.0)
    s.add_argument("--address", help="optional: auto-connect to this BMS on startup")
    s.add_argument("--demo", action="store_true", help="optional: auto-start the simulator on startup")
    s.add_argument("--password", nargs="?", const=p.DEFAULT_PASSWORD, default=None,
                   help="optional default unlock password")
    s.set_defaults(func=cmd_dashboard, is_async=False)

    s = sub.add_parser("gui", help="desktop GUI (Tkinter, scan/connect from the window)")
    s.add_argument("--interval", type=float, default=1.0)
    s.add_argument("--address", help="optional: auto-connect to this BMS on startup")
    s.add_argument("--demo", action="store_true", help="optional: auto-start the simulator on startup")
    s.add_argument("--fullscreen", action="store_true", help="kiosk mode (Esc to leave)")
    s.add_argument("--password", nargs="?", const=p.DEFAULT_PASSWORD, default=None,
                   help="optional default unlock password")
    s.set_defaults(func=cmd_gui, is_async=False)

    s = sub.add_parser("registers", help="list known settings (offline)")
    s.set_defaults(func=cmd_registers, is_async=False)

    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    if getattr(args, "is_async", False):
        asyncio.run(args.func(args))
    else:
        args.func(args)


if __name__ == "__main__":
    main()
