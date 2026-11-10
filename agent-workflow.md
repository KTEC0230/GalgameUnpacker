# Agent 攻坚工作流（`新功能.md` 落地说明）

> 一句话：标准链路失败时，软件自动落一份**诊断包**；任何 Agent（zcode / Claude Code）
> 按任务书在**沙箱**里用**白名单动作**验证假设；产物由**硬验证器**裁决；
> 解出来的路子写成**候选规则**，人工审核后转正——下次同类症状直接命中。

## 一、怎么用（用户视角，四步）

```bash
# 1. 诊断包（失败时已自动生成；也可手动对任意游戏/失败 manifest 出包）
python orchestrator.py --agent-diagnose <游戏目录或 D:\GalgameOutput\<名>\manifest.json>

# 2. 生成任务书（可直接粘贴给 zcode / Claude Code 的那份）
python orchestrator.py --agent-taskbook --diagnostic <_work/diagnostic/diagnostic.json>

# 3. Agent 干活（它产出 plan.json 后，软件代跑——动作出白名单即硬失败）
python orchestrator.py --agent-run --plan <plan.json> --source <游戏目录> --sandbox <空目录>

# 4. 裁决
python orchestrator.py --agent-validate --sandbox <沙箱目录> [--expectation e.json]
```

源码态也可以直接 `python agent_cli.py <子命令>`（参数同上，`--help` 可查）。
诊断包是自包含 JSON：错误码、引擎指纹、输入清单（含魔数）、**真实报错原文**、
案例命中、经验候选、日志路径、Agent 契约。**报错原文在里面，不用再翻日志。**

## 二、验证器怎么判（为什么 Agent 骗不了它）

- 逐文件真实打开：图片 Pillow `verify()`、音视频 ffprobe（失败带原因串）；
- 数量按期望核（`count_at_least` / `count_exact` + 可选扩展名过滤）；
- 三态：**ok** / **partial**（差额 ≤20% 且已交付部分全可开）/ **failed**
  （空目录、0 字节文件、打不开的媒体、差超 20%）；
- **不看任何工具退出码**（坑 4：rc=0 而 0 产物是常态陷阱）。

反例测试在 `tests/test_sandbox.py`：假产物、0 字节、错扩展名、数量不符、
rc=0 空目录，全部判 failed。

## 三、怎么审规则（候选 → 正式的唯一人工关卡）

1. Agent 验证成功后产出候选：`python orchestrator.py --agent-candidate
   --diagnostic <包> --id <kebab-id> --hypothesis "..." --actions a,b --validation "..."`
   → 落 `rules/candidates/<id>-<日期>.json`；
2. 人工审核三件事：症状是否够特异（会不会误命中）、动作是否都在白名单、
   negative_examples 是否把不适用场景写清；
3. 通过 → **人工** `git mv rules/candidates/<file>.json rules/experiences/<file>.json`
   并把 `status` 改为正式（去掉 candidate/rejected 字段），重建案例库无关、不用跑构建；
4. 拒绝 → 把 `status` 改 `rejected` + 写 `rejected_reason`，文件留档
   （范例：`link6-kaguya-arc-20261110.json`，用户 2026-11-10 复核维持划走）。
   **候选永不自动转正**；转正也不改 `rules/engines.json`（那是判定规则，另一套）。

## 四、怎么扩展动作白名单

1. `sandbox/actions.py` 的 `REGISTRY` 加条目：名字、`params`（JSON-Schema 子集：
   type/properties/required/enum）、`precondition`、`product_judgment`；
2. `run_action()` 加对应分支：**一律经 toolbridge**（环境清洗/DLL 隔离已被它覆盖），
   成败按 `count_products` 口径、rc 只进诊断字段；
3. 实现里禁止：直接 `subprocess`（绕开 toolbridge）、写沙箱外路径、访问网络；
4. 补测试（happy path + 违规路径），跑 `tests/test_sandbox.py`；
5. 契约文件是**代码生成**的（`generate_contract()`），不用手改；
   构建时 `build_exe.agent_contract_file()` 自动打进包。

## 五、设计红线（改代码前重读）

- 不信任 Agent，信任验证器；未过验证器一律不算成功；
- 沙箱只读源，copy 不 move；白名单外硬失败；
- 候选规则不自动入库；案例 `expected_total` 只进提示不进 reconcile；
- 不做任何绕过 DRM/版权保护的设计；不联网；不读未授权密钥；
- 经验条目引用的动作必须在 `sandbox.actions.REGISTRY` 里（`experiences.py --self-check`）。
