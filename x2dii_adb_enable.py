#!/usr/bin/env python3
"""Interactive, bilingual ADB enable wizard for X2D II 100C firmware 1.3.16.2."""

from __future__ import annotations

import argparse
import base64
import binascii
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

from x2dii_protocol import (CMD_HBLSHELL, CMD_PRODCONFIG, ProtocolError,
                            exchange, probe_frame, shell_frame)

CAMERA_HOST = "192.168.42.2"
PRODUCT = "eagle2_hb722"
ADB_KEYS = "/blackbox/system/adb/misc/adb/adb_keys"
KEY_STAGE = "/blackbox/system/adb/misc/adb/adb_keys.x2dii-stage"
USB_ADB = "rndis,mass_storage,bulk,acm,adb"

MESSAGES = {
    "zh": {
        "title": "Hasselblad X2D II 100C ADB 启用向导（固件 1.3.16.2）",
        "risk": "风险：操作可能使保修失效，也可能造成相机故障或损坏。使用者自行承担全部后果。",
        "scope": "仅在本人拥有或获授权的 X2D II 100C 上使用；先备份照片并保持电量充足。",
        "already": "已发现相机 ADB 在线：{serial}。无需重复写入。",
        "adb_missing": "找不到 adb。请安装 Android Platform Tools，或使用 --adb-path 指定 adb.exe。",
        "key_missing": "找不到 ADB 公钥 {path}。请先运行 adb devices，或用 --adb-pubkey 指定 adbkey.pub。",
        "key_invalid": "ADB 公钥格式无效：{path}。只接受公钥，不接受私钥。",
        "connect": "正在连接相机 USB 诊断通道 {host}:30303…",
        "connection_fail": "无法连接相机。确认 USB RNDIS 网络已连接，并能访问 {host}:30303。",
        "probe_fail": "未收到匹配且 CRC 正确的只读诊断应答，已停止。",
        "probe_ok": "只读诊断应答有效。",
        "shell_fail": "未确认 cmd 65 shell 可用；此固件/状态不适用已验证流程，已停止。",
        "shell_ok": "cmd 65 shell 已通过只读 id 检查。",
        "plan": "将本机 ADB 公钥追加到相机 adb_keys（保留原有密钥），再临时切换 USB 配置以启动 ADB。",
        "no_firmware": "此流程不刷固件、不修改启动分区；USB 重连期间连接可能短暂中断。",
        "confirm": "输入 ENABLE 才继续写入（其他输入取消）：",
        "cancel": "已取消，未执行写入。",
        "needs_tty": "需要交互确认；自动化运行须显式传 --yes。",
        "staging": "正在写入公钥：{current}/{total}",
        "stage_fail": "写入阶段缺少有效应答，已停止；不会切换 USB。",
        "key_fail": "未确认公钥长度，已停止；不会切换 USB。",
        "install_fail": "未确认公钥安装，已停止；不会切换 USB。",
        "switch": "正在切换 USB 配置；诊断连接可能立即断开…",
        "verify": "正在检查 ADB 相机身份（最多 {seconds} 秒）…",
        "success": "成功：ADB 相机 {serial}，ro.product.device={product}。",
        "verify_fail": "未能确认 ADB 相机在线。不要把其他 Android 设备当作相机；检查 USB 枚举、驱动及 adb devices。",
        "dry": "离线预演：不会连接相机，不会调用 ADB，也不会写入任何内容。",
        "check_done": "检查完成；未修改相机。",
        "unexpected": "操作失败：{error}",
    },
    "en": {
        "title": "Hasselblad X2D II 100C ADB wizard (firmware 1.3.16.2)",
        "risk": "Risk: this may void your warranty or cause camera malfunction or damage. You accept all consequences.",
        "scope": "Use only on an X2D II 100C you own or are authorized to service. Back up photos and charge the battery first.",
        "already": "Camera ADB is already online: {serial}. No write is needed.",
        "adb_missing": "adb was not found. Install Android Platform Tools or pass --adb-path.",
        "key_missing": "ADB public key not found: {path}. Run adb devices first or pass --adb-pubkey.",
        "key_invalid": "Invalid ADB public key: {path}. A private key is never accepted.",
        "connect": "Connecting to camera USB diagnostic channel {host}:30303…",
        "connection_fail": "Cannot reach camera. Check USB RNDIS networking and {host}:30303.",
        "probe_fail": "No matching, CRC-valid read-only diagnostic reply. Stopped.",
        "probe_ok": "Read-only diagnostic reply is valid.",
        "shell_fail": "Could not confirm cmd 65 shell access. This firmware/state is outside the tested path. Stopped.",
        "shell_ok": "cmd 65 shell passed the read-only id check.",
        "plan": "The wizard will append this host's ADB public key to camera adb_keys (preserving existing keys), then temporarily switch USB mode to start ADB.",
        "no_firmware": "This workflow does not flash firmware or edit boot partitions. USB may disconnect briefly.",
        "confirm": "Type ENABLE to write (anything else cancels):",
        "cancel": "Cancelled before writing.",
        "needs_tty": "Interactive confirmation is required; automation must explicitly pass --yes.",
        "staging": "Writing public key: {current}/{total}",
        "stage_fail": "No valid reply during key staging. Stopped before changing USB mode.",
        "key_fail": "Public key length was not confirmed. Stopped before changing USB mode.",
        "install_fail": "Public key installation was not confirmed. Stopped before changing USB mode.",
        "switch": "Switching USB mode; the diagnostic connection may drop immediately…",
        "verify": "Checking ADB camera identity (up to {seconds} seconds)…",
        "success": "Success: ADB camera {serial}, ro.product.device={product}.",
        "verify_fail": "Could not confirm camera ADB. Do not mistake another Android device for the camera; check USB enumeration, drivers and adb devices.",
        "dry": "Offline preview: no camera connection, ADB call or write will occur.",
        "check_done": "Check complete; camera was not modified.",
        "unexpected": "Operation failed: {error}",
    },
}


