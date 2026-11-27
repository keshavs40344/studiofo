from pathlib import Path

from upsc_studio.publishing.youtube_publisher import YouTubePublisher


def test_upload_is_blocked_without_per_run_user_approval(tmp_path):
    video = tmp_path / "final.mp4"
    result = YouTubePublisher(token_path=tmp_path / "missing-token.json").upload_video(
        video, {"video_title": "Test"}, qa_passed=True
    )
    assert result["status"] == "BLOCKED_AWAITING_EXPLICIT_USER_APPROVAL"
    assert result["upload_attempted"] is False


def test_public_upload_remains_blocked_even_with_approval(tmp_path):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"placeholder")
    publisher = YouTubePublisher(token_path=tmp_path / "missing-token.json")
    try:
        publisher.upload_video(
            video, {"video_title": "Test"}, qa_passed=True,
            privacy_status="public", user_approved=True,
        )
    except PermissionError as exc:
        assert "Public upload blocked" in str(exc)
    else:
        raise AssertionError("Public upload must remain blocked")


def test_private_upload_without_oauth_stays_pending_after_approval(tmp_path):
    video = tmp_path / "final.mp4"
    video.write_bytes(b"placeholder")
    result = YouTubePublisher(token_path=tmp_path / "missing-token.json").upload_video(
        video, {"video_title": "Test"}, qa_passed=True,
        privacy_status="private", user_approved=True,
    )
    assert result["status"] == "PENDING_OAUTH_CONNECTION"
