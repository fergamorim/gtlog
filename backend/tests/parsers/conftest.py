from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name: str) -> list[str]:
    return (FIXTURES / name).read_text(encoding="utf-8").splitlines()


@pytest.fixture
def fixture_lines():
    return read_fixture
