from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.schemas.catchment_area import (
    CatchmentAreaRoutingModeActiveMobility,
    CatchmentAreaRoutingModePT,
    CatchmentAreaStreetNetwork,
)
from src.schemas.layer import ToolType
from src.schemas.toolbox_base import (
    CatchmentAreaStartingPointsBase,
    PTTimeWindow,
    check_starting_points,
    input_layer_type_line,
    input_layer_type_point,
)


class IStartingPointNearbyStationAccess(CatchmentAreaStartingPointsBase):
    """Model for the starting points of the nearby station endpoint."""

    check_starting_points = check_starting_points(1000)


class INearbyStationAccess(BaseModel):
    """Model for the nearby station endpoint."""

    starting_points: IStartingPointNearbyStationAccess = Field(
        ...,
        title="Starting Points",
        description="The starting point for the nearby station calculation.",
    )
    access_mode: CatchmentAreaRoutingModeActiveMobility = Field(
        ...,
        title="Access Mode",
        description="The access mode of the active mobility.",
    )
    speed: int = Field(
        ...,
        title="Speed",
        description="The speed in km/h.",
        ge=1,
        le=25,
    )
    max_traveltime: int = Field(
        ...,
        title="Max Travel Time",
        description="The maximum travel time in minutes.",
        ge=1,
        le=15,
    )
    mode: List[CatchmentAreaRoutingModePT] = Field(
        ...,
        title="Mode",
        description="The mode of the public transport.",
    )
    time_window: PTTimeWindow = Field(
        ...,
        title="Time Window",
        description="The time window of the catchment area.",
    )
    scenario_id: UUID | None = Field(
        None,
        title="Scenario ID",
        description="The ID of the scenario that is to be applied on the input layer or base network.",
    )
    street_network: Optional[CatchmentAreaStreetNetwork] = Field(
        None,
        title="Street Network Layer Config",
        description="The configuration of the street network layers to use.",
    )

    # Ensure at least one mode is selected
    @field_validator("mode", mode="after")
    def check_mode(cls, value: List[CatchmentAreaRoutingModePT]):
        if not value or len(value) == 0:
            raise ValueError("At least one mode must be selected.")
        return value

    @property
    def tool_type(self):
        return ToolType.nearby_station_access

    @property
    def input_layer_types(self):
        return {
            "layer_project_id": input_layer_type_point,
            "edge_layer_project_id": input_layer_type_line,
            "node_layer_project_id": input_layer_type_point,
        }

    @property
    def geofence_table(self):
        return "basic.geofence_pt"


request_example_nearby_station_access = {
    "single_point_nearby_station": {
        "summary": "Nearby station for a single starting point",
        "value": {
            "starting_points": {"latitude": [52.5200], "longitude": [13.4050]},
            "access_mode": "walking",
            "speed": 5,
            "max_traveltime": 10,
            "mode": ["bus", "tram", "rail", "subway"],
            "time_window": {"weekday": "weekday", "from_time": 25200, "to_time": 32400},
        },
    }
}
