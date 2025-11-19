from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TypeGuard, Union
from project.csv_parsable import CSVParsable


def _calc_start_end_times(time_str: str, day: str, identifier: str):
    time_split = time_str.split(":")
    hour = int(time_split[0])
    minute = 0 if time_split[1] == "00" else 0.5
    start_time = hour + minute

    if day == "MO":
        end_time = start_time + 1
    elif day == "TU":
        if "TUT" in identifier:
            end_time = start_time + 1
        else:
            end_time = start_time + 1.5
    else:
        end_time = start_time + 2

    return start_time, end_time

@dataclass(slots=True)
class BaseSlot(CSVParsable):
    day: str
    time: str
    max_cap: int
    min_cap: int
    alt_max: int
    identifier: str = field(default="", init=False)
    identifier_suffix: str = field(default="", init=False)
    start_time: float = field(init=False)
    end_time: float = field(init=False)
    current_cap: int = field(default=0, init=False)
    current_alt_cap: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.start_time, self.end_time, =_calc_start_end_times(self.time, self.day, self.identifier_suffix)
        self.identifier = f"{self.day}{self.time}{self.identifier_suffix}"

@dataclass(slots=True)
class LectureSlot(BaseSlot):
    identifier_suffix = "LEC"

@dataclass(slots=True)
class TutorialSlot(BaseSlot):
    identifier_suffix = "TUT"

@dataclass(slots=True)
class LecTut(CSVParsable):
    identifier: str
    alrequired: bool
    level: int = field(default=0, init=False)
    is_evening: bool = field(default=False, init=False)
    
    def __post_init__(self) -> None:
        id_split = self.identifier.split(" ")
        self.level = int(id_split[1][0])
        self.is_evening = self.level == 9

@dataclass(slots=True)
class Lecture(LecTut):
    lecture_id: str = field(default="", init=False)
    def __post_init__(self) -> None:
        LecTut.__post_init__(self)
        id_split = self.identifier.split(" ")
        self.lecture_id = " ".join(id_split[:2])

@dataclass(slots=True)
class Tutorial(LecTut):
    parent_lecture_id: str = field(default="", init=False)
    def __post_init__(self) -> None:
        LecTut.__post_init__(self)
        id_split = self.identifier.split(" ")
        if "LEC" in self.identifier:
            self.parent_lecture_id = " ".join(id_split[:4])
        else:
            self.parent_lecture_id = " ".join(id_split[:2] + ["LEC 01"])


@dataclass(frozen=True, slots=True)
class NotCompatible(CSVParsable):
    id1: str
    id2: str

@dataclass(slots=True)
class Unwanted(CSVParsable):
    identifier: str
    day: str
    time: str
    start_time: float = field(init=False)
    end_time: float = field(init=False)

    def __post_init__(self) -> None:
        self.start_time, self.end_time, =_calc_start_end_times(self.time, self.day, self.identifier)


@dataclass(slots=True)
class Preference(CSVParsable):
    day: str
    time: str
    identifier: str
    pref_val: int
    start_time: float = field(init=False)
    end_time: float = field(init=False)

    def __post_init__(self) -> None:
        self.start_time, self.end_time, =_calc_start_end_times(self.time, self.day, self.identifier)


@dataclass(frozen=True, slots=True)
class Pair(CSVParsable):
    id1: str
    id2: str


@dataclass(frozen=True, slots=True)
class PartialAssignment(CSVParsable):
    identifier: str
    day: str
    time: str

LecTutSlot = Union[LectureSlot, TutorialSlot]


def is_tut(obj: "LecTut") -> TypeGuard["Tutorial"]:
    return isinstance(obj, Tutorial)

def is_lec(obj: "LecTut") -> TypeGuard["Lecture"]:
    return isinstance(obj, Lecture)