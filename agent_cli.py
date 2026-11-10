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

import diagnostics          # noqa: E402  （顶部 import：PyInstaller 打包清单依据，§19.2）
import experiences
import sandbox.actions
import sandbox.validator


def _emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_diagnose(args: argparse.Namespace) -> int:
    target = Path(args.target)
    package = diagnostics.build_from_manifest(target)
    if args.out:
        written = diagnostics.write_package(package, Path(args.out))
        print(f"[OK] 诊断包写入：{written}", file=sys.stderr)
    _emit(package)
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    diag = json.loads(Path(args.diagnostic).read_text(encoding="utf-8"))
    plan = experiences.plan(diag, dir=args.library)
    _emit(plan)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    sa = sandbox.actions
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    actions = plan.get("actions") or []
    if not actions:
        print("[ERROR] 计划里没有 actions", file=sys.stderr)
        return 2
    # 局部变量不能叫 `sandbox`——顶层 import 的模块名会被它整个遮蔽（UnboundLocalError）
    sb = sa.Sandbox(args.source, args.sandbox)
    report = {"sandbox": str(sb.sandbox_root), "source": str(sb.source_dir),
              "results": [], "ok": True}
    for step in actions:
        name = step.get("action")
        params = step.get("params") or {}
        try:
            res = sa.run_action(name, params, sb)
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
    validator = sandbox.validator
    expectation = {}
    if args.expectation:
        expectation = json.loads(Path(args.expectation).read_text(encoding="utf-8"))
    verdict = validator.validate(Path(args.sandbox), expectation)
    print(f"[i] 裁决：{verdict['verdict']}（{verdict['total']} 个产物；"
          f"{'；'.join(verdict['reasons'])}）", file=sys.stderr)
    _emit(verdict)
    return 0 if verdict["verdict"] == "ok" else 1


# ---------------------------------------------------------------- P2

_TASKBOOK_TEMPLATE = """# 解包攻坚任务书（可直接整段粘贴给 Agent）

## 你是什么、规则是什么
你是「GalgameUnpacker 解包攻坚 Agent」。软件已自动跑完标准链路并在下面这份
诊断包里记录了失败现场。你的工作：读诊断包 → 对照经验库提假设 → **只用允许的
动作**在沙箱里验证假设 → 产物交给验证器裁决。

红线（违反任何一条 = 本轮作废）：
1. 只用「允许的动作」清单里的动作名，白名单外一律不许尝试；
2. 沙箱目录是唯一可写区，源目录只读（copy 不 move）；
3. 产物成败由 `--agent-validate` 的验证器裁决，你自述成功无效；
4. 不联网、不跑诊断包/经验库之外的任何脚本、不改规则库文件；
5. 假设验证通过后，把「症状 → 假设 → 动作 → 产物证据」写成一条候选规则
   交给用户审核（放入 rules/candidates/，绝不直接改 rules/experiences/）。

## 诊断包
路径：{diag_path}
error_code：{error_code}　引擎：{engine}

## 允许的动作（本轮白名单）
{actions}

## 经验候选（检索结果，按分排序）
{candidates}

## 沙箱约定
源目录（只读）：{source_dir}
沙箱目录（唯一可写）：{sandbox_dir}
执行入口：`python orchestrator.py --agent-run --plan <plan.json> --source <源目录> --sandbox <沙箱>`
裁决入口：`python orchestrator.py --agent-validate --sandbox <沙箱> [--expectation e.json]`

## 交付
1. 沙箱产物 + 验证器 ok 裁决；
2. 一份「这次是怎么解的」简报（假设/证据/步骤）；
3. 一条候选规则 JSON（模板见 rules/candidates/ 现有条目）。
"""


def cmd_taskbook(args: argparse.Namespace) -> int:
    """诊断包 → 用户可粘贴的 Agent 任务书（Markdown，落诊断包旁）。"""
    diag_path = Path(args.diagnostic)
    diag = json.loads(diag_path.read_text(encoding="utf-8"))
    plan = experiences.plan(diag, dir=args.library)
    engine = (diag.get("engine") or {}).get("name") or "?"
    text = _TASKBOOK_TEMPLATE.format(
        diag_path=str(diag_path.resolve()),
        error_code=diag.get("error_code"),
        engine=engine,
        actions="\n".join(f"- {a}" for a in plan["allowed_actions"])
        or "- （检索无候选：仅允许只读侦察动作 hex_inspect / copy_to_sandbox）",
        candidates="\n".join(
            f"- {c['id']}（分 {c['score']}，置信 {c['confidence']}）：{c['hypothesis']}"
            for c in plan["candidates"][:5])
        or "- （无命中——按诊断包自行推理，动作仍受白名单约束）",
        source_dir=args.source or (diag.get("game") or {}).get("dir") or "<源目录>",
        sandbox_dir=args.sandbox or "<建议：诊断包旁新建 sb/ 目录>",
    )
    out = diag_path.parent / "taskbook.md"
    # fail-soft（2026-11-11 冻结实测）：新构建的未签名 exe 在陌生目录写盘会被
    # 按进程信誉拦（PermissionError，同文件源码态可写）——任务书是本轮唯一交付物，
    # 写不进去就退回 cwd，再不行直接把全文塞进 JSON，绝不崩、绝不空手。
    import os
    written = None
    for cand in (out, Path.cwd() / "taskbook.md"):
        try:
            cand.write_text(text, encoding="utf-8", newline="\n")
            written = cand
            break
        except OSError:
            continue
    if written is not None:
        print(f"[OK] 任务书写入：{written}", file=sys.stderr)
        _emit({"taskbook": str(written), "candidates": len(plan["candidates"]),
               "allowed_actions": plan["allowed_actions"]})
    else:
        print("[WARN] 任务书写不进任何候选位置，全文放 JSON 里", file=sys.stderr)
        _emit({"taskbook": None, "taskbook_text": text,
               "candidates": len(plan["candidates"]),
               "allowed_actions": plan["allowed_actions"]})
    return 0


