#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""错误码表 —— 「退出码 / error 字符串」的**唯一出处**（新功能 P0，2026-11-09）。

## 为什么需要它

run() 与 faillog 调用点散着 15 个错误码字面量，语义只活在写它那天的脑子里；
Agent 攻坚（`新功能.md`）要靠这张表把「软件报了什么」翻译成「该往哪个方向查」。
本表是**数据 + 纯函数**：不 import orchestrator（避免循环依赖）、不读磁盘、不碰网络。

## 与其它模块的分工

  · orchestrator  —— 错误码的**生产方**（_finish_failure / faillog 调用点，字面量不变）
  · manual.py     —— 按错误码给人工方案（plan_for 的入参就是这里的 code）
  · diagnostics.py—— 诊断包 `error_code` 字段的校验与解释（Agent 的第一读入口）
  · tests         —— 用源码扫描护栏钉住「调用点新增的码必须进表」（防漂移）

`experience_hints` 指向 rules/experiences/ 的条目 id（P1 落地）；表先写**约定**，
条目没落地时消费方必须容忍空引用——查无此 id 就当没有，不许报错。
"""
from __future__ import annotations

import re
from typing import Mapping

#: 错误码 → 元数据。`rc` = orchestrator 的进程退出码；
#: `stage_hint` = 一句话「失败发生在哪」；`experience_hints` = 建议查的经验方向
#: （id 是 P1 rules/experiences/ 的约定命名，查不到就忽略，不许当错误）。
ERROR_CODES: dict[str, dict] = {
    "detect-failed": {
        "rc": 3,
        "summary": "指纹规则没命中，判不出引擎",
        "stage_hint": "detect",
        "typical_symptoms": ["目录里没有已知引擎的标志性文件", "游戏根目录选错（多套了一层）"],
        "experience_hints": ["detect-game-root-nested"],
    },
    "chain-not-implemented": {
        "rc": 2,
        "summary": "引擎判得出，但没有自动链路",
        "stage_hint": "extract",
        "typical_symptoms": ["Tyrano/Electron 等小众引擎", "退出码 2"],
        "experience_hints": ["tyrano-asar-manual"],
    },
    "preflight-failed": {
        "rc": 1,
        "summary": "解包前预检失败（磁盘余量等）",
        "stage_hint": "preflight",
        "typical_symptoms": ["磁盘余量不足", "游戏目录不可读"],
        "experience_hints": [],
    },
    "reset-failed": {
        "rc": 1,
        "summary": "输出目录清空失败（--overwrite 路径）",
        "stage_hint": "reset",
        "typical_symptoms": ["旧产物被进程占用", "权限拒绝"],
        "experience_hints": ["output-dir-locked"],
    },
    "cancelled": {
        "rc": 1,
        "summary": "用户主动取消（不是失败）",
        "stage_hint": "任意阶段边界",
        "typical_symptoms": ["GUI 取消按钮", "Ctrl+C"],
        "experience_hints": [],
    },
    "no-extractor-mapped": {
        "rc": 2,
        "summary": "引擎有链路实现但 EXTRACTORS 没映射到（内部状态不一致）",
        "stage_hint": "extract",
        "typical_symptoms": ["IMPLEMENTED 与 EXTRACTORS 漂移（护栏测试应已拦住）"],
        "experience_hints": [],
    },
    "extract-failed": {
        "rc": 1,
        "summary": "解包阶段失败（链路本体没走通）",
        "stage_hint": "extract",
        "typical_symptoms": ["GARbro 列不出/解不出", "AssetStudio 枚举 0 资产",
                             "KrkrExtract 窗口不出现"],
        "experience_hints": ["garbro-console-false-negative", "assetstudio-zero-products",
                             "assetstudio-batch-cap", "krkr-encrypted-xp3",
                             "krkr-fatal-dialog-blocks-drop", "krkr-drop-point-blocked",
                             "krkr-exe-rename-check", "repack-external-ress"],
    },
    "postprocess-failed": {
        "rc": 1,
        "summary": "后处理失败（tlg/pna 转 PNG 等）",
        "stage_hint": "postprocess",
        "typical_symptoms": ["tlg2png 崩", "pna carve 0 帧"],
        "experience_hints": ["tlg2png-cjk-path"],
    },
    "verify-failed": {
        "rc": 1,
        "summary": "验收失败（有产物但验不过）",
        "stage_hint": "verify",
        "typical_symptoms": ["Pillow verify() 报错", "ffprobe 无结果"],
        "experience_hints": ["ffprobe-embedded-cover"],
    },
    "verify-no-products": {
        "rc": 1,
        "summary": "验收时没有可验收的产物（extract 声称成功但 raw 是空的）",
        "stage_hint": "verify",
        "typical_symptoms": ["rc=0 却 0 文件（坑 4 同族）"],
        "experience_hints": ["assetstudio-zero-products"],
    },
    # ---- faillog-only（发生在阶段装配之前，没有完整 manifest）----
    "game-dir-missing": {
        "rc": None,
        "summary": "游戏目录不存在",
        "stage_hint": "main",
        "typical_symptoms": ["路径打错", "盘符/移动盘换位"],
        "experience_hints": [],
    },
    "dry-run-detect-failed": {
        "rc": None,
        "summary": "--dry-run 阶段判不出引擎",
        "stage_hint": "dry-run",
        "typical_symptoms": [],
        "experience_hints": ["detect-game-root-nested"],
    },
    "output-not-writable": {
        "rc": None,
        "summary": "输出目录不可写（写探针失败）",
        "stage_hint": "main",
        "typical_symptoms": ["安全软件按进程+目录拦截", "Documents 受终端防护"],
        "experience_hints": ["output-dir-av-protect", "integrity-low"],
    },
    "reuse-raw-missing": {
        "rc": None,
        "summary": "--reuse-raw 指向的 raw 目录不存在",
        "stage_hint": "main",
        "typical_symptoms": ["路径打错", "上一轮产物被删"],
        "experience_hints": [],
    },
    "reuse-raw-clean-failed": {
        "rc": None,
        "summary": "复用模式清空旧 png/manifest 失败",
        "stage_hint": "main",
        "typical_symptoms": ["文件被占用"],
        "experience_hints": ["output-dir-locked"],
    },
    # ---- GUI 侧（gui.py 工作线程/目录探测）----
    "no-writable-location": {
        "rc": None,
        "summary": "GUI 找遍候选目录都不可写",
        "stage_hint": "gui",
        "typical_symptoms": ["程序目录/LOCALAPPDATA/TEMP 全被拦"],
        "experience_hints": ["output-dir-av-protect", "integrity-low"],
    },
    "worker-crashed": {
        "rc": None,
        "summary": "GUI 工作线程异常退出",
        "stage_hint": "gui",
        "typical_symptoms": ["BaseException 穿透（_worker 兜底记录）"],
        "experience_hints": [],
    },
}


def get(code: str) -> dict | None:
    """查错误码元数据；查无此码返回 None（调用方自行降级，不许抛）。"""
    return ERROR_CODES.get(code)


def describe(code: str) -> str:
    """一行人读描述（诊断包 / 日志用）；未知码原样返回。"""
    meta = get(code)
    if not meta:
        return code
    rc = meta.get("rc")
    rc_text = f"（退出码 {rc}）" if rc is not None else ""
    return f"{code}{rc_text}：{meta.get('summary', '')}"


def experience_hints(code: str) -> list[str]:
    """该错误码建议查的经验条目 id（P1 前 always 空、查无即空，不报错）。"""
    meta = get(code) or {}
    return list(meta.get("experience_hints") or [])


#: 从源码里扫「调用点用了但表里没有」的码 —— 测试用，防新码漂移。
#: 参数区禁括号（`[^()]`）：verify 的错误码存进变量再传（`…, err, …)`）时，
#: 松正则会跨过整个调用爬到下一个带引号的词上（实测扫出假阳性 "organize"）。
_RE_FINISH = re.compile(r'_finish_failure\([^()]*?"([a-z-]+)"')
_RE_FAILLOG = re.compile(r'log_failure\(error="([a-z-]+)"')


def codes_in_source(source_text: str) -> set[str]:
    """静态扫描一段源码里出现的错误码（_finish_failure / log_failure 调用点）。"""
    return set(_RE_FINISH.findall(source_text)) | set(_RE_FAILLOG.findall(source_text))


def missing_from_table(source_text: str) -> set[str]:
    """源码里用到、但表里没有的码（应为空集；测试钉住）。"""
    return codes_in_source(source_text) - set(ERROR_CODES)


def as_contract() -> dict:
    """给 Agent 契约文件用的精简视图（stable 字段，测试锁定键集）。"""
    return {
        code: {
            "rc": meta.get("rc"),
            "summary": meta.get("summary", ""),
            "stage_hint": meta.get("stage_hint", ""),
            "experience_hints": list(meta.get("experience_hints") or []),
        }
        for code, meta in ERROR_CODES.items()
    }


def _self_check() -> int:
    """CLI 冒烟：python errorcodes.py [源文件...] —— 报「源码有而表没有」的码。"""
    import sys
    bad: set[str] = set()
    for path in sys.argv[1:]:
        bad |= missing_from_table(__import__("pathlib").Path(path).read_text(encoding="utf-8"))
    if bad:
        print("表里缺这些码：", ", ".join(sorted(bad)))
        return 1
    print(f"OK：表 {len(ERROR_CODES)} 个码，源码引用无遗漏")
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_check())
