# -*- coding: utf-8 -*-
"""_collect_krkr_output：KrkrExtract 产出 → raw/ 的收货布局锁（2026-11-08）。

背景：真机（教师催眠2）实证 KrkrExtract 按「每个 xp3 一个同名子目录」产出，
旧收货代码硬编码只认 KrkrExtract_Output/data，把 9764 个图片音频视频丢在半路
（manifest 却照报 rc=0 —— 无声的错）。
"""

from orchestrator import _collect_krkr_output


def _touch(tree, rel):
    f = tree / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"x")


def test_multi_folder_layout_collects_per_package(tmp_path):
    """真机形态：每个 xp3 一个同名子目录 → raw/<包名>/，png 归 png。"""
    kout = tmp_path / "KrkrExtract_Output"
    _touch(kout, "data/startup.tjs")
    _touch(kout, "image00/a.png")
    _touch(kout, "voice02/b.ogg")
    _touch(kout, "png/converted.png")
    raw = tmp_path / "raw"
    png = tmp_path / "png"

    err = _collect_krkr_output(kout, raw, png)

    assert err is None
    assert (raw / "data" / "startup.tjs").is_file()
    assert (raw / "image00" / "a.png").is_file()
    assert (raw / "voice02" / "b.ogg").is_file()
    assert (png / "converted.png").is_file()


def test_single_data_layout_merges_into_raw_root(tmp_path):
    """旧机形态：全部在 data/ 下 → 内容并到 raw 根（教师催眠1 5724 那次的布局）。"""
    kout = tmp_path / "KrkrExtract_Output"
    _touch(kout, "data/macro/a.tjs")
    _touch(kout, "data/startup.tjs")
    raw = tmp_path / "raw"
    png = tmp_path / "png"

    err = _collect_krkr_output(kout, raw, png)

    assert err is None
    assert (raw / "macro" / "a.tjs").is_file()
    assert (raw / "startup.tjs").is_file()


def test_existing_raw_content_is_replaced_not_nested(tmp_path):
    """目标已存在时清掉重搬，绝不嵌层（_move_dir_clean 的契约）。"""
    kout = tmp_path / "KrkrExtract_Output"
    _touch(kout, "image00/new.png")
    raw = tmp_path / "raw"
    _touch(raw, "image00/old.png")
    png = tmp_path / "png"

    err = _collect_krkr_output(kout, raw, png)

    assert err is None
    assert (raw / "image00" / "new.png").is_file()
    assert not (raw / "image00" / "old.png").exists()
    assert not (raw / "image00" / "image00").exists(), "嵌层就是那句「无声的错」"
