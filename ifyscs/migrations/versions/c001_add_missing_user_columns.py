"""Add columns that _ensure_schema adds at runtime (missing from Alembic)"""
from alembic import op
import sqlalchemy as sa

revision = 'c001add_missing_user_cols'
down_revision = 'b272b9aa585e'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('avatar', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('zoom_email', sa.String(120), nullable=True))
    op.add_column('users', sa.Column('google_email', sa.String(120), nullable=True))
    op.add_column('users', sa.Column('google_oauth_token', sa.Text(), nullable=True))
    op.add_column('users', sa.Column(
        'is_super_admin', sa.Boolean(), nullable=False, server_default='false'
    ))


def downgrade():
    op.drop_column('users', 'is_super_admin')
    op.drop_column('users', 'google_oauth_token')
    op.drop_column('users', 'google_email')
    op.drop_column('users', 'zoom_email')
    op.drop_column('users', 'avatar')
