#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""agent_cli 四命令的护栏（新功能 P1）：stdout 纯 JSON、exit code 语义、
orchestrator 旗标转发。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import agent_cli  # noqa: E402


def _failed_manifest(out_dir: Path, game_dir: Path) -> Path:
    game_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    man = {"ok": False, "error": "extract-failed", "engine": "KiriKiri",
           "source": {"game_dir": str(game_dir),
                      "archives": [{"name": "data.xp3", "entries": None,
                                    "extracted": None}]},
           "stages": [{"stage": "detect", "ok": True, "engine": "KiriKiri",
                       "score": 90, "fired_ids": ["xp3"]}]}
    p = out_dir / "manifest.json"
    p.write_text(json.dumps(man, ensure_ascii=False), encoding="utf-8")
    return p


def test_diagnose_stdout_is_pure_json(tmp_path, capsys):
    mp = _failed_manifest(tmp_path / "out", tmp_path / "game")
    rc = agent_cli.main(["diagnose", str(mp)])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)                 # stdout 必须是合法 JSON
    assert rc == 0 and payload["error_code"] == "extract-failed"


def test_plan_from_diagnostic(tmp_path, capsys):
    mp = _failed_manifest(tmp_path / "out", tmp_path / "game")
    import diagnostics as dg
    diag_file = tmp_path / "diag.json"
    diag_file.write_text(json.dumps(dg.build_from_manifest(mp), ensure_ascii=False),
                         encoding="utf-8")
    rc = agent_cli.main(["plan", "--diagnostic", str(diag_file)])
    plan = json.loads(capsys.readouterr().out)
    assert rc == 0 and plan["candidates"] and plan["allowed_actions"]


def test_run_rejects_plan_outside_whitelist(tmp_path, capsys):
    plan = {"actions": [{"action": "format_c_drive", "params": {}}]}
    pf = tmp_path / "plan.json"
    pf.write_text(json.dumps(plan), encoding="utf-8")
    rc = agent_cli.main(["run", "--plan", str(pf),
                         "--source", str(tmp_path), "--sandbox", str(tmp_path / "sb")])
    report = json.loads(capsys.readouterr().out)
    assert rc == 1 and report["ok"] is False
    assert "沙箱违规" in report["results"][0]["detail"]


def test_run_executes_and_validate_judges(tmp_path, capsys):
    game = tmp_path / "game"
    game.mkdir()
    (game / "data.bin").write_bytes(bytes(range(64)))
    plan = {"actions": [{"action": "hex_inspect",
                         "params": {"path": "data.bin", "length": 8}}]}
    pf = tmp_path / "plan.json"
    pf.write_text(json.dumps(plan), encoding="utf-8")
    rc = agent_cli.main(["run", "--plan", str(pf), "--source", str(game),
                         "--sandbox", str(tmp_path / "sb")])
    report = json.loads(capsys.readouterr().out)
    assert rc == 0 and report["results"][0]["ok"] is True

    # validate：hex_inspect 不产媒体文件 → 空目录按红线判 failed
    rc2 = agent_cli.main(["validate", "--sandbox", str(tmp_path / "sb")])
    verdict = json.loads(capsys.readouterr().out)
    assert rc2 == 1 and verdict["verdict"] == "failed"


def test_orchestrator_forwards_agent_flags(tmp_path):
    mp = _failed_manifest(tmp_path / "out", tmp_path / "game")
    r = subprocess.run(
        [sys.executable, str(ROOT / "orchestrator.py"),
         "--agent-diagnose", str(mp)],
        capture_output=True, text=True, timeout=120, encoding="utf-8",
        errors="replace", cwd=str(ROOT))
    payload = json.loads(r.stdout)
    assert payload["error_code"] == "extract-failed" and r.returncode == 0
