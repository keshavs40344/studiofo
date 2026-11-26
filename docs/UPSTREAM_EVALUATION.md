# Upstream Repository Evaluation & Compatibility Report

**Evaluation Date:** 2026-11-26  
**Target Hardware:** Windows, 11th Gen Intel Core i5-1135G7 (4C/8T), 15.69 GB RAM, Intel Iris Xe Graphics (no dedicated GPU), Python 3.14.6.

| Repository | Version | License | Py 3.14 / Win | GPU Required? | Decision | Integration Strategy |
|---|---|---|---|---|---|---|
| `ManimCommunity/manim` | `v0.22.1` | `MIT` | `>=3.11` (check C-deps) | No (CPU OK) | **ADOPT (Subprocess)** | Isolated `.venv_manim` worker for constitutional/economic/flowchart animations + Pillow fallback |
| `FFmpeg/FFmpeg` | `7.1` (`imageio-ffmpeg`) | `LGPL/GPL` | Verified installed | No (CPU `libx264`) | **ADOPT (Core)** | Scene assembly, `xfade` transitions, `loudnorm` audio mixing, `blackdetect` QC |
| `qgis/QGIS` | `final-3_44_16` | `GPL-2.0` | Not installed | No | **OPTIONAL ADAPTER** | Invoke `qgis_process` if installed; fallback to verified GeoJSON/Pillow thematic maps |
| `m-bain/whisperX` | `v3.8.6` | `BSD-2-Clause` | **Incompatible** (`<3.14`) | Recommended (PyTorch) | **REJECTED for Py 3.14** | Use `faster-whisper` (`MIT`, `>=3.9`, CPU INT8) as optional worker + script-aligned SRT fallback |
| `Breakthrough/PySceneDetect` | `v0.7.3` | `BSD-3-Clause` | `>=3.10`, pure wheel | No | **ADOPT (Optional)** | Scene-cut & media inspection + FFmpeg `blackdetect` fallback |
| `ASWF/OpenTimelineIO` | `v0.18.1` | `Apache-2.0` | **No `cp314` wheel** | No | **SCHEMA INTEROP** | Pure-Python OTIO `Timeline.1` JSON exporter (no C++ wheel needed) |
| `Comfy-Org/ComfyUI` | `v0.46.0` | `GPL-3.0` + model licences | Python | **Yes (CUDA VRAM)** | **DEFERRED** | Optional remote-only hook; unsuitable for Iris Xe 16 GB laptop |
| `remotion-dev/remotion` | `v4.0.547` | **Commercial / Source-avail.** | Node.js + Chromium | No (RAM heavy) | **NOT ADOPTED** | Avoids commercial licence & Chromium overhead; Manim (MIT) + FFmpeg cover animations |
