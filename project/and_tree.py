from __future__ import annotations
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence, Union
from project.models import LecTut, Lecture, LectureSlot, NotCompatible, TutorialSlot, LecTutSlot, is_tut, is_lec
from project.parser import InputData



@dataclass(frozen=True, slots=True)
class ScheduledItem:                # ScheduledItem: represents one actual assignment
    lt: LecTut                      # a lecture or tutorial
    slot: LecTutSlot                # a slot
    cap_at_assign: int              # a capacity snapshot
    b_score_contribution: float     # a bounding score (pentaly contribution) for pruning



# Dummy objects used for initializing the DFS tree's root node
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



# Represents a node in the DFS tree
# Stores most recent ScheduledItem added, so the search knows what to expand next
@dataclass(frozen=True, slots=True)
class Node:  
    most_recent_item: ScheduledItem = field(default_factory=DummyScheduledItem) 



EVENING_TIME = 18
LEVEL_5XX = 5



# Returns whether two time intervals overlap
def _overlap(start1: float, end1: float, start2: float, end2: float) -> bool:
    return not ((end1 < start2) or (end2 < start1))


# Turns best schedule into a readable timetable
def _get_formatted_schedule(sched: Mapping[str, ScheduledItem]) -> str:
    """Order lectures alphabetically, and put tutorials under their lecture"""
    
    # Seperate lectures and tutorials
    lectures = sorted([item for item in sched.values() if is_lec(item.lt)], key=lambda x: x.lt.identifier)
    tutorials = sorted([item for item in sched.values() if is_tut(item.lt)], key=lambda x: x.lt.identifier)

    # Map each lecture to the list of its tutorials
    lec_tut_mapping = defaultdict(list)

    for tut_sched in tutorials:
        assert is_tut(tut_sched.lt)
        lec_tut_mapping[tut_sched.lt.parent_lecture_id].append(tut_sched)
    
    # Compute width for printing
    all_ids = [item.lt.identifier for item in sched.values()]
    max_orig = max((len(s) for s in all_ids), default=0)
    target_width = max_orig + 2

    # Build output lines
    lines: List[str] = []
    for lec in lectures:
        lec_display = lec.lt.identifier.ljust(target_width)
        lines.append(f"{lec_display} : {lec.slot.day}, {lec.slot.time}")
        
        for tut in sorted(lec_tut_mapping.get(lec.lt.identifier, []), key=lambda x: x.lt.identifier):
            tut_display = tut.lt.identifier.ljust(target_width)
            lines.append(f"{tut_display} : {tut.slot.day}, {tut.slot.time}")
            tutorials.remove(tut)

    # Add any remaining tutorials
    for tut in tutorials:
        tut_display = tut.lt.identifier.ljust(target_width)
        lines.append(f"{tut_display} : {tut.slot.day}, {tut.slot.time}")
    
    return "\n".join(lines)


##################################################################################################################################


