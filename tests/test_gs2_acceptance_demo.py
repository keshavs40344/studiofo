"""Acceptance test: Complete GS-II demonstration chapter with animated process, map, chart, transitions, OTIO, and completeness audit."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from upsc_studio.audio.processor import VoiceAudioProcessor
from upsc_studio.core.hardware import detect_hardware
from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, RightsStatus, SceneSpec, VerificationStatus
from upsc_studio.graphics.rights import AssetRightsLedger
from upsc_studio.graphics.visual_systems import ExtendedVisualSystems
from upsc_studio.integrations.manim_worker import AnimationEngine
from upsc_studio.integrations.qgis_map import MapVisualEngine
from upsc_studio.integrations.registry import get_tool_registry
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.qa.auditor import QAAuditor
from upsc_studio.qa.completeness_audit import CompletenessAuditor, ElementCategory
from upsc_studio.research.verifier import EvidenceEngine
from upsc_studio.syllabus.engine import SyllabusEngine
from upsc_studio.teaching.engine import TeachingEngine
from upsc_studio.video.renderer import VideoRenderer


def _make_voice_wav(path: Path, duration_sec: float = 12.0) -> None:
    sr = 44100
    n = int(sr * duration_sec)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        buf = bytearray()
        for i in range(n):
            v = int(11000 * math.sin(2.0 * math.pi * 240.0 * (i / sr)))
            buf.extend(struct.pack("<h", v))
        wf.writeframes(bytes(buf))


def test_gs2_complete_demo_with_animation_map_chart_otio_and_audit(tmp_path: Path) -> None:
    conn = init_db(tmp_path / "demo.db")
    mgr = ProjectManager(conn, tmp_path / "projects")
    proj = mgr.create_project(
        ProjectCreate(
            name="GS2 Anti-Defection Demo",
            chapter_title="Anti-Defection Law and Tenth Schedule",
            exam_cycle="UPSC CSE 2026",
            cutoff_date="2026-11-26",
        )
    )
    proj_dir = Path(proj.root_dir)

    # Tool registry verification
    registry = get_tool_registry(tmp_path)
    assert any(t["name"] == "FFmpeg" and t["installed"] for t in registry)
    assert any(t["name"] == "OpenTimelineIO" and t["mode"] == "SCHEMA_INTEROP" for t in registry)

    # Syllabus & verified evidence
    syllabus = SyllabusEngine(conn)
    cmap = syllabus.map_chapter(
        proj.id,
        proj_dir,
        proj.chapter_title,
        notes_text="The Anti-Defection Law refers to the Tenth Schedule added by the 52nd Amendment Act 1985.",
    )
    ev = EvidenceEngine(conn, proj_dir)
    src_id = ev.add_source(
        proj.id,
        title="Constitution of India — Tenth Schedule",
        publisher="Ministry of Law and Justice",
        source_tier="PRIMARY_OFFICIAL",
        url="https://legislative.gov.in/",
        pub_date="1985-02-15",
    )
    clm_id = ev.add_claim(
        proj.id,
        "52nd Constitutional Amendment Act, 1985 inserted the Tenth Schedule.",
        "Constitutional Basis",
        status=VerificationStatus.VERIFIED,
        source_id=src_id,
        page_or_section="Tenth Schedule",
    )
    ev.export_ledger(proj.id, "2026-11-26")

    TeachingEngine(conn, proj_dir).generate_teaching_package(proj.id, proj.chapter_title, cmap)

    rights = AssetRightsLedger(conn, proj_dir)
    anim_engine = AnimationEngine(proj_dir, rights)
    map_engine = MapVisualEngine(proj_dir, rights)
    vis_engine = ExtendedVisualSystems(proj_dir, rights)

    # 1. Animated constitutional process (MP4)
    anim_res = anim_engine.render_process_animation(
        proj.id,
        "SCN_01",
        "Tenth Schedule Disqualification Process",
        [
            "Petition filed before Presiding Officer",
            "Notice & hearing under House Rules",
            "Speaker/Chairman decision (No fixed time limit)",
            "Judicial Review (Kihoto Hollohan, 1992)",
        ],
        source_citation="Constitution of India (Tenth Schedule); SC 1992",
        duration_sec=3.6,
    )
    anim_mp4 = Path(anim_res["output_mp4"])
    assert anim_mp4.exists()

    # 2. Institutional / Jurisdictional visual map (PNG)
    map_png = map_engine.render_institutional_map(
        proj.id,
        "SCN_02",
        "Constitutional Jurisdiction: Union & States",
        [
            ("Union Parliament", "Article 102(2) — LS & RS"),
            ("State Legislatures", "Article 191(2) — Vidhan Sabha"),
            ("Supreme Court", "Judicial Review (1992)"),
        ],
        source_label="Constitution of India",
        ref_date="2026-11-26",
    )
    assert map_png.exists()

    # 3. Source-cited data comparison chart (PNG)
    chart_png = vis_engine.render_bar_chart(
        proj.id,
        "SCN_03",
        "Key Constitutional Milestones (Illustrative Timeline Index)",
        [("52nd Amdt (1985)", 85.0), ("Kihoto Hollohan (1992)", 92.0), ("91st Amdt (2003)", 103.0)],
        unit="Year Index",
        source_label="Constitution of India & SC Records",
        ref_period="1985-2003",
    )
    assert chart_png.exists()

    # 4. Split-screen comparison (PNG)
    split_png = vis_engine.render_split_comparison(
        proj.id,
        "SCN_04",
        "Before vs After 91st Constitutional Amendment (2003)",
        "Before 2003 (1/3rd Split)",
        ["Allowed 1/3rd split exemption", "Encouraged group defections"],
        "After 2003 (2/3rd Merger Only)",
        ["Deleted 1/3rd split protection", "Only 2/3rd merger protected"],
        source_label="91st Amendment Act, 2003",
    )
    assert split_png.exists()

    scenes = [
        SceneSpec(
            scene_id="SCN_01",
            section_id="SEC_01",
            section_title="Disqualification Process",
            learning_objective="Explain step-by-step Tenth Schedule procedure.",
            narration_text="Tenth Schedule ke tahat Presiding Officer petition par decision lete hain.",
            claim_ids=[clm_id],
            estimated_duration_sec=3.5,
            visual_category="Animated Constitutional Process",
            primary_asset=str(anim_mp4),
            asset_rights_status=RightsStatus.ORIGINAL_GENERATED,
            on_screen_title="Tenth Schedule Process",
            transition_in="fade_in",
            transition_out="cross_dissolve",
            source_citations=["Constitution of India"],
        ),
        SceneSpec(
            scene_id="SCN_02",
            section_id="SEC_02",
            section_title="Institutional Jurisdiction",
            learning_objective="Show applicability to Parliament and State Legislatures.",
            narration_text="Yeh law Article 102(2) aur Article 191(2) dono par apply hota hai.",
            claim_ids=[clm_id],
            estimated_duration_sec=3.0,
            visual_category="Institutional Map",
            primary_asset=str(map_png),
            asset_rights_status=RightsStatus.ORIGINAL_GENERATED,
            on_screen_title="Union & State Jurisdiction",
            transition_in="cross_dissolve",
            transition_out="slide_left",
            source_citations=["Constitution of India"],
        ),
        SceneSpec(
            scene_id="SCN_03",
            section_id="SEC_03",
            section_title="Constitutional Evolution Data",
            learning_objective="Compare major milestones.",
            narration_text="1985 ke 52nd Amendment se lekar 2003 ke 91st Amendment tak key milestones dekhein.",
            claim_ids=[clm_id],
            estimated_duration_sec=3.0,
            visual_category="Data Visualisation",
            primary_asset=str(chart_png),
            asset_rights_status=RightsStatus.ORIGINAL_GENERATED,
            on_screen_title="Evolution Milestones",
            transition_in="slide_left",
            transition_out="cross_dissolve",
            source_citations=["Constitution of India"],
        ),
        SceneSpec(
            scene_id="SCN_04",
            section_id="SEC_04",
            section_title="91st Amendment Comparison",
            learning_objective="Contrast before and after 91st Amendment.",
            narration_text="91st Amendment ne 1/3rd split exemption khatam kar diya.",
            claim_ids=[clm_id],
            estimated_duration_sec=3.0,
            visual_category="Split-Screen Comparison",
            primary_asset=str(split_png),
            asset_rights_status=RightsStatus.ORIGINAL_GENERATED,
            on_screen_title="Before vs After 91st Amendment",
            transition_in="cross_dissolve",
            transition_out="dip_to_black",
            source_citations=["91st Amendment Act, 2003"],
        ),
    ]

    wav_path = tmp_path / "gs2_voice.wav"
    _make_voice_wav(wav_path, duration_sec=12.0)

    audio_proc = VoiceAudioProcessor(proj_dir, rights_ledger=rights)
    audio_rep = audio_proc.ingest_and_process(proj.id, wav_path)
    srt_path = audio_proc.generate_subtitles(scenes, total_audio_sec=audio_rep["duration_sec"])

    hw = detect_hardware(proj_dir)
    renderer = VideoRenderer(conn, proj_dir)
    manifest = renderer.render_project(
        project_id=proj.id,
        scenes=scenes,
        narration_wav=Path(audio_rep["processed_file"]),
        subtitles_srt=srt_path,
        preset=hw.recommended_preset,
        fps=hw.recommended_fps,
        resolution="1280x720",
        enable_transitions=True,
    )

    final_mp4 = Path(manifest["final_video"])
    assert final_mp4.exists() and final_mp4.stat().st_size > 20000
    assert Path(manifest["otio_timeline"]).exists()
    assert Path(manifest["chapters_ffmeta"]).exists()

    qa = QAAuditor(conn, proj_dir).run_all_checks(proj.id, human_approved_by="Creator")
    assert qa["academic"]["status"] == "PASSED"
    assert qa["rights"]["status"] == "PASSED"
    assert qa["media"]["status"] == "PASSED"
    assert qa["publication"]["status"] == "PASSED"

    comp = CompletenessAuditor(proj_dir).audit_video(scenes, final_mp4, is_csat_chapter=False)
    assert comp["scenes_audited"] == 4
    assert comp["black_frame_segments_detected"] == 0
    assert comp["element_matrix"]["animated_constitutional_or_process_visual"] == ElementCategory.OPTIONAL_AND_USED.value
    assert comp["element_matrix"]["institutional_or_geographical_map"] == ElementCategory.OPTIONAL_AND_USED.value
    assert comp["element_matrix"]["source_cited_data_chart"] == ElementCategory.OPTIONAL_AND_USED.value
    assert comp["element_matrix"]["otio_interchange_timeline"] == ElementCategory.OPTIONAL_AND_USED.value
    assert comp["element_matrix"]["csat_problem_solving_animation"] == ElementCategory.NOT_APPLICABLE.value
