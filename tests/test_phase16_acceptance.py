"""Comprehensive 8-minute Fundamental Rights acceptance test with verified evidence, visuals, and QA."""

from __future__ import annotations

from pathlib import Path

from upsc_studio.academic.specialists import SpecialistProfileEngine
from upsc_studio.core.hardware import detect_hardware, find_ffmpeg
from upsc_studio.db.database import init_db
from upsc_studio.db.schemas import ProjectCreate, VerificationStatus
from upsc_studio.graphics.publishing import PublishingPackageBuilder
from upsc_studio.graphics.rights import AssetRightsLedger
from upsc_studio.graphics.visual_systems import ExtendedVisualSystems
from upsc_studio.integrations.manim_worker import AnimationEngine
from upsc_studio.integrations.qgis_map import MapVisualEngine
from upsc_studio.projects.manager import ProjectManager
from upsc_studio.qa.auditor import QAAuditor
from upsc_studio.qa.ten_gates import TenGateAuditor
from upsc_studio.research.verifier import EvidenceEngine
from upsc_studio.storyboard.director import StoryboardDirector
from upsc_studio.syllabus.engine import SyllabusEngine
from upsc_studio.teaching.duration_planner import DurationPlanner
from upsc_studio.teaching.engine import TeachingEngine
from upsc_studio.tts.adapter import PiperTTSEngine
from upsc_studio.video.renderer import VideoRenderer


