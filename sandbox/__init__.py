# -*- coding: utf-8 -*-
"""沙箱层：Agent 受控动作白名单（actions）+ 硬验证器（validator，P1）。

红线（`新功能.md` §4，本包是它们的执行点）：
  · 白名单外的动作硬失败——Agent 不能自己拼命令行；
  · 沙箱只读源：唯一写盘动作是 copy_to_sandbox，且只写进沙箱目录；
  · Agent 的产出只有通过 validator 才算成功（validator 在 P1 落地）。
"""
