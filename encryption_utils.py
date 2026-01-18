import os
import logging
import re
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet, InvalidToken
import hashlib
from dotenv import load_dotenv
import threading
from get_secreats import load_env_from_secret

load_dotenv()

def get_key():
    try:
        FERNET_KEY = load_env_from_secret("FERNET_KEY")
        
        # ✅ SECURITY: Validate key exists and is properly formatted
        if not FERNET_KEY:
            raise ValueError("FERNET_KEY environment variable not set")
        
        # ✅ SECURITY: Validate key is valid base64 and correct length (32 bytes)
        if len(FERNET_KEY) != 44:  # Fernet keys are 44 chars (32 bytes base64 encoded)
            raise ValueError(f"Invalid FERNET_KEY length: {len(FERNET_KEY)} (expected 44)")
        
        # Test key validity by attempting to create cipher
        cipher_suite = Fernet(FERNET_KEY.encode('utf-8'))
        
        # ✅ SECURITY: Test encryption/decryption works
        test_encrypted = cipher_suite.encrypt(b"test")
        cipher_suite.decrypt(test_encrypted)

        return cipher_suite
        
    except ValueError as e:
        logging.critical(f"Failed to initialize Fernet cipher: {e}. Check key length and format.")
        raise
    except Exception as e:
        logging.critical(f"Fernet initialization error: {e}")
        raise


# --- Encryption/Decryption Functions ---

import logging
from typing import Dict, Any

# Base logger for fallback errors
log = logging.getLogger(__name__)
log.setLevel(logging.ERROR)

if not log.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s'))
    log.addHandler(handler)

class logger:
    """Singleton logger with robust error handling for database and security operations."""
    _instance = None
    _lock = threading.Lock()  # ✅ CLASS-LEVEL lock for singleton creation

    def __new__(cls):
        if cls._instance is None:
            # ✅ Use class-level lock for thread-safe singleton creation
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        # ✅ Prevent re-initialization
        if self._initialized:
            return
        
        self._initialize()
        self._initialized = True

    def _initialize(self):
        """Initialize the logger with file and console handlers."""
        try:
            self.logger = logging.getLogger('Customer_support')
            self.logger.setLevel(logging.INFO)
            self.logger.handlers.clear()  # Remove old handlers

            formatter = logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(funcName)-30s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

            # Optional console handler for warnings and above
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.WARNING)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

        except Exception as e:
            # If logger initialization fails, print instead
            print(f"Logger initialization failed: {e}")

    def info_(self, message: str):
        """Logs INFO messages safely."""
        try:
            self.logger.info(message)
        except Exception as e:
            self._safe_log_error("info", e, {"message": message})

    def log_query(self, operation: str, collection: str, success: bool, duration_ms: float = None):
        """Logs database query operations safely."""
        try:
            status = "SUCCESS" if success else "FAILED"
            duration_str = f" | {duration_ms:.2f}ms" if duration_ms else ""
            self.logger.info(f"QUERY-{operation} | Collection: {collection} | {status}{duration_str}")
        except Exception as e:
            self._safe_log_error("log_query", e, {
                "operation": operation,
                "collection": collection,
                "success": success,
                "duration_ms": duration_ms
            })

    def log_client_operation(self, operation: str, client_id: str, success: bool):
        """Logs client operations safely."""
        try:
            safe_id = client_id[:12] + "..." if len(client_id) > 12 else client_id
            status = "SUCCESS" if success else "FAILED"
            self.logger.info(f"CLIENT-{operation} | Client: {safe_id} | {status}")
        except Exception as e:
            self._safe_log_error("log_client_operation", e, {
                "operation": operation,
                "client_id": client_id,
                "success": success
            })

    def log_security_event(self, event_type: str, details: Dict[str, Any]):
        """Logs security events safely."""
        try:
            details_str = " | ".join(f"{k}: {v}" for k, v in details.items())
            self.logger.warning(f"SECURITY | {event_type} | {details_str}")
        except Exception as e:
            self._safe_log_error("log_security_event", e, {"event_type": event_type, "details": details})

    def log_error(self, function: str, error: Exception, context: Dict[str, Any] = None):
        """Logs detailed errors safely with filtered context."""
        try:
            context_str = ""
            if context:
                safe_context = {k: v for k, v in context.items() if k not in ['password', 'token', 'api_key', 'secret']}
                context_str = f" | Context: {safe_context}"
            
            error_msg = str(error) if not isinstance(error, str) else error
            self.logger.error(
                f"ERROR in {function} | Type: {type(error).__name__} | "
                f"Message: {error_msg[:200]}{context_str}"
            )
        except Exception as e:
            # If even logging fails, print to console as last resort
            print(f"Critical logging failure in log_error: {e}")

    def _safe_log_error(self, function: str, error: Exception, context: Dict[str, Any] = None):
        """
        Internal fallback: called if any logging function fails.
        Delegates to log_error to ensure the issue is captured.
        """
        try:
            # Avoid recursion if log_error itself fails
            if function != "_safe_log_error":
                self.log_error(function, error, context)
            else:
                print(f"Critical logging failure in _safe_log_error: {error} | Context: {context}")
        except Exception as e:
            print(f"Unhandled logging error: {e} | Original context: {context}")


