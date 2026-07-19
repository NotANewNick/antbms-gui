"""
Encode/decode ANT BMS settings between raw register bytes and engineering
values, and assemble a contiguous settings image from read chunks.
"""
from .registers import (
    REGISTERS,
    REG_BY_KEY,
    CAPACITY_HIGH_WORD_ADDRESSES,
    SETTINGS_READ_CHUNKS,
    group_for_address,
)


def _read_le(image: dict, address: int, size: int):
    """Read a little-endian unsigned int of ``size`` bytes from a {addr: byte}
    image. Returns None if any byte is missing."""
    val = 0
    for i in range(size):
        b = image.get(address + i)
        if b is None:
            return None
        val |= b << (8 * i)
    return val


def decode_value(reg, raw: int) -> float:
    """raw register integer -> engineering value."""
    value = raw / reg.scale
    if reg.decimals:
        value = round(value, reg.decimals)
    elif reg.scale == 1:
        value = int(value)
    return value


def encode_value(reg, value: float) -> bytes:
    """engineering value -> little-endian register bytes (reg.size long)."""
    raw = int(round(float(value) * reg.scale))
    if raw < 0:
        raw &= (1 << (8 * reg.size)) - 1
    return raw.to_bytes(reg.size, "little")


def image_from_chunks(chunks: dict) -> dict:
    """Build a {address: byte} image from {start_address: bytes} read results."""
    image = {}
    for start, data in chunks.items():
        for i, byte in enumerate(data):
            image[start + i] = byte
    return image


def decode_settings(image: dict) -> dict:
    """Decode a {address: byte} image into {key: {...}} settings."""
    out = {}
    for reg in REGISTERS:
        if reg.address in CAPACITY_HIGH_WORD_ADDRESSES:
            continue
        raw = _read_le(image, reg.address, reg.size)
        if raw is None:
            continue
        out[reg.key] = {
            "id": reg.id,
            "address": reg.address,
            "name": reg.name,
            "raw": raw,
            "value": decode_value(reg, raw),
            "unit": reg.unit,
            "group": group_for_address(reg.address),
        }
    return out


def settings_to_register_writes(values: dict) -> list:
    """Translate {key: engineering_value} into [(address, bytes), ...] writes.

    Unknown keys are ignored. Used by 'set' and by restore-from-decoded.
    """
    writes = []
    for key, value in values.items():
        reg = REG_BY_KEY.get(key)
        if reg is None:
            continue
        writes.append((reg.address, encode_value(reg, value)))
    return writes
