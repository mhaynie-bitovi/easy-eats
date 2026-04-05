from dataclasses import dataclass


@dataclass
class ValetParkingInput:
    license_plate: str
    trip_duration_seconds: int


@dataclass
class MoveCarInput:
    license_plate: str
    from_location: str
    to_location: str


@dataclass
class MoveCarOutput:
    distance_driven: float
    start_time: str
    end_time: str


@dataclass
class ValetParkingOutput:
    pass
