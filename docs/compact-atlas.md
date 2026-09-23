# Compact atlas pages

`compact-atlas` is a deterministic post-compose tool. It trims transparent pixels
without resampling, packs the resulting rectangles into equal square pages, and writes
the page index plus logical-cell offsets into a new manifest.

```bash
sprite-gen compact-atlas --run-dir <run> \
  --page-size 2048 --max-pages 4 --gutter 2 --alpha-padding 1 \
  --max-empty-percent 25
```

The default policy keeps every animation clip on one Texture2DArray slice. Empty space
is measured against all allocated fixed-size slices, including gutter. If that ratio is
above `--max-empty-percent`, the report records `thresholdExceeded: true` but still keeps
clip locality.

Add `--allow-clip-split-over-threshold` to opt into a second global MaxRects pass only
when the threshold is exceeded. That pass may place frames from one clip on multiple
slices. `compact-atlas.report.json.clipsSpanningPages` lists every affected clip, so the
choice is observable rather than implicit.

Outputs are non-destructive:

- `<page-prefix>-0.png` through `<page-prefix>-N.png`, each exactly `page-size` square.
- `manifest.compact.json`, whose frame rects contain `page`, `x/y/w/h`, and
  `sourceX/sourceY`.
- `compact-atlas.report.json`, including occupancy, policy, page count and split clips.

The original `sprite-sheet-alpha.png` and `manifest.json` remain compose/correction SOTs.
Installers copy the compact manifest under the runtime name only after QA.

## Individual-frame source

When `frames/frames-manifest.json` exists, `compact-atlas` reads its ordered
`rows[].files[]` PNGs directly instead of cutting cells back out of the composed atlas.
For each PNG it finds the alpha bounds, applies `--alpha-padding`, and writes the packed
`page/x/y/w/h` plus logical-cell `sourceX/sourceY` offsets to `manifest.compact.json`.
It also records `pivotX/pivotY` in trimmed-frame pixels from the top-left. The pivot is
the original logical cell's bottom-center, so it remains stable even when transparent
bottom or side padding is removed. `frame_layout.logicalPivot` and `pivotOrigin` make
that coordinate contract explicit.
This is a pixel-for-pixel crop: there is no resampling or regeneration, and long weapons
cannot spill into a neighboring atlas cell. The composed-atlas path remains as a
backward-compatible fallback for older runs without a frames manifest.
