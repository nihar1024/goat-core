# Standard library imports
from typing import List, Union
from uuid import UUID

# Third party imports
from fastapi import HTTPException, status
from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from src.core.layer import CRUDLayerBase
from src.core.statistics import StatisticsBase
from src.db.models._link_model import LayerProjectLink
from src.db.models.layer import Layer
from src.db.models.project import Project
from src.schemas.error import LayerNotFoundError, UnsupportedLayerTypeError
from src.schemas.layer import (
    FeatureGeometryType,
    LayerType,
)
from src.schemas.project import (
    layer_type_mapping_read,
    layer_type_mapping_update,
)
from src.schemas.toolbox_base import ColumnStatisticsOperation
from src.utils import (
    build_where,
    build_where_clause,
    search_value,
)
from src.expression_converter import QgsExpressionToSqlConverter

# Local application imports
from .base import CRUDBase


class CRUDLayerProject(CRUDLayerBase, StatisticsBase):
    async def layer_projects_to_schemas(
        self, async_session: AsyncSession, layers_project
    ):
        """Convert layer projects to schemas."""
        layer_projects_schemas = []

        # Loop through layer and layer projects
        for layer_project_tuple in layers_project:
            layer = layer_project_tuple[0]
            layer_project = layer_project_tuple[1]

            # Get layer type
            if layer.feature_layer_type is not None:
                layer_type = layer.type + "_" + layer.feature_layer_type
            else:
                layer_type = layer.type

            layer_dict = layer.dict()
            # Delete id from layer
            del layer_dict["id"]
            # Update layer with layer project
            layer_dict.update(layer_project.dict())
            layer_project = layer_type_mapping_read[layer_type](**layer_dict)

            # Get feature cnt for all feature layers and tables
            if layer_project.type in [LayerType.feature.value, LayerType.table.value]:
                feature_cnt = await self.get_feature_cnt(
                    async_session=async_session, layer_project=layer_project
                )
                layer_project.total_count = feature_cnt["total_count"]
                layer_project.filtered_count = feature_cnt.get("filtered_count")

            # Write into correct schema
            layer_projects_schemas.append(layer_project)

        return layer_projects_schemas

    async def get_layers(
        self,
        async_session: AsyncSession,
        project_id: UUID,
    ):
        """Get all layers from a project"""

        # Get all layers from project
        query = select(Layer, LayerProjectLink).where(
            LayerProjectLink.project_id == project_id,
            Layer.id == LayerProjectLink.layer_id,
        )

        # Get all layers from project
        layers_project = await self.get_multi(
            async_session,
            query=query,
        )
        layer_projects_to_schemas = await self.layer_projects_to_schemas(
            async_session, layers_project
        )
        return layer_projects_to_schemas

    async def get_by_ids(self, async_session: AsyncSession, ids: list[int]):
        """Get all layer projects links by the ids"""

        # Get all layers from project by id
        query = select(Layer, LayerProjectLink).where(
            LayerProjectLink.id.in_(ids),
        ).where(
            Layer.id == LayerProjectLink.layer_id,
        )

        # Get all layers from project
        layer_projects = await self.get_multi(
            async_session,
            query=query,
        )
        layer_projects = await self.layer_projects_to_schemas(
            async_session, layer_projects
        )
        return layer_projects

    async def get_internal(
        self,
        async_session: AsyncSession,
        id: int,
        project_id: UUID,
        expected_layer_types: List[Union[LayerType.feature, LayerType.table]] = [
            LayerType.feature
        ],
        expected_geometry_types: List[FeatureGeometryType] | None = None,
    ):
        """Get internal layer from layer project"""

        # Get layer project
        query = select(Layer, LayerProjectLink).where(
            LayerProjectLink.id == id,
            Layer.id == LayerProjectLink.layer_id,
            LayerProjectLink.project_id == project_id,
        )
        layer_project = await self.get_multi(
            db=async_session,
            query=query,
        )
        layer_project = await self.layer_projects_to_schemas(
            async_session, layer_project
        )

        # Make sure layer project exists
        if layer_project == []:
            raise LayerNotFoundError("Layer project not found")
        layer_project = layer_project[0]
        # Check if one of the expected layer types is given
        if layer_project.type not in expected_layer_types:
            raise UnsupportedLayerTypeError(
                f"Layer {layer_project.name} is not a {[layer_type.value for layer_type in expected_layer_types]} layer"
            )

        # Check if geometry type is correct
        if layer_project.type == LayerType.feature.value:
            if expected_geometry_types is not None:
                if (
                    layer_project.feature_layer_geometry_type
                    not in expected_geometry_types
                ):
                    raise UnsupportedLayerTypeError(
                        f"Layer {layer_project.name} is not a {[geom_type.value for geom_type in expected_geometry_types]} layer"
                    )

        return layer_project

    async def create(
        self,
        async_session: AsyncSession,
        project_id: UUID,
        layer_ids: List[UUID],
    ):
        """Create a link between a project and a layer"""

        # Remove duplicate layer_ids
        layer_ids = list(set(layer_ids))

        # Get number of layers in project
        layer_projects = await self.get_multi(
            async_session,
            query=select(LayerProjectLink).where(
                LayerProjectLink.project_id == project_id
            ),
        )

        # Check if maximum number of layers in project is reached. In case layer_project is empty just go on.
        if layer_projects != []:
            if len(layer_projects) + len(layer_ids) >= 300:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Maximum number of layers in project reached",
                )

        layers = await CRUDBase(Layer).get_multi(
            async_session,
            query=select(Layer).where(Layer.id.in_(layer_ids)),
        )

        if len(layers) != len(layer_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or several Layers were not found",
            )

        # Define array for layer project ids
        layer_project_ids = []

        # Create link between project and layer
        for layer in layers:
            layer = layer[0]

            # Check if layer with same name and ID already exists in project. Then the layer should be duplicated with a new name.
            layer_name = layer.name
            if layer_projects != []:
                if layer.name in [
                    layer_project[0].name for layer_project in layer_projects
                ]:
                    layer_name = "Copy from " + layer.name

            # Create layer project link
            layer_project = LayerProjectLink(
                project_id=project_id,
                layer_id=layer.id,
                name=layer_name,
                properties=layer.properties,
                other_properties=layer.other_properties,
            )

            # Add to database
            layer_project = await CRUDBase(LayerProjectLink).create(
                async_session,
                obj_in=layer_project.model_dump(),
            )
            layer_project_ids.append(layer_project.id)

        # Get project to update layer order
        project = await CRUDBase(Project).get(async_session, id=project_id)
        layer_order = project.layer_order
        # Add layer ids to the beginning of the list
        if layer_order is None:
            layer_order = layer_project_ids
        else:
            layer_order = layer_project_ids + layer_order

        # Update project layer order
        project = await CRUDBase(Project).update(
            async_session,
            db_obj=project,
            obj_in={"layer_order": layer_order},
        )
        layers = await self.get_by_ids(async_session, ids=layer_project_ids)
        return layers

    async def update(
        self,
        async_session: AsyncSession,
        id: int,
        layer_in: dict,
    ):
        """Update a link between a project and a layer"""

        # Get layer project
        layer_project_old = await self.get(
            async_session,
            id=id,
        )
        layer_id = layer_project_old.layer_id

        # Get base layer object
        layer = await CRUDBase(Layer).get(async_session, id=layer_id)
        layer_dict = layer.dict()

        # Get right schema for respective layer type
        if layer.feature_layer_type is not None:
            model_type_update = layer_type_mapping_update.get(
                layer.type + "_" + layer.feature_layer_type
            )
            model_type_read = layer_type_mapping_read.get(
                layer.type + "_" + layer.feature_layer_type
            )
        else:
            model_type_update = layer_type_mapping_update.get(layer.type)
            model_type_read = layer_type_mapping_read.get(layer.type)

        # Parse and validate the data against the model
        try:
            layer_in = TypeAdapter(model_type_update).validate_python(layer_in)
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

        if layer_project_old is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Layer project not found"
            )

        # Update layer project
        layer_project = await CRUDBase(LayerProjectLink).update(
            async_session,
            db_obj=layer_project_old,
            obj_in=layer_in,
        )
        layer_project_dict = layer_project.dict()
        del layer_dict["id"]
        # Update layer
        layer_dict.update(layer_project_dict)
        layer_project = model_type_read(**layer_dict)

        # Get feature cnt for non-raster layers
        if layer_project.type in [LayerType.feature.value, LayerType.table.value]:
            feature_cnt = await self.get_feature_cnt(
                async_session, layer_project=layer_project
            )
            layer_project.total_count = feature_cnt.get("total_count")
            layer_project.filtered_count = feature_cnt.get("filtered_count")
        return layer_project

    async def get_feature_cnt(
        self,
        async_session: AsyncSession,
        layer_project: SQLModel | BaseModel,
        where_query: str = None,
    ):
        """Get feature count for a layer or a layer project."""

        # Get feature count total
        feature_cnt = {}
        table_name = layer_project.table_name
        sql_query = f"SELECT COUNT(*) FROM {table_name} WHERE layer_id = '{str(layer_project.layer_id)}'"
        result = await async_session.execute(text(sql_query))
        feature_cnt["total_count"] = result.scalar_one()

        # Get feature count filtered
        if not where_query:
            where_query = build_where_clause([layer_project.where_query])
        else:
            where_query = build_where_clause([where_query])
        if where_query:
            sql_query = f"SELECT COUNT(*) FROM {table_name} {where_query}"
            result = await async_session.execute(text(sql_query))
            feature_cnt["filtered_count"] = result.scalar_one()
        return feature_cnt

    async def check_exceed_feature_cnt(
        self,
        async_session: AsyncSession,
        max_feature_cnt: int,
        layer,
        where_query: str,
    ):
        """Check if feature count is exceeding the defined limit."""
        feature_cnt = await self.get_feature_cnt(
            async_session=async_session, layer_project=layer, where_query=where_query
        )

        if feature_cnt.get("filtered_count") is not None:
            cnt_to_check = feature_cnt["filtered_count"]
        else:
            cnt_to_check = feature_cnt["total_count"]

        if cnt_to_check > max_feature_cnt:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Operation not supported. The layer contains more than {max_feature_cnt} features. Please apply a filter to reduce the number of features.",
            )
        return feature_cnt

    async def update_layer_id(
        self,
        async_session: AsyncSession,
        layer_id: UUID,
        new_layer_id: UUID,
    ):
        """Update layer id in layer project link."""

        # Update all layers from project by id
        query = (
            update(LayerProjectLink)
            .where(LayerProjectLink.layer_id == layer_id)
            .values(layer_id=new_layer_id)
        )

        async with async_session.begin():
            await async_session.execute(query)
            await async_session.commit()

    ##############################################
    ### Statistical endpoints
    ##############################################

    async def get_statistic_aggregation(
        self,
        async_session: AsyncSession,
        project_id: UUID,
        layer_project_id: int,
        column_name: str | None,
        operation: ColumnStatisticsOperation | None,
        group_by_column_name: str | None,
        expression: str | None,
        size: int,
        query: str,
        order: str,
    ) -> dict:
        """Get aggregated statistics for a numeric column based on the supplied group-by column and CQL-filter."""

        # Get layer project data
        layer_project = await self.get_internal(
            async_session=async_session, project_id=project_id, id=layer_project_id
        )

        mapped_statistics_field = None

        # For expression-based operations, validate columns and attribute mapping
        if expression:
            converter = QgsExpressionToSqlConverter(expression)
            column_names = converter.extract_field_names()
            for column in column_names:
                try:
                    # Check if column is in attribute mapping
                    column_mapped = search_value(layer_project.attribute_mapping, column)
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Column {column} not found in layer attribute mapping",
                    )

                # Replace original column name with mapped column name
                converter.replace_field_name(column, column_mapped)

            # Convert expression to SQL
            statistics_column_query, mapped_group_by_field = converter.translate()
        else:
            # Check if mapped statistics field is float, integer or biginteger
            mapped_statistics_field = (
                await self.check_column_statistics(
                    layer_project=layer_project,
                    column_name=column_name,
                    operation=operation,
                )
            )["mapped_statistics_field"]

            # TODO: Consider performing a data type check on the group-by column
            mapped_group_by_field = search_value(
                layer_project.attribute_mapping,
                group_by_column_name,
            )

            # Build statistics portion of select clause
            statistics_column_query = self.get_statistics_sql(
                field=mapped_statistics_field,
                operation=operation,
            )

        # Build where clause combining layer project and CQL query
        where_query = build_where_clause(
            [
                layer_project.where_query,  # Clause from the layer-project filter
                build_where(
                    id=layer_project.layer_id,
                    table_name=layer_project.table_name,
                    query=query,
                    attribute_mapping=layer_project.attribute_mapping,
                    return_basic_filter=False,
                ),  # Clause from the supplied CQL query
            ],
        )

        # Build count query
        sql_count_query = f"""
            SELECT COUNT({mapped_statistics_field if mapped_statistics_field else '*'})
            FROM {layer_project.table_name}
            {where_query};
        """
        total_count = (await async_session.execute(text(sql_count_query))).scalar_one()

        # Build final statistics queries
        group_by_clause = f"GROUP BY {mapped_group_by_field}" if mapped_group_by_field else ""
        order_mapped = {"descendent": "DESC", "ascendent": "ASC"}[order]
        sql_data_query = f"""
            SELECT *
            FROM (
                SELECT {statistics_column_query} operation_value
                    {f',{mapped_group_by_field}' if mapped_group_by_field else ''}
                FROM {layer_project.table_name}
                {where_query}
                {group_by_clause}
            ) subquery
            ORDER BY operation_value {order_mapped};
        """
        result = (await async_session.execute(text(sql_data_query))).fetchall()

        # Create a response object
        response = {
            "items": [
                {
                    "operation_value": res[0],
                    "grouped_value": res[1] if mapped_group_by_field else None,
                }
                for res in result[:size]
            ],
            "total_items": len(result),
            "total_count": total_count,
        }
        return response

    async def get_statistic_histogram(
        self,
        async_session: AsyncSession,
        project_id: UUID,
        layer_project_id: int,
        column_name: str,
        num_bins: int,
        query: str,
        order: str,
    ) -> dict:
        """Get histogram statistics for a numeric column based on the specified number of bins and CQL-filter."""

        # Get layer project data
        layer_project = await self.get_internal(
            async_session=async_session, project_id=project_id, id=layer_project_id
        )

        # Check if mapped statistics field is float, integer or biginteger
        mapped_statistics_field = (
            await self.check_column_statistics(
                layer_project=layer_project,
                column_name=column_name,
                operation=ColumnStatisticsOperation.sum,
            )
        )["mapped_statistics_field"]

        # Build where clause combining layer project and CQL query
        where_query = build_where_clause(
            [
                layer_project.where_query,  # Clause from the layer-project filter
                build_where(
                    id=layer_project.layer_id,
                    table_name=layer_project.table_name,
                    query=query,
                    attribute_mapping=layer_project.attribute_mapping,
                    return_basic_filter=False,
                ),  # Clause from the supplied CQL query
            ],
        )

        # Build statistics column metadata query
        sql_metadata_query = f"""
            SELECT COUNT(*), MIN({mapped_statistics_field}), MAX({mapped_statistics_field})
            FROM {layer_project.table_name}
            {where_query};
        """
        result = (await async_session.execute(text(sql_metadata_query))).fetchone()
        total_count, min_val, max_val = result[0], result[1], result[2]

        # Build final statistics queries
        order_mapped = {"descendent": "DESC", "ascendent": "ASC"}[order]
        sql_data_query = f"""
            WITH bins AS (
                SELECT generate_series(1, {num_bins}) AS bin_number
            ),
            histogram AS (
                SELECT
                    width_bucket({mapped_statistics_field}, {min_val}, {max_val + 1}, {num_bins}) AS bin_number,
                    COUNT(*) AS count
                FROM {layer_project.table_name}
                {where_query}
                AND {mapped_statistics_field} IS NOT NULL
                GROUP BY bin_number
            )
            SELECT
                bins.bin_number,
                ROUND(({min_val} + (bins.bin_number - 1) * ({max_val} - {min_val}) / {num_bins})::NUMERIC, 2) AS lower_bound,
                ROUND(({min_val} + bins.bin_number * ({max_val} - {min_val}) / {num_bins})::NUMERIC, 2) AS upper_bound,
                COALESCE(histogram.count, 0) AS count
            FROM bins
            LEFT JOIN histogram ON bins.bin_number = histogram.bin_number
            ORDER BY bins.bin_number {order_mapped};
        """
        result = (await async_session.execute(text(sql_data_query))).fetchall()

        # Create a response object
        missing_count = total_count - sum([res[3] for res in result])
        response = {
            "bins": [{"range": [res[1], res[2]], "count": res[3]} for res in result],
            "missing_count": missing_count,
            "total_rows": total_count,
        }
        return response


layer_project = CRUDLayerProject(LayerProjectLink)