def cmd_candidate(args: argparse.Namespace) -> int:
    """验证通过的解法 → 候选规则 JSON（落 rules/candidates/，人工审核后人工转正）。"""
    import hashlib
    diag = json.loads(Path(args.diagnostic).read_text(encoding="utf-8"))
    # 审计哈希必须**可复现**：内置 hash() 按进程随机化（PYTHONHASHSEED），同诊断包
    # 两次运行得出不同值，审计链就断了——用 sha256。
    diag_hash = args.hash or hashlib.sha256(
        json.dumps(diag, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
    entry = {
        "id": args.id,
        "status": "candidate",
        "submitted_by": args.by or "user",
        "diagnostic_hash": diag_hash,
        "symptoms": {
            "error_code": [diag.get("error_code")] if diag.get("error_code") else [],
            "tool_error_strings": ([diag["gui_error"][:60]]
                                   if diag.get("gui_error") else []),
            "magic_hex_prefix": [],
            "dir_features": list((diag.get("game") or {}).get("dir_features") or []),
        },
        "hypothesis": args.hypothesis,
        "actions": args.actions.split(",") if args.actions else [],
        "constraints": {},
        "validation": {"kind": "count_at_least", "expect": args.validation or ""},
        "negative_examples": [],
        "confidence": args.confidence,
        "source": args.note or "",
        "applies_to": {"engine": (diag.get("engine") or {}).get("name")},
    }
    bad = [a for a in entry["actions"] if a not in sandbox.actions.REGISTRY]
    if bad:
        print(f"[ERROR] 动作不在白名单：{bad}", file=sys.stderr)
        return 2
    here = Path(__file__).resolve().parent
    out_dir = Path(args.library) if args.library else here / "rules" / "candidates"
    import time as _time
    out = out_dir / f"{args.id}-{_time.strftime('%Y%m%d')}.json"
    # fail-soft：冻结态下 rules/ 可能在只读安装目录里——写不进就交回给调用方处理，
    # 给出明确出路而不是裸 traceback。
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8", newline="\n")
    except OSError as exc:
        payload = json.dumps(entry, ensure_ascii=False, indent=2)
        print(f"[WARN] 候选规则写不进 {out_dir}（{exc}）；全文放 JSON 里，"
              f"请人工保存到仓库 rules/candidates/", file=sys.stderr)
        _emit({"candidate": None, "status": "unwritten", "entry_text": payload})
        return 1
    print(f"[OK] 候选规则写入（待人工审核转正）：{out}", file=sys.stderr)
    _emit({"candidate": str(out), "status": "candidate"})
    return 0


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

    p5 = sub.add_parser("taskbook", help="诊断包 → 用户可粘贴的 Agent 任务书")
    p5.add_argument("--diagnostic", required=True)
    p5.add_argument("--library", default=None)
    p5.add_argument("--source", default=None, help="源目录（写进任务书）")
    p5.add_argument("--sandbox", default=None, help="沙箱目录建议（写进任务书）")

    p6 = sub.add_parser("candidate", help="验证通过的解法 → 候选规则（人工审核转正）")
    p6.add_argument("--diagnostic", required=True)
    p6.add_argument("--id", required=True, help="候选规则 id（kebab-case）")
    p6.add_argument("--hypothesis", required=True)
    p6.add_argument("--actions", default="", help="逗号分隔的白名单动作名")
    p6.add_argument("--validation", default="")
    p6.add_argument("--confidence", type=float, default=0.5)
    p6.add_argument("--note", default="")
    p6.add_argument("--by", default="user")
    p6.add_argument("--hash", default=None)
    p6.add_argument("--library", default=None)

    p1.set_defaults(fn=cmd_diagnose)
    p2.set_defaults(fn=cmd_plan)
    p3.set_defaults(fn=cmd_run)
    p4.set_defaults(fn=cmd_validate)
    p5.set_defaults(fn=cmd_taskbook)
    p6.set_defaults(fn=cmd_candidate)
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else list(argv)
    args = build_parser().parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
