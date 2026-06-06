"""
LLM Service - Stages 3 & 7
Handles claim extraction and explanation generation using Cohere API via LangChain
"""
import json
import logging
import uuid
from typing import List, Dict, Any, Optional
from langchain_cohere import ChatCohere
from langchain_core.prompts import PromptTemplate
from app.config import settings
from app.models.schemas import Claim

logger = logging.getLogger(__name__)


class LLMService:
    """LangChain client for Cohere LLM inference"""
    
    # Extraction prompt template for Cohere
    EXTRACTION_PROMPT = """You are an ESG analyst extracting carbon and emissions claims from corporate sustainability reports.

Extract ONLY claims related to:
- Carbon emissions (Scope 1, 2, or 3)
- Greenhouse gas emissions
- Energy consumption
- Renewable electricity
- Carbon offsets
- Net-zero commitments
- Factory or facility operations

For each claim found, return a JSON object with these exact fields:
- claim_text: The full sentence or paragraph containing the claim
- claim_type: One of [emissions_reduction, net_zero_target, renewable_energy, scope_1, scope_2, scope_3, energy_efficiency, carbon_offset]
- value: The numeric value (if present, otherwise null)
- unit: The unit of measurement (percent, tonnes CO2e, MWh, etc., or null)
- year: The reporting or target year (integer, or null)
- target_or_achieved: One of [target, achieved, unknown]
- confidence: Your confidence in this extraction (0.0 to 1.0)

Return ONLY a valid JSON object containing a "claims" key with an array of claim objects. If no claims are found, return {{"claims": []}}.
Output must be strictly JSON format without markdown blocks.

TEXT TO ANALYZE:
{text}
"""

    # Explanation prompt template for Cohere
    EXPLANATION_PROMPT = """You are an ESG verification analyst. Based on the claims and evidence below, write a concise 4-bullet summary.

You must deeply analyze all provided evidence. Do NOT just look at keywords. Read the full text and descriptions of the news articles, and carefully evaluate the map and air quality (AQI) reports.

For the first 3 bullets:
- Cite the specific claim and the specific external signal (e.g., news article details, map/location data, AQI levels)
- Do NOT accuse the company of fraud
- Use neutral, factual language
- Focus on what was verified, what was not verified, and what appears inconsistent

For the 4th bullet:
- Provide a "Final Verdict" that states clearly what is true and what is not based on the news articles and map results.

CLAIMS:
{claims}

EVIDENCE:
{evidence}

Write exactly 4 bullet points:"""

    def __init__(self):
        """Initialize LangChain Cohere model"""
        # Create the ChatCohere instances for different temperatures
        self.extraction_llm = ChatCohere(
            cohere_api_key=settings.cohere_api_key,
            model=settings.cohere_model,
            temperature=0.1,
            max_tokens=4000,
            safety_mode="NONE"
        )
        
        self.explanation_llm = ChatCohere(
            cohere_api_key=settings.cohere_api_key,
            model=settings.cohere_model,
            temperature=0.3,
            max_tokens=4000,
            safety_mode="NONE"
        )
        
        # Setup prompt templates
        self.extraction_template = PromptTemplate.from_template(self.EXTRACTION_PROMPT)
        self.explanation_template = PromptTemplate.from_template(self.EXPLANATION_PROMPT)
        
        # Create chains
        self.extraction_chain = self.extraction_template | self.extraction_llm
        self.explanation_chain = self.explanation_template | self.explanation_llm
        
        logger.info(f"Initialized LangChain Cohere service with model {settings.cohere_model}")
    
    def extract_claims_from_chunk(
        self,
        chunk_text: str,
        page_number: int,
        document_id: str
    ) -> List[Claim]:
        """
        Extract ESG claims from a text chunk using Cohere via LangChain
        
        Args:
            chunk_text: Text to analyze
            page_number: Source page number
            document_id: Parent document ID
            
        Returns:
            List of extracted Claim objects
        """
        try:
            # Run the chain
            response = self.extraction_chain.invoke({"text": chunk_text})
            content = response.content
            
            # Parse JSON response
            claims_data = self._parse_json_response(content)
            
            # Unwrap if it's a dict containing a list
            if isinstance(claims_data, dict):
                for val in claims_data.values():
                    if isinstance(val, list):
                        claims_data = val
                        break
                else:
                    if "claim_text" in claims_data:
                        claims_data = [claims_data]
                    else:
                        claims_data = []

            # Convert to Claim objects
            claims = []
            if isinstance(claims_data, list):
                for idx, claim_dict in enumerate(claims_data):
                    try:
                        claim = Claim(
                            claim_id=f"{document_id}_claim_{str(uuid.uuid4())[:8]}",
                            document_id=document_id,
                            claim_text=claim_dict.get("claim_text", ""),
                            claim_type=claim_dict.get("claim_type", "unknown"),
                            value=claim_dict.get("value"),
                            unit=claim_dict.get("unit"),
                            year=claim_dict.get("year"),
                            target_or_achieved=claim_dict.get("target_or_achieved", "unknown"),
                            page_number=page_number,
                            confidence=float(claim_dict.get("confidence", 0.5))
                        )
                        
                        # Only include claims with confidence >= 0.6
                        if claim.confidence >= 0.6:
                            claims.append(claim)
                        else:
                            logger.warning(f"Filtered low-confidence claim: {claim.confidence}")
                            
                    except Exception as e:
                        logger.error(f"Error creating Claim object: {e}")
                        continue
            
            logger.info(f"Extracted {len(claims)} claims from chunk")
            return claims
            
        except Exception as e:
            logger.error(f"Error extracting claims: {e}")
            return []
    
    def generate_explanation(
        self,
        claims: List[Dict[str, Any]],
        evidence: List[Dict[str, Any]]
    ) -> str:
        """
        Generate natural language explanation using Cohere via LangChain
        
        Args:
            claims: List of claim dictionaries
            evidence: List of evidence dictionaries
            
        Returns:
            3-bullet explanation text
        """
        try:
            # Deep copy to avoid mutating the original data
            import copy
            safe_claims = copy.deepcopy(claims)
            safe_evidence = copy.deepcopy(evidence)
            
            # Light truncation just as a final safeguard
            for claim in safe_claims:
                if "claim_text" in claim and isinstance(claim["claim_text"], str) and len(claim["claim_text"]) > 2000:
                    claim["claim_text"] = claim["claim_text"][:2000] + "...[TRUNCATED]"
                    
            for item in safe_evidence:
                # Evidence could have "snippet", "content", or "description"
                for key in ["snippet", "content", "description", "text"]:
                    if key in item and isinstance(item[key], str) and len(item[key]) > 2000:
                        item[key] = item[key][:2000] + "...[TRUNCATED]"
                        
            # Format inputs
            claims_text = json.dumps(safe_claims, indent=2)
            evidence_text = json.dumps(safe_evidence, indent=2)
            
            # Hard fallback truncation just in case it's somehow over 100k chars
            if len(claims_text) > 20000:
                claims_text = claims_text[:20000] + "\n...[CLAIMS TRUNCATED DUE TO LENGTH]"
            if len(evidence_text) > 50000:
                evidence_text = evidence_text[:50000] + "\n...[EVIDENCE TRUNCATED DUE TO LENGTH]"
            
            # Run the chain
            response = self.explanation_chain.invoke({
                "claims": claims_text,
                "evidence": evidence_text
            })
            
            explanation = response.content.strip()
            
            logger.info("Generated explanation")
            return explanation
            
        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
            return "Unable to generate explanation due to an error."
    
    def _parse_json_response(self, response: str) -> Any:
        """
        Parse JSON from model response, handling common formatting issues
        """
        import re
        import yaml
        
        def clean_json(s: str) -> str:
            # Remove trailing commas
            s = re.sub(r',\s*\}', '}', s)
            s = re.sub(r',\s*\]', ']', s)
            return s
            
        def try_yaml_fallback(s: str) -> Any:
            """Fallback to YAML parser which handles malformed JSON perfectly"""
            try:
                return yaml.safe_load(s)
            except Exception:
                return None
            
        try:
            return json.loads(clean_json(response))
        except json.JSONDecodeError:
            try:
                # Try YAML fallback first on the raw response
                yaml_result = try_yaml_fallback(response)
                if yaml_result is not None and isinstance(yaml_result, (dict, list)):
                    return yaml_result
                    
                if "```json" in response:
                    json_start = response.find("```json") + 7
                    json_end = response.find("```", json_start)
                    content = response[json_start:json_end].strip()
                    try:
                        return json.loads(clean_json(content))
                    except:
                        return try_yaml_fallback(content) or []
                elif "```" in response:
                    json_start = response.find("```") + 3
                    json_end = response.find("```", json_start)
                    content = response[json_start:json_end].strip()
                    try:
                        return json.loads(clean_json(content))
                    except:
                        return try_yaml_fallback(content) or []
                
                # Try to find JSON array or object
                start_idx = response.find("[")
                end_idx = response.rfind("]") + 1
                if start_idx != -1 and end_idx > start_idx:
                    content = response[start_idx:end_idx]
                    try:
                        return json.loads(clean_json(content))
                    except:
                        return try_yaml_fallback(content) or []
                    
                start_idx = response.find("{")
                end_idx = response.rfind("}") + 1
                if start_idx != -1 and end_idx > start_idx:
                    content = response[start_idx:end_idx]
                    try:
                        return json.loads(clean_json(content))
                    except:
                        return try_yaml_fallback(content) or []
            except Exception as e:
                logger.warning(f"Could not parse JSON from response: {e}")
                
            return []


# Singleton instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create the LLM service singleton"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

