"""Create communication schema with conversation and message tables"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202501171200"
down_revision: str | None = None
branch_labels: tuple[str, ...] | None = None
depends_on: tuple[str, ...] | None = None

SCHEMA = "communication"
CHANNEL_ENUM_NAME = "channel_enum"
DIRECTION_ENUM_NAME = "direction_enum"
STATUS_ENUM_NAME = "status_enum"

CHANNEL_VALUES = ("whatsapp", "email", "web")
DIRECTION_VALUES = ("inbound", "outbound")
STATUS_VALUES = ("received", "read", "queued", "sent", "failed")

PRIMARY_KEY_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _dialect_name() -> str:
    return op.get_bind().dialect.name


def _schema_for_dialect() -> str | None:
    return SCHEMA if _dialect_name() == "postgresql" else None


def _boolean_default() -> sa.sql.elements.TextClause:
    return sa.text("true") if _dialect_name() == "postgresql" else sa.text("1")


def _enum_for_column(name: str, values: tuple[str, ...]) -> sa.Enum:
    if _dialect_name() == "postgresql":
        return sa.Enum(
            *values,
            name=name,
            schema=SCHEMA,
            create_type=False,
            validate_strings=True,
        )
    return sa.Enum(
        *values,
        name=name,
        native_enum=False,
        validate_strings=True,
    )


def _create_enum_type(name: str, values: tuple[str, ...]) -> None:
    if _dialect_name() != "postgresql":
        return
    enum = postgresql.ENUM(*values, name=name, schema=SCHEMA)
    enum.create(op.get_bind(), checkfirst=True)


def _drop_enum_type(name: str) -> None:
    if _dialect_name() != "postgresql":
        return
    enum = postgresql.ENUM(name=name, schema=SCHEMA)  # type: ignore[arg-type]
    enum.drop(op.get_bind(), checkfirst=True)


def upgrade() -> None:
    schema = _schema_for_dialect()
    dialect = _dialect_name()

    if dialect == "postgresql":
        op.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))

    _create_enum_type(CHANNEL_ENUM_NAME, CHANNEL_VALUES)
    _create_enum_type(DIRECTION_ENUM_NAME, DIRECTION_VALUES)
    _create_enum_type(STATUS_ENUM_NAME, STATUS_VALUES)

    timestamp_type = (
        postgresql.TIMESTAMP(timezone=True)
        if dialect == "postgresql"
        else sa.DateTime(timezone=True)
    )

    op.create_table(
        "conversation",
        sa.Column("id", PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True),
        sa.Column("user_identifier", sa.Text(), nullable=False),
        sa.Column(
            "channel",
            _enum_for_column(CHANNEL_ENUM_NAME, CHANNEL_VALUES),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=_boolean_default(),
        ),
        sa.Column(
            "started_at",
            timestamp_type,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("ended_at", timestamp_type, nullable=True),
        schema=schema,
    )

    op.create_index(
        "ix_conversation_user_identifier_channel_is_active",
        "conversation",
        ["user_identifier", "channel", "is_active"],
        unique=False,
        schema=schema,
    )

    op.create_index(
        "uq_conversation_active_identifier_channel",
        "conversation",
        ["user_identifier", "channel"],
        unique=True,
        schema=schema,
        postgresql_where=sa.text("is_active = true") if dialect == "postgresql" else None,
        sqlite_where=sa.text("is_active = 1") if dialect == "sqlite" else None,
    )

    conversation_fk_target = (
        f"{SCHEMA}.conversation.id" if schema else "conversation.id"
    )

    op.create_table(
        "message",
        sa.Column("id", PRIMARY_KEY_TYPE, primary_key=True, autoincrement=True),
        sa.Column(
            "conversation_id",
            PRIMARY_KEY_TYPE,
            sa.ForeignKey(conversation_fk_target, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "direction",
            _enum_for_column(DIRECTION_ENUM_NAME, DIRECTION_VALUES),
            nullable=False,
        ),
        sa.Column(
            "status",
            _enum_for_column(STATUS_ENUM_NAME, STATUS_VALUES),
            nullable=False,
        ),
        sa.Column(
            "timestamp",
            timestamp_type,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("content", sa.Text(), nullable=False),
        schema=schema,
    )

    op.create_index(
        "ix_message_conversation_id_timestamp",
        "message",
        ["conversation_id", "timestamp"],
        unique=False,
        schema=schema,
    )
    op.create_index(
        "ix_message_status_direction",
        "message",
        ["status", "direction"],
        unique=False,
        schema=schema,
    )


def downgrade() -> None:
    schema = _schema_for_dialect()
    dialect = _dialect_name()

    op.drop_index(
        "ix_message_status_direction",
        table_name="message",
        schema=schema,
    )
    op.drop_index(
        "ix_message_conversation_id_timestamp",
        table_name="message",
        schema=schema,
    )
    op.drop_table("message", schema=schema)

    op.drop_index(
        "uq_conversation_active_identifier_channel",
        table_name="conversation",
        schema=schema,
    )
    op.drop_index(
        "ix_conversation_user_identifier_channel_is_active",
        table_name="conversation",
        schema=schema,
    )
    op.drop_table("conversation", schema=schema)

    _drop_enum_type(STATUS_ENUM_NAME)
    _drop_enum_type(DIRECTION_ENUM_NAME)
    _drop_enum_type(CHANNEL_ENUM_NAME)

    if dialect == "postgresql":
        op.execute(sa.text(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE'))
