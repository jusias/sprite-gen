# SPDX-License-Identifier: Apache-2.0
"""Effect subject profile component extraction tests.

Verifies:
1. `subject: effect` retains scattered debris pieces across slots instead of dropping them as stray satellites.
2. Similar-sized pieces across slots get grouped cleanly per slot rather than clustering seeds into one slot.
3. `subject: character` preserves legacy behavior by dropping stray satellites outside seed proximity.
"""
from __future__ import annotations

from PIL import Image

from sprite_gen.frames.extract import extract_component_images, connected_components


def _draw_solid_rect(image: Image.Image, x0: int, y0: int, w: int, h: int, color=(200, 200, 200, 255)) -> None:
    px = image.load()
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            if 0 <= x < image.width and 0 <= y < image.height:
                px[x, y] = color


def test_effect_extraction_keeps_all_scattered_pieces() -> None:
    # 6 slots, 100px each -> 600x100 strip
    strip = Image.new("RGBA", (600, 100), (0, 0, 0, 0))

    # Slot 0 (0..100): 1 main body
    _draw_solid_rect(strip, 30, 30, 40, 40)

    # Slot 1 (100..200): 1 main body
    _draw_solid_rect(strip, 130, 30, 40, 40)

    # Slot 2 (200..300): 5 scattered pieces
    _draw_solid_rect(strip, 210, 20, 12, 12)
    _draw_solid_rect(strip, 240, 20, 12, 12)
    _draw_solid_rect(strip, 270, 20, 12, 12)
    _draw_solid_rect(strip, 220, 60, 12, 12)
    _draw_solid_rect(strip, 260, 60, 12, 12)

    # Slot 3 (300..400): 4 scattered pieces
    _draw_solid_rect(strip, 315, 25, 14, 14)
    _draw_solid_rect(strip, 365, 25, 14, 14)
    _draw_solid_rect(strip, 325, 65, 14, 14)
    _draw_solid_rect(strip, 365, 65, 14, 14)

    # Slot 4 (400..500): 5 scattered pieces
    _draw_solid_rect(strip, 410, 20, 12, 12)
    _draw_solid_rect(strip, 440, 20, 12, 12)
    _draw_solid_rect(strip, 470, 20, 12, 12)
    _draw_solid_rect(strip, 420, 60, 12, 12)
    _draw_solid_rect(strip, 460, 60, 12, 12)

    # Slot 5 (500..600): 4 scattered pieces
    _draw_solid_rect(strip, 515, 25, 14, 14)
    _draw_solid_rect(strip, 565, 25, 14, 14)
    _draw_solid_rect(strip, 525, 65, 14, 14)
    _draw_solid_rect(strip, 565, 65, 14, 14)

    # 1. Effect mode: all pieces in each slot must be retained
    effect_images = extract_component_images(strip, 6, subject="effect")
    assert effect_images is not None
    assert len(effect_images) == 6

    counts = [len(connected_components(img)) for img in effect_images]
    assert counts == [1, 1, 5, 4, 5, 4], f"Effect should retain all pieces: {counts}"

    # 2. Character mode: scattered pieces outside seed proximity are dropped
    char_images = extract_component_images(strip, 6, subject="character")
    assert char_images is not None
    char_counts = [len(connected_components(img)) for img in char_images]
    # In character mode, the 6 seeds pick the largest areas (slots 0 and 1, plus 4 other pieces),
    # and distant satellites in other slots get dropped.
    assert char_counts != [1, 1, 5, 4, 5, 4]


def test_effect_similar_sized_pieces_grouped_per_slot() -> None:
    # 6 slots, 100px each. Each slot has 3 similar-sized pieces (15x15).
    strip = Image.new("RGBA", (600, 100), (0, 0, 0, 0))
    for slot in range(6):
        x_base = slot * 100
        _draw_solid_rect(strip, x_base + 15, 30, 15, 15)
        _draw_solid_rect(strip, x_base + 45, 30, 15, 15)
        _draw_solid_rect(strip, x_base + 75, 30, 15, 15)

    effect_images = extract_component_images(strip, 6, subject="effect")
    assert effect_images is not None
    assert len(effect_images) == 6

    # Every slot must have exactly its 3 pieces
    for i, img in enumerate(effect_images):
        comps = connected_components(img)
        assert len(comps) == 3, f"Slot {i} expected 3 components, got {len(comps)}"


def test_character_profile_drops_stray_satellite() -> None:
    # 2 slots (200x100)
    strip = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
    # Slot 0: main body (40x40) + distant satellite (10x10) far away from seed bbox
    _draw_solid_rect(strip, 10, 10, 40, 40)
    _draw_solid_rect(strip, 80, 80, 10, 10)  # > 15% pad from seed

    # Slot 1: main body (40x40)
    _draw_solid_rect(strip, 130, 10, 40, 40)

    char_images = extract_component_images(strip, 2, subject="character")
    assert char_images is not None
    assert len(char_images) == 2

    # In character mode, distant satellite is dropped
    comps0 = connected_components(char_images[0])
    assert len(comps0) == 1, f"Character should have dropped distant satellite, got {len(comps0)}"
