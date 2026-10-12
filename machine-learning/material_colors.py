import json
from pathlib import Path

#Shared palette used by Python and the Three.js viewer for Material IDs:
PALETTE_PATH = Path(__file__).resolve().parent.parent / "shared" / "material_colors.json"


def load_material_colors():
    if not PALETTE_PATH.is_file():
        raise FileNotFoundError(f"Shared material colours not found: {PALETTE_PATH}")

    with PALETTE_PATH.open("r", encoding="utf-8") as file:
        palette = json.load(file)

    if not isinstance(palette, dict) or not palette:
        raise ValueError("Material palette must be a nonempty JSON object")

    colors = {}

    for material, rgb in palette.items():
        if not isinstance(rgb, list) or len(rgb) != 3:
            raise ValueError(f"Invalid RGB colour for {material}: {rgb}")

        if any(type(channel) is not int or not 0 <= channel <= 255 for channel in rgb):
            raise ValueError(f"Invalid RGB channel for {material}: {rgb}")

        colors[material] = tuple(rgb)

    return colors


MATERIAL_COLORS = load_material_colors()