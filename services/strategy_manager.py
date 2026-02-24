"""Strategy Manager for handling strategy state per session."""
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class StrategyManager:
    """Manages strategy code state for different sessions.
    
    Provides session-based storage for current strategy code,
    allowing multiple users to work on different strategies simultaneously.
    """
    
    def __init__(self):
        """Initialize the strategy manager with empty session storage."""
        self._sessions: Dict[str, dict] = {}
        logger.info("StrategyManager initialized")
    
    def get_strategy(self, session_id: str) -> Optional[str]:
        """Get the current strategy code for a session.
        
        Args:
            session_id: Unique identifier for the session
            
        Returns:
            Strategy code as string, or None if no strategy exists
        """
        session = self._sessions.get(session_id)
        if session:
            return session.get("code")
        return None
    
    def set_strategy(self, session_id: str, code: str) -> None:
        """Set or update the strategy code for a session.
        
        Args:
            session_id: Unique identifier for the session
            code: Python code for the Zipline strategy
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = {}
        
        self._sessions[session_id]["code"] = code
        self._sessions[session_id]["updated_at"] = datetime.now()
        logger.info(f"Strategy updated for session {session_id}")
    
    def has_strategy(self, session_id: str) -> bool:
        """Check if a session has a strategy defined.
        
        Args:
            session_id: Unique identifier for the session
            
        Returns:
            True if strategy exists, False otherwise
        """
        return session_id in self._sessions and "code" in self._sessions[session_id]
    
    def get_session_info(self, session_id: str) -> Optional[dict]:
        """Get metadata about a session's strategy.
        
        Args:
            session_id: Unique identifier for the session
            
        Returns:
            Dictionary with session metadata, or None if session doesn't exist
        """
        if session_id not in self._sessions:
            return None
        
        session = self._sessions[session_id]
        return {
            "has_strategy": "code" in session,
            "updated_at": session.get("updated_at"),
            "code_length": len(session.get("code", ""))
        }
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its associated strategy.
        
        Args:
            session_id: Unique identifier for the session
            
        Returns:
            True if session was deleted, False if it didn't exist
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Session {session_id} deleted")
            return True
        return False
    
    def list_sessions(self) -> list[str]:
        """Get list of all active session IDs.
        
        Returns:
            List of session ID strings
        """
        return list(self._sessions.keys())