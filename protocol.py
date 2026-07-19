"""
ANT BMS BLE wire protocol.

Reverse-engineered from the ANT BMS Android app
(``util/.../bleapi.js`` transport + module ``80d5`` framing helpers
``ReadData`` / ``WriteData`` / ``CheckCrc16``).

Transport
---------
* GATT service        ``0000FFE0-0000-1000-8000-00805F9B34FB``
* write/notify char   ``0000FFE1-0000-1000-8000-00805F9B34FB``
* Frames are written to the characteristic in <=20-byte chunks.
* Replies arrive as notifications and are concatenated until a complete
  frame (valid header + tail) is present.

Frame format (identical for request and reply)
-----------------------------------------------
    offset  field
    0       0x7E            header byte 1
    1       0xA1            header byte 2 (device address)
    2       function code
    3       address low byte
    4       address high byte
    5       length  (number of data bytes that follow)
    6..     data    (``length`` bytes; empty for reads / commands)
    n-4     CRC low byte    (CRC-16/MODBUS, little-endian)
    n-3     CRC high byte
    n-2     0xAA            tail byte 1
    n-1     0x55            tail byte 2

The CRC is computed over the bytes ``frame[1 : 6 + length]`` i.e.
``0xA1, func, addr_lo, addr_hi, length, *data`` (``5 + length`` bytes).

Function codes
--------------
    0x02  read settings/register area
    0x03  request realtime status   (length 0)
    0x04  read identity area
    0x05  read realtime data
    0x07  read (block)
    0x22  write register            (value bytes)
    0x23  write string/password
    0x26  write
    0x51  command: save settings to flash (addr 7, length 0)
    0x53  command
"""

HEADER = (0x7E, 0xA1)
TAIL = (0xAA, 0x55)

# Function codes
FUNC_READ = 0x02
FUNC_READ_STATUS = 0x03
FUNC_READ_ID = 0x04
FUNC_READ_REALTIME = 0x05
FUNC_WRITE_REG = 0x22
FUNC_WRITE_STR = 0x23
FUNC_SAVE = 0x51

# Save-to-flash command target (app: WriteData(7, 0, 0x51, 0))
SAVE_ADDRESS = 7

# Password unlock (app: WriteData(330, 8, 0x23, password[8]))
PASSWORD_ADDRESS = 330
DEFAULT_PASSWORD = "12345678"


def crc16_modbus(data: bytes) -> int:
    """Standard CRC-16/MODBUS (poly 0xA001, init 0xFFFF).

    Verified bit-for-bit against the app's table-based ``CheckCrc16``.
    Returns the 16-bit CRC; transmit low byte first.
    """
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def build_frame(func: int, address: int, length: int, data: bytes = b"") -> bytes:
    """Build a complete protocol frame.

    For reads/commands ``data`` is empty and ``length`` is the number of
    bytes to read. For writes ``length`` must equal ``len(data)``.
    """
    body = bytes(
        [
            HEADER[1],            # 0xA1
            func & 0xFF,
            address & 0xFF,
            (address >> 8) & 0xFF,
            length & 0xFF,
        ]
    ) + bytes(data)
    crc = crc16_modbus(body)
    return (
        bytes([HEADER[0]])        # 0x7E
        + body
        + bytes([crc & 0xFF, (crc >> 8) & 0xFF])
        + bytes(TAIL)
    )


def build_read(address: int, length: int, func: int = FUNC_READ) -> bytes:
    """Frame to read ``length`` bytes starting at ``address``."""
    return build_frame(func, address, length, b"")


def build_write(address: int, data: bytes, func: int = FUNC_WRITE_REG) -> bytes:
    """Frame to write ``data`` at ``address``."""
    return build_frame(func, address, len(data), data)


def build_save() -> bytes:
    """Frame for the 'save settings to flash' command."""
    return build_frame(FUNC_SAVE, SAVE_ADDRESS, 0, b"")


def build_unlock(password: str = DEFAULT_PASSWORD) -> bytes:
    """Frame that writes the access password to unlock writing."""
    raw = password.encode("ascii")[:8]
    raw = raw + b"\x00" * (8 - len(raw))
    return build_write(PASSWORD_ADDRESS, raw, func=FUNC_WRITE_STR)


