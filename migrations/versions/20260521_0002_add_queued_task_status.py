"""
Add queued task status.

Revision ID: 20260521_0002
Revises: 20260521_0001
Create Date: 2026-05-21 00:02:00
"""

from collections.abc import Sequence

revision: str = "20260521_0002"
down_revision: str | None = "20260521_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No schema changes; task statuses are stored as strings."""


def downgrade() -> None:
    """No schema changes; task statuses are stored as strings."""
