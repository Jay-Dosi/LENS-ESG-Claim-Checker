"""
FastAPI Routes - API Endpoints with Session Management
"""
import os
import uuid
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Header
from fastapi.responses import JSONResponse

from app.models.schemas import (
    UploadResponse,
    ClaimExtractionResponse,
    VerificationResponse,
    ScoringResponse,
    Claim,
    Evidence
)
from app.services import (
    PDFExtractor,
    get_storage_service,
    get_llm_service,
    get_nlu_service,
    get_external_data_service,
    get_scoring_service
)
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


# Session Management Endpoints

@router.post("/session/create")
async def create_session():
    """
    Create a new session for stateless storage
    
    Returns:
        Session ID and info
    """
    try:
        storage = get_storage_service()
        session_id = storage.create_session()
        
        return {
            "session_id": session_id,
            "message": "Session created successfully",
            "timeout_minutes": 60
        }
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """
    Get session information
    
    Args:
        session_id: Session identifier
        
    Returns:
        Session info
    """
    try:
        storage = get_storage_service()
        session_info = storage.get_session_info(session_id)
        
        if not session_info:
            raise HTTPException(status_code=404, detail="Session not found or expired")
        
        return session_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}")
async def cleanup_session(session_id: str):
    """
    Clean up a session and all its data
    
    Args:
        session_id: Session identifier
        
    Returns:
        Cleanup status
    """
    try:
        storage = get_storage_service()
        success = storage.cleanup_session(session_id)
        
        if success:
            return {
                "message": "Session cleaned up successfully",
                "session_id": session_id
            }
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cleaning up session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/cleanup-expired")
async def cleanup_expired_sessions():
    """
    Clean up all expired sessions (admin endpoint)
    
    Returns:
        Number of sessions cleaned up
    """
    try:
        storage = get_storage_service()
        count = storage.cleanup_expired_sessions()
        
        return {
            "message": f"Cleaned up {count} expired sessions",
            "count": count
        }
    except Exception as e:
        logger.error(f"Error cleaning up expired sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/reset")
async def reset_all_data():
    """
    Reset all data (for demo/testing)
    WARNING: This will delete ALL data
    
    Returns:
        Reset status
    """
    try:
        storage = get_storage_service()
        success = storage.reset_all_data()
        
        if success:
            return {
                "message": "All data reset successfully",
                "warning": "All sessions and data have been cleared"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to reset data")
    except Exception as e:
        logger.error(f"Error resetting data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Document Processing Endpoints

@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    company_name: str = "Unknown Company",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    location_name: Optional[str] = None,
    session_id: Optional[str] = Header(None, alias="X-Session-ID")
) -> UploadResponse:
    """
    Stage 1: Upload a sustainability report PDF
    
    Args:
        file: PDF file upload
        company_name: Name of the reporting company
        session_id: Session ID (from X-Session-ID header)
        
    Returns:
        UploadResponse with document ID and status
    """
    try:
        # Create session if not provided
        storage = get_storage_service()
        if not session_id:
            session_id = storage.create_session()
            logger.info(f"Created new session: {session_id}")
        else:
            # Validate session exists
            if not storage.get_session_info(session_id):
                raise HTTPException(status_code=401, detail="Invalid or expired session")
        
        # Validate file type
        if not file.filename.endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are allowed"
            )
        
        # Validate file size
        file_content = await file.read()
        if len(file_content) > settings.max_file_size_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds {settings.max_file_size_mb}MB limit"
            )
        
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        # Save file locally
        os.makedirs(settings.upload_dir, exist_ok=True)
        local_path = os.path.join(settings.upload_dir, f"{document_id}.pdf")
        
        with open(local_path, 'wb') as f:
            f.write(file_content)
        
        # Upload to storage with session
        object_key = f"uploads/{document_id}.pdf"
        file_url = storage.upload_file(session_id, local_path, object_key)
        
        # Store document metadata
        document_metadata = {
            "document_id": document_id,
            "filename": file.filename,
            "company_name": company_name,
            "uploaded_at": datetime.now().isoformat(),
            "file_url": file_url,
            "status": "uploaded",
            "session_id": session_id,
            "latitude": latitude,
            "longitude": longitude,
            "location_name": location_name
        }
        
        storage.upload_json(
            session_id,
            document_metadata,
            f"metadata/{document_id}.json"
        )
        
        logger.info(f"Document uploaded: {document_id} (session: {session_id})")
        
        return UploadResponse(
            document_id=document_id,
            filename=file.filename,
            file_url=file_url,
            status="uploaded",
            message=f"Document uploaded successfully (session: {session_id})"
        )
        
    except Exception as e:
        logger.error(f"Error uploading document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-claims", response_model=ClaimExtractionResponse)
