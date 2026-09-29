# Hasselblad X2D II 100C USB ADB 启用工具

简体中文 · [English](README.md)

适用于 **Hasselblad X2D II 100C，固件 1.3.16.2** 的中英双语交互式命令行工具。cmd 65 路线和最终 ADB 身份验证已在一台实机上测试。本仓库新增的“保留旧密钥并追加公钥”序列已通过离线测试，但**尚未在未启用 ADB 的相机上重新完整运行**。**其他机型、固件版本尚未验证。**

> **风险与责任：** 此操作可能导致保修失效，也可能造成相机故障或损坏。是否运行由使用者自行决定，后果由使用者自行承担；作者和贡献者按现状提供软件，不对损失或损坏负责。请先备份照片、保持相机电量充足，并仅在本人拥有或获授权维修的相机上使用。

## 准备

- Windows 10/11、Python 3.11 或更新版本、Android Platform Tools（`adb.exe`）。Python 部分不依赖第三方包。
- USB 数据线，以及正常工作的相机 USB RNDIS 网络连接。默认诊断地址是 `192.168.42.2:30303`。
- 电脑上的 ADB **公钥** `%USERPROFILE%\.android\adbkey.pub`。如尚未生成，可先运行 `adb devices`。不要传入或发布私钥 `adbkey`。

## 使用

在本仓库目录打开 PowerShell：

```powershell
# 完全离线预演：不连接相机，也不调用 ADB
py -3.11 -X utf8 .\x2dii_adb_enable.py --lang zh --dry-run

# 只读诊断探测和 shell id 测试
py -3.11 -X utf8 .\x2dii_adb_enable.py check --lang zh

# 交互式向导：可选择语言，写入前需输入 ENABLE
py -3.11 -X utf8 .\x2dii_adb_enable.py --adb-path "C:\path\to\platform-tools\adb.exe"

# 确认 ADB 中的设备确实是这台相机
py -3.11 -X utf8 .\x2dii_adb_enable.py verify --lang zh --adb-path "C:\path\to\platform-tools\adb.exe"
```

如果 `adb` 已加入 `PATH`，可省略 `--adb-path`。公钥不在默认位置时，用 `--adb-pubkey "C:\path\to\adbkey.pub"` 指定。自动化运行可显式传入 `--lang zh --yes` 跳过写入确认，请先审阅屏幕上的操作计划。`--host` 可覆盖相机 IP。

向导会先检查 ADB 中是否已有 `ro.product.device=eagle2_hb722` 的相机，若有则直接退出，不重复写入。否则依次验证只读诊断应答、执行只读 `id` 和型号检查、暂存并校验公钥长度、将公钥追加到相机 `adb_keys`（保留现有密钥）、切换 USB 配置，再等待最多 90 秒确认正确型号的 ADB 设备。**仅仅发送命令不算成功。**

## 实际改动

工具把本机 ADB 公钥写入 `/blackbox/system/adb/misc/adb/adb_keys`，并请求 `sys.usb.config=rndis,mass_storage,bulk,acm,adb`。工具不会刷入固件、改启动分区或修改照片。USB 可能短暂断开并重新枚举。公钥文件可能在重启后继续保留，所以**重启相机不等于彻底撤销授权**。本项目尚未验证完整移除与持久化行为，因此没有提供自动回滚命令。

如果 `check` 不能确认诊断应答、只读 shell 和相机型号，向导会在写入前停止。工具不会自动读取并核对固件版本；使用前请在相机上确认是 1.3.16.2。如果切换 USB 后 ADB 没有出现，请检查 `adb devices`、Windows USB 驱动和 RNDIS 网络；不要把其他 Android 设备误认为相机。

## 致谢与来源

**WeiCheng97** 发布的 [Hasselblad X2d-series 5g-unlock](https://github.com/WeiCheng97/Hasselblad-X2d-series-5g-unlock) 项目公开了原厂诊断通道和帧格式，为本研究提供了基础。本仓库的 ADB 流程与命令行是独立实现；WeiCheng97 并未声称或验证本 ADB 流程。另外感谢 [radium-wang 的 X 系列固件研究](https://github.com/radium-wang/Hasselblad-X-System-CIM-Firmware-Research-Feature-Extensions) 提供背景资料。本仓库不包含厂商固件、密钥、相机备份或设备专属日志。

## 许可证

本仓库的原创代码采用 MIT 许可证，见 [LICENSE](LICENSE)。外部项目各自保留其作者与许可条款。
