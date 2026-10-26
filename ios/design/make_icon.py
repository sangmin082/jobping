"""앱 아이콘 원본. `python3 make_icon.py` → AppIcon.svg.

PNG(1024, 알파 없음)는 SVG 를 브라우저로 렌더해서 만든다 — Assets.xcassets/AppIcon.appiconset/icon-1024.png.
남색 그라데이션 + 흰 서류가방 + 민트 "핑"(새 공고 알림). 링·이음선은 마스크로 뚫어서 배경이 비친다.
"""
import math
def arc(cx, cy, r, a0, a1):
    p = lambda a: (cx + r*math.cos(math.radians(a)), cy + r*math.sin(math.radians(a)))
    (x0,y0),(x1,y1) = p(a0), p(a1)
    return f"M{x0:.1f},{y0:.1f} A{r},{r} 0 0 1 {x1:.1f},{y1:.1f}"
bg1, bg2, glyph, mint = "#111D47", "#26338A", "#FFFFFF", "#3DF5A2"
bw, bh = 540, 370
bx, by = 486 - bw//2, 432
hw, hh = 216, 140
hx, hy = 486 - hw//2, by - 104
cx, cy, r = 738, 366, 82
waves = "".join(
    f'<path d="{arc(cx, cy, rr, -80, 8)}" fill="none" stroke="{mint}" stroke-width="28" stroke-linecap="round" opacity="{op}"/>'
    for rr, op in ((148, .95), (204, .5)))
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
<defs>
<linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{bg1}"/><stop offset="1" stop-color="{bg2}"/></linearGradient>
<mask id="cut" maskUnits="userSpaceOnUse" x="0" y="0" width="1024" height="1024">
  <rect width="1024" height="1024" fill="#fff"/>
  <circle cx="{cx}" cy="{cy}" r="{r+26}" fill="#000"/>
  <rect x="{bx}" y="{by+156}" width="{bw}" height="20" fill="#000"/>
  <rect x="{486-57}" y="{by+121}" width="114" height="90" rx="28" fill="#000"/>
</mask>
</defs>
<rect width="1024" height="1024" fill="url(#g)"/>
<g mask="url(#cut)" fill="{glyph}">
  <rect x="{hx}" y="{hy}" width="{hw}" height="{hh}" rx="44" fill="none" stroke="{glyph}" stroke-width="44"/>
  <rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="78"/>
</g>
<rect x="{486-39}" y="{by+139}" width="78" height="54" rx="14" fill="{glyph}"/>
{waves}
<circle cx="{cx}" cy="{cy}" r="{r}" fill="{mint}"/>
</svg>'''
open("AppIcon.svg","w").write(svg)
