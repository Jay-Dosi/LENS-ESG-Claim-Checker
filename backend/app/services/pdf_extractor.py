"""
PDF Text Extraction Service - Stage 2
Extracts and chunks text from PDF documents with page number metadata
"""
import re
import logging
from typing import List, Dict, Tuple
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract and process text from PDF documents"""
    
    # ESG-related keywords to identify candidate chunks
    ESG_KEYWORDS = [
        "carbon", "emission", "emissions", "co2", "greenhouse", "ghg",
        "scope 1", "scope 2", "scope 3", "net zero", "net-zero",
        "renewable", "sustainability", "environmental", "energy",
        "reduction", "target", "goal", "commitment", "offset",
        "facility", "plant", "manufacturing", "operations"
    ]
    
    def __init__(self):
        self.esg_pattern = re.compile(
            r"|".join(self.ESG_KEYWORDS),
            re.IGNORECASE
        )
        self.number_pattern = re.compile(r'\d+\.?\d*\s*%|\d+\.?\d*\s*(?:tonnes?|tons?|mt|mwh|gwh|kwh)')
    
    def extract_text_from_pdf(self, pdf_path: str) -> List[Dict[str, any]]:
        """
        Extract text from PDF with page numbers
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of page dictionaries with text and metadata
        """
        pages = []
        
        try:
            doc = fitz.open(pdf_path)
            logger.info(f"Opened PDF with {len(doc)} pages")
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                
                # Clean the text
                cleaned_text = self._clean_text(text)
                
                if cleaned_text.strip():
                    pages.append({
                        "page_number": page_num + 1,
                        "text": cleaned_text,
                        "char_count": len(cleaned_text)
                    })
            
            doc.close()
            logger.info(f"Extracted text from {len(pages)} pages")
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            raise
        
        return pages
    
    def _clean_text(self, text: str) -> str:
        """
        Clean extracted text by removing headers, footers, and formatting artifacts
        
        Args:
            text: Raw text from PDF
            
        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common header/footer patterns
        text = re.sub(r'Page \d+ of \d+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)
        
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        return text.strip()
    
    def chunk_text(self, pages: List[Dict[str, any]], max_chunk_size: int = 2000) -> List[Dict[str, any]]:
        """
        Split text into logical chunks aligned to paragraphs
        
        Args:
            pages: List of page dictionaries
            max_chunk_size: Maximum characters per chunk
            
        Returns:
            List of chunk dictionaries with metadata
        """
        chunks = []
        
        for page in pages:
            text = page["text"]
            page_num = page["page_number"]
            
            # Split by paragraphs (double newline or sentence boundaries)
            paragraphs = re.split(r'\n\n+|(?<=[.!?])\s+(?=[A-Z])', text)
            
            current_chunk = ""
            current_chunk_start_page = page_num
            
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue
                
                # If adding this paragraph exceeds max size, save current chunk
                if len(current_chunk) + len(para) > max_chunk_size and current_chunk:
                    chunks.append({
                        "chunk_id": len(chunks),
                        "text": current_chunk,
                        "page_number": current_chunk_start_page,
                        "char_count": len(current_chunk)
                    })
                    current_chunk = para
                    current_chunk_start_page = page_num
                else:
                    current_chunk += " " + para if current_chunk else para
            
            # Add remaining chunk
            if current_chunk:
                chunks.append({
                    "chunk_id": len(chunks),
                    "text": current_chunk,
                    "page_number": current_chunk_start_page,
                    "char_count": len(current_chunk)
                })
        
        logger.info(f"Created {len(chunks)} text chunks")
        return chunks
    
    def filter_candidate_chunks(self, chunks: List[Dict[str, any]]) -> List[Dict[str, any]]:
        """
        Filter chunks to only those containing ESG-related content
        
        Args:
            chunks: List of all text chunks
            
        Returns:
            Filtered list of candidate chunks for AI processing
        """
        candidate_chunks = []
        
        for chunk in chunks:
            text = chunk["text"]
            
            # Check for ESG keywords
            has_esg_keyword = bool(self.esg_pattern.search(text))
            
            # Check for numerical values (metrics)
            has_numbers = bool(self.number_pattern.search(text))
            
            # Check for year references
            has_year = bool(re.search(r'\b(19|20)\d{2}\b', text))
            
            # Flag as candidate if it has ESG keywords AND (numbers OR years)
            if has_esg_keyword and (has_numbers or has_year):
                chunk["is_candidate"] = True
                chunk["has_metrics"] = has_numbers
                chunk["has_year"] = has_year
                candidate_chunks.append(chunk)
        
        logger.info(f"Filtered to {len(candidate_chunks)} candidate chunks from {len(chunks)} total")
        return candidate_chunks
    
    def process_pdf(self, pdf_path: str) -> Tuple[List[Dict[str, any]], List[Dict[str, any]]]:
        """
        Complete PDF processing pipeline
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Tuple of (all_pages, candidate_chunks)
        """
        # Extract text from all pages
        pages = self.extract_text_from_pdf(pdf_path)
        
        # Chunk the text
        chunks = self.chunk_text(pages)
        
        # Filter to candidate chunks
        candidate_chunks = self.filter_candidate_chunks(chunks)
        
        return pages, candidate_chunks

# Made with Bob
