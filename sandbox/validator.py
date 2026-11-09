#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""硬验证器 —— Agent 产物的裁判（`新功能.md` 零件 C，P1）。

## 红线

**Agent 的产出只有通过验证器才算成功**——Agent 自述成功无效。这里不看任何
工具退出码（坑 4），只做三件事：
  1. 逐文件真实打开（图片 Pillow verify / 音视频 ffprobe）；
  2. 按期望核数量与扩展名；
  3. 给出 ok / partial / failed 三态 + 具体原因（哪些文件、差多少）。

## 期望（expectation）从哪来

诊断包（inputs/entries）、经验条目的 validation、或调用方手写。格式::

    {"kind": "count_at_least" | "count_exact",
     "count": N,                      # 期望产物数
     "exts": [".png", ...],           # 可选：只认这些扩展名
     "playable": true}                # 可选：逐文件过 Pillow/ffprobe

判定：
  · failed —— 空目录 / 有 0 字节文件 / 有打不开的媒体 / 数量低于期望且差得离谱（>20%）
  · partial —— 数量略低于期望（≤20%）但已交付的部分全部可开
  · ok —— 数量达标（或超出）且全部可开
"""
from __future__ import annotations

from pathlib import Path

#: 与 manifest/_verify_media 同一口径的媒体扩展名白名单（静态事实，就地声明）。
IMG_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".gif", ".tga"}
AV_EXT = {".mp4", ".mkv", ".avi", ".webm", ".mov", ".wmv", ".flv", ".mpg", ".mpeg",
          ".mp3", ".ogg", ".wav", ".opus", ".flac", ".m4a", ".aac", ".wma"}

#: 数量差额超过期望的 20% 直接 failed；以内是 partial。
PARTIAL_RATIO = 0.2


def _probe_image(p: Path) -> str | None:
    """Pillow verify；返回失败原因，None = 通过。"""
    try:
        from PIL import Image
        with Image.open(p) as im:
            im.verify()
        return None
    except Exception as exc:                                   # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"


def _probe_av(p: Path) -> str | None:
    """ffprobe（经 toolbridge，失败带原因串）；返回失败原因，None = 通过。"""
    try:
        import toolbridge as tb
        info, reason = tb.ffprobe_ex(str(p))
        return None if info else (reason or "ffprobe 无结果")
    except Exception as exc:                                   # noqa: BLE001
        return f"{type(exc).__name__}: {exc}"


def validate(products_dir: Path | str, expectation: dict | None = None) -> dict:
    """产物目录 + 期望 → 裁决。**只读**；永不抛（坏输入也是一份裁决）。"""
    products_dir = Path(products_dir)
    expectation = expectation or {}
    exts = {e.lower() if e.startswith(".") else f".{e.lower()}"
            for e in (expectation.get("exts") or [])}
    want = expectation.get("count")
    playable = bool(expectation.get("playable", True))

    result: dict = {"verdict": "failed", "products_dir": str(products_dir),
                    "total": 0, "empty_files": [], "broken": [],
                    "nonmedia": 0, "reasons": []}
    reasons = result["reasons"]

    if not products_dir.is_dir():
        reasons.append(f"产物目录不存在：{products_dir}")
        return result
    files = [p for p in sorted(products_dir.rglob("*")) if p.is_file()]
    if exts:
        files = [p for p in files if p.suffix.lower() in exts]
    result["total"] = len(files)
    if not files:
        reasons.append("没有产物（rc=0 空目录是**常态陷阱**，不是成功）")
        return result

    for p in files:
        try:
            size = p.stat().st_size
        except OSError as exc:
            result["broken"].append({"file": p.name, "reason": f"stat 失败：{exc}"})
            continue
        if size == 0:
            result["empty_files"].append(p.name)
    if result["empty_files"]:
        reasons.append(f"{len(result['empty_files'])} 个 0 字节文件"
                       f"（如 {result['empty_files'][:3]}）")

    if playable:
        for p in files:
            if p.name in result["empty_files"]:
                continue
            ext = p.suffix.lower()
            if ext in IMG_EXT:
                err = _probe_image(p)
            elif ext in AV_EXT:
                err = _probe_av(p)
            else:
                result["nonmedia"] += 1
                continue
            if err:
                result["broken"].append({"file": p.name, "reason": err[:160]})
    if result["broken"]:
        reasons.append(f"{len(result['broken'])} 个文件打不开"
                       f"（如 {result['broken'][:2]}）")

    # 数量判定
    if want is not None:
        got = result["total"]
        if got >= want:
            result["verdict"] = "ok"
        elif want and (want - got) / want > PARTIAL_RATIO:
            reasons.append(f"数量 {got} < 期望 {want}（差超过 20%）")
            result["verdict"] = "failed"
        else:
            reasons.append(f"数量 {got} 略低于期望 {want}（≤20%，partial）")
            result["verdict"] = "partial"
    else:
        result["verdict"] = "ok"

    # 任何硬伤（0 字节 / 打不开）压过数量结论
    if result["empty_files"] or result["broken"]:
        result["verdict"] = "failed"
    if result["verdict"] == "ok" and not reasons:
        reasons.append(f"{result['total']} 个产物全部可开"
                       + (f"，数量达标（期望 {want}）" if want is not None else ""))
    return result
