"""compare.py OURS.png THEIRS.jpg OUT.jpg [label_ours] [label_theirs]
Side-by-side of our style frame and the benchmark's best frame, plus 3x crops of matching regions."""
import sys
from PIL import Image, ImageDraw, ImageFont

F_B = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


def main(ours, theirs, out, lo='Awakening II', lt='The Moss Keeper (best frame)'):
    a = Image.open(ours).convert('RGB').resize((1920, 1040))
    b = Image.open(theirs).convert('RGB').resize((1920, 1040))
    W = 960
    sheet = Image.new('RGB', (2 * W + 30, 520 + 60 + 2 * 330 + 40), (14, 14, 16))
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(F_B, 24)
    sheet.paste(b.resize((W, 520)), (10, 50)); sheet.paste(a.resize((W, 520)), (W + 20, 50))
    d.text((14, 14), lt, fill=(220, 220, 220), font=f)
    d.text((W + 24, 14), lo, fill=(255, 210, 120), font=f)
    # detail crops: centre and lower third, at 1:1
    crops = [(760, 260, 1240, 590), (300, 600, 780, 930)]
    y = 590
    for (x0, y0, x1, y1) in crops:
        cb = b.crop((x0, y0, x1, y1)).resize((W // 2 * 2 // 2 * 1, 330))
        ca = a.crop((x0, y0, x1, y1)).resize((W // 2 * 2 // 2 * 1, 330))
        sheet.paste(cb.resize((W, 330)), (10, y)); sheet.paste(ca.resize((W, 330)), (W + 20, y))
        y += 340
    sheet.save(out, quality=90)
    print('wrote', out)


if __name__ == '__main__':
    main(*sys.argv[1:])
