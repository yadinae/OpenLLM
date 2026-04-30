"""
Token Monitor for OpenLLM

Real-time token usage monitoring, session tracking, and anomaly detection.
Provides visibility into API costs, token consumption, and optimization opportunities.

Features:
- Session-based token tracking
- Cost calculation and reporting
- Anomaly detection (duplicate calls, context overflow, token spikes)
- Real-time statistics and dashboards
"""

import time
import logging
import hashlib
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AnomalySeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Anomaly:
    """Detected anomaly in token usage"""
    type: str
    severity: AnomalySeverity
    message: str
    timestamp: float = field(default_factory=time.time)
    session_id: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class SessionStats:
    """Statistics for a single session"""
    session_id: str
    turns: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_tokens: int = 0
    compressed_tokens: int = 0
    cost: float = 0.0
    max_context: int = 128000
    duplicate_tool_calls: int = 0
    anomalies: list = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
    
    @property
    def fill_rate(self) -> float:
        return self.input_tokens / self.max_context if self.max_context > 0 else 0.0
    
    @property
    def compression_ratio(self) -> float:
        if self.input_tokens == 0:
            return 0.0
        return self.compressed_tokens / self.input_tokens


@dataclass
class GlobalStats:
    """Global statistics across all sessions"""
    total_sessions: int = 0
    total_turns: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_tokens: int = 0
    total_compressed_tokens: int = 0
    total_cost: float = 0.0
    active_sessions: int = 0
    anomalies_detected: int = 0


