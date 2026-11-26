"""Own-voice audio inspection, conservative FFmpeg cleanup, and SRT subtitle alignment."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import wave
from pathlib import Path

from upsc_studio.core.hardware import find_ffmpeg
from upsc_studio.db.schemas import RightsStatus, SceneSpec
from upsc_studio.graphics.rights import AssetRightsLedger


class VoiceAudioProcessor:
    """Processes user's own voice recording conservatively without AI replacement."""

    def __init__(self, project_dir: Path, rights_ledger: AssetRightsLedger | None = None) -> None:
        self.project_dir = project_dir
        self.raw_dir = project_dir / "audio" / "raw"
        self.proc_dir = project_dir / "audio" / "processed"
        self.sub_dir = project_dir / "subtitles"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.proc_dir.mkdir(parents=True, exist_ok=True)
        self.sub_dir.mkdir(parents=True, exist_ok=True)
        self.rights_ledger = rights_ledger

    def ingest_and_process(self, project_id: str, voice_path: Path) -> dict:
        """Preserve raw voice, measure loudness/clipping, and produce cleaned WAV."""
        if not voice_path.exists():
            raise FileNotFoundError(f"Voice recording not found: {voice_path}")

        raw_copy = self.raw_dir / voice_path.name
        if voice_path.resolve() != raw_copy.resolve():
            shutil.copy2(voice_path, raw_copy)

        if self.rights_ledger is not None:
            self.rights_ledger.register_asset(
                project_id=project_id,
                asset_type="user_voice_narration",
                file_path=raw_copy,
                creator="Project User",
                licence="USER_OWNED",
                rights_status=RightsStatus.USER_OWNED,
                attribution="User's own recorded narration",
            )

        ffmpeg_exe = find_ffmpeg()
        if not ffmpeg_exe:
            raise RuntimeError("FFmpeg not found. Cannot process audio.")

        clean_wav = self.proc_dir / "narration_clean.wav"
        cmd = [
            ffmpeg_exe,
            "-y",
            "-i",
            str(raw_copy),
            "-af",
            "highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11",
            "-ar",
            "44100",
            "-ac",
            "1",
            str(clean_wav),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)

        metrics = self._measure_audio(ffmpeg_exe, clean_wav)
        report = {
            "raw_file": str(raw_copy),
            "processed_file": str(clean_wav),
            "tts_used": False,
            "voice_cloning_used": False,
            **metrics,
        }
        (self.proc_dir / "audio_qa.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    @staticmethod
    def _measure_audio(ffmpeg_exe: str, wav_path: Path) -> dict:
        """Measure actual duration, mean volume, max peak, and clipping."""
        duration_sec = 0.0
        with wave.open(str(wav_path), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            channels = wf.getnchannels()
            duration_sec = round(frames / float(rate), 3) if rate else 0.0

        proc = subprocess.run(
            [ffmpeg_exe, "-i", str(wav_path), "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True,
            text=True,
        )
        stderr = proc.stderr or ""
        mean_match = re.search(r"mean_volume:\s*([-\d.]+)\s*dB", stderr)
        max_match = re.search(r"max_volume:\s*([-\d.]+)\s*dB", stderr)
        mean_db = float(mean_match.group(1)) if mean_match else -99.0
        max_db = float(max_match.group(1)) if max_match else -99.0

        return {
            "duration_sec": duration_sec,
            "sample_rate": rate,
            "channels": channels,
            "mean_volume_db": mean_db,
            "max_volume_db": max_db,
            "clipping_detected": max_db >= -0.1,
            "intelligible_level": mean_db > -45.0,
        }

    def generate_subtitles(self, scenes: list[SceneSpec], total_audio_sec: float | None = None) -> Path:
        """Align scene narration text to timed SRT subtitles and transcript.json."""
        est_total = sum(s.estimated_duration_sec for s in scenes) or 1.0
        scale = (total_audio_sec / est_total) if (total_audio_sec and total_audio_sec > 0) else 1.0

        srt_blocks: list[str] = []
        transcript_segments: list[dict] = []
        cursor = 0.0
        sub_idx = 1

        for scene in scenes:
            scene_dur = max(1.0, scene.estimated_duration_sec * scale)
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", scene.narration_text) if s.strip()]
            if not sentences:
                sentences = [scene.on_screen_title]
            total_chars = sum(len(s) for s in sentences) or 1

            for sent in sentences:
                seg_dur = max(0.8, scene_dur * (len(sent) / total_chars))
                start = cursor
                end = cursor + seg_dur
                cursor = end
                srt_blocks.append(
                    f"{sub_idx}\n{self._fmt_srt_time(start)} --> {self._fmt_srt_time(end)}\n{sent}\n"
                )
                transcript_segments.append(
                    {
                        "index": sub_idx,
                        "scene_id": scene.scene_id,
                        "start_sec": round(start, 3),
                        "end_sec": round(end, 3),
                        "text": sent,
                    }
                )
                sub_idx += 1

        srt_path = self.sub_dir / "subtitles.srt"
        srt_path.write_text("\n".join(srt_blocks), encoding="utf-8")
        (self.sub_dir / "transcript.json").write_text(
            json.dumps(transcript_segments, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return srt_path

    @staticmethod
    def compare_transcript_to_script(script_text: str, transcript_text: str) -> dict:
        """Compare spoken transcript against approved script to detect missing or extra sentences."""
        script_sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script_text) if len(s.strip()) >= 8]
        trans_sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", transcript_text) if len(s.strip()) >= 8]

        def _norm(s: str) -> set[str]:
            return set(re.findall(r"[a-zA-Z0-9\u0900-\u097F]+", s.lower()))

        missing: list[str] = []
        for s in script_sents:
            s_toks = _norm(s)
            if not s_toks:
                continue
            best = max((len(s_toks & _norm(t)) / len(s_toks) for t in trans_sents), default=0.0)
            if best < 0.5:
                missing.append(s)

        extra: list[str] = []
        for t in trans_sents:
            t_toks = _norm(t)
            if not t_toks:
                continue
            best = max((len(t_toks & _norm(s)) / len(t_toks) for s in script_sents), default=0.0)
            if best < 0.5:
                extra.append(t)

        return {
            "script_sentences": len(script_sents),
            "transcript_sentences": len(trans_sents),
            "missing_sentences": missing,
            "extra_sentences": extra,
            "requires_retake_or_review": bool(missing or extra),
        }

    @staticmethod
    def _fmt_srt_time(seconds: float) -> str:
        ms_total = int(round(seconds * 1000))
        hrs, rem = divmod(ms_total, 3600000)
        mins, rem = divmod(rem, 60000)
        secs, ms = divmod(rem, 1000)
        return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"
