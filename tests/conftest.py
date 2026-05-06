import os
import sys

# SlowAPI: avoid flaky tests from shared "testclient" IP bucket.
os.environ.setdefault("RATE_LIMIT_ENABLED", "0")

# Allow `import face_engine` etc. when running pytest from repo root.
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