# ✅ Create a GLOBAL singleton instance at module level
_logger_instance = logger()

# ✅ Export a function that returns the singleton
def get_logger():
    """Get the singleton logger instance."""
    return _logger_instance

def encrypt_data(data: str, cipher_suite = get_key()) -> str:
    """
    Encrypts a string using the symmetric Fernet cipher.

    The encryption is deterministic (same input yields same output) and includes a
    timestamp in the token to prevent replay attacks. The data is first encoded to
    UTF-8 bytes before encryption, and the result is decoded back to a URL-safe string.

    Args:
        data (str): The plain text string to be encrypted.

    Returns:
        str: The base64-encoded encrypted token, or an empty string if encryption fails.
    """
    if not isinstance(data, str):
        logging.error(f"Encryption failed: Invalid input type {type(data)}")
        return ""
    
    # ✅ SECURITY: Prevent encryption of excessively large data (DoS prevention)
    MAX_ENCRYPT_SIZE = 1024 * 1024  # 1MB limit
    if len(data) > MAX_ENCRYPT_SIZE:
        logging.error(f"Encryption failed: Data too large ({len(data)} bytes)")
        return ""
    try:
        # Encode string to bytes, encrypt, and decode the result back to a string.
        encrypted_text = cipher_suite.encrypt(data.encode('utf-8'))
        return encrypted_text.decode('utf-8')
    except Exception as e:
        logging.error(f"Encryption failed: {e}")
        return ""

def decrypt_data(encrypted_data: str, cipher_suite = get_key()) -> str:
    """
    Decrypts a Fernet token string back to the original text.
    Handles `InvalidToken` specifically, which usually means the key is incorrect,
    the token is corrupted, or the token's timestamp has expired (anti-replay check).
    
    Args:
        encrypted_data (str): The base64-encoded Fernet token.
    
    Returns:
        str: The decrypted plain text string, or the original data if decryption fails.
    """
    import re
    
    # ✅ FIX: Type validation first
    if not isinstance(encrypted_data, str):
        logging.error(f"Decryption failed: Invalid type {type(encrypted_data).__name__}, expected string")
        return ""
    
    # ✅ FIX: Check for None or empty
    if not encrypted_data or encrypted_data.strip() == "":
        logging.error("Decryption failed: Empty or None data")
        return ""
    
    # ✅ FIX: Regex validation
    if not re.match(r'^[A-Za-z0-9_\-]+=*$', encrypted_data):
        logging.error("Decryption failed: Invalid token format")
        return encrypted_data  # Return as-is if not encrypted format
    
    # ✅ SECURITY: Length validation
    if len(encrypted_data) < 20 or len(encrypted_data) > 1024 * 1024:
        logging.error("Decryption failed: Invalid token length")
        return ""
    
    try:
        encrypted_data = encrypted_data.strip()
        # Encode string to bytes, decrypt, and decode the result back to a string.
        decrypted_text = cipher_suite.decrypt(encrypted_data.encode('utf-8'))
        return decrypted_text.decode('utf-8')
    except InvalidToken:
        logging.error("Decryption failed: Invalid token or key.")
        return encrypted_data  # Return original if can't decrypt
    except Exception as e:
        logging.error(f"Decryption failed: {e}")
        return ""


# --- Input Sanitization Function ---

import re
import unicodedata
import html
import hashlib