async def extract_claims(
    document_id: str,
    session_id: Optional[str] = Header(None, alias="X-Session-ID")
) -> ClaimExtractionResponse:
    """
    Stages 2 & 3: Extract text and claims from uploaded document
    
    Args:
        document_id: Document identifier
        session_id: Session ID (from X-Session-ID header)
        
    Returns:
        ClaimExtractionResponse with extracted claims
    """
    try:
        storage = get_storage_service()
        
        # Get session from metadata if not provided
        if not session_id:
            metadata = storage.download_json(f"metadata/{document_id}.json")
            session_id = metadata.get("session_id")
            if not session_id:
                raise HTTPException(status_code=401, detail="Session ID required")
        
        # Validate session
        if not storage.get_session_info(session_id):
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        
        # Download PDF from storage
        local_path = os.path.join(settings.upload_dir, f"{document_id}.pdf")
        storage.download_file(f"uploads/{document_id}.pdf", local_path)
        
        # Stage 2: Extract and chunk text
        pdf_extractor = PDFExtractor()
        pages, candidate_chunks = pdf_extractor.process_pdf(local_path)
        
        # Store extracted text
        storage.upload_json(
            session_id,
            {"pages": pages, "chunks": candidate_chunks},
            f"text/{document_id}.json"
        )
        
        logger.info(f"Extracted {len(candidate_chunks)} candidate chunks")
        
        # Stage 3: Extract claims using LLM
        llm_service = get_llm_service()
        all_claims = []
        
        # Process up to 5 chunks to stay within quota
        for chunk in candidate_chunks[:5]:
            claims = llm_service.extract_claims_from_chunk(
                chunk_text=chunk["text"],
                page_number=chunk["page_number"],
                document_id=document_id
            )
            all_claims.extend(claims)
        
        # Store claims
        claims_data = [claim.dict() for claim in all_claims]
        storage.upload_json(
            session_id,
            {"claims": claims_data},
            f"claims/{document_id}.json"
        )
        
        logger.info(f"Extracted {len(all_claims)} claims")
        
        return ClaimExtractionResponse(
            document_id=document_id,
            claims=all_claims,
            total_claims=len(all_claims),
            status="claims_extracted"
        )
        
    except Exception as e:
        logger.error(f"Error extracting claims: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify", response_model=VerificationResponse)
