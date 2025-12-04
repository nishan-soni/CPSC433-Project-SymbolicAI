import sys
from project.parser import get_input_data
from project.and_tree import AndTreeSearch
import random

SHAQ = 32
random.seed(SHAQ)


def main():
    input_data = get_input_data(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        sys.argv[4],
        sys.argv[5],
        sys.argv[6],
        sys.argv[7],
        sys.argv[8],
        sys.argv[9],
    )
    shuffle = False
    if len(sys.argv) > 10:
        break_limit = 1
        shuffle = True
    else:
        break_limit = None

    search = AndTreeSearch(input_data, break_limit=break_limit, shuffle=shuffle)
    search.search()
    print(search.get_formatted_answer_with_eval())


if __name__ == "__main__":
    main()
