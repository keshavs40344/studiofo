# Phase 14 — Open-Source GitHub Ecosystem Discovery & Prioritised Shortlist (24 Candidates)

**Audit Date:** 2026-11-26  
**Target Environment:** Windows, `11th Gen Intel(R) Core(TM) i5-1135G7`, `15.69 GB RAM`, `Intel(R) Iris(R) Xe Graphics` (no dedicated GPU), `Python 3.14.6`, `Node v24.18.0`, Free-First Budget.

**Compatibility Classes:**  
`A` = Directly compatible | `B` = Compatible via isolated worker | `C` = Requires another Python/Node runtime | `D` = Requires dedicated GPU | `E` = Too resource-intensive | `F` = Licence incompatible/review | `G` = Not suitable

| # | Repository | Stars | Licence | Pushed | Class | Recommendation | UPSC Studio Use Case & Notes |
|---|---|---|---|---|---|---|---|
| 1 | `https://github.com/ffmpeg/FFmpeg` | 68,255 | LGPL/GPL | 2026-11-26 | **A** | **Integrate (Core)** | Scene assembly, `xfade`, `loudnorm`, `blackdetect`. Bundled via `imageio-ffmpeg` 7.1. |
| 2 | `https://github.com/altair-viz/altair` | 10,522 | BSD-3-Clause | 2026-11-17 | **A** | **Integrate (Core)** | Already installed (`6.2.2`); generates Vega-Lite JSON + interactive HTML data charts. |
| 3 | `https://github.com/ManimCommunity/manim` | 42,934 | MIT | 2026-11-26 | **B** | **Optional Adapter** | Constitutional/economic 2D vector animations in isolated `.venv_manim` + Pillow/FFmpeg fallback. |
| 4 | `https://github.com/heygen-com/hyperframes` | 90,581 | Apache-2.0 | 2026-11-26 | **C** | **Optional Adapter** | HTML/CSS-to-video motion graphics (`Node v24.18.0` installed); exporter generates compatible HTML5 scenes. |
| 5 | `https://github.com/motion-canvas/motion-canvas` | 20,264 | MIT | 2026-07-02 | **C** | **Reference / Optional** | TypeScript procedural 2D animation & kinetic typography. |
| 6 | `https://github.com/docling-project/docling` | 71,100 | MIT | 2026-11-26 | **B** | **Optional Adapter** | Complex PDF table/layout extraction in isolated worker; `pypdf` fallback active. |
| 7 | `https://github.com/SYSTRAN/faster-whisper` | 27,035 | MIT | 2026-11-25 | **B** | **Optional Adapter** | CPU INT8 speech transcription (`>=3.9`, pure wheel); script-aligned SRT fallback active. |
| 8 | `https://github.com/ggerganov/whisper.cpp` | 55,546 | MIT | 2026-11-26 | **B** | **Optional Adapter** | Zero-Python C++ local ASR for Hinglish/English voice alignment. |
| 9 | `https://github.com/Breakthrough/PySceneDetect` | 5,663 | BSD-3-Clause | 2026-11-25 | **B** | **Optional Adapter** | Shot/cut detection; FFmpeg `blackdetect` handles continuity QA. |
| 10 | `https://github.com/AcademySoftwareFoundation/OpenTimelineIO` | 2,120 | Apache-2.0 | 2026-11-25 | **A (Schema)** | **Integrate (Schema)** | No `cp314` wheel; pure-Python `Timeline.1` `.otio` exporter integrated. |
| 11 | `https://github.com/Zulko/moviepy` | 15,213 | MIT | 2026-08-26 | **A** | **Reference Only** | FFmpeg subprocesses are faster and lower-RAM on 16 GB Windows than MoviePy frame buffers. |
| 12 | `https://github.com/maplibre/maplibre-gl-js` | 12,184 | BSD-3-Clause | 2026-11-26 | **C** | **Reference / Future** | Vector tile animated maps in Node/Browser; requires tile server/offline MBTiles. |
| 13 | `https://github.com/geopandas/geopandas` | 5,313 | BSD-3-Clause | 2026-11-23 | **B** | **Optional Adapter** | Shapefile/GeoJSON thematic mapping when GDAL/Fiona wheels are installed. |
| 14 | `https://github.com/qgis/QGIS` | 14,892 | GPL-2.0 | 2026-11-26 | **B** | **Optional Adapter** | `qgis_process` CLI adapter + Pillow/vector institutional map fallback. |
| 15 | `https://github.com/matplotlib/matplotlib` | 23,506 | PSF-based | 2026-11-26 | **A** | **Optional Adapter** | Static publication charts; Pillow + Altair already cover charts cleanly. |
| 16 | `https://github.com/PaddlePaddle/PaddleOCR` | 93,303 | Apache-2.0 | 2026-09-16 | **B / E** | **Optional Adapter** | Heavy model footprint (~1 GB+); use only in isolated OCR worker for Hindi/English scans. |
| 17 | `https://github.com/VikParuchuri/marker` | 41,085 | Apache-2.0 | 2026-11-20 | **D / E** | **Reject (Local)** | PyTorch PDF-to-Markdown; heavy RAM/GPU footprint for 16 GB laptop. |
| 18 | `https://github.com/blender/blender` | 22,577 | GPL-2.0+ | 2026-11-26 | **B / E** | **Optional Adapter** | Selective 3D terrain/architecture only if user installs Blender externally. |
| 19 | `https://github.com/KDE/kdenlive` | 6,191 | GPL-3.0 | 2026-11-26 | **B** | **Optional Manual NLE** | Manual finishing of `.otio`/MP4 exports if user installs Kdenlive. |
| 20 | `https://github.com/mltframework/shotcut` | 15,799 | GPL-3.0 | 2026-11-26 | **B** | **Reference Only** | Alternative open-source NLE; Kdenlive + OTIO preferred. |
| 21 | `https://github.com/audacity/audacity` | 19,188 | GPL-2.0/3.0 | 2026-11-26 | **B** | **Optional Manual Audio** | Manual voice inspection; FFmpeg `loudnorm` handles automated cleanup. |
| 22 | `https://github.com/opentoonz/opentoonz` | 8,379 | BSD-3-Clause | 2026-11-26 | **E** | **Reject** | GUI cel-animation suite; not suited for automated script-to-video pipelines. |
| 23 | `https://github.com/NatronGitHub/Natron` | 5,775 | GPL-2.0 | 2026-11-26 | **E** | **Reject** | Node-based VFX compositor; heavy and redundant with FFmpeg/Manim. |
| 24 | `https://github.com/remotion-dev/remotion` | 75,884 | Commercial | 2026-11-26 | **F** | **Reject** | Commercial/source-available licence restrictions + Chromium RAM overhead. |
