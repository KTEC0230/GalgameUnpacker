#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""经验库检索 —— 症状→假设→动作的推理单元（`新功能.md` 零件 A，P1）。

## 与 cases/ 的分工（别混）

  · cases/      ——「整局游戏」的已验证结果（指纹签名查表，report-only）
  · experiences/——「症状」的推理单元：什么症状 → 什么假设 → 用哪些动作验证

## schema（rules/experiences/*.json，用户 2026-11-09 批准 JSON 不用 YAML）

    id / symptoms{error_code[], tool_error_strings[], magic_hex_prefix[],
                  dir_features[]} / hypothesis / actions[]（必须是
                  sandbox.actions.REGISTRY 里的名字）/ constraints / validation /
                  negative_examples[] / confidence(0~1) / source / applies_to{engine}

## 检索口径

打分制**只报告不决策**（与 case_lib 同一纪律）：把诊断包的症状对照每条经验打分、
排序、给出命中原因，用不用由 Agent（或人）定。检索器绝不改状态、绝不执行动作。
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parent / "rules" / "experiences"

#: 各命中信号的权重（经验条目的 confidence 是它的先验，命中是证据）。
_W_ERROR_CODE = 3.0
_W_TOOL_ERROR = 3.0
_W_MAGIC = 2.0
_W_DIR_FEATURE = 1.0
_W_ENGINE = 1.0

#: schema 必备字段（加载时校验；坏条目跳过并报告，不让一条脏数据毒死整库）。
REQUIRED_FIELDS = ("id", "symptoms", "hypothesis", "actions", "confidence",
                   "source", "applies_to")


def _validate_entry(entry: dict, source: str) -> tuple[dict | None, str | None]:
    """单条校验：返回 (entry, None) 或 (None, 原因)。"""
    missing = [k for k in REQUIRED_FIELDS if k not in entry]
    if missing:
        return None, f"{source}: 缺字段 {','.join(missing)}"
    conf = entry.get("confidence")
    if not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
        return None, f"{source}: confidence 必须是 0~1"
    if not isinstance(entry.get("actions"), list):
        return None, f"{source}: actions 必须是列表"
    if not isinstance(entry.get("symptoms"), dict):
        return None, f"{source}: symptoms 必须是对象"
    return entry, None


def load_all(dir: Path | str | None = None) -> tuple[list[dict], list[str]]:
    """加载经验库。返回 (entries, problems)——坏条目跳过但**留痕**（无声的漏最危险）。"""
    root = Path(dir) if dir else DEFAULT_DIR
    entries: list[dict] = []
    problems: list[str] = []
    if not root.is_dir():
        return entries, [f"经验库目录不存在：{root}"]
    for p in sorted(root.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{p.name}: 解析失败（{exc}）")
            continue
        entry, problem = _validate_entry(data, p.name)
        if problem:
            problems.append(problem)
        else:
            entries.append(entry)
    return entries, problems


def _hit_text(diagnostic: dict) -> str:
    """把诊断包里所有「报错文本」拼成一块，供 tool_error_strings 子串匹配。"""
    parts = [str(diagnostic.get("gui_error") or "")]
    for a in diagnostic.get("attempted") or []:
        parts.append(str(a.get("detail") or ""))
    return "\n".join(parts)


def match(diagnostic: dict, entries: list[dict] | None = None,
          dir: Path | str | None = None) -> list[dict]:
    """诊断包 → 按分排序的候选经验（附命中原因）。**只报告不执行**。"""
    if entries is None:
        entries, _problems = load_all(dir)
    err_code = str(diagnostic.get("error_code") or "")
    hit_text = _hit_text(diagnostic).lower()
    features = set(diagnostic.get("game", {}).get("dir_features") or [])
    engine = ((diagnostic.get("engine") or {}).get("name")) or ""
    magics = [str(i.get("magic_hex") or "").lower()
              for i in diagnostic.get("inputs") or [] if i.get("magic_hex")]

    out: list[dict] = []
    for e in entries:
        sym = e.get("symptoms") or {}
        reasons: list[str] = []
        score = 0.0
        codes = sym.get("error_code") or []
        if err_code and err_code in codes:
            score += _W_ERROR_CODE
            reasons.append(f"error_code={err_code}")
        for s in sym.get("tool_error_strings") or []:
            if str(s).lower() in hit_text:
                score += _W_TOOL_ERROR
                reasons.append(f"报错串命中：{s}")
                break
        for pref in sym.get("magic_hex_prefix") or []:
            pref_l = str(pref).lower()
            if any(m.startswith(pref_l) for m in magics):
                score += _W_MAGIC
                reasons.append(f"魔数 {pref}")
                break
        hits_feat = [f for f in (sym.get("dir_features") or []) if f in features]
        if hits_feat:
            score += _W_DIR_FEATURE * len(hits_feat)
            reasons.append("目录特征：" + "、".join(hits_feat))
        applies = e.get("applies_to") or {}
        if applies.get("engine"):
            if applies["engine"] == engine:
                score += _W_ENGINE
            else:
                continue                      # 明确写了他引擎的条目，不投给这个案子
        if score <= 0:
            continue
        out.append({
            "id": e["id"],
            "hypothesis": e["hypothesis"],
            "actions": list(e.get("actions") or []),
            "constraints": e.get("constraints") or {},
            "validation": e.get("validation") or {},
            "negative_examples": list(e.get("negative_examples") or []),
            "confidence": e.get("confidence"),
            "source": e.get("source"),
            "score": round(score, 2),
            "matched": reasons,
        })
    out.sort(key=lambda x: (-x["score"], -(x["confidence"] or 0)))
    return out


def plan(diagnostic: dict, dir: Path | str | None = None) -> dict:
    """诊断包 → Agent 计划骨架（候选经验 + 允许动作 + 沙箱说明）。

    计划是**给 Agent 的出发点**：候选按分排序、动作并集是本轮白名单子集；
    Agent 在此之上细化步骤，但动作不得越出 sandbox.actions.REGISTRY。
    """
    entries, problems = load_all(dir)
    candidates = match(diagnostic, entries)
    allowed = sorted({a for c in candidates for a in c["actions"]})
    return {
        "schema_version": 1,
        "error_code": diagnostic.get("error_code"),
        "engine": (diagnostic.get("engine") or {}).get("name"),
        "candidates": candidates,
        "allowed_actions": allowed,
        "library_problems": problems,
        "note": ("计划只含检索结果；执行必须走 sandbox（--agent-run），"
                 "产物必须过验证器（--agent-validate）才算成功。"),
    }


def _self_check() -> int:
    """CLI 冒烟：校验自带经验库的 schema 与动作名。"""
    import sandbox.actions as sa
    entries, problems = load_all()
    bad_actions = [a for e in entries for a in e["actions"] if a not in sa.REGISTRY]
    print(f"经验 {len(entries)} 条；问题 {len(problems)}；未知动作 {sorted(set(bad_actions))}")
    for p in problems:
        print("  -", p)
    return 1 if problems or bad_actions else 0


if __name__ == "__main__":
    raise SystemExit(_self_check())
