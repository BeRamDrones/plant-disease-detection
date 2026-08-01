"""Init Schema

Revision ID: f1d8c1c4f529
Revises: 
Create Date: 2026-08-01 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = 'f1d8c1c4f529'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Ensure PostGIS is enabled
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # 3. Create 'drone' table
    op.create_table(
        'drone',
        sa.Column('drone_id', sa.String(length=100), nullable=False),
        sa.Column('model_name', sa.String(length=150), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('drone_id')
    )
    op.create_index('ix_drone_drone_id', 'drone', ['drone_id'], unique=False)

    # 4. Create 'mission' table
    op.create_table(
        'mission',
        sa.Column('mission_id', sa.Integer(), nullable=False),
        sa.Column('drone_id', sa.String(length=100), nullable=False),
        sa.Column('phase', sa.Enum('survey', 'detection', name='missionphase'), nullable=False),
        sa.Column('status', sa.Enum('scheduled', 'in_progress', 'completed', 'aborted', name='missionstatus'), nullable=False),
        sa.Column('crop_class', sa.String(length=100), nullable=True),
        sa.Column('boundary_points', geoalchemy2.types.Geometry(geometry_type='POLYGON', srid=4326, spatial_index=False), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['drone_id'], ['drone.drone_id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('mission_id')
    )
    op.create_index('ix_mission_mission_id', 'mission', ['mission_id'], unique=False)
    op.create_index('ix_mission_drone_id', 'mission', ['drone_id'], unique=False)
    # GiST index for boundary_points
    op.create_index('idx_mission_boundary_points', 'mission', ['boundary_points'], unique=False, postgresql_using='gist')

    # 5. Create 'flight_zone' table
    op.create_table(
        'flight_zone',
        sa.Column('zone_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('mission_id', sa.Integer(), nullable=False),
        sa.Column('zone_geometry', geoalchemy2.types.Geometry(geometry_type='POLYGON', srid=4326, spatial_index=False), nullable=False),
        sa.Column('zone_label', sa.String(length=50), nullable=False),
        sa.Column('crop_class', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['mission_id'], ['mission.mission_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('zone_id')
    )
    op.create_index('ix_flight_zone_zone_id', 'flight_zone', ['zone_id'], unique=False)
    op.create_index('ix_flight_zone_mission_id', 'flight_zone', ['mission_id'], unique=False)
    # GiST index for zone_geometry
    op.create_index('idx_flight_zone_zone_geometry', 'flight_zone', ['zone_geometry'], unique=False, postgresql_using='gist')

    # 6. Create 'parent_model_disease_classification' table
    op.create_table(
        'parent_model_disease_classification',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('zone_id', sa.Integer(), nullable=True),
        sa.Column('mission_id', sa.Integer(), nullable=False),
        sa.Column('detected_class', sa.String(length=100), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lon', sa.Float(), nullable=False),
        sa.Column('image_ref', sa.String(length=1000), nullable=True),
        sa.Column('model_version', sa.String(length=100), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['mission_id'], ['mission.mission_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['zone_id'], ['flight_zone.zone_id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_parent_model_disease_classification_id', 'parent_model_disease_classification', ['id'], unique=False)
    op.create_index('ix_parent_model_disease_classification_mission_id', 'parent_model_disease_classification', ['mission_id'], unique=False)
    op.create_index('ix_parent_model_disease_classification_zone_id', 'parent_model_disease_classification', ['zone_id'], unique=False)


def downgrade() -> None:
    # Drop tables
    op.drop_table('parent_model_disease_classification')
    op.drop_table('flight_zone')
    op.drop_table('mission')
    op.drop_table('drone')

    # Drop Enum types
    op.execute("DROP TYPE missionstatus")
    op.execute("DROP TYPE missionphase")