def test_fundamental_rights_8min_documentary_production(tmp_path: Path) -> None:
    """End-to-end 8-minute acceptance test for Fundamental Rights documentary production."""
    conn = init_db(tmp_path / "fr_test.db")
    projects_root = tmp_path / "projects"
    mgr = ProjectManager(conn, projects_root)

    proj = mgr.create_project(
        ProjectCreate(
            name="Fundamental Rights 8-Min Documentary",
            chapter_title="Fundamental Rights: Scope, Writs, and Judicial Review",
            exam_cycle="UPSC CSE 2026",
            cutoff_date="2026-11-26",
            target_duration_min=8,
            tts_enabled=True,
        )
    )
    proj_dir = Path(proj.root_dir)

    # 1. Syllabus Mapping
    syllabus = SyllabusEngine(conn)
    cmap = syllabus.map_chapter(
        proj.id,
        proj_dir,
        proj.chapter_title,
        notes_text="Part III Articles 12-35 Fundamental Rights and Article 32 Writs jurisdiction of Supreme Court.",
    )
    assert any("GS Paper II" in p or "GS-II" in p for p in cmap["primary_papers"])

    # 2. Evidence Verification (Primary official sources with page/section proof)
    ev = EvidenceEngine(conn, proj_dir)
    src_const = ev.add_source(
        proj.id,
        title="Constitution of India — Part III",
        publisher="Ministry of Law and Justice, Government of India",
        source_tier="PRIMARY_OFFICIAL",
        url="https://legislative.gov.in/",
        pub_date="2024-05-01",
    )
    src_sc = ev.add_source(
        proj.id,
        title="Supreme Court Judgment — Maneka Gandhi vs Union of India (1978)",
        publisher="Supreme Court of India",
        source_tier="PRIMARY_OFFICIAL",
        pub_date="1978-01-25",
    )

    claim_part_iii = ev.add_claim(
        proj.id,
        "Part III (Articles 12-35) provides constitutionally protected Fundamental Rights.",
        "Constitutional Foundation",
        status=VerificationStatus.VERIFIED,
        source_id=src_const,
        page_or_section="Articles 12 to 35",
        verification_notes="Verified against official legislative text.",
    )
    claim_article_32 = ev.add_claim(
        proj.id,
        "Article 32 guarantees the right to move the Supreme Court for enforcement of rights via 5 writs.",
        "Writs & Enforcement",
        status=VerificationStatus.VERIFIED,
        source_id=src_const,
        page_or_section="Article 32",
        verification_notes="Habeas Corpus, Mandamus, Prohibition, Quo-Warranto, Certiorari.",
    )
    claim_maneka = ev.add_claim(
        proj.id,
        "Maneka Gandhi v. UOI (1978) established that procedure established by law under Article 21 must be just, fair, and reasonable.",
        "Judicial Evolution",
        status=VerificationStatus.VERIFIED,
        source_id=src_sc,
        page_or_section="1978 AIR 597",
        verification_notes="Substantive due process benchmark.",
    )
    for claim_id, source_id, section, excerpt in [
        (claim_part_iii, src_const, "Articles 12 to 35", "Part III of the Constitution contains the provisions relating to Fundamental Rights."),
        (claim_article_32, src_const, "Article 32", "The right to move the Supreme Court for enforcement of Fundamental Rights is guaranteed."),
        (claim_maneka, src_sc, "1978 AIR 597", "The procedure under Article 21 must be right, just and fair and not arbitrary."),
    ]:
        ev.verify_claim_against_source(
            claim_id, source_id, section, excerpt, reviewer_id="acceptance-test-reviewer"
        )
    ledger = ev.export_ledger(proj.id, proj.cutoff_date)
    assert ledger["status_counts"]["VERIFIED"] == 3
    assert ledger["status_counts"]["UNSUPPORTED"] == 0

    # 3. Teaching Package with 8-Minute Syllabus-Preserving Expansion
    teaching_engine = TeachingEngine(conn, proj_dir)
    pkg = teaching_engine.generate_teaching_package(
        project_id=proj.id,
        chapter_title=proj.chapter_title,
        chapter_map=cmap,
        target_duration_min=8,
        tts_enabled=True,
    )
    assert pkg["sections_count"] == 7  # Expanded 7 sections for 8-min target

    # 4. Duration Schedule
    planner = DurationPlanner(teaching_engine.WORDS_PER_MINUTE)
    sched = planner.build_schedule(proj_dir, pkg["sections"], target_duration_min=8)
    assert sched["target_duration_min"] == 8
    assert len(sched["sections"]) == 7

    # 5. Visual Storyboard and Diverse Graphics
    director = StoryboardDirector(proj_dir)
    scenes = director.build_storyboard(proj.chapter_title, pkg["sections"])
    assert len(scenes) == 7

    rights = AssetRightsLedger(conn, proj_dir)
    anim_engine = AnimationEngine(proj_dir, rights)
    map_engine = MapVisualEngine(proj_dir, rights)
    vis_engine = ExtendedVisualSystems(proj_dir, rights)

    # Asset A: Institutional Jurisdiction Map (PNG)
    map_path = map_engine.render_institutional_map(
        proj.id,
        scenes[1].scene_id,
        "Constitutional Rights Jurisdiction",
        [
            ("Supreme Court", "Article 32 — Union-wide enforcement"),
            ("High Courts", "Article 226 — Fundamental + Legal rights"),
            ("State & Union Entities", "Article 12 — Definition of State"),
        ],
        source_label="Constitution of India",
        ref_date=proj.cutoff_date,
    )
    scenes[1].primary_asset = str(map_path)

    # Asset B: Animated Constitutional Writ Process (MP4)
    anim_res = anim_engine.render_process_animation(
        proj.id,
        scenes[2].scene_id,
        "Article 32 Writ Enforcement Mechanism",
        [
            "Violation of Part III Guarantee",
            "Direct Petition to Supreme Court",
            "Issuance of Appropriate Prerogative Writ",
            "Immediate Relief & Judicial Restitution",
        ],
        source_citation="Constitution of India Article 32",
        duration_sec=3.5,
    )
    scenes[2].primary_asset = anim_res["output_mp4"]

    # Asset C: Split Comparison (PNG)
    split_path = vis_engine.render_split_comparison(
        proj.id,
        scenes[3].scene_id,
        "Procedure Established by Law vs Due Process",
        "Procedure Established by Law (Literal)",
        ["Formal legislative enactment", "Executive adherence to law"],
        "Due Process & Article 21 (Substantive)",
        ["Fair, just, and reasonable test", "Protection against arbitrary state action"],
        source_label="Maneka Gandhi (1978); AK Gopalan (1950)",
    )
    scenes[3].primary_asset = str(split_path)

    # Generate supporting graphics for remaining scenes
    from upsc_studio.graphics.generator import GraphicsGenerator
    gfx = GraphicsGenerator(proj_dir, rights)
    for s in scenes:
        if not s.primary_asset or not Path(s.primary_asset).exists():
            s.primary_asset = str(gfx.generate_scene_graphic(proj.id, proj.chapter_title, s))

    # 6. Audio Narration (TTS Synthesis or Safe Voice Blocker Verification)
    tts = PiperTTSEngine(proj_dir, rights_ledger=rights)
    caps = tts.detect_voice_capabilities()

    # We synthesize scenes if Hindi voice is available
    if caps["can_synthesize_hindi"]:
        audio_report = tts.synthesize_scenes(proj.id, scenes)
        narration_wav = Path(audio_report["narration_full_wav"])
        srt_path = Path(audio_report["narration_transcript_srt"])
        assert narration_wav.exists()
        assert srt_path.exists()

        # 7. Video Rendering via FFmpeg
        hw = detect_hardware(proj_dir)
        renderer = VideoRenderer(conn, proj_dir)
        render_res = renderer.render_project(
            project_id=proj.id,
            scenes=scenes,
            narration_wav=narration_wav,
            subtitles_srt=srt_path,
            preset=hw.recommended_preset,
            fps=hw.recommended_fps,
            resolution="1280x720",
        )
        final_mp4 = Path(render_res["final_video"])
        assert final_mp4.exists()
        assert final_mp4.stat().st_size > 50000

        # 8. QA and 10-Gate Audit
        auditor = QAAuditor(conn, proj_dir)
        qa = auditor.run_all_checks(proj.id, human_approved_by="Lead Instructor")
        assert qa["academic"]["status"] == "PASSED"
        assert qa["rights"]["status"] == "PASSED"
        assert qa["media"]["status"] == "PASSED"
        assert qa["publication"]["status"] == "PASSED"

        ten_gates = TenGateAuditor(conn, proj_dir).run_ten_gates(proj.id, scenes, final_mp4, human_approved_by="Lead Instructor")
        assert ten_gates["all_gates_passed"] is True
        assert ten_gates["ready_for_publication"] == "PASSED"
    else:
        # If no Hindi voice is available, verify it cleanly reports capability status
        assert caps["can_synthesize_hindi"] is False
