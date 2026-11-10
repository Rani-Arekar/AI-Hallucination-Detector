from alembic import op
import sqlalchemy as sa

revision = "0001_create_analyses"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "analyses",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("owner_id", sa.String(160), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("original_input", sa.Text(), nullable=True),
        sa.Column("preview", sa.String(300), nullable=False),
        sa.Column("reliability_score", sa.Integer(), nullable=False),
        sa.Column("hallucination_risk_score", sa.Integer(), nullable=False),
        sa.Column("decision_confidence", sa.Integer(), nullable=False),
        sa.Column("total_claims", sa.Integer(), nullable=False),
        sa.Column("supported_claims", sa.Integer(), nullable=False),
        sa.Column("contradicted_claims", sa.Integer(), nullable=False),
        sa.Column("uncertain_claims", sa.Integer(), nullable=False),
        sa.Column("unverifiable_claims", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("source_type", sa.String(80), nullable=False),
        sa.Column("verification_mode", sa.String(40), nullable=False),
        sa.Column("score_type", sa.String(30), nullable=False),
        sa.Column("claims", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_analyses_owner_id", "analyses", ["owner_id"])
    op.create_index("ix_analyses_created_at", "analyses", ["created_at"])

def downgrade():
    op.drop_table("analyses")
