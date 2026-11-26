"""YouTube Dub Pack Builder: generates complete multi-language audio and subtitle package."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from upsc_studio.core.hardware import find_ffmpeg
from upsc_studio.languages.registry import LanguageRegistry
from upsc_studio.languages.subtitles import AudioAwareSubtitleSynchronizer
from upsc_studio.languages.translation import MultilingualTranslationEngine, ScriptSegment
from upsc_studio.tts.multilingual_engine import MultilingualTTSEngine


class YouTubeDubPackBuilder:
    """Assembles YouTube-compliant multilingual dubbing pack containing WAV, MP3, SRT, VTT, and metadata."""

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.pack_dir = project_dir / "publishing" / "youtube_dub_pack"
        self.pack_dir.mkdir(parents=True, exist_ok=True)
        self.registry = LanguageRegistry()
        self.trans_engine = MultilingualTranslationEngine(project_dir)
        self.tts_engine = MultilingualTTSEngine(project_dir)
        self.sub_sync = AudioAwareSubtitleSynchronizer(project_dir)

    def build_dub_pack(
        self,
        chapter_title: str,
        canonical_script_segments: list[dict[str, Any]],
        target_languages: list[str],
        primary_video_path: Path | None = None,
    ) -> dict[str, Any]:
        """Generate translated tracks, subtitles, audio-only exports (WAV & MP3) and metadata for each language."""
        ffmpeg_exe = find_ffmpeg()
        created_languages: list[str] = []
        lang_reports: dict[str, Any] = {}

        manifest: dict[str, Any] = {
            "chapter_title": chapter_title,
            "target_languages": target_languages,
            "primary_video_path": str(primary_video_path) if primary_video_path else None,
            "languages": {},
        }

        # Step 1: Write README_UPLOAD_STEPS.md in the dub pack root
        readme_content = [
            "# YouTube Multilingual Audio & Dubbing Instructions",
            "",
            "## How to attach dub tracks in YouTube Studio:",
            "1. Sign in to YouTube Studio (https://studio.youtube.com).",
            "2. From the left menu, select **Content** and click the uploaded video.",
            "3. Select **Subtitles** / **Languages** from the left menu.",
            "4. Click **ADD LANGUAGE** and select your target language.",
            "5. Under **Audio**, click **ADD** and select the language's `audio_track.mp3` or `audio_track.wav`.",
            "6. Under **Subtitles**, click **ADD** and upload `subtitles.srt` or `subtitles.vtt` with timing.",
            "7. Paste the localized title and description from `metadata.json`.",
            "8. Click **PUBLISH** to activate the multi-language audio track.",
            "",
            "> **Note:** Multi-language audio requires Advanced features enabled on your YouTube channel.",
        ]
        (self.pack_dir / "README_UPLOAD_STEPS.md").write_text("\n".join(readme_content), encoding="utf-8")

        # Step 2: Process each language
        for lang in target_languages:
            lp = self.registry.get(lang)
            if not lp:
                continue

            lang_folder = self.pack_dir / lang
            lang_folder.mkdir(parents=True, exist_ok=True)

            # Localize Title and Description
            localized_title = self.trans_engine.translate_text(chapter_title, "en", lang)
            meta_json = {
                "language_code": lang,
                "youtube_bcp47": lp.youtube_code,
                "language_name": lp.name,
                "native_name": lp.native_name,
                "localized_title": localized_title,
                "localized_description": (
                    f"UPSC Studio Educational Documentary — {localized_title}.\n\n"
                    f"Language: {lp.name} ({lp.native_name}).\n"
                    "Comprehensive General Studies preparation, evidence-backed claims, and visual explanations."
                ),
                "tags": ["UPSC", "Civil Services", chapter_title, lp.name],
            }
            (lang_folder / "metadata.json").write_text(json.dumps(meta_json, indent=2, ensure_ascii=False), encoding="utf-8")

            # Extract full text for this language
            lang_sentences: list[str] = []
            for seg in canonical_script_segments:
                raw_text = seg.get("narration", "")
                t_text = self.trans_engine.translate_text(raw_text, "en", lang)
                lang_sentences.append(t_text)

            full_script_text = " ".join(lang_sentences)
            (lang_folder / "translated_script.md").write_text(
                f"# Localized Script — {lp.name} ({lp.native_name})\n\n{full_script_text}\n",
                encoding="utf-8",
            )

            # Synthesize Audio Track (WAV)
            audio_wav = lang_folder / "audio_track.wav"
            tts_res = self.tts_engine.synthesize_speech(
                text=full_script_text,
                lang_code=lang,
                output_wav=audio_wav,
            )

            # Export MP3 if FFmpeg is available
            audio_mp3 = lang_folder / "audio_track.mp3"
            if ffmpeg_exe and audio_wav.exists():
                subprocess.run(
                    [ffmpeg_exe, "-y", "-i", str(audio_wav), "-vn", "-b:a", "192k", str(audio_mp3)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            # Synchronize Subtitles (SRT & VTT)
            sub_res = self.sub_sync.generate_subtitles(
                sentences=lang_sentences,
                total_audio_sec=tts_res["duration_sec"],
                out_srt=lang_folder / "subtitles.srt",
                out_vtt=lang_folder / "subtitles.vtt",
                lang_code=lang,
            )

            # Translation and Terminology QA Report
            qa_res = self.trans_engine.audit_translation(
                source_text=" ".join(s.get("narration", "") for s in canonical_script_segments),
                translated_text=full_script_text,
                target_lang=lang,
            )

            report = {
                "language": lang,
                "status": "READY_FOR_STUDIO_ATTACHMENT",
                "tts": tts_res,
                "subtitles": sub_res,
                "translation_qa": qa_res.model_dump(),
                "files": {
                    "wav": str(audio_wav),
                    "mp3": str(audio_mp3) if audio_mp3.exists() else None,
                    "srt": str(lang_folder / "subtitles.srt"),
                    "vtt": str(lang_folder / "subtitles.vtt"),
                    "metadata": str(lang_folder / "metadata.json"),
                },
            }
            (lang_folder / "qa_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

            manifest["languages"][lang] = report
            created_languages.append(lang)
            lang_reports[lang] = report

        (self.pack_dir / "video_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        return {
            "pack_dir": str(self.pack_dir),
            "languages_count": len(created_languages),
            "languages": created_languages,
            "manifest": manifest,
        }
