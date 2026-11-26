"""Tool version, licence, and hardware compatibility registry."""

from __future__ import annotations

import shutil
from pathlib import Path

from upsc_studio.core.hardware import find_ffmpeg


def get_tool_registry(project_root: Path | None = None) -> list[dict]:
    """Return actual availability, licence, and integration mode for each upstream tool."""
    ffmpeg_exe = find_ffmpeg()
    manim_venv = (project_root / ".venv_manim" / "Scripts" / "python.exe") if project_root else None
    has_manim = bool(manim_venv and manim_venv.exists()) or bool(shutil.which("manim"))
    has_qgis = bool(shutil.which("qgis_process") or shutil.which("qgis"))
    has_scenedetect = bool(shutil.which("scenedetect"))

    return [
        {
            "name": "FFmpeg",
            "repo": "https://github.com/FFmpeg/FFmpeg",
            "license": "LGPL-2.1+ / GPL-2.0+",
            "installed": ffmpeg_exe is not None,
            "path": ffmpeg_exe,
            "mode": "CORE_ACTIVE",
            "notes": "Bundled 7.1-essentials via imageio-ffmpeg; CPU libx264 + xfade + loudnorm + blackdetect.",
        },
        {
            "name": "ManimCommunity/manim",
            "repo": "https://github.com/ManimCommunity/manim",
            "license": "MIT",
            "installed": has_manim,
            "path": str(manim_venv) if (manim_venv and manim_venv.exists()) else shutil.which("manim"),
            "mode": "SUBPROCESS_WITH_FALLBACK",
            "notes": "Uses isolated .venv_manim if present; falls back to Pillow + FFmpeg progressive animation.",
        },
        {
            "name": "QGIS",
            "repo": "https://github.com/qgis/QGIS",
            "license": "GPL-2.0",
            "installed": has_qgis,
            "path": shutil.which("qgis_process") or shutil.which("qgis"),
            "mode": "OPTIONAL_WITH_FALLBACK",
            "notes": "Invokes qgis_process if installed; falls back to verified Pillow/vector thematic & institutional maps.",
        },
        {
            "name": "Blender",
            "repo": "https://github.com/blender/blender",
            "license": "GPL-2.0+",
            "installed": bool(shutil.which("blender")),
            "path": shutil.which("blender"),
            "mode": "OPTIONAL_3D_ADAPTER",
            "notes": "Selective 3D rendering only when installed and hardware permits.",
        },
        {
            "name": "Audacity",
            "repo": "https://github.com/audacity/audacity",
            "license": "GPL-2.0 / GPL-3.0",
            "installed": bool(shutil.which("audacity")),
            "path": shutil.which("audacity"),
            "mode": "OPTIONAL_MANUAL_AUDIO",
            "notes": "Optional manual voice inspection; FFmpeg loudnorm handles automated cleanup.",
        },
        {
            "name": "whisper.cpp",
            "repo": "https://github.com/ggerganov/whisper.cpp",
            "license": "MIT",
            "installed": bool(shutil.which("whisper-cli") or shutil.which("main")),
            "path": shutil.which("whisper-cli") or shutil.which("main"),
            "mode": "OPTIONAL_LOCAL_ASR",
            "notes": "Local C++ Whisper option; script-aligned SRT fallback active when absent.",
        },
        {
            "name": "WhisperX / faster-whisper",
            "repo": "https://github.com/m-bain/whisperX",
            "license": "BSD-2-Clause (whisperX) / MIT (faster-whisper)",
            "installed": False,
            "path": None,
            "mode": "FALLBACK_SCRIPT_ALIGNMENT",
            "notes": "whisperX requires Python <3.14 and PyTorch/GPU; script-aligned SRT fallback active on Python 3.14.",
        },
        {
            "name": "PySceneDetect",
            "repo": "https://github.com/Breakthrough/PySceneDetect",
            "license": "BSD-3-Clause",
            "installed": has_scenedetect,
            "path": shutil.which("scenedetect"),
            "mode": "OPTIONAL_WITH_FFMPEG_FALLBACK",
            "notes": "Uses FFmpeg blackdetect/freezedetect for automated media QA when scenedetect CLI is absent.",
        },
        {
            "name": "OpenTimelineIO",
            "repo": "https://github.com/AcademySoftwareFoundation/OpenTimelineIO",
            "license": "Apache-2.0",
            "installed": True,
            "path": "pure-python-schema-exporter",
            "mode": "SCHEMA_INTEROP",
            "notes": "No cp314 C++ wheel on PyPI; exports valid OTIO Timeline.1 JSON natively.",
        },
        {
            "name": "ComfyUI",
            "repo": "https://github.com/Comfy-Org/ComfyUI",
            "license": "GPL-3.0 (models vary)",
            "installed": False,
            "path": None,
            "mode": "DEFERRED",
            "notes": "Requires dedicated CUDA VRAM; unsuitable for local Intel Iris Xe 16 GB laptop.",
        },
        {
            "name": "Remotion",
            "repo": "https://github.com/remotion-dev/remotion",
            "license": "Commercial / Source-Available",
            "installed": False,
            "path": None,
            "mode": "NOT_ADOPTED",
            "notes": "Commercial licensing restrictions and headless Chromium RAM overhead.",
        },
    ]
