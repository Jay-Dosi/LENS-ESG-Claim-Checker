"""
Storage Service - Stateless, Session-Based Architecture
Uses ChromaDB for in-memory storage with automatic cleanup
NO external storage services required - FREE deployment
"""
import json
import logging
import os
import base64
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path
import chromadb
# Monkeypatch chromadb telemetry to silence errors
try:
    from chromadb.telemetry.product.posthog import Posthog
    Posthog.capture = lambda *args, **kwargs: None
except Exception:
    pass

from chromadb.config import Settings as ChromaSettings
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

class DummyEmbeddingFunction(EmbeddingFunction):
    """
    Prevents ChromaDB from downloading and loading the heavy 80MB ONNX model.
    Since we only use Chroma as a key-value store, we don't need real embeddings.
    This saves ~300MB of RAM and prevents Render OOM crashes.
    """
    def __call__(self, input: Documents) -> Embeddings:
        return [[0.0] * 384 for _ in input]

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages user sessions with automatic cleanup"""
    
    def __init__(self, session_timeout_minutes: int = 60):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
    
    def create_session(self) -> str:
        """Create a new session and return session ID"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "created_at": datetime.now(),
            "last_accessed": datetime.now(),
            "data": {}
        }
        logger.info(f"Created session: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data if it exists and is not expired"""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        
        # Check if session is expired
        if datetime.now() - session["last_accessed"] > self.session_timeout:
            self.delete_session(session_id)
            return None
        
        # Update last accessed time
        session["last_accessed"] = datetime.now()
        return session
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its data"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
            return True
        return False
    
    def cleanup_expired_sessions(self) -> int:
        """Remove all expired sessions"""
        expired = []
        for session_id, session in self.sessions.items():
            if datetime.now() - session["last_accessed"] > self.session_timeout:
                expired.append(session_id)
        
        for session_id in expired:
            self.delete_session(session_id)
        
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")
        return len(expired)
    
    def get_all_sessions(self) -> List[str]:
        """Get all active session IDs"""
        return list(self.sessions.keys())


class ChromaDBStorage:
    """
    ChromaDB-based storage for session data
    Runs in-memory or with local persistence
    NO external services required
    """
    
    def __init__(self, persist_directory: Optional[str] = None, in_memory: bool = True):
        """
        Initialize ChromaDB storage
        
        Args:
            persist_directory: Directory for persistent storage (optional)
            in_memory: If True, use in-memory storage (default)
        """
        self.in_memory = in_memory
        
        if in_memory:
            # In-memory mode - data cleared on restart
            self.client = chromadb.Client(ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            ))
            logger.info("ChromaDB initialized in MEMORY mode (stateless)")
        else:
            # Persistent mode - data saved to disk
            persist_directory = persist_directory or "./chroma_storage"
            os.makedirs(persist_directory, exist_ok=True)
            self.client = chromadb.Client(ChromaSettings(
                persist_directory=persist_directory,
                anonymized_telemetry=False,
                allow_reset=True
            ))
            logger.info(f"ChromaDB initialized with persistence: {persist_directory}")
        
        # Create collections for different data types
        self._init_collections()
    
    def _init_collections(self):
        """Initialize ChromaDB collections"""
        try:
            dummy_ef = DummyEmbeddingFunction()
            self.documents_collection = self.client.get_or_create_collection("documents", embedding_function=dummy_ef)
            self.metadata_collection = self.client.get_or_create_collection("metadata", embedding_function=dummy_ef)
            self.claims_collection = self.client.get_or_create_collection("claims", embedding_function=dummy_ef)
            self.evidence_collection = self.client.get_or_create_collection("evidence", embedding_function=dummy_ef)
            self.reports_collection = self.client.get_or_create_collection("reports", embedding_function=dummy_ef)
            logger.info("ChromaDB collections initialized with Dummy Embeddings (RAM saved)")
        except Exception as e:
            logger.error(f"Error initializing collections: {e}")
            raise
    
    def store_file(self, session_id: str, document_id: str, file_content: bytes, 
                   filename: str, metadata: Dict[str, Any]) -> str:
        """
        Store file content as base64 in ChromaDB
        
        Args:
            session_id: Session identifier
            document_id: Document identifier
            file_content: Binary file content
            filename: Original filename
            metadata: Additional metadata
            
        Returns:
            Document ID
        """
        try:
            # Encode file as base64
            file_base64 = base64.b64encode(file_content).decode('utf-8')
            
            # Store in documents collection
            self.documents_collection.add(
                ids=[document_id],
                documents=[file_base64],
                metadatas=[{
                    "session_id": session_id,
                    "filename": filename,
                    "uploaded_at": datetime.now().isoformat(),
                    **metadata
                }]
            )
            
            logger.info(f"Stored file: {document_id} (session: {session_id})")
            return document_id
            
        except Exception as e:
            logger.error(f"Error storing file: {e}")
            raise
    
    def get_file(self, document_id: str) -> Optional[bytes]:
        """
        Retrieve file content from ChromaDB
        
        Args:
            document_id: Document identifier
            
        Returns:
            Binary file content or None
        """
        try:
            result = self.documents_collection.get(ids=[document_id])
            
            if not result["documents"]:
                return None
            
            # Decode base64
            file_base64 = result["documents"][0]
            file_content = base64.b64decode(file_base64)
            
            return file_content
            
        except Exception as e:
            logger.error(f"Error retrieving file: {e}")
            return None
    
    def store_json(self, collection_name: str, document_id: str, 
                   data: Dict[str, Any], session_id: str) -> str:
        """
        Store JSON data in specified collection
        
        Args:
            collection_name: Collection to store in (metadata, claims, evidence, reports)
            document_id: Document identifier
            data: JSON data to store
            session_id: Session identifier
            
        Returns:
            Document ID
        """
        try:
            collection_map = {
                "metadata": self.metadata_collection,
                "claims": self.claims_collection,
                "evidence": self.evidence_collection,
                "reports": self.reports_collection
            }
            
            collection = collection_map.get(collection_name)
            if not collection:
                raise ValueError(f"Invalid collection: {collection_name}")
            
            # Store as JSON string
            json_str = json.dumps(data, default=str)
            
            collection.add(
                ids=[document_id],
                documents=[json_str],
                metadatas=[{
                    "session_id": session_id,
                    "stored_at": datetime.now().isoformat()
                }]
            )
            
            logger.info(f"Stored JSON in {collection_name}: {document_id}")
            return document_id
            
        except Exception as e:
            logger.error(f"Error storing JSON: {e}")
            raise
    
    def get_json(self, collection_name: str, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve JSON data from specified collection
        
        Args:
            collection_name: Collection to retrieve from
            document_id: Document identifier
            
        Returns:
            Parsed JSON data or None
        """
        try:
            collection_map = {
                "metadata": self.metadata_collection,
                "claims": self.claims_collection,
                "evidence": self.evidence_collection,
                "reports": self.reports_collection
            }
            
            collection = collection_map.get(collection_name)
            if not collection:
                raise ValueError(f"Invalid collection: {collection_name}")
            
            result = collection.get(ids=[document_id])
            
            if not result["documents"]:
                return None
            
            # Parse JSON
            json_str = result["documents"][0]
            data = json.loads(json_str)
            
            return data
            
        except Exception as e:
            logger.error(f"Error retrieving JSON: {e}")
            return None
    
    def delete_session_data(self, session_id: str) -> int:
        """
        Delete all data for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            Number of items deleted
        """
        deleted_count = 0
        
        try:
            # Delete from all collections
            for collection in [self.documents_collection, self.metadata_collection,
                             self.claims_collection, self.evidence_collection,
                             self.reports_collection]:
                
                # Get all items for this session
                results = collection.get(where={"session_id": session_id})
                
                if results["ids"]:
                    collection.delete(ids=results["ids"])
                    deleted_count += len(results["ids"])
            
            logger.info(f"Deleted {deleted_count} items for session: {session_id}")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error deleting session data: {e}")
            return deleted_count
    
    def reset_all_data(self) -> bool:
        """
        Reset all data in ChromaDB (for demo/testing)
        
        Returns:
            True if successful
        """
        try:
            self.client.reset()
            self._init_collections()
            logger.info("ChromaDB reset complete - all data cleared")
            return True
        except Exception as e:
            logger.error(f"Error resetting ChromaDB: {e}")
            return False


class StorageService:
    """
    Unified storage service with session management
    Stateless architecture - no external services required
    """
    
    def __init__(self, in_memory: bool = True, session_timeout_minutes: int = 60):
        """
        Initialize storage service
        
        Args:
            in_memory: Use in-memory storage (default True for stateless)
            session_timeout_minutes: Session timeout in minutes
        """
        self.session_manager = SessionManager(session_timeout_minutes)
        self.storage = ChromaDBStorage(in_memory=in_memory)
        logger.info(f"Storage service initialized (in_memory={in_memory})")
    
    def create_session(self) -> str:
        """Create a new session"""
        return self.session_manager.create_session()
    
    def upload_file(self, session_id: str, file_path: str, object_key: str) -> str:
        """
        Upload a file to storage
        
        Args:
            session_id: Session identifier
            file_path: Local path to the file
            object_key: Key (identifier) for storage
            
        Returns:
            Storage key
        """
        try:
            # Read file content
            with open(file_path, 'rb') as f:
                file_content = f.read()
            
            # Extract filename
            filename = os.path.basename(file_path)
            
            # Store in ChromaDB
            document_id = object_key.replace('/', '_')
            self.storage.store_file(
                session_id=session_id,
                document_id=document_id,
                file_content=file_content,
                filename=filename,
                metadata={"object_key": object_key}
            )
            
            return object_key
            
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            raise
    
    def download_file(self, object_key: str, local_path: str) -> str:
        """
        Download a file from storage
        
        Args:
            object_key: Key (identifier) in storage
            local_path: Local path to save the file
            
        Returns:
            Local file path
        """
        try:
            document_id = object_key.replace('/', '_')
            file_content = self.storage.get_file(document_id)
            
            if file_content is None:
                raise FileNotFoundError(f"File not found: {object_key}")
            
            # Create directory if needed
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Write file
            with open(local_path, 'wb') as f:
                f.write(file_content)
            
            logger.info(f"Downloaded file to: {local_path}")
            return local_path
            
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            raise
    
    def upload_json(self, session_id: str, data: Dict[Any, Any], object_key: str) -> str:
        """
        Upload JSON data to storage
        
        Args:
            session_id: Session identifier
            data: Dictionary to serialize as JSON
            object_key: Key (identifier) in storage
            
        Returns:
            Storage key
        """
        try:
            # Determine collection from object_key
            if "metadata" in object_key:
                collection = "metadata"
            elif "claims" in object_key:
                collection = "claims"
            elif "evidence" in object_key:
                collection = "evidence"
            elif "reports" in object_key:
                collection = "reports"
            else:
                collection = "metadata"
            
            document_id = object_key.replace('/', '_').replace('.json', '')
            self.storage.store_json(collection, document_id, data, session_id)
            
            return object_key
            
        except Exception as e:
            logger.error(f"Error uploading JSON: {e}")
            raise
    
    def download_json(self, object_key: str) -> Dict[Any, Any]:
        """
        Download and parse JSON from storage
        
        Args:
            object_key: Key (identifier) in storage
            
        Returns:
            Parsed JSON data
        """
        try:
            # Determine collection from object_key
            if "metadata" in object_key:
                collection = "metadata"
            elif "claims" in object_key:
                collection = "claims"
            elif "evidence" in object_key:
                collection = "evidence"
            elif "reports" in object_key:
                collection = "reports"
            else:
                collection = "metadata"
            
            document_id = object_key.replace('/', '_').replace('.json', '')
            data = self.storage.get_json(collection, document_id)
            
            if data is None:
                raise FileNotFoundError(f"JSON not found: {object_key}")
            
            return data
            
        except Exception as e:
            logger.error(f"Error downloading JSON: {e}")
            raise
    
    def cleanup_session(self, session_id: str) -> bool:
        """
        Clean up a session and all its data
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful
        """
        try:
            # Delete session data from storage
            self.storage.delete_session_data(session_id)
            
            # Delete session from manager
            self.session_manager.delete_session(session_id)
            
            logger.info(f"Cleaned up session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning up session: {e}")
            return False
    
    def cleanup_expired_sessions(self) -> int:
        """
        Clean up all expired sessions
        
        Returns:
            Number of sessions cleaned up
        """
        expired_sessions = []
        
        for session_id in self.session_manager.get_all_sessions():
            session = self.session_manager.get_session(session_id)
            if session is None:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.storage.delete_session_data(session_id)
        
        return len(expired_sessions)
    
    def reset_all_data(self) -> bool:
        """
        Reset all data (for demo/testing)
        
        Returns:
            True if successful
        """
        try:
            # Reset ChromaDB
            self.storage.reset_all_data()
            
            # Clear all sessions
            for session_id in self.session_manager.get_all_sessions():
                self.session_manager.delete_session(session_id)
            
            logger.info("All data reset complete")
            return True
            
        except Exception as e:
            logger.error(f"Error resetting data: {e}")
            return False
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session information"""
        session = self.session_manager.get_session(session_id)
        if session:
            return {
                "session_id": session_id,
                "created_at": session["created_at"].isoformat(),
                "last_accessed": session["last_accessed"].isoformat(),
                "active": True
            }
        return None


# Singleton instance
_storage_service: Optional[StorageService] = None


def get_storage_service() -> StorageService:
    """Get or create the storage service singleton"""
    global _storage_service
    if _storage_service is None:
        # Default to in-memory mode for stateless architecture
        _storage_service = StorageService(in_memory=True, session_timeout_minutes=60)
    return _storage_service

