from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Union
from project.models import LecTut, Lecture, LectureSlot, TutorialSlot, LecTutSlot, is_tut, is_lec
from project.parser import InputData

@dataclass(frozen=True)
class ScheduledItem:
    lt: LecTut
    start_time: float
    end_time: float
    day: str
    slot: LecTutSlot
    cap_at_assign: int

@dataclass
class DummyLecTut(LecTut):
    identifier: str = "Dummy"
    alrequired: bool = False

    @classmethod
    def make(cls) -> DummyLecTut:
        return cls()

@dataclass(frozen=True)
class DummyScheduledItem(ScheduledItem):
    lt: LecTut = field(default_factory=DummyLecTut.make)
    start_time: float = 0.0
    end_time: float = 0.0
    day: str = ""
    slot: Optional[LecTutSlot] = None
    cap_at_assign: int = 0
    is_dummy: bool = True

    @classmethod
    def make(cls) -> DummyScheduledItem:
        return cls()

@dataclass
class Node:
    schedule: Dict[str, ScheduledItem]
    most_recent_item: ScheduledItem = field(default_factory=DummyScheduledItem.make)


def _overlap(start1: float, end1: float, start2: float, end2: float) -> bool:
    return not ((end1 < start2) or (end2 < start1))

class AndTreeSearch:

    def __init__(self, input_data: InputData) -> None:
        self._input_data = input_data
        self._unassigned_lecs = self._input_data.lectures.copy()
        self._unassigned_tuts = self._input_data.tutorials.copy()

        # CHANGE THESE TO A MIN HEAP STRUCUTE FOR EVAL IN THE FUTURE?
        self._open_lecture_slots = {item.identifier: item for item in self._input_data.lec_slots}
        self._open_tut_slots = {item.identifier: item for item in self._input_data.tut_slots}

        self._successors: Dict[str, LecTut] = {}

        self._results = []

    
    def _pass_hc(self, curr_sched: Dict[str, ScheduledItem], next_item: ScheduledItem) -> bool:
        # Handle tutorial and lecture TIME OVERLAPS
        if is_tut(next_item.lt) and next_item.lt.parent_lecture_id in curr_sched:
            sched_lecture = curr_sched[next_item.lt.parent_lecture_id]
            if _overlap(sched_lecture.start_time, sched_lecture.end_time, next_item.start_time, next_item.end_time):
                return False

        # Handle not compatible TIME OVERLAPS
        for non_c in self._input_data.not_compatible:
            id1, id2 = non_c.id1, non_c.id2
            if next_item.lt.identifier not in (id1, id2):
                continue
            if id1 in curr_sched:
                sched_item = curr_sched[id1]
            elif id2 in curr_sched:
                sched_item = curr_sched[id2]
            else:
                continue
            if _overlap(sched_item.start_time, sched_item.end_time, next_item.start_time, next_item.end_time):
                return False

        # Handle unwanted SLOT ASSIGNMENTS

        if (ident := next_item.lt.identifier) in self._input_data.unwanted:
            for uw in self._input_data.unwanted[ident]:
                if next_item.day == uw.day and next_item.start_time == uw.start_time:
                    return False
        
        return True
    

    def _get_expansions(self, leaf: Node) -> List[ScheduledItem]:
        
        # THIS IS BASICALLY THE F_TRANS PICKING WHAT TO SCHEDULE NEXT
        if (ident := leaf.most_recent_item.lt.identifier) in self._successors:
            next_lectut = self._successors[ident]
        else:
            if self._unassigned_lecs:
                next_lectut = self._unassigned_lecs.pop()
            elif self._unassigned_tuts:
                next_lectut = self._unassigned_tuts.pop()
            else:
                return []
            self._successors[leaf.most_recent_item.lt.identifier] = next_lectut
        
        if isinstance(next_lectut, Lecture):
            open_slots = self._open_lecture_slots
        else:
            open_slots = self._open_tut_slots
        
        expansions = []
        for _, os in open_slots.items():
            new_item = ScheduledItem(next_lectut, os.start_time, os.end_time, os.day, os, os.current_cap)
            if not self._pass_hc(leaf.schedule, new_item):
                continue
            expansions.append(new_item)
        return expansions

    def _pre_process(self) -> Node:
        return Node ({}, DummyScheduledItem.make())
    
    def _pre_dfs_pop(self, slot: LecTutSlot) -> None:

        """
        NEED TO HANDLE ACTIVE LEARNING
        """
        slot.increment_current_cap()

        if slot.current_cap >= slot.max_cap:
            if slot.identifier in self._open_lecture_slots:
                del self._open_lecture_slots[slot.identifier]
            else:
                del self._open_tut_slots[slot.identifier]
    
    def _post_dfs_updates(self, slot: LecTutSlot) -> None:
        """
        NEED TO HANDLE ACTIVE LEARNING
        """
        slot.decrement_current_cap()
        if slot.current_cap < slot.max_cap:
            if isinstance(slot, LectureSlot):
                self._open_lecture_slots[slot.identifier] = slot
            else:
                self._open_tut_slots[slot.identifier] = slot


    def _dfs(self, current_leaf: Node):

        expansions = self._get_expansions(current_leaf)

        if not expansions:
            # print(len(current_leaf.schedule))
            # print(current_leaf)
            # print(self._unassigned_lecs)
            # print(self._unassigned_tuts)
            # print(self._open_lecture_slots)
            # print(self._open_tut_slots)
            # print(" ")
            self._results.append(current_leaf)
            return

        for next_item in expansions:
            new_leaf = Node(most_recent_item=next_item, schedule=current_leaf.schedule | {next_item.lt.identifier: next_item})
            self._pre_dfs_pop(next_item.slot)
            self._dfs(new_leaf)
            self._post_dfs_updates(next_item.slot)


    def search(self) -> List:

        s_0 = self._pre_process()
        self._dfs(s_0)


        return self._results

