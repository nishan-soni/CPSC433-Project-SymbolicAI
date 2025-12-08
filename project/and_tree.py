from __future__ import annotations
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
import random
from typing import Dict, List, Mapping, Optional
from project.models import (
    LecTut,
    LectureSlot,
    NotCompatible,
    PartialAssignment,
    Tutorial,
    LecTutSlot,
    is_tut,
    is_lec,
)
from project.parser import InputData


EVENING_TIME = 18
LEVEL_5XX = 5

@dataclass(frozen=True, slots=True)
class ScheduledItem:
    lt: LecTut
    slot: LecTutSlot
    cap_at_assign: int
    b_score_contribution: float


@dataclass
class DummyLecTut(LecTut):
    identifier: str = "DMM 123 LEC 01"
    alrequired: bool = False


@dataclass(frozen=True)
class DummyScheduledItem(ScheduledItem):
    lt: LecTut = field(default_factory=DummyLecTut)
    start_time: float = 0.0
    end_time: float = 0.0
    day: str = ""
    slot: Optional[LecTutSlot] = None
    cap_at_assign: int = 0
    b_score_contribution: float = 0


@dataclass(frozen=True, slots=True)
class Node:
    most_recent_item: ScheduledItem = field(default_factory=DummyScheduledItem)


def _day_overlap(lt1: LecTut, day1: str, lt2: LecTut, day2: str) -> bool:
    """Returns True if the scheduling of two lectures day's overlap"""
    if day1 == day2:
        return True

    # Check if MWF lecture clashes with F tutorial
    if is_lec(lt1) and day1 == "MO" and is_tut(lt2) and day2 == "FR":
        return True
    if is_tut(lt1) and day1 == "FR" and is_lec(lt2) and day2 == "MO":
        return True

    return False


def _overlap(start1: float, end1: float, start2: float, end2: float) -> bool:
    """Return True if two times overlap"""
    return not ((end1 <= start2) or (end2 <= start1))


def _get_formatted_schedule(sched: Mapping[str, ScheduledItem]) -> str:
    """Creates a formatted output of the schedule"""

    lectures = sorted(
        [item for item in sched.values() if is_lec(item.lt)],
        key=lambda x: x.lt.identifier,
    )
    tutorials = sorted(
        [item for item in sched.values() if is_tut(item.lt)],
        key=lambda x: x.lt.identifier,
    )

    lec_tut_mapping = defaultdict(list)

    for tut_sched in tutorials:
        assert is_tut(tut_sched.lt)
        lec_tut_mapping[tut_sched.lt.parent_lecture_id].append(tut_sched)

    all_ids = [item.lt.identifier for item in sched.values()]
    max_orig = max((len(s) for s in all_ids), default=0)
    target_width = max_orig + 2

    lines: List[str] = []
    for lec in lectures:
        lec_display = lec.lt.identifier.ljust(target_width)
        lines.append(f"{lec_display} : {lec.slot.day}, {lec.slot.time}")
        for tut in sorted(
            lec_tut_mapping.get(lec.lt.identifier, []), key=lambda x: x.lt.identifier
        ):
            tut_display = tut.lt.identifier.ljust(target_width)
            lines.append(f"{tut_display} : {tut.slot.day}, {tut.slot.time}")
            tutorials.remove(tut)

    # add any remaining tutorials
    for tut in tutorials:
        tut_display = tut.lt.identifier.ljust(target_width)
        lines.append(f"{tut_display} : {tut.slot.day}, {tut.slot.time}")
    return "\n".join(lines)


