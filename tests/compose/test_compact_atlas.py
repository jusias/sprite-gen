import json
from pathlib import Path

from PIL import Image, ImageDraw

from sprite_gen.compose import compact_atlas


def _run(tmp_path: Path, *, clips: int = 2, frames: int = 2, page_size: int = 64,
         max_empty_percent: float = 100, allow_split: bool = False,
         use_frames_manifest: bool = True):
    atlas = Image.new("RGBA", (frames * 32, clips * 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(atlas)
    rows = {}
    animation_rows = {}
    frame_rows = []
    for clip in range(clips):
        name = f"clip_{clip}"
        row = []
        files = []
        for frame in range(frames):
            x, y = frame * 32, clip * 32
            color = (clip * 70, frame * 70, 255, 255)
            draw.rectangle((x + 4, y + 4, x + 27, y + 27), fill=color)
            row.append({"x": x, "y": y, "w": 32, "h": 32})
            relative_name = f"frames/{name}/frame-{frame}.png"
            frame_path = tmp_path / relative_name
            frame_path.parent.mkdir(parents=True, exist_ok=True)
            individual = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
            ImageDraw.Draw(individual).rectangle((4, 4, 27, 27), fill=color)
            individual.save(frame_path)
            files.append(relative_name)
        rows[name] = row
        animation_rows[name] = {"row": clip, "frames": frames, "fps": 8, "loop": True}
        frame_rows.append({"state": name, "frames": frames, "files": files})
    atlas.save(tmp_path / "sprite-sheet-alpha.png")
    manifest = {
        "characterId": "test",
        "sprite_sheet_alpha": "sprite-sheet-alpha.png",
        "game_input": "sprite-sheet-alpha.png",
        "animation": {"cellWidth": 32, "cellHeight": 32, "columns": frames, "rows": animation_rows},
        "frame_layout": {"sheetWidth": atlas.width, "sheetHeight": atlas.height,
                         "cellWidth": 32, "cellHeight": 32, "rows": rows},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if use_frames_manifest:
        (tmp_path / "frames" / "frames-manifest.json").write_text(
            json.dumps({"rows": frame_rows}), encoding="utf-8")
    result = compact_atlas.run(
        run_dir=tmp_path, page_size=page_size, max_pages=4, gutter=1, alpha_padding=0,
        max_empty_percent=max_empty_percent,
        allow_clip_split_over_threshold=allow_split,
    )
    return result, json.loads((tmp_path / "manifest.compact.json").read_text()), \
        json.loads((tmp_path / "compact-atlas.report.json").read_text())


def test_compact_atlas_trims_without_resampling_and_preserves_each_clip_page(tmp_path: Path) -> None:
    result, manifest, report = _run(tmp_path)

    assert result == 0
    assert manifest["frame_layout"]["sheetCount"] == 1
    assert manifest["frame_layout"]["sheets"] == ["sprite-sheet-alpha-0.png"]
    assert report["clipsSpanningPages"] == {}
    assert report["frameSource"] == "frames/frames-manifest.json"
    frame = manifest["frame_layout"]["rows"]["clip_0"][0]
    assert (frame["w"], frame["h"], frame["sourceX"], frame["sourceY"]) == (24, 24, 4, 4)
    with Image.open(tmp_path / "sprite-sheet-alpha-0.png") as page:
        restored = page.crop((frame["x"], frame["y"], frame["x"] + frame["w"], frame["y"] + frame["h"]))
    assert restored.getpixel((0, 0)) == (0, 0, 255, 255)


def test_clip_split_is_applied_only_when_threshold_is_exceeded_and_enabled(tmp_path: Path) -> None:
    _result, manifest, report = _run(
        tmp_path, clips=2, frames=3, page_size=64, max_empty_percent=10, allow_split=True)

    assert manifest["compact_atlas"]["clipSplitApplied"] is True
    assert report["clipSplitApplied"] is True
    assert report["clipsSpanningPages"]


def test_threshold_excess_does_not_split_without_opt_in(tmp_path: Path) -> None:
    _result, manifest, report = _run(
        tmp_path, clips=2, frames=2, page_size=64, max_empty_percent=10, allow_split=False)

    assert manifest["compact_atlas"]["clipSplitApplied"] is False
    assert report["thresholdExceeded"] is True
    assert report["clipsSpanningPages"] == {}


def test_composed_atlas_fallback_remains_available(tmp_path: Path) -> None:
    _result, manifest, report = _run(tmp_path, use_frames_manifest=False)

    assert report["frameSource"] == "sprite-sheet-alpha.png"
    frame = manifest["frame_layout"]["rows"]["clip_0"][0]
    assert (frame["w"], frame["h"], frame["sourceX"], frame["sourceY"]) == (24, 24, 4, 4)
    assert (frame["pivotX"], frame["pivotY"]) == (12, 28)


def test_individual_frames_are_used_instead_of_composed_cell_pixels(tmp_path: Path) -> None:
    _run(tmp_path)
    with Image.open(tmp_path / "sprite-sheet-alpha.png") as opened:
        contaminated = opened.convert("RGBA")
    ImageDraw.Draw(contaminated).rectangle((28, 0, 31, 31), fill=(255, 0, 0, 255))
    contaminated.save(tmp_path / "sprite-sheet-alpha.png")

    _result, manifest, _report = _run_existing(tmp_path)
    frame = manifest["frame_layout"]["rows"]["clip_0"][0]
    assert (frame["pivotX"], frame["pivotY"]) == (12, 28)
    assert manifest["frame_layout"]["logicalPivot"] == {"x": 16, "y": 32}
    assert manifest["frame_layout"]["pivotOrigin"] == "trimmed-frame-top-left-pixels"
    with Image.open(tmp_path / "sprite-sheet-alpha-0.png") as page:
        packed = page.crop((frame["x"], frame["y"], frame["x"] + frame["w"], frame["y"] + frame["h"]))
    assert (255, 0, 0, 255) not in set(packed.getdata())


def _run_existing(tmp_path: Path):
    result = compact_atlas.run(
        run_dir=tmp_path, page_size=64, max_pages=4, gutter=1, alpha_padding=0,
        max_empty_percent=100, allow_clip_split_over_threshold=False,
    )
    return result, json.loads((tmp_path / "manifest.compact.json").read_text()), \
        json.loads((tmp_path / "compact-atlas.report.json").read_text())