def say(lang: str, key: str, **kwargs: object) -> None:
    print(MESSAGES[lang][key].format(**kwargs), flush=True)


def choose_language(selected: str | None) -> str:
    if selected:
        return selected
    if not sys.stdin.isatty():
        return "en"
    print("Language / 语言: 1 中文  |  2 English")
    return "en" if input("[1/2] > ").strip() == "2" else "zh"


def adb_executable(explicit: str | None) -> str | None:
    if explicit:
        return explicit if Path(explicit).is_file() else None
    return shutil.which("adb")


def adb_camera(adb: str) -> str | None:
    listing = subprocess.run([adb, "devices", "-l"], capture_output=True, text=True,
                             timeout=12, check=False)
    if listing.returncode:
        return None
    for line in listing.stdout.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 2 or fields[1] != "device":
            continue
        serial = fields[0]
        device = subprocess.run([adb, "-s", serial, "shell", "getprop", "ro.product.device"],
                                capture_output=True, text=True, timeout=8, check=False)
        if device.returncode == 0 and PRODUCT in device.stdout.splitlines():
            return serial
    return None


def wait_for_camera(adb: str, seconds: int) -> str | None:
    deadline = time.monotonic() + seconds
    while True:
        serial = adb_camera(adb)
        if serial:
            return serial
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        time.sleep(min(3, remaining))


def read_public_key(path: Path, lang: str) -> str:
    if not path.is_file():
        raise ValueError(MESSAGES[lang]["key_missing"].format(path=path))
    if path.name == "adbkey" or path.suffix != ".pub":
        raise ValueError(MESSAGES[lang]["key_invalid"].format(path=path))
    key = path.read_text(encoding="ascii").strip().replace("=\0 ", "= ")
    try:
        blob = key.split(" ", 1)[0]
        decoded = base64.b64decode(blob, validate=True)
        if len(decoded) < 256 or len(key) > 2048 or not re.fullmatch(r"[ -~]+", key):
            raise ValueError
    except (ValueError, binascii.Error) as exc:
        raise ValueError(MESSAGES[lang]["key_invalid"].format(path=path)) from exc
    return key


def key_commands(key: str) -> list[str]:
    commands = [f"mkdir -p {ADB_KEYS.rsplit('/', 1)[0]}"]
    for pos in range(0, len(key), 140):
        redirect = ">" if pos == 0 else ">>"
        commands.append(f"printf %s {shlex.quote(key[pos:pos + 140])} {redirect} {KEY_STAGE}")
    commands.append(f"printf '\\n' >> {KEY_STAGE}")
    commands.append(f'test "$(wc -c < {KEY_STAGE})" -eq {len(key) + 1} && echo ADB_KEY_STAGED')
    commands.append(f"if test -s {ADB_KEYS}; then printf '\\n' >> {ADB_KEYS}; fi")
    commands.append(f"cat {KEY_STAGE} >> {ADB_KEYS} && echo ADB_KEY_INSTALLED")
    commands.append(f"rm -f {KEY_STAGE}")
    for command in commands:
        shell_frame(command)  # enforce the 232-byte frame payload limit before writing
    return commands


