#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断包构建 —— 失败时给 Agent 的第一手材料（`新功能.md` 零件 D，P0）。

## 它是什么

一份**自包含**的 JSON：错误码、引擎指纹、输入清单（含魔数）、真实报错原文、
案例命中、日志路径、Agent 契约。目标读者是**外部 Agent**（zcode / Claude Code）：
它没有会话上下文，包里没有的东西它就不知道——所以「把报错原文抄进来」比
「给个错误码让它猜」值钱得多（manual.py 的 gui_error 教训原样适用）。

## 边界

  · 只读：构建过程只读游戏目录 / manifest / _work 日志，唯一写盘是
    `write_package()`（落在 `<out>/_work/diagnostic/`），失败永不抛——
    诊断包写不出去绝不能把一次失败变成两次失败（faillog.py 同一纪律）。
  · 无网络、无 Agent 逻辑：本模块只**描述现场**，不动手解任何东西。
  · P0 范围：experience_candidates 先落 schema 位（空列表 +
    errorcodes 的经验方向提示）；检索器在 P1。

## CLI 预览（不是 P1 的四个 agent 命令）

    python diagnostics.py <manifest.json 或输出目录> [--out PATH]

stdout 纯 JSON、人读提示走 stderr——与 --dry-run 同一口径。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import errorcodes

#: 诊断包 schema 版本（消费方按它做兼容判断；改字段先升它）。
SCHEMA_VERSION = 1

#: 顶层文件清单上限（目录特征用，防巨型目录拖垮构建）。
_TOP_FILES_CAP = 40


def _head_hex(p: Path, n: int = 16) -> str | None:
    """文件头魔数的 hex；读不到（不存在/无权限）返回 None，绝不抛。"""
    try:
        if not p.is_file():
            return None
        with p.open("rb") as fh:
            head = fh.read(n)
        return head.hex()
    except OSError:
        return None


def _top_files(game_dir: Path) -> list[str]:
    """顶层文件名（截断）。目录特征给经验检索用，不递归——大目录 rglob 是分钟级。"""
    try:
        names = sorted(p.name for p in game_dir.iterdir())
        return names[:_TOP_FILES_CAP]
    except OSError:
        return []


def _dir_features(game_dir: Path) -> list[str]:
    """目录特征标签（小写连字符）。经验条目的 symptoms.dir_features 与它对齐。"""
    features: list[str] = []
    try:
        entries = list(game_dir.iterdir())
    except OSError:
        return features
    names = [p.name.lower() for p in entries]
    if any(n.startswith("unins") for n in names):
        features.append("installer-layout")
    if any(n.endswith(".xp3") for n in names):
        features.append("xp3-archives")
    if any(n == "krkrextract.exe" for n in names):
        features.append("krkr-tool-present")
    data_dirs = [p for p in entries if p.is_dir() and p.name.endswith("_Data")]
    if data_dirs:
        features.append("unity-data-dir")
        d = data_dirs[0]
        if (d / "GameAssembly.dll").exists() or (d / "il2cpp_data").exists():
            features.append("il2cpp")
        if (d / "data.unity3d").exists():
            features.append("data-unity3d")
        if (d / "StreamingAssets").exists():
            features.append("streaming-assets")
    if any(n == "gameassembly.dll" for n in names):
        features.append("il2cpp")
    return features


def _env_block() -> dict:
    """环境快照（只读、无子进程）。单项失败就留一句，残缺好过没有（doctor 同纪律）。"""
    env: dict = {"python": sys.version.split()[0], "platform": sys.platform}
    try:
        import doctor
        env["integrity"] = doctor.integrity_level()
    except Exception:                                          # noqa: BLE001
        env["integrity"] = "未知"
    env["tools"] = {}
    try:
        import toolbridge as tb
        for key in ("garbro", "assetstudio", "krkr"):
            try:
                env["tools"][key] = str(tb.find_tool(key))
            except Exception:                                  # noqa: BLE001
                env["tools"][key] = None
    except Exception:                                          # noqa: BLE001
        env["tools"] = {}
    return env


def _logs_block(out_dir: Path | None) -> dict:
    """_work 下的阶段日志路径（存在才列——不存在的路径对 Agent 是噪音）。"""
    logs: dict = {}
    if out_dir is None:
        return logs
    work = Path(out_dir) / "_work"
    try:
        if work.is_dir():
            for p in sorted(work.glob("*.log")):
                logs[p.stem] = str(p)
    except OSError:
        pass
    return logs


def _inputs_block(source: dict | None, game_dir: Path | None) -> list[dict]:
    """输入清单：archives + unsupported 合并，能摸到文件就补魔数。

    Unity 链路的 archives 是类型名（Texture2D…）不是文件 → 摸不到就 fields 留空，
    不硬造（「没验」不许伪装成「验过」的同一纪律）。
    """
    inputs: dict[str, dict] = {}
    for a in (source or {}).get("archives") or []:
        name = a.get("name") or a.get("archive")
        if not name:
            continue
        inputs[name] = {"name": name, "size": None, "magic_hex": None,
                        "entries": a.get("entries"), "extracted": a.get("extracted"),
                        "listable": a.get("entries") is not None, "reason": None}
    for u in (source or {}).get("unsupported") or []:
        name = u.get("archive") or u.get("name")
        if not name:
            continue
        row = inputs.setdefault(name, {"name": name, "size": None, "magic_hex": None,
                                       "entries": None, "extracted": None,
                                       "listable": False, "reason": None})
        row["listable"] = False
        row["reason"] = u.get("reason")
    if game_dir is not None:
        for name, row in inputs.items():
            p = Path(game_dir) / name
            if p.is_file():
                row["magic_hex"] = _head_hex(p)
                try:
                    row["size"] = p.stat().st_size
                except OSError:
                    pass
    return list(inputs.values())


