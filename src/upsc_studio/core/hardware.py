"""Hardware, OS, and external tool detection for CPU-safe defaults."""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import psutil


@dataclass(frozen=True)
class HardwareProfile:
    """Measured local hardware and software capabilities."""

    os_name: str
    os_version: str
    python_version: str
    cpu_model: str
    physical_cores: int
    logical_cores: int
    total_ram_gb: float
    available_ram_gb: float
    free_disk_gb: float
    gpu_name: str
    has_dedicated_gpu: bool
    ffmpeg_path: Optional[str]
    ffprobe_path: Optional[str]
    tesseract_path: Optional[str]
    inkscape_path: Optional[str]
    qgis_path: Optional[str]
    kdenlive_path: Optional[str]
    recommended_preset: str
    recommended_resolution: str
    recommended_fps: int
    max_concurrent_jobs: int

    def to_dict(self) -> dict:
        return asdict(self)


def find_ffmpeg() -> Optional[str]:
    """Locate ffmpeg on PATH or via bundled imageio-ffmpeg."""
    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).exists():
            return exe
    except Exception:
        pass
    return None


def _detect_windows_cpu_and_gpu() -> tuple[str, str]:
    """Query WMI/CIM on Windows for exact CPU and GPU names without guessing."""
    cpu_name = platform.processor() or "Unknown CPU"
    gpu_name = "Unknown GPU"
    if platform.system().lower() != "windows":
        return cpu_name, gpu_name
    try:
        ps_cmd = (
            "$c=(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name);"
            "$g=(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join '; ';"
            "Write-Output \"$c|||$g\""
        )
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        ).strip()
        if "|||" in out:
            c_part, g_part = out.split("|||", 1)
            if c_part.strip():
                cpu_name = c_part.strip()
            if g_part.strip():
                gpu_name = g_part.strip()
    except Exception:
        pass
    return cpu_name, gpu_name


def detect_hardware(workspace_path: Path | str = ".") -> HardwareProfile:
    """Measure actual CPU, RAM, GPU, disk space, and available media tools."""
    mem = psutil.virtual_memory()
    disk = shutil.disk_usage(str(workspace_path))
    cpu_model, gpu_name = _detect_windows_cpu_and_gpu()
    gpu_lower = gpu_name.lower()
    has_dedicated_gpu = any(
        vendor in gpu_lower for vendor in ("nvidia", "geforce", "rtx", "gtx", "radeon rx")
    )
    total_ram_gb = round(mem.total / (1024**3), 2)
    available_ram_gb = round(mem.available / (1024**3), 2)
    free_disk_gb = round(disk.free / (1024**3), 2)

    # Conservative CPU-safe defaults for 16 GB RAM / integrated GPU laptops
    max_jobs = 1 if (not has_dedicated_gpu or total_ram_gb <= 16.5) else 2
    preset = "medium" if has_dedicated_gpu else "veryfast"
    resolution = "1920x1080"
    fps = 30

    return HardwareProfile(
        os_name=platform.system(),
        os_version=platform.version(),
        python_version=platform.python_version(),
        cpu_model=cpu_model,
        physical_cores=psutil.cpu_count(logical=False) or 1,
        logical_cores=psutil.cpu_count(logical=True) or 1,
        total_ram_gb=total_ram_gb,
        available_ram_gb=available_ram_gb,
        free_disk_gb=free_disk_gb,
        gpu_name=gpu_name,
        has_dedicated_gpu=has_dedicated_gpu,
        ffmpeg_path=find_ffmpeg(),
        ffprobe_path=shutil.which("ffprobe"),
        tesseract_path=shutil.which("tesseract"),
        inkscape_path=shutil.which("inkscape"),
        qgis_path=shutil.which("qgis"),
        kdenlive_path=shutil.which("kdenlive"),
        recommended_preset=preset,
        recommended_resolution=resolution,
        recommended_fps=fps,
        max_concurrent_jobs=max_jobs,
    )


def check_disk_space_ok(path: Path | str, min_free_gb: float = 2.0) -> tuple[bool, float]:
    """Verify sufficient free disk space before starting a render."""
    free_gb = round(shutil.disk_usage(str(path)).free / (1024**3), 2)
    return free_gb >= min_free_gb, free_gb