class TokenMonitor:
    """
    Real-time token usage monitor for OpenLLM.
    
    Features:
    - Track token usage per session
    - Calculate API costs
    - Detect anomalies (duplicate calls, context overflow, token spikes)
    - Provide real-time statistics
    """
    
    # Cost per 1K tokens (approximate, in USD)
    COST_PER_1K_TOKENS = {
        'input': 0.005,   # $0.005 per 1K input tokens
        'output': 0.015,  # $0.015 per 1K output tokens
        'cache': 0.001,   # $0.001 per 1K cached tokens
    }
    
    # Anomaly detection thresholds
    THRESHOLDS = {
        'duplicate_tool_calls': 3,
        'context_overflow': 0.85,
        'token_spike_multiplier': 3.0,
        'cost_spike_multiplier': 2.0,
    }
    
    def __init__(self, config: dict = None):
        """
        Initialize TokenMonitor
        
        Args:
            config: Optional configuration dict
                - cost_per_token: Custom cost rates
                - thresholds: Custom anomaly thresholds
                - max_sessions: Maximum sessions to track
        """
        self.config = config or {}
        self.sessions: dict[str, SessionStats] = {}
        self.anomalies: list[Anomaly] = []
        
        # Apply custom config
        if 'cost_per_token' in self.config:
            self.COST_PER_1K_TOKENS.update(self.config['cost_per_token'])
        if 'thresholds' in self.config:
            self.THRESHOLDS.update(self.config['thresholds'])
        
        self.max_sessions = self.config.get('max_sessions', 1000)
    
    def record_request(self, session_id: str, request: dict, response: dict, 
                       compression_info: dict = None) -> SessionStats:
        """
        Record a request/response pair
        
        Args:
            session_id: Session identifier
            request: Request dict with usage info
            response: Response dict with usage info
            compression_info: Optional compression metadata
        
        Returns:
            Updated SessionStats
        """
        if session_id not in self.sessions:
            if len(self.sessions) >= self.max_sessions:
                # Evict oldest session
                oldest_id = min(self.sessions.keys(), 
                              key=lambda k: self.sessions[k].last_activity)
                del self.sessions[oldest_id]
            
            self.sessions[session_id] = SessionStats(session_id=session_id)
        
        session = self.sessions[session_id]
        session.turns += 1
        session.last_activity = time.time()
        
        # Extract token usage
        request_usage = request.get('usage', {})
        response_usage = response.get('usage', {})
        
        session.input_tokens += request_usage.get('prompt_tokens', 0)
        session.output_tokens += response_usage.get('completion_tokens', 0)
        session.cache_tokens += response_usage.get('cache_tokens', 0)
        
        # Track compression
        if compression_info:
            session.compressed_tokens += compression_info.get('tokens_saved', 0)
        
        # Calculate cost
        session.cost += self._calculate_cost(request_usage, response_usage)
        
        # Detect anomalies
        session_anomalies = self.detect_anomalies(session_id)
        session.anomalies.extend(session_anomalies)
        self.anomalies.extend(session_anomalies)
        
        return session
    
    def _calculate_cost(self, request_usage: dict, response_usage: dict) -> float:
        """Calculate cost for a request/response pair"""
        input_tokens = request_usage.get('prompt_tokens', 0)
        output_tokens = response_usage.get('completion_tokens', 0)
        cache_tokens = response_usage.get('cache_tokens', 0)
        
        cost = (
            (input_tokens / 1000) * self.COST_PER_1K_TOKENS['input'] +
            (output_tokens / 1000) * self.COST_PER_1K_TOKENS['output'] +
            (cache_tokens / 1000) * self.COST_PER_1K_TOKENS['cache']
        )
        
        return round(cost, 6)
    
    def detect_anomalies(self, session_id: str) -> list[Anomaly]:
        """
        Detect anomalies in session
        
        Args:
            session_id: Session to analyze
        
        Returns:
            List of detected anomalies
        """
        session = self.sessions.get(session_id)
        if not session:
            return []
        
        anomalies = []
        
        # Check duplicate tool calls
        if session.duplicate_tool_calls > self.THRESHOLDS['duplicate_tool_calls']:
            anomalies.append(Anomaly(
                type='duplicate_tool_calls',
                severity=AnomalySeverity.WARNING,
                message=f"Detected {session.duplicate_tool_calls} duplicate tool calls",
                session_id=session_id,
                details={'count': session.duplicate_tool_calls}
            ))
        
        # Check context overflow
        if session.fill_rate > self.THRESHOLDS['context_overflow']:
            anomalies.append(Anomaly(
                type='context_overflow',
                severity=AnomalySeverity.CRITICAL,
                message=f"Context fill rate {session.fill_rate:.0%}, approaching limit",
                session_id=session_id,
                details={
                    'fill_rate': session.fill_rate,
                    'input_tokens': session.input_tokens,
                    'max_context': session.max_context
                }
            ))
        
        # Check token spike (if we have enough history)
        if session.turns > 2:
            avg_tokens = session.total_tokens / session.turns
            last_turn_tokens = session.total_tokens  # Approximate
            if last_turn_tokens > avg_tokens * self.THRESHOLDS['token_spike_multiplier']:
                anomalies.append(Anomaly(
                    type='token_spike',
                    severity=AnomalySeverity.WARNING,
                    message=f"Token usage spike detected ({last_turn_tokens} vs avg {avg_tokens:.0f})",
                    session_id=session_id,
                    details={
                        'current': last_turn_tokens,
                        'average': avg_tokens,
                        'multiplier': last_turn_tokens / avg_tokens if avg_tokens > 0 else 0
                    }
                ))
        
        return anomalies
    
    def get_session_stats(self, session_id: str) -> Optional[SessionStats]:
        """Get statistics for a specific session"""
        return self.sessions.get(session_id)
    
    def get_global_stats(self) -> GlobalStats:
        """Get global statistics across all sessions"""
        stats = GlobalStats(
            total_sessions=len(self.sessions),
            active_sessions=sum(1 for s in self.sessions.values() 
                              if time.time() - s.last_activity < 300),  # 5 min
            anomalies_detected=len(self.anomalies)
        )
        
        for session in self.sessions.values():
            stats.total_turns += session.turns
            stats.total_input_tokens += session.input_tokens
            stats.total_output_tokens += session.output_tokens
            stats.total_cache_tokens += session.cache_tokens
            stats.total_compressed_tokens += session.compressed_tokens
            stats.total_cost += session.cost
        
        return stats
    
    def get_session_list(self, limit: int = 50, offset: int = 0) -> list[SessionStats]:
        """Get list of sessions sorted by last activity"""
        sorted_sessions = sorted(
            self.sessions.values(),
            key=lambda s: s.last_activity,
            reverse=True
        )
        return sorted_sessions[offset:offset + limit]
    
    def get_anomalies(self, session_id: str = None, severity: str = None, 
                      limit: int = 100) -> list[Anomaly]:
        """Get anomalies with optional filtering"""
        anomalies = self.anomalies
        
        if session_id:
            anomalies = [a for a in anomalies if a.session_id == session_id]
        
        if severity:
            anomalies = [a for a in anomalies if a.severity.value == severity]
        
        return anomalies[-limit:]
    
    def clear_session(self, session_id: str):
        """Clear a specific session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
    
    def clear_all(self):
        """Clear all sessions and anomalies"""
        self.sessions.clear()
        self.anomalies.clear()
    
    def export_report(self, session_id: str = None) -> dict:
        """
        Export monitoring report
        
        Args:
            session_id: Optional session to report on (None for global)
        
        Returns:
            Report dict
        """
        if session_id:
            session = self.sessions.get(session_id)
            if not session:
                return {'error': 'Session not found'}
            
            return {
                'session_id': session_id,
                'turns': session.turns,
                'input_tokens': session.input_tokens,
                'output_tokens': session.output_tokens,
                'cache_tokens': session.cache_tokens,
                'compressed_tokens': session.compressed_tokens,
                'compression_ratio': session.compression_ratio,
                'total_tokens': session.total_tokens,
                'cost': session.cost,
                'fill_rate': session.fill_rate,
                'anomalies': [
                    {
                        'type': a.type,
                        'severity': a.severity.value,
                        'message': a.message,
                        'timestamp': a.timestamp
                    }
                    for a in session.anomalies
                ],
                'created_at': session.created_at,
                'last_activity': session.last_activity
            }
        else:
            global_stats = self.get_global_stats()
            return {
                'total_sessions': global_stats.total_sessions,
                'active_sessions': global_stats.active_sessions,
                'total_turns': global_stats.total_turns,
                'total_input_tokens': global_stats.total_input_tokens,
                'total_output_tokens': global_stats.total_output_tokens,
                'total_cache_tokens': global_stats.total_cache_tokens,
                'total_compressed_tokens': global_stats.total_compressed_tokens,
                'total_cost': global_stats.total_cost,
                'anomalies_detected': global_stats.anomalies_detected,
                'recent_anomalies': [
                    {
                        'type': a.type,
                        'severity': a.severity.value,
                        'message': a.message,
                        'session_id': a.session_id,
                        'timestamp': a.timestamp
                    }
                    for a in self.anomalies[-20:]
                ]
            }


# Global monitor instance
_monitor: Optional[TokenMonitor] = None


def get_monitor(config: dict = None) -> TokenMonitor:
    """Get or create global TokenMonitor instance"""
    global _monitor
    if _monitor is None:
        _monitor = TokenMonitor(config)
    return _monitor


def reset_monitor():
    """Reset global monitor (for testing)"""
    global _monitor
    _monitor = None
