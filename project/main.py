import sys
from time import perf_counter
from project.parser import get_input_data
from project.and_tree import AndTreeSearch
import tracemalloc

def main():
    input_data = get_input_data(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7], sys.argv[8], sys.argv[9])

    search = AndTreeSearch(input_data, break_limit=1)
    search.search()
    print(search.get_formatted_answer_with_eval())

if __name__ == "__main__":
    main()