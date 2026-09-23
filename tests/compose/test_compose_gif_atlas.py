import json
from pathlib import Path

from PIL import Image, ImageSequence

from sprite_gen.compose import compose_gif


def test_compose_gif_reconstructs_logical_frames_from_compact_atlas(tmp_path: Path) -> None:
    page = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    page.paste((255, 0, 0, 255), (1, 2, 5, 8))
    page.paste((0, 0, 255, 255), (10, 3, 13, 8))
    page.save(tmp_path / "page-0.png")
    manifest = {
        "sprite_sheet_alpha": "page-0.png",
        "sprite_sheet_alpha_pages": ["page-0.png"],
        "animation": {
            "cellWidth": 16,
            "cellHeight": 16,
            "rows": {"south_attack": {"row": 0, "frames": 2, "fps": 10, "loop": False}},
        },
        "frame_layout": {
            "cellWidth": 16,
            "cellHeight": 16,
            "sheetWidth": 32,
            "sheetHeight": 32,
            "sheetCount": 1,
            "sheets": ["page-0.png"],
            "logicalPivot": {"x": 8, "y": 16},
            "pivotOrigin": "trimmed-frame-top-left-pixels",
            "rows": {
                "south_attack": [
                    {"page": 0, "x": 1, "y": 2, "w": 4, "h": 6,
                     "sourceX": 2, "sourceY": 4, "pivotX": 6, "pivotY": 12},
                    {"page": 0, "x": 10, "y": 3, "w": 3, "h": 5,
                     "sourceX": 9, "sourceY": 7, "pivotX": -1, "pivotY": 9},
                ],
            },
        },
    }
    (tmp_path / "manifest.compact.json").write_text(json.dumps(manifest), encoding="utf-8")

    assert compose_gif.run(run_dir=tmp_path, atlas_manifest="manifest.compact.json") == 0

    output = tmp_path / "exports" / "south_attack.gif"
    with Image.open(output) as gif:
        frames = [frame.convert("RGBA").copy() for frame in ImageSequence.Iterator(gif)]
    assert len(frames) == 2
    assert frames[0].size == (16, 16)
    assert frames[0].getpixel((2, 4))[:3] == (255, 0, 0)
    assert frames[1].getpixel((9, 7))[:3] == (0, 0, 255)

    gif_manifest = json.loads((tmp_path / "exports" / "gif-manifest.json").read_text())
    assert gif_manifest["atlas_manifest"] == "manifest.compact.json"
    assert gif_manifest["exports"][0]["source"] == "manifest.compact.json"


def test_compose_gif_rejects_pivot_that_does_not_restore_logical_pivot(tmp_path: Path) -> None:
    page = Image.new("RGBA", (8, 8), (255, 255, 255, 255))
    page.save(tmp_path / "page.png")
    manifest = {
        "sprite_sheet_alpha": "page.png",
        "animation": {
            "cellWidth": 8,
            "cellHeight": 8,
            "rows": {"south_idle": {"row": 0, "frames": 1, "fps": 8, "loop": True}},
        },
        "frame_layout": {
            "cellWidth": 8,
            "cellHeight": 8,
            "logicalPivot": {"x": 4, "y": 8},
            "rows": {"south_idle": [
                {"page": 0, "x": 0, "y": 0, "w": 8, "h": 8,
                 "sourceX": 0, "sourceY": 0, "pivotX": 3, "pivotY": 8},
            ]},
        },
    }
    (tmp_path / "manifest.compact.json").write_text(json.dumps(manifest), encoding="utf-8")

    try:
        compose_gif.run(run_dir=tmp_path, atlas_manifest="manifest.compact.json")
    except SystemExit as exc:
        assert "pivot does not restore logicalPivot" in str(exc)
    else:
        raise AssertionError("invalid pivot must fail")
