# -*- coding: utf-8 -*-
"""拖拽**源头**（Explorer 条目）的遮挡恢复（2026-11-08，堕落妻子真机）。

真机现场：游戏致命框（#32770，NO_AUTO_DISMISS 刻意留着不能点）压住 Explorer
条目中心，旧代码只试中心点、裸 SetForegroundWindow 抬窗被前台锁拒绝、重试
只会重取同一个矩形 → 4 次全灭 assert。修复 = `_find_item_point` 扫整块条目
矩形（中心优先）+ `raise_ui_window` TOPMOST 连招 + 挪 Explorer 三级递进。

替身思路与 test_krkr_drop_point.py 一致：把 Z 序抽象成 WindowFromPoint 的返回值。
"""
from ctypes import wintypes

import pytest

import krkr_auto_extract as kae

EXPLORER_HWND = 3003
DIALOG_HWND = 2002
RECT_ITEM = (100, 100, 300, 300)      # Explorer 里某个 xp3 条目的矩形

CLASSES = {EXPLORER_HWND: "CabinetWClass", DIALOG_HWND: "#32770"}


class FakeUser32:
    def __init__(self, overlay):
        self.overlay = overlay          # callable(x, y) -> hwnd
        self.setpos_calls = []

    def ShowWindow(self, hwnd, cmd):
        return 1

    def SetWindowPos(self, hwnd, after, x, y, cx, cy, flags):
        self.setpos_calls.append((hwnd, after, x, y, cx, cy))
        return 1

    def BringWindowToTop(self, hwnd):
        return 1

    def SetForegroundWindow(self, hwnd):
        return 0                        # 永远模拟前台锁

    def GetForegroundWindow(self):
        return DIALOG_HWND

    def GetWindowRect(self, hwnd, ptr):
        rc = ptr._obj
        rc.left, rc.top, rc.right, rc.bottom = (0, 0, 2000, 1000)
        return 1

    def WindowFromPoint(self, pt):
        return self.overlay(pt.x, pt.y)

    def GetClassNameW(self, hwnd, buf, n):
        # 真实 Win32 对 0/未知句柄返回 0 字符（cls.value == ""）
        buf.value = CLASSES.get(hwnd, "")[: max(0, n - 1)]
        return len(buf.value)

    def EnumWindows(self, cb, lp):
        return 1                        # 桌面上没有别的窗口（close_all_explorers 用）


def _install(monkeypatch, overlay):
    fake = FakeUser32(overlay)
    monkeypatch.setattr(kae, "user32", fake)
    monkeypatch.setattr(kae.time, "sleep", lambda *a: None)
    monkeypatch.setattr(kae, "log", lambda *a, **kw: None)
    return fake


def test_center_blocked_other_point_found(monkeypatch):
    """中心被致命框压住、矩形其余点露着 → 必须从面上找到非中心点。"""
    cx, cy = 200, 200

    def overlay(x, y):
        return DIALOG_HWND if (x, y) == (cx, cy) else EXPLORER_HWND

    _install(monkeypatch, overlay)

    point, blockers, sampled = kae._find_item_point(RECT_ITEM)

    assert point is not None and point != (cx, cy), "不能死磕中心点"
    x, y = point
    assert RECT_ITEM[0] <= x < RECT_ITEM[2] and RECT_ITEM[1] <= y < RECT_ITEM[3]
    assert blockers.get("#32770") == 1, "中心那一下要记进诊断"
    assert sampled >= 2


def test_whole_rect_blocked_reports_blocker(monkeypatch):
    """整块矩形全被压 → None，且 blockers 说得清是谁挡的（不许塌缩成空 dict）。"""
    _install(monkeypatch, lambda x, y: DIALOG_HWND)

    point, blockers, sampled = kae._find_item_point(RECT_ITEM)

    assert point is None
    assert sampled > 0
    assert set(blockers) == {"#32770"}


