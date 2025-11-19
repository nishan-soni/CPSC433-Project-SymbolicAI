from __future__ import annotations
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Union
from project.models import LecTut, Lecture, LectureSlot, TutorialSlot, LecTutSlot, is_tut, is_lec
from project.parser import InputData

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


def _overlap(start1: float, end1: float, start2: float, end2: float) -> bool:
    return not ((end1 < start2) or (end2 < start1))

class AndTreeSearch:

    def __init__(self, input_data: InputData) -> None:
        self._input_data = input_data

        self._open_lecture_slots = {item.identifier: item for item in self._input_data.lec_slots}
        self._open_tut_slots = {item.identifier: item for item in self._input_data.tut_slots}

        self._5XX_lectures = OrderedDict({item.identifier: item for item in self._input_data.lectures if item.level == 5})
        self._evening_lectures = OrderedDict({item.identifier: item for item in self._input_data.lectures if item.is_evening})
        self._other_lectures = OrderedDict({item.identifier: item for item in self._input_data.lectures if item.identifier not in self._5XX_lectures and item.identifier not in self._evening_lectures})
        self._tutorials = OrderedDict({item.identifier: item for item in self._input_data.tutorials})

        self._successors: Dict[str, LecTut] = {}

        self._curr_schedule: Dict[str, ScheduledItem] = {}

        self._curr_bounding_score = 0

        self._min_eval = float('inf')

        self._results = []

        self.num_leafs = 0 # for observability

        self.ans: Optional[Dict[str, ScheduledItem]] = None
    
    def _calc_bounding_score_contrib(self, next_lt: LecTut, next_slot: LecTutSlot) -> float:
        # Preference penalty
        pref_pen = 0
        
        if (ident := next_lt.identifier) in self._input_data.preferences and (self._input_data.preferences[ident].day != next_slot.day or self._input_data.preferences[ident].start_time != next_slot.start_time):
            pref_pen = self._input_data.preferences[ident].pref_val
    
        # Pair penality
        pair_pen = 0
        if (ident := next_lt.identifier) in self._input_data.pair and (pair_id := self._input_data.pair[ident]) in self._curr_schedule and (self._curr_schedule[pair_id].slot.day != next_slot.day or self._curr_schedule[pair_id].slot.start_time != next_slot.start_time):
            pair_pen = self._input_data.pen_not_paired
        
        # Section penalty

        section_pen = 0
        if not is_lec(next_lt):
            return pref_pen + pair_pen

        for _, item in self._curr_schedule.items():
            if not is_lec(item.lt):
                continue
            if next_lt.lecture_id == item.lt.lecture_id and next_slot.day == item.slot.day and next_slot.start_time == item.slot.start_time:
                section_pen = self._input_data.pen_section

        b_score = pref_pen + pair_pen + section_pen
        return b_score
    
    def _get_eval_score(self):
        """
        KEEP TRACK OF CURRENT EVAL SCORE FOR SPEED INSTEAD
        """
        return self._curr_bounding_score
    
    def _fail_hc(self, curr_sched: Dict[str, ScheduledItem], next_lt: LecTut, next_slot: LecTutSlot) -> bool:

        # Handle cap limit
        if next_slot.current_cap >= next_slot.max_cap:
            return True

        # Handle AL limit
        if next_lt.alrequired and next_slot.current_alt_cap >= next_slot.alt_max:
            return True
        
        # Handle 5XX TIME OVERLAPS
        if is_lec(next_lt) and next_lt.level == 5:
            for sched_item in self._curr_schedule.values():
                if is_lec(sched_item.lt) and sched_item.lt.level == 5 and sched_item.slot.day == next_slot.day and sched_item.slot.start_time == next_slot.start_time:
                    return True


        # Handle tutorial and lecture TIME OVERLAPS
        if is_tut(next_lt) and next_lt.parent_lecture_id in curr_sched:
            sched_lecture = curr_sched[next_lt.parent_lecture_id]
            if _overlap(sched_lecture.slot.start_time, sched_lecture.slot.end_time, next_slot.start_time, next_slot.end_time):
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
            if _overlap(sched_item.slot.start_time, sched_item.slot.end_time, next_slot.start_time, next_slot.end_time):
                return True

        # Handle unwanted SLOT ASSIGNMENTS

        if (ident := next_lt.identifier) in self._input_data.unwanted:
            for uw in self._input_data.unwanted[ident]:
                if next_slot.day == uw.day and next_slot.start_time == uw.start_time:
                    return True
        
        return False
    

    def _get_expansions(self, leaf: Node) -> List[ScheduledItem]:
        """
        Expansion ordering

        If most recent assignment is a lecture:
            - Assign its tutorial
        If most recent assignment is a tutorial:
            - Assign its next related tutorial if available (Ex CPSC LEC 01 TUT 03 if TUT 02 was just assigned)
        
        If the immediate priority is unavailable^:
        - Assign in this priority:
            - A 5XX Lecture
            - An Evening Lecture
            - Other lecture
            - Other tutorial
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
            for lt_bucket in (self._5XX_lectures, self._evening_lectures, self._other_lectures, self._tutorials):
                if lt_bucket:
                    _, chosen_lectut = lt_bucket.popitem(last=False)
                    break
            else:
                return []

        self._successors[leaf.most_recent_item.lt.identifier] = chosen_lectut

        open_slots = self._open_lecture_slots if is_lec(chosen_lectut) else self._open_tut_slots
        
        expansions = []
        for _, os in open_slots.items():
            if self._fail_hc(self._curr_schedule, chosen_lectut, os):
                continue
            next_b_score = self._calc_bounding_score_contrib(chosen_lectut, os)
            if next_b_score + self._curr_bounding_score > self._min_eval:
                continue
            expansions.append(ScheduledItem(chosen_lectut, os, os.current_cap, next_b_score))
        return expansions

    def _pre_process(self) -> Node:
        return Node (DummyScheduledItem())
    
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

        expansions = self._get_expansions(current_leaf)

        if not expansions:
            self.num_leafs += 1 # for observability
            if len(self._curr_schedule) == len(self._input_data.lectures) + len(self._input_data.tutorials):
                self._results.append(self._curr_schedule.copy())
                if (ev := self._get_eval_score()) < self._min_eval:
                    self.ans = self._curr_schedule.copy()
                    self._min_eval = ev
            return

        for next_item in expansions:
            new_leaf = Node(most_recent_item=next_item)
            self._pre_dfs_updates(next_item)
            self._dfs(new_leaf)
            self._post_dfs_updates(next_item)

    def get_formatted_answer(self) -> List[str]:
        if not self.ans:
            return []

        res = []
        for _, node in self.ans.items():
            res.append(f"{node.lt.identifier}, {node.slot.day}, {node.slot.time}")

        return sorted(res)


    def search(self):

        s_0 = self._pre_process()
        self._dfs(s_0)


        return self._results, self.ans
    

