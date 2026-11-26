"""Section-wise own-voice recording, retake management, script pace comparison, and stitching."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from upsc_studio.audio.processor import VoiceAudioProcessor
from upsc_studio.core.hardware import find_ffmpeg


class SectionVoiceManager:
    """Manages section-wise user recordings, retakes, missing-section detection, and assembly."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.sections_raw_dir = project_dir / "audio" / "raw" / "sections"
        self.sections_proc_dir = project_dir / "audio" / "processed" / "sections"
        self.sections_raw_dir.mkdir(parents=True, exist_ok=True)
        self.sections_proc_dir.mkdir(parents=True, exist_ok=True)
        self.processor = VoiceAudioProcessor(project_dir)

    def submit_section_audio(self, section_id: str, audio_path: Path) -> Path:
        """Store or retake a single section's raw recording without altering other sections."""
        if not audio_path.exists():
            raise FileNotFoundError(f"Section audio not found: {audio_path}")
        dest = self.sections_raw_dir / f"{section_id}{audio_path.suffix.lower()}"
        shutil.copy2(audio_path, dest)
        return dest

    def audit_and_stitch(self, project_id: str, sections: list[dict], words_per_minute: float = 130.0) -> dict:
        """Check for missing sections, compare pace vs script, and stitch complete narration."""
        ffmpeg_exe = find_ffmpeg()
        if not ffmpeg_exe:
            raise RuntimeError("FFmpeg required for section audio processing.")

        missing: list[str] = []
        section_reports: list[dict] = []
        clean_files: list[Path] = []

        for sec in sections:
            sid = sec["section_id"]
            matches = list(self.sections_raw_dir.glob(f"{sid}.*"))
            if not matches:
                missing.append(sid)
                section_reports.append({"section_id": sid, "status": "MISSING", "retake_needed": True})
                continue

            raw_file = matches[0]
            clean_sec = self.sections_proc_dir / f"{sid}_clean.wav"
            subprocess.run(
                [
                    ffmpeg_exe,
                    "-y",
                    "-i",
                    str(raw_file),
                    "-af",
                    "highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-ar",
                    "44100",
                    "-ac",
                    "1",
                    str(clean_sec),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            metrics = self.processor._measure_audio(ffmpeg_exe, clean_sec)
            word_count = len(sec["narration"].split())
            expected_sec = max(2.0, (word_count / words_per_minute) * 60.0)
            ratio = metrics["duration_sec"] / expected_sec if expected_sec else 1.0
            pace_ok = 0.2 <= ratio <= 3.0  # Flag extreme omissions or dead air

            section_reports.append(
                {
                    "section_id": sid,
                    "status": "OK" if (metrics["intelligible_level"] and not metrics["clipping_detected"]) else "NEEDS_RETAKE",
                    "duration_sec": metrics["duration_sec"],
                    "expected_script_sec": round(expected_sec, 2),
                    "pace_ratio": round(ratio, 2),
                    "pace_ok": pace_ok,
                    "clipping_detected": metrics["clipping_detected"],
                    "intelligible_level": metrics["intelligible_level"],
                }
            )
            clean_files.append(clean_sec)

        stitched_wav: Path | None = None
        if not missing and clean_files:
            concat_txt = self.sections_proc_dir / "sections_concat.txt"
            concat_txt.write_text(
                "\n".join(f"file '{p.resolve().as_posix()}'" for p in clean_files), encoding="utf-8"
            )
            stitched_wav = self.project_dir / "audio" / "processed" / "narration_clean.wav"
            subprocess.run(
                [ffmpeg_exe, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(stitched_wav)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )

        report = {
            "project_id": project_id,
            "tts_used": False,
            "missing_sections": missing,
            "all_sections_present": len(missing) == 0,
            "stitched_narration": str(stitched_wav) if stitched_wav else None,
            "sections": section_reports,
        }
        (self.project_dir / "audio" / "processed" / "section_voice_report.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        return report
