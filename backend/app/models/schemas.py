"""
Data models for ESG Claim Verification Assistant
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, validator


class Document(BaseModel):
    """Document metadata model"""
    document_id: str
    filename: str
    company_name: str
    uploaded_at: datetime
    file_url: Optional[str] = None
    status: str = "uploaded"


class Claim(BaseModel):
    """ESG claim extracted from document"""
    claim_id: str
    document_id: str
    claim_text: str
    claim_type: str = Field(
        description="Category: emissions_reduction, net_zero_target, renewable_energy, etc."
    )
    value: Optional[float] = None
    unit: Optional[str] = None
    year: Optional[int] = None
    target_or_achieved: Optional[str] = Field(
        default="unknown",
        description="Whether claim is 'target', 'achieved', or 'unknown'"
    )
    page_number: int
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence score")
    facility_name: Optional[str] = None
    location: Optional[str] = None
    
    @validator('target_or_achieved', pre=True, always=True)
    def set_target_or_achieved_default(cls, v):
        """Convert None to 'unknown' for target_or_achieved field"""
        return v or "unknown"


class FacilityLocation(BaseModel):
    """Resolved facility location"""
    facility_name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    resolved: bool = False


class Evidence(BaseModel):
    """External evidence for a claim"""
    evidence_id: str
    claim_id: str
    source: str = Field(description="Data source: OPENWEATHERMAP, GOOGLE_NEWS, etc.")
    signal_type: str = Field(
        description="poor_air_quality, negative_news, no_data, etc."
    )
    signal_text: str
    signal_strength: float = Field(
        ge=0.0, le=1.0, description="Relative weight in scoring"
    )
    timestamp: datetime
    metadata: Optional[dict] = None


class RiskScore(BaseModel):
    """Risk assessment for claims"""
    document_id: str
    truth_score: int = Field(ge=0, le=100, description="Composite verification score")
    risk_band: str = Field(description="High Risk, Medium Risk, or Low Risk")
    claim_breakdown: List[dict]
    reasoning: str
    generated_at: datetime


class UploadResponse(BaseModel):
    """Response after document upload"""
    document_id: str
    filename: str
    file_url: str
    status: str
    message: str


class ClaimExtractionResponse(BaseModel):
    """Response after claim extraction"""
    document_id: str
    claims: List[Claim]
    total_claims: int
    status: str


class VerificationResponse(BaseModel):
    """Response after verification"""
    document_id: str
    evidence: List[Evidence]
    total_evidence: int
    status: str
    claims: Optional[List[dict]] = None


class ScoringResponse(BaseModel):
    """Response after scoring"""
    document_id: str
    risk_score: RiskScore
    status: str

# Made with Bob
