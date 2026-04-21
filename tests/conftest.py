import os
import sys
import tempfile
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


TEST_DB_PATH = Path(tempfile.gettempdir()) / f"ai_issue_dashboard_test_{os.getpid()}_{uuid.uuid4().hex}.db"
os.environ["APP_DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
