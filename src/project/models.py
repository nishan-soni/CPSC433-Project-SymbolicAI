from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TypeGuard, Union
from project.csv_parsable import CSVParsable

@dataclass
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

    def increment_current_cap(self):
        self.current_cap += 1

    def decrement_current_cap(self):
        self.current_cap -= 1

    def __post_init__(self) -> None:
        time_split = self.time.split(":")
        hour = int(time_split[0])
        minute = 0 if time_split[1] == "00" else 0.5
        start_time = hour + minute

        if self.day == "MO":
            end_time = start_time + 1
        elif self.day == "TU":
            if self.identifier_suffix == "LEC":
                end_time = start_time + 1.5
            else:
                end_time = start_time + 1
        else:
            end_time = start_time + 2

        self.start_time = start_time
        self.end_time = end_time
        # identifier_suffix is set by subclasses before calling super().__post_init__()
        self.identifier = f"{self.day}{self.time}{self.identifier_suffix}"
        # current_cap already has a default; keep as-is


@dataclass
class LectureSlot(BaseSlot):
    # keeps the same positional signature as the previous LectureSlot:
    # LectureSlot(day, time, lecturemax, lecturemin, allecturemax)
    def __post_init__(self) -> None:
        self.identifier_suffix = "LEC"
        super().__post_init__()

    # backwards-compatible property names
    @property
    def lecturemax(self) -> int:
        return self.max_cap

    @lecturemax.setter
    def lecturemax(self, v: int) -> None:
        self.max_cap = v

    @property
    def lecturemin(self) -> int:
        return self.min_cap

    @lecturemin.setter
    def lecturemin(self, v: int) -> None:
        self.min_cap = v

    @property
    def allecturemax(self) -> int:
        return self.alt_max

    @allecturemax.setter
    def allecturemax(self, v: int) -> None:
        self.alt_max = v


@dataclass
class TutorialSlot(BaseSlot):
    def __post_init__(self) -> None:
        self.identifier_suffix = "TUT"
        super().__post_init__()

    # backwards-compatible property names
    @property
    def tutorialmax(self) -> int:
        return self.max_cap

    @tutorialmax.setter
    def tutorialmax(self, v: int) -> None:
        self.max_cap = v

    @property
    def tutorialmin(self) -> int:
        return self.min_cap

    @tutorialmin.setter
    def tutorialmin(self, v: int) -> None:
        self.min_cap = v

    @property
    def altutorialmax(self) -> int:
        return self.alt_max

    @altutorialmax.setter
    def altutorialmax(self, v: int) -> None:
        self.alt_max = v

@dataclass
class LecTut(CSVParsable, ABC):
    identifier: str
    alrequired: bool

@dataclass
class Lecture(LecTut):
    pass

@dataclass
class Tutorial(LecTut):
    parent_lecture_id: str = field(default="", init=False)
    def __post_init__(self) -> None:
        id_split = self.identifier.split(" ")
        if "LEC" in self.identifier:
            self.parent_lecture_id = " ".join(id_split[:4])
        else:
            self.parent_lecture_id = " ".join(id_split[:2] + ["LEC 01"])



@dataclass(frozen=True)
class NotCompatible(CSVParsable):
    id1: str
    id2: str

@dataclass
class Unwanted(CSVParsable):
    identifier: str
    day: str
    time: str

    def __post_init__(self) -> None:
        time_split = self.time.split(":")
        hour = int(time_split[0])
        minute = 0 if time_split[1] == "00" else 0.5
        start_time = hour + minute

        if self.day == "MO":
            end_time = start_time + 1
        elif self.day == "TU":
            if "TUT" in self.identifier:
                end_time = start_time + 1
            else:
                end_time = start_time + 1.5
        else:
            end_time = start_time + 2

        self.start_time = start_time
        self.end_time = end_time


@dataclass(frozen=True)
class Preference(CSVParsable):
    day: str
    time: str
    identifier: str
    pref_val: str


@dataclass(frozen=True)
class Pair(CSVParsable):
    id1: str
    id2: str


@dataclass(frozen=True)
class PartialAssignment(CSVParsable):
    identifier: str
    day: str
    time: str

LecTutSlot = Union[LectureSlot, TutorialSlot]


def is_tut(obj: "LecTut") -> TypeGuard["Tutorial"]:
    return isinstance(obj, Tutorial)

def is_lec(obj: "LecTut") -> TypeGuard["Lecture"]:
    return isinstance(obj, Lecture)