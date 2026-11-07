"""Rebuild the original geometric shield/eye icon using existing Pillow only."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def build():
    size = 1024
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    navy = '#203B60'
    # A simple code-native mark, rendered large and reduced for smooth edges.
    shield = [(512, 60), (900, 205), (870, 580), (790, 740),
              (680, 860), (512, 970), (344, 860), (234, 740), (154, 580), (124, 205)]
    draw.polygon(shield, fill=navy)
    eye = []
    for direction in (1, -1):
        for step in range(101):
            t = step / 100 if direction == 1 else 1 - step / 100
            x = 250 + 524 * t
            y = 475 - direction * 145 * (4 * t * (1 - t))
            eye.append((x, y))
    draw.polygon(eye, fill='white')
    draw.ellipse((414, 377, 610, 573), fill=navy)
    draw.ellipse((476, 397, 517, 438), fill='white')
    assets = ROOT / 'assets'
    assets.mkdir(exist_ok=True)
    image.resize((256, 256), Image.Resampling.LANCZOS).save(assets / 'exam_review.png')
    image.save(assets / 'exam_review.ico', sizes=[(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)])


if __name__ == '__main__':
    build()
