from typing import List
from uuid import UUID

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    status,
)
from fastapi.responses import JSONResponse
from fastapi_pagination import Page
from fastapi_pagination import Params as PaginationParams
from pydantic import UUID4
from sqlalchemy import select

from src.core.chart import read_chart_data
from src.crud.crud_layer_project import layer_project as crud_layer_project
from src.crud.crud_project import project as crud_project
from src.crud.crud_scenario import scenario as crud_scenario
from src.crud.crud_user_project import user_project as crud_user_project
from src.db.models._link_model import LayerProjectLink, ScenarioScenarioFeatureLink
from src.db.models.project import Project
from src.db.models.scenario import Scenario
from src.db.models.scenario_feature import ScenarioFeature
from src.db.session import AsyncSession
from src.deps.auth import auth_z, auth_z_lite
from src.endpoints.deps import get_db, get_scenario, get_user_id
from src.schemas.common import OrderEnum
from src.schemas.error import HTTPErrorHandler
from src.schemas.project import (
    IFeatureStandardProjectRead,
    IFeatureToolProjectRead,
    InitialViewState,
    IProjectBaseUpdate,
    IProjectCreate,
    IProjectRead,
    IRasterProjectRead,
    ITableProjectRead,
    ProjectPublicRead,
)
from src.schemas.project import (
    request_examples as project_request_examples,
)
from src.schemas.scenario import (
    IScenarioCreate,
    IScenarioFeatureCreate,
    IScenarioFeatureUpdate,
    IScenarioUpdate,
)
from src.schemas.scenario import (
    request_examples as scenario_request_examples,
)
from src.schemas.toolbox_base import ColumnStatisticsOperation
from src.utils import delete_orphans, to_feature_collection

router = APIRouter()


### Project endpoints
@router.post(
    "",
    summary="Create a new project",
    response_model=IProjectRead,
    response_model_exclude_none=True,
    status_code=201,
    dependencies=[Depends(auth_z)],
)
async def create_project(
    async_session: AsyncSession = Depends(get_db),
    user_id: UUID4 = Depends(get_user_id),
    *,
    project_in: IProjectCreate = Body(
        ..., example=project_request_examples["create"], description="Project to create"
    ),
):
    """This will create an empty project with a default initial view state. The project does not contains layers."""

    # Create project
    return await crud_project.create(
        async_session=async_session,
        project_in=Project(**project_in.model_dump(exclude_none=True), user_id=user_id),
        initial_view_state=project_in.initial_view_state,
    )


