"""baseline (empty)

Revision ID: bb678cb2bb05
Revises:
Create Date: 2025-08-27 15:32:24.722593

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "bb678cb2bb05"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
