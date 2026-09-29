"""Regression checks for protocol validation and camera selection safeguards."""

import struct
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import x2dii_adb_enable as cli
from x2dii_protocol import CMD_PRODCONFIG, crc16_xmodem, parse_replies, probe_frame


class ProtocolTests(unittest.TestCase):
    def test_crc_and_padded_reply(self):
        self.assertEqual(crc16_xmodem(b"123456789"), 0x31C3)
        reply = bytearray(probe_frame())
        reply[:5] = b"\x09\x00\x05\x09\xfc"
        reply.extend(b"\0" * (1024 - len(reply)))
        self.assertEqual(parse_replies(bytes(reply), CMD_PRODCONFIG)[0].field, 13)
        reply[5 + 0x18] ^= 1
        self.assertEqual(parse_replies(bytes(reply), CMD_PRODCONFIG), [])

    def test_wrong_cookie_is_rejected(self):
        reply = bytearray(probe_frame())
        reply[:5] = b"\x09\x00\x05\x09\xfc"
        struct.pack_into("<I", reply, 5 + 0x08, 0x1234)
        self.assertEqual(parse_replies(bytes(reply), CMD_PRODCONFIG), [])


class SafetyTests(unittest.TestCase):
    def test_private_key_is_rejected(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "adbkey"
            path.write_text("private", encoding="ascii")
            with self.assertRaises(ValueError):
                cli.read_public_key(path, "en")

    def test_key_commands_preserve_existing_key_file(self):
        commands = cli.key_commands("A" * 709)
        self.assertTrue(all(not re.search(r"(?<!>)> " + re.escape(cli.ADB_KEYS) + r"(?:$|\s)", c)
                            for c in commands))
        self.assertIn("cat " + cli.KEY_STAGE + " >> " + cli.ADB_KEYS, commands[-2])
        self.assertTrue(all(len(command.encode("ascii")) + 1 <= 232 for command in commands))

    def test_existing_camera_skips_all_diagnostic_writes(self):
        with patch.object(cli, "adb_executable", return_value="adb"), \
             patch.object(cli, "adb_camera", return_value="CAMERA"), \
             patch.object(cli, "read_only_check") as check, \
             patch.object(cli, "enable") as enable:
            self.assertEqual(cli.main(["--lang", "en"]), 0)
            check.assert_not_called()
            enable.assert_not_called()

    def test_other_android_device_is_not_camera(self):
        from subprocess import CompletedProcess

        def fake_run(command, **_kwargs):
            if command[1:3] == ["devices", "-l"]:
                return CompletedProcess(command, 0, "List of devices attached\nPHONE device\nCAMERA device\n", "")
            return CompletedProcess(command, 0,
                                    "eagle2_hb722\n" if command[2] == "CAMERA" else "other\n", "")

        with patch.object(cli.subprocess, "run", side_effect=fake_run):
            self.assertEqual(cli.adb_camera("adb"), "CAMERA")


if __name__ == "__main__":
    unittest.main()
