import time
import hashlib
from typing import Dict, Tuple, Optional
from threading import Lock
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from encryption_utils import get_logger

logger = get_logger()

@dataclass
class RateLimitConfig:
    request_per_minitue: int = 300
    request_per_hour: int = 5000
    request_per_day: int = 50000

    brust_size: int = 120
    brust_window: int = 60   # 1-minute rolling burst

    duplicate_message_window: int = 10
    max_message_lengh: int = 4000

    suspicious_requests_per_minitue: int = 100
    block_durtion: int = 120

class TokenBucket:
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = Lock()

    def consume(self, tokens: int = 1) -> bool:
        with self._lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min( self.capacity, self.tokens + (elapsed * self.refill_rate))
            self.last_refill = now
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def get_wait_time(self) -> float:
        with self._lock:
            if self.tokens >=1:
                return 0.0
            return(1.0 - self.tokens) / self.refill_rate
        
class SlidingWindowCounter:
    def __init__(self, window_size: int):
        self.window_size = window_size
        self.request = deque()
        self._lock = Lock()
    
    def add_request(self, timestamp: float = None):
        if timestamp is None:
            timestamp = time.time()
        with self._lock:
            self.request.append(timestamp)
            self._cleanup(timestamp)
    
    def get_count(self, timestamp: float = None) -> int:
        if timestamp is None:
            timestamp = time.time()
        with self._lock:
            self._cleanup(timestamp)
            return len(self.request)
    
    def _cleanup(self, current_time: float):
        cutoff = current_time - self.window_size
        while self.request and self.request[0] < cutoff:
            self.request.popleft()