# Settings replies (func 0x12) append a short auxiliary record between the
# data CRC and the AA 55 tail (observed on hardware: ff 0b 00 00 + own CRC).
# Upper bound on how many such extra bytes we accept before declaring the
# frame corrupt.
MAX_EXTRA = 16


class ParsedFrame:
    __slots__ = ("func", "address", "length", "data", "raw", "extra")

    def __init__(self, func, address, length, data, raw, extra=b""):
        self.func = func
        self.address = address
        self.length = length
        self.data = data
        self.raw = raw
        self.extra = extra

    def __repr__(self):
        return (
            f"ParsedFrame(func=0x{self.func:02X}, address={self.address}, "
            f"length={self.length}, data={self.data.hex()})"
        )


def parse_frame(buf: bytes) -> ParsedFrame:
    """Validate and decode a complete frame. Raises ValueError on failure.

    Tolerates up to ``MAX_EXTRA`` auxiliary bytes between the data CRC and
    the tail (settings replies carry such a record); they are returned in
    ``ParsedFrame.extra``.
    """
    if len(buf) < 10:
        raise ValueError("frame too short")
    if buf[0] != HEADER[0] or buf[1] != HEADER[1]:
        raise ValueError("bad header")
    if buf[-2] != TAIL[0] or buf[-1] != TAIL[1]:
        raise ValueError("bad tail")
    length = buf[5]
    expected = 6 + length + 4
    if not expected <= len(buf) <= expected + MAX_EXTRA:
        raise ValueError(f"length mismatch: got {len(buf)}, expected {expected}")
    crc_pos = 6 + length
    crc_rx = buf[crc_pos] | (buf[crc_pos + 1] << 8)
    crc_calc = crc16_modbus(buf[1:crc_pos])
    if crc_rx != crc_calc:
        raise ValueError(f"CRC mismatch: rx=0x{crc_rx:04X} calc=0x{crc_calc:04X}")
    return ParsedFrame(
        func=buf[2],
        address=buf[3] | (buf[4] << 8),
        length=length,
        data=bytes(buf[6 : 6 + length]),
        raw=bytes(buf),
        extra=bytes(buf[crc_pos + 2 : -2]),
    )


class FrameAssembler:
    """Reassembles frames from streamed BLE notification chunks.

    Mirrors the app logic: accumulate bytes, and once the buffer starts with
    the header and ends with the tail and the length/CRC check passes, emit a
    frame. Tolerant of leading garbage by resyncing on the 0x7E 0xA1 header.
    """

    def __init__(self):
        self._buf = bytearray()

    def feed(self, chunk: bytes):
        """Add received bytes; yield every complete, valid frame found."""
        self._buf.extend(chunk)
        while True:
            frame = self._try_extract()
            if frame is None:
                return
            yield frame

    def reset(self):
        self._buf.clear()

    def _try_extract(self):
        b = self._buf
        # Resync: drop bytes until a header start is at index 0.
        start = b.find(b"\x7e\xa1")
        if start < 0:
            # keep at most 1 trailing byte (could be a partial header)
            if b and b[-1] == 0x7E:
                del b[:-1]
            else:
                b.clear()
            return None
        if start > 0:
            del b[:start]
        if len(b) < 6:
            return None
        length = b[5]
        crc_pos = 6 + length
        if len(b) < crc_pos + 4:          # need at least data + CRC + tail
            return None
        # Validate the CRC at its declared position first: if it is wrong,
        # this header was a false start — resync.
        crc_rx = b[crc_pos] | (b[crc_pos + 1] << 8)
        if crc_rx != crc16_modbus(bytes(b[1:crc_pos])):
            del b[:2]
            return None
        # The tail normally follows the CRC directly, but settings replies
        # insert a short auxiliary record first — scan a bounded window.
        window_end = crc_pos + 2 + MAX_EXTRA + 2
        rel = bytes(b[crc_pos + 2 : min(len(b), window_end)]).find(b"\xaa\x55")
        if rel < 0:
            if len(b) < window_end:
                return None               # tail may still be in flight
            del b[:2]                     # no tail within the window: corrupt
            return None
        total = crc_pos + 2 + rel + 2
        candidate = bytes(b[:total])
        try:
            frame = parse_frame(candidate)
        except ValueError:
            del b[:2]
            return None
        del b[:total]
        return frame
