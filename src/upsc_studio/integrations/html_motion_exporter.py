"""HTML5/CSS3 motion-graphics scene exporter (HyperFrames / headless-browser compatible)."""

from __future__ import annotations

import html
from pathlib import Path

from upsc_studio.db.schemas import SceneSpec


class HTMLMotionSceneExporter:
    """Exports self-contained animated HTML/CSS kinetic-typography scenes with lower thirds."""

    def export_scene_html(self, out_dir: Path, chapter_title: str, scene: SceneSpec) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        bullets_html = "\n".join(
            f'<li style="animation-delay:{0.25 * (i + 1):.2f}s">{html.escape(b)}</li>'
            for i, b in enumerate(scene.on_screen_bullets[:4])
        )
        doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>{html.escape(scene.scene_id)} — {html.escape(scene.section_title)}</title>
  <style>
    body {{ margin:0; width:1920px; height:1080px; background:#0f172a; color:#f8fafc; font-family:Segoe UI, sans-serif; overflow:hidden; }}
    .bar {{ height:10px; background:#f59e0b; width:100%; }}
    .wrap {{ padding:72px 96px; }}
    .tag {{ color:#f59e0b; font-size:24px; font-weight:700; letter-spacing:1px; }}
    h1 {{ font-size:54px; margin:16px 0 36px; animation: fadeSlide 0.6s ease-out forwards; }}
    ul {{ list-style:none; padding:0; margin:0; }}
    li {{ background:#1e293b; border-left:5px solid #38bdf8; padding:24px 32px; margin-bottom:20px; font-size:32px; border-radius:8px; opacity:0; animation: fadeSlide 0.5s ease-out forwards; }}
    .lower-third {{ position:absolute; bottom:48px; left:96px; right:96px; display:flex; justify-content:space-between; color:#94a3b8; font-size:22px; border-top:1px solid #334155; padding-top:16px; }}
    @keyframes fadeSlide {{ from {{ opacity:0; transform:translateY(18px); }} to {{ opacity:1; transform:translateY(0); }} }}
  </style>
</head>
<body>
  <div class="bar"></div>
  <div class="wrap">
    <div class="tag">UPSC STUDIO &bull; {html.escape(chapter_title.upper())} &bull; {html.escape(scene.visual_category.upper())}</div>
    <h1>{html.escape(scene.on_screen_title)}</h1>
    <ul>{bullets_html}</ul>
  </div>
  <div class="lower-third">
    <span>Sources: {html.escape(', '.join(scene.source_citations))}</span>
    <span>{html.escape(scene.scene_id)}</span>
  </div>
</body>
</html>"""
        out_path = out_dir / f"{scene.scene_id}_motion.html"
        out_path.write_text(doc, encoding="utf-8")
        return out_path
