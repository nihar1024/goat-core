from enum import Enum
from typing import List

from pydantic import UUID4, BaseModel, Field, ValidationError, validator
from pygeofilter.parsers.cql2_json import parse as cql2_json_parser


class OrderEnum(str, Enum):
    ascendent = "ascendent"
    descendent = "descendent"


class ContentIdList(BaseModel):
    ids: List[UUID4]


class IntersectionGeomType(str, Enum):
    bbox = "bbox"
    draw = "draw"
    boundary = "boundary"


class IntersectionQueryMetadata(BaseModel):
    label: str | None = Field(None, description="Name of the bounday")
    geom_type: str = Field(..., description="Value of the metadata")
    buffer_size: float | None = Field(None, description="Buffer size for the boundary")


class MetaDataQuery(BaseModel):
    intersection: IntersectionQueryMetadata | None = Field(
        None, description="Intersection query"
    )


class CQLQueryObject(BaseModel):
    metadata: MetaDataQuery | None = Field(None, description="Metadata query")
    cql: dict | None = Field(None, description="CQL query")

    # Validate using cql2_json_parser(query)
    @validator("cql")
    def validate_query(cls, v):
        if v is None:
            return v
        try:
            cql2_json_parser(v)
        except Exception as e:
            raise ValidationError(f"Invalid CQL query: {e}")
        return v


class CQLQuery(BaseModel):
    """Model for CQL query."""

    query: CQLQueryObject | None = Field(None, description="CQL query")


# test = CQLQueryObject(
#     cql={
#         "op": "=",
#         "args": [{"property": "category"}, "second_category"],
#     }
# )
# print(test)

# x={'query': {'cql': {'op': '=', 'args': [{'property': 'category'}, 'second_category']}}}
# CQLQuery(**x)