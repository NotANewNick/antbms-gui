# ANT BMS BLE protocol — reverse-engineering notes

This documents how the ANT BMS BLE protocol was recovered from the official
Android app and how the protocol works, step by step, so the result can be
audited and extended.

## 1. Source material

* App package: `ant.bms-B8xC8hUzNxnEMcuVjYt7dA==/base.apk` (ANT BMS, ~58 MB).
* It is a **uni-app (DCloud) hybrid app**: the business logic lives in the
  JavaScript bundle, not the DEX files. Relevant file inside the APK:
  `assets/apps/__UNI__8BF5A80/www/app-service.js` (~1.7 MB, minified).

### How it was opened

1. `unzip -l base.apk` → identified it as uni-app from the `assets/apps/.../www/*.js` layout.
2. Extracted the JS bundles with `unzip`.
3. Beautified `app-service.js` with `js-beautify` (74 k lines) — the minified
   bundle keeps original source paths inside `console.log` strings, e.g.
   `" at util/bleapi.js:605"`, which reveal the original module layout:
   * `util/bleapi.js`    – BLE transport (open/scan/connect/write/notify)
   * `utils/bletools.js` – service/characteristic discovery
   * module `80d5`       – framing helpers `ReadData` / `WriteData` / `CheckCrc16`
   * module `b42a`       – constants + the full `param_list` settings map
   * module `b54d`       – send-queue / chunked write
   * module `24fa`       – UUIDs and connection constants

## 2. Transport layer

From module `24fa` and `bleapi.js`:

| Item                    | Value                                   |
|-------------------------|-----------------------------------------|
| GATT service UUID       | `0000FFE0-0000-1000-8000-00805F9B34FB`  |
| Write characteristic    | `0000FFE1-0000-1000-8000-00805F9B34FB`  |
| Notify characteristic   | `0000FFE1-0000-1000-8000-00805F9B34FB`  |
| Device name filter      | name contains `ANT` / `ant`             |

* Frames are written to `FFE1` in **≤20-byte chunks** (`bleapi.js writeBLE`,
  `sendBlebuff1`), with a short delay between chunks.
* Replies arrive as `FFE1` notifications and are **concatenated** until a full
  frame is present (`quanxian.vue notifylisten`):
  the app checks `s[0]==0x7E && s[1]==0xA1 && s[-2]==0xAA && s[-1]==0x55`.

## 3. Frame format

Recovered from `80d5.ReadData` / `80d5.WriteData`:

```
ReadData(addr, len, func):
    s = [0x7E, 0xA1, func, addr&0xFF, addr>>8, len]
    crc = CheckCrc16(s, 1, 5)            # over s[1..5]
    s += [crc>>8, crc&0xFF, 0xAA, 0x55]

WriteData(addr, len, func, data):       # len == len(data)
    o = [0x7E, 0xA1, func, addr&0xFF, addr>>8, len, *data]
    crc = CheckCrc16(o, 1, 5+len)        # over o[1..5+len]
    o += [crc>>8, crc&0xFF, 0xAA, 0x55]
```

So both directions share one layout:

```
0x7E 0xA1 <func> <addr_lo> <addr_hi> <len> <data...> <crc_lo> <crc_hi> 0xAA 0x55
```

* `addr` is a 16-bit little-endian **byte offset** into the settings memory.
* `len` is the number of `data` bytes (0 for reads/commands).
* CRC covers `0xA1, func, addr_lo, addr_hi, len, *data` (`5 + len` bytes).
* The CRC is stored high-byte-first by the app code (`crc>>8` then `crc&0xFF`),
  but because the app's `CheckCrc16` returns the **byte-swapped** MODBUS value
  (see §4), the bytes on the wire are the normal MODBUS order
  `crc_lo, crc_hi`.

The reply parser (`quanxian.vue`) confirms the same layout and validates
`CheckCrc16(reply, 1, 5 + reply[5]) == (reply[-4]<<8 | reply[-3])`.

### Settings replies carry an auxiliary record (verified on hardware)

