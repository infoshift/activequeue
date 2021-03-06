"""Initial migration.

Revision ID: 50fa4d591121
Revises: None
Create Date: 2015-08-06 16:57:30.111472

"""

# revision identifiers, used by Alembic.
revision = '50fa4d591121'
down_revision = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('job',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('job_id', sa.String(length=128), nullable=True),
    sa.Column('queue', sa.String(length=255), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=True),
    sa.Column('result', sa.Text(), nullable=True),
    sa.Column('data', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('executed_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('job_id')
    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('job')
    ### end Alembic commands ###
