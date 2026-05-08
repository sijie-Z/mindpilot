"""Add conversation branching support.

Revision ID: 002
Revises: 001
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create conversation_branches table
    op.create_table(
        'conversation_branches',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('parent_message_id', sa.String(36), sa.ForeignKey('messages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Add branch_id column to messages
    op.add_column('messages', sa.Column('branch_id', sa.String(36), sa.ForeignKey('conversation_branches.id', ondelete='SET NULL'), nullable=True))
    op.create_index('ix_messages_branch_id', 'messages', ['branch_id'])


def downgrade() -> None:
    op.drop_index('ix_messages_branch_id', table_name='messages')
    op.drop_column('messages', 'branch_id')
    op.drop_table('conversation_branches')