@router.get(
    "/{project_id}",
    summary="Retrieve a project by its ID",
    response_model=IProjectRead,
    response_model_exclude_none=True,
    status_code=200,
    dependencies=[Depends(auth_z)],
)
async def read_project(
    async_session: AsyncSession = Depends(get_db),
    user_=Depends(get_user_id),
    project_id: UUID4 = Path(
        ...,
        description="The ID of the project to get",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    ),
):
    """Retrieve a project by its ID."""

    # Get project
    project = await crud_project.get(async_session, id=project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return IProjectRead(**project.dict())


@router.get(
    "",
    summary="Retrieve a list of projects",
    response_model=Page[IProjectRead],
    response_model_exclude_none=True,
    status_code=200,
    dependencies=[Depends(auth_z)],
)
async def read_projects(
    async_session: AsyncSession = Depends(get_db),
    page_params: PaginationParams = Depends(),
    folder_id: UUID4 | None = Query(None, description="Folder ID"),
    user_id: UUID4 = Depends(get_user_id),
    team_id: UUID | None = Query(
        None,
        description="The ID of the team to get the layers from",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    ),
    organization_id: UUID | None = Query(
        None,
        description="The ID of the organization to get the layers from",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    ),
    search: str = Query(None, description="Searches the name of the project"),
    order_by: str = Query(
        None,
        description="Specify the column name that should be used to order. You can check the Project model to see which column names exist.",
        example="created_at",
    ),
    order: OrderEnum = Query(
        "descendent",
        description="Specify the order to apply. There are the option ascendent or descendent.",
        example="descendent",
    ),
):
    """Retrieve a list of projects."""

    projects = await crud_project.get_projects(
        async_session=async_session,
        user_id=user_id,
        folder_id=folder_id,
        page_params=page_params,
        search=search,
        order_by=order_by,
        order=order,
        team_id=team_id,
        organization_id=organization_id,
    )

    return projects


@router.put(
    "/{project_id}",
    response_model=IProjectRead,
    response_model_exclude_none=True,
    status_code=200,
    dependencies=[Depends(auth_z)],
)
async def update_project(
    async_session: AsyncSession = Depends(get_db),
    project_id: UUID4 = Path(
        ...,
        description="The ID of the project to get",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    ),
    project_in: IProjectBaseUpdate = Body(
        ..., example=project_request_examples["update"], description="Project to update"
    ),
):
    """Update base attributes of a project by its ID."""

    # Update project
    project = await crud_project.update_base(
        async_session=async_session,
        id=project_id,
        project=project_in,
    )
    return project


@router.delete(
    "/{project_id}",
    response_model=None,
    status_code=204,
    dependencies=[Depends(auth_z)],
)
async def delete_project(
    async_session: AsyncSession = Depends(get_db),
    project_id: UUID4 = Path(
        ...,
        description="The ID of the project to get",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    ),
):
    """Delete a project by its ID."""

    # Get project
    project = await crud_project.get(async_session, id=project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    # Delete project
    await crud_project.delete(db=async_session, id=project_id)
    return


@router.get(
    "/{project_id}/initial-view-state",
    response_model=InitialViewState,
    response_model_exclude_none=True,
    status_code=200,
    dependencies=[Depends(auth_z)],
)
async def read_project_initial_view_state(
    async_session: AsyncSession = Depends(get_db),
    user_id: UUID4 = Depends(get_user_id),
    project_id: UUID4 = Path(
        ...,
        description="The ID of the project to get",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    ),
):
    """Retrieve initial view state of a project by its ID."""

    # Get initial view state
    user_project = await crud_user_project.get_by_multi_keys(
        async_session, keys={"user_id": user_id, "project_id": project_id}
    )
    return user_project[0].initial_view_state


@router.put(
    "/{project_id}/initial-view-state",
    response_model=InitialViewState,
    response_model_exclude_none=True,
    status_code=200,
    dependencies=[Depends(auth_z)],
)
async def update_project_initial_view_state(
    async_session: AsyncSession = Depends(get_db),
    user_id: UUID4 = Depends(get_user_id),
    project_id: UUID4 = Path(
        ...,
        description="The ID of the project to get",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    ),
    initial_view_state: InitialViewState = Body(
        ...,
        example=project_request_examples["initial_view_state"],
        description="Initial view state to update",
    ),
):
    """Update initial view state of a project by its ID."""

    # Update project
    user_project = await crud_user_project.update_initial_view_state(
        async_session,
        user_id=user_id,
        project_id=project_id,
        initial_view_state=initial_view_state,
    )
    return user_project.initial_view_state


##############################################
### Layer endpoints
##############################################


@router.post(
    "/{project_id}/layer",
    response_model=List[
        IFeatureStandardProjectRead
        | IFeatureToolProjectRead
        | ITableProjectRead
        | IRasterProjectRead
    ],
    response_model_exclude_none=True,
    status_code=200,
    dependencies=[Depends(auth_z)],
)
async def add_layers_to_project(
    async_session: AsyncSession = Depends(get_db),
    project_id: UUID4 = Path(
        ...,
        description="The ID of the project to get",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    ),
    layer_ids: List[UUID4] = Query(
        ...,
        description="List of layer IDs to add to the project",
        example=["3fa85f64-5717-4562-b3fc-2c963f66afa6"],
    ),
):
    """Add layers to a project by its ID."""

    # Add layers to project
    layers_project = await crud_layer_project.create(
        async_session=async_session,
        project_id=project_id,
        layer_ids=layer_ids,
    )

    return layers_project


@router.get(
    "/{project_id}/layer",
    response_model=list,
    response_model_exclude_none=True,
    status_code=200,
    dependencies=[Depends(auth_z)],
)
async def get_layers_from_project(
    async_session: AsyncSession = Depends(get_db),
    project_id: UUID4 = Path(
        ...,
        description="The ID of the project to get",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    ),
):
    """Get layers from a project by its ID."""

    # Get all layers from project
    layers_project = await crud_layer_project.get_layers(
        async_session,
        project_id=project_id,
    )
    return layers_project


@router.get(
    "/{project_id}/layer/{layer_project_id}",
    response_model=IFeatureStandardProjectRead
    | IFeatureToolProjectRead
    | ITableProjectRead
    | IRasterProjectRead,
    response_model_exclude_none=True,
    status_code=200,
    dependencies=[Depends(auth_z)],
)
async def get_layer_from_project(
    async_session: AsyncSession = Depends(get_db),
    project_id: UUID4 = Path(
        ...,
        description="The ID of the project to get",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    ),
    layer_project_id: int = Path(
        ...,
        description="Layer project ID to get",
        example="1",
    ),
):
    layer_project = await crud_layer_project.get_by_ids(
        async_session, ids=[layer_project_id]
    )
    return layer_project[0]


@router.put(
    "/{project_id}/layer/{layer_project_id}",
    response_model=IFeatureStandardProjectRead
    | IFeatureToolProjectRead
    | ITableProjectRead
    | IRasterProjectRead,
    response_model_exclude_none=True,
    status_code=200,
    dependencies=[Depends(auth_z)],
)
async def update_layer_in_project(
    async_session: AsyncSession = Depends(get_db),
    project_id: UUID4 = Path(
        ...,
        description="The ID of the project to get",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    ),
    layer_project_id: int = Path(
        ...,
        description="Layer Project ID to update",
        example="1",
    ),
    layer_in: dict = Body(
        ...,
        examples=project_request_examples["update_layer"],
        description="Layer to update",
    ),
):
    """Update layer in a project by its ID."""

    # NOTE: Avoid getting layer_id from layer_in as the authorization is running against the query params.

    # Update layer in project
    layer_project = await crud_layer_project.update(
        async_session=async_session,
        id=layer_project_id,
        layer_in=layer_in,
    )
    # Update the last updated at of the project
    # Get project to update it
    project = await crud_project.get(async_session, id=project_id)

    # Update project updated_at
    await crud_project.update(
        async_session,
        db_obj=project,
        obj_in={"updated_at": layer_project.updated_at},
    )

    # Get layers in project
    return layer_project


@router.delete(
    "/{project_id}/layer",
    response_model=None,
    status_code=204,
    dependencies=[Depends(auth_z)],
)
async def delete_layer_from_project(
    async_session: AsyncSession = Depends(get_db),
    project_id: UUID4 = Path(
        ...,
        description="The ID of the project",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    ),
    layer_project_id: int = Query(
        ...,
        description="Layer ID to delete",
        example="1",
    ),
):
    """Delete layer from a project by its ID."""

    # Get layer project
    layer_project = await crud_layer_project.get(async_session, id=layer_project_id)
    if layer_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Layer project relation not found",
        )

    # Delete layer from project
    await crud_layer_project.delete(
        db=async_session,
        id=layer_project.id,
    )

    # Delete layer from project layer order
    project = await crud_project.get(async_session, id=project_id)
    layer_order = project.layer_order.copy()
    layer_order.remove(layer_project.id)

    await crud_project.update(
        async_session,
        db_obj=project,
        obj_in={"layer_order": layer_order},
    )

    return None


@router.get(
    "/{project_id}/layer/{layer_project_id}/chart-data",
    response_model=dict,
    response_model_exclude_none=True,
    status_code=200,
    dependencies=[Depends(auth_z)],
)
async def get_chart_data(
    async_session: AsyncSession = Depends(get_db),
    project_id: UUID4 = Path(
        ...,
        description="The ID of the project to get",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    ),
    layer_project_id: int = Path(
        ...,
        description="Layer Project ID to get chart data",
        example="1",
    ),
    cumsum: bool = Query(
        False,
        description="Specify if the data should be cumulated. This only works if the x-axis is a number.",
        example=False,
    ),
):
    """Get chart data from a layer in a project by its ID."""

    # Get chart data
    with HTTPErrorHandler():
        return await read_chart_data(
            async_session=async_session,
            project_id=project_id,
            layer_project_id=layer_project_id,
            cumsum=cumsum,
        )


@router.get(
    "/{project_id}/layer/{layer_project_id}/statistic-aggregation",
    summary="Get aggregated statistics for a column",
    response_model=dict,
    status_code=200,
)
async def get_statistic_aggregation(
    request: Request,
    async_session: AsyncSession = Depends(get_db),
    project_id: UUID4 = Path(
        ...,
        description="The ID of the project to get",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    ),
    layer_project_id: int = Path(
        ...,
        description="Layer Project ID to get chart data",
        example="1",
    ),
    column_name: str | None = Query(
        None,
        description="The column name to get the unique values from",
        example="name",
    ),
    operation: ColumnStatisticsOperation | None = Query(
        None,
        description="The operation to perform",
        example="sum",
    ),
    group_by_column_name: str | None = Query(
        None,
        description="The name of the column to group by",
        example="name",
    ),
    expression: str | None = Query(
        None,
        description="The QGIS expression to use for the statistic operation",
        example='sum("population")',
    ),
    size: int = Query(
        100, description="The number of grouped values to return", example=5
    ),
    query: str = Query(
        None,
        description="CQL2-Filter in JSON format",
        example={"op": "=", "args": [{"property": "category"}, "bus_stop"]},
    ),
    order: OrderEnum = Query(
        "descendent",
        description="Specify the order to apply. There are the option ascendent or descendent.",
        example="descendent",
    ),
):
    """Get aggregated statistics for a numeric column based on the supplied group-by column and CQL-filter."""

    # Check authorization status
    try:
        await auth_z_lite(request, async_session)
    except HTTPException:
        # Check publication status if unauthorized
        public_project = await crud_project.get_public_project(
            async_session=async_session,
            project_id=str(project_id),
        )
        if not public_project:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
            )

    # Ensure an operation or expression is specified
    if operation is None and expression is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An operation or expression must be specified.",
        )

    # Ensure a column name is specified for all operations except count
    if (
        operation
        and operation != ColumnStatisticsOperation.count
        and column_name is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A column name must be specified for all operations except count.",
        )

    # If an operation is specified, a group-by column name must also be specified
    if operation and group_by_column_name is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A group-by column name must be specified.",
        )

    # Ensure the size is not excessively large
    if size > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The size is limited to 100.",
        )

    with HTTPErrorHandler():
        values = await crud_layer_project.get_statistic_aggregation(
            async_session=async_session,
            project_id=project_id,
            layer_project_id=layer_project_id,
            column_name=column_name,
            operation=operation,
            group_by_column_name=group_by_column_name,
            expression=expression,
            size=size,
            query=query,
            order=order,
        )

    # Return result
    return values


