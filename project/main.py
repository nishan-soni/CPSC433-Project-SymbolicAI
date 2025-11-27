import sys
from time import perf_counter
from project.parser import get_input_data
from project.and_tree import AndTreeSearch
import tracemalloc

def main():

    # Read command-line args and parse into InputData object (parser.py)
    input_data = get_input_data(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7], sys.argv[8], sys.argv[9])

    # ?? do we want to keep this v
    # for slot in input_data.lec_slots:
    #     slot.current_cap += 1

    search = AndTreeSearch(input_data)

    tracemalloc.start()                     # start tracking memory allocations
    start = perf_counter()                  # start timer

    # Run the and-tree search
    res, ans = search.search()              # res = list of all found solutions; ans = selected (best) solution

    end = perf_counter()                    # stop timer
    snapshot = tracemalloc.take_snapshot()  # store memory usage snapshot
    tracemalloc.stop()                      # stop memory tracking

    # Print most memory-consuming lines of code
    top = snapshot.statistics("lineno")[:20]
    print("Top 20 memory allocations:")
    for stat in top:
        print(stat)

    print(f"speed: {end - start}")          # Print total runtime of search

    print("num leafs:", search.num_leafs)   # Print num of leaf nodes explored

    print("num valid solutions:", len([r for r in res if len(r) == len(input_data.lectures) + len(input_data.tutorials)]))
                                            # Count valid solutions (s.t. it includes all lectures/tutorials)


    # ?? do we want this v
    # for r in res:
    #     print(len(r.schedule))
    #     print(" ")

    print(" ")
    print(ans)                               # Print the selected answer

if __name__ == "__main__":
    main()