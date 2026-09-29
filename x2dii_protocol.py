"""Minimal X2D II factory diagnostic protocol used by the ADB wizard.

Frame layout follows the public research credited in the README. This module
only sends a read-only production query and the cmd 65 shell command used by
the tested ADB workflow.
"""

from __future__ import annotations

import socket
import struct
import time
from dataclasses import dataclass

FRAME_SIZE = 257
BODY_SIZE = 252
COOKIE = 0x4842
CMD_PRODCONFIG = 49
CMD_HBLSHELL = 65
FIELD_WIFI_REGION = 13


class ProtocolError(Exception):
    pass


def crc16_xmodem(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _frame(command: int, function: int, payload: bytes) -> bytes:
    if len(payload) > BODY_SIZE - 0x14:
        raise ValueError("diagnostic command exceeds the frame payload")
    body = bytearray(BODY_SIZE)
    struct.pack_into("<III", body, 0, command, function, COOKIE)
    body[0x14:0x14 + len(payload)] = payload
    struct.pack_into("<I", body, 0x0C, crc16_xmodem(body[0x10:]))
    return b"\x05\x00\x09\x05\xfc" + body


def probe_frame() -> bytes:
    return _frame(CMD_PRODCONFIG, 2, struct.pack("<I", FIELD_WIFI_REGION))


def shell_frame(command: str) -> bytes:
    return _frame(CMD_HBLSHELL, 1, command.encode("ascii") + b"\0")


@dataclass(frozen=True)
class Reply:
    command: int
    function: int
    cookie: int
    field: int
    value: int
    text: str


def parse_replies(raw: bytes, expected_command: int) -> list[Reply]:
    # Production msg2dbus replies use zero-padded 1024-byte records. Other
    # versions may return packed 257-byte frames.
    padded = (len(raw) >= 1024 and len(raw) % 1024 == 0 and
              all(not any(raw[pos + FRAME_SIZE:pos + 1024])
                  for pos in range(0, len(raw), 1024)))
    stride = 1024 if padded else FRAME_SIZE
    replies = []
    for pos in range(0, len(raw) - stride + 1, stride):
        frame = raw[pos:pos + FRAME_SIZE]
        if frame[:5] != b"\x09\x00\x05\x09\xfc":
            continue
        body = frame[5:]
        command, function, cookie, sent_crc = struct.unpack_from("<IIII", body)
        if command != expected_command or cookie != COOKIE:
            continue
        if sent_crc != crc16_xmodem(body[0x10:]):
            continue
        field, value = struct.unpack_from("<II", body, 0x14)
        printable = bytes(ch if 32 <= ch < 127 or ch in (10, 13) else 46
                          for ch in body[0x10:])
        replies.append(Reply(command, function, cookie, field, value,
                             printable.decode("ascii").rstrip(". ")))
    return replies


def exchange(host: str, frame: bytes, command: int, timeout: float = 2.0) -> list[Reply]:
    raw = bytearray()
    try:
        with socket.create_connection((host, 30303), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(frame)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    chunk = sock.recv(4096)
                except socket.timeout:
                    break
                except OSError:
                    break  # USB reconfiguration can drop the socket.
                if not chunk:
                    break
                raw.extend(chunk)
    except OSError as exc:
        raise ProtocolError(f"{host}:30303: {exc}") from exc
    return parse_replies(bytes(raw), command)