@router.get(
    "/{project_id}/layer/{layer_project_id}/statistic-histogram",
    summary="Get histogram statistics for a column",
    response_model=dict,
    status_code=200,
)
async def get_statistic_histogram(
    request: Request,
    async_session: AsyncSession = Depends(get_db),
    project_id: UUID4 = Path(
        ...,
        description="The ID of the project to get",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    ),
    layer_project_id: int = Path(
        ...,
        description="Layer Project ID to get chart data",
        example="1",
    ),
    column_name: str = Query(
        ...,
        description="The column name to get the unique values from",
        example="name",
    ),
    num_bins: int = Query(
        ...,
        description="The number of bins / classes the histogram should have",
        example=5,
    ),
    query: str = Query(
        None,
        description="CQL2-Filter in JSON format",
        example={"op": "=", "args": [{"property": "category"}, "bus_stop"]},
    ),
    order: OrderEnum = Query(
        "ascendent",
        description="Specify the order to apply. There are the option ascendent or descendent.",
        example="ascendent",
    ),
):
    """Get histogram statistics for a numeric column based on the specified number of bins and CQL-filter."""

    # Check authorization status
    try:
        await auth_z_lite(request, async_session)
    except HTTPException:
        # Check publication status if unauthorized
        public_project = await crud_project.get_public_project(
            async_session=async_session,
            project_id=str(project_id),
        )
        if not public_project:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
            )

    # Ensure the number of bins is not excessively large
    if num_bins > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The number of bins is limited to 100.",
        )

    with HTTPErrorHandler():
        values = await crud_layer_project.get_statistic_histogram(
            async_session=async_session,
            project_id=project_id,
            layer_project_id=layer_project_id,
            column_name=column_name,
            num_bins=num_bins,
            query=query,
            order=order,
        )

    # Return result
    return values


