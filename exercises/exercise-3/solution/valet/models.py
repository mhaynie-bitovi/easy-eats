from dataclasses import dataclass
from enum import StrEnum

NUM_VALET_ZONES = 3


class LocationKind(StrEnum):
    PARKING_SPACE = "parking_space"
    VALET_ZONE = "valet_zone"


@dataclass
class Location:
    kind: LocationKind
    id: str


@dataclass
class ValetParkingInput:
    license_plate: str
    trip_duration_seconds: int
    valet_zone_location: Location


@dataclass
class ValetParkingOutput:
    total_bill: float | None = None


@dataclass
class MoveCarInput:
    license_plate: str
    from_location: Location
    to_location: Location


@dataclass
class MoveCarOutput:
    distance_driven: float
    start_time: str
    end_time: str


@dataclass
class RequestParkingSpaceInput:
    license_plate: str


@dataclass
class RequestParkingSpaceOutput:
    parking_space_number: str


@dataclass
class ReleaseParkingSpaceInput:
    license_plate: str


@dataclass
class ReleaseParkingSpaceOutput:
    pass


@dataclass
class ParkingLotInput:
    parking_spaces: dict[str, str | None] | None


@dataclass
class ParkingLotOutput:
    pass


@dataclass
class NotifyOwnerInput:
    license_plate: str
    message: str


@dataclass
class NotifyOwnerOutput:
    notified: bool


@dataclass
class BillCustomerInput:
    license_plate: str
    duration_seconds: int
    total_distance: float


@dataclass
class BillCustomerOutput:
    amount: float
