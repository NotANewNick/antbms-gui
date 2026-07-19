"""ANT BMS BLE integration toolkit (reverse-engineered from the ANT BMS app).

The protocol/codec/registers/backup modules work with the standard library
only. ``AntBmsClient`` and ``scan`` additionally require ``bleak`` and are
imported lazily so the offline parts work without it installed.
"""
from . import protocol, codec, backup, registers, realtime, commands

SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

__all__ = [
    "AntBmsClient",
    "scan",
    "SERVICE_UUID",
    "CHAR_UUID",
    "protocol",
    "codec",
    "backup",
    "registers",
    "realtime",
    "commands",
]


def __getattr__(name):
    if name in ("AntBmsClient", "scan"):
        from . import client
        return getattr(client, name)
    raise AttributeError(name)
