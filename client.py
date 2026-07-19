"""
Async BLE client for ANT BMS boards (built on bleak).

Implements: scan, connect, read-all-settings, write/set, save-to-flash,
backup and restore.
"""
import asyncio

from bleak import BleakClient, BleakScanner

from . import protocol as p
from . import realtime as rt
from . import commands as cmds
from .backup import diff_writes_against_image
from .registers import SETTINGS_READ_CHUNKS, REG_BY_KEY
from .codec import (
    image_from_chunks,
    decode_settings,
    encode_value,
)

SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
NAME_PREFIXES = ("ANT", "ant")

WRITE_CHUNK = 20            # app writes the characteristic in 20-byte pieces
DEFAULT_TIMEOUT = 4.0


def is_ant_device(name: str) -> bool:
    return bool(name) and any(pfx in name for pfx in NAME_PREFIXES)


async def scan(timeout: float = 6.0, all_devices: bool = False):
    """Scan for BLE devices. Returns a list of (address, name, rssi).

    By default only ANT-named devices are returned.
    """
    found = {}

    def cb(device, adv):
        if device.address in found:
            return
        name = adv.local_name or device.name or ""
        if all_devices or is_ant_device(name):
            found[device.address] = (device.address, name, adv.rssi)

    scanner = BleakScanner(detection_callback=cb)
    await scanner.start()
    await asyncio.sleep(timeout)
    await scanner.stop()
    return sorted(found.values(), key=lambda x: x[2] or -999, reverse=True)


