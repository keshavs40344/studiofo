"""Translation provider, target voice model and dashboard language-output tests."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from upsc_studio.db.schemas import SceneSpec
from upsc_studio.tts.adapter import PiperTTSEngine
import upsc_studio.web.app as web_module
from upsc_studio.web.app import create_app


class FakeTranslateSession:
    def __init__(self):
        self.get_calls = 0
        self.post_calls = 0
        self.headers = {}

    def get(self, url, timeout=None):
        self.get_calls += 1
        class Response:
            def raise_for_status(self): pass
            def json(self):
                return [{"code": "en"}, {"code": "ta"}, {"code": "hi"}]
        return Response()

    def post(self, url, data=None, timeout=None):
        self.post_calls += 1
        class Response:
            def raise_for_status(self): pass
            def json(self):
                return {"translatedText": f"translated:{data['q']}"}
        return Response()


def test_translation_checks_capabilities_once_and_preserves_segment_order(tmp_path: Path) -> None:
    from upsc_studio.i18n.translation import TranslationService

    session = FakeTranslateSession()
    service = TranslationService(session=session)
    result = service.translate_segments(["First factual line.", "Second factual line."], "ta")
    assert result["provider"] == "LIBRETRANSLATE"
    assert result["translated_texts"] == [
        "translated:First factual line.",
        "translated:Second factual line.",
    ]
    assert result["human_language_review_required"] is True
    assert session.get_calls == 1
    assert session.post_calls == 2


def test_piper_model_inventory_requires_explicit_commercial_license_metadata(tmp_path: Path) -> None:
    model_dir = tmp_path / "piper"
    model_dir.mkdir()
    model = model_dir / "ta_IN-test-medium.onnx"
    model.write_bytes(b"model-fixture")
    Path(str(model) + ".json").write_text("{}", encoding="utf-8")
    (model_dir / "voice_licenses.json").write_text(
        json.dumps({
            model.name: {
                "license": "CC-BY-4.0",
                "attribution": "Voice model author",
                "commercial_use": True,
                "confirmed_by": "Reviewer",
            }
        }),
        encoding="utf-8",
    )

    engine = PiperTTSEngine(tmp_path)
    engine.model_path = model
    inventory = engine.discover_piper_models()
    assert len(inventory) == 1
    assert inventory[0]["language_code"] == "ta"
    assert inventory[0]["usable_for_dubbing"] is True

    (model_dir / "voice_licenses.json").write_text("{}", encoding="utf-8")
    unlicensed_engine = PiperTTSEngine(tmp_path)
    unlicensed_engine.model_path = model
    assert unlicensed_engine.discover_piper_models()[0]["usable_for_dubbing"] is False


def test_dashboard_translation_produces_script_and_subtitles_when_voice_model_is_absent(
    tmp_path: Path, monkeypatch
) -> None:
    class FakeTranslation:
        def translate_segments(self, texts, target_language):
            return {
                "target_language": target_language,
                "target_language_label": "Tamil",
                "provider": "TEST_TRANSLATOR",
                "segment_count": len(texts),
                "translated_texts": [f"TAMIL {item}" for item in texts],
                "machine_translation": True,
                "human_language_review_required": True,
                "quality_status": "NOT_HUMAN_REVIEWED",
            }

        def write_translated_script(self, project_dir, chapter_title, scenes, translated, language, provider):
            output = project_dir / "teaching" / "translations" / language / "translated_script.md"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("\n".join(translated), encoding="utf-8")
            return output

    class FakeTTS:
        def __init__(self, project_dir, rights_ledger=None): pass
        def discover_piper_models(self): return []

    monkeypatch.setattr(web_module, "TranslationService", FakeTranslation)
    monkeypatch.setattr(web_module, "PiperTTSEngine", FakeTTS)

    app = create_app(
        db_path=tmp_path / "dub.db",
        projects_root=tmp_path / "dub_projects",
    )
    client = TestClient(app)
    created = client.post(
        "/api/projects",
        json={"name": "Tamil dub", "chapter_title": "Federalism"},
    )
    project_id = created.json()["id"]
    project_root = next((tmp_path / "dub_projects").iterdir())
    storyboard = project_root / "storyboard" / "storyboard.json"
    storyboard.parent.mkdir(parents=True, exist_ok=True)
    scene = SceneSpec(
        scene_id="SCN_01",
        section_id="SEC_01",
        section_title="Introduction",
        learning_objective="Introduce the topic",
        narration_text="Federalism distributes constitutional powers.",
        claim_ids=["clm_verified"],
        estimated_duration_sec=6.0,
        visual_category="Title card",
        primary_asset="unused.png",
        on_screen_title="Federalism",
    )
    storyboard.write_text(json.dumps([scene.model_dump(mode="json")]), encoding="utf-8")

    response = client.post(
        f"/api/projects/{project_id}/dub",
        json={"target_language": "ta"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "TRANSLATION_READY_VOICE_MODEL_REQUIRED"
    assert Path(data["translated_script"]).is_file()
    assert Path(data["translated_subtitles"]).is_file()
    assert data["dubbed_audio"] is None
