"""Tile locations shared by the server and asset downloader."""

INTERACTIVE_URL = "https://satisfactoryinteractivemap.com/tiles"
CALCULATOR_URL = "https://static.satisfactory-calculator.com/imgMap"
INTERACTIVE_LAYERS = {"interactive-game": "game", "interactive-terrain": "terrain"}
CALCULATOR_LAYERS = {"calculator-game": "gameLayer", "calculator-realistic": "realisticLayer"}
TEXTURES = ("calculator-game", "interactive-game", "interactive-terrain", "calculator-realistic")


def tile_range(texture, z, x_axis=False):
    if texture in INTERACTIVE_LAYERS and 1 <= z <= 5:
        return range(2 ** z)
    if texture in CALCULATOR_LAYERS and 3 <= z <= 6:
        count = 2 ** (z - 1)
        end = (9 * count + 7) // 8
        # The calculator's west bound is slightly west of the dashboard's.
        return range(count // 8, end + (x_axis and count % 8 == 0))
    return range(0)


def tile_url(texture, z, x, y):
    if x not in tile_range(texture, z, x_axis=True) or y not in tile_range(texture, z):
        return None
    if texture in CALCULATOR_LAYERS:
        return f"{CALCULATOR_URL}/{CALCULATOR_LAYERS[texture]}/Stable/{z}/{x}/{y}.webp"
    return f"{INTERACTIVE_URL}/{INTERACTIVE_LAYERS[texture]}/{z}/{y}/{x}.webp"