def test_degenerate_rect_is_invalid_not_empty_blockers(monkeypatch):
    """矩形退化（最小化/句柄失效）要显式报 rect_invalid，不许伪装成「没人挡」。"""
    _install(monkeypatch, lambda x, y: EXPLORER_HWND)

    point, blockers, _s = kae._find_item_point((100, 100, 100, 100))

    assert point is None
    assert blockers.get("rect_invalid") == 1


def test_windowfrompoint_zero_reported(monkeypatch):
    """WindowFromPoint 返回 0（窗口不可见）要记进诊断。"""
    _install(monkeypatch, lambda x, y: 0)

    point, blockers, _s = kae._find_item_point(RECT_ITEM)

    assert point is None
    assert any("WindowFromPoint 返回 0" in k for k in blockers), blockers


def test_directuihwnd_also_accepted(monkeypatch):
    """Explorer 的列表视图宿主（DirectUIHWND）与框架类同口径接受。"""
    classes = {EXPLORER_HWND: "DirectUIHWND", DIALOG_HWND: "#32770"}

    class Fake2(FakeUser32):
        def GetClassNameW(self, hwnd, buf, n):
            buf.value = classes.get(hwnd, "Unknown")[: max(0, n - 1)]
            return len(buf.value)

    fake = Fake2(lambda x, y: DIALOG_HWND if (x, y) == (200, 200) else EXPLORER_HWND)
    monkeypatch.setattr(kae, "user32", fake)
    monkeypatch.setattr(kae.time, "sleep", lambda *a: None)
    monkeypatch.setattr(kae, "log", lambda *a, **kw: None)

    point, _b, _s = kae._find_item_point(RECT_ITEM)

    assert point is not None and point != (200, 200)


def test_main_drags_from_unblocked_grid_point_when_center_covered(
        tmp_path, monkeypatch):
    """端到端：中心被 #32770 压住时，main 仍能从网格点拖出去（旧代码在此 assert 死）。"""
    stage = tmp_path / "stage" / "auto"
    stage.mkdir(parents=True)
    (stage / "game.exe").write_bytes(b"fake")
    (stage / "data.xp3").write_bytes(b"a")
    game = tmp_path / "game"
    game.mkdir()

    # 条目矩形 (10,10,50,50)：中心 (30,30) 被致命框压住，网格点 (22,22) 露在 Explorer 上
    grid = [(x, y) for y in range(22, 50, 24) for x in range(22, 50, 24)]

    def overlay(x, y):
        if (x, y) == (30, 30):
            return DIALOG_HWND
        if (x, y) in grid:
            return EXPLORER_HWND
        return DIALOG_HWND

    fake = _install(monkeypatch, overlay)
    monkeypatch.setattr(kae, "STAGE_ROOT", str(stage.parent))
    monkeypatch.setattr(kae, "pids_by_exe_path", lambda target: [123])
    monkeypatch.setattr(kae.subprocess, "Popen", lambda *a, **kw: None)
    monkeypatch.setattr(kae.subprocess, "run", lambda *a, **kw: None)
    monkeypatch.setattr(kae, "WINDOW_WAIT", 0)
    monkeypatch.setattr(kae, "wait_ui_window", lambda pid: (1001, 0.0))
    monkeypatch.setattr(kae, "dismiss_dialogs", lambda pid: [])
    monkeypatch.setattr(kae, "click_button_ex", lambda pid, label: (True, "替身：已开启"))
    monkeypatch.setattr(kae, "close_all_explorers", lambda hint: None)
    monkeypatch.setattr(kae, "find_explorer_by_title_hint", lambda hint: EXPLORER_HWND)
    monkeypatch.setattr(kae, "uia_item_rect", lambda hwnd, name: (10, 10, 50, 50))
    monkeypatch.setattr(kae, "wait_task_done", lambda outdir, ui: (2, {}, 0))
    monkeypatch.setattr(kae, "find_drop_point_ex", lambda hwnd, attempts=None: (1001, (106, 106)))
    monkeypatch.setattr(kae, "ensure_drop_point", lambda hwnd, point: point)
    drags = []
    monkeypatch.setattr(kae, "drag", lambda *a: drags.append(a))

    assert kae.main([str(game), "--reuse-stage", "--keep-stage"]) == 0
    assert len(drags) == 1
    assert drags[0][:2] == (22, 22), "必须从没被压住的网格点起拖，而不是死在中心"
    assert drags[0][:2] != (30, 30)
    # Explorer 必须被摆到固定位置（起点终点同屏）：place 调用不动 Z 序（after=0）带显式尺寸
    assert any(c[0] == EXPLORER_HWND and c[1] == 0 and c[2:4] == kae.EXPLORER_PLACE[:2]
               for c in fake.setpos_calls), fake.setpos_calls


