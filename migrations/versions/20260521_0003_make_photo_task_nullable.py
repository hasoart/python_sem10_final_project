"""
Make photo task nullable.

Revision ID: 20260521_0003
Revises: 20260521_0002
Create Date: 2026-05-21 00:03:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260521_0003"
down_revision: str | None = "20260521_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow photos to be uploaded before task creation."""
    op.drop_constraint("photos_task_id_fkey", "photos", type_="foreignkey")
    op.alter_column("photos", "task_id", nullable=True)
    op.create_foreign_key("photos_task_id_fkey", "photos", "tasks", ["task_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    """Require every photo to be linked to a task."""
    op.drop_constraint("photos_task_id_fkey", "photos", type_="foreignkey")
    op.alter_column("photos", "task_id", nullable=False)
    op.create_foreign_key("photos_task_id_fkey", "photos", "tasks", ["task_id"], ["id"], ondelete="CASCADE")
