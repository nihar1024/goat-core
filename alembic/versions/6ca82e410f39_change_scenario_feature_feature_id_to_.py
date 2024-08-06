"""change scenario_feature feature_id to bigint

Revision ID: 6ca82e410f39
Revises: e99c8bdebbf7
Create Date: 2024-07-21 11:32:06.112104

"""
from alembic import op
import sqlalchemy as sa
import geoalchemy2
import sqlmodel  



# revision identifiers, used by Alembic.
revision = '6ca82e410f39'
down_revision = 'e99c8bdebbf7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('scenario_feature', 'feature_id',
               existing_type=sa.INTEGER(),
               type_=sa.BigInteger(),
               existing_nullable=True,
               schema='customer')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('scenario_feature', 'feature_id',
               existing_type=sa.BigInteger(),
               type_=sa.INTEGER(),
               existing_nullable=True,
               schema='customer')
    # ### end Alembic commands ###