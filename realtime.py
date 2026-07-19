"""
ANT BMS realtime telemetry.

Reverse-engineered from the app's main dashboard parser
``bleIndex.vue jiexi`` and the periodic poll command ``SendCom``.

Poll
----
The app sends, every 500 ms::

    SendCom = 7E A1 01 00 00 BE <crc> AA 55   ==  ReadData(0, 190, func=1)

The BMS replies with a function ``0x11`` (17) frame whose data payload is
decoded by :func:`parse_realtime`.

Payload layout (little-endian; offsets are within the frame *data*, i.e.
after the 6-byte ``7E A1 11 addr_lo addr_hi len`` header)::

    0      u8    permission level (SysOperationAuth)
    1      u8    system state          -> SYSTEM_STATE
    2      u8    temperature sensor count (T)
    3      u8    cell count (N)
    4..7   u32   protection bitmask  word 0   -> PROTECTION_BITS[0..31]
    8..11  u32   protection bitmask  word 1   -> PROTECTION_BITS[32..63]
    12..15 u32   warning bitmask     word 0   -> WARNING_BITS[0..31]
    16..19 u32   warning bitmask     word 1   -> WARNING_BITS[32..63]
    20..27 8 reserved bytes (skipped by the app)
    28..   N * u16   cell voltages (mV -> V)
           T * s16   temperatures (degC, signed)
           s16   MOS temperature
           s16   balance temperature
           u16   pack voltage   (/100 -> V)
           s16   current        (/10  -> A, signed)
           u16   SOC (%)
           u16   SOH (%)
           u8    discharge MOS state  -> DISCHARGE_MOS_STATE
           u8    charge MOS state     -> CHARGE_MOS_STATE
           u16   balance state        -> BALANCE_STATE
           u32   physical capacity (/1e6 -> Ah)
           u32   remaining capacity (/1e6 -> Ah)
           u32   total cycle capacity (/1e3 -> Ah)
           s32   power (W, signed)
           u32   total runtime (s)
           u32   balance state bitmask (per-cell)
           u16   max cell voltage (/1000 -> V)
           u16   max cell position
           u16   min cell voltage (/1000 -> V)
           u16   min cell position
           u16   cell voltage difference (/1000 -> V)
           u16   average cell voltage (/1000 -> V)
           u16   discharge-detect voltage
           u16   discharge-MOS voltage
           u16   charge-MOS voltage
           u16   NH-MOS voltage
           u16   battery chemistry type
           u32   accumulated discharge Ah
           u32   accumulated charge Ah
           u32   accumulated discharge time (s)
           u32   accumulated charge time (s)
    (optional, when len > 2*T + 2*N + 106)
           u32   estimated next charge time
           u32   charge time interval
           u16   charge time remaining
           u16   discharge time remaining
"""
import struct

from . import protocol as p

# Realtime poll command (== app SendCom). Response arrives as func 0x11.
FUNC_REALTIME_REQUEST = 0x01
FUNC_REALTIME_REPLY = 0x11
REALTIME_READ_LENGTH = 190


def build_poll() -> bytes:
    """The realtime status poll frame (identical to the app's SendCom)."""
    return p.build_read(0, REALTIME_READ_LENGTH, func=FUNC_REALTIME_REQUEST)


# --- label tables (from bleIndex.vue) ---------------------------------------
SYSTEM_STATE = {
    0: "none", 1: "idle", 2: "charging", 3: "standby",
    4: "discharging", 5: "fault",
}

CHARGE_MOS_STATE = [
    "off", "on", "cell overvoltage", "current protection", "battery full",
    "pack overvoltage", "battery over-temp", "MOS over-temp",
    "current abnormal", "balance line loose", "board over-temp", "11",
    "open failed", "discharge tube abnormal", "waiting", "manual off",
    "secondary overvoltage", "low-temp protection", "voltage-diff exceeded",
    "19", "self-test error", "21", "22", "23", "24", "25", "26", "27",
    "28", "29", "30", "31",
]

DISCHARGE_MOS_STATE = [
    "off", "on", "cell low voltage", "current protection",
    "secondary overcurrent", "pack undervoltage", "battery over-temp",
    "MOS over-temp", "current abnormal", "balance line loose",
    "board over-temp", "charge open", "short-circuit protection",
    "discharge tube abnormal", "open failed", "manual off",
    "secondary low voltage", "low-temp protection", "voltage-diff exceeded",
    "self-test error", "20", "21", "22", "23", "24", "25", "26", "27",
    "28", "29", "30", "31",
]

BALANCE_STATE = [
    "off", "limit balancing", "charge voltage-diff balancing",
    "balance over-temp", "auto balancing", "manual balancing",
    "6", "7", "8", "9", "10", "11", "12", "13", "14", "15",
]

# 64-bit protection bitmask labels (word0 = bits 0..31, word1 = bits 32..63)
PROTECTION_BITS = [
    "set cell type", "cell overvoltage", "cell L2 overvoltage",
    "pack overvoltage", "cell undervoltage", "cell L2 undervoltage",
    "pack undervoltage", "cell voltage-diff", "charge over-temp",
    "discharge over-temp", "MOS over-temp", "charge low-temp",
    "discharge low-temp", "charge overcurrent", "discharge overcurrent",
    "discharge L2 overcurrent", "short circuit", "manual off discharge MOS 1",
    "manual off discharge MOS 2", "manual off discharge MOS 3",
    "manual off discharge MOS 4", "manual off charge MOS 1",
    "manual off charge MOS 2", "manual off charge MOS 3",
    "manual off charge MOS 4", "open wire", "current error",
    "discharge MOS error", "charge MOS error", "internal comm error",
    "precharge failure", "starting",
    "self-test 1", "self-test 2", "charger connected", "DTU lost",
    "fire prevention", "check 3", "please upgrade firmware",
    "relay precharge failed", "relay adhesion", "abnormal discharge fuse",
    "abnormal charge fuse", "module loss", "device expiration",
] + [str(i) for i in range(45, 64)]