class AntBmsClient:
    """Connected session with a single ANT BMS."""

    def __init__(self, address: str, timeout: float = DEFAULT_TIMEOUT):
        self.address = address
        self.timeout = timeout
        self._client = BleakClient(address)
        self._assembler = p.FrameAssembler()
        self._waiter = None          # asyncio.Future for the next reply
        self._match = None           # (func, address) we are waiting for
        # One frame exchange at a time: the realtime stream and user actions
        # (settings read, backup, writes) share the characteristic, and
        # interleaved sends corrupt frames / clobber the reply waiter.
        self._lock = asyncio.Lock()

    # -- connection ---------------------------------------------------------
    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *exc):
        await self.disconnect()

    async def connect(self):
        await self._client.connect()
        await self._client.start_notify(CHAR_UUID, self._on_notify)

    async def disconnect(self):
        try:
            await self._client.stop_notify(CHAR_UUID)
        except Exception:
            pass
        await self._client.disconnect()

    # -- notification handling ---------------------------------------------
    def _on_notify(self, _char, data: bytearray):
        for frame in self._assembler.feed(bytes(data)):
            if self._waiter and not self._waiter.done():
                want = self._match
                if want is None or (frame.func == want[0] and frame.address == want[1]):
                    self._waiter.set_result(frame)

    async def _send(self, frame: bytes):
        for i in range(0, len(frame), WRITE_CHUNK):
            await self._client.write_gatt_char(
                CHAR_UUID, frame[i : i + WRITE_CHUNK], response=False
            )
            await asyncio.sleep(0.02)

    async def _request(self, frame: bytes, match=None):
        """Send a frame and await the matching reply frame."""
        async with self._lock:
            loop = asyncio.get_running_loop()
            self._waiter = loop.create_future()
            self._match = match
            self._assembler.reset()
            await self._send(frame)
            try:
                return await asyncio.wait_for(self._waiter, self.timeout)
            finally:
                self._waiter = None
                self._match = None

    # -- low level read/write ----------------------------------------------
    async def read(self, address: int, length: int, func: int = p.FUNC_READ) -> bytes:
        frame = p.build_read(address, length, func)
        reply_func = func | 0x10  # BMS replies with func + 0x10 (e.g. 0x02 -> 0x12)
        reply = await self._request(frame, match=(reply_func, address))
        return reply.data

    async def write_register(self, address: int, data: bytes):
        """Write raw bytes to a register address (no reply is awaited)."""
        async with self._lock:
            await self._send(p.build_write(address, data))
            await asyncio.sleep(0.06)

    async def unlock(self, password: str = p.DEFAULT_PASSWORD):
        """Send the access password so the BMS accepts writes."""
        async with self._lock:
            await self._send(p.build_unlock(password))
            await asyncio.sleep(0.1)

    async def save(self):
        """Persist current settings to flash (0x51 command)."""
        async with self._lock:
            await self._send(p.build_save())
            await asyncio.sleep(0.2)

    # -- high level settings ------------------------------------------------
    async def read_all_chunks(self) -> dict:
        """Read every settings chunk. Returns {start_address: bytes}."""
        chunks = {}
        for start, length in SETTINGS_READ_CHUNKS:
            data = await self.read(start, length)
            chunks[start] = data
        return chunks

    async def read_all_settings(self) -> dict:
        """Read and decode all settings into {key: {...}}."""
        chunks = await self.read_all_chunks()
        return decode_settings(image_from_chunks(chunks))

    async def set_value(self, key: str, value, save: bool = False):
        """Set one setting by key to an engineering value."""
        reg = REG_BY_KEY.get(key)
        if reg is None:
            raise KeyError(f"unknown setting key: {key}")
        await self.write_register(reg.address, encode_value(reg, value))
        if save:
            await self.save()

    async def set_values(self, values: dict, save: bool = True):
        """Set multiple settings ({key: value}). Saves once at the end."""
        for key, value in values.items():
            await self.set_value(key, value, save=False)
        if save:
            await self.save()

    async def restore_verified(self, writes: list, save: bool = True) -> dict:
        """Write a register set, read everything back, and save to flash only
        if the read-back matches what was written.

        A snapshot of the current settings is taken first; if writing fails
        part-way or the read-back does not verify, the snapshot is written
        back so the running (RAM) config returns to its pre-restore state.
        Flash is never touched on failure, so a BMS power cycle / restart
        also reverts to the last saved settings. Errors after the snapshot
        are reported in the result (``error`` / ``rollback_*``), not raised;
        only the initial snapshot read may raise (nothing written yet).

        Volatile live counters (see ``backup.VOLATILE_KEYS``) are allowed to
        drift without blocking the save.
        """
        image0 = image_from_chunks(await self.read_all_chunks())
        undo = []
        for address, data in writes:
            old = [image0.get(address + i) for i in range(len(data))]
            if None not in old:
                undo.append((address, bytes(old)))
        result = {"planned": len(writes), "written": 0, "verified": False,
                  "saved": False, "mismatches": [], "volatile_mismatches": [],
                  "rolled_back": False, "rollback_ok": None, "error": None}
        try:
            for address, data in writes:
                await self.write_register(address, data)
                result["written"] += 1
            await asyncio.sleep(0.3)      # let the BMS settle before read-back
            image = image_from_chunks(await self.read_all_chunks())
            mismatches, volatile = diff_writes_against_image(writes, image)
            result["mismatches"] = mismatches
            result["volatile_mismatches"] = volatile
            result["verified"] = not mismatches
            if not mismatches:
                if save:
                    await self.save()
                    result["saved"] = True
                return result
        except Exception as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        # Write error or failed verification: revert RAM to the snapshot.
        try:
            for address, old in undo:
                await self.write_register(address, old)
            result["rolled_back"] = True
            await asyncio.sleep(0.3)
            image = image_from_chunks(await self.read_all_chunks())
            back_bad, _ = diff_writes_against_image(undo, image)
            result["rollback_ok"] = not back_bad
        except Exception as exc:
            result["rollback_error"] = f"{type(exc).__name__}: {exc}"
            result["rollback_ok"] = False
        return result

    # -- action / control commands -----------------------------------------
    async def send_command(self, id_or_key, password=None):
        """Send a control command (e.g. 'charge_mos_on', 'restart_bms', 9).

        If ``password`` is given, unlock first (most control commands require
        a permission level).
        """
        cmd = cmds.resolve(id_or_key)
        if password is not None:
            await self.unlock(password)
        async with self._lock:
            await self._send(cmds.build_command(cmd.id))
            await asyncio.sleep(0.1)
        return cmd

    # -- realtime telemetry -------------------------------------------------
    async def read_realtime(self) -> dict:
        """Poll the BMS once and return decoded realtime telemetry."""
        frame = p.build_read(0, rt.REALTIME_READ_LENGTH, func=rt.FUNC_REALTIME_REQUEST)
        reply = await self._request(frame, match=(rt.FUNC_REALTIME_REPLY, 0))
        return rt.parse_realtime(reply.data)

    async def stream_realtime(self, interval: float = 1.0):
        """Async generator yielding decoded telemetry every ``interval`` s."""
        while True:
            try:
                yield await self.read_realtime()
            except asyncio.TimeoutError:
                yield None
            await asyncio.sleep(interval)