def _gui_error(stages: list[dict] | None) -> str:
    """真实报错原文（与 manual.py 同一提取逻辑——从它那借，别抄第二份）。"""
    try:
        import manual
        return manual._gui_error_text(stages or [])
    except Exception:                                          # noqa: BLE001
        return ""


def _detect_block(stages: list[dict] | None, engine: str | None) -> dict:
    """引擎指纹块。detect 阶段的 data 被 `Stage.as_dict()` 平铺到顶层
    （engine/score/fired_ids…，见 manual.py 对同款行为的注释），从那儿取。"""
    det = next((s for s in stages or []
                if isinstance(s, dict) and s.get("stage") == "detect"), {})
    return {
        "name": det.get("engine") or engine,
        "score": det.get("score"),
        "above_threshold": det.get("above_threshold"),
        "fired_signals": list(det.get("fired_ids") or []),
        "notes": det.get("notes") or [],
    }


def build(*, error_code: str, engine: str | None = None,
          game_dir: Path | str | None = None, out_dir: Path | str | None = None,
          stages: list[dict] | None = None, source: dict | None = None,
          case_match: dict | None = None) -> dict:
    """组装诊断包（纯函数，除了读盘探测；永不抛——调用方放心直呼）。"""
    game = Path(game_dir) if game_dir else None
    out = Path(out_dir) if out_dir else None
    meta = errorcodes.get(error_code) or {}
    try:
        from sandbox.actions import generate_contract
        contract = generate_contract()
    except Exception:                                          # noqa: BLE001
        contract = None
    package: dict = {
        "schema_version": SCHEMA_VERSION,
        "error_code": error_code,
        "error_summary": meta.get("summary") or error_code,
        "error_description": errorcodes.describe(error_code),
        "experience_hints": errorcodes.experience_hints(error_code),
        "engine": _detect_block(stages, engine),
        "game": {
            "dir": str(game) if game else None,
            "top_files": _top_files(game) if game else [],
            "dir_features": _dir_features(game) if game else [],
        },
        "inputs": _inputs_block(source, game),
        "attempted": [
            {"stage": s.get("stage"), "ok": s.get("ok"), "detail": s.get("detail")}
            for s in (stages or [])
            if isinstance(s, dict) and not s.get("ok")
        ],
        "gui_error": _gui_error(stages),
        "case_matches": case_match or None,
        "experience_candidates": [],      # P1：experiences 检索结果（schema 位先占）
        "logs": _logs_block(out),
        "env": _env_block(),
        "agent": {"contract": contract},
    }
    return {k: v for k, v in package.items() if v is not None}


def write_package(package: dict, out_dir: Path | str) -> Path | None:
    """把诊断包写到 `<out>/_work/diagnostic/diagnostic.json`。**永不抛**。

    返回实际路径；写不了（目录建不出等）返回 None 并 stderr 一句——
    与 faillog 同一纪律：诊断是善后，不能变成新的失败。
    """
    import traceback as _tb
    try:
        d = Path(out_dir) / "_work" / "diagnostic"
        d.mkdir(parents=True, exist_ok=True)
        path = d / "diagnostic.json"
        path.write_text(json.dumps(package, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return path
    except OSError as exc:
        print(f"[WARN] 诊断包写不进去：{type(exc).__name__}: {exc}", file=sys.stderr)
    except Exception as exc:                                   # noqa: BLE001
        print(f"[WARN] 诊断包构建/写入异常：{exc}", file=sys.stderr)
        _tb.print_exc(file=sys.stderr)
    return None


def build_from_manifest(manifest_path: Path | str) -> dict:
    """从一次**已落盘的失败 manifest** 重建诊断包（给存量失败补包 / CLI 预览）。"""
    path = Path(manifest_path)
    if path.is_dir():
        path = path / "manifest.json"
    man = json.loads(path.read_text(encoding="utf-8"))
    out_dir = path.parent
    src = man.get("source") or {}
    return build(
        error_code=str(man.get("error") or "unknown"),
        engine=man.get("engine"),
        game_dir=src.get("game_dir"),
        out_dir=out_dir,
        stages=man.get("stages"),
        source=src,
        case_match=src.get("case_match"),
    )


def main(argv: list[str] | None = None) -> int:
    """预览入口：stdout 纯 JSON，人读提示走 stderr。"""
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or argv[0] in ("-h", "--help"):
        print("用法: python diagnostics.py <manifest.json 或输出目录> [--out PATH]",
              file=sys.stderr)
        return 2
    target = Path(argv[0])
    try:
        package = build_from_manifest(target)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[ERROR] 读不到失败 manifest：{target}（{exc}）", file=sys.stderr)
        return 1
    if "--out" in argv:
        i = argv.index("--out")
        if i + 1 < len(argv):
            written = write_package(package, Path(argv[i + 1]))
            print(f"[OK] 诊断包写入：{written}", file=sys.stderr)
    print(json.dumps(package, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