class AndTreeSearch:

    def __init__(
        self, input_data: InputData, break_limit: Optional[int] = None, shuffle=False
    ) -> None:
        self._input_data = input_data

        if shuffle:
            random.shuffle(self._input_data.tutorials)
            random.shuffle(self._input_data.lectures)

        self._NUM_LEC = len(self._input_data.lectures)
        self._NUM_TUT = len(self._input_data.tutorials)

        self._open_lecture_slots = {
            item.identifier: item for item in self._input_data.lec_slots
        }
        self._open_tut_slots = {
            item.identifier: item for item in self._input_data.tut_slots
        }

        self._successors: Dict[str, LecTut] = {}

        self._curr_schedule: Dict[str, ScheduledItem] = {}

        self._curr_bounding_score = 0

        self._min_eval = float("inf")

        self.ans: Optional[Dict[str, ScheduledItem]] = None

        self._break_limit = break_limit

        self._num_results = 0

        self._init_schedule()

        assert self._NUM_LEC >= len(self._5XX_lectures) + len(
            self._al_required_lectures
        ) + len(self._other_lectures) + len(self._evening_lectures)
        assert self._NUM_TUT >= len(self._tutorials)

    def _calc_bounding_score_contrib(
        self, next_lt: LecTut, next_slot: LecTutSlot
    ) -> float:
        """Calculates the bounding score change that occurs if we add a lecture or tutorial to the schedule"""
        pref_pen = 0

        if (ident := next_lt.identifier) in self._input_data.preferences:
            for pref in self._input_data.preferences[ident]:
                if pref.day != next_slot.day or pref.start_time != next_slot.start_time:
                    pref_pen += pref.pref_val

        section_pen = 0
        if not is_lec(next_lt):
            return pref_pen

        for _, item in self._curr_schedule.items():
            if not is_lec(item.lt):
                continue
            if (
                next_lt.course_id == item.lt.course_id
                and _day_overlap(next_lt, next_slot.day, item.lt, item.slot.day)
                and next_slot.start_time == item.slot.start_time
            ):
                section_pen += self._input_data.pen_section

        b_score = pref_pen + section_pen
        return b_score

    def _get_eval_score(self):
        """Gets the eval score of the current schedule"""

        tut_min_pen = 0
        lec_min_pen = 0

        for slot in self._open_lecture_slots.values():
            lec_min_pen += (
                max(slot.min_cap - slot.current_cap, 0) * self._input_data.pen_lec_min
            )

        for slot in self._open_tut_slots.values():
            tut_min_pen += (
                max(slot.min_cap - slot.current_cap, 0) * self._input_data.pen_tut_min
            )

        pair_pen = 0
        # Pair penality
        for pair in self._input_data.pair:
            item_1 = self._curr_schedule[pair.id1]
            item_2 = self._curr_schedule[pair.id2]
            if (
                item_1.slot.day != item_2.slot.day
                or item_1.slot.time != item_2.slot.time
            ):
                pair_pen += self._input_data.pen_not_paired

        return self._curr_bounding_score + lec_min_pen + tut_min_pen + pair_pen

    def _fail_hc(
        self,
        curr_sched: Dict[str, ScheduledItem],
        next_lt: LecTut,
        next_slot: LecTutSlot,
    ) -> bool:
        """Check if adding the lecture/tutorial in the given slot fails hard constraints"""

        # Handle evening constraint
        if next_lt.is_evening and next_slot.start_time < EVENING_TIME:
            return True

        # Handle cap limit
        if next_slot.current_cap >= next_slot.max_cap:
            return True

        # Handle AL limit
        if next_lt.alrequired and next_slot.current_alt_cap >= next_slot.alt_max:
            return True

        # Handle 5XX TIME OVERLAPS
        if is_lec(next_lt) and next_lt.level == LEVEL_5XX:
            for sched_item in self._curr_schedule.values():
                if (
                    is_lec(sched_item.lt)
                    and sched_item.lt.level == LEVEL_5XX
                    and _day_overlap(
                        sched_item.lt, sched_item.slot.day, next_lt, next_slot.day
                    )
                    and _overlap(
                        sched_item.slot.start_time,
                        sched_item.slot.end_time,
                        next_slot.start_time,
                        next_slot.end_time,
                    )
                ):
                    return True

        # Handle tutorial and lecture TIME OVERLAPS
        if is_tut(next_lt) and next_lt.parent_lecture_id in curr_sched:
            sched_lecture = curr_sched[next_lt.parent_lecture_id]
            if _day_overlap(
                sched_lecture.lt, sched_lecture.slot.day, next_lt, next_slot.day
            ) and _overlap(
                sched_lecture.slot.start_time,
                sched_lecture.slot.end_time,
                next_slot.start_time,
                next_slot.end_time,
            ):
                return True

        if is_lec(next_lt):
            for sched_tut in curr_sched.values():
                if (
                    is_tut(sched_tut.lt)
                    and sched_tut.lt.parent_lecture_id == next_lt.identifier
                ):
                    if _day_overlap(
                        sched_tut.lt, sched_tut.slot.day, next_lt, next_slot.day
                    ) and _overlap(
                        sched_tut.slot.start_time,
                        sched_tut.slot.end_time,
                        next_slot.start_time,
                        next_slot.end_time,
                    ):
                        return True

        # Handle not compatible TIME OVERLAPS
        for non_c in self._input_data.not_compatible:
            id1, id2 = non_c.id1, non_c.id2
            if next_lt.identifier not in (id1, id2):
                continue
            if id1 in curr_sched:
                sched_item = curr_sched[id1]
            elif id2 in curr_sched:
                sched_item = curr_sched[id2]
            else:
                continue
            if _day_overlap(
                sched_item.lt, sched_item.slot.day, next_lt, next_slot.day
            ) and _overlap(
                sched_item.slot.start_time,
                sched_item.slot.end_time,
                next_slot.start_time,
                next_slot.end_time,
            ):
                return True

        # Handle unwanted SLOT ASSIGNMENTS

        if (ident := next_lt.identifier) in self._input_data.unwanted:
            for uw in self._input_data.unwanted[ident]:
                if next_slot.day == uw.day and next_slot.start_time == uw.start_time:
                    return True

        return False

    def _get_expansions(self, leaf: Node) -> List[ScheduledItem]:
        """Gets the expansions of a leaf in the And-tree search. The expansion ordering is as follows:

        If most recent assignment is a lecture:
            - Assign its tutorial
        If most recent assignment is a tutorial:
            - Assign its next related tutorial if available (Ex CPSC LEC 01 TUT 03 if TUT 02 was just assigned)

        If the immediate priority is unavailable^:
        - Assign in this priority:
            - An Evening Lecture
            - A 5XX Lecture
            - Other tutorial
            - Other lecture
        """
        chosen_lectut = None

        if (ident := leaf.most_recent_item.lt.identifier) in self._successors:
            chosen_lectut = self._successors[ident]
        elif is_lec((lec := leaf.most_recent_item.lt)):
            for t_id, tut in self._tutorials.items():
                if tut.parent_lecture_id == lec.identifier:
                    chosen_lectut = self._tutorials.pop(t_id)
                    break
        elif is_tut((most_recent_tut := leaf.most_recent_item.lt)):
            for t_id, tut in self._tutorials.items():
                if tut.parent_lecture_id == most_recent_tut.parent_lecture_id:
                    chosen_lectut = self._tutorials.pop(t_id)
                    break

        if not chosen_lectut:
            for lt_bucket in (
                self._al_required_lectures,
                self._5XX_lectures,
                self._evening_lectures,
                self._tutorials,
                self._other_lectures,
            ):
                if lt_bucket:
                    _, chosen_lectut = lt_bucket.popitem(last=False)
                    break
            else:
                return []

        self._successors[leaf.most_recent_item.lt.identifier] = chosen_lectut

        open_slots = (
            self._open_lecture_slots if is_lec(chosen_lectut) else self._open_tut_slots
        )

        expansions = []
        for _, os in open_slots.items():
            if self._fail_hc(self._curr_schedule, chosen_lectut, os):
                continue
            next_b_score = self._calc_bounding_score_contrib(chosen_lectut, os)
            if next_b_score + self._curr_bounding_score > self._min_eval:
                continue
            expansions.append(
                ScheduledItem(chosen_lectut, os, os.current_cap, next_b_score)
            )
        return sorted(expansions, key=lambda x: x.b_score_contribution)

    def _init_schedule(self):
        """Initialize the schedule with the projects edge cases and partial assignments"""

        # remove Tuesday @ 11-12:30 from slots
        self._open_lecture_slots = {
            k: v
            for k, v in self._open_lecture_slots.items()
            if not (v.day == "TU" and v.time == "11:00")
        }

        initial_schedule: Dict[str, ScheduledItem] = {}
        self._all_lectures = {
            item.identifier: item for item in self._input_data.lectures
        }
        self._tutorials = OrderedDict(
            {item.identifier: item for item in self._input_data.tutorials}
        )

        # Add partial assignments for 851 TUT and 913 TUT to TU 18:00 if 351 or 413 exist
        id_851 = "CPSC 851 TUT 01"
        id_913 = "CPSC 913 TUT 01"

        for _, lec in self._all_lectures.items():
            if lec.course_id == "CPSC 351":
                self._tutorials[id_851] = Tutorial(id_851, False)
                self._input_data.part_assign[id_851] = PartialAssignment(
                    id_851, "TU", "18:00"
                )
                self._NUM_TUT += 1
                for lt in self._input_data.lectures + self._input_data.tutorials:
                    if lt.course_id == "CPSC 351":
                        self._input_data.not_compatible.append(
                            NotCompatible(lt.identifier, id_851)
                        )

            if lec.course_id == "CPSC 413":
                self._tutorials[id_913] = Tutorial(id_913, False)
                self._input_data.part_assign[id_913] = PartialAssignment(
                    id_913, "TU", "18:00"
                )
                self._NUM_TUT += 1
                for lt in self._input_data.lectures + self._input_data.tutorials:
                    if lt.course_id == "CPSC 413":
                        self._input_data.not_compatible.append(
                            NotCompatible(lt.identifier, id_913)
                        )

        # Assign the partial assignments
        for lt_id, p_assign in self._input_data.part_assign.items():
            if lt_id in self._tutorials:
                lt = self._tutorials[lt_id]
                lt_bucket = self._tutorials
            elif lt_id in self._all_lectures:
                lt = self._all_lectures[lt_id]
                lt_bucket = self._all_lectures
            else:
                raise Exception(
                    f"The partial assignment for lecture / tutorial {lt_id} failed because it does not exist in the schedule."
                )
            open_slots = (
                self._open_lecture_slots if is_lec(lt) else self._open_tut_slots
            )
            for slot in open_slots.values():
                if slot.day == p_assign.day and slot.time == p_assign.time:
                    if self._fail_hc(initial_schedule, lt, slot):
                        raise Exception("Partial Assignments failed hard constraints.")
                    slot.current_cap += 1
                    b_score = self._calc_bounding_score_contrib(lt, slot)
                    self._curr_bounding_score += b_score
                    initial_schedule[lt_id] = ScheduledItem(
                        lt, slot, slot.current_cap, b_score
                    )
                    del lt_bucket[lt_id]
                    break
            else:
                raise Exception(
                    f"The slot for partial assignment {lt_id} {p_assign.day} {p_assign.time} does not exist."
                )

        self._curr_schedule = initial_schedule
        self._al_required_lectures = OrderedDict(
            {
                item.identifier: item
                for item in self._all_lectures.values()
                if item.alrequired
            }
        )
        self._5XX_lectures = OrderedDict(
            {
                item.identifier: item
                for item in self._all_lectures.values()
                if item.level == LEVEL_5XX
                and item.identifier not in self._al_required_lectures
            }
        )
        self._evening_lectures = OrderedDict(
            {
                item.identifier: item
                for item in self._all_lectures.values()
                if item.is_evening
                and item.identifier not in self._5XX_lectures
                and item.identifier not in self._al_required_lectures
            }
        )
        self._other_lectures = OrderedDict(
            {
                item.identifier: item
                for item in self._all_lectures.values()
                if item.identifier not in self._5XX_lectures
                and item.identifier not in self._evening_lectures
                and item.identifier not in self._al_required_lectures
            }
        )

    def _pre_dfs_slot_update(self, sched_item: ScheduledItem) -> None:
        slot = sched_item.slot

        slot.current_cap += 1

        if sched_item.lt.alrequired:
            slot.current_alt_cap += 1

    def _post_dfs_slot_update(self, sched_item: ScheduledItem) -> None:
        slot = sched_item.slot
        slot.current_cap -= 1

        if sched_item.lt.alrequired:
            slot.current_alt_cap -= 1

    def _pre_dfs_updates(self, scheduled_item: ScheduledItem):
        self._pre_dfs_slot_update(scheduled_item)
        self._curr_schedule[scheduled_item.lt.identifier] = scheduled_item
        self._curr_bounding_score += scheduled_item.b_score_contribution

    def _post_dfs_updates(self, scheduled_item: ScheduledItem):
        self._post_dfs_slot_update(scheduled_item)
        del self._curr_schedule[scheduled_item.lt.identifier]
        self._curr_bounding_score -= scheduled_item.b_score_contribution

    def _dfs(self, current_leaf: Node):
        if self._break_limit and self._num_results >= self._break_limit:
            return

        expansions = self._get_expansions(current_leaf)
        print(len(self._curr_schedule), end="\r")
        if not expansions:
            if len(self._curr_schedule) == self._NUM_TUT + self._NUM_LEC:
                res = self._curr_schedule.copy()
                if (ev := self._get_eval_score()) < self._min_eval:
                    self.ans = res
                    self._min_eval = ev
                    self._num_results += 1
            return

        for next_item in expansions:
            new_leaf = Node(most_recent_item=next_item)
            self._pre_dfs_updates(next_item)
            self._dfs(new_leaf)
            self._post_dfs_updates(next_item)

    def get_formatted_answer(self) -> str:
        if not self.ans:
            return "No valid schedule!"
        return _get_formatted_schedule(self.ans)

    def get_formatted_answer_with_eval(self) -> str:
        return f"Eval-value: {self._min_eval}\n{self.get_formatted_answer()}"

    def search(self):

        root = Node(DummyScheduledItem())
        self._dfs(root)

        return self.ans
