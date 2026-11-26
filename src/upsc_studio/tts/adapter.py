"""Provider-independent TTS adapter: Piper (MIT, CPU ONNX) with Windows SAPI fallback."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from upsc_studio.audio.processor import VoiceAudioProcessor
from upsc_studio.core.hardware import find_ffmpeg
from upsc_studio.core.paths import PROJECT_ROOT
from upsc_studio.db.schemas import RightsStatus, SceneSpec
from upsc_studio.graphics.rights import AssetRightsLedger
from upsc_studio.tts.pronunciation import PronunciationNormalizer


class PiperTTSEngine:
    """Synthesizes Hindi/Hinglish narration segments via isolated .venv_tts Piper or SAPI fallback."""

    def __init__(self, project_dir: Path, rights_ledger: AssetRightsLedger | None = None) -> None:
        self.project_dir = project_dir
        self.tts_python = PROJECT_ROOT / ".venv_tts" / "Scripts" / "python.exe"
        self.model_path = PROJECT_ROOT / "data" / "tts_models" / "piper" / "hi_IN-pratham-medium.onnx"
        self.seg_dir = project_dir / "audio" / "narration_segments"
        self.proc_dir = project_dir / "audio" / "processed"
        self.sub_dir = project_dir / "subtitles"
        self.seg_dir.mkdir(parents=True, exist_ok=True)
        self.proc_dir.mkdir(parents=True, exist_ok=True)
        self.sub_dir.mkdir(parents=True, exist_ok=True)
        self.rights_ledger = rights_ledger
        self.normalizer = PronunciationNormalizer()
        self.audio_proc = VoiceAudioProcessor(project_dir)

    def is_piper_available(self) -> bool:
        return self.tts_python.exists() and self.model_path.exists()

    def synthesize_scenes(self, project_id: str, scenes: list[SceneSpec]) -> dict:
        """Synthesize per-scene WAVs, stitch into narration_full.wav, and generate quality reports."""
        t0 = time.perf_counter()
        ffmpeg_exe = find_ffmpeg()
        if not ffmpeg_exe:
            raise RuntimeError("FFmpeg is required for TTS audio assembly.")

        use_piper = self.is_piper_available()
        engine_name = "piper_hi_IN-pratham-medium" if use_piper else "windows_sapi_fallback"
        model_license = "MIT (rhasspy/piper-voices hi_IN-pratham-medium)" if use_piper else "Windows Built-in SAPI"

        pron_reports: list[dict] = []
        raw_seg_wavs: list[Path] = []
        seg_durations: list[float] = []

        for scene in scenes:
            spoken_text, applied_terms = self.normalizer.normalize(scene.narration_text)
            pron_reports.append({"scene_id": scene.scene_id, "applied_terms": applied_terms})

            seg_wav = self.seg_dir / f"{scene.scene_id}.wav"
            if use_piper:
                try:
                    self._run_piper(spoken_text, seg_wav)
                except Exception:
                    engine_name = "windows_sapi_fallback"
                    self._run_sapi(scene.narration_text, seg_wav)
            else:
                self._run_sapi(scene.narration_text, seg_wav)

            metrics = self.audio_proc._measure_audio(ffmpeg_exe, seg_wav)
            seg_durations.append(metrics["duration_sec"])
            scene.estimated_duration_sec = max(2.0, round(metrics["duration_sec"] + 0.4, 2))
            raw_seg_wavs.append(seg_wav)

        # Concatenate segments and normalize loudness conservatively
        concat_txt = self.seg_dir / "tts_concat.txt"
        concat_txt.write_text(
            "\n".join(f"file '{p.resolve().as_posix()}'" for p in raw_seg_wavs), encoding="utf-8"
        )
        full_wav = self.proc_dir / "narration_full.wav"
        subprocess.run(
            [
                ffmpeg_exe,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_txt),
                "-af",
                "highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11",
                "-ar",
                "44100",
                "-ac",
                "1",
                str(full_wav),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Also copy to narration_clean.wav for VideoRenderer compatibility
        clean_wav = self.proc_dir / "narration_clean.wav"
        clean_wav.write_bytes(full_wav.read_bytes())

        full_metrics = self.audio_proc._measure_audio(ffmpeg_exe, full_wav)
        srt_path = self.audio_proc.generate_subtitles(scenes, total_audio_sec=full_metrics["duration_sec"])
        srt_copy = self.sub_dir / "narration_transcript.srt"
        srt_copy.write_text(srt_path.read_text(encoding="utf-8"), encoding="utf-8")

        pron_path = self.normalizer.save_report(self.proc_dir / "pronunciation_report.json", pron_reports)

        quality_report = {
            "project_id": project_id,
            "engine": engine_name,
            "model_license": model_license,
            "voice_cloning_used": False,
            "segments_count": len(raw_seg_wavs),
            "segment_durations_sec": seg_durations,
            "narration_full_wav": str(full_wav),
            "narration_transcript_srt": str(srt_copy),
            "pronunciation_report": str(pron_path),
            "synthesis_time_sec": round(time.perf_counter() - t0, 2),
            **full_metrics,
        }
        (self.proc_dir / "voice_quality_report.json").write_text(
            json.dumps(quality_report, indent=2), encoding="utf-8"
        )
        (self.proc_dir / "audio_qa.json").write_text(
            json.dumps(quality_report, indent=2), encoding="utf-8"
        )

        if self.rights_ledger is not None:
            self.rights_ledger.register_asset(
                project_id=project_id,
                asset_type="ai_tts_narration",
                file_path=full_wav,
                creator=engine_name,
                licence=model_license,
                rights_status=RightsStatus.LICENSED,
                attribution=f"Synthesized using {engine_name} ({model_license})",
            )

        return quality_report

    def _run_piper(self, text: str, out_wav: Path) -> None:
        script = (
            "import sys, wave; from piper.voice import PiperVoice; "
            "v = PiperVoice.load(sys.argv[1]); "
            "txt = sys.stdin.read(); "
            "with wave.open(sys.argv[2], 'wb') as wf: v.synthesize_wav(txt, wf)"
        )
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        subprocess.run(
            [str(self.tts_python), "-c", script, str(self.model_path), str(out_wav)],
            input=text,
            text=True,
            encoding="utf-8",
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=120,
        )

    @staticmethod
    def _run_sapi(text: str, out_wav: Path) -> None:
        ps = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.SetOutputToWaveFile('{str(out_wav)}'); "
            "$txt = [Console]::In.ReadToEnd(); "
            "$s.Speak($txt); $s.Dispose()"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            input=text,
            text=True,
            encoding="utf-8",
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=60,
        )
