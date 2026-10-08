"""Store avatar images in the database instead of on the ephemeral filesystem"""
from alembic import op
import sqlalchemy as sa

revision = 'c002_add_avatar_blob_cols'
down_revision = 'c001add_missing_user_cols'
branch_labels = None
depends_on = None

_COLUMNS = (
    ('avatar_data', sa.LargeBinary()),
    ('avatar_mime', sa.String(32)),
)


def _existing():
    bind = op.get_bind()
    return {c['name'] for c in sa.inspect(bind).get_columns('users')}


def upgrade():
    # Guarded because an earlier build added these at startup, so they may
    # already exist on databases that ran it.
    existing = _existing()
    for name, type_ in _COLUMNS:
        if name not in existing:
            op.add_column('users', sa.Column(name, type_, nullable=True))


def downgrade():
    existing = _existing()
    for name, _ in reversed(_COLUMNS):
        if name in existing:
            op.drop_column('users', name)
