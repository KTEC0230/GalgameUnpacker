#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""受控动作白名单 —— Agent 能做什么的**唯一注册表**（`新功能.md` 零件 B）。

## 设计立场

Agent（外部 LLM）不可信：它不许拼命令行、不许碰白名单外的工具、不许写沙箱外
的任何路径。所以这里的每个动作都是**对 toolbridge 现有能力的一层薄封装**——
不新增子进程出口（toolbridge 的 `_sanitize_env`/`_clear_dll_dir` 已覆盖全部出口，
§19.2 第 3 条），成败一律按 `count_products` 数产物、rc 只进诊断字段（全库口径）。

## P0 边界（2026-11-09）

本文件先落**注册表**（名字 / 参数 schema / 前置条件 / 产物判定 / 约束），
它是 `generate_contract()` 的数据源、随包分发给 Agent 当「行为说明书」。
**执行体（`run_action`）在 P1 接线**——P0 阶段 registry 每项的 `status` 是
`"planned"`，P1 全部翻 `"ready"` 并补 `run()`。契约消费方（Agent）必须容忍
`planned` 动作被拒绝执行。

## csc_build 的收紧（用户 2026-11-09 批准）

只允许编译**仓库自带**的 .cs（`_gyu_tool` / `_hg3_tool`，经 `tb.ensure_csharp`），
Agent 提供的源码一律拒绝——不给自己造一个「编译执行任意代码」的口子。
"""
from __future__ import annotations

#: 全局约束（进契约文件；validator 与 run_action 共同执行）。
CONSTRAINTS = {
    "sandbox_only": "所有动作只读源目录；写盘只允许发生在沙箱目录内",
    "no_network": "任何动作不访问网络",
    "no_arbitrary_commands": "白名单外动作硬失败；参数由 schema 约束",
    "trust_products_not_rc": "成败看产物数（toolbridge count_products 口径），rc 只进诊断",
    "csc_sources_allowlist": ["_gyu_tool.cs", "_hg3_tool.cs"],
}

#: 动作注册表。`params` 用 JSON-Schema 子集（type/properties/required/description），
#: Agent 可读、validator 可校验、不引依赖。
REGISTRY: dict[str, dict] = {
    "garbro_list": {
        "description": "用 GARbro.Console 列归档条目数（判定「能不能读」的第一探针）",
        "status": "planned",
        "toolbridge": "garbro_list",
        "params": {
            "type": "object",
            "properties": {
                "archive": {"type": "string", "description": "归档文件绝对路径"},
            },
            "required": ["archive"],
        },
        "precondition": "archive 在沙箱可见的源目录内且存在",
        "product_judgment": "返回 (listable, 条目数, stderr 尾部)；条目数即产物口径",
    },
    "garbro_extract": {
        "description": "用 GARbro.Console 解归档到沙箱目录",
        "status": "planned",
        "toolbridge": "run",
        "params": {
            "type": "object",
            "properties": {
                "archive": {"type": "string"},
                "dest": {"type": "string", "description": "沙箱内目标目录"},
            },
            "required": ["archive", "dest"],
        },
        "precondition": "dest 必须在沙箱目录内",
        "product_judgment": "dest 树内新增文件数（count_products 快照差）",
    },
    "assetstudio_export": {
        "description": "AssetStudio.CLI Convert 导出（Texture2D/Sprite/AudioClip 单类型）",
        "status": "planned",
        "toolbridge": "assetstudio_export",
        "params": {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "*_Data 目录或 bundle 文件"},
                "dest": {"type": "string"},
                "type_name": {"type": "string", "enum": ["Texture2D", "Sprite", "AudioClip"]},
            },
            "required": ["input", "dest", "type_name"],
        },
        "precondition": "dest 在沙箱内；type_name 单类型（坑 4：逗号静默归零）",
        "product_judgment": "dest 树内文件数；rc=0 而 0 产物是**常态**不是成功",
    },
    "assetstudio_json": {
        "description": "AssetStudio.CLI JSON 枚举（地面真相口径）",
        "status": "planned",
        "toolbridge": "assetstudio_export",
        "params": {
            "type": "object",
            "properties": {
                "input": {"type": "string"},
                "dest": {"type": "string"},
                "type_name": {"type": "string"},
                "group_assets": {"type": "string", "enum": ["ByType", "BySource"]},
            },
            "required": ["input", "dest", "type_name"],
        },
        "precondition": "dest 在沙箱内",
        "product_judgment": "JSON 文件数（每个资产一份）",
    },
    "tlg2png": {
        "description": "tlg2png 批量转 PNG",
        "status": "planned",
        "toolbridge": "tlg2png",
        "params": {
            "type": "object",
            "properties": {
                "src": {"type": "string"},
                "dst": {"type": "string"},
            },
            "required": ["src", "dst"],
        },
        "precondition": "dst 在沙箱内",
        "product_judgment": "PNG 产物数 vs 输入 tlg 数",
    },
    "png_carve": {
        "description": "PNA/PNAP 多帧容器逐帧 carve（_pna_carve.carve）",
        "status": "planned",
        "toolbridge": "_pna_carve",
        "params": {
            "type": "object",
            "properties": {
                "src": {"type": "string"},
                "dst": {"type": "string"},
            },
            "required": ["src", "dst"],
        },
        "precondition": "dst 在沙箱内；一个容器出多帧，产物数 ≠ 输入数",
        "product_judgment": "carve 出的帧数（postprocess 的 frames_out 口径）",
    },
    "csc_build": {
        "description": "编译仓库自带的 C# 工具（白名单：_gyu_tool.cs / _hg3_tool.cs）",
        "status": "planned",
        "toolbridge": "ensure_csharp",
        "params": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "enum": ["gyu", "hg3"]},
            },
            "required": ["key"],
        },
        "precondition": "key 在 CONSTRAINTS.csc_sources_allowlist 内；Agent 源码一律拒绝",
        "product_judgment": "exe 存在且不比源码旧（ensure_csharp 语义）",
    },
    "ffprobe_check": {
        "description": "ffprobe 探单个媒体（含失败原因串）",
        "status": "planned",
        "toolbridge": "ffprobe_ex",
        "params": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
        "precondition": "path 在沙箱内",
        "product_judgment": "info 或 (None, reason)——reason 是诊断素材不是可忽略噪音",
    },
    "pillow_verify": {
        "description": "Pillow verify() 探单张图片",
        "status": "planned",
        "toolbridge": None,
        "params": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
        "precondition": "path 在沙箱内",
        "product_judgment": "可开 + 尺寸；异常原文进诊断",
    },
    "hex_inspect": {
        "description": "读文件头部十六进制（魔数判别，只读）",
        "status": "planned",
        "toolbridge": None,
        "params": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "length": {"type": "integer", "minimum": 4, "maximum": 4096},
            },
            "required": ["path"],
        },
        "precondition": "path 在沙箱内；length 缺省 64",
        "product_judgment": "hex + ASCII 双栏文本",
    },
    "copy_to_sandbox": {
        "description": "把源文件/目录拷进沙箱（唯一写盘动作；copy 不 move，源只读）",
        "status": "planned",
        "toolbridge": None,
        "params": {
            "type": "object",
            "properties": {
                "src": {"type": "string"},
                "dest": {"type": "string", "description": "沙箱内相对路径"},
            },
            "required": ["src", "dest"],
        },
        "precondition": "src 在源目录内（只读）；dest 解析后必须在沙箱根内",
        "product_judgment": "拷贝后字节数一致",
    },
}


def generate_contract() -> dict:
    """Agent 契约（随包分发 / 嵌进每个诊断包）：能做什么、不许做什么。"""
    return {
        "schema_version": 1,
        "role": (
            "你是解包攻坚 Agent。读诊断包 → 查经验库（rules/experiences/，P1）→ 提假设 → "
            "只用下列动作在沙箱里验证 → 产物必须通过验证器（sandbox/validator.py，P1）"
            "才算成功。你不被信任：验证器才是裁判。"
        ),
        "constraints": dict(CONSTRAINTS),
        "actions": {
            name: {
                "description": spec["description"],
                "status": spec["status"],
                "params": spec["params"],
                "precondition": spec["precondition"],
                "product_judgment": spec["product_judgment"],
            }
            for name, spec in REGISTRY.items()
        },
        "validator": {
            "entry": "sandbox/validator.py（P1）",
            "rule": "ok / partial / failed 三态；Agent 自述成功无效",
        },
        "candidate_rules": {
            "target": "rules/candidates/",
            "rule": "候选规则带诊断包哈希与操作者，绝不自动进 rules/experiences/",
        },
    }


def _self_check() -> int:
    """CLI 冒烟：打印契约 JSON 到 stdout。"""
    import json
    print(json.dumps(generate_contract(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_self_check())
