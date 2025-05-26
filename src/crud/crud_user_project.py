from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models._link_model import UserProjectLink
from src.db.models.project import Project
from src.schemas.project import InitialViewState

from .base import CRUDBase


class CRUDUserProject(CRUDBase):
    async def update_initial_view_state(
        self,
        async_session: AsyncSession,
        project_id: UUID,
        user_id: UUID,
        initial_view_state: InitialViewState,
    ) -> UserProjectLink:
        """Update the initial view state of a project for a user"""

        # Get existing user project relation
        user_project = await self.get_by_multi_keys(
            async_session,
            keys={"user_id": user_id, "project_id": project_id},
        )
        if user_project == []:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User project not found"
            )

        # Update initial view state
        user_project = await self.update(
            async_session,
            db_obj=user_project[0],
            obj_in={"initial_view_state": initial_view_state.model_dump()},
        )
        # Get project
        project = await CRUDBase(Project).get(async_session, id=project_id)

        # Update project updated_at
        await CRUDBase(Project).update(
            async_session,
            db_obj=project,
            obj_in={"updated_at": user_project.updated_at},
        )

        return user_project


user_project = CRUDUserProject(UserProjectLink)
