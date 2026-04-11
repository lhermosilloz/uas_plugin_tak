"""Generate the ATAK-PX4 Relay app icon (app_icon.ico)."""
from PIL import Image, ImageDraw, ImageFont
import os

SIZE = 256
img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Background: rounded dark blue square
pad = 10
draw.rounded_rectangle(
    [pad, pad, SIZE - pad, SIZE - pad],
    radius=40,
    fill=(25, 40, 72),
    outline=(70, 130, 220),
    width=4,
)

# Draw a simple drone silhouette (cross shape with circles at tips)
cx, cy = SIZE // 2, SIZE // 2 - 10
arm_len = 65
arm_w = 8
color_arm = (180, 200, 230)
color_rotor = (70, 160, 255)
color_body = (200, 220, 255)

# Arms (X shape)
for dx, dy in [(-1, -1), (1, -1), (-1, 1), (1, 1)]:
    x2 = cx + dx * arm_len
    y2 = cy + dy * arm_len
    draw.line([(cx, cy), (x2, y2)], fill=color_arm, width=arm_w)
    # Rotor circles
    draw.ellipse(
        [x2 - 22, y2 - 22, x2 + 22, y2 + 22],
        outline=color_rotor, width=3
    )

# Center body
draw.ellipse(
    [cx - 18, cy - 18, cx + 18, cy + 18],
    fill=color_body, outline=(70, 130, 220), width=3
)

# Signal waves (bottom right, representing relay/connection)
wave_cx, wave_cy = cx + 50, cy + 70
for r in [14, 26, 38]:
    draw.arc(
        [wave_cx - r, wave_cy - r, wave_cx + r, wave_cy + r],
        start=220, end=320,
        fill=(100, 220, 100), width=3
    )
draw.ellipse(
    [wave_cx - 4, wave_cy - 4, wave_cx + 4, wave_cy + 4],
    fill=(100, 220, 100)
)

# Save as .ico with multiple sizes
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app_icon.ico')
img.save(out, format='ICO', sizes=[(256, 256), (64, 64), (48, 48), (32, 32), (16, 16)])
print(f'Icon saved to {out}')
