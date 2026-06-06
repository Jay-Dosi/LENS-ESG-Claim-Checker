"""
NLU Service - spaCy Implementation
Uses spaCy for local, free entity extraction instead of IBM Watson NLU
"""
import logging
import spacy
from spacy.cli import download
from typing import List, Dict, Any, Optional
from app.config import settings
from app.models.schemas import FacilityLocation

logger = logging.getLogger(__name__)


class NLUService:
    """spaCy client for entity extraction"""
    
    def __init__(self):
        """Initialize spaCy NLP model"""
        model_name = "en_core_web_md"
        try:
            self.nlp = spacy.load(model_name)
            logger.info(f"Loaded spaCy model: {model_name}")
        except OSError:
            logger.warning(f"spaCy model {model_name} not found. Attempting to download...")
            try:
                download(model_name)
                self.nlp = spacy.load(model_name)
                logger.info(f"Successfully downloaded and loaded {model_name}")
            except Exception as e:
                logger.error(f"Failed to download spaCy model: {e}")
                # Fallback to small model if medium fails
                logger.warning("Falling back to en_core_web_sm...")
                try:
                    self.nlp = spacy.load("en_core_web_sm")
                except OSError:
                    download("en_core_web_sm")
                    self.nlp = spacy.load("en_core_web_sm")
                logger.info("Successfully loaded fallback model")
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract entities from text using spaCy
        
        Args:
            text: Text to analyze
            
        Returns:
            Dictionary with entity types as keys and lists of entity mentions as values
        """
        try:
            doc = self.nlp(text)
            
            entities = {
                'locations': [],
                'organizations': [],
                'facilities': [],
                'keywords': []
            }
            
            for ent in doc.ents:
                entity_text = ent.text.strip()
                
                # spaCy labels:
                # GPE: Countries, cities, states
                # LOC: Non-GPE locations, mountain ranges, bodies of water
                # ORG: Companies, agencies, institutions
                # FAC: Buildings, airports, highways, bridges, etc.
                
                if ent.label_ in ['GPE', 'LOC']:
                    entities['locations'].append(entity_text)
                    
                elif ent.label_ == 'ORG':
                    entities['organizations'].append(entity_text)
                    
                elif ent.label_ == 'FAC':
                    entities['facilities'].append(entity_text)
            
            # Extract noun chunks for potential facility keywords
            facility_keywords = [
                'plant', 'facility', 'factory', 'site', 'center', 'centre',
                'manufacturing', 'production', 'warehouse', 'office', 'campus',
                'refinery', 'mill', 'works', 'hub', 'station'
            ]
            
            for chunk in doc.noun_chunks:
                chunk_text = chunk.text.strip()
                entities['keywords'].append(chunk_text)
                if any(kw in chunk_text.lower() for kw in facility_keywords):
                    entities['facilities'].append(chunk_text)
            
            # Remove duplicates while preserving order
            for key in entities:
                entities[key] = list(dict.fromkeys(entities[key]))
            
            return entities
            
        except Exception as e:
            logger.error(f"Error extracting entities with spaCy: {e}")
            return {'locations': [], 'organizations': [], 'facilities': [], 'keywords': []}
    
    def identify_facilities_in_claims(
        self,
        claims: List[Dict[str, Any]],
        full_document_text: str
    ) -> List[str]:
        """
        Identify facility names mentioned in claims
        
        Args:
            claims: List of claim dictionaries
            full_document_text: Complete document text for context
            
        Returns:
            List of unique facility names
        """
        facility_names = set()
        
        # Extract entities from each claim
        for claim in claims:
            claim_text = claim.get('claim_text', '')
            if claim_text:
                entities = self.extract_entities(claim_text)
                facility_names.update(entities['facilities'])
                facility_names.update(entities['keywords'])
        
        # Also scan the full document for facility mentions
        if full_document_text:
            # We removed the 10000 char limit, processing full text. 
            # Note: spaCy has a max length limit (usually 1,000,000 chars), we'll truncate only if it exceeds that.
            max_spacy_length = 1000000
            if len(full_document_text) > max_spacy_length:
                sample_text = full_document_text[:max_spacy_length]
            else:
                sample_text = full_document_text
                
            entities = self.extract_entities(sample_text)
            facility_names.update(entities['facilities'])
            facility_names.update(entities['keywords'])
        
        # Filter out generic terms and keep only specific facility names
        filtered_facilities = []
        generic_terms = {'facility', 'plant', 'factory', 'site', 'center', 'centre', 'operations', 'manufacturing'}
        
        for facility in facility_names:
            # Keep if it's not just a generic term
            if facility.lower() not in generic_terms:
                # Keep if it contains a proper noun or specific identifier (e.g. starts with capital, has digits)
                if any(char.isupper() for char in facility) or any(char.isdigit() for char in facility):
                    filtered_facilities.append(facility)
        
        facility_list = list(set(filtered_facilities))
        logger.info(f"Identified {len(facility_list)} unique facility names")
        return facility_list
    
    def extract_locations_from_text(self, text: str) -> List[Dict[str, str]]:
        """
        Extract location entities with additional context
        
        Args:
            text: Text to analyze
            
        Returns:
            List of location dictionaries with text and type
        """
        try:
            doc = self.nlp(text)
            locations = []
            
            for ent in doc.ents:
                if ent.label_ in ['GPE', 'LOC']:
                    locations.append({
                        'text': ent.text,
                        'type': ent.label_,
                        'relevance': 1.0 # spaCy doesn't provide relevance, defaulting to 1.0
                    })
            
            return locations
            
        except Exception as e:
            logger.error(f"Error extracting locations: {e}")
            return []
    
    def resolve_facility_location(
        self,
        facility_name: str,
        location_mapping: Dict[str, Dict[str, Any]]
    ) -> FacilityLocation:
        """
        Resolve a facility name to geographic coordinates
        
        Args:
            facility_name: Name of the facility
            location_mapping: Pre-loaded mapping of facility names to coordinates
            
        Returns:
            FacilityLocation object
        """
        # Normalize facility name for matching
        normalized_name = facility_name.lower().strip()
        
        # Check if facility exists in mapping
        for mapped_name, location_data in location_mapping.items():
            mapped_normalized = mapped_name.lower().strip()
            
            # Exact match or substring match
            if (normalized_name == mapped_normalized or 
                normalized_name in mapped_normalized or 
                mapped_normalized in normalized_name):
                
                return FacilityLocation(
                    facility_name=facility_name,
                    latitude=location_data.get('latitude'),
                    longitude=location_data.get('longitude'),
                    address=location_data.get('address'),
                    resolved=True
                )
        
        # If not found, return unresolved
        logger.warning(f"Could not resolve location for facility: {facility_name}")
        return FacilityLocation(
            facility_name=facility_name,
            resolved=False
        )
    
    def extract_numerical_values(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract numerical values and their units from text
        Useful for extracting emissions values, percentages, etc.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of dictionaries with value, unit, and context
        """
        try:
            doc = self.nlp(text)
            values = []
            
            for ent in doc.ents:
                if ent.label_ in ['QUANTITY', 'CARDINAL', 'PERCENT', 'MONEY']:
                    values.append({
                        'value': ent.text,
                        'unit': None,  # spaCy groups number+unit often in QUANTITY
                        'context': ent.text,
                        'relevance': 1.0
                    })
            
            return values
            
        except Exception as e:
            logger.error(f"Error extracting numerical values: {e}")
            return []


# Singleton instance
_nlu_service: Optional[NLUService] = None


def get_nlu_service() -> NLUService:
    """Get or create the NLU service singleton"""
    global _nlu_service
    if _nlu_service is None:
        _nlu_service = NLUService()
    return _nlu_service

# Made with Bob