class AndTreeSearch:

    def __init__(self, input_data: InputData) -> None:
        '''
        Initializes the search:
        - loads all available slots
        - loads all lectures/tutorials
        - applies partial assignments
        - sets up bounding score, best answer, and slot usage states
        '''
        self._input_data = input_data

        # Dictionaries mapping slot identifier to slot
        self._open_lecture_slots = {item.identifier: item for item in self._input_data.lec_slots}   # all possible lec slots
        self._open_tut_slots = {item.identifier: item for item in self._input_data.tut_slots}       # all possible tut slots

        self._successors: Dict[str, LecTut] = {}            # used for expanding lec/tut in a sequence
        self._curr_schedule: Dict[str, ScheduledItem] = {}  # current partial schedule
        self._curr_bounding_score = 0                       # penalty so far
        self._min_eval = float('inf')                       # best full schedule's score found so far
        self._results = []                                  # all full schedules found
        self.num_leafs = 0                                  # for observability
        self.ans: Optional[Dict[str, ScheduledItem]] = None # best schedule found

        self._init_schedule()                               # apply partial assignments and set up priorities
        print(input_data.not_compatible)


    # Calculates bounding score based on penalties, for pruning
    def _calc_bounding_score_contrib(self, next_lt: LecTut, next_slot: LecTutSlot) -> float:
        
        # Preference penalty
        pref_pen = 0
        if (ident := next_lt.identifier) in self._input_data.preferences and (self._input_data.preferences[ident].day != next_slot.day or self._input_data.preferences[ident].start_time != next_slot.start_time):
            pref_pen = self._input_data.preferences[ident].pref_val
    
        # Pair penality: items that must be scheduled together
        pair_pen = 0
        if (ident := next_lt.identifier) in self._input_data.pair and (pair_id := self._input_data.pair[ident]) in self._curr_schedule and (self._curr_schedule[pair_id].slot.day != next_slot.day or self._curr_schedule[pair_id].slot.start_time != next_slot.start_time):
            pair_pen = self._input_data.pen_not_paired
        
        # Section penalty: two lectures of same course at same slot
        section_pen = 0
        if not is_lec(next_lt):
            return pref_pen + pair_pen

        for _, item in self._curr_schedule.items():
            if not is_lec(item.lt):
                continue
            if next_lt.lecture_id == item.lt.lecture_id and next_slot.day == item.slot.day and next_slot.start_time == item.slot.start_time:
                section_pen = self._input_data.pen_section

        b_score = pref_pen + pair_pen + section_pen # final calculated score
        return b_score
    

    # Computes total estimated score = current penalty + min future penalty
    def _get_eval_score(self):
        """This can most likely be optimized"""

        tut_min_pen = 0
        lec_min_pen = 0

        # Penalties for lecture slots that would stay under min capacity
        for slot in self._open_lecture_slots.values():
            lec_min_pen += max(slot.min_cap - slot.current_cap, 0) * self._input_data.pen_lec_min

        # Penalties for tutorial slots that would stay under min capacity
        for slot in self._open_tut_slots.values():
            tut_min_pen += max(slot.min_cap - slot.current_cap, 0) * self._input_data.pen_tut_min

        return self._curr_bounding_score + lec_min_pen + tut_min_pen
    

    # Checks whether assigning a lec/tut to a slot violates any hard constraint
    # If any rule is violated: return True (fail)
    def _fail_hc(self, curr_sched: Dict[str, ScheduledItem], next_lt: LecTut, next_slot: LecTutSlot) -> bool:

        # Handle capacity limit
        if next_slot.current_cap >= next_slot.max_cap:
            return True

        # Handle AL limit
        if next_lt.alrequired and next_slot.current_alt_cap >= next_slot.alt_max:
            return True
        
        # Handle 5XX TIME OVERLAPS
        if is_lec(next_lt) and next_lt.level == LEVEL_5XX:
            for sched_item in self._curr_schedule.values():
                if is_lec(sched_item.lt) and sched_item.lt.level == LEVEL_5XX and sched_item.slot.day == next_slot.day and _overlap(sched_item.slot.start_time, sched_item.slot.end_time, next_slot.start_time, next_slot.end_time):
                    return True

        # Handle tutorial and lecture TIME OVERLAPS
        if is_tut(next_lt) and next_lt.parent_lecture_id in curr_sched:
            sched_lecture = curr_sched[next_lt.parent_lecture_id]
            if sched_lecture.slot.day == sched_lecture.slot.day and _overlap(sched_lecture.slot.start_time, sched_lecture.slot.end_time, next_slot.start_time, next_slot.end_time):
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
            if sched_item.slot.day == next_slot.day and _overlap(sched_item.slot.start_time, sched_item.slot.end_time, next_slot.start_time, next_slot.end_time):
                return True

        # Handle unwanted SLOT ASSIGNMENTS
        if (ident := next_lt.identifier) in self._input_data.unwanted:
            for uw in self._input_data.unwanted[ident]:
                if next_slot.day == uw.day and next_slot.start_time == uw.start_time:
                    return True
        
        return False
    

    def _get_expansions(self, leaf: Node) -> List[ScheduledItem]:
        """
        Determines which lecture/tutorial to assign next, using a heuristic.
        Returns a list of ScheduledItem objects that correspond to valid options.
        
        Expansion ordering heuristic:

        If most recent assignment is a lecture:
            - Assign its tutorial
        If most recent assignment is a tutorial:
            - Assign its next related tutorial if available (Ex CPSC LEC 01 TUT 03 if TUT 02 was just assigned)
        
        Otherwise, if the immediate priority is unavailable^:
        - Assign in this priority:
            - An Evening Lecture
            - A 5XX Lecture
            - Other lecture
            - Other tutorial
        """

        chosen_lectut = None

        # If we have decided the next item for this one, use it
        if (ident := leaf.most_recent_item.lt.identifier) in self._successors:
            chosen_lectut = self._successors[ident]

        # If it's a lecture, schedule its tutorials next
        elif is_lec((lec := leaf.most_recent_item.lt)):
            for t_id, tut in self._all_tutorials.items():
                if tut.parent_lecture_id == lec.identifier:
                    chosen_lectut = self._all_tutorials.pop(t_id)
                    break

        # If it's a tutorial, schedule the next tutorial for the same lecture
        elif is_tut((most_recent_tut := leaf.most_recent_item.lt)):
            for t_id, tut in self._all_tutorials.items():
                if tut.parent_lecture_id == most_recent_tut.parent_lecture_id:
                    chosen_lectut = self._all_tutorials.pop(t_id)
                    break

        # Otherwise, use priority buckets
        if not chosen_lectut:
            for lt_bucket in (self._evening_lectures, self._5XX_lectures, self._other_lectures, self._all_tutorials):
                if lt_bucket:
                    _, chosen_lectut = lt_bucket.popitem(last=False)
                    break
            else:
                return [] # If there are no remaining items, no expansions

        # Store chosen successor for the item
        self._successors[leaf.most_recent_item.lt.identifier] = chosen_lectut

        # Pick slots
        open_slots = self._open_lecture_slots if is_lec(chosen_lectut) else self._open_tut_slots
        
        expansions = []
        for _, os in open_slots.items():

            # Evening lectures use evening slots
            if chosen_lectut.is_evening and os.start_time < EVENING_TIME:
                continue

            # Hard constraints check
            if self._fail_hc(self._curr_schedule, chosen_lectut, os):
                continue

            # Penalty for this placement
            next_b_score = self._calc_bounding_score_contrib(chosen_lectut, os)
            
            # Pruning: if it exceeds best score, skip
            if next_b_score + self._curr_bounding_score > self._min_eval:
                continue

            expansions.append(ScheduledItem(chosen_lectut, os, os.current_cap, next_b_score))
        return expansions


    def _init_schedule(self):
        # remove Tuesday @ 11-12:30 from slots
        self._open_lecture_slots = {k: v for k, v in self._open_lecture_slots.items() if not (v.day == "TU" and v.time == "11:00")}

        # Loads all lectures and tutorials
        initial_schedule: Dict[str, ScheduledItem] = {}
        self._all_lectures = {item.identifier: item for item in self._input_data.lectures}                  # all unscheduled lectures
        self._all_tutorials = OrderedDict({item.identifier: item for item in self._input_data.tutorials})   # all unscheduled tutorials

        # Partial assignments:

        # Assign 851 and 913 to TU 18:00 if they exist  
        special_time_slot = LectureSlot("TU", "18:00", 2, 0, 0)   
        special_time_slot.end_time = 19
        for key, lec in self._all_lectures.items():
            if lec.lecture_id in ("CPSC 851", "CPSC 913"):
                initial_schedule[lec.identifier] = ScheduledItem(lec, special_time_slot, 0, 0)
        
        # the rest of the partial assignments
        for lt_id, p_assign in self._input_data.part_assign.items():
            if lt_id in self._all_tutorials:
                lt = self._all_tutorials[lt_id]
                lt_bucket = self._all_tutorials
            elif lt_id in self._all_lectures:
                lt = self._all_lectures[lt_id]
                lt_bucket = self._all_lectures
            else:
                raise Exception(f"The partial assignment for lecture / tutorial {lt_id} failed because it does not exist in the schedule.")
            open_slots = self._open_lecture_slots if is_lec(lt) else self._open_tut_slots
            for slot in open_slots.values():
                if slot.day == p_assign.day and slot.time == p_assign.time:
                    b_score = self._calc_bounding_score_contrib(lt, slot)
                    self._curr_bounding_score += b_score
                    initial_schedule[lt_id] = ScheduledItem(lt, slot, slot.current_cap, b_score)
                    del lt_bucket[lt_id]
                    break
            else:
                raise Exception(f"The slot for partial assignment {lt_id} {p_assign.day} {p_assign.time} does not exist.")
        
        self._curr_schedule = initial_schedule
        
        # Add incompatible statements with all CPSC 331 + 851 and CPSC 413 + CPSC 913
        for id_351, lt_351 in (self._all_lectures | self._all_tutorials).items():
            if is_lec(lt_351) and lt_351.lecture_id != "CPSC 351" or is_tut(lt_351) and "CPSC 351" not in lt_351.parent_lecture_id: 
                continue
            for id_851, lt_851 in (self._all_lectures | self._all_tutorials).items():
                if is_lec(lt_851) and lt_851.lecture_id != "CPSC 851" or is_tut(lt_851) and "CPSC 851" not in lt_851.parent_lecture_id: 
                    continue
                self._input_data.not_compatible.append(NotCompatible(id_351, id_851))
        for id_413, lt_413 in (self._all_lectures | self._all_tutorials).items():
            if is_lec(lt_413) and lt_413.lecture_id != "CPSC 413" or is_tut(lt_413) and "CPSC 413" not in lt_413.parent_lecture_id:
                continue
            for id_913, lt_913 in (self._all_lectures | self._all_tutorials).items():
                if is_lec(lt_913) and lt_913.lecture_id != "CPSC 913" or is_tut(lt_913) and "CPSC 913" not in lt_913.parent_lecture_id:
                    continue
                self._input_data.not_compatible.append(NotCompatible(id_413, id_913))

        # Priority lectures (evening -> 5XX -> other lec -> other tut)
        self._5XX_lectures = OrderedDict({item.identifier: item for item in self._all_lectures.values() if item.level == LEVEL_5XX})
        self._evening_lectures = OrderedDict({item.identifier: item for item in self._all_lectures.values() if item.is_evening})
        self._other_lectures = OrderedDict({item.identifier: item for item in self._all_lectures.values() if item.identifier not in self._5XX_lectures and item.identifier not in self._evening_lectures})


    # Update slot usages before recursion
    def _pre_dfs_slot_update(self, sched_item: ScheduledItem) -> None:
        slot = sched_item.slot
        slot.current_cap += 1
        if sched_item.lt.alrequired:
            slot.current_alt_cap += 1
    
    # Undo slot usage after recursion
    def _post_dfs_slot_update(self, sched_item: ScheduledItem) -> None:
        slot = sched_item.slot
        slot.current_cap -= 1
        if sched_item.lt.alrequired:
            slot.current_alt_cap -= 1

    # Apply updates when trying an item
    def _pre_dfs_updates(self, scheduled_item: ScheduledItem):
        self._pre_dfs_slot_update(scheduled_item)
        self._curr_schedule[scheduled_item.lt.identifier] = scheduled_item
        self._curr_bounding_score += scheduled_item.b_score_contribution

    # Undo updates when backtracking
    def _post_dfs_updates(self, scheduled_item: ScheduledItem):
        self._post_dfs_slot_update(scheduled_item)
        del self._curr_schedule[scheduled_item.lt.identifier]
        self._curr_bounding_score -= scheduled_item.b_score_contribution


    # Depth first search over all schedules
    def _dfs(self, current_leaf: Node):

        # Get expansions for the current node
        expansions = self._get_expansions(current_leaf)

        # If there are no expansions and all lec/tut are assigned, update ans if best score improved
        if not expansions:
            self.num_leafs += 1 # for observability
            if len(self._curr_schedule) == len(self._input_data.lectures) + len(self._input_data.tutorials):
                self._results.append(self._curr_schedule.copy())
                if (ev := self._get_eval_score()) < self._min_eval:
                    self.ans = self._curr_schedule.copy()
                    self._min_eval = ev
            return

        # Otherwise, for each expansion, apply slot/score updates, recurse, and undo updates
        for next_item in expansions:
            new_leaf = Node(most_recent_item=next_item)
            self._pre_dfs_updates(next_item)
            self._dfs(new_leaf)
            self._post_dfs_updates(next_item)


    # Coverts best answer to a formatted string
    def get_formatted_answer(self) -> str:
        if not self.ans:
            return ""
        return _get_formatted_schedule(self.ans)


    # Starts search process
    def search(self):
        root = Node(DummyScheduledItem())
        self._dfs(root)
        return self._results, self.ans