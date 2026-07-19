# antbms_tool

Python toolkit for **ANT BMS** battery management systems over Bluetooth LE —
scan, live telemetry, read & change settings, back up, restore, and save to
flash. Includes a CLI, a Tkinter desktop GUI (great on a Raspberry Pi), a
self-hosted web dashboard, and an async Python library.

The protocol was reverse-engineered from the official ANT BMS Android app;
see [`PROTOCOL.md`](PROTOCOL.md) for the full derivation.

## Features

* **Scan** for nearby ANT BMS boards
* **Live telemetry** — SOC, pack voltage, current, power, per-cell voltages
  with balancing markers, temperatures, MOS & balance state, protections
* **Settings** — read all ~130 settings decoded to engineering units, change
  any of them, persist to flash
* **Backup & restore** — lossless raw-register backups; restore is verified
  before writing (device identity + structure + value diff), read back after
  writing, and automatically rolled back on failure — flash is never touched
  by a failed restore
* **Control commands** — MOS on/off, auto-balance, chemistry presets,
  restart, counters, buzzer, …
* **Demo mode** — full simulated battery, so every UI works with no hardware
* **No dependencies** beyond [bleak](https://github.com/hbldh/bleak)
  (and Tkinter for the GUI)

## Install

```bash
git clone <this repo>        # the folder must be named antbms_tool
pip install -r antbms_tool/requirements.txt   # installs bleak
```

All commands below are run from the directory *containing* the
`antbms_tool` folder. Linux needs BlueZ; macOS and Windows are supported by
bleak directly. For the GUI, Tkinter is included with most Python installs
(`sudo apt install python3-tk` on minimal Debian/Ubuntu/Raspberry Pi images).

## Quick start

```bash
python -m antbms_tool gui          # desktop GUI — press "Demo" to try it
                                   # without hardware, or Scan → Connect
./antbms_tool/run_gui.sh           # same, via a launcher that creates a
                                   # venv + installs bleak on first run
```

## CLI

```bash
# Discover ANT BMS boards (use --all to see every BLE device)
python -m antbms_tool scan

# Read & print every setting
python -m antbms_tool read    --address AA:BB:CC:DD:EE:FF
python -m antbms_tool read    --address AA:BB:CC:DD:EE:FF --json

# Read one setting
python -m antbms_tool get     --address AA:BB:CC:DD:EE:FF --key cell_overvoltage_protection

# Change one setting (unlock with default password, then persist to flash)
python -m antbms_tool set     --address AA:BB:CC:DD:EE:FF \
        --key cell_overvoltage_protection --value 3.65 --password --save

# Back up everything to a file (lossless)
python -m antbms_tool backup  --address AA:BB:CC:DD:EE:FF --out my_bms.json

# Restore everything from a backup and persist (verified; see below)
python -m antbms_tool restore --address AA:BB:CC:DD:EE:FF --in my_bms.json --password --save

# Persist current settings to flash
python -m antbms_tool save    --address AA:BB:CC:DD:EE:FF --password

# Live realtime telemetry in the terminal
python -m antbms_tool monitor --address AA:BB:CC:DD:EE:FF

# Send a control command (list them with `commands`)
python -m antbms_tool command --address AA:BB:CC:DD:EE:FF --command charge_mos_on --password

# Offline reference: list every known setting / control command
python -m antbms_tool registers
python -m antbms_tool commands
```

`--password` with no value uses the app default `12345678`; pass
`--password yourpass` to override. Omit it if the board does not require an
unlock for writes.

### Verified restore

Restore is verified twice. Before writing, the backup is compared against a
fresh read of the device — same item count, same register names, and the
exact value differences are shown for confirmation (`--yes` skips the prompt,
`--force` proceeds despite a structural mismatch, e.g. a backup from a
different model). After writing, every register is read back; save-to-flash
only happens if the read-back matches. If a write fails or verification
mismatches, the previous settings are automatically written back and flash is
left untouched.

## Desktop GUI

`python -m antbms_tool gui` opens a native Tkinter window — no browser or
server, which makes it the practical choice on a Raspberry Pi. Scan → pick a
device → Connect from the top bar, or press **Demo** for a simulated battery.

* **Dashboard** — SOC ring, pack V / current / power / state, per-cell bars
  with balancing markers, temperatures, MOS & balance state, protections
* **Settings** — read all settings, double-click to edit, save-to-flash,
  backup & restore via file dialogs (restore shows the same verification
  report as the CLI and only saves to flash after a clean read-back)
* **Control** — the app's control commands; destructive ones ask to confirm

Options: `--fullscreen` starts in kiosk mode (Esc leaves it);
`--address` / `--demo` / `--password` auto-connect on startup; `--interval`
sets the telemetry poll rate.

### Raspberry Pi kiosk

`run_gui.sh` bootstraps everything on first run (creates `~/.antbms-venv`,
installs bleak — this also sidesteps Raspberry Pi OS Bookworm's blocked
system-wide pip). To boot straight into a fullscreen monitor, create
`~/.config/autostart/antbms.desktop`:

```ini
[Desktop Entry]
Type=Application
Name=ANT BMS
Exec=/home/pi/antbms_tool/run_gui.sh --fullscreen --address AA:BB:CC:DD:EE:FF
Path=/home/pi
```

Note: the BMS accepts a single BLE connection — disconnect the phone app
before scanning.

## Web dashboard

```bash
python -m antbms_tool dashboard
# open http://127.0.0.1:8765, then Scan → Connect (or Demo)
```

Serves a single-page UI (no internet/CDN needed) with the same features as
the GUI. Telemetry is read-only and needs no password; pass `--password` to
enable settings writes from the UI. Use `--host 0.0.0.0` to reach it from
other machines — there is no authentication, so only do that on a trusted
network.

## Library

```python
import asyncio
from antbms_tool import scan, AntBmsClient
from antbms_tool.backup import build_backup, save_backup, load_backup, backup_to_register_writes

async def main():
    for addr, name, rssi in await scan():
        print(addr, name, rssi)

    async with AntBmsClient("AA:BB:CC:DD:EE:FF") as bms:
        # realtime telemetry
        t = await bms.read_realtime()
        print(t["soc"], t["pack_voltage"], t["current"], t["cells"], t["warnings"])
        # or stream it
        async for t in bms.stream_realtime(interval=1.0):
            print(t["soc"], "%", t["power"], "W")
            break

        settings = await bms.read_all_settings()
        print(settings["cell_overvoltage_protection"])   # {'value': 3.6, 'unit': 'V', ...}

        await bms.unlock()                                # default password
        await bms.set_value("cell_overvoltage_protection", 3.65, save=True)

        # backup
        chunks = await bms.read_all_chunks()
        save_backup("my_bms.json", build_backup(chunks, {"address": bms.address}))

        # verified restore (pre-check, read-back, rollback on failure)
        writes = backup_to_register_writes(load_backup("my_bms.json"))
        result = await bms.restore_verified(writes, save=True)
        print(result["written"], "registers written")

asyncio.run(main())
```

## Project layout

| File | Purpose |
| --- | --- |
| `protocol.py` | wire protocol: framing, CRC-16/MODBUS, frame reassembly |
| `registers.py` | every known setting register (address, scale, unit, group) |
| `realtime.py` | realtime telemetry request + payload parser |
| `commands.py` | control/action command table |
| `codec.py` | raw register bytes ⇄ engineering values |
| `client.py` | async BLE client (bleak): read/write/unlock/save/stream |
| `backup.py` | backup file format, restore planning, verification |
| `cli.py` | command-line interface |
| `gui.py` | Tkinter desktop GUI |
| `webui.py`, `web_assets.py` | web dashboard (server + embedded single-page UI) |
| `selftest.py`, `simtest.py` | offline tests (below) |

## Tests (no hardware needed)

```bash
python -m antbms_tool.selftest
python -m antbms_tool.simtest
```

`selftest` checks the CRC against the app's exact algorithm and round-trips
frames, encoding/decoding, and the BLE reassembler. `simtest` runs the client
against a simulated BMS (including the settings-reply trailer real hardware
sends) and exercises backup-while-polling and every restore outcome: verified
save, failed verification, mid-restore write errors, and rollback.

## Safety

This tool can change protection thresholds and switch MOSFETs on a device
that manages a large battery. Wrong values can be dangerous. Always `backup`
before you `set`/`restore`, validate against your own board, and treat the
register map as reverse-engineered documentation, not a manufacturer
guarantee. This project is not affiliated with or endorsed by ANT BMS.
