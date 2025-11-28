from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TypeGuard, Union
from project.csv_parsable import CSVParsable


def _calc_start_end_times(time_str: str, day: str, identifier: str):
    '''
    Convert a military time string into numbers for calculations.
    Durations depends.
    Returns (start_time,end_time) as floats (e.g. '13:00' on Monday -> (13.0,14.0))
    '''
    time_split = time_str.split(":")
    hour = int(time_split[0])
    minute = 0 if time_split[1] == "00" else 0.5    # convert minutes to decimal
    start_time = hour + minute                      # e.g. "30" -> 0.5

    # Course durations based on day/type
    if day == "MO":
        end_time = start_time + 1           # monday classes = 1 hour
    elif day == "TU":
        if "TUT" in identifier:
            end_time = start_time + 1       # tuesday tutorials = 1 hour
        else:
            end_time = start_time + 1.5     # tuesday lectures = 1.5 hours
    else:
        end_time = start_time + 2           # other classes = 2 hours

    return start_time, end_time


@dataclass(slots=True)
class BaseSlot(CSVParsable):
    '''
    Time slot for lec/tuts. Parsed from CSV
    '''
    day: str
    time: str
    max_cap: int
    min_cap: int
    alt_max: int
    identifier: str = field(default="", init=False)
    start_time: float = field(init=False)
    end_time: float = field(init=False)
    current_cap: int = field(default=0, init=False)
    current_alt_cap: int = field(default=0, init=False)
    identifier_suffix = ""

    def __post_init__(self) -> None:
        self.start_time, self.end_time, =_calc_start_end_times(self.time, self.day, self.identifier_suffix)
        self.identifier = f"{self.day}{self.time}{self.identifier_suffix}"

@dataclass(slots=True)
class LectureSlot(BaseSlot):
    identifier_suffix = "LEC"   # Time slot for lecture

@dataclass(slots=True)
class TutorialSlot(BaseSlot):
    identifier_suffix = "TUT"   # Time slot for tutorial


@dataclass(slots=True)
class LecTut(CSVParsable):
    '''
    Lecture/Tutorial objects, some properties found from indentifier.
    '''
    identifier: str                                     # identifier, like "CPSC 251 ..."
    alrequired: bool                                    # whether alt section is required
    level: int = field(default=0, init=False)
    is_evening: bool = field(default=False, init=False)
    
    def __post_init__(self) -> None:
        id_split = self.identifier.split(" ")           # split identifiers (e.g. "CPSC", "251")
        self.level = int(id_split[1][0])                # course level, e.g. CPSC 251 -> level 2)
        self.is_evening = id_split[3].startswith("9")   # evening class if starts with 9?


@dataclass(slots=True)
class Lecture(LecTut):
    '''
    A lecture section.
    '''
    lecture_id: str = field(default="", init=False)

    def __post_init__(self) -> None:
        LecTut.__post_init__(self)                  # LecTut processing (see above class)
        id_split = self.identifier.split(" ")       # extract identifier info
        self.lecture_id = " ".join(id_split[:2])

@dataclass(slots=True)
class Tutorial(LecTut):
    '''
    A tutorial section. Also finds the lecture the tutorial belongs to.
    '''
    parent_lecture_id: str = field(default="", init=False)

    def __post_init__(self) -> None:
        LecTut.__post_init__(self)
        id_split = self.identifier.split(" ")
        if "LEC" in self.identifier:    
            self.parent_lecture_id = " ".join(id_split[:4])                 # if tut is with a lecture, use that
        else:
            self.parent_lecture_id = " ".join(id_split[:2] + ["LEC 01"])    # otherwise, use LEC 01




@dataclass(frozen=True, slots=True)
class NotCompatible(CSVParsable):       # For two items that shouldn't be scheduled simultaneously
    id1: str
    id2: str

@dataclass(slots=True)                  
class Unwanted(CSVParsable):            # For items unwanted at a certain time
    identifier: str
    day: str
    time: str
    start_time: float = field(init=False)
    end_time: float = field(init=False)

    def __post_init__(self) -> None:
        self.start_time, self.end_time, =_calc_start_end_times(self.time, self.day, self.identifier)


@dataclass(slots=True)
class Preference(CSVParsable):          # For items preferred at a certain time
    day: str
    time: str
    identifier: str
    pref_val: int
    start_time: float = field(init=False)
    end_time: float = field(init=False)

    def __post_init__(self) -> None:
        self.start_time, self.end_time, =_calc_start_end_times(self.time, self.day, self.identifier)


@dataclass(frozen=True, slots=True)
class Pair(CSVParsable):                # For items that should be taken together
    id1: str    
    id2: str


@dataclass(frozen=True, slots=True)
class PartialAssignment(CSVParsable):   # For partial assignments provided by input
    identifier: str
    day: str
    time: str



LecTutSlot = Union[LectureSlot, TutorialSlot]   # a slot can either be a lecture slot or a tutorial slot

def is_tut(obj: "LecTut") -> TypeGuard["Tutorial"]:
    return isinstance(obj, Tutorial)

def is_lec(obj: "LecTut") -> TypeGuard["Lecture"]:
    return isinstance(obj, Lecture)