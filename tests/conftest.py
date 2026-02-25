import shutil
import sys

import pytest
from test_harness import DOWNLOADS_DIR, _output_line_count


@pytest.fixture(scope="session", autouse=True)
def clear_downloads():
	"""Clear the downloads directory once before the entire test session."""
	if DOWNLOADS_DIR.exists():
		shutil.rmtree(DOWNLOADS_DIR)
	DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_logreport(report):
	"""Clear printed invoke output before pytest writes the PASSED/FAILED result."""
	if report.when == "call":
		n = _output_line_count[0]
		_output_line_count[0] = 0
		if n > 0:
			for _ in range(n):
				sys.stdout.write("\x1b[1A\x1b[2K")  # move up + clear line
			sys.stdout.flush()