Captured traffic (ANT@BLE16ZNUB, 2026-07) shows that **func `0x12`
(settings-read) replies insert 6 extra bytes between the data CRC and the
`AA 55` tail** — a 4-byte record plus its own CRC-16/MODBUS (lo, hi):

```
7E A1 12 <addr> <len> <data…> <crc> FF 0B 00 00 41 F2 AA 55
                                    └─record──┘ └CRC─┘
```

(`0xF241 == crc16(FF 0B 00 00)`; the record was constant across all reads in
the capture — meaning unknown, possibly a status/permission word.) This is why
the app's reply check reads the CRC from `reply[-4:-2]`: that is the *aux*
record's CRC, adjacent to the tail. Identity (`0x14`) and realtime (`0x11`)
replies have **no** such record. `parse_frame` accepts up to `MAX_EXTRA`
trailing bytes and exposes them as `ParsedFrame.extra`.

Realtime note: the reply's `len` field is the actual payload size (148 bytes
observed), not the 190 requested by the poll frame.

## 4. CRC

`80d5` uses a split-table CRC (`r`/`o` high/low tables, init `0xFFFF`). It was
**verified bit-for-bit** against the standard **CRC-16/MODBUS**
(poly `0xA001`, init `0xFFFF`) over 5000 random inputs
(`selftest.py`): the app's `s<<8|n` equals the byte-swapped MODBUS CRC, hence
the on-wire bytes are MODBUS little-endian (`lo, hi`). `protocol.crc16_modbus`
implements the standard algorithm.

## 5. Function codes

| Code  | Meaning                                          | Evidence (app call)                 |
|-------|--------------------------------------------------|-------------------------------------|
| 0x02  | read settings/register area                      | `ReadData(0,52,2)` etc.             |
| 0x03  | request realtime status (len 0)                  | `ReadData(e,0,3)`                   |
| 0x04  | read identity area                               | `ReadData(0,12,4)`                  |
| 0x05  | read realtime data                               | `ReadData(0,40,5)`                  |
| 0x22  | write register value                             | `WriteData(2*id,2,34,intToByteArray(v))` |
| 0x23  | write string / password                          | `WriteData(330,8,35,pwd)`           |
| 0x51  | **save settings to flash** (addr 7, len 0)       | `WriteData(7,0,81,0)` (`saveparam`) |
| 0x53  | command                                          | `WriteData(1,0,83,0)`               |

## 6. Settings map

Module `b42a.param_list` is the full settings table (138 entries). Each entry:

* `id`           — sequential id (write address for a 2-byte reg = `2*id`).
* `startaddress` — byte offset = `2*id`.
* `name`         — Chinese label (translated to English in `registers.py`).
* `iTimes`       — scale: `raw = value * iTimes` (e.g. 1000 for cell V→mV,
  10 for pack V and currents, 1 000 000 for capacities, 1 for counts/seconds).
* `decimal_len`  — display precision.
* `unit`         — `V`, `A`, `AH`(Ah), `MR`(mΩ), `S`(cells), `N`, or none.

Read/write conversion:

```
engineering value = raw / iTimes
raw               = round(value * iTimes)
```

The 138 named settings span byte addresses **0–327**. The app reads them per
settings page; the union of those reads (used here for full read/backup) is:

```
(0,52) (56,44) (104,32) (140,12) (152,142) (298,34)
```

A few capacity fields are **32-bit** (read as two consecutive 16-bit words):
addresses 162/166/170 (physical capacity, remaining capacity, total cycle
capacity); the app writes them with `intTo4ByteArray` / `WriteData(...,4,...)`.
These are modelled with `size=4` and the high words at 164/168/172 are skipped.

## 7. Writing a setting

From `changjia.vue shezhiya` / `dianya.vue`:

1. (If needed) **unlock**: write the 8-char access password to address `330`
   with func `0x23` — `WriteData(330, 8, 0x23, password)`. Default password in
   the app is `12345678`. The device reports a permission level
   (`SysOperationAuth`); writes require level ≥ 1.
