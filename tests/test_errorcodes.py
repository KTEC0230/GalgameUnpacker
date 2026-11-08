#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""errorcodes.py 的护栏（新功能 P0，2026-11-09）：

1. 源码扫描护栏：orchestrator.py / gui.py 调用点用到的错误码必须在表里
   （新码进源码不进表 = 测试红，防「表与代码漂移」）。
2. 松正则的历史教训：`_finish_failure` 的错误码存变量再传时（verify 三连），
   允许跨引号爬行的正则会扫出假阳性（实测 "organize"）——参数区禁括号。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import errorcodes as ec  # noqa: E402


def test_source_codes_all_in_table():
    """★护栏★ 源码里引用的每个错误码都在表里。"""
    text = ((ROOT / "orchestrator.py").read_text(encoding="utf-8")
            + (ROOT / "gui.py").read_text(encoding="utf-8"))
    assert ec.missing_from_table(text) == set(), "源码有而表没有的错误码"


def test_table_fields_complete():
    for code, meta in ec.ERROR_CODES.items():
        assert isinstance(meta.get("summary"), str) and meta["summary"], code
        assert "rc" in meta and "stage_hint" in meta, code
        assert isinstance(meta.get("experience_hints"), list), code


def test_describe_known_and_unknown():
    assert "判不出引擎" in ec.describe("detect-failed")
    assert ec.describe("detect-failed").startswith("detect-failed")
    assert ec.describe("no-such-code") == "no-such-code"      # 未知码不抛、原样返回
    assert ec.experience_hints("no-such-code") == []
    assert ec.get("no-such-code") is None


def test_regex_does_not_crawl_out_of_call():
    """历史假阳性回归：变量传参的调用点不许让正则爬到别的引号词上。"""
    src = 'x = _finish_failure(ctx, stages, engine, 1, err, t_all)\n'
    src += 'later = stage_organize("organize")\n'
    assert "organize" not in ec.codes_in_source(src)


def test_as_contract_stable_keys():
    c = ec.as_contract()
    assert set(c) == set(ec.ERROR_CODES)
    row = c["extract-failed"]
    assert set(row) == {"rc", "summary", "stage_hint", "experience_hints"}
