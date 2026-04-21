from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    issues: Mapped[list["Issue"]] = relationship(back_populates="source")
    # Delivery-side models use separate tables.


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(255))
    press_name: Mapped[str | None] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    original_url: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="뉴스")
    region: Mapped[str | None] = mapped_column(String(20))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    raw_content: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="collected", server_default="collected")
    unique_hash: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    source: Mapped[Source] = relationship(back_populates="issues")
    summaries: Mapped[list["IssueSummary"]] = relationship(back_populates="issue")
    reports: Mapped[list["Report"]] = relationship(back_populates="issue")
    embedding: Mapped["IssueEmbedding | None"] = relationship(back_populates="issue")


class IssueSummary(Base):
    __tablename__ = "issue_summaries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True)
    llm_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    llm_model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(30))
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    importance: Mapped[str | None] = mapped_column(String(20))
    key_points_json: Mapped[str | None] = mapped_column(Text)
    research_value: Mapped[str | None] = mapped_column(Text)
    tracking_keywords_json: Mapped[str | None] = mapped_column(Text)
    summary_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="completed", server_default="completed"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    issue: Mapped[Issue] = relationship(back_populates="summaries")
    reports: Mapped[list["Report"]] = relationship(back_populates="summary")


class IssueEmbedding(Base):
    __tablename__ = "issue_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True, unique=True
    )
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    issue: Mapped[Issue] = relationship(back_populates="embedding")


class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    summary_date: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("report_channels.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ready", server_default="ready")
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    channel: Mapped["ReportChannel"] = relationship()


class ReportChannel(Base):
    __tablename__ = "report_channels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    channel_type: Mapped[str] = mapped_column(String(30), nullable=False)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    reports: Mapped[list["Report"]] = relationship(back_populates="channel")
    delivery_logs: Mapped[list["DeliveryLog"]] = relationship(back_populates="channel")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True)
    summary_id: Mapped[int] = mapped_column(
        ForeignKey("issue_summaries.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel_id: Mapped[int] = mapped_column(ForeignKey("report_channels.id"), nullable=False, index=True)
    report_title: Mapped[str] = mapped_column(String(500), nullable=False)
    preview_message: Mapped[str] = mapped_column(Text, nullable=False)
    report_status: Mapped[str] = mapped_column(String(30), nullable=False, default="ready", server_default="ready")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    issue: Mapped[Issue] = relationship(back_populates="reports")
    summary: Mapped[IssueSummary] = relationship(back_populates="reports")
    channel: Mapped[ReportChannel] = relationship(back_populates="reports")
    delivery_logs: Mapped[list["DeliveryLog"]] = relationship(back_populates="report")


class DeliveryLog(Base):
    __tablename__ = "delivery_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("report_channels.id"), nullable=False, index=True)
    delivery_status: Mapped[str] = mapped_column(String(30), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    response_code: Mapped[str | None] = mapped_column(String(30))
    response_body: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    report: Mapped[Report] = relationship(back_populates="delivery_logs")
    channel: Mapped[ReportChannel] = relationship(back_populates="delivery_logs")
