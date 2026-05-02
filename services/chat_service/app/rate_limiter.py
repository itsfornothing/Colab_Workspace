"""
Rate limiting for WebSocket signaling messages.

This module provides rate limiting functionality to prevent abuse of
WebRTC signaling messages. It uses Redis to track message counts per user.

Requirements:
- 10.4: Implement rate limiting for signaling messages
- 12.2: Add signaling message validation
"""
import time
from django.core.cache import cache
from django.conf import settings


class SignalingRateLimiter:
    """
    Rate limiter for WebRTC signaling messages.
    
    Limits the number of signaling messages a user can send within a time window
    to prevent abuse and DoS attacks.
    """
    
    # Rate limit: 100 signaling messages per minute per user
    MAX_MESSAGES_PER_MINUTE = getattr(settings, 'SIGNALING_RATE_LIMIT', 100)
    WINDOW_SECONDS = 60
    
    @classmethod
    def check_rate_limit(cls, user_id: str, message_type: str) -> tuple[bool, int]:
        """
        Check if user has exceeded rate limit for signaling messages.
        
        Args:
            user_id: User ID to check
            message_type: Type of signaling message (for tracking)
        
        Returns:
            Tuple of (is_allowed, remaining_quota)
            - is_allowed: True if message is allowed, False if rate limit exceeded
            - remaining_quota: Number of messages remaining in current window
        """
        cache_key = f"signaling_rate:{user_id}"
        
        # Get current count and timestamp
        data = cache.get(cache_key)
        current_time = time.time()
        
        if data is None:
            # First message in window
            cache.set(cache_key, {
                'count': 1,
                'start_time': current_time,
                'messages': {message_type: 1}
            }, timeout=cls.WINDOW_SECONDS)
            return True, cls.MAX_MESSAGES_PER_MINUTE - 1
        
        # Check if window has expired
        if current_time - data['start_time'] >= cls.WINDOW_SECONDS:
            # Reset window
            cache.set(cache_key, {
                'count': 1,
                'start_time': current_time,
                'messages': {message_type: 1}
            }, timeout=cls.WINDOW_SECONDS)
            return True, cls.MAX_MESSAGES_PER_MINUTE - 1
        
        # Check if limit exceeded
        if data['count'] >= cls.MAX_MESSAGES_PER_MINUTE:
            return False, 0
        
        # Increment count
        data['count'] += 1
        data['messages'][message_type] = data['messages'].get(message_type, 0) + 1
        
        # Update cache with remaining TTL
        remaining_ttl = int(cls.WINDOW_SECONDS - (current_time - data['start_time']))
        cache.set(cache_key, data, timeout=remaining_ttl)
        
        return True, cls.MAX_MESSAGES_PER_MINUTE - data['count']
    
    @classmethod
    def get_rate_limit_info(cls, user_id: str) -> dict:
        """
        Get current rate limit status for a user.
        
        Args:
            user_id: User ID to check
        
        Returns:
            Dictionary with rate limit information:
            - count: Current message count in window
            - limit: Maximum messages allowed
            - remaining: Messages remaining
            - reset_time: Unix timestamp when window resets
        """
        cache_key = f"signaling_rate:{user_id}"
        data = cache.get(cache_key)
        
        if data is None:
            return {
                'count': 0,
                'limit': cls.MAX_MESSAGES_PER_MINUTE,
                'remaining': cls.MAX_MESSAGES_PER_MINUTE,
                'reset_time': int(time.time() + cls.WINDOW_SECONDS)
            }
        
        return {
            'count': data['count'],
            'limit': cls.MAX_MESSAGES_PER_MINUTE,
            'remaining': max(0, cls.MAX_MESSAGES_PER_MINUTE - data['count']),
            'reset_time': int(data['start_time'] + cls.WINDOW_SECONDS)
        }


def sanitize_signaling_data(data: dict) -> dict:
    """
    Sanitize user-provided data in signaling messages.
    
    Validates and sanitizes SDP offers, answers, and ICE candidates to prevent
    injection attacks and ensure data integrity.
    
    Args:
        data: Raw signaling data from client
    
    Returns:
        Sanitized data dictionary
    
    Raises:
        ValueError: If data is invalid or malicious
    """
    sanitized = {}
    
    # Validate and sanitize SDP data
    if 'sdp' in data:
        sdp = data['sdp']
        if not isinstance(sdp, dict):
            raise ValueError("SDP must be a dictionary")
        
        # Validate SDP type
        if 'type' in sdp:
            if sdp['type'] not in ['offer', 'answer', 'pranswer', 'rollback']:
                raise ValueError(f"Invalid SDP type: {sdp['type']}")
            sanitized['sdp'] = {'type': sdp['type']}
        
        # Validate SDP string (basic validation)
        if 'sdp' in sdp:
            sdp_str = str(sdp['sdp'])
            # Limit SDP size to prevent DoS
            if len(sdp_str) > 50000:  # 50KB limit
                raise ValueError("SDP too large")
            sanitized['sdp']['sdp'] = sdp_str
    
    # Validate and sanitize ICE candidate
    if 'candidate' in data:
        candidate = data['candidate']
        if not isinstance(candidate, dict):
            raise ValueError("ICE candidate must be a dictionary")
        
        sanitized['candidate'] = {}
        
        # Validate candidate string
        if 'candidate' in candidate:
            cand_str = str(candidate['candidate'])
            if len(cand_str) > 1000:  # 1KB limit
                raise ValueError("ICE candidate too large")
            sanitized['candidate']['candidate'] = cand_str
        
        # Validate sdpMid
        if 'sdpMid' in candidate:
            sdp_mid = str(candidate['sdpMid'])
            if len(sdp_mid) > 100:
                raise ValueError("sdpMid too large")
            sanitized['candidate']['sdpMid'] = sdp_mid
        
        # Validate sdpMLineIndex
        if 'sdpMLineIndex' in candidate:
            try:
                index = int(candidate['sdpMLineIndex'])
                if index < 0 or index > 100:
                    raise ValueError("Invalid sdpMLineIndex")
                sanitized['candidate']['sdpMLineIndex'] = index
            except (ValueError, TypeError):
                raise ValueError("sdpMLineIndex must be an integer")
    
    # Validate room_id
    if 'room_id' in data:
        room_id = str(data['room_id'])
        if len(room_id) > 100:
            raise ValueError("room_id too large")
        sanitized['room_id'] = room_id
    
    # Validate to_user_id
    if 'to_user_id' in data:
        to_user_id = str(data['to_user_id'])
        if len(to_user_id) > 100:
            raise ValueError("to_user_id too large")
        sanitized['to_user_id'] = to_user_id
    
    return sanitized
