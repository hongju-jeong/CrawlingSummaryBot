from backend.app.api.routes.crawl import stop_latest_sources
from backend.app.services.runtime.crawl_control import registry


def test_stop_latest_sources_returns_false_when_idle():
    registry.finish(registry.current().run_id) if registry.current() else None
    response = stop_latest_sources()
    assert response["stopped"] is False


def test_stop_latest_sources_returns_true_when_active():
    run = registry.start()
    assert run is not None
    response = stop_latest_sources()
    assert response["stopped"] is True
    registry.finish(run.run_id)
