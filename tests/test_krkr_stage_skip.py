# -*- coding: utf-8 -*-
"""stage 构建跳过游戏根下的非引擎目录（2026-11-08 速度优化）。

背景：真机（教师催眠2）实证 stage 复制把 output* 产物目录也整树 copy2 一遍
（单轮 ~15GB、多花 2-5 分钟）。这些目录是我们自己的交付物，不参与注入提取。
锁三件事：① output*/分类/.galunpack-view 标记目录被跳过并带原因显式报出；
② 引擎文件（exe / plugin / *.xp3 硬链接）照旧进 stage；③ 单游戏 exe 断言不回退。
"""

import os

import pytest

import krkr_auto_extract as k


def _mk(p, data=b"x"):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def test_reason_matches_products_and_views():
    assert k._stage_skip_reason("output", False) is not None
    assert k._stage_skip_reason("Output", False) is not None      # Windows 大小写无关
    assert k._stage_skip_reason("output_fullauto3", False) is not None
    assert k._stage_skip_reason("分类", False) is not None
    assert k._stage_skip_reason("我的视图", True) is not None      # .galunpack-view 标记
    assert k._stage_skip_reason("plugin", False) is None
    assert k._stage_skip_reason("savedata", False) is None
    # KrkrExtract_Output 只存在于 stage 里，不以这个名字出现在游戏根；即便出现也不匹配产物前缀
    assert k._stage_skip_reason("KrkrExtract_Output", False) is None


def test_scan_reports_skipped_with_counts(tmp_path):
    _mk(tmp_path / "output" / "raw" / "a.png")
    _mk(tmp_path / "output" / "png" / "b.png")
    _mk(tmp_path / "output_fullauto3" / "raw" / "c.ogg")
    _mk(tmp_path / "分类" / "音频" / "d.ogg")
    _mk(tmp_path / "我的视图" / "e.png")
    _mk(tmp_path / "我的视图" / ".galunpack-view", b"mark")
    _mk(tmp_path / "plugin" / "foo.tpm")
    _mk(tmp_path / "savedata" / "save.dat")

    skipped = {name: (n, reason)
               for name, n, reason in k._stage_skip_scan(str(tmp_path))}

    assert set(skipped) == {"output", "output_fullauto3", "分类", "我的视图"}
    assert skipped["output"][0] == 2
    assert skipped["我的视图"][0] == 2          # 标记文件也数进去，规模参考而已
    assert "output*" in skipped["output"][1]
    assert ".galunpack-view" in skipped["我的视图"][1]


def test_scan_ignores_top_level_files_and_missing_dir(tmp_path):
    _mk(tmp_path / "类目清单.csv")   # 顶层文件不是目录，不参与跳过
    assert k._stage_skip_scan(str(tmp_path)) == []
    assert k._stage_skip_scan(str(tmp_path / "不存在")) == []


def test_build_stage_tree_skips_products_keeps_engine(tmp_path):
    game = tmp_path / "game"
    _mk(game / "katei2.exe", b"MZ-fake")
    _mk(game / "data.xp3", b"XP3-fake")
    _mk(game / "plugin" / "foo.tpm")
    _mk(game / "output" / "raw" / "a.png")
    _mk(game / "分类" / ".galunpack-view", b"mark")
    _mk(game / "分类" / "图片" / "b.png")
    stage = tmp_path / "stage"
    stage.mkdir()

    skipped, exe_name = k._build_stage_tree(str(game), str(stage))

    assert {name for name, _n, _r in skipped} == {"output", "分类"}
    assert exe_name == "katei2.exe", "主程序保留原名（exe 名校验型补丁会判改名致死）"
    assert (stage / "katei2.exe").read_bytes() == b"MZ-fake"
    assert not (stage / "game.exe").exists(), "不再额外改名复制一份 game.exe"
    assert (stage / "data.xp3").is_file()
    assert (stage / "plugin" / "foo.tpm").is_file()
    assert not (stage / "output").exists()
    assert not (stage / "分类").exists()


def test_build_stage_tree_hardlinks_xp3(tmp_path):
    game = tmp_path / "game"
    _mk(game / "game.exe", b"MZ")
    _mk(game / "data.xp3", b"XP3")
    stage = tmp_path / "stage"
    stage.mkdir()

    k._build_stage_tree(str(game), str(stage))

    s1, s2 = os.stat(game / "data.xp3"), os.stat(stage / "data.xp3")
    assert (s1.st_ino, s1.st_dev) == (s2.st_ino, s2.st_dev)   # 硬链接零拷贝


def test_build_stage_tree_requires_single_game_exe(tmp_path):
    game = tmp_path / "game"
    _mk(game / "a.exe")
    _mk(game / "b.exe")
    stage = tmp_path / "stage"
    stage.mkdir()
    with pytest.raises(AssertionError):
        k._build_stage_tree(str(game), str(stage))


def test_build_stage_tree_ignores_uninstaller_exes(tmp_path):
    """安装器版游戏目录里的 unins000.exe（Inno）不是游戏主程序（2026-11-08 aniyome 真机）。"""
    game = tmp_path / "game"
    _mk(game / "aniyome.exe", b"MZ-game")
    _mk(game / "unins000.exe", b"MZ-unins")
    _mk(game / "data.xp3", b"XP3")
    stage = tmp_path / "stage"
    stage.mkdir()

    _skipped, exe_name = k._build_stage_tree(str(game), str(stage))

    assert exe_name == "aniyome.exe"
    assert (stage / "aniyome.exe").read_bytes() == b"MZ-game"
    assert (stage / "unins000.exe").is_file(), "卸载器照旧复制进 stage，只是不参与主程序断言"
