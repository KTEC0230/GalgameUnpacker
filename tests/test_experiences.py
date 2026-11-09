#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""experiences.py 的护栏（新功能 P1）：自带经验库的 schema、动作名合法性、
检索命中正确性（症状 → 应命中的经验）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import experiences as ex  # noqa: E402
import sandbox.actions as sa  # noqa: E402


def test_shipped_library_valid():
    entries, problems = ex.load_all()
    assert not problems, f"自带经验库有问题：{problems}"
    assert len(entries) >= 8, "首批 ≥8 条（新功能.md §5 P1）"
    for e in entries:
        for a in e["actions"]:
            assert a in sa.REGISTRY, f"{e['id']} 引用白名单外动作 {a}"
        assert 0 <= e["confidence"] <= 1


def test_match_krkr_encrypted_case():
    """aniyome 形症状 → krkr-encrypted-xp3 应排第一。"""
    diag = {
        "error_code": "extract-failed",
        "gui_error": "RuntimeError: KrkrExtract 窗口 40s 内未出现，"
                     "静态 index 兜底也不适用：compressed or unsupported XP3 entry",
        "attempted": [{"detail": "GARbro 列不出条目（地面真相缺失）"}],
        "game": {"dir_features": ["xp3-archives", "installer-layout"]},
        "engine": {"name": "KiriKiri"},
        "inputs": [{"name": "data.xp3", "magic_hex": "5850330d0a201a"}],
    }
    got = ex.match(diag)
    assert got, "一条都不命中 = 检索器坏了"
    assert got[0]["id"] == "krkr-encrypted-xp3"
    assert got[0]["matched"], "候选必须带命中原因（只报告不决策的报告要有依据）"


def test_match_engine_filter():
    """明确写了他引擎的条目不投给这个案子。"""
    diag = {"error_code": "extract-failed", "engine": {"name": "Unity"},
            "game": {}, "inputs": []}
    got = ex.match(diag)
    assert all(c["id"] not in ("krkr-encrypted-xp3",) for c in got)


def test_match_returns_empty_not_error_on_silent_diagnostic():
    got = ex.match({"error_code": "detect-failed", "engine": {"name": None},
                    "game": {}, "inputs": []})
    # detect-failed → detect-game-root-nested 命中；没有该条目时空列表也不报错
    assert isinstance(got, list)


def test_missing_dir_tolerated(tmp_path):
    entries, problems = ex.load_all(tmp_path / "nope")
    assert entries == [] and problems


def test_bad_entry_reported_not_fatal(tmp_path):
    import json
    d = tmp_path / "lib"
    d.mkdir()
    (d / "bad.json").write_text(json.dumps({"id": "bad"}), encoding="utf-8")
    (d / "good.json").write_text(json.dumps(
        {"id": "good", "symptoms": {}, "hypothesis": "h", "actions": [],
         "confidence": 0.5, "source": "s", "applies_to": {}}), encoding="utf-8")
    entries, problems = ex.load_all(d)
    assert len(entries) == 1 and entries[0]["id"] == "good"
    assert problems and "bad.json" in problems[0]


def test_plan_shape():
    diag = {"error_code": "extract-failed", "engine": {"name": "KiriKiri"},
            "gui_error": "unknown format",
            "game": {"dir_features": ["xp3-archives"]}, "inputs": []}
    plan = ex.plan(diag)
    assert plan["candidates"] and plan["allowed_actions"]
    assert all(a in sa.REGISTRY for a in plan["allowed_actions"])
