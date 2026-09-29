# Hasselblad X2D II 100C ADB Enable

[简体中文](README.zh-CN.md) · English

An interactive, bilingual command-line wizard for enabling USB ADB on a **Hasselblad X2D II 100C running firmware 1.3.16.2**. The cmd 65 route and final ADB identity check were tested on one physical camera. This packaged wizard's revised key-appending sequence has passed offline tests but has **not** been rerun on a fresh camera. Other models and firmware versions are **not verified**.

> **Risk and responsibility:** This operation may void your warranty and may cause camera malfunction or damage. You choose to run it and accept all consequences. The authors and contributors provide the software as-is and are not responsible for any loss or damage. Back up your photos, keep the battery charged, and use it only on a camera you own or are authorized to service. This project is basically an experimental tool I made with Codex. Just because it works on my camera does not mean it will work on yours. If it doesn’t work, something breaks, or you brick your camera—don’t blame me :)

## Requirements

- Windows 10/11, Python 3.11 or newer, and Android Platform Tools (`adb.exe`). Python uses only the standard library.
- A USB data cable and a working USB RNDIS network connection to the camera. The default diagnostic address is `192.168.42.2:30303`.
- Your host ADB **public** key at `%USERPROFILE%\.android\adbkey.pub`. `adb devices` normally creates the key pair if needed. Never pass or publish the private `adbkey` file.

## Run

Open PowerShell in this repository:

```powershell
# Offline preview: makes no camera or ADB connection
py -3.11 -X utf8 .\x2dii_adb_enable.py --lang en --dry-run

# Read-only diagnostic probe and shell id test
py -3.11 -X utf8 .\x2dii_adb_enable.py check --lang en

# Interactive wizard: prompts for language and requires typing ENABLE before writing
py -3.11 -X utf8 .\x2dii_adb_enable.py --adb-path "C:\path\to\platform-tools\adb.exe"

# Verify that the ADB device is actually this camera
py -3.11 -X utf8 .\x2dii_adb_enable.py verify --lang en --adb-path "C:\path\to\platform-tools\adb.exe"
```

If `adb` is on `PATH`, omit `--adb-path`. If the public key is elsewhere, pass `--adb-pubkey "C:\path\to\adbkey.pub"`. For scripted use, `--lang en --yes` skips the write confirmation; do this only after reviewing the displayed plan. `--host` overrides the default camera IP.

The wizard first checks whether an ADB device already identifies as `ro.product.device=eagle2_hb722`. If so, it exits without writing. Otherwise it validates a read-only diagnostic reply, runs read-only `id` and product identity checks, stages and checks the public key, appends it to `adb_keys` while preserving existing keys, switches USB mode to include ADB, and waits up to 90 seconds for an ADB device with the correct product identity. A successful send alone is never reported as success.
<img width="1091" height="694" alt="image" src="https://github.com/user-attachments/assets/6413c721-47da-446f-a54f-c91d27c679b5" />

## What changes

The tool writes the host's public ADB key to `/blackbox/system/adb/misc/adb/adb_keys` and requests `sys.usb.config=rndis,mass_storage,bulk,acm,adb`. It does not flash firmware, edit boot partitions, or modify camera images. USB can temporarily disconnect and re-enumerate. The public key file can remain after a reboot; restarting the camera alone is **not** a complete removal of authorization. Removal and persistence have not been validated by this project, so no automated rollback is provided.

If `check` cannot validate the diagnostic reply, read-only shell, and product identity, the wizard stops before any write. The tool does not read or verify the firmware version automatically; check version 1.3.16.2 on the camera before using it. If ADB does not appear after switching USB, inspect `adb devices`, Windows USB drivers, and the RNDIS network; do not assume that another attached Android device is the camera.

## Credit and provenance

**WeiCheng97** published the [Hasselblad X2d-series 5g-unlock project](https://github.com/WeiCheng97/Hasselblad-X2d-series-5g-unlock), including the public factory diagnostic channel and frame format. That work made this investigation possible. This repository's ADB workflow and CLI are a separate implementation; WeiCheng97 did not claim or verify this ADB procedure. Thanks also to [radium-wang's X-system firmware research](https://github.com/radium-wang/Hasselblad-X-System-CIM-Firmware-Research-Feature-Extensions) for background context. No vendor firmware, keys, camera backups, or device-specific logs are included.

## License

The original code in this repository is MIT licensed; see [LICENSE](LICENSE). The linked upstream projects have their own licenses and authors.
