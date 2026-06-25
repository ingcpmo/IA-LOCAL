"""Pydantic models for GMP Change Control Module."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class CRStatus(str, Enum):
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    IMPLEMENTED = "IMPLEMENTED"
    CLOSED = "CLOSED"


class CRPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ChangeRequestCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10)
    priority: CRPriority = CRPriority.MEDIUM
    initiator: str = Field(..., description="User ID o nombre del iniciador (Part 11)")
    department: str
    affected_systems: list[str] = Field(default_factory=list)
    justification: str = Field(..., min_length=10, description="Justificación técnica del cambio")


class ChangeRequestResponse(BaseModel):
    cr_id: str
    title: str
    description: str
    priority: CRPriority
    status: CRStatus
    initiator: str
    department: str
    affected_systems: list[str]
    justification: str
    created_at: datetime
    updated_at: datetime
    audit_hash: str = Field(..., description="SHA256 del registro (Part 11 integrity)")


class ImpactAssessment(BaseModel):
    cr_id: str
    risk_level: str
    affected_processes: list[str]
    validation_required: bool
    capa_required: bool
    estimated_effort_days: Optional[int] = None
    notes: str
    assessed_at: datetime
    assessed_by: str = "system_auto"
    regulatory_note: str = "PENDING_DOCUMENT: evaluación completa requiere PDFs regulatorios"


class ApprovalRequest(BaseModel):
    approver: str = Field(..., description="Firma electrónica del aprobador (Part 11)")
    decision: str = Field(..., pattern="^(APPROVED|REJECTED)$")
    comments: str = Field(default="")
    capa_required: bool = False


class AuditEntry(BaseModel):
    entry_id: str
    cr_id: Optional[str] = None
    action: str
    actor: str
    timestamp: datetime
    data_hash: str
    details: dict = Field(default_factory=dict)
    alcoa_compliant: bool = True
