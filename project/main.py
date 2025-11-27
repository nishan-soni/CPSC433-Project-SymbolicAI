import sys
from time import perf_counter
from project.parser import get_input_data
from project.and_tree import AndTreeSearch
import tracemalloc

def main():
    input_data = get_input_data(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7], sys.argv[8], sys.argv[9])

    # for slot in input_data.lec_slots:
    #     slot.current_cap += 1

    search = AndTreeSearch(input_data, break_limit=20000)

    tracemalloc.start()
    start = perf_counter()
    res, ans = search.search()
    end = perf_counter()
    snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()

    top = snapshot.statistics("lineno")[:20]
    print("Top 20 memory allocations:")
    for stat in top:
        print(stat)

    print(f"speed: {end - start}")

    print("num leafs:", search.num_leafs)
    print("num valid solutions:", len([r for r in res if len(r) == len(input_data.lectures) + len(input_data.tutorials)]))

    # for r in res:
    #     print(len(r.schedule))
    #     print(" ")

    print(" ")
    print(search.get_formatted_answer())
    print("min eval", search._min_eval)

if __name__ == "__main__":
    main()