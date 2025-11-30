

from pathlib import Path

import pytest

from project.and_tree import AndTreeSearch
from project.parser import get_input_data

TEST_DIR = Path(__file__).parent
INPUTS_DIR = TEST_DIR / "inputs"

OUTPUTS_DIR = TEST_DIR / "expected_outputs"

input_files = sorted(INPUTS_DIR.glob("*.txt"))

@pytest.mark.parametrize("input_path", input_files, ids=lambda p: p.name)
def test_input_files(input_path: Path):
    expected_path = OUTPUTS_DIR / input_path.name
    assert expected_path.exists(), f"Expected output file not found: {expected_path}"

    input_data = get_input_data(input_path, "1", "1", "1", "1", "1", "1", "1", "1")
    search = AndTreeSearch(input_data)
    search.search()

    expected = expected_path.read_text()

    if "Eval-value" in expected:
        assert search.get_formatted_answer_with_eval() == expected
    else:
        assert search.get_formatted_answer() == expected