from typing import Any, Optional
from uuid import UUID

import boto3
from pydantic import PostgresDsn, ValidationInfo, field_validator
from pydantic_settings import BaseSettings


class AsyncPostgresDsn(PostgresDsn):
    allowed_schemes = {"postgres+psycopg", "postgresql+psycopg"}


# For old versions of SQLAlchemy (< 1.4)
class SyncPostgresDsn(PostgresDsn):
    allowed_schemes = {"postgresql", "postgresql+psycopg2", "postgresql+pg8000"}


class Settings(BaseSettings):
    AUTH: Optional[bool] = True
    TEST_MODE: Optional[bool] = False
    ENVIRONMENT: Optional[str] = "dev"
    API_V2_STR: str = "/api/v2"
    DATA_DIR: str = "/app/data"
    TEST_DATA_DIR: str = "/app/tests/data"
    PROJECT_NAME: str = "GOAT Core API"
    USER_DATA_SCHEMA: Optional[str] = "user_data"
    CUSTOMER_SCHEMA: Optional[str] = "customer"
    ACCOUNTS_SCHEMA: Optional[str] = "accounts"
    REGION_MAPPING_PT_TABLE: Optional[str] = "basic.region_mapping_pt"
    BASE_STREET_NETWORK: Optional[UUID] = UUID("903ecdca-b717-48db-bbce-0219e41439cf")

    JOB_TIMEOUT_DEFAULT: int = 120
    ASYNC_CLIENT_DEFAULT_TIMEOUT: Optional[float] = (
        10.0  # Default timeout for async http client
    )
    ASYNC_CLIENT_READ_TIMEOUT: Optional[float] = (
        30.0  # Read timeout for async http client
    )
    CRUD_NUM_RETRIES: Optional[int] = 30  # Number of times to retry calling an endpoint
    CRUD_RETRY_INTERVAL: Optional[int] = 3  # Number of seconds to wait between retries

    HEATMAP_GRAVITY_MAX_SENSITIVITY: int = 1000000

    SENTRY_DSN: Optional[str] = None
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: Optional[int] = 5432

    POSTGRES_DATABASE_URI: Optional[str] = None

    @field_validator("POSTGRES_DATABASE_URI", mode="after")
    def postgres_database_uri_(cls, value: Optional[str], info: ValidationInfo) -> str:
        if value:
            return value
        return f'postgresql://{info.data.get("POSTGRES_USER")}:{info.data.get("POSTGRES_PASSWORD")}@' \
            f'{info.data.get("POSTGRES_SERVER")}:{info.data.get("POSTGRES_PORT")}/{info.data.get("POSTGRES_DB")}'

    ASYNC_SQLALCHEMY_DATABASE_URI: Optional[str] = None

    @field_validator("ASYNC_SQLALCHEMY_DATABASE_URI", mode="after")
    def assemble_async_db_connection(cls, value: Optional[str], info: ValidationInfo) -> str:
        if value:
            return value
        return str(AsyncPostgresDsn.build(
            scheme="postgresql+psycopg",
            username=info.data.get("POSTGRES_USER"),
            password=info.data.get("POSTGRES_PASSWORD"),
            host=info.data.get("POSTGRES_SERVER"),
            port=info.data.get("POSTGRES_PORT"),
            path=f"{info.data.get('POSTGRES_DB') or ''}",
        ))

    # R5 config
    R5_WORKER_VERSION: str = "v7.0"
    R5_VARIANT_INDEX: int = -1
    R5_AUTHORIZATION: Optional[str] = None

    @field_validator("R5_AUTHORIZATION", mode="after")
    def r5_authorization(cls, value: Optional[str], info: ValidationInfo) -> Any:
        if value:
            return f"Basic {value}"
        return None

    # GOAT GeoAPI config
    GOAT_GEOAPI_HOST: Optional[str] = None

    # GOAT Routing config
    GOAT_ROUTING_HOST: str
    GOAT_ROUTING_PORT: int

    GOAT_ROUTING_URL: Optional[str] = None
    @field_validator("GOAT_ROUTING_URL", mode="after")
    def goat_routing_url(cls, value: Optional[str], info: ValidationInfo) -> str:
        if value:
            return value
        return f'{info.data.get("GOAT_ROUTING_HOST")}:{info.data.get("GOAT_ROUTING_PORT")}/api/v2/routing'

    GOAT_ROUTING_AUTHORIZATION: Optional[str] = None

    @field_validator("GOAT_ROUTING_AUTHORIZATION", mode="after")
    def goat_routing_authorization(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        if value:
            return f"Basic {value}"
        return None

    SAMPLE_AUTHORIZATION: str = "Bearer eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICI0OG80Z1JXelh3YXBTY3NTdHdTMXZvREFJRlNOa0NtSVFpaDhzcEJTc2kwIn0.eyJleHAiOjE2OTEwMDQ1NTYsImlhdCI6MTY5MTAwNDQ5NiwiYXV0aF90aW1lIjoxNjkxMDAyNjIzLCJqdGkiOiI1MjBiN2RhNC0xYmM0LTRiM2QtODY2ZC00NDU0ODY2YThiYjIiLCJpc3MiOiJodHRwczovL2Rldi5hdXRoLnBsYW40YmV0dGVyLmRlL3JlYWxtcy9tYXN0ZXIiLCJzdWIiOiI3NDRlNGZkMS02ODVjLTQ5NWMtOGIwMi1lZmViY2U4NzUzNTkiLCJ0eXAiOiJCZWFyZXIiLCJhenAiOiJzZWN1cml0eS1hZG1pbi1jb25zb2xlIiwibm9uY2UiOiJjNGIzMDQ3Yi0xODVmLTQyOWEtOGZlNS1lNDliNTVhMzE3MzIiLCJzZXNzaW9uX3N0YXRlIjoiMzk5ZTc2NWMtYjM1MC00NDEwLTg4YTMtYjU5NDIyMmJkZDlhIiwiYWNyIjoiMCIsImFsbG93ZWQtb3JpZ2lucyI6WyJodHRwczovL2Rldi5hdXRoLnBsYW40YmV0dGVyLmRlIl0sInNjb3BlIjoib3BlbmlkIGVtYWlsIHByb2ZpbGUiLCJzaWQiOiIzOTllNzY1Yy1iMzUwLTQ0MTAtODhhMy1iNTk0MjIyYmRkOWEiLCJlbWFpbF92ZXJpZmllZCI6ZmFsc2UsInByZWZlcnJlZF91c2VybmFtZSI6InA0YiJ9.mjywr9Dv19egsXwM1fK6g3sZ0trk87X0tEfK7oOizuBuCdkr6PZN1Eg58FCdjIgEBXqjltOWV43UIkXde4iPVa-KU5Q34Qjv6w0STa3Aq9vFbaUfSm_690qCdr8XSKMJUWQXWYwD2cjck5UCqf7-QqsF2Ab56i40_CJLZkJOi25WKIC855qPDi8BkJgh5eWoxobdyCbwJMEeoM-3QnxY5ikib5a2_AASEN3_5MYmT6-fvpW2t-MS6u4vtcG-WfqriK8YNoGPS2a1pFjLqQLHkM__j0O_t4wXP56x9yjkUdHCXqVcSlDvZYNWrv5CLqecqjOoliNMs6RTu9gV0Gr-cA"
    KEYCLOAK_SERVER_URL: Optional[str] = "http://auth-keycloak:8080"
    REALM_NAME: Optional[str] = "p4b"
    CELERY_TASK_TIME_LIMIT: Optional[int] = 60  # seconds
    RUN_AS_BACKGROUND_TASK: Optional[bool] = True
    MAX_NUMBER_PARALLEL_JOBS: Optional[int] = 6
    TESTING: Optional[bool] = False
    MAX_FOLDER_COUNT: Optional[int] = 100

    MAPBOX_TOKEN: Optional[str] = None
    MAPTILER_TOKEN: Optional[str] = None
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: Optional[str] = "eu-central-1"
    AWS_S3_ASSETS_BUCKET: Optional[str] = "plan4better-assets"

    S3_CLIENT: Optional[Any] = None

    @field_validator("S3_CLIENT", mode="after")
    def assemble_s3_client(cls, value: Optional[str], info: ValidationInfo) -> Any:
        if value:
            return value
        return boto3.client(
            "s3",
            aws_access_key_id=info.data.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=info.data.get("AWS_SECRET_ACCESS_KEY"),
            region_name=info.data.get("AWS_REGION"),
        )

    DEFAULT_PROJECT_THUMBNAIL: Optional[str] = (
        "https://assets.plan4better.de/img/goat_new_project_artwork.png"
    )
    DEFAULT_LAYER_THUMBNAIL: Optional[str] = (
        "https://assets.plan4better.de/img/goat_new_dataset_thumbnail.png"
    )
    DEFAULT_REPORT_THUMBNAIL: Optional[str] = (
        "https://goat-app-assets.s3.eu-central-1.amazonaws.com/logos/goat_green.png"
    )
    ASSETS_URL: Optional[str] = None

    THUMBNAIL_DIR_LAYER: Optional[str] = None

    @field_validator("THUMBNAIL_DIR_LAYER", mode="after")
    def set_thumbnail_dir_layer(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        environment = info.data.get("ENVIRONMENT", "dev")
        if value is None:
            return f"img/users/{environment}/thumbnails/layer"
        return value

    THUMBNAIL_DIR_PROJECT: Optional[str] = None

    @field_validator("THUMBNAIL_DIR_PROJECT", mode="after")
    def set_thumbnail_dir_project(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        environment = info.data.get("ENVIRONMENT", "dev")
        if value is None:
            return f"img/users/{environment}/thumbnails/project"
        return value

    MARKER_DIR: Optional[str] = "icons/maki"
    MARKER_PREFIX: Optional[str] = "goat-marker-"

    class Config:
        case_sensitive = True


settings = Settings()