def read_only_check(host: str, lang: str) -> bool:
    say(lang, "connect", host=host)
    try:
        with socket.create_connection((host, 30303), timeout=3):
            pass
    except OSError:
        say(lang, "connection_fail", host=host)
        return False
    replies = exchange(host, probe_frame(), CMD_PRODCONFIG)
    if not any(r.function == 2 and r.field == 13 for r in replies):
        say(lang, "probe_fail")
        return False
    say(lang, "probe_ok")
    replies = exchange(host, shell_frame("id"), CMD_HBLSHELL)
    if not any(re.search(r"\buid=\d+", r.text) for r in replies):
        say(lang, "shell_fail")
        return False
    say(lang, "shell_ok")
    return True


def enable(host: str, key: str, lang: str) -> bool:
    commands = key_commands(key)
    for index, command in enumerate(commands, 1):
        say(lang, "staging", current=index, total=len(commands))
        replies = exchange(host, shell_frame(command), CMD_HBLSHELL)
        if not replies:
            say(lang, "stage_fail")
            return False
        if index == len(commands) - 3 and not any("ADB_KEY_STAGED" in r.text for r in replies):
            say(lang, "key_fail")
            return False
        if index == len(commands) - 1 and not any("ADB_KEY_INSTALLED" in r.text for r in replies):
            say(lang, "install_fail")
            return False
    say(lang, "switch")
    switch = f"setprop sys.usb.config none; sleep 1; setprop sys.usb.config {USB_ADB}"
    try:
        exchange(host, shell_frame(switch), CMD_HBLSHELL)
    except ProtocolError:
        pass  # The USB function may disappear before a reply can arrive.
    return True  # ADB identity verification is the only success criterion.


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", nargs="?", choices=("wizard", "check", "verify"),
                        default="wizard", help="wizard / 只读检查 check / ADB 验证 verify")
    parser.add_argument("--lang", choices=("zh", "en"), help="语言 / language")
    parser.add_argument("--host", default=CAMERA_HOST, help="相机 IP / camera IP (USB default: 192.168.42.2)")
    parser.add_argument("--adb-path", help="adb executable / adb.exe 路径")
    parser.add_argument("--adb-pubkey", help="ADB public key / adbkey.pub 路径")
    parser.add_argument("--yes", action="store_true", help="skip the interactive write confirmation / 跳过写入确认")
    parser.add_argument("--dry-run", action="store_true", help="offline preview / 离线预演")
    args = parser.parse_args(argv)
    lang = choose_language(args.lang)
    say(lang, "title")
    say(lang, "risk")
    say(lang, "scope")
    if args.dry_run:
        say(lang, "dry")
        say(lang, "plan")
        say(lang, "no_firmware")
        return 0
    adb = adb_executable(args.adb_path)
    if args.action == "verify":
        if not adb:
            say(lang, "adb_missing")
            return 1
        serial = wait_for_camera(adb, 1)
        if serial:
            say(lang, "success", serial=serial, product=PRODUCT)
            return 0
        say(lang, "verify_fail")
        return 1
    if args.action == "wizard" and not adb:
        say(lang, "adb_missing")
        return 1
    try:
        if args.action == "wizard":
            serial = adb_camera(adb)
            if serial:
                say(lang, "already", serial=serial)
                return 0
        if not read_only_check(args.host, lang):
            return 1
        if args.action == "check":
            say(lang, "check_done")
            return 0
        key_path = Path(args.adb_pubkey).expanduser() if args.adb_pubkey else Path.home() / ".android" / "adbkey.pub"
        key = read_public_key(key_path, lang)
        say(lang, "plan")
        say(lang, "no_firmware")
        say(lang, "risk")
        if not args.yes:
            if not sys.stdin.isatty():
                say(lang, "needs_tty")
                return 1
            if input(MESSAGES[lang]["confirm"] + " ").strip() != "ENABLE":
                say(lang, "cancel")
                return 1
        if not enable(args.host, key, lang):
            return 1
        say(lang, "verify", seconds=90)
        serial = wait_for_camera(adb, 90)
        if serial:
            say(lang, "success", serial=serial, product=PRODUCT)
            return 0
        say(lang, "verify_fail")
        return 1
    except (ProtocolError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        say(lang, "unexpected", error=exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
