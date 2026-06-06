"""
Risk Scoring Service - Stage 6
Calculates transparent, explainable risk scores for ESG claims
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.models.schemas import RiskScore, Evidence

logger = logging.getLogger(__name__)


class ScoringService:
    """Service for calculating verification risk scores"""
    
    # Scoring weights (must sum to 100)
    WEIGHT_EVIDENCE_MISMATCH = 35
    WEIGHT_LOCATION_SIGNAL = 25
    WEIGHT_NEGATIVE_NEWS = 20
    WEIGHT_MISSING_VERIFICATION = 20
    
    def calculate_risk_score(
        self,
        document_id: str,
        claims: List[Dict[str, Any]],
        evidence: List[Dict[str, Any]]
    ) -> RiskScore:
        """
        Calculate composite risk score for all claims
        
        Args:
            document_id: Document identifier
            claims: List of claim dictionaries
            evidence: List of evidence dictionaries
            
        Returns:
            RiskScore object with breakdown
        """
        # Start with perfect score
        truth_score = 100
        
        # Track penalties for transparency
        penalties = {
            "evidence_mismatch": 0,
            "location_signal": 0,
            "negative_news": 0,
            "missing_verification": 0
        }
        
        # Build claim breakdown
        claim_breakdown = []
        
        for claim in claims:
            claim_id = claim.get("claim_id")
            claim_score = 100
            claim_flags = []
            
            # Get evidence for this claim
            claim_evidence = [e for e in evidence if e.get("claim_id") == claim_id]
            
            # Flag 1: Evidence mismatch
            # Check if external signals contradict the claim
            has_mismatch = self._check_evidence_mismatch(claim, claim_evidence)
            if has_mismatch:
                claim_score -= self.WEIGHT_EVIDENCE_MISMATCH
                penalties["evidence_mismatch"] += self.WEIGHT_EVIDENCE_MISMATCH
                claim_flags.append("Evidence contradicts claim")
            
            # Flag 2: Location signal risk
            # Check for thermal anomalies or unresolved locations
            location_risk = self._check_location_signals(claim, claim_evidence)
            if location_risk:
                claim_score -= self.WEIGHT_LOCATION_SIGNAL
                penalties["location_signal"] += self.WEIGHT_LOCATION_SIGNAL
                claim_flags.append("Location signals indicate risk")
            
            # Flag 3: Negative news signal
            # Check for significant negative media coverage
            news_risk = self._check_news_signals(claim_evidence)
            if news_risk:
                claim_score -= self.WEIGHT_NEGATIVE_NEWS
                penalties["negative_news"] += self.WEIGHT_NEGATIVE_NEWS
                claim_flags.append("Negative news coverage detected")
            
            # Flag 4: Missing verification
            # Check if no external evidence could be found
            if len(claim_evidence) == 0:
                claim_score -= self.WEIGHT_MISSING_VERIFICATION
                penalties["missing_verification"] += self.WEIGHT_MISSING_VERIFICATION
                claim_flags.append("No external verification available")
            
            # Ensure score doesn't go below 0
            claim_score = max(0, claim_score)
            
            claim_breakdown.append({
                "claim_id": claim_id,
                "claim_text": claim.get("claim_text", "")[:100] + "...",
                "claim_type": claim.get("claim_type"),
                "score": claim_score,
                "flags": claim_flags,
                "evidence_count": len(claim_evidence)
            })
        
        # Calculate overall score (average of claim scores)
        if claim_breakdown:
            truth_score = sum(c["score"] for c in claim_breakdown) / len(claim_breakdown)
        
        # Determine risk band
        risk_band = self._determine_risk_band(truth_score)
        
        # Generate reasoning text
        reasoning = self._generate_reasoning(truth_score, penalties, claim_breakdown)
        
        risk_score = RiskScore(
            document_id=document_id,
            truth_score=int(truth_score),
            risk_band=risk_band,
            claim_breakdown=claim_breakdown,
            reasoning=reasoning,
            generated_at=datetime.now()
        )
        
        logger.info(f"Calculated risk score: {truth_score:.1f} ({risk_band})")
        return risk_score
    
    def _check_evidence_mismatch(
        self,
        claim: Dict[str, Any],
        evidence: List[Dict[str, Any]]
    ) -> bool:
        """
        Check if evidence contradicts the claim
        
        Args:
            claim: Claim dictionary
            evidence: List of evidence for this claim
            
        Returns:
            True if mismatch detected
        """
        claim_type = claim.get("claim_type", "")
        target_or_achieved = claim.get("target_or_achieved", "")
        
        # If claim is about emissions reduction or achievement
        if "reduction" in claim_type.lower() or target_or_achieved == "achieved":
            # Check for thermal anomalies (contradictory signal)
            for ev in evidence:
                if ev.get("signal_type") == "thermal_anomaly":
                    signal_strength = ev.get("signal_strength", 0)
                    if signal_strength > 0.3:  # Significant anomaly
                        return True
        
        return False
    
    def _check_location_signals(
        self,
        claim: Dict[str, Any],
        evidence: List[Dict[str, Any]]
    ) -> bool:
        """
        Check for location-based risk signals
        
        Args:
            claim: Claim dictionary
            evidence: List of evidence for this claim
            
        Returns:
            True if location risk detected
        """
        # Check if location could not be resolved
        if not claim.get("facility_name") or not claim.get("location"):
            return True
        
        # Check for FIRMS thermal anomalies
        for ev in evidence:
            if ev.get("source") == "NASA_FIRMS":
                if ev.get("signal_type") == "thermal_anomaly":
                    return True
        
        return False
    
    def _check_news_signals(self, evidence: List[Dict[str, Any]]) -> bool:
        """
        Check for negative news signals
        
        Args:
            evidence: List of evidence for this claim
            
        Returns:
            True if negative news risk detected
        """
        for ev in evidence:
            if ev.get("source") in ["GDELT", "GOOGLE_NEWS"]:
                if ev.get("signal_type") == "negative_news":
                    signal_strength = ev.get("signal_strength", 0)
                    if signal_strength > 0.25:  # Significant negative coverage
                        return True
        
        return False
    
    def _determine_risk_band(self, score: float) -> str:
        """
        Determine risk band from score
        
        Args:
            score: Truth score (0-100)
            
        Returns:
            Risk band string
        """
        if score <= 30:
            return "High Risk"
        elif score <= 60:
            return "Medium Risk"
        else:
            return "Low Risk"
    
    def _generate_reasoning(
        self,
        score: float,
        penalties: Dict[str, int],
        claim_breakdown: List[Dict[str, Any]]
    ) -> str:
        """
        Generate human-readable reasoning for the score
        
        Args:
            score: Truth score
            penalties: Dictionary of penalty amounts
            claim_breakdown: List of claim scores
            
        Returns:
            Reasoning text
        """
        lines = []
        
        # Overall assessment
        risk_band = self._determine_risk_band(score)
        lines.append(f"Overall Verification Score: {score:.1f}/100 ({risk_band})")
        lines.append("")
        
        # Explain penalties
        if penalties["evidence_mismatch"] > 0:
            lines.append(f"• Evidence Mismatch Penalty: -{penalties['evidence_mismatch']} points")
            lines.append("  External signals contradict reported claims")
        
        if penalties["location_signal"] > 0:
            lines.append(f"• Location Signal Penalty: -{penalties['location_signal']} points")
            lines.append("  Thermal anomalies or unresolved facility locations detected")
        
        if penalties["negative_news"] > 0:
            lines.append(f"• Negative News Penalty: -{penalties['negative_news']} points")
            lines.append("  Significant negative environmental coverage found")
        
        if penalties["missing_verification"] > 0:
            lines.append(f"• Missing Verification Penalty: -{penalties['missing_verification']} points")
            lines.append("  Some claims lack external corroboration")
        
        lines.append("")
        
        # Claim summary
        high_risk_claims = [c for c in claim_breakdown if c["score"] <= 30]
        medium_risk_claims = [c for c in claim_breakdown if 30 < c["score"] <= 60]
        low_risk_claims = [c for c in claim_breakdown if c["score"] > 60]
        
        lines.append(f"Claim Analysis: {len(claim_breakdown)} total claims")
        lines.append(f"  • {len(high_risk_claims)} high-risk claims")
        lines.append(f"  • {len(medium_risk_claims)} medium-risk claims")
        lines.append(f"  • {len(low_risk_claims)} low-risk claims")
        
        return "\n".join(lines)


# Singleton instance
_scoring_service: Optional[ScoringService] = None


def get_scoring_service() -> ScoringService:
    """Get or create the scoring service singleton"""
    global _scoring_service
    if _scoring_service is None:
        _scoring_service = ScoringService()
    return _scoring_service

# Made with Bob
