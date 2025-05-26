# WIP: Recreate trigger for all tables in user_data schema
# Get all tables from user_data
from sqlalchemy import create_engine, text

from src.core.config import settings

engine = create_engine(settings.POSTGRES_DATABASE_URI)


def get_tables():
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'user_data';")
        )
        tables = result.fetchall()
        return tables


def add_uuid_constraint(tables):
    with engine.connect() as conn:
        for table in tables:
            table_name = table[0]
            # Set default to basic.uuid_generate_v7() but don't recreate column
            # print(f"ALTER TABLE user_data.{table_name} ALTER COLUMN id SET DEFAULT basic.uuid_generate_v7();")
            # Check type of id column
            is_uuid = conn.execute(
                text(f"SELECT data_type FROM information_schema.columns WHERE table_name = '{table_name}' AND column_name = 'id';")
            )
            is_uuid = is_uuid.fetchone()
            # If is uuid type, set default to basic.uuid_generate_v7()
            if is_uuid[0] == "uuid":
                conn.execute(
                    text(f"ALTER TABLE user_data.{table_name} ALTER COLUMN id SET DEFAULT basic.uuid_generate_v7();")
                )
            else:
                continue
            # Commit changes


def add_trigger(tables):
    with engine.connect() as conn:
        for table in tables:
            table_name = table[0]
            table_type = table_name.split("_")[0]

            if table_type in ("point", "line", "polygon"):
                # Check if trigger exists
                trigger_exists = conn.execute(
                    text(f"SELECT trigger_name FROM information_schema.triggers WHERE trigger_name = 'trigger_{settings.USER_DATA_SCHEMA}_{table_name}';")
                )
                trigger_exists = trigger_exists.fetchone()
                if not trigger_exists:
                    # Create Trigger
                    sql_create_trigger = text(f"""CREATE TRIGGER trigger_{settings.USER_DATA_SCHEMA}_{table_name}
                        BEFORE INSERT OR UPDATE ON {settings.USER_DATA_SCHEMA}."{table_name}"
                        FOR EACH ROW EXECUTE FUNCTION basic.set_user_data_h3();
                    """)
                    conn.execute(sql_create_trigger)


# tables = get_tables()
# add_uuid_constraint(tables)
# add_trigger(tables)
