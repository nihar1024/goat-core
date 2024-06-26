import pytest
from httpx import AsyncClient

from src.core.config import settings
from src.schemas.oev_gueteklasse import station_config_example
from tests.utils import check_job_status


@pytest.mark.asyncio
async def test_compute_catchment_area_pt(client: AsyncClient, fixture_catchment_area_pt):
    assert fixture_catchment_area_pt["job_id"] is not None

@pytest.mark.asyncio
async def test_compute_catchment_area_car_layer(
    client: AsyncClient,
    fixture_add_aggregate_point_layer_to_project,
):
    project_id = fixture_add_aggregate_point_layer_to_project["project_id"]
    layer_project_id = fixture_add_aggregate_point_layer_to_project[
        "source_layer_project_id"
    ] # TODO: Switch to smaller layer with <= 50 points as this is the max for car catchment areas

    # Produce catchment area request payload
    params = {
        "starting_points": {"layer_project_id": layer_project_id},
        "routing_type": "car",
        "travel_cost": {
            "max_traveltime": 15,
            "steps": 5,
        },
        "catchment_area_type": "polygon",
        "polygon_difference": True,
    }
    response = await client.post(
        f"{settings.API_V2_STR}/motorized-mobility/car/catchment-area?project_id={project_id}",
        json=params,
    )
    assert response.status_code == 201
    # Check if job is finished
    job = await check_job_status(client, response.json()["job_id"])
    # Check if job is finished
    assert job["status_simple"] == "finished"


@pytest.mark.asyncio
async def test_compute_catchment_area_car_lat_lon(
    client: AsyncClient,
    fixture_create_project,
    fixture_create_user,
):
    project_id = fixture_create_project["id"]
    fixture_create_user["id"]

    # Produce catchment area request payload
    params = {
        "starting_points": {
            "latitude": [51.201582802561035],
            "longitude": [9.481917667178564],
        },
        "routing_type": "car",
        "travel_cost": {
            "max_traveltime": 30,
            "steps": 5,
        },
        "catchment_area_type": "polygon",
        "polygon_difference": True,
    }
    response = await client.post(
        f"{settings.API_V2_STR}/motorized-mobility/car/catchment-area?project_id={project_id}",
        json=params,
    )
    assert response.status_code == 201
    # Check if job is finished
    job = await check_job_status(client, response.json()["job_id"])
    # Check if job is finished
    assert job["status_simple"] == "finished"


@pytest.mark.asyncio
async def test_oev_gueteklasse_buffer(
    client: AsyncClient, fixture_add_polygon_layer_to_project
):
    project_id = fixture_add_polygon_layer_to_project["project_id"]
    reference_layer_project_id = fixture_add_polygon_layer_to_project[
        "layer_project_id"
    ]

    payload = {
        "time_window": {
            "weekday": "sunday",
            "from_time": 25200,
            "to_time": 32400,
        },
        "reference_area_layer_project_id": reference_layer_project_id,
        "station_config": station_config_example,
    }

    response = await client.post(
        f"{settings.API_V2_STR}/motorized-mobility/oev-gueteklassen?project_id={project_id}",
        json=payload,
    )
    assert response.status_code == 201
    assert response.json()["job_id"] is not None

    job = await check_job_status(client, response.json()["job_id"])
    assert job["status_simple"] == "finished"

@pytest.mark.asyncio
async def test_oev_gueteklasse_network(
    client: AsyncClient, fixture_add_polygon_layer_to_project
):
    project_id = fixture_add_polygon_layer_to_project["project_id"]
    reference_layer_project_id = fixture_add_polygon_layer_to_project[
        "layer_project_id"
    ]

    payload = {
        "time_window": {
            "weekday": "sunday",
            "from_time": 25200,
            "to_time": 32400,
        },
        "reference_area_layer_project_id": reference_layer_project_id,
        "station_config": station_config_example,
        "catchment_type": "network",
    }

    response = await client.post(
        f"{settings.API_V2_STR}/motorized-mobility/oev-gueteklassen?project_id={project_id}",
        json=payload,
    )
    assert response.status_code == 201
    assert response.json()["job_id"] is not None

    job = await check_job_status(client, response.json()["job_id"])
    assert job["status_simple"] == "finished"


@pytest.mark.asyncio
async def test_trip_count_station(
    client: AsyncClient, fixture_add_polygon_layer_to_project
):
    project_id = fixture_add_polygon_layer_to_project["project_id"]
    reference_layer_project_id = fixture_add_polygon_layer_to_project[
        "layer_project_id"
    ]

    payload = {
        "reference_area_layer_project_id": reference_layer_project_id,
        "time_window": {
            "weekday": "weekday",
            "from_time": 25200,
            "to_time": 32400,
        },
    }

    response = await client.post(
        f"{settings.API_V2_STR}/motorized-mobility/trip-count-station?project_id={project_id}",
        json=payload,
    )
    assert response.status_code == 201
    assert response.json()["job_id"] is not None

    job = await check_job_status(client, response.json()["job_id"])
    # Check if job is finished
    assert job["status_simple"] == "finished"


async def test_single_catchment_area_public_transport(
    client: AsyncClient, fixture_create_project
):
    project_id = fixture_create_project["id"]
    params = {
        "starting_points": {"latitude": [53.55390], "longitude": [10.01770]},
        "routing_type": {
            "mode": [
                "bus",
                "tram",
                "rail",
                "subway",
                "ferry",
                "cable_car",
                "gondola",
                "funicular",
            ],
            "egress_mode": "walk",
            "access_mode": "walk",
        },
        "travel_cost": {
            "max_traveltime": 60,
            "steps": 5,
        },
        "time_window": {
            "weekday": "weekday",
            "from_time": 25200,  # 7 AM
            "to_time": 39600,  # 9 AM
        },
        "catchment_area_type": "polygon",
        "polygon_difference": True,
    }
    response = await client.post(
        f"{settings.API_V2_STR}/motorized-mobility/pt/catchment-area?project_id={project_id}",
        json=params,
    )
    assert response.status_code == 201
    # Check if job is finished
    job = await check_job_status(client, response.json()["job_id"])
    # Check if job is finished
    assert job["status_simple"] == "finished"


async def test_nearby_station_access(client: AsyncClient, fixture_create_project):
    project_id = fixture_create_project["id"]
    params = {
        "starting_points": {"latitude": [52.5200], "longitude": [13.4050]},
        "access_mode": "walking",
        "speed": 5,
        "max_traveltime": 10,
        "mode": ["bus", "tram", "rail", "subway"],
        "time_window": {"weekday": "weekday", "from_time": 25200, "to_time": 32400},
    }
    response = await client.post(
        f"{settings.API_V2_STR}/motorized-mobility/nearby-station-access?project_id={project_id}",
        json=params,
    )
    assert response.status_code == 201
    # Check if job is finished
    job = await check_job_status(client, response.json()["job_id"])
    # Check if job is finished
    assert job["status_simple"] == "finished"
