#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sandbox 执行层与验证器的护栏（新功能 P1）。

红线测试：白名单外硬失败、路径围栏、csc 只认自带源码；验证器反例
（假产物/0 字节/错扩展名/数量不符/rc=0 空目录全判 failed）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import sandbox.actions as sa  # noqa: E402
import sandbox.validator as validator  # noqa: E402


# ---------------------------------------------------------------- 围栏

def test_sandbox_rejects_escape():
    sb = sa.Sandbox(Path(r"D:/game"), Path(r"D:/work/sb"))
    with pytest.raises(sa.SandboxViolation):
        sb.resolve_in_sandbox(r"..\..\elsewhere")
    with pytest.raises(sa.SandboxViolation):
        sb.resolve_in_sandbox(r"D:\elsewhere\x")
    assert sb.resolve_in_sandbox("sub/x.png").is_relative_to(sb.sandbox_root)


def test_sandbox_rejects_outside_source():
    sb = sa.Sandbox(Path(r"D:/game"), Path(r"D:/work/sb"))
    with pytest.raises(sa.SandboxViolation):
        sb.check_source(Path(r"D:\other\file.bin"))


def test_whitelist_hard_fail():
    sb = sa.Sandbox(Path(r"D:/game"), Path(r"D:/work/sb"))
    with pytest.raises(sa.SandboxViolation):
        sa.run_action("format_c_drive", {}, sb)
    with pytest.raises(sa.SandboxViolation):
        sa.run_action("garbro_list", {}, sb)          # 缺必填参数


def test_param_schema_enforced():
    sb = sa.Sandbox(Path(r"D:/game"), Path(r"D:/work/sb"))
    with pytest.raises(sa.SandboxViolation):
        sa.run_action("assetstudio_export",
                      {"input": "a", "dest": "b", "type_name": "NotAType"}, sb)
    with pytest.raises(sa.SandboxViolation):
        sa.run_action("csc_build", {"key": "agent_supplied_evil.cs"}, sb)


# ---------------------------------------------------------------- 动作（真产物）

def test_hex_inspect_reads_head(tmp_path):
    game = tmp_path / "game"
    game.mkdir()
    (game / "data.bin").write_bytes(bytes(range(70)))
    sb = sa.Sandbox(game, tmp_path / "sb")
    r = sa.run_action("hex_inspect", {"path": "data.bin", "length": 8}, sb)
    assert r["ok"] and r["hex"] == "0001020304050607"


def test_copy_to_sandbox_and_source_readonly(tmp_path):
    game = tmp_path / "game"
    (game / "sub").mkdir(parents=True)
    (game / "sub" / "a.txt").write_text("hello")
    sb = sa.Sandbox(game, tmp_path / "sb")
    r = sa.run_action("copy_to_sandbox",
                      {"src": str(game / "sub" / "a.txt"), "dest": "copy/a.txt"}, sb)
    assert r["ok"]
    assert (tmp_path / "sb" / "copy" / "a.txt").read_text() == "hello"
    assert (game / "sub" / "a.txt").exists(), "源必须保留（copy 不 move）"


def test_pillow_verify_rejects_fake_png(tmp_path):
    game = tmp_path / "game"
    game.mkdir()
    (game / "fake.png").write_bytes(b"\x89PNG\r\n\x1a\n not really")
    sb = sa.Sandbox(game, tmp_path / "sb")
    r = sa.run_action("pillow_verify", {"path": "fake.png"}, sb)
    assert r["ok"] is False, "假 PNG 必须判失败"


# ---------------------------------------------------------------- 验证器反例

def _expect(count=None, exts=None):
    e = {}
    if count is not None:
        e["count"] = count
    if exts:
        e["exts"] = exts
    return e


def test_validator_ok(tmp_path):
    d = tmp_path / "p"
    d.mkdir()
    from PIL import Image
    for i in range(3):
        Image.new("RGB", (4, 4)).save(d / f"a{i}.png")
    v = validator.validate(d, _expect(count=3, exts=[".png"]))
    assert v["verdict"] == "ok"


def test_validator_empty_dir_is_failed(tmp_path):
    d = tmp_path / "p"
    d.mkdir()
    v = validator.validate(d, _expect(count=5))
    assert v["verdict"] == "failed" and "没有产物" in v["reasons"][0]


def test_validator_zero_byte_files_fail(tmp_path):
    d = tmp_path / "p"
    d.mkdir()
    from PIL import Image
    Image.new("RGB", (4, 4)).save(d / "a.png")
    (d / "b.png").write_bytes(b"")
    v = validator.validate(d, _expect(count=2, exts=[".png"]))
    assert v["verdict"] == "failed" and v["empty_files"] == ["b.png"]


def test_validator_fake_media_fails(tmp_path):
    d = tmp_path / "p"
    d.mkdir()
    (d / "x.wav").write_bytes(b"RIFF-Not-really")
    v = validator.validate(d, _expect(count=1))
    assert v["verdict"] == "failed" and v["broken"]


def test_validator_partial_on_small_shortfall(tmp_path):
    d = tmp_path / "p"
    d.mkdir()
    from PIL import Image
    for i in range(9):
        Image.new("RGB", (4, 4)).save(d / f"a{i}.png")
    v = validator.validate(d, _expect(count=10, exts=[".png"]))
    assert v["verdict"] == "partial"


def test_validator_big_shortfall_fails(tmp_path):
    d = tmp_path / "p"
    d.mkdir()
    from PIL import Image
    Image.new("RGB", (4, 4)).save(d / "a.png")
    v = validator.validate(d, _expect(count=10, exts=[".png"]))
    assert v["verdict"] == "failed"


def test_validator_ext_filter_ignores_strays(tmp_path):
    d = tmp_path / "p"
    d.mkdir()
    from PIL import Image
    Image.new("RGB", (4, 4)).save(d / "a.png")
    (d / "note.txt").write_text("rubbish")
    v = validator.validate(d, _expect(count=1, exts=[".png"]))
    assert v["verdict"] == "ok" and v["total"] == 1