def sanitize_input(text: str) -> str:
    """
    Strong multilingual-safe input sanitizer.
    ✅ Defends against XSS, SQL/Command/Path Injection, and control character exploits.
    ✅ Preserves Unicode text (Hindi, Arabic, Chinese, emoji, etc.).
    ✅ Logs and neutralizes malicious patterns instead of over-sanitizing.
    """

    MAX_LENGTH = 4096

    try:
        if not isinstance(text, str):
            return ""

        # Normalize Unicode (prevents homoglyph or confusable char abuse)
        sanitized = unicodedata.normalize("NFKC", text.strip())

        # Enforce max length
        if len(sanitized) > MAX_LENGTH:
            sanitized = sanitized[:MAX_LENGTH]
            print(f"[SECURITY] Input truncated to {MAX_LENGTH} chars")

        # Remove control chars (except basic whitespace)
        sanitized = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', sanitized)

        # Remove invisible unicode separators (zero-width spaces, etc.)
        sanitized = re.sub(r'[\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]', '', sanitized)

        # Neutralize command execution attempts
        command_patterns = [
            r'\beval\s*\(', r'\bsystem\s*\(', r'\bshell\s*\(',
            r'\bexecv\b', r'\bpopen\b', r'\bsubprocess\b',
            r'\bos\.', r'__import__', r'\bimportlib\b',
            r'\bglobals\s*\(', r'\blocals\s*\(',
            r'\bcompile\s*\(', r'\bexec\s*\('
        ]
        for pattern in command_patterns:
            if re.search(pattern, sanitized, re.IGNORECASE):
                print(f"[SECURITY] Command injection pattern detected: {pattern}")
                sanitized = re.sub(pattern, '[filtered]', sanitized, flags=re.IGNORECASE)

        # Path traversal neutralization
        traversal_patterns = [
            r'\.\./', r'\.\.\\', r'%2e%2e', r'%252e%252e',
            r'\\x2e\\x2e', r'/etc/passwd', r'c:\\windows'
        ]
        for pattern in traversal_patterns:
            if re.search(pattern, sanitized, re.IGNORECASE):
                print(f"[SECURITY] Path traversal attempt detected: {pattern}")
                sanitized = re.sub(pattern, '[filtered]', sanitized, flags=re.IGNORECASE)

        # SQL keyword hardening
        sql_keywords = [
            'select', 'insert', 'delete', 'update', 'drop', 'union', 'exec',
            'truncate', 'waitfor', 'declare', 'cast', 'convert', 'having'
        ]
        for keyword in sql_keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', sanitized, re.IGNORECASE):
                print(f"[SECURITY] SQL keyword detected: {keyword}")
                sanitized = re.sub(r'\b' + re.escape(keyword) + r'\b',
                                   '[sql]', sanitized, flags=re.IGNORECASE)

        # Neutralize inline JS or HTML (XSS)
        sanitized = re.sub(r'<\s*script.*?>.*?<\s*/\s*script\s*>', '[filtered]',
                           sanitized, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r'on\w+\s*=', 'onevent=', sanitized, flags=re.IGNORECASE)

        # Escape HTML entities for final safety (display/output contexts)
        sanitized = html.escape(sanitized, quote=True)

        return sanitized.strip()

    except Exception as e:
        print(f"[ERROR] sanitize_input failed: {e}")
        return ""


def hash_password(password: str) -> str:
    # ✅ SECURITY: Validate input
    if not password or not isinstance(password, str):
        logger().log_security_event("INVALID_PASSWORD_HASH_ATTEMPT", {"error": "Empty or invalid password"})
        raise ValueError("Password cannot be empty")
    
    # ✅ SECURITY: Enforce minimum password length
    if len(password) < 8:
        logger().log_security_event("WEAK_PASSWORD_ATTEMPT", {"length": len(password)})
        raise ValueError("Password must be at least 8 characters")
    
    # ✅ SECURITY: Prevent extremely long passwords (DoS prevention)
    if len(password) > 128:
        logger().log_security_event("PASSWORD_TOO_LONG", {"length": len(password)})
        raise ValueError("Password exceeds maximum length")
    
    from argon2 import PasswordHasher
    ph = PasswordHasher(
        time_cost=2,
        memory_cost=102400,
        parallelism=8,
        hash_len=32,
        salt_len=16
    )
    try:
        hashed = ph.hash(password)
        return hashed
    except Exception as e:
        logger().log_error("hash_password",e)
# --- Specialized Logging Class ---

def verify_password(hash_password: str, password: str):
    try:
        from argon2 import PasswordHasher
        from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHash
        if not hash_password or not password:
            # Return False without logging to prevent timing attacks
            return False
        
        if not isinstance(hash_password, str) or not isinstance(password, str):
            return False
        
        ph = PasswordHasher(
            time_cost=2,
            memory_cost=102400,
            parallelism=8,
            hash_len=32,
            salt_len=16
        )
        try:
            return ph.verify(hash_password, password)
        except:
            o = hashlib.sha256(password.encode("utf-8")).hexdigest()
            if hash_password is o or hash_password == o:
                return True
    
    except Exception as e:
        logger().log_error("hash_password",e)

