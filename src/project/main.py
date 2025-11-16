from time import perf_counter
from project.parser import get_input_data
from project.and_tree import AndTreeSearch
import tracemalloc

def main():
    input_data = get_input_data("../input.txt")

    # for slot in input_data.lec_slots:
    #     slot.current_cap += 1

    search = AndTreeSearch(input_data)

    tracemalloc.start()
    start = perf_counter()
    res = search.search()
    end = perf_counter()
    snapshot = tracemalloc.take_snapshot()
    tracemalloc.stop()

    top = snapshot.statistics("lineno")[:20]
    print("Top 20 memory allocations:")
    for stat in top:
        print(stat)

    print(f"speed: {end - start}")

    print("num leafs:", len(res))
    print("num valid solutions:", len([r for r in res if len(r.schedule) == len(input_data.lectures) + len(input_data.tutorials)]))

    # for r in res:
    #     print(len(r.schedule))
    #     print(" ")

if __name__ == "__main__":
    main()