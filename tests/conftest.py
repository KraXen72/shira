import shutil

import pytest
from test_harness import DOWNLOADS_DIR


@pytest.fixture(scope="session", autouse=True)
def clear_downloads():
	"""Clear the downloads directory once before the entire test session."""
	if DOWNLOADS_DIR.exists():
		shutil.rmtree(DOWNLOADS_DIR)
	DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)