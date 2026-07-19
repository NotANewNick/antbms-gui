"""
Offline self-test: validates the protocol implementation against the exact
algorithms reverse-engineered from the app (no hardware required).

Run:  python -m antbms_tool.selftest
"""
from . import protocol as p
from .codec import encode_value, decode_value, image_from_chunks, decode_settings
from .registers import REG_BY_KEY, REGISTERS


# --- Reference CRC: the app's exact table-based CheckCrc16 (module 80d5) -----
_RT = [0,193,129,64,1,192,128,65,1,192,128,65,0,193,129,64,1,192,128,65,0,193,129,64,0,193,129,64,1,192,128,65,1,192,128,65,0,193,129,64,0,193,129,64,1,192,128,65,0,193,129,64,1,192,128,65,1,192,128,65,0,193,129,64,1,192,128,65,0,193,129,64,0,193,129,64,1,192,128,65,0,193,129,64,1,192,128,65,1,192,128,65,0,193,129,64,0,193,129,64,1,192,128,65,1,192,128,65,0,193,129,64,1,192,128,65,0,193,129,64,0,193,129,64,1,192,128,65,1,192,128,65,0,193,129,64,0,193,129,64,1,192,128,65,0,193,129,64,1,192,128,65,1,192,128,65,0,193,129,64,0,193,129,64,1,192,128,65,1,192,128,65,0,193,129,64,1,192,128,65,0,193,129,64,0,193,129,64,1,192,128,65,0,193,129,64,1,192,128,65,1,192,128,65,0,193,129,64,1,192,128,65,0,193,129,64,0,193,129,64,1,192,128,65,1,192,128,65,0,193,129,64,0,193,129,64,1,192,128,65,0,193,129,64,1,192,128,65,1,192,128,65,0,193,129,64]
_OT = [0,192,193,1,195,3,2,194,198,6,7,199,5,197,196,4,204,12,13,205,15,207,206,14,10,202,203,11,201,9,8,200,216,24,25,217,27,219,218,26,30,222,223,31,221,29,28,220,20,212,213,21,215,23,22,214,210,18,19,211,17,209,208,16,240,48,49,241,51,243,242,50,54,246,247,55,245,53,52,244,60,252,253,61,255,63,62,254,250,58,59,251,57,249,248,56,40,232,233,41,235,43,42,234,238,46,47,239,45,237,236,44,228,36,37,229,39,231,230,38,34,226,227,35,225,33,32,224,160,96,97,161,99,163,162,98,102,166,167,103,165,101,100,164,108,172,173,109,175,111,110,174,170,106,107,171,105,169,168,104,120,184,185,121,187,123,122,186,190,126,127,191,125,189,188,124,180,116,117,181,119,183,182,118,114,178,179,115,177,113,112,176,80,144,145,81,147,83,82,146,150,86,87,151,85,149,148,84,156,92,93,157,95,159,158,94,90,154,155,91,153,89,88,152,136,72,73,137,75,139,138,74,78,142,143,79,141,77,76,140,68,132,133,69,135,71,70,134,130,66,67,131,65,129,128,64]


def app_crc(buf, start, length):
    s, n, c = 255, 255, 0
    while length:
        length -= 1
        i = s ^ buf[c + start]
        s = _OT[0] if False else (n ^ _RT[i])
        n = _OT[i]
        c += 1
    return (s << 8) | n


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    assert cond, name


