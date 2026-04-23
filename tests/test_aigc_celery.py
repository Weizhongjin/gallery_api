from unittest.mock import patch, MagicMock


def test_celery_aigc_generate_task_exists():
    from app.ai.tasks import celery_aigc_generate
    assert celery_aigc_generate is not None


def test_celery_aigc_generate_calls_run():
    from app.ai.tasks import celery_aigc_generate

    mock_db = MagicMock()

    with patch("app.ai.tasks.SessionLocal", return_value=mock_db), \
         patch("app.aigc.service.run_aigc_generation") as mock_run:
        celery_aigc_generate(task_id="00000000-0000-0000-0000-000000000001")
        mock_run.assert_called_once()
        mock_db.commit.assert_called()


def test_celery_aigc_generate_marks_failed_on_error():
    from app.ai.tasks import celery_aigc_generate

    mock_db = MagicMock()

    with patch("app.ai.tasks.SessionLocal", return_value=mock_db), \
         patch("app.aigc.service.run_aigc_generation", side_effect=RuntimeError("boom")), \
         patch("app.aigc.service.mark_aigc_task_failed") as mock_fail:
        try:
            celery_aigc_generate(task_id="00000000-0000-0000-0000-000000000001")
        except RuntimeError:
            pass
        mock_fail.assert_called_once()
