# Dependency & Licence Register — UPSC Studio

| Component | Source / Package | Licence | Status on This Machine | Notes |
|---|---|---|---|---|
| Python Runtime | Python 3.14.6 | PSF | Installed | Core runtime |
| FastAPI / Uvicorn / Pydantic | PyPI | MIT | Installed | Local desktop web UI & schemas |
| Pillow | PyPI | HPND / MIT-CMU | Installed | 1080p slides, maps, charts, thumbnails |
| pypdf / python-docx / openpyxl / python-pptx | PyPI | BSD / MIT | Installed | Multi-format document ingestion |
| FFmpeg | `imageio-ffmpeg` (`7.1-essentials`) | LGPL-2.1+ / GPL-2.0+ | Installed | Core video/audio processing & `blackdetect` |
| Manim Community | `ManimCommunity/manim` | MIT | Optional (Fallback active) | Subprocess worker if `.venv_manim` exists |
| Blender | `blender.org` | GPL-2.0+ | Not installed | Optional selective 3D adapter |
| QGIS | `qgis/QGIS` | GPL-2.0 | Not installed | Optional GIS adapter; Pillow/vector fallback active |
| Audacity | `audacityteam.org` | GPL-2.0 / GPL-3.0 | Not installed | Optional manual audio inspection |
| whisper.cpp | `ggerganov/whisper.cpp` | MIT | Not installed | Optional local CPU transcription |
| PySceneDetect | `Breakthrough/PySceneDetect` | BSD-3-Clause | Not installed | FFmpeg `blackdetect` fallback active |
| OpenTimelineIO | `ASWF/OpenTimelineIO` | Apache-2.0 | Schema Interop | Pure-Python `Timeline.1` `.otio` exporter |
| ComfyUI | `Comfy-Org/ComfyUI` | GPL-3.0 | Deferred | Requires dedicated CUDA VRAM |
| Remotion | `remotion-dev/remotion` | Commercial / Source-avail. | Not adopted | Commercial licence & Chromium overhead |