WARNING_BITS = [
    "cell high", "pack high", "cell low", "pack low", "cell voltage-diff",
    "charge over-temp", "discharge over-temp", "charge low-temp",
    "discharge low-temp", "MOS over-temp", "charge overcurrent",
    "discharge overcurrent", "SOC low L1", "SOC low L2",
    "cell verify error", "cell count error", "precharge failure",
    "battery full", "charging", "discharging", "CAN charger in",
    "RS485 charger in", "charger in", "charge MOS on", "discharge MOS on",
    "balancing on", "sleep", "balance limit", "balance diff",
    "auto balance", "balance over-temp", "cell/pack voltage protect",
    "temperature protect", "system error", "DTU lost", "balance test",
    "electric heating", "forcing output", "bluetooth off",
    "relay precharging", "MOS precharging", "charging relay on",
    "discharge relay on", "XTAL error", "force charging",
] + [str(i) for i in range(45, 64)]


def _bits(mask: int, labels) -> list:
    return [labels[i] for i in range(min(64, len(labels))) if mask & (1 << i)]


class _Cur:
    """Sequential little-endian reader over a bytes payload."""

    def __init__(self, data: bytes):
        self.d = data
        self.i = 0

    def u8(self):
        v = self.d[self.i]
        self.i += 1
        return v

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.i)[0]
        self.i += 2
        return v

    def s16(self):
        v = struct.unpack_from("<h", self.d, self.i)[0]
        self.i += 2
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.i)[0]
        self.i += 4
        return v

    def s32(self):
        v = struct.unpack_from("<i", self.d, self.i)[0]
        self.i += 4
        return v

    def skip(self, n):
        self.i += n

    def remaining(self):
        return len(self.d) - self.i


def parse_realtime(data: bytes) -> dict:
    """Decode a func-0x11 realtime payload (``ParsedFrame.data``)."""
    c = _Cur(data)
    permission = c.u8()
    state_code = c.u8()
    temp_count = c.u8()
    cell_count = c.u8()
    prot0, prot1 = c.u32(), c.u32()
    warn0, warn1 = c.u32(), c.u32()
    c.skip(8)

    cells = [round(c.u16() / 1000.0, 3) for _ in range(cell_count)]
    temps = [c.s16() for _ in range(temp_count)]
    temp_mos = c.s16()
    temp_balance = c.s16()
    pack_voltage = round(c.u16() / 100.0, 2)
    current = round(c.s16() / 10.0, 2)
    soc = c.u16()
    soh = c.u16()
    dis_mos = c.u8()
    ch_mos = c.u8()
    balance = c.u16()
    physical_ah = round(c.u32() / 1e6, 1)
    remaining_ah = round(c.u32() / 1e6, 2)
    cycle_ah = round(c.u32() / 1e3, 3)
    power = c.s32()
    runtime_s = c.u32()
    balance_bits = c.u32()
    v_max = round(c.u16() / 1000.0, 3)
    v_max_pos = c.u16()
    v_min = round(c.u16() / 1000.0, 3)
    v_min_pos = c.u16()
    v_diff = round(c.u16() / 1000.0, 3)
    v_avg = round(c.u16() / 1000.0, 3)

    out = {
        "permission": permission,
        "state_code": state_code,
        "state": SYSTEM_STATE.get(state_code, str(state_code)),
        "cell_count": cell_count,
        "temp_count": temp_count,
        "cells": cells,
        "temperatures": temps,
        "temp_mos": temp_mos,
        "temp_balance": temp_balance,
        "pack_voltage": pack_voltage,
        "current": current,
        "power": power,
        "soc": soc,
        "soh": soh,
        "physical_capacity_ah": physical_ah,
        "remaining_capacity_ah": remaining_ah,
        "cycle_capacity_ah": cycle_ah,
        "runtime_s": runtime_s,
        "cell_v_max": v_max,
        "cell_v_max_pos": v_max_pos,
        "cell_v_min": v_min,
        "cell_v_min_pos": v_min_pos,
        "cell_v_diff": v_diff,
        "cell_v_avg": v_avg,
        "discharge_mos": _label(DISCHARGE_MOS_STATE, dis_mos),
        "charge_mos": _label(CHARGE_MOS_STATE, ch_mos),
        "balance": _label(BALANCE_STATE, balance),
        "discharge_mos_code": dis_mos,
        "charge_mos_code": ch_mos,
        "balance_code": balance,
        "balancing_cells": [i + 1 for i in range(cell_count) if balance_bits & (1 << i)],
        "protection_mask": prot0 | (prot1 << 32),
        "warning_mask": warn0 | (warn1 << 32),
        "protections": _bits(prot0 | (prot1 << 32), PROTECTION_BITS),
        "warnings": _bits(warn0 | (warn1 << 32), WARNING_BITS),
    }

    # optional trailing block
    try:
        if c.remaining() >= 12:
            out["next_charge_time_s"] = c.u32()
            out["charge_time_interval_s"] = c.u32()
            out["charge_time_remaining_min"] = c.u16()
            out["discharge_time_remaining_min"] = c.u16()
    except (IndexError, struct.error):
        pass
    return out


def _label(table, idx):
    return table[idx] if 0 <= idx < len(table) else str(idx)
