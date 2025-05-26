from typing import List
from uuid import UUID

from sqlalchemy import text

from src.core.config import settings
from src.core.job import job_init, job_log, run_background_or_immediately
from src.crud.crud_heatmap import CRUDHeatmapBase
from src.schemas.heatmap import (
    ROUTING_MODE_DEFAULT_SPEED,
    TRAVELTIME_MATRIX_RESOLUTION,
    TRAVELTIME_MATRIX_TABLE,
    ActiveRoutingHeatmapType,
    IHeatmapClosestAverageActive,
    IHeatmapClosestAverageMotorized,
    MotorizedRoutingHeatmapType,
)
from src.schemas.job import JobStatusType
from src.schemas.layer import FeatureGeometryType, IFeatureLayerToolCreate
from src.schemas.toolbox_base import DefaultResultLayerName
from src.utils import format_value_null_sql


class CRUDHeatmapClosestAverage(CRUDHeatmapBase):
    def __init__(self, job_id, background_tasks, async_session, user_id, project_id):
        super().__init__(job_id, background_tasks, async_session, user_id, project_id)

    async def create_distributed_opportunity_table(
        self,
        routing_type: ActiveRoutingHeatmapType | MotorizedRoutingHeatmapType,
        layers: List[dict],
        scenario_id: UUID,
        opportunity_geofence_layer,
    ):
        """Create distributed table for user-specified opportunities."""

        # Create temp table name for points
        temp_points = await self.create_temp_table_name("points")

        # Create formatted opportunity geofence layer strings for SQL query
        geofence_table = (
            "NULL"
            if opportunity_geofence_layer is None
            else f"'{opportunity_geofence_layer.table_name}'"
        )
        geofence_where_filter = "NULL"
        if opportunity_geofence_layer is not None:
            geofence_where_filter = opportunity_geofence_layer.where_query.replace(
                "'", "''"
            )
            geofence_where_filter = f"'{geofence_where_filter}'"

        append_to_existing = False
        for layer in layers:
            # Compute geofence buffer distance
            geofence_buffer_dist = (
                layer["layer"].max_traveltime
                * ((ROUTING_MODE_DEFAULT_SPEED[routing_type] * 1000) / 60)
                if opportunity_geofence_layer is not None
                else "NULL"
            )

            # Create distributed point table using sql
            await self.async_session.execute(
                text(f"""SELECT basic.create_heatmap_closest_average_opportunity_table(
                    {layer["layer"].opportunity_layer_project_id},
                    '{layer["table_name"]}',
                    '{settings.CUSTOMER_SCHEMA}',
                    {format_value_null_sql(scenario_id)},
                    {geofence_table},
                    {geofence_where_filter},
                    {geofence_buffer_dist},
                    {layer["layer"].max_traveltime},
                    {layer["layer"].number_of_destinations},
                    '{layer["where_query"].replace("'", "''")}',
                    '{temp_points}',
                    {TRAVELTIME_MATRIX_RESOLUTION[routing_type]},
                    {layer["geom_type"] == FeatureGeometryType.polygon},
                    {append_to_existing}
                )""")
            )

            await self.async_session.commit()
            append_to_existing = True

        return temp_points

    def build_query(
        self,
        params: IHeatmapClosestAverageActive | IHeatmapClosestAverageMotorized,
        opportunity_table: str,
        result_table: str,
        result_layer_id: str,
    ):
        """Builds SQL query to compute heatmap closest-average."""

        query = text(f"""
            INSERT INTO {result_table} (layer_id, geom, text_attr1, float_attr1)
            WITH grouped AS (
                SELECT dest_id, (ARRAY_AGG(traveltime ORDER BY traveltime))[1:num_destinations] AS traveltime
                FROM (
                    SELECT opportunity_id, dest_id.value AS dest_id, min(traveltime) AS traveltime, num_destinations
                    FROM (
                        SELECT opportunity.id AS opportunity_id, matrix.orig_id, matrix.dest_id, matrix.traveltime, opportunity.num_destinations
                        FROM {opportunity_table} opportunity, {TRAVELTIME_MATRIX_TABLE[params.routing_type]} matrix
                        WHERE matrix.h3_3 = opportunity.h3_3
                        AND matrix.orig_id = opportunity.h3_index
                        AND matrix.traveltime <= opportunity.max_traveltime
                    ) sub_matrix
                    JOIN LATERAL UNNEST(sub_matrix.dest_id) dest_id(value) ON TRUE
                    GROUP BY opportunity_id, dest_id.value, num_destinations
                ) grouped_opportunities
                GROUP BY dest_id, num_destinations
            )
            SELECT '{result_layer_id}', ST_SetSRID(h3_cell_to_boundary(grouped.dest_id)::geometry, 4326), grouped.dest_id,
                AVG(traveltime.value) AS accessibility
            FROM grouped
            JOIN LATERAL UNNEST(grouped.traveltime) traveltime(value) ON TRUE
            GROUP BY grouped.dest_id;
        """)

        return query

    @job_log(job_step_name="heatmap_closest_average")
    async def heatmap(
        self,
        params: IHeatmapClosestAverageActive | IHeatmapClosestAverageMotorized,
    ):
        """Compute heatmap closest-average."""

        # Fetch opportunity tables
        layers, opportunity_geofence_layer = await self.fetch_opportunity_layers(params)
        opportunity_table = await self.create_distributed_opportunity_table(
            params.routing_type,
            layers,
            params.scenario_id,
            opportunity_geofence_layer,
        )

        # Initialize result table
        result_table = f"{settings.USER_DATA_SCHEMA}.{FeatureGeometryType.polygon.value}_{str(self.user_id).replace('-', '')}"

        # Create feature layer to store computed heatmap output
        layer_heatmap = IFeatureLayerToolCreate(
            name=(
                DefaultResultLayerName.heatmap_closest_average_active_mobility.value
                if type(params.routing_type) == ActiveRoutingHeatmapType
                else DefaultResultLayerName.heatmap_closest_average_motorized_mobility.value
            ),
            feature_layer_geometry_type=FeatureGeometryType.polygon,
            attribute_mapping={
                "text_attr1": "h3_index",
                "float_attr1": "accessibility",
            },
            tool_type=params.tool_type.value,
            job_id=self.job_id,
        )

        # Compute heatmap & write to result table
        await self.async_session.execute(
            self.build_query(
                params=params,
                opportunity_table=opportunity_table,
                result_table=result_table,
                result_layer_id=str(layer_heatmap.id),
            )
        )

        # Register feature layer
        await self.create_feature_layer_tool(
            layer_in=layer_heatmap,
            params=params,
        )

        return {
            "status": JobStatusType.finished.value,
            "msg": "Heatmap closest-average was successfully computed.",
        }

    @run_background_or_immediately(settings)
    @job_init()
    async def run_heatmap(
        self,
        params: IHeatmapClosestAverageActive | IHeatmapClosestAverageMotorized,
    ):
        return await self.heatmap(params=params)
