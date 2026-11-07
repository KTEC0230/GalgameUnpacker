# -*- coding: utf-8 -*-
"""NO_AUTO_DISMISS（默认开）的行为锁（2026-11-08）。

背景：krkrZ 的「正常に起動できませんでした」是致命启动失败框——点掉 OK
游戏进程必退、注入式提取 UI 陪葬（11-07/11-08 四轮真机 + 弹窗正文日志实证）。
抽文件发生在**弹窗挂着的时候**，所以默认不自动点框，带弹窗拖包。
"""

import krkr_auto_extract as kae


def test_no_auto_dismiss_defaults_on():
    """致命框默认不能点：NO_AUTO_DISMISS 缺省必须为 True。"""
    assert kae.NO_AUTO_DISMISS is True, (
        "NO_AUTO_DISMISS 默认值被改掉了——点掉致命框 = 游戏必退 = 整条链路死")


def test_gate_blocks_dismissal(monkeypatch):
    """开关开着时 dismiss_dialogs 必须在碰任何 user32 之前就返回空。"""
    monkeypatch.setattr(kae, "NO_AUTO_DISMISS", True)
    # user32 换成没有 EnumWindows 的空壳：若闸门失效往下走会立刻 AttributeError
    monkeypatch.setattr(kae, "user32", object())
    assert kae.dismiss_dialogs(123) == []
