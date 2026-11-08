#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""diagnostics.py 的护栏（新功能 P0，2026-11-09）：

诊断包是 Agent 的第一手材料——「报错原文抄进来」比「给个错误码让它猜」值钱。
这里锁住：schema 关键字段、魔数采集、gui_error 提取、**写包永不抛**（faillog 同纪律）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import diagnostics as dg  # noqa: E402
import errorcodes  # noqa: E402


def ec_expected(code: str) -> list:
    return errorcodes.experience_hints(code)


def _failed_manifest(out_dir: Path, game_dir: Path) -> Path:
    """照真实形状造一份失败 manifest（aniyome 口径：11 包全列不出 → 简化成 1 包）。"""
    game_dir.mkdir(parents=True, exist_ok=True)
    (game_dir / "data.xp3").write_bytes(b"XP3\r\n \x10\x19\x90\x00fake")
    (game_dir / "unins000.exe").write_bytes(b"MZ")
    (out_dir / "_work").mkdir(parents=True, exist_ok=True)
    (out_dir / "_work" / "extract.log").write_text("日志内容", encoding="utf-8")
    man = {
        "ok": False, "error": "extract-failed", "engine": "KiriKiri",
        "source": {
            "game_dir": str(game_dir),
            "archives": [{"name": "data.xp3", "entries": None, "extracted": None}],
            "unsupported": [{"archive": "data.xp3",
                             "reason": "GARbro 列不出条目（地面真相缺失）"}],
        },
        "stages": [
            {"stage": "detect", "ok": True, "engine": "KiriKiri", "score": 90,
             "fired_ids": ["xp3", "xp3_known_names"], "above_threshold": True},
            {"stage": "extract", "ok": False, "detail": "GUI 链路失败",
             "gui_error": "RuntimeError: KrkrExtract 窗口 40s 内未出现"},
        ],
    }
    path = out_dir / "manifest.json"
    path.write_text(json.dumps(man, ensure_ascii=False), encoding="utf-8")
    return path


def test_build_from_manifest_fields(tmp_path):
    mp = _failed_manifest(tmp_path / "out", tmp_path / "game")
    p = dg.build_from_manifest(mp)

    assert p["schema_version"] == dg.SCHEMA_VERSION
    assert p["error_code"] == "extract-failed"
    assert "extract-failed" in p["error_description"]        # describe() 展开
    assert p["engine"]["name"] == "KiriKiri"
    assert p["engine"]["score"] == 90
    assert "xp3" in p["engine"]["fired_signals"]             # detect 平铺字段取到
    assert p["gui_error"] == "RuntimeError: KrkrExtract 窗口 40s 内未出现"


def test_inputs_magic_and_features(tmp_path):
    mp = _failed_manifest(tmp_path / "out", tmp_path / "game")
    p = dg.build_from_manifest(mp)

    inp = p["inputs"][0]
    assert inp["name"] == "data.xp3"
    assert inp["magic_hex"].startswith("5850 33".replace(" ", "")), "XP3 魔数要采到"
    assert inp["listable"] is False
    assert "GARbro 列不出" in inp["reason"]
    assert "installer-layout" in p["game"]["dir_features"]   # unins000.exe → 特征
    assert p["logs"]["extract"].endswith("extract.log")


def test_write_package_never_raises(tmp_path):
    """写包目标不可写时返回 None，绝不抛（诊断是善后，不能变成新失败）。"""
    p = dg.build(error_code="detect-failed", engine=None, game_dir=tmp_path)
    blocker = tmp_path / "blocker"
    blocker.write_text("我是一个文件，不是目录", encoding="utf-8")
    assert dg.write_package(p, blocker) is None              # mkdir 会撞这个文件

    ok = dg.write_package(p, tmp_path / "real")
    assert ok is not None and ok.is_file()
    again = json.loads(ok.read_text(encoding="utf-8"))
    assert again["error_code"] == "detect-failed"


def test_contract_embedded(tmp_path):
    p = dg.build(error_code="extract-failed", game_dir=tmp_path)
    contract = (p.get("agent") or {}).get("contract") or {}
    assert len(contract.get("actions") or {}) >= 11
    assert "sandbox_only" in contract.get("constraints", {})
    # 白名单动作名抽查（契约是 Agent 的行为说明书，动作名是它的 API）
    for name in ("garbro_list", "assetstudio_export", "ffprobe_check",
                 "copy_to_sandbox", "csc_build"):
        assert name in contract["actions"]


def test_experience_candidates_schema_slot(tmp_path):
    """P0 只占位：列表存在且为空；experience_hints 来自错误码表。"""
    p = dg.build(error_code="extract-failed", game_dir=tmp_path)
    assert p["experience_candidates"] == []
    assert isinstance(p["experience_hints"], list) and p["experience_hints"]
    assert p["experience_hints"] == ec_expected("extract-failed")


def test_graceful_on_missing_pieces(tmp_path):
    """空 manifest / 没有游戏目录 → 各块降级为空，绝不抛。"""
    out = tmp_path / "out"
    out.mkdir()
    (out / "manifest.json").write_text(json.dumps({"ok": False, "error": "detect-failed"}),
                                       encoding="utf-8")
    p = dg.build_from_manifest(out)
    assert p["error_code"] == "detect-failed"
    assert p["inputs"] == [] and p["game"]["top_files"] == []