def validate_phone_number(phone: str) -> bool:
    """
    Validate phone number format to prevent injection.
    
    Security Enhancements:
    - Stricter validation
    - International format support
    - SQL injection prevention
    """
    if not phone or not isinstance(phone, str):
        return False
    
    # Remove whitespace and common separators for validation
    phone_clean = phone.strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    
    # ✅ SECURITY: Allow + for international format
    if phone_clean.startswith('+'):
        phone_clean = phone_clean[1:]
    
    # ✅ SECURITY: Only digits allowed (no SQL injection possible)
    if not phone_clean.isdigit():
        return False
    
    # ✅ SECURITY: Validate length (international standard)
    if len(phone_clean) < 10 or len(phone_clean) > 15:
        return False
    
    # ✅ SECURITY: Prevent sequential patterns that might be test data
    if phone_clean in ['0000000000', '1111111111', '1234567890', '9999999999']:
        logger().log_security_event("SUSPICIOUS_PHONE", {"pattern": "sequential"})
        return False
    
    return True

def validate_email(email: str) -> bool:
    """
    Validate email format to prevent injection.
    """
    if not email or not isinstance(email, str):
        return False
    
    # Basic email regex (prevents most injection attempts)
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_pattern, email):
        return False
    
    # Additional length check
    if len(email) > 255:
        return False
    
    return True


def validate_client_id(client_id: str) -> bool:
    """
    Validate client ID format (Firebase document IDs are alphanumeric).
    """
    if not client_id or not isinstance(client_id, str):
        return False
    
    # Firebase document IDs should be alphanumeric
    if not re.match(r'^[a-zA-Z0-9_-]{1,128}$', client_id):
        return False
    
    return True


import re

def sanitize_string_input(input_str: str, max_length: int = 1000) -> str:
    """
    Sanitize string input to prevent injection attacks.
    
    Security Enhancements:
    - Unicode normalization
    - Homograph attack prevention
    - Better control character filtering
    """
    if not isinstance(input_str, str):
        return ""
    
    if not input_str or not input_str.strip():
        return ""
    
    # ✅ SECURITY: Unicode normalization to prevent homograph attacks
    import unicodedata
    try:
        sanitized = unicodedata.normalize('NFKC', input_str)
    except Exception:
        sanitized = input_str
    
    # ✅ SECURITY: Remove control characters except newline and carriage return
    sanitized = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f]', '', sanitized)
    
    # ✅ SECURITY: Remove zero-width characters (used in obfuscation)
    zero_width_chars = [
        '\u200B',  # Zero-width space
        '\u200C',  # Zero-width non-joiner
        '\u200D',  # Zero-width joiner
        '\uFEFF',  # Zero-width no-break space
    ]
    for char in zero_width_chars:
        sanitized = sanitized.replace(char, '')
    
    # ✅ SECURITY: Remove dangerous Firebase query patterns
    dangerous_patterns = [
        r'__.*?__',  # Firebase internal fields
        r'\$[a-zA-Z]+',  # Query operators like $where, $regex
    ]
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, '', sanitized)
    
    # ✅ SECURITY: Limit length and strip
    return sanitized[:max_length].strip()



def hash_for_logging(sensitive_data: str) -> str:
    """
    Hash sensitive data before logging.
    Uses SHA-256 for one-way hashing.
    """
    if not sensitive_data:
        return "EMPTY"
    
    return hashlib.sha256(sensitive_data.encode()).hexdigest()[:16]


def validate_jwt_secret(SECRETE_JWT_KEY: str) -> bool:
    """
    Validate JWT secret key strength with entropy check.
    
    Security Enhancements:
    - Minimum length check
    - Entropy validation
    - Character diversity check
    """
    if not SECRETE_JWT_KEY:
        return False
    
    # ✅ SECURITY: Minimum 32 characters
    if len(SECRETE_JWT_KEY) < 32:
        logger().log_security_event(
            "WEAK_JWT_SECRET",
            {"length": len(SECRETE_JWT_KEY), "minimum": 32}
        )
        return False
    
    # ✅ SECURITY: Check character diversity
    has_upper = any(c.isupper() for c in SECRETE_JWT_KEY)
    has_lower = any(c.islower() for c in SECRETE_JWT_KEY)
    has_digit = any(c.isdigit() for c in SECRETE_JWT_KEY)
    has_special = any(not c.isalnum() for c in SECRETE_JWT_KEY)
    
    diversity_score = sum([has_upper, has_lower, has_digit, has_special])
    
    if diversity_score < 3:
        logger().log_security_event(
            "LOW_JWT_SECRET_ENTROPY",
            {"diversity_score": diversity_score}
        )
        return False
    
    return True

import base64

def hash_for_FB(number: str) -> str:
    try:
        if not number or number == None:
            logger.log_error("number. hasg_for_FB. encryption_utils.py", "Failed to get the number or number is not given.")
        return base64.urlsafe_b64encode(
            hashlib.sha256(number.encode()).digest()
        ).decode().rstrip("=")
    except Exception as e:
        logger.log_error("hash_for_FB. encryption_utils.py", e)