##############################################
### Scenario endpoints
##############################################


@router.get(
    "/{project_id}/scenario",
    summary="Retrieve a list of scenarios",
    response_model=Page[Scenario],
    status_code=200,
    dependencies=[Depends(auth_z)],
)
async def read_scenarios(
    async_session: AsyncSession = Depends(get_db),
    page_params: PaginationParams = Depends(),
    project_id: UUID4 = Path(
        ...,
        description="The ID of the project to get",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    ),
    search: str = Query(None, description="Searches the name of the scenario"),
    order_by: str = Query(
        None,
        description="Specify the column name that should be used to order",
        example="created_at",
    ),
    order: OrderEnum = Query(
        "descendent",
        description="Specify the order to apply. There are the option ascendent or descendent.",
        example="descendent",
    ),
):
    """Retrieve a list of scenarios."""
    query = select(Scenario).where(Scenario.project_id == project_id)
    scenarios = await crud_scenario.get_multi(
        db=async_session,
        query=query,
        page_params=page_params,
        search_text={"name": search} if search else {},
        order_by=order_by,
        order=order,
    )

    return scenarios


@router.post(
    "/{project_id}/scenario",
    summary="Create scenario",
    status_code=201,
    response_model=Scenario,
    response_model_exclude_none=True,
    dependencies=[Depends(auth_z)],
)
async def create_scenario(
    async_session: AsyncSession = Depends(get_db),
    user_id: UUID4 = Depends(get_user_id),
    project_id: UUID4 = Path(
        ...,
        description="The ID of the project to create a scenario",
        example="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    ),
    scenario_in: IScenarioCreate = Body(
        ...,
        example=scenario_request_examples["create"],
        description="Scenario to create",
    ),
):
    """Create scenario."""

    return await crud_scenario.create(
        db=async_session,
        obj_in=Scenario(
            **scenario_in.model_dump(exclude_none=True),
            user_id=user_id,
            project_id=project_id,
        ).model_dump(),
    )


@router.put(
    "/{project_id}/scenario/{scenario_id}",
    summary="Update scenario",
    status_code=201,
    dependencies=[Depends(auth_z)],
)
async def update_scenario(
    async_session: AsyncSession = Depends(get_db),
    scenario: Scenario = Depends(get_scenario),
    scenario_in: IScenarioUpdate = Body(
        ...,
        example=scenario_request_examples["update"],
        description="Scenario to update",
    ),
):
    """Update scenario."""

    return await crud_scenario.update(
        db=async_session,
        db_obj=scenario,
        obj_in=scenario_in,
    )


@router.delete(
    "/{project_id}/scenario/{scenario_id}",
    summary="Delete scenario",
    status_code=204,
    dependencies=[Depends(auth_z)],
)
async def delete_scenario(
    async_session: AsyncSession = Depends(get_db),
    scenario: Scenario = Depends(get_scenario),
):
    """Delete scenario."""

    await crud_scenario.remove(db=async_session, id=scenario.id)
    # Deletes scenario features that are not linked to any scenario (orphans).
    # This can't be achieved using CASCADE because the relationship is many-to-many.
    await delete_orphans(
        async_session,
        ScenarioFeature,
        ScenarioFeature.id.key,
        ScenarioScenarioFeatureLink,
        ScenarioScenarioFeatureLink.scenario_feature_id.key,
    )
    return None


@router.get(
    "/{project_id}/scenario/{scenario_id}/features",
    summary="Retrieve a list of scenario features",
    response_class=JSONResponse,
    status_code=200,
    dependencies=[Depends(auth_z)],
)
async def read_scenario_features(
    async_session: AsyncSession = Depends(get_db),
    scenario: Scenario = Depends(get_scenario),
):
    """Retrieve a list of scenario features."""

    scenario_features = await crud_scenario.get_features(
        async_session=async_session,
        scenario_id=scenario.id,
    )

    fc = to_feature_collection(scenario_features)

    return fc


@router.post(
    "/{project_id}/layer/{layer_project_id}/scenario/{scenario_id}/features",
    summary="Create scenario features",
    response_class=JSONResponse,
    status_code=201,
    dependencies=[Depends(auth_z)],
)
async def create_scenario_features(
    async_session: AsyncSession = Depends(get_db),
    scenario: Scenario = Depends(get_scenario),
    features: List[IScenarioFeatureCreate] = Body(
        ...,
        example=scenario_request_examples["create_scenario_features"],
        description="Scenario features to create",
    ),
):
    """Create scenario features."""

    fc = await crud_scenario.create_features(
        async_session=async_session,
        user_id=scenario.user_id,
        scenario=scenario,
        features=features,
    )

    return fc


@router.put(
    "/{project_id}/layer/{layer_project_id}/scenario/{scenario_id}/features",
    summary="Update scenario features",
    status_code=201,
    dependencies=[Depends(auth_z)],
)
async def update_scenario_feature(
    async_session: AsyncSession = Depends(get_db),
    user_id: UUID4 = Depends(get_user_id),
    layer_project_id: int = Path(
        ...,
        description="Layer Project ID",
        example="1",
    ),
    scenario: Scenario = Depends(get_scenario),
    features: List[IScenarioFeatureUpdate] = Body(
        ...,
        description="Scenario features to update",
    ),
):
    """Update scenario features."""

    layer_project = await crud_layer_project.get(
        async_session, id=layer_project_id, extra_fields=[LayerProjectLink.layer]
    )
    if layer_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Layer project relation not found",
        )

    for feature in features:
        await crud_scenario.update_feature(
            async_session=async_session,
            user_id=user_id,
            layer_project=layer_project,
            scenario=scenario,
            feature=feature,
        )

    return None


