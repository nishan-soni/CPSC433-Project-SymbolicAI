

from pathlib import Path
from project.and_tree import AndTreeSearch
from project.parser import get_input_data

TEST_DIR = Path(__file__).parent
INPUTS_DIR = TEST_DIR / "inputs"

def test_section_penalty_simple():
    input_data = get_input_data(INPUTS_DIR / "test_sec_pen_simple.txt", "1", "1", "1", "1", "1", "1", "1", "1") 
    search = AndTreeSearch(input_data)
    search.search()
    
    assert search.get_formatted_answer() == sorted(["CPSC 231 LEC 01, MO, 8:00", "CPSC 231 LEC 02, TU, 10:00", "CPSC 231 LEC 01 TUT 01, TU, 10:00"])

def test_pref_penalty_simple():
    input_data = get_input_data(INPUTS_DIR / "test_pref_pen_simple.txt", "1", "1", "1", "1", "1", "1", "1", "1") 
    search = AndTreeSearch(input_data)
    search.search()
    
    assert search.get_formatted_answer() == sorted(["CPSC 231 LEC 02, TU, 13:00", "CPSC 231 LEC 01, MO, 8:00", "CPSC 231 LEC 01 TUT 01, TU, 10:00"])

def test_pair_penalty_simple():
    input_data = get_input_data(INPUTS_DIR / "test_pair_pen_simple.txt", "1", "1", "1", "1", "1", "1", "1", "1") 
    search = AndTreeSearch(input_data)
    search.search()
    
    assert search.get_formatted_answer() == sorted(["CPSC 231 LEC 01, TU, 13:00", "CPSC 331 LEC 01, TU, 13:00", "CPSC 231 TUT 01, TU, 10:00"])