def main():
    # 1. CRC matches the app's table CRC for many random inputs
    import random
    for _ in range(5000):
        L = random.randint(1, 40)
        body = bytes(random.randint(0, 255) for _ in range(L + 5))
        app = app_crc(body, 1, L)            # app returns s<<8|n
        mine = p.crc16_modbus(body[1:1 + L])  # standard modbus
        # app stores high byte = app>>8 then low = app&0xff; frame order is
        # [modbus_low, modbus_high]. So app>>8 == modbus_low, app&0xff == modbus_high.
        if not ((app >> 8) == (mine & 0xFF) and (app & 0xFF) == (mine >> 8)):
            check("crc agrees with app", False)
    check("crc16_modbus matches app CheckCrc16", True)

    # 2. Known read frame: ReadData(0, 52, 2)  (app: dianya.vue voltage page)
    rd = p.build_read(0, 52, p.FUNC_READ)
    check("read frame header/tail", rd[:2] == bytes([0x7E, 0xA1]) and rd[-2:] == bytes([0xAA, 0x55]))
    check("read frame fields", rd[2] == 0x02 and rd[3] == 0 and rd[4] == 0 and rd[5] == 52)
    check("read frame length is 10 bytes", len(rd) == 10)

    # 3. Save command: WriteData(7, 0, 0x51, 0)
    sv = p.build_save()
    check("save frame", sv[2] == 0x51 and sv[3] == 7 and sv[5] == 0 and len(sv) == 10)

    # 4. Write register: cell overvoltage protection = 3.65 V (scale 1000 -> 3650)
    reg = REG_BY_KEY["cell_overvoltage_protection"]
    data = encode_value(reg, 3.65)
    check("encode 3.65V -> 3650 LE", data == (3650).to_bytes(2, "little"))
    wf = p.build_write(reg.address, data)
    check("write frame func/addr/len", wf[2] == 0x22 and wf[3] == reg.address and wf[5] == 2)

    # 5. Round-trip a frame through parse_frame
    parsed = p.parse_frame(wf)
    check("parse write frame", parsed.func == 0x22 and parsed.address == reg.address and parsed.data == data)

    # 6. Build a synthetic READ REPLY (func 2, addr 0, 52 bytes) and decode it.
    #    Fill cell OVP=3.60 (3600), recovery=3.40 (3400) at addr 0 and 2.
    payload = bytearray(52)
    payload[0:2] = (3600).to_bytes(2, "little")
    payload[2:4] = (3400).to_bytes(2, "little")
    reply = p.build_frame(p.FUNC_READ, 0, 52, bytes(payload))
    rp = p.parse_frame(reply)
    img = image_from_chunks({0: rp.data})
    decoded = decode_settings(img)
    check("decode OVP=3.6", abs(decoded["cell_overvoltage_protection"]["value"] - 3.6) < 1e-9)
    check("decode OVP recovery=3.4", abs(decoded["cell_overvoltage_recovery"]["value"] - 3.4) < 1e-9)

    # 7. FrameAssembler reassembles a frame split into 20-byte BLE chunks,
    #    with leading garbage to test resync.
    asm = p.FrameAssembler()
    stream = b"\x00\xff" + reply  # garbage prefix
    frames = []
    for i in range(0, len(stream), 20):
        frames.extend(asm.feed(stream[i:i + 20]))
    check("assembler recovers 1 frame", len(frames) == 1 and frames[0].length == 52)

    # 8. encode/decode inverse for several scales
    for key in ("balance_limit_voltage", "charge_overcurrent_protection", "configured_cell_count_series"):
        r = REG_BY_KEY[key]
        v = decode_value(r, 1234 % (1 << 15))
        raw2 = int.from_bytes(encode_value(r, v), "little")
        check(f"roundtrip {key}", abs(decode_value(r, raw2) - v) < 1e-6)

    # 9. Realtime: the poll frame equals the app's hard-coded SendCom, and a
    #    synthesized func-0x11 payload decodes to the expected values.
    from . import realtime as rt
    import struct
    check("realtime poll == app SendCom",
          rt.build_poll() == bytes([126, 161, 1, 0, 0, 190, 24, 85, 170, 85]))

    N, T = 4, 2
    payload = bytearray()
    payload += bytes([1, 2, T, N])                       # perm, state=charging, T, N
    payload += struct.pack("<I", 1 << 13)                # protection: charge overcurrent
    payload += struct.pack("<I", 0)                      # protection word1
    payload += struct.pack("<I", (1 << 18) | (1 << 23))  # warnings: charging + charge MOS on
    payload += struct.pack("<I", 0)                      # warning word1
    payload += bytes(8)                                  # reserved
    for mv in (3300, 3310, 3290, 3305):
        payload += struct.pack("<H", mv)                 # cells
    payload += struct.pack("<h", 250) + struct.pack("<h", -5)   # temps
    payload += struct.pack("<h", 30) + struct.pack("<h", 28)    # MOS, balance temp
    payload += struct.pack("<H", 1320)                   # pack voltage /100 -> 13.20
    payload += struct.pack("<h", 155)                    # current /10 -> 15.5 A
    payload += struct.pack("<H", 87) + struct.pack("<H", 99)    # SOC, SOH
    payload += bytes([1, 1])                             # dis MOS on, ch MOS on
    payload += struct.pack("<H", 4)                      # balance: auto balancing
    payload += struct.pack("<I", 100_000_000)            # physical 100.0 Ah
    payload += struct.pack("<I", 87_000_000)             # remaining 87.0 Ah
    payload += struct.pack("<I", 5_000)                  # cycle 5.0 Ah
    payload += struct.pack("<i", -198)                   # power -198 W
    payload += struct.pack("<I", 3661)                   # runtime 3661 s
    payload += struct.pack("<I", 0b1010)                 # balancing cells 2 & 4
    payload += struct.pack("<H", 3310) + struct.pack("<H", 2)   # vmax, pos
    payload += struct.pack("<H", 3290) + struct.pack("<H", 3)   # vmin, pos
    payload += struct.pack("<H", 20) + struct.pack("<H", 3301)  # diff, avg
    payload += bytes(2 * 5)                              # DS/DIS/CH/NH MOS V + type
    payload += bytes(4 * 4)                              # accumulated dis/ch Ah/time

    frame = p.build_frame(rt.FUNC_REALTIME_REPLY, 0, len(payload), bytes(payload))
    tele = rt.parse_realtime(p.parse_frame(frame).data)
    check("rt cell count", tele["cell_count"] == 4 and len(tele["cells"]) == 4)
    check("rt cell mv->V", tele["cells"][0] == 3.3)
    check("rt pack voltage", tele["pack_voltage"] == 13.2)
    check("rt current signed", tele["current"] == 15.5)
    check("rt power signed", tele["power"] == -198)
    check("rt soc/soh", tele["soc"] == 87 and tele["soh"] == 99)
    check("rt temps signed", tele["temperatures"] == [250, -5])
    check("rt state label", tele["state"] == "charging")
    check("rt protections", "charge overcurrent" in tele["protections"])
    check("rt warnings", "charging" in tele["warnings"] and "charge MOS on" in tele["warnings"])
    check("rt balancing cells", tele["balancing_cells"] == [2, 4])
    check("rt mos labels", tele["charge_mos"] == "on" and tele["discharge_mos"] == "on")
    check("rt balance label", tele["balance"] == "auto balancing")
    check("rt capacities", tele["physical_capacity_ah"] == 100.0 and tele["remaining_capacity_ah"] == 87.0)

    # 10. Control commands: framing matches the app (WriteData(id,0,0x51,0)).
    from . import commands as cmds
    save_via_cmd = cmds.build_command(7)
    check("command(7) == save frame", save_via_cmd == p.build_save())
    chg_on = cmds.build_command(6)
    pf = p.parse_frame(chg_on)
    check("command frame func 0x51", pf.func == 0x51 and pf.address == 6 and pf.length == 0)
    check("resolve by key", cmds.resolve("charge_mos_on").id == 6)
    check("resolve by id", cmds.resolve(9).key == "restart_bms")
    check("dangerous flagged", cmds.CMD_BY_KEY["factory_reset"].confirm and
          not cmds.CMD_BY_KEY["charge_mos_on"].confirm)

    # 11. Captured settings reply (real hardware, 2026-07): func 0x12 replies
    #     carry a 6-byte auxiliary record between the data CRC and the tail.
    captured = bytes.fromhex(
        "7ea1128c000c6810041014000500b4006400fcd6ff0b000041f2aa55")
    pf = p.parse_frame(captured)
    check("captured 0x12 reply parses", pf.func == 0x12 and pf.address == 140
          and pf.length == 12 and pf.extra == bytes.fromhex("ff0b000041f2"))
    asm = p.FrameAssembler()
    frames = []
    for i in range(0, len(captured), 20):
        frames.extend(asm.feed(captured[i:i + 20]))
    check("assembler handles aux record", len(frames) == 1
          and frames[0].data == pf.data)

    # 12. Restore verification: verify_backup + diff_writes_against_image.
    from .backup import (build_backup, verify_backup, backup_to_register_writes,
                         diff_writes_against_image, VOLATILE_KEYS)
    from .registers import SETTINGS_READ_CHUNKS
    import copy
    chunks = {start: bytes((start + i) % 251 for i in range(ln))
              for start, ln in SETTINGS_READ_CHUNKS}
    bk = build_backup(chunks, {"address": "AA:BB"})
    device = decode_settings(image_from_chunks(chunks))
    r = verify_backup(bk, device, "aa:bb")
    check("verify: identical backup is ok", r["ok"] and not r["differences"]
          and r["backup_count"] == r["device_count"] == r["identical"]
          and r["address_match"] is True)

    dev2 = copy.deepcopy(device)
    dev2["cell_overvoltage_protection"]["raw"] += 5     # device value changed
    r = verify_backup(bk, dev2, "CC:DD")
    check("verify: value diff doesn't clear ok", r["ok"] and len(r["differences"]) == 1
          and r["differences"][0]["key"] == "cell_overvoltage_protection"
          and r["address_match"] is False)

    dev3 = copy.deepcopy(device)
    dev3["cell_overvoltage_protection"]["name"] = "Something else"
    check("verify: name mismatch clears ok",
          not verify_backup(bk, dev3)["ok"])
    dev4 = copy.deepcopy(device)
    dev4.pop("cell_overvoltage_protection")
    r = verify_backup(bk, dev4)
    check("verify: item count mismatch clears ok",
          not r["ok"] and r["only_in_backup"] == ["cell_overvoltage_protection"])
    bk2 = copy.deepcopy(bk)
    bk2["settings"]["cell_overvoltage_protection"]["raw"] += 1   # hand-edited file
    r = verify_backup(bk2, device)
    check("verify: chunk/settings inconsistency detected",
          not r["ok"] and r["inconsistent_with_chunks"] == ["cell_overvoltage_protection"])

    writes = backup_to_register_writes(bk)
    image = image_from_chunks(chunks)
    check("readback: clean image has no mismatches",
          diff_writes_against_image(writes, image) == ([], []))
    image2 = dict(image)
    image2[0] ^= 0xFF                                    # first register corrupted
    volatile_addr = REG_BY_KEY["remaining_capacity"].address
    image2[volatile_addr] ^= 0xFF                        # live counter drifted
    bad, vol = diff_writes_against_image(writes, image2)
    check("readback: mismatch found and classified",
          [m["key"] for m in bad] == ["cell_overvoltage_protection"]
          and [m["key"] for m in vol] == ["remaining_capacity"]
          and set(VOLATILE_KEYS) >= {m["key"] for m in vol})

    print(f"\nAll self-tests passed.  {len(REGISTERS)} registers, {len(cmds.COMMANDS)} commands.")


if __name__ == "__main__":
    main()
