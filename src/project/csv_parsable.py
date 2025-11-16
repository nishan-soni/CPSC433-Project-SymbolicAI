from dataclasses import dataclass
from typing import NamedTuple, get_type_hints, Type, TypeVar

T = TypeVar("T", bound="CSVParsable")

class CSVParsable:
    
    @classmethod
    def from_csv(cls: Type[T], line: str) -> T:
        parts = [p.strip() for p in line.split(",")]
        hints = get_type_hints(cls)

        converted = []
        for raw, (_, ftype) in zip(parts, hints.items()):
            if ftype == bool:
                converted.append(raw.lower() in ("1", "true", "yes"))
            else:
                converted.append(ftype(raw))
        return cls(*converted)