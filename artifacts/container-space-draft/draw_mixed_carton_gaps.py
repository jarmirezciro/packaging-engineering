"""Draw two to-scale conceptual cutaways for the article's fit explanation."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUTPUT = Path(__file__).resolve().parent
SCALE = 0.50
CARTON_DEPTH = 600
BAY_DEPTH = 2 * CARTON_DEPTH
WIDTH = 1200
HEIGHT = 900
FLOOR = 595


def draw_scene(packed: bool) -> Image.Image:
    art = Image.new("RGBA", (820, 660))
    ink = ImageDraw.Draw(art)

    def project(x, y, z=0):
        return round(56 + x * SCALE + z * 0.11), round(FLOOR - y * SCALE - z * 0.085)

    def surface(points, fill, outline=None, line_width=2):
        vertices = [project(*point) for point in points]
        ink.polygon(vertices, fill=fill)
        if outline:
            ink.line(vertices + [vertices[0]], fill=outline, width=line_width, joint="curve")

    def cuboid(x, y, width, height, palette, *, front=0):
        face, top, side, edge, tape = palette
        right, upper = x + width, y + height
        back = front + CARTON_DEPTH
        surface(
            [(x, upper, front), (right, upper, front), (right, upper, back), (x, upper, back)],
            top, edge,
        )
        surface(
            [(right, y, front), (right, y, back), (right, upper, back), (right, upper, front)],
            side, edge,
        )
        surface([(x, y, front), (right, y, front), (right, upper, front), (x, upper, front)], face, edge)
        center = x + width / 2
        surface(
            [(center - 20, upper, front + 6), (center + 20, upper, front + 6),
             (center + 20, upper, back - 5), (center - 20, upper, back - 5)],
            tape,
        )
        surface(
            [(center - 20, upper, front), (center + 20, upper, front),
             (center + 20, upper - 58, front), (center - 20, upper - 58, front)],
            tape,
        )
        ink.line([project(x + 10, upper - 10, front), project(right - 10, upper - 10, front)],
                 fill=(255, 255, 255, 80), width=2)

    shadow = Image.new("RGBA", art.size)
    ImageDraw.Draw(shadow).ellipse((50, 535, 785, 620), fill=(24, 55, 65, 43))
    art.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(13)))
    wall = "#9db3bd"
    surface([(0, 0, BAY_DEPTH), (WIDTH, 0, BAY_DEPTH), (WIDTH, HEIGHT, BAY_DEPTH), (0, HEIGHT, BAY_DEPTH)],
            "#edf4f5", wall)
    for x in range(80, WIDTH, 80):
        ink.line([project(x, 0, BAY_DEPTH), project(x, HEIGHT, BAY_DEPTH)], fill="#dce8ea", width=2)

    surface([(0, 0, 0), (WIDTH, 0, 0), (WIDTH, 0, BAY_DEPTH), (0, 0, BAY_DEPTH)],
            "#c4d3d9", "#6d8a96", 4)
    gaps = [(600, WIDTH)] if packed else [(0, 300), (900, WIDTH)]
    for low, high in gaps:
        surface([(low, 0, 0), (high, 0, 0), (high, 0, CARTON_DEPTH), (low, 0, CARTON_DEPTH)],
                "#b9ded5", "#488d81", 3)

    # Wireframe only on the right and along the roof keeps the cutaway open.
    surface([(WIDTH, 0, 0), (WIDTH, 0, BAY_DEPTH), (WIDTH, HEIGHT, BAY_DEPTH), (WIDTH, HEIGHT, 0)],
            None, wall, 3)
    ink.line([project(0, HEIGHT), project(WIDTH, HEIGHT), project(WIDTH, HEIGHT, BAY_DEPTH)],
             fill=wall, width=3)
    ink.line([project(0, 0), project(0, HEIGHT), project(0, HEIGHT, BAY_DEPTH)], fill=wall, width=3)

    offset = 0 if packed else 300
    kraft = ("#dfac77", "#f3c892", "#b57c4d", "#875a38", "#efcc9d")
    kraft_light = ("#e8bb8b", "#f6d1a6", "#be895e", "#875a38", "#f4d6ad")
    blue = ("#4a93c1", "#8ac7e4", "#27709e", "#155276", "#b8e2f2")
    background = ("#cfa584", "#e2bea1", "#ad8264", "#8c6b57", "#e7ccb3")
    # A full rear row adds depth and shows why a floor slot must extend into
    # the container. Keep it identical in the two arrangements.
    for x, width, upper in [(0, 400, 900), (400, 420, 650), (820, 380, 780)]:
        cuboid(x, 0, width, 390, background, front=CARTON_DEPTH)
        cuboid(x, 390, width, upper - 390, background, front=CARTON_DEPTH)

    cuboid(offset, 0, 300, 480, kraft)
    cuboid(offset, 480, 300, 420, kraft_light)
    cuboid(offset + 300, 0, 300, 370, kraft_light)
    cuboid(offset + 300, 370, 300, 230, kraft)
    if packed:
        cuboid(600, 0, 600, 600, blue)

    if not packed:
        # Test the same cube against the right wall. The striped part of its
        # front face intersects the short stack in this attempted position.
        start, end = project(600, 600), project(900, 0)
        hatch = Image.new("RGBA", (end[0] - start[0], end[1] - start[1]), (43, 127, 175, 30))
        hatch_ink = ImageDraw.Draw(hatch)
        for y in range(-hatch.width, hatch.height, 23):
            hatch_ink.line((0, y, hatch.width, y + hatch.width), fill=(17, 87, 130, 172), width=5)
        art.alpha_composite(hatch, start)

        def dashed(start, end):
            length = abs(end[0] - start[0]) + abs(end[1] - start[1])
            dx = (end[0] - start[0]) / length
            dy = (end[1] - start[1]) / length
            for p in range(0, length, 27):
                q = min(p + 15, length)
                ink.line([(round(start[0] + dx * p), round(start[1] + dy * p)),
                          (round(start[0] + dx * q), round(start[1] + dy * q))],
                         fill="#145d8d", width=7)

        boundary = [project(600, 0), project(WIDTH, 0), project(WIDTH, 600), project(600, 600)]
        for start, end in zip(boundary, boundary[1:] + boundary[:1], strict=True):
            dashed(start, end)

    return art


if __name__ == "__main__":
    draw_scene(packed=False).save(OUTPUT / "mixed-cartons-split-art.png")
    draw_scene(packed=True).save(OUTPUT / "mixed-cartons-clear-art.png")
