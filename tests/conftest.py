import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


TEST_DB_PATH = Path(tempfile.gettempdir()) / "ai_issue_dashboard_test.db"
os.environ["APP_DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"


def pytest_sessionstart(session) -> None:  # type: ignore[no-untyped-def]
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


def pytest_sessionfinish(session, exitstatus) -> None:  # type: ignore[no-untyped-def]
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
