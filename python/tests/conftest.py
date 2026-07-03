from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "spec" / "examples"


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES_DIR


def example_files():
    return sorted(EXAMPLES_DIR.glob("*.mtph"))
