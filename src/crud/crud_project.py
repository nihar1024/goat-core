import json
from uuid import UUID

from fastapi_pagination import Page
from fastapi_pagination import Params as PaginationParams
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.content import (
    build_shared_with_object,
    create_query_shared_content,
    update_content_by_id,
)
from src.crud.base import CRUDBase
from src.crud.crud_layer_project import layer_project as crud_layer_project
from src.crud.crud_user_project import user_project as crud_user_project
from src.db.models import (
    Organization,
    Project,
    ProjectOrganizationLink,
    ProjectTeamLink,
    Role,
    Team,
)
from src.db.models._link_model import UserProjectLink
from src.db.models.project import ProjectPublic
from src.schemas.common import OrderEnum
from src.schemas.project import (
    InitialViewState,
    IProjectBaseUpdate,
    IProjectRead,
    ProjectPublicConfig,
    ProjectPublicProjectConfig,
    ProjectPublicRead,
)


class CRUDProject(CRUDBase):
    async def create(
        self,
        async_session: AsyncSession,
        project_in: Project,
        initial_view_state: InitialViewState,
    ) -> IProjectRead:
        """Create project"""

        # Create project
        project = await CRUDBase(Project).create(
            db=async_session,
            obj_in=project_in,
        )
        # Default initial view state
        initial_view_state = {
            "zoom": 5,
            "pitch": 0,
            "bearing": 0,
            "latitude": 51.01364693631891,
            "max_zoom": 20,
            "min_zoom": 0,
            "longitude": 9.576740589534126,
        }

        # Create link between user and project for initial view state
        await crud_user_project.create(
            async_session,
            obj_in=UserProjectLink(
                user_id=project.user_id,
                project_id=project.id,
                initial_view_state=initial_view_state,
            ).model_dump(),
        )
        # If not in testing environment add default layers to project
        if not settings.TESTING:
            # Add network layer to project
            await crud_layer_project.create(
                async_session=async_session,
                project_id=project.id,
                layer_ids=[settings.BASE_STREET_NETWORK],
            )
        # Doing unneeded type conversion to make sure the relations of project are not loaded
        return IProjectRead(**project.dict())

    async def get_projects(
        self,
        async_session: AsyncSession,
        user_id: UUID,
        page_params: PaginationParams,
        folder_id: UUID = None,
        search: str = None,
        order_by: str = None,
        order: OrderEnum = None,
        ids: list = None,
        team_id: UUID = None,
        organization_id: UUID = None,
    ) -> Page[IProjectRead]:
        """Get projects for a user and folder"""

        # Build query and filters
        if team_id or organization_id:
            filters = []
        elif folder_id:
            filters = [
                Project.user_id == user_id,
                Project.folder_id == folder_id,
            ]
        else:
            filters = [Project.user_id == user_id]

        if ids:
            query = select(Project).where(Project.id.in_(ids))
        else:
            query = create_query_shared_content(
                Project,
                ProjectTeamLink,
                ProjectOrganizationLink,
                Team,
                Organization,
                Role,
                filters,
                team_id=team_id,
                organization_id=organization_id,
            )

        # Get roles
        roles = await CRUDBase(Role).get_all(
            async_session,
        )
        role_mapping = {role.id: role.name for role in roles}

        # Get projects
        projects = await self.get_multi(
            async_session,
            query=query,
            page_params=page_params,
            search_text={"name": search} if search else {},
            order_by=order_by,
            order=order,
        )
        projects.items = build_shared_with_object(
            items=projects.items,
            role_mapping=role_mapping,
            team_key="team_links",
            org_key="organization_links",
            model_name="project",
            team_id=team_id,
            organization_id=organization_id,
        )
        return projects

    async def update_base(
        self, async_session: AsyncSession, id: UUID, project: IProjectBaseUpdate
    ) -> IProjectRead:
        """Update project base"""

        # Update project
        project = await update_content_by_id(
            async_session=async_session,
            id=id,
            model=Project,
            crud_content=self,
            content_in=project,
        )

        return IProjectRead(**project.dict())

    async def get_public_project(
        self, *, async_session: AsyncSession, project_id: str
    ) -> ProjectPublicRead | None:
        project_public = select(ProjectPublic).where(
            ProjectPublic.project_id == project_id
        )
        result = await async_session.execute(project_public)
        project = result.scalars().first()
        if not project:
            return None
        project_public_read = ProjectPublicRead(**project.dict())
        return project_public_read

    async def publish_project(
        self, *, async_session: AsyncSession, project_id: str
    ) -> ProjectPublic:
        project = select(Project).where(Project.id == project_id)
        project = await async_session.execute(project)
        project: Project | None = project.scalars().first()
        if not project:
            raise Exception("Project not found")
        project_public = select(ProjectPublic).where(
            ProjectPublic.project_id == project_id
        )
        project_public = await async_session.execute(project_public)
        project_public: ProjectPublic | None = project_public.scalars().first()
        user_project = select(UserProjectLink).where(
            and_(
                UserProjectLink.project_id == project_id,
                Project.user_id == UserProjectLink.user_id,
            )
        )
        user_project = await async_session.execute(user_project)
        user_project: UserProjectLink = user_project.scalars().first()
        if project_public:
            await async_session.delete(project_public)

        project_layers = await crud_layer_project.get_layers(
            async_session=async_session, project_id=project_id
        )

        new_project_public_project_config = ProjectPublicProjectConfig(
            id=project.id,
            name=project.name,
            description=project.description,
            tags=project.tags,
            thumbnail_url=project.thumbnail_url,
            initial_view_state=user_project.initial_view_state,
            basemap=project.basemap,
            layer_order=project.layer_order,
            max_extent=project.max_extent,
            folder_id=project.folder_id,
            builder_config=project.builder_config,
        )
        new_project_public_config = ProjectPublicConfig(
            layers=project_layers,
            project=new_project_public_project_config,
        )
        new_project_public = ProjectPublic(
            project_id=project_id, config=json.loads(new_project_public_config.json())
        )

        async_session.add(new_project_public)
        await async_session.commit()
        return new_project_public

    async def unpublish_project(
        self, *, async_session: AsyncSession, project_id: str
    ) -> None:
        public_project = select(ProjectPublic).where(
            ProjectPublic.project_id == project_id
        )
        public_project = await async_session.execute(public_project)
        public_project = public_project.scalars().first()
        if public_project:
            await async_session.delete(public_project)
            await async_session.commit()
        else:
            raise Exception("Project not found")
        return None


project = CRUDProject(Project)
