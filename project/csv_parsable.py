from dataclasses import dataclass
from typing import NamedTuple, get_type_hints, Type, TypeVar


T = TypeVar("T", bound="CSVParsable") # Generic type var that inherits CSVParsable


class CSVParsable:

    @classmethod
    def from_csv(cls: Type[T], line: str) -> T:
        '''Creates an instance of a class from csv format, and returns the class instance'''
        
        parts = [p.strip() for p in line.split(",")]    # Split the csv line and remove whitespace
        hints = get_type_hints(cls)                     # Get the types of the subclass

        converted = []

        # Loop through CSV parts
        for raw, (_, ftype) in zip(parts, hints.items()):
            if ftype == bool:
                converted.append(raw.lower() in ("1", "true", "yes"))   # Convert any booleans (everything but 1, true, and yes is false)
            else:
                converted.append(ftype(raw))                            # Convert using the type
        
        return cls(*converted) # Creates an instance of the class using the converted values
