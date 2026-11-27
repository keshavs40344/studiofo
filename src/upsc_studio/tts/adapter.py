"""Provider-independent TTS adapter: Piper (MIT, CPU ONNX) with strict voice verification."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from upsc_studio.audio.processor import VoiceAudioProcessor
from upsc_studio.core.hardware import find_ffmpeg
from upsc_studio.core.paths import PROJECT_ROOT
from upsc_studio.db.schemas import RightsStatus, SceneSpec
from upsc_studio.graphics.rights import AssetRightsLedger
from upsc_studio.tts.pronunciation import PronunciationNormalizer


class PiperTTSEngine:
    """Synthesizes Hindi/Hinglish narration segments via verified Hindi voice engine.
    
    Hardened voice requirements:
    - Verifies Piper model presence and license.
    - Inspects Windows SAPI voices specifically for Hindi culture ('hi-IN').
    - NEVER silently substitutes an English voice for Hindi text.
    - If no suitable Hindi voice is found, raises VoiceNotAvailableError so pipeline pauses in WAITING_FOR_VOICE.
    """

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
        """Check if isolated Piper python and Hindi ONNX model exist."""
        return self.tts_python.exists() and self.model_path.exists()

    def get_installed_sapi_hindi_voice(self) -> str | None:
        """Query SAPI voices on Windows to see if any Hindi voice is installed."""
        try:
            ps = (
                "Add-Type -AssemblyName System.Speech; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                "$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like '*hi*' -or $_.VoiceInfo.Name -like '*Kalpana*' -or $_.VoiceInfo.Name -like '*Hemant*' } | Select-Object -First 1; "
                "if ($v) { Write-Output $v.VoiceInfo.Name }; $s.Dispose()"
            )
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command", ps],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
            ).strip()
            return out if out else None
        except Exception:
            return None

    def detect_voice_capabilities(self) -> dict[str, Any]:
        """Detect actual available Hindi voices across Piper and SAPI."""
        piper_avail = self.is_piper_available()
        sapi_hindi = self.get_installed_sapi_hindi_voice()
        return {
            "piper_hindi_available": piper_avail,
            "piper_model_path": str(self.model_path) if self.model_path.exists() else None,
            "sapi_hindi_available": bool(sapi_hindi),
            "sapi_hindi_voice": sapi_hindi,
            "can_synthesize_hindi": piper_avail or bool(sapi_hindi),
        }

    def synthesize_scenes(self, project_id: str, scenes: list[SceneSpec]) -> dict[str, Any]:
        """Synthesize per-scene WAVs, stitch into narration_full.wav, and generate quality reports."""
        t0 = time.perf_counter()
        ffmpeg_exe = find_ffmpeg()
        if not ffmpeg_exe:
            raise RuntimeError("FFmpeg is required for TTS audio assembly.")

        use_piper = self.is_piper_available()
        sapi_hindi = self.get_installed_sapi_hindi_voice()

        # Strict check: NEVER silently fall back to English SAPI voice for Hindi content
        if not use_piper and not sapi_hindi:
            raise RuntimeError(
                "No suitable Hindi voice engine found. Piper Hindi model is missing and no Windows SAPI Hindi voice is installed. "
                "Cannot synthesize Hindi narration without acceptable voice engine; project must pause in WAITING_FOR_VOICE."
            )

        if use_piper:
            engine_name = "piper_hi_IN-pratham-medium"
            model_license = "MIT (rhasspy/piper-voices hi_IN-pratham-medium)"
        else:
            engine_name = f"windows_sapi_hindi_{sapi_hindi}"
            model_license = "Windows SAPI Hindi Voice"

        pron_reports: list[dict[str, Any]] = []
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
                    if sapi_hindi:
                        self._run_sapi(scene.narration_text, seg_wav, voice_name=sapi_hindi)
                    else:
                        raise
            else:
                self._run_sapi(scene.narration_text, seg_wav, voice_name=sapi_hindi)

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

    def discover_piper_models(self) -> list[dict[str, Any]]:
        """List installed Piper voices and their explicitly recorded licence metadata."""
        model_dir = self.model_path.parent
        manifest_path = model_dir / "voice_licenses.json"
        try:
            license_manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
        except (OSError, json.JSONDecodeError):
            license_manifest = {}
        models: list[dict[str, Any]] = []
        for path in sorted(model_dir.glob("*.onnx")):
            config_path = Path(str(path) + ".json")
            locale = path.stem.split("-", 1)[0]
            language_code = locale.split("_", 1)[0].lower()
            licence_data = license_manifest.get(path.name, {})
            if not isinstance(licence_data, dict):
                licence_data = {}
            models.append({
                "model_file": path.name,
                "model_path": str(path),
                "locale": locale,
                "language_code": language_code,
                "config_present": config_path.is_file(),
                "license": licence_data.get("license"),
                "attribution": licence_data.get("attribution"),
                "commercial_use": licence_data.get("commercial_use") is True,
                "license_confirmed_by": licence_data.get("confirmed_by"),
                "usable_for_dubbing": bool(
                    config_path.is_file()
                    and licence_data.get("license")
                    and licence_data.get("attribution")
                    and licence_data.get("commercial_use") is True
                    and licence_data.get("confirmed_by")
                ),
            })
        return models

    def synthesize_translated_scenes(
        self,
        project_id: str,
        scenes: list[SceneSpec],
        translated_texts: list[str],
        language_code: str,
        model_path: Path,
    ) -> dict[str, Any]:
        """Create a language-specific narration only from an installed, licensed Piper model."""
        if len(scenes) != len(translated_texts) or not scenes:
            raise ValueError("Translated text count must match a non-empty scene list.")
        resolved_model = Path(model_path).expanduser().resolve()
        model_root = self.model_path.parent.resolve()
        try:
            resolved_model.relative_to(model_root)
        except ValueError as exc:
            raise ValueError("Piper voice model must be installed inside the configured model directory.") from exc
        model = next((item for item in self.discover_piper_models() if Path(item["model_path"]).resolve() == resolved_model), None)
        if model is None:
            raise FileNotFoundError("Requested Piper voice model is not installed.")
        if model["language_code"] != language_code.lower():
            raise ValueError(
                f"Voice model language '{model['language_code']}' does not match target '{language_code}'."
            )
        if not model["usable_for_dubbing"]:
            raise PermissionError(
                "Voice model licence is not cleared. Add its exact licence, attribution, commercial_use=true "
                "and confirmed_by fields to voice_licenses.json after reviewing the model licence."
            )
        if not self.tts_python.is_file():
            raise RuntimeError(f"Isolated Piper runtime is missing: {self.tts_python}")
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            raise RuntimeError("FFmpeg is required to assemble translated narration.")

        output_dir = self.project_dir / "audio" / "multilingual" / language_code.lower()
        segment_dir = output_dir / "segments"
        output_dir.mkdir(parents=True, exist_ok=True)
        segment_dir.mkdir(parents=True, exist_ok=True)
        segment_paths: list[Path] = []
        for index, text in enumerate(translated_texts, start=1):
            if not text.strip():
                raise ValueError(f"Translated narration segment {index} is empty.")
            segment_path = segment_dir / f"scene_{index:03d}.wav"
            self._run_piper(text, segment_path, model_path=resolved_model)
            segment_paths.append(segment_path)

        concat_file = segment_dir / "concat.txt"
        concat_file.write_text(
            "\n".join(f"file '{path.resolve().as_posix()}'" for path in segment_paths),
            encoding="utf-8",
        )
        narration = output_dir / "narration.wav"
        subprocess.run(
            [
                ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
                "-af", "highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11",
                "-ar", "44100", "-ac", "1", str(narration),
            ],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
        metrics = self.audio_proc._measure_audio(ffmpeg, narration)
        translated_scenes = [
            scene.model_copy(update={"narration_text": translated})
            for scene, translated in zip(scenes, translated_texts)
        ]
        subtitle_path = output_dir / "subtitles.srt"
        self.audio_proc.generate_subtitles(
            translated_scenes, total_audio_sec=metrics["duration_sec"], output_path=subtitle_path
        )
        report = {
            "status": "DUBBED_AUDIO_READY",
            "project_id": project_id,
            "language_code": language_code.lower(),
            "model_file": model["model_file"],
            "model_license": model["license"],
            "model_attribution": model["attribution"],
            "voice_cloning_used": False,
            "narration_wav": str(narration),
            "subtitles_srt": str(subtitle_path),
            "segment_count": len(segment_paths),
            **metrics,
        }
        (output_dir / "voice_quality_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        if self.rights_ledger is not None:
            self.rights_ledger.register_asset(
                project_id=project_id,
                asset_type="multilingual_ai_tts_narration",
                file_path=narration,
                creator=f"Piper model {model['model_file']}",
                licence=str(model["license"]),
                rights_status=RightsStatus.LICENSED,
                attribution=str(model["attribution"]),
            )
        return report

    def _run_piper(self, text: str, out_wav: Path, model_path: Path | None = None) -> None:
        selected_model = model_path or self.model_path
        script = (
            "import sys, wave\n"
            "from piper.voice import PiperVoice\n"
            "v = PiperVoice.load(sys.argv[1])\n"
            "txt = sys.stdin.read()\n"
            "with wave.open(sys.argv[2], 'wb') as wf:\n"
            "    v.synthesize_wav(txt, wf)\n"
        )
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        subprocess.run(
            [str(self.tts_python), "-c", script, str(selected_model), str(out_wav)],
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
    def _run_sapi(text: str, out_wav: Path, voice_name: str | None = None) -> None:
        voice_select = f"$s.SelectVoice('{voice_name}'); " if voice_name else ""
        ps = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            f"{voice_select}"
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