@router.delete(
    "/{project_id}/layer/{layer_project_id}/scenario/{scenario_id}/features/{feature_id}",
    summary="Delete scenario feature",
    status_code=204,
    dependencies=[Depends(auth_z)],
)
async def delete_scenario_features(
    async_session: AsyncSession = Depends(get_db),
    user_id: UUID4 = Depends(get_user_id),
    layer_project_id: int = Path(
        ...,
        description="Layer Project ID",
        example="1",
    ),
    scenario: Scenario = Depends(get_scenario),
    feature_id: UUID = Path(
        ...,
        description="Feature ID to delete",
    ),
    h3_3: int | None = Query(
        None,
        description="H3 3 resolution",
        example=5,
    ),
):

    layer_project = await crud_layer_project.get(
        async_session, id=layer_project_id, extra_fields=[LayerProjectLink.layer]
    )
    if layer_project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Layer project relation not found",
        )

    await crud_scenario.delete_feature(
        async_session=async_session,
        user_id=user_id,
        layer_project=layer_project,
        scenario=scenario,
        feature_id=feature_id,
        h3_3=h3_3,
    )

    return None


##############################################
### Project public endpoints
##############################################


@router.get(
    "/{project_id}/public",
    summary="Get public project",
    response_model=ProjectPublicRead | None,
    response_model_exclude_none=True,
)
async def get_public_project(
    project_id: str,
    async_session: AsyncSession = Depends(get_db),
):
    """
    Get shared project
    """
    result = await crud_project.get_public_project(
        async_session=async_session, project_id=project_id
    )

    return result


@router.post(
    "/{project_id}/publish",
    summary="Publish a project",
    dependencies=[Depends(auth_z)],
)
async def publish_project(
    project_id: str,
    async_session: AsyncSession = Depends(get_db),
):
    """
    Publish a project
    """
    result = await crud_project.publish_project(
        async_session=async_session, project_id=project_id
    )

    return result


@router.delete(
    "/{project_id}/unpublish",
    summary="Unpublish a project",
    dependencies=[Depends(auth_z)],
)
async def unpublish_project(
    project_id: str,
    async_session: AsyncSession = Depends(get_db),
):
    """
    Unpublish a project
    """
    result = await crud_project.unpublish_project(
        async_session=async_session, project_id=project_id
    )

    return result
