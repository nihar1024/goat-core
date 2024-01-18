from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends

from src.core.tool import start_calculation
from src.crud.crud_isochrone import CRUDIsochronePT
from src.crud.crud_motorized_mobility import CRUDOevGueteklasse
from src.db.session import AsyncSession
from src.endpoints.deps import get_db, get_http_client, get_user_id
from src.schemas.job import JobType
from src.schemas.motorized_mobility import (
    IIsochroneCar,
    IIsochronePT,
    IOevGueteklasse,
    request_example_oev_gueteklasse,
    request_examples_isochrone_car,
    request_examples_isochrone_pt,
)
from src.schemas.toolbox_base import CommonToolParams, IToolResponse

router = APIRouter()


@router.post(
    "/pt/isochrone",
    summary="Compute isochrones for public transport.",
    response_model=IToolResponse,
    status_code=201,
)
async def compute_pt_isochrone(
    *,
    common: CommonToolParams = Depends(),
    params: IIsochronePT = Body(
        ...,
        examples=request_examples_isochrone_pt,
        description="The isochrone parameters.",
    ),
):
    """Compute isochrones for public transport."""
    return await start_calculation(
        job_type=JobType.isochrone_pt,
        tool_class=CRUDIsochronePT,
        crud_method="run_isochrone",
        async_session=common.async_session,
        user_id=common.user_id,
        background_tasks=common.background_tasks,
        project_id=common.project_id,
        params=params,
        http_client=get_http_client(),
    )


@router.post(
    "/car/isochrone",
    summary="Compute isochrones for car.",
    response_model=IToolResponse,
    status_code=201,
)
async def compute_car_isochrone(
    *,
    async_session: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_user_id),
    params: IIsochroneCar = Body(
        ...,
        examples=request_examples_isochrone_car,
        description="The isochrone parameters.",
    ),
):
    """Compute isochrones for car."""
    return {"job_id": uuid4()}


@router.post(
    "/oev-gueteklassen",
    summary="Calculate ÖV-Güteklassen.",
    response_model=IToolResponse,
    status_code=201,
)
async def calculate_oev_gueteklassen(
    *,
    common: CommonToolParams = Depends(),
    params: IOevGueteklasse = Body(..., examples=request_example_oev_gueteklasse),
):
    """
    ÖV-Güteklassen (The public transport quality classes) is an indicator for access to public transport.
    The indicator makes it possible to identify locations which, thanks to their good access to public transport, have great potential as focal points for development.
    The calculation in an automated process from the data in the electronic timetable (GTFS).
    """

    return await start_calculation(
        job_type=JobType.oev_gueteklasse,
        tool_class=CRUDOevGueteklasse,
        crud_method="oev_gueteklasse",
        async_session=common.async_session,
        user_id=common.user_id,
        background_tasks=common.background_tasks,
        project_id=common.project_id,
        params=params,
    )