class RateLimiter:
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self.token_bucket: Dict[str, TokenBucket] = {}
        self.minitue_counters: Dict[str, SlidingWindowCounter] = {}
        self.hour_counters: Dict[str, SlidingWindowCounter] = {}
        self.day_counters: Dict[str, SlidingWindowCounter] = {}
        self.last_messages: Dict[str, Tuple[str, float]] = {}
        self.burst_tracker: Dict[str, deque] = {}
        self.blocked_users: Dict[str, float] = {}
        self.stats = {
            'total_requests': 0,
            'blocked_requests': 0,
            'spam_detected': 0,
            'burst_violations': 0
        }
        self._lock = Lock()
        self._cleanup_interval = 300 #Clean up every 5 minutes
        self._last_cleanup = time.time()
    
    def _get_user_id(self, phone_number: str, client_id: str) -> str:
        combined = f"{client_id}:{phone_number}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    def check_rate_limit(self, phone_number: str, client_id: str, message: str) -> Tuple[bool, Optional[str], Optional[int]]:
        user_id = self._get_user_id(phone_number, client_id)
        current_time = time.time()
        
        with self._lock:
            self.stats['total_requests'] += 1
        
        if user_id in self.blocked_users:
            unblock_time = self.blocked_users[user_id]
            if current_time < unblock_time:
                retry_after = int(unblock_time - current_time)
                return False, "Temporary block due to suspicious activity", retry_after
            else:
                del self.blocked_users[user_id]
            
        #Initialize trackers if needed
        if user_id not in self.token_bucket:
            self.token_bucket[user_id] = TokenBucket( capacity=self.config.brust_size, refill_rate= self.config.request_per_minitue / 60.0)
        
        if user_id not in self.minitue_counters:
            self.minitue_counters[user_id] = SlidingWindowCounter(60)
            self.hour_counters[user_id] = SlidingWindowCounter(3600)
            self.day_counters[user_id] = SlidingWindowCounter(86400)
            self.burst_tracker[user_id] = deque()

        message_hash = hashlib.md5(message.lower().strip().encode()).hexdigest()
        if user_id in self.last_messages:
            last_hash, last_time = self.last_messages[user_id]
            if (last_hash == message_hash and current_time - last_time < self.config.duplicate_message_window):
                with self._lock:
                    self.stats['spam_detected'] += 1
                return False, "Duplicated message detected. Please wait before responding.", 30
        
        self.last_messages[user_id] = (message_hash, current_time)

        if len(message) > self.config.max_message_lengh:
            return False, "Message too long. Please keep it under 2000 character.", None
        
        burst_tracker = self.burst_tracker[user_id]
        burst_tracker.append(current_time)

        burst_cutoff = current_time - self.config.brust_window
        while burst_tracker and burst_tracker[0] < burst_cutoff:
            burst_tracker.popleft()
        
        if len(burst_tracker) > self.config.brust_size:
            with self._lock:
                self.stats['burst_voilations'] += 1
            return False, "Too many requests in short time. Please slow down.", 10
        
        if not self.token_bucket[user_id].consume():
            wait_time = int(self.token_bucket[user_id].get_wait_time()) + 1
            return False, "Rate limit exceeded. Please wait.", wait_time
        
        self.minitue_counters[user_id].add_request(current_time)
        self.hour_counters[user_id].add_request(current_time)
        self.day_counters[user_id].add_request(current_time)

        minute_count = self.minitue_counters[user_id].get_count(current_time)
        hour_count = self.hour_counters[user_id].get_count(current_time)
        day_count = self.day_counters[user_id].get_count(current_time)

        if minute_count > self.config.suspicious_requests_per_minitue:
            self.blocked_users[user_id] = current_time + self.config.block_durtion
            with self._lock:
                self.stats['blocked_requests'] += 1
            return False, "Suspicious activity detected. Temporarily blocked.", self.config.block_durtion
        
        if minute_count > self.config.request_per_minitue:
            return False, "Too many requests in per minute. Please wait.", 60
        if hour_count > self.config.request_per_hour:
            return False, "Hourly request limit reached. Please try again later.", 300
        if day_count > self.config.request_per_day:
            return False, "Dailty request limit reached. Please try again tommorow.", 3600
        
        if current_time - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_data(current_time)
        
        return True, None, None
    
    def _cleanup_old_data(self, current_time: float):
        with self._lock:
            self._last_cleanup = current_time
            cutoff = current_time - 3600
            old_users = [
                user_id for user_id, (_, timestamp) in self.last_messages.items()
                if timestamp < cutoff
            ]
            for user_id in old_users:
                del self.last_messages[user_id]
            
            expired_blocks = [
                user_id for user_id, unblock_time in self.blocked_users.items()
                if current_time >= unblock_time
            ]

            for user_id in expired_blocks:
                del self.blocked_users[user_id]
            
            inactive_cutoff = current_time - 86400
            inactive_users = []

            for user_id in list(self.day_counters.keys()):
                if self.day_counters[user_id].get_count(current_time) == 0:
                    inactive_users.append(user_id)
            
            for user_id in inactive_users:
                self.token_bucket.pop(user_id, None)
                self.minitue_counters.pop(user_id, None)
                self.hour_counters.pop(user_id, None)
                self.day_counters.pop(user_id, None)
                self.burst_tracker.pop(user_id, None)
            
            if inactive_users:
                logger.logging.info(f"Cleaned up {len(inactive_users)} inactive rate limit tracker.")

    def get_user_stats(self, phone_number: str, client_id: str) -> Dict:
        user_id = self._get_user_id(phone_number, client_id)
        current_time = time.time()
        if user_id not in self.minitue_counters:
            return{
                'requests_last_minute': 0,
                'requests_last_hour': 0,
                'requests_last_day': 0,
                'is_blocked': False
            }
        
        return{
            'requests_last_minute': self.minitue_counters[user_id].get_count(current_time),
            'requests_last_hour': self.hour_counters[user_id].get_count(current_time),
            'requests_last_day': self.day_counters[user_id].get_count(current_time),
            'is_blocked': user_id in self.blocked_users,
            'tokens_available': self.token_bucket[user_id].tokens if user_id in self.token_bucket else 0
        }
    
    def get_global_stats(self) -> Dict:
        with self._lock:
            return{
                **self.stats,
                'active_users': len(self.minitue_counters),
                'blocked_users': len(self.blocked_users),
                'tracked_messages': len(self.last_messages)
            }
    
    def unblock_user(self, phone_number: str, client_id: str):
        user_id = self._get_user_id(phone_number, client_id)
        if user_id in self.blocked_users:
            del self.blocked_users[user_id]
            return True
        return False
    
    def reset_user_limits(self, phone_number: str, client_id: str):
        user_id = self._get_user_id(phone_number, client_id)

        self.token_bucket.pop(user_id, None)
        self.minitue_counters.pop(user_id, None)
        self.day_counters.pop(user_id, None)
        self.hour_counters.pop(user_id, None)
        self.burst_tracker.pop(user_id, None)
        self.last_messages.pop(user_id, None)
        self.blocked_users.pop(user_id, None)

_rate_limiter = RateLimiter()

def get_rate_limiter() ->RateLimiter:
    return _rate_limiter