def test_place_explorer_uses_fixed_layout(monkeypatch):
    """_place_explorer 摆到 EXPLORER_PLACE（不动 Z 序，after=0）。"""
    fake = _install(monkeypatch, lambda x, y: EXPLORER_HWND)

    kae._place_explorer(EXPLORER_HWND)

    assert fake.setpos_calls == [(EXPLORER_HWND, 0) + kae.EXPLORER_PLACE]


# ---------------------------------------------------------------------------
# 2026-11-08 堕落妻子第二轮真机：失败路径泄漏 stage 进程（game.exe 活着占住部署
# 目录，下一次部署改名直接 Permission denied）。收尾清理改放 finally，两条路径都要锁：
# ① inject 中途异常；② index-carve 兜底 early_done 提前 return（旧代码也跳过清理）。
# ---------------------------------------------------------------------------

def _stage_fixture(tmp_path):
    stage = tmp_path / "stage" / "auto"
    stage.mkdir(parents=True)
    (stage / "game.exe").write_bytes(b"fake")
    (stage / "data.xp3").write_bytes(b"a")
    game = tmp_path / "game"
    game.mkdir()
    return game


def test_main_failure_still_kills_stage_processes(tmp_path, monkeypatch):
    game = _stage_fixture(tmp_path)
    _install(monkeypatch, lambda x, y: 0)
    monkeypatch.setattr(kae, "STAGE_ROOT", str(tmp_path / "stage"))
    monkeypatch.setattr(kae, "pids_by_exe_path", lambda target: [123] if str(target).endswith("game.exe") else [456])
    killed = []

    def fake_run(cmd, **kw):
        killed.append(cmd)
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(kae.subprocess, "run", fake_run)
    monkeypatch.setattr(kae.subprocess, "Popen", lambda *a, **kw: None)
    monkeypatch.setattr(kae, "WINDOW_WAIT", 0)
    monkeypatch.setattr(kae, "_run_inject",
                        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("item point blocked")))

    with pytest.raises(AssertionError):
        kae.main([str(game), "--reuse-stage"])   # 不带 --keep-stage：finally 必须收进程

    assert any("taskkill" in c for c in killed), "失败也要收 stage 进程"


def test_main_early_done_still_kills_stage_processes(tmp_path, monkeypatch):
    game = _stage_fixture(tmp_path)
    _install(monkeypatch, lambda x, y: 0)
    monkeypatch.setattr(kae, "STAGE_ROOT", str(tmp_path / "stage"))
    monkeypatch.setattr(kae, "pids_by_exe_path", lambda target: [123])
    killed = []

    def fake_run(cmd, **kw):
        killed.append(cmd)
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr(kae.subprocess, "run", fake_run)
    monkeypatch.setattr(kae.subprocess, "Popen", lambda *a, **kw: None)
    monkeypatch.setattr(kae, "WINDOW_WAIT", 0)
    monkeypatch.setattr(kae, "_run_inject", lambda *a, **kw: ([], True))

    assert kae.main([str(game), "--reuse-stage"]) == 0
    assert any("taskkill" in c for c in killed), "early_done 提前 return 也要收进程"
