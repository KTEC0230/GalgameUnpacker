#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agent 攻坚 CLI —— 四个命令（`新功能.md` 零件 D，P1）。

    diagnose <游戏目录|失败manifest>   现场或存量失败 → 诊断包（JSON）
    plan     --diagnostic <pkg.json>   诊断包 → 经验候选计划（JSON）
    run      --plan <plan.json> --source DIR --sandbox DIR   计划 → 沙箱执行报告
    validate --sandbox DIR [--expectation e.json]     沙箱产物 → 验证器裁决

口径：stdout **纯 JSON**（Agent 读），人读提示一律 stderr——与 --dry-run 同款。
编排器以旗标形态转发到本模块（单 exe 双模式惯例，冻结打包靠静态 import）。

红线在四个命令之间闭环：Agent 可以自由组合 diagnose/plan 的结论，
但 run 只认白名单动作、validate 只认产物——自述成功不算成功。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_diagnose(args: argparse.Namespace) -> int:
    import diagnostics
    target = Path(args.target)
    package = diagnostics.build_from_manifest(target)
    if args.out:
        written = diagnostics.write_package(package, Path(args.out))
        print(f"[OK] 诊断包写入：{written}", file=sys.stderr)
    _emit(package)
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    import experiences
    diag = json.loads(Path(args.diagnostic).read_text(encoding="utf-8"))
    plan = experiences.plan(diag, dir=args.library)
    _emit(plan)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    import sandbox.actions as sa
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    actions = plan.get("actions") or []
    if not actions:
        print("[ERROR] 计划里没有 actions", file=sys.stderr)
        return 2
    sandbox = sa.Sandbox(args.source, args.sandbox)
    report = {"sandbox": str(sandbox.sandbox_root), "source": str(sandbox.source_dir),
              "results": [], "ok": True}
    for step in actions:
        name = step.get("action")
        params = step.get("params") or {}
        try:
            res = sa.run_action(name, params, sandbox)
        except sa.SandboxViolation as exc:
            res = {"action": name, "ok": False,
                   "detail": f"沙箱违规（硬失败）：{exc}"}
        report["results"].append(res)
        if not res.get("ok"):
            report["ok"] = False
    n_ok = sum(1 for r in report["results"] if r.get("ok"))
    print(f"[i] 动作 {n_ok}/{len(report['results'])} 成功（成败看产物，详见 JSON）",
          file=sys.stderr)
    _emit(report)
    return 0 if report["ok"] else 1


def cmd_validate(args: argparse.Namespace) -> int:
    import sandbox.validator as validator
    expectation = {}
    if args.expectation:
        expectation = json.loads(Path(args.expectation).read_text(encoding="utf-8"))
    verdict = validator.validate(Path(args.sandbox), expectation)
    print(f"[i] 裁决：{verdict['verdict']}（{verdict['total']} 个产物；"
          f"{'；'.join(verdict['reasons'])}）", file=sys.stderr)
    _emit(verdict)
    return 0 if verdict["verdict"] == "ok" else 1


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="agent", description="解包攻坚 Agent CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("diagnose", help="游戏目录或失败 manifest → 诊断包")
    p1.add_argument("target")
    p1.add_argument("--out", default=None, help="同时把包写到该输出目录的 _work/diagnostic/")

    p2 = sub.add_parser("plan", help="诊断包 → 经验候选计划")
    p2.add_argument("--diagnostic", required=True)
    p2.add_argument("--library", default=None, help="经验库目录（默认仓库自带）")

    p3 = sub.add_parser("run", help="计划 → 沙箱执行")
    p3.add_argument("--plan", required=True)
    p3.add_argument("--source", required=True, help="源目录（只读）")
    p3.add_argument("--sandbox", required=True, help="沙箱目录（唯一可写区）")

    p4 = sub.add_parser("validate", help="沙箱产物 → 验证器裁决")
    p4.add_argument("--sandbox", required=True)
    p4.add_argument("--expectation", default=None)

    p1.set_defaults(fn=cmd_diagnose)
    p2.set_defaults(fn=cmd_plan)
    p3.set_defaults(fn=cmd_run)
    p4.set_defaults(fn=cmd_validate)
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    args = build_parser().parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
