"""Initial Citus-sharded schema: users, matches, match_participants.

Server_Design.md §5 (ADR-001): users hash-distributed by id; matches
distributed by white_user_id; match_participants (one row per side, new
table) distributed by user_id so "my match history" stays a single-shard
read. Plain `CREATE TABLE` first (Alembic/SQLAlchemy has no
Citus-specific DDL), then `create_distributed_table(...)` per table —
requires the coordinator to already know about its workers, which
deploy/citus/register-workers.sh does before this migration runs.

Revision ID: 0001
Revises:
Create Date: 2026-07-28
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citus")

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("salt", sa.Text(), nullable=False),
        sa.Column("elo", sa.Integer(), nullable=False, server_default="1200"),
        sa.Column("created_at", sa.DOUBLE_PRECISION(), nullable=False),
        sa.UniqueConstraint("id", "username", name="uq_users_id_username"),
    )
    op.create_index("ix_users_username", "users", ["username"])

    # Citus requires every unique/primary-key constraint on a distributed
    # table to include the distribution column. `id` therefore cannot be a
    # standalone primary key here (distribution column is white_user_id,
    # not id) — it's an Identity column with a composite unique constraint
    # instead, which is the standard Citus pattern for this shape of table.
    op.create_table(
        "matches",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("white_user_id", sa.BigInteger(), nullable=False),
        sa.Column("black_user_id", sa.BigInteger(), nullable=False),
        sa.Column("winner_user_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("ended_at", sa.DOUBLE_PRECISION(), nullable=False),
        sa.UniqueConstraint("id", "white_user_id", name="uq_matches_id_white_user_id"),
    )

    op.create_table(
        "match_participants",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("match_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("color", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("elo_delta", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("id", "user_id", name="uq_match_participants_id_user_id"),
    )
    op.create_index("ix_match_participants_user_id", "match_participants", ["user_id"])
    op.create_index("ix_match_participants_match_id", "match_participants", ["match_id"])

    op.execute("SELECT create_distributed_table('users', 'id')")
    op.execute("SELECT create_distributed_table('matches', 'white_user_id')")
    op.execute("SELECT create_distributed_table('match_participants', 'user_id')")


def downgrade() -> None:
    op.drop_table("match_participants")
    op.drop_table("matches")
    op.drop_table("users")