2. **Write** the value: `WriteData(2*id, 2, 0x22, intToByteArray(value*iTimes))`.
   (32-bit fields use a 4-byte payload.)
3. **Save** to flash so it survives a power cycle: `WriteData(7, 0, 0x51, 0)`.

The app sets each value with its own write, then re-reads the page to confirm,
and a separate "save" button issues the 0x51 command.

## 8. Realtime telemetry

From the main dashboard `bleIndex.vue` (`Time500`, `SendCom`, `jiexi`) and the
central RX dispatcher `blueshebeidata/index.vue AntProtocol_RxBufFindBmsPort`.

* The app polls every 500 ms with a fixed frame `SendCom`:
  `7E A1 01 00 00 BE 18 55 AA 55` — exactly `ReadData(0, 190, func=0x01)`.
  (Verified: our `build_read(0,190,1)` reproduces those bytes including CRC.)
* The BMS replies with a **function `0x11` (17)** frame. The dispatcher routes
  by reply function code: `0x11`→realtime, `0x12`→params, `0x13`→syslog,
  `0x14`→SocId, `0x15`→info. Note `0x11 == 0x01 | 0x10` (reply = request | 0x10).
* `parse_realtime` (`realtime.py`) decodes the payload; the full field layout,
  scaling and signedness are documented at the top of that module. Cell count
  and temperature-sensor count are read from the payload itself (bytes 3 and 2),
  so any pack size is handled. Currents/power/temperatures are **signed**;
  voltages/capacities are unsigned with fixed scales.
* Status/label tables (system state, charge/discharge MOS state, balance state,
  and the 64-bit protection & warning bitmasks) were taken verbatim from
  `bleIndex.vue` and translated to English in `realtime.py`.

A second hardware variant (`Ver != 0`) uses an alternate big-endian layout
(`jiexi1`, reply framing led by `AA 55`); only the primary `jiexi` (func `0x11`)
format is implemented here, which is what the current app dashboard uses.

## 9. Mapping to this Python package

| Concept                       | Code                                   |
|-------------------------------|----------------------------------------|
| Frame build / parse / CRC     | `protocol.py`                          |
| BLE chunk reassembly          | `protocol.FrameAssembler`              |
| Register table (138 entries)  | `registers.py`                         |
| value ↔ raw bytes             | `codec.py`                             |
| Realtime poll + decode        | `realtime.py`                          |
| Scan/connect/read/write/save  | `client.py` (`AntBmsClient`, `scan`)   |
| Backup / restore JSON         | `backup.py`                            |
| Web dashboard (UI)            | `webui.py` + `web_assets.py`           |
| Desktop GUI (Tkinter)         | `gui.py`                               |
| CLI                           | `cli.py` (`python -m antbms_tool ...`) |
| Offline verification          | `selftest.py`, `simtest.py`            |

## 10. Caveats / unknowns

* Realtime telemetry is implemented via the app's `0x01` poll (§8). The
  alternate read functions seen in the app (`0x03` status, `0x04` identity,
  `0x05` realtime) are documented but not wired to high-level API calls
  (`AntBmsClient.read()` accepts a ``func`` argument if you want to try them).
* All listed params decode as unsigned. Should any prove to be signed
  (`80d5.UnsignToSign` exists for `>32767.5`), add a `signed` flag to the
  register and apply it in `codec.decode_value`.
* The password/permission scheme: only level-1 unlock via the default password
  is wired. Higher levels (`pwd2..pwd5` at addresses 338/346/354/362) follow the
  same `WriteData(addr, len, 0x23, pwd)` pattern.
* Reads (settings 0x02, identity 0x04, realtime 0x01) are verified against
  real hardware (ANT@BLE16ZNUB, 2026-07); see §3 for the settings-reply
  auxiliary record discovered in that capture. The meaning of the record
  (`FF 0B 00 00` in the capture) is still unknown. Verify writes against your
  own hardware before relying on them.
