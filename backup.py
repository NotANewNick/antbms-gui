"""
Backup / restore of ANT BMS settings.

A backup is a JSON file that stores BOTH:
  * ``chunks`` - the raw settings bytes exactly as read (lossless; covers
    reserved/temperature/unnamed regions too), and
  * ``settings`` - the decoded, human-readable & editable values.

Restore prefers the lossless ``chunks`` and writes every known register from
that image; if ``chunks`` is absent it falls back to ``settings`` values.
"""
import json
from datetime import datetime, timezone

from .registers import REGISTERS, CAPACITY_HIGH_WORD_ADDRESSES, REG_BY_KEY
from .codec import image_from_chunks, decode_settings, encode_value, decode_value

BACKUP_FORMAT = "antbms-settings-backup"
BACKUP_VERSION = 1

# Live counters the BMS maintains itself. Restoring them overwrites the pack's
# current SOC / lifetime bookkeeping, and they may legitimately drift between
# a write and its read-back — so they never block a save-to-flash.
VOLATILE_KEYS = {"remaining_capacity", "total_cycle_capacity"}

REG_BY_ADDRESS = {r.address: r for r in REGISTERS
                  if r.address not in CAPACITY_HIGH_WORD_ADDRESSES}


def build_backup(chunks: dict, device: dict | None = None) -> dict:
    """Create a backup document from raw read chunks ({start: bytes})."""
    image = image_from_chunks(chunks)
    return {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "device": device or {},
        "chunks": {str(addr): bytes(data).hex() for addr, data in chunks.items()},
        "settings": {
            k: {"value": v["value"], "raw": v["raw"], "name": v["name"], "unit": v["unit"]}
            for k, v in decode_settings(image).items()
        },
    }


def save_backup(path: str, backup: dict):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(backup, fh, ensure_ascii=False, indent=2)


def load_backup(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        backup = json.load(fh)
    if backup.get("format") != BACKUP_FORMAT:
        raise ValueError("not an ANT BMS settings backup file")
    return backup


def backup_to_register_writes(backup: dict) -> list:
    """Return [(address, bytes), ...] to restore every known register.

    Uses the lossless raw image when available, else the decoded values.
    """
    writes = []
    chunks = backup.get("chunks")
    if chunks:
        image = {}
        for start, hexdata in chunks.items():
            data = bytes.fromhex(hexdata)
            for i, b in enumerate(data):
                image[int(start) + i] = b
        for reg in REGISTERS:
            if reg.address in CAPACITY_HIGH_WORD_ADDRESSES:
                continue
            raw = 0
            ok = True
            for i in range(reg.size):
                b = image.get(reg.address + i)
                if b is None:
                    ok = False
                    break
                raw |= b << (8 * i)
            if ok:
                writes.append((reg.address, raw.to_bytes(reg.size, "little")))
    else:
        for key, item in backup.get("settings", {}).items():
            reg = REG_BY_KEY.get(key)
            if reg:
                writes.append((reg.address, encode_value(reg, item["value"])))
    return writes


def verify_backup(backup: dict, device_settings: dict,
                  connected_address: str | None = None) -> dict:
    """Pre-flight check: compare a backup document against the settings just
    read from the device it is about to be restored to.

    ``report["ok"]`` means the backup structurally matches the device — same
    number of items, same keys, same register names, and the file's decoded
    values agree with its raw chunks — so a restore writes exactly what the
    file shows. Value ``differences`` are listed but never clear ``ok``:
    changing values is what a restore is for.
    """
    bset = backup.get("settings", {})
    only_in_backup = sorted(k for k in bset if k not in device_settings)
    only_on_device = sorted(k for k in device_settings if k not in bset)
    unknown_keys = sorted(k for k in bset if k not in REG_BY_KEY)

    name_mismatches = []
    differences = []
    identical = 0
    for key, item in bset.items():
        dev = device_settings.get(key)
        if dev is None:
            continue
        if item.get("name") != dev.get("name"):
            name_mismatches.append(
                {"key": key, "backup": item.get("name"), "device": dev.get("name")})
        if item.get("raw") != dev.get("raw"):
            differences.append({
                "key": key,
                "name": dev.get("name"),
                "unit": item.get("unit") or "",
                "device": dev.get("value"),
                "backup": item.get("value"),
                "volatile": key in VOLATILE_KEYS,
            })
        else:
            identical += 1
    differences.sort(key=lambda d: REG_BY_KEY[d["key"]].address
                     if d["key"] in REG_BY_KEY else 1 << 16)

    # Internal consistency: restore prefers the raw chunks, so decoded values
    # that disagree with them (a hand-edited file?) would be silently ignored.
    inconsistent = []
    if backup.get("chunks"):
        image = image_from_chunks(
            {int(s): bytes.fromhex(hx) for s, hx in backup["chunks"].items()})
        decoded = decode_settings(image)
        inconsistent = sorted(
            k for k, item in bset.items()
            if k in decoded and decoded[k]["raw"] != item.get("raw"))

    baddr = (backup.get("device") or {}).get("address")
    report = {
        "backup_count": len(bset),
        "device_count": len(device_settings),
        "only_in_backup": only_in_backup,
        "only_on_device": only_on_device,
        "unknown_keys": unknown_keys,
        "name_mismatches": name_mismatches,
        "identical": identical,
        "differences": differences,
        "inconsistent_with_chunks": inconsistent,
        "has_chunks": bool(backup.get("chunks")),
        "backup_address": baddr,
        "connected_address": connected_address,
        "address_match": (None if not baddr or not connected_address
                         else baddr.upper() == connected_address.upper()),
        "timestamp": backup.get("timestamp"),
    }
    report["ok"] = (
        report["backup_count"] == report["device_count"]
        and not only_in_backup and not only_on_device
        and not unknown_keys and not name_mismatches and not inconsistent
    )
    return report


def diff_writes_against_image(writes: list, image: dict):
    """Compare an intended write-set with the {addr: byte} image read back
    from the device. Returns (mismatches, volatile_mismatches): registers
    whose read-back differs from what was written, the volatile ones (live
    counters) split out so they don't block a save-to-flash.
    """
    mismatches, volatile = [], []
    for address, data in writes:
        got = [image.get(address + i) for i in range(len(data))]
        actual = None if None in got else bytes(got)
        if actual == bytes(data):
            continue
        reg = REG_BY_ADDRESS.get(address)
        entry = {
            "address": address,
            "key": reg.key if reg else f"addr_{address}",
            "name": reg.name if reg else "(unknown register)",
            "wrote": bytes(data).hex(),
            "read_back": actual.hex() if actual is not None else None,
        }
        if reg is not None:
            entry["wrote_value"] = decode_value(reg, int.from_bytes(data, "little"))
            if actual is not None:
                entry["read_back_value"] = decode_value(
                    reg, int.from_bytes(actual, "little"))
        target = volatile if (reg and reg.key in VOLATILE_KEYS) else mismatches
        target.append(entry)
    return mismatches, volatile
