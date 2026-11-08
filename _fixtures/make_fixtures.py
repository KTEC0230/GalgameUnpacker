#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 dry-run 分派器的测试样本（合成目录结构，非真实游戏）。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

MAGIC_XP3 = b"XP3\r\n \n\x1a\x8bg\x01"


def w(p: Path, data: bytes = b"") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


# 1) Unity + IL2CPP
u = ROOT / "unity_game" / "MyGame_Data"
w(u / "StreamingAssets" / "aa" / "stuff.bundle", b"UnityFS\x00\x00\x00\x06")
w(u / "Managed" / "Assembly-CSharp.dll", b"MZ")
w(u / "il2cpp_data" / "global-metadata.dat", b"\xaf\x1b\xb1\xfa")
w(u / "globalgamemanagers", b"\x00" * 32)
w(ROOT / "unity_game" / "GameAssembly.dll", b"MZ")
w(ROOT / "unity_game" / "MyGame.exe", b"MZ")

# 2) KiriKiri 正常
k = ROOT / "krkr_game"
w(k / "data.xp3", MAGIC_XP3 + b"\x00" * 64)
w(k / "bgimage.xp3", MAGIC_XP3 + b"\x00" * 64)
w(k / "fgimage.xp3", MAGIC_XP3 + b"\x00" * 64)

# 3) KiriKiri 头部被改（应触发警告）
km = ROOT / "krkr_modified"
w(km / "data.xp3", b"\xde\xad\xbe\xef" + b"\x00" * 64)

# 4) Ren'Py
r = ROOT / "renpy_game"
w(r / "archive.rpa", b"RPA-3.0 0000000000000000 deadbeef\n")
w(r / "renpy" / "common" / "00library.rpyc", b"\x00")
w(r / "game" / "script.rpyc", b"\x00")

# 5) Tyrano / Electron
t = ROOT / "tyrano_game"
w(t / "resources" / "app.asar", b"\x04\x00\x00\x00" + b"\x00" * 16)
w(t / "tyrano" / "data" / "system" / "Config.tjs", b"")

# 6) 未知
w(ROOT / "unknown_game" / "mystery.dat", b"\x01\x02\x03\x04" * 32)

# 7) RPG Maker MV（NW.js 壳 + www/）
#    2026-11-08：唯一真实样本 常識改変学園-製品版- 从盘上消失（用户清理），
#    护栏 test_detect_covers_all_implemented_engines 因此红——
#    「宣称支持的引擎必须有样本真判出来」。用可重建的 fixture 顶上，
#    让该护栏不再依赖用户的盘。信号面照 rules/engines.json：
#    rpgmaker_nwjs(70) + rpgmaker_variant(25, MV) + rpgmaker_keyfile(10) = 105。
m = ROOT / "rpgmaker_game"
w(m / "nw.dll", b"MZ")
w(m / "icudtl.dat", b"\x00" * 16)
w(m / "locales" / "en-US.pak", b"\x00")
w(m / "www" / "js" / "rpg_core.js", b"// RPG Maker MV core scripts")
w(m / "www" / "js" / "plugins.js", b"")
w(m / "www" / "data" / "System.json",
  b'{"encryptionKey":"d41d8cd98f00b204e9800998ecf8427e"}')
w(m / "www" / "img" / "animations" / "a.png", b"RPGMV" + b"\x00" * 11)
w(m / "www" / "audio" / "bgm" / "a.ogg", b"RPGMV" + b"\x00" * 11)

# 8) AdvHD（AdvHD.exe + AdvHDLang.dll + .arc 封包）
#    同 7)：唯一真实样本 ラブラブお痴験バイト性活 从盘上消失后顶住引擎覆盖护栏。
#    信号面照 rules/engines.json：advhd_exe(70) + advhd_lang(20) + advhd_arc(15) = 105。
a = ROOT / "advhd_game"
w(a / "AdvHD.exe", b"MZ")
w(a / "AdvHDLang.dll", b"MZ")
for i in range(3):
    w(a / ("data%02d.arc" % i), b"ADVHD ARC" + b"\x00" * 16)

print("fixtures built at", ROOT)
