"""
Offline client-level simulation tests (no hardware, no bleak connection).

A fake BMS keeps a register image and behaves like the real board: settings
reads are answered with the auxiliary trailer observed on hardware, writes
mutate the image, save-to-flash is recorded. On top of it, this exercises the
paths that matter for safety:

  1. backup while realtime polling runs (request serialization)
  2. restore happy path: write -> read-back verify -> save
  3. stuck register: verification fails, no save, rollback verified
  4. transient BLE write failure: rollback verified, no save
  5. link dies mid-restore: rollback incomplete is reported honestly, no save

Run:  python -m antbms_tool.simtest
"""
import asyncio

from . import protocol as p
from .client import AntBmsClient
from .backup import build_backup, backup_to_register_writes
from .registers import SETTINGS_READ_CHUNKS, REG_BY_KEY

AUX_TRAILER = bytes.fromhex("ff0b000041f2")   # as captured from hardware
DATA_FUNCS = {0x22, 0x23, 0x26}               # request frames carrying payload


def check(name, cond):
    print(("PASS" if cond else "FAIL"), name)
    assert cond, name


class FakeBms:
    """Stands in for BleakClient: parses request frames, answers notifications."""

    def __init__(self, client_ref, image):
        self.client_ref = client_ref
        self.image = image                    # {addr: byte}
        self.buf = bytearray()
        self.saved = False
        self.stuck_addresses = set()          # writes silently ignored
        self.fail_write_no = None             # 1-based 0x22 ordinal that fails
        self.fail_mode = None                 # "once" or "dead"
        self._write_ops = 0

    async def write_gatt_char(self, _char, data, response=False):
        if self.fail_mode == "dead" and self._write_ops >= (self.fail_write_no or 0):
            raise OSError("simulated BLE link death")
        self.buf.extend(bytes(data))
        while len(self.buf) >= 6 and self.buf[0] == 0x7E and self.buf[1] == 0xA1:
            func, length = self.buf[2], self.buf[5]
            dlen = length if func in DATA_FUNCS else 0
            total = 6 + dlen + 4
            if len(self.buf) < total:
                return
            frame = bytes(self.buf[:total])
            del self.buf[:total]
            crc = p.crc16_modbus(frame[1:6 + dlen])
            assert frame[6 + dlen] | (frame[7 + dlen] << 8) == crc, \
                f"corrupt frame at BMS: {frame.hex()}"
            assert frame[-2:] == b"\xaa\x55", "bad tail"
            self._handle(func, frame[3] | (frame[4] << 8), frame[6:6 + dlen], length)

    def _handle(self, func, address, data, length):
        if func == 0x22:
            self._write_ops += 1
            if self.fail_write_no and self._write_ops == self.fail_write_no:
                if self.fail_mode == "once":
                    self.fail_write_no = None
                raise OSError("simulated transient BLE write failure")
            if address not in self.stuck_addresses:
                for i, byte in enumerate(data):
                    self.image[address + i] = byte
        elif func == 0x02:                    # settings read, with trailer
            payload = bytes(self.image.get(address + i, 0) for i in range(length))
            reply = p.build_frame(0x12, address, length, payload)
            self._reply(reply[:-2] + AUX_TRAILER + reply[-2:])
        elif func == 0x01:                    # realtime poll, plain frame
            self._reply(p.build_frame(0x11, 0, 148, bytes(148)))
        elif func == 0x51:
            self.saved = True

    def _reply(self, reply):
        asyncio.get_running_loop().create_task(self._notify(reply))

    async def _notify(self, reply):
        client = self.client_ref[0]
        for i in range(0, len(reply), 20):    # BLE-sized notification chunks
            await asyncio.sleep(0.002)
            client._on_notify(None, bytearray(reply[i:i + 20]))


def make_client(image):
    client = AntBmsClient("00:00:00:00:00:00", timeout=2.0)
    fake = FakeBms([client], image)
    client._client = fake
    return client, fake


def written_region(writes, image):
    """The image restricted to the addresses a write-set touches."""
    return {a + i: image.get(a + i) for a, d in writes for i in range(len(d))}


async def main():
    # A "source" battery to back up; "target" images start out different.
    src = {}
    for start, ln in SETTINGS_READ_CHUNKS:
        for i in range(ln):
            src[start + i] = (start * 3 + i) % 251

    def fresh_target():
        return {a: (b + 7) % 251 for a, b in src.items()}

    client, _ = make_client(dict(src))
    backup = build_backup(await client.read_all_chunks(), {"address": "SRC"})
    writes = backup_to_register_writes(backup)
    check("backup from fake source (131 settings)",
          len(backup["settings"]) == 131 and len(writes) == 131)

    # 1. backup while a realtime poll loop hammers the same client
    client, fake = make_client(dict(src))

    async def poll(n):
        for _ in range(n):
            await client._request(p.build_read(0, 190, func=0x01), match=(0x11, 0))
            await asyncio.sleep(0.01)

    poll_task = asyncio.create_task(poll(10))
    chunks = await asyncio.wait_for(client.read_all_chunks(), 20)
    await poll_task
    check("backup during polling: 6 clean chunks", len(chunks) == 6)

    # 2. happy path
    client, fake = make_client(fresh_target())
    res = await client.restore_verified(writes, save=True)
    check("restore: verified & saved", res["verified"] and res["saved"]
          and fake.saved and not res["mismatches"] and res["error"] is None)
    check("restore: image matches backup",
          written_region(writes, fake.image) == written_region(writes, src))

    # 3. stuck register -> no save, rollback verified
    client, fake = make_client(fresh_target())
    fake.stuck_addresses.add(REG_BY_KEY["cell_overvoltage_protection"].address)
    res = await client.restore_verified(writes, save=True)
    check("stuck reg: mismatch named, not saved",
          not res["verified"] and not res["saved"] and not fake.saved
          and [m["key"] for m in res["mismatches"]] == ["cell_overvoltage_protection"])
    check("stuck reg: rolled back & verified",
          res["rolled_back"] and res["rollback_ok"]
          and written_region(writes, fake.image) == written_region(writes, fresh_target()))

    # 4. transient write failure mid-restore -> rollback verified
    client, fake = make_client(fresh_target())
    fake.fail_write_no, fake.fail_mode = 40, "once"
    res = await client.restore_verified(writes, save=True)
    check("transient failure: error reported, not saved",
          res["error"] is not None and "transient" in res["error"]
          and not res["saved"] and not fake.saved and res["written"] == 39)
    check("transient failure: rolled back & verified",
          res["rolled_back"] and res["rollback_ok"]
          and written_region(writes, fake.image) == written_region(writes, fresh_target()))

    # 5. link dies mid-restore -> rollback impossible, reported honestly
    client, fake = make_client(fresh_target())
    fake.fail_write_no, fake.fail_mode = 40, "dead"
    res = await client.restore_verified(writes, save=True)
    check("dead link: error reported, not saved, rollback incomplete",
          res["error"] is not None and not res["saved"] and not fake.saved
          and res["rollback_ok"] is False and "rollback_error" in res)

    print("\nAll simulation tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