async def verify_claims(
    document_id: str,
    session_id: Optional[str] = Header(None, alias="X-Session-ID")
) -> VerificationResponse:
    """
    Stages 4 & 5: Resolve facilities and collect external evidence
    
    Args:
        document_id: Document identifier
        session_id: Session ID (from X-Session-ID header)
        
    Returns:
        VerificationResponse with evidence and facility data
    """
    try:
        storage = get_storage_service()
        
        # Load claims
        claims_data = storage.download_json(f"claims/{document_id}.json")
        claims = claims_data.get("claims", [])
        
        # Load document metadata
        metadata = storage.download_json(f"metadata/{document_id}.json")
        company_name = metadata.get("company_name", "Unknown Company")
        
        # Get session from metadata if not provided
        if not session_id:
            session_id = metadata.get("session_id")
            if not session_id:
                raise HTTPException(status_code=401, detail="Session ID required")
        
        # Validate session
        if not storage.get_session_info(session_id):
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        
        # Stage 4: Resolve facility locations
        nlu = get_nlu_service()
        
        # Load facility mapping from config
        import json
        facility_mapping = {}
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "facility_mapping.json")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
                    facility_mapping = config_data.get("facility_mapping", {})
                logger.info(f"Loaded {len(facility_mapping)} facilities from config")
        except Exception as e:
            logger.warning(f"Could not load facility mapping: {e}")
        
        # Check if manual coordinates were provided in metadata
        manual_lat = metadata.get("latitude")
        manual_lon = metadata.get("longitude")
        manual_loc_name = metadata.get("location_name", "Manually Pinned Location")
        
        resolved_facilities = {}
        has_resolved = False
        
        # Determine the primary facility name
        facility_names = list(set([c.get("facility_name") for c in claims if c.get("facility_name")]))
        if not facility_names:
            facility_names = [company_name]
        
        if manual_lat is not None and manual_lon is not None:
            logger.info(f"Using manually pinned location: ({manual_lat}, {manual_lon}) - {manual_loc_name}")
            fallback_location = {
                "facility_name": company_name,
                "resolved": True,
                "latitude": float(manual_lat),
                "longitude": float(manual_lon),
                "address": manual_loc_name,
                "confidence": 1.0,
                "source": "manual_pin"
            }
            resolved_facilities = {company_name: fallback_location}
            has_resolved = True
        else:
            # Extract full document text for context
            text_data = storage.download_json(f"text/{document_id}.json")
            full_text = " ".join([page["text"] for page in text_data.get("pages", [])])
            
            # Identify facilities if needed (optional since we extracted from claims above)
            nlu_facilities = nlu.identify_facilities_in_claims(claims, full_text[:5000])
            if nlu_facilities:
                facility_names = nlu_facilities
            
            # Resolve locations
            for facility_name in facility_names[:3]:  # Limit to 3 facilities for demo
                location = nlu.resolve_facility_location(facility_name, facility_mapping)
                loc_dict = location.dict()
                resolved_facilities[facility_name] = loc_dict
                if loc_dict.get("resolved"):
                    has_resolved = True
            
            # If no facilities were successfully resolved, create a default one with company name
            if not has_resolved:
                # Create a fallback facility with demo coordinates
                fallback_location = {
                    "facility_name": company_name,
                    "resolved": True,
                    "latitude": 37.7749,  # San Francisco (demo)
                    "longitude": -122.4194,
                    "address": "Headquarters Location (Demo Data)",
                    "confidence": 0.5,
                    "source": "fallback"
                }
                # Clear unresolved facilities to force the use of the fallback
                resolved_facilities = {company_name: fallback_location}
                logger.info(f"Created fallback facility for {company_name}")
        
        # Update claims with facility information
        # This ensures the frontend receives facility data
        primary_facility = list(resolved_facilities.keys())[0] if resolved_facilities else company_name
        
        for claim in claims:
            facility_name = claim.get("facility_name")
            
            # If claim has no facility, or its facility is not in our resolved list
            if not facility_name or facility_name not in resolved_facilities or not resolved_facilities[facility_name].get("resolved"):
                claim["facility_name"] = primary_facility
                
            # Add location info
            fac_name = claim["facility_name"]
            if fac_name in resolved_facilities and resolved_facilities[fac_name].get("resolved"):
                claim["location"] = resolved_facilities[fac_name].get("address", "Location available")
                claim["latitude"] = resolved_facilities[fac_name].get("latitude")
                claim["longitude"] = resolved_facilities[fac_name].get("longitude")
        
        # Save updated claims with facility information
        storage.upload_json(
            session_id,
            {"claims": claims},
            f"claims/{document_id}.json"
        )
        
        # Stage 5: Collect external evidence
        external_data = get_external_data_service()
        all_evidence = []
        
        for claim in claims[:5]:  # Limit to 5 claims for demo
            # Add company name to claim
            claim["company_name"] = company_name
            
            # Get facility location if available
            facility_location = None
            facility_name = claim.get("facility_name", primary_facility)
            if facility_name in resolved_facilities:
                facility_location = resolved_facilities[facility_name]
            
            # Collect evidence
            evidence_list = await external_data.collect_evidence_for_claim(
                claim,
                facility_location
            )
            all_evidence.extend(evidence_list)
        
        # Store evidence and facilities
        evidence_data = [ev.dict() for ev in all_evidence]
        storage.upload_json(
            session_id,
            {
                "evidence": evidence_data,
                "facilities": resolved_facilities
            },
            f"evidence/{document_id}.json"
        )
        
        logger.info(f"Collected {len(all_evidence)} evidence records for {len(facility_names)} facilities")
        
        return VerificationResponse(
            document_id=document_id,
            evidence=all_evidence,
            total_evidence=len(all_evidence),
            status="verification_complete",
            claims=claims
        )
        
    except Exception as e:
        logger.error(f"Error verifying claims: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/score", response_model=ScoringResponse)
async def score_claims(
    document_id: str,
    session_id: Optional[str] = Header(None, alias="X-Session-ID")
) -> ScoringResponse:
    """
    Stages 6 & 7: Calculate risk score and generate explanation
    
    Args:
        document_id: Document identifier
        session_id: Session ID (from X-Session-ID header)
        
    Returns:
        ScoringResponse with risk score and explanation
    """
    try:
        storage = get_storage_service()
        
        # Get session from metadata if not provided
        if not session_id:
            metadata = storage.download_json(f"metadata/{document_id}.json")
            session_id = metadata.get("session_id")
            if not session_id:
                raise HTTPException(status_code=401, detail="Session ID required")
        
        # Validate session
        if not storage.get_session_info(session_id):
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        
        # Load claims and evidence
        claims_data = storage.download_json(f"claims/{document_id}.json")
        claims = claims_data.get("claims", [])
        
        evidence_data = storage.download_json(f"evidence/{document_id}.json")
        evidence = evidence_data.get("evidence", [])
        
        # Stage 6: Calculate risk score
        scoring = get_scoring_service()
        risk_score = scoring.calculate_risk_score(document_id, claims, evidence)
        
        # Stage 7: Generate explanation
        llm_service = get_llm_service()
        explanation = llm_service.generate_explanation(claims[:5], evidence[:10])
        
        # Update risk score with AI-generated explanation
        risk_score.reasoning = explanation
        
        # Store final report
        storage.upload_json(
            session_id,
            risk_score.dict(),
            f"reports/{document_id}.json"
        )
        
        logger.info(f"Generated risk score: {risk_score.truth_score}")
        
        return ScoringResponse(
            document_id=document_id,
            risk_score=risk_score,
            status="scoring_complete"
        )
        
    except Exception as e:
        logger.error(f"Error scoring claims: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/map-data/{document_id}")
async def get_map_data(
    document_id: str,
    session_id: Optional[str] = Header(None, alias="X-Session-ID")
):
    """
    Get facility location data for map visualization
    
    Args:
        document_id: Document identifier
        session_id: Session ID (from X-Session-ID header)
        
    Returns:
        Facility locations and claims with coordinates
    """
    try:
        storage = get_storage_service()
        
        # Get session from metadata if not provided
        if not session_id:
            metadata = storage.download_json(f"metadata/{document_id}.json")
            session_id = metadata.get("session_id")
            if not session_id:
                raise HTTPException(status_code=401, detail="Session ID required")
        
        # Validate session
        if not storage.get_session_info(session_id):
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        
        # Load claims with location data
        claims_data = storage.download_json(f"claims/{document_id}.json")
        claims = claims_data.get("claims", [])
        
        # Load facilities if available
        facilities = {}
        try:
            evidence_data = storage.download_json(f"evidence/{document_id}.json")
            facilities = evidence_data.get("facilities", {})
        except:
            pass
        
        # Extract unique locations from claims
        locations = []
        seen_coords = set()
        
        for claim in claims:
            lat = claim.get("latitude")
            lon = claim.get("longitude")
            if lat and lon:
                coord_key = f"{lat},{lon}"
                if coord_key not in seen_coords:
                    seen_coords.add(coord_key)
                    locations.append({
                        "facility_name": claim.get("facility_name", "Unknown"),
                        "latitude": lat,
                        "longitude": lon,
                        "address": claim.get("location", ""),
                        "claim_count": sum(1 for c in claims if c.get("latitude") == lat and c.get("longitude") == lon)
                    })
        
        return {
            "document_id": document_id,
            "locations": locations,
            "facilities": facilities,
            "total_locations": len(locations)
        }
        
    except Exception as e:
        logger.error(f"Error getting map data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "ESG Claim Verification Assistant"}

# Made with Bob
