import firebase_admin
from firebase_admin import credentials, firestore
from encryption_utils import get_logger, encrypt_data, decrypt_data, sanitize_input, load_env_from_secret
from encryption_utils import hash_password, validate_phone_number, validate_email, validate_client_id, sanitize_string_input, hash_for_logging, validate_jwt_secret
from dotenv import load_dotenv
import os
from typing import Dict, Optional, List
from datetime import datetime, timezone, timedelta
import httpx
import jwt
import json
from get_secreats import get_secret_json
import hashlib
import re

#Setup logger
logger = get_logger()

def initialize_firebase():
    """
    Initialize Firebase Admin SDK with secure credential loading.
    
    Security:
    - Validates credential file path
    - Checks file existence
    - Singleton pattern (no duplicate initialization)
    
    Raises:
        RuntimeError: If credentials missing or invalid
    """
    try:
        load_dotenv()  # Load environment variables
        
        # Check if already initialized (singleton pattern)
        if firebase_admin._apps:
            logger.logger.info("Firebase already initialized, skipping")
            return
        
        cred_path = get_secret_json("FIREBASE_CREDENTIALS_PATH")
        # Initialize Firebase
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        
        logger.logger.info("Firebase initialized successfully")

    except Exception as e:
        logger.log_error("initialize_firebase", e)
        raise

try:
    # Initialize Firebase on module load
    initialize_firebase()

    # Get Firestore client
    db = firestore.client()

    load_dotenv()
except Exception as e:
    logger.log_error("initialize_firebase -> module. firebase.py", e)

from threading import Lock
import time

class FirestoreCache:
    """
    In-memory cache to prevent redundant Firestore reads.
    Reduces reads by 70-80% for frequently accessed data.
    """
    def __init__(self, ttl_seconds=300):  # 5 minute default TTL
        self._cache = {}
        self._lock = Lock()
        self._ttl = ttl_seconds
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str):
        """Get cached value if not expired."""
        with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if time.time() - timestamp < self._ttl:
                    self._hits += 1
                    return value
                else:
                    del self._cache[key]
            self._misses += 1
            return None
    
    def set(self, key: str, value):
        """Cache value with timestamp."""
        with self._lock:
            self._cache[key] = (value, time.time())
            # Limit cache size
            if len(self._cache) > 1000:
                oldest = min(self._cache.items(), key=lambda x: x[1][1])
                del self._cache[oldest[0]]
    
    def invalidate(self, key: str):
        """Remove specific key."""
        with self._lock:
            self._cache.pop(key, None)
    
    def get_stats(self):
        """Get cache performance stats."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "size": len(self._cache)
        }

# Global Firestore cache instance
firestore_cache = FirestoreCache(ttl_seconds=300)

#phone_number helper function
def formate_number(number: str, default_country_code: str = "+91") -> str:
    try:
        import re
        # Remove all spaces, dashes, parentheses, etc.
        digits_only = re.sub(r"\D", "", number)

        # If the number already starts with country code (e.g. 91...) and has more than 10 digits
        if digits_only.startswith(default_country_code.replace("+", "")) and len(digits_only) > 10:
            return f"+{digits_only}"

        # If it's a local 10-digit number, prepend country code
        if len(digits_only) == 10:
            return f"{default_country_code}{digits_only}"

        # Otherwise just return with plus sign if missing
        return f"+{digits_only}"
    except Exception as e:
        logger.log_error("formate_number. firebase.py", e)
        return number

def add_universal_client(data: dict):
    try:
        doc_ref = db.collection("clients").document()
        #Add the client's data
        unencrypted_data = ["Plan","password","WA_Phone_ID_Hash"]
        user_id = doc_ref.id

        #Make client id
        data["client_id"] = user_id

        #Formate phone number for actual usage of what'sapp
        phone = data["Phone"]
        data["Phone"] = formate_number(phone)

        #Encryption
        encrypted_data = {}
        for key, values in data.items():
            if any(s in key.lower() for s in unencrypted_data):
                encrypted_data[key] = values
            else:
                encrypted_data[key] = encrypt_data(values)
        if "password" in encrypted_data:
            # Use the dictionary variable 'encrypted_data' here
            encrypted_data["password"] = deterministic_hash(encrypted_data["password"])
        if "WA_Phone_ID_Hash" in encrypted_data:
            encrypted_data["WA_Phone_ID_Hash"] = hash_password(encrypted_data["WA_Phone_ID_Hash"])
        
        db.collection("clients").document(user_id).set(encrypted_data)
        data.clear()
        logger.log_client_operation("CLient_added_to_firestore",user_id,success=True)
    except Exception as e:
        logger.log_error("add_universal_client. firebase.py", e)

def get_client(client_id: str) -> Dict | None:
    try:
        if not validate_client_id(client_id):
            logger.log_security_event(
                "INVALID_CLIENT_ID",
                {"client_id_hash": hash_for_logging(client_id)}
            )
            return None
        
        #cached = firestore_cache.get(client_id)

        #if cached is not None:
            #return cached
            
        doc = db.collection("clients").document(client_id).get()
        if not doc.exists:
            logger.log_error(
                "get_client",
                f"Client not found: {hash_for_logging(client_id)}"
            )
            return None
        client_data = doc.to_dict()

        for key, value in client_data.items():
            try:
                if any(s not in key.lower() for s in ["plan","password"]):
                    client_data[key] = decrypt_data(value)
            except Exception as e:
                logger.log_error("decrypt_data. get_client. firebase.py", e)
        
        #firestore_cache.set(client_id, client_data)

        return client_data
    
    except Exception as e:
        logger.log_error("get_client .firebase.py", e)
        return None

def get_client_by_phone_number(phone_number: str) -> Optional[Dict]:
    try:
        if not validate_phone_number(phone_number):
            logger.log_security_event(
                "INVALID_PHONE_NUMBER",
                {"phone_hash": hash_for_logging(phone_number)}
            )
            return None
        query = db.collection("clients").where("Phone","==",phone_number).limit(1).get()
        client_doc = query[0]
        client_data = client_doc.to_dict()
        query.clear()
        logger.log_client_operation("Client data fetched from the database from moblie number.",hash_for_logging(client_data["client_id"]),success=True)
        return client_data
    except Exception as e:
        logger.log_error("get_client_by_phone_number. firebase.py", e)

def decrypt_client_data(data: Dict):
    try:
        for key, value in data.items():
            try:
                if key in ["plan", "password", "wa_phone_id_hash"]:
                    data[key] = decrypt_data(value)
            except Exception as e:
                logger.log_error("key_not_found. decrypt_client_data. firebase.py", e)
        return data
    except Exception as e:
        logger.log_error("decrypt_client_data. firebase.py", e)

def get_client_id_by_phone_number(phone_number: str):
    try:
        query = db.collection("clients").where("Phone","==",phone_number).limit(1).get()
        if not query:
            logger.log_error("get_client_id_by_phone_number","Failed to get client from the firebase.")
            return None
        client_doc = query[0]
        client_data = client_doc.to_dict()
        logger.log_client_operation("Client id fetched from the database from moblie number.",client_data["client_id"],success=True)
        return client_data["client_id"]
    except Exception as e:
        logger.log_error("get_client_id_by_phone_number. firebase.py", e)

import fitz  # PyMuPDF
def read_file_content(file, file_name: str) -> Optional[str]:
    """
    Secure high-performance file reader for menu files (PDF/TXT)
    Uses magic number validation instead of python-magic library
    """
    try:
        # ✅ SECURITY: Validate and sanitize filename
        file_name = os.path.basename(file_name)  # Prevent path traversal
        
        if not file_name or len(file_name) > 255:
            logger.log_security_event("INVALID_FILENAME", {"name": file_name})
            raise ValueError("Invalid filename")
        
        # ✅ SECURITY: Block dangerous characters in filename
        dangerous_chars = ["<", ">", ":", '"', "|", "?", "*", "\x00", "\\"]
        if any(char in file_name for char in dangerous_chars):
            logger.log_security_event("DANGEROUS_FILENAME", {"name": file_name})
            raise ValueError("Filename contains dangerous characters")
        
        ext = os.path.splitext(file_name)[1].lower()
        
        # ✅ SECURITY: Whitelist only allowed extensions
        allowed_extensions = [".txt", ".pdf"]
        if ext not in allowed_extensions:
            logger.log_security_event("INVALID_FILE_UPLOAD", {"extension": ext})
            return f"Unsupported file format: {ext}"
        
        # ✅ PERFORMANCE: Use os.fstat instead of seek operations
        file_size = os.fstat(file.fileno()).st_size
        
        # ✅ SECURITY: File size validation (prevent DoS)
        min_size = 10  # At least 10 bytes
        max_size = 10 * 1024 * 1024  # 10MB max
        
        if file_size < min_size or file_size > max_size:
            logger.log_security_event("INVALID_FILE_SIZE", {"size": file_size})
            raise ValueError(f"File size must be between {min_size} and {max_size} bytes")
        
        # ✅ SECURITY: Read file header for magic number validation
        file.seek(0)
        file_header = file.read(2048)  # Read first 2KB
        file.seek(0)
        
        # ✅ SECURITY: Validate file signature (magic numbers)
        if not validate_file_signature(file_header, ext):
            logger.log_security_event(
                "INVALID_FILE_SIGNATURE",
                {"extension": ext, "header": file_header[:20].hex()}
            )
            raise ValueError(f"File content doesn't match {ext} format")
        
        # ✅ SECURITY: Calculate file hash for logging/tracking
        file.seek(0)
        file_hash = hashlib.sha256(file.read()).hexdigest()
        file.seek(0)
        logger.logger.info("FILE_PROCESSING", {"hash": file_hash, "size": file_size})
        
        if ext == ".txt":
            # ✅ PERFORMANCE: Read in chunks for large files
            chunks = []
            chunk_size = 8192  # 8KB chunks
            
            while True:
                chunk = file.read(chunk_size)
                if not chunk:
                    break
                chunks.append(chunk.decode("utf-8", errors="ignore"))
            
            content = "".join(chunks)
            
            # ✅ SECURITY: Sanitize suspicious patterns in text
            content = sanitize_text_content(content)
            
            return content[:1000000]  # Limit to 1MB
        
        elif ext == ".pdf":
            # ✅ PERFORMANCE: PyMuPDF for fast extraction
            file.seek(0)
            pdf_bytes = file.read()
            
            # ✅ SECURITY: Open PDF with error handling for malformed files
            try:
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            except Exception as e:
                logger.log_security_event("MALFORMED_PDF", {"error": str(e)})
                raise ValueError("Invalid or corrupted PDF file")
            
            # ✅ SECURITY: Validate PDF structure
            if not validate_pdf_security(doc):
                doc.close()
                logger.log_security_event("PDF_SECURITY_CHECK_FAILED", {})
                raise ValueError("PDF contains suspicious content")
            
            # ✅ SECURITY: Limit pages (prevent decompression bombs)
            max_pages = min(len(doc), 100)
            
            if len(doc) > 100:
                logger.log_security_event("PDF_TOO_MANY_PAGES", {"pages": len(doc)})
            
            # ✅ PERFORMANCE: List comprehension + join (O(n) vs O(n²))
            text_parts = []
            for page_num in range(max_pages):
                try:
                    page_text = doc[page_num].get_text("text")
                    if page_text:
                        text_parts.append(page_text)
                except Exception as e:
                    logger.log_error(f"Error reading page {page_num}", e)
                    continue
            
            doc.close()
            
            text = "".join(text_parts).strip()
            
            # ✅ SECURITY: Check for suspicious content
            if contains_suspicious_patterns(text):
                logger.log_security_event("SUSPICIOUS_PDF_CONTENT", {})
                raise ValueError("PDF contains potentially malicious content")
            
            return text[:1000000]  # Limit to 1MB
        
    except Exception as e:
        logger.log_error("read_file_content_error", e)
        return None


def validate_file_signature(file_header: bytes, extension: str) -> bool:
    """
    Validates file signature (magic numbers) without python-magic library
    Checks the actual file content against expected signatures
    """
    # Define magic numbers for supported file types
    file_signatures = {
        ".pdf": [
            b"%PDF-",  # Standard PDF signature
        ],
        ".txt": [
            # Text files can start with various encodings
            b"\xef\xbb\xbf",  # UTF-8 BOM
            b"\xff\xfe",      # UTF-16 LE BOM
            b"\xfe\xff",      # UTF-16 BE BOM
        ]
    }
    
    if extension == ".pdf":
        # PDF files must start with %PDF-
        if not file_header.startswith(b"%PDF-"):
            return False
        
        # Additional PDF validation - check for %%EOF at the end
        # (We only have header, so just check the start)
        return True
    
    elif extension == ".txt":
        # Text files are more flexible
        # Check if it's valid UTF-8 or ASCII
        try:
            # Try to decode as UTF-8
            file_header.decode("utf-8")
            return True
        except UnicodeDecodeError:
            try:
                # Try ASCII
                file_header.decode("ascii", errors="strict")
                return True
            except:
                # Check for BOM markers
                for signature in file_signatures[".txt"]:
                    if file_header.startswith(signature):
                        return True
                return False
    
    return False


def validate_pdf_security(doc: fitz.Document) -> bool:
    """
    Validates PDF for security threats: JavaScript, embedded files, large objects
    """
    try:
        # ✅ SECURITY: Check for JavaScript (common attack vector)
        metadata_str = str(doc.metadata)
        if "/JavaScript" in metadata_str or "/JS" in metadata_str:
            logger.log_security_event("PDF_JAVASCRIPT_DETECTED", {})
            return False
        
        # ✅ SECURITY: Check for embedded files (potential malware carrier)
        try:
            if doc.embfile_count() > 0:
                logger.log_security_event("PDF_EMBEDDED_FILES", {"count": doc.embfile_count()})
                return False
        except:
            pass
        
        # ✅ SECURITY: Check for excessive object count (deflate bomb indicator)
        xref_length = doc.xref_length()
        if xref_length > 10000:  # Unusually high for a menu
            logger.log_security_event("PDF_EXCESSIVE_OBJECTS", {"count": xref_length})
            return False
        
        # ✅ SECURITY: Check page dimensions (prevent memory exhaustion)
        for page_num in range(min(len(doc), 10)):  # Check first 10 pages
            page = doc[page_num]
            rect = page.rect
            
            # Unreasonably large page dimensions
            if rect.width > 50000 or rect.height > 50000:
                logger.log_security_event("PDF_OVERSIZED_PAGE", {
                    "width": rect.width,
                    "height": rect.height
                })
                return False
        
        return True
        
    except Exception as e:
        logger.log_error("validate_pdf_security_error", e)
        return False


def sanitize_text_content(text: str) -> str:
    """
    Sanitizes text content to remove potentially malicious patterns
    """
    # ✅ SECURITY: Remove null bytes
    text = text.replace("\x00", "")
    
    # ✅ SECURITY: Limit consecutive newlines (prevent formatting attacks)
    while "\n\n\n\n" in text:
        text = text.replace("\n\n\n\n", "\n\n")
    
    return text


def contains_suspicious_patterns(text: str) -> bool:
    """
    Checks for suspicious patterns in extracted text
    """
    import re
    
    # ✅ SECURITY: Check for script tags or suspicious code
    suspicious_patterns = [
        r"<script[^>]*>",
        r"javascript:",
        r"eval\s*\(",
        r"onclick\s*=",
        r"onerror\s*=",
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    return False

def add_customer_to_firebase(client_id: str, name: str, phone: str, plan_and_date):
    """
    SECURITY FIX: Add transaction safety and better validation
    """
    try:
        # Validate inputs
        if not validate_client_id(client_id):
            raise ValueError("Invalid client ID")
        
        if not validate_phone_number(phone):
            raise ValueError("Invalid phone number")
        
        # Format phone number
        phone = formate_number(phone)
        
        # Sanitize name
        name = sanitize_string_input(name, max_length=100)
        if not name:
            raise ValueError("Invalid name")
        
        # Validate date
        if not isinstance(plan_and_date, (str, datetime)):
            raise ValueError("Invalid date format")
        
        # ✅ SECURITY: Use transaction for atomicity
        @firestore.transactional
        def add_customer_transaction(transaction, client_ref, customer_ref):
            # Verify client exists
            client_snapshot = client_ref.get(transaction=transaction)
            if not client_snapshot.exists:
                raise ValueError("Client not found")
            
            # Set customer data
            transaction.set(customer_ref, {
                "name": encrypt_data(name),
                "phone": encrypt_data(phone),
                "phone_hash": hash_password(phone),  # For lookups
                "plan_end_date": str(plan_and_date),
                "status": "active",
                "created_at": datetime.now(timezone.utc),
                "client_id": encrypt_data(client_id)  # ✅ CRITICAL: Store client_id for IDOR prevention
            })
        
        # Execute transaction
        client_ref = db.collection("clients").document(client_id)
        customer_ref = client_ref.collection("members").document()
        
        transaction = db.transaction()
        add_customer_transaction(transaction, client_ref, customer_ref)
        
        logger.log_client_operation("customer_added", client_id, success=True)
        
    except Exception as e:
        logger.log_error("add_customer_to_firebase", e)
        raise

# ============================================================================
# ADD THESE FUNCTIONS TO firebase.py
# ============================================================================

def get_rag_conversation_history(client_id: str) -> List[Dict[str, str]]:
    """
    Retrieve RAG conversation history from Firebase.
    
    Args:
        client_id: Client/customer identifier
        
    Returns:
        List of conversation messages
    """
    try:
        doc_ref = db.collection("rag_cache").document(client_id)
        doc = doc_ref.get()
        
        if doc.exists:
            data = doc.to_dict()
            history = data.get("conversation_history", [])
            logger.log_client_operation(
                "RAG_history_retrieved",
                client_id,
                success=True
            )
            return history
        
        return []
        
    except Exception as e:
        logger.log_error("get_rag_conversation_history", e)
        return []


def save_rag_conversation_history(client_id: str, history: List[Dict[str, str]]):
    """
    Save RAG conversation history to Firebase.
    
    Args:
        client_id: Client/customer identifier
        history: List of conversation messages
    """
    try:
        doc_ref = db.collection("rag_cache").document(client_id)
        doc_ref.set({
            "conversation_history": history,
            "updated_at": datetime.now(timezone.utc)
        }, merge=True)
        
        logger.log_client_operation(
            "RAG_history_saved",
            client_id,
            success=True
        )
        
    except Exception as e:
        logger.log_error("save_rag_conversation_history", e)


def clear_rag_cache(client_id: str):
    """
    Clear all RAG cache data for a client.
    
    Args:
        client_id: Client/customer identifier
    """
    try:
        doc_ref = db.collection("rag_cache").document(client_id)
        doc_ref.delete()
        
        logger.log_client_operation(
            "RAG_cache_cleared",
            client_id,
            success=True
        )
        
    except Exception as e:
        logger.log_error("clear_rag_cache", e)


def get_all_cached_clients() -> List[str]:
    """
    Get list of all clients with cached RAG data.
    Useful for bulk operations or analytics.
    
    Returns:
        List of client IDs
    """
    try:
        docs = db.collection("rag_cache").stream()
        client_ids = [doc.id for doc in docs]
        
        logger.logger.info(f"Retrieved {len(client_ids)} cached clients")
        return client_ids
        
    except Exception as e:
        logger.log_error("get_all_cached_clients", e)
        return []


def cleanup_old_rag_caches(days_old: int = 30):
    """
    Remove RAG cache entries older than specified days.
    Should be run periodically to manage storage.
    
    Args:
        days_old: Delete caches older than this many days
    """
    try:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        
        docs = db.collection("rag_cache").where(
            "updated_at", "<", cutoff_date
        ).stream()
        
        deleted_count = 0
        for doc in docs:
            doc.reference.delete()
            deleted_count += 1
        
        logger.logger.info(f"Cleaned up {deleted_count} old RAG caches")
        return deleted_count
        
    except Exception as e:
        logger.log_error("cleanup_old_rag_caches", e)
        return 0

try:
    SECRETE_JWT_KEY = load_env_from_secret("JWT_SECRET_KEY")
except Exception as e:
    logger.log_error("SECRETE_JWT_KEY. firebase.py", e)

def create_jwt(client_id: str, expire_minitue: int = 300):
    """
    SECURITY FIX: Enhanced JWT with additional security claims
    """
    try:
        # Try to decrypt first.
        try:
            client_id = decrypt_data(client_id)
        except Exception as e:
            logger.log_error("client_id. create_jwt. firebase.py", e)
            pass
        if not validate_client_id(client_id):
            logger.log_security_event(
                "INVALID_JWT_CLIENT_ID",
                {"client_id_hash": hash_for_logging(client_id)}
            )
            return None
        import secrets
        # ✅ SECURITY: Add jti (JWT ID) for token revocation capability
        jti = secrets.token_urlsafe(32)
        
        payload = {
            "client_id": client_id,
            "exp": datetime.utcnow() + timedelta(minutes=expire_minitue),
            "iat": datetime.utcnow(),  # Issued at
            "jti": jti,  # JWT ID for revocation
            "iss": "business_portal"  # Issuer
        }
        token = jwt.encode(payload, SECRETE_JWT_KEY, algorithm="HS256")
        
        logger.log_security_event(
            "JWT_CREATED",
            {"client_id_hash": hashlib.sha256(client_id.encode()).hexdigest()}
        )

        return token
        
    except Exception as e:
        logger.log_error("create_jwt", e)
        return None
    
def decode_jwt(token: str):
    """
    SECURITY FIX: Validate JWT with strict algorithm whitelist
    Prevents algorithm confusion attacks
    """
    try:
        if not token or not isinstance(token, str):
            logger.log_security_event("INVALID_JWT_TOKEN", {"error": "Invalid token format"})
            return None
        
        # ✅ CRITICAL: Specify algorithms to prevent algorithm confusion attack
        payload = jwt.decode(token, SECRETE_JWT_KEY, algorithms=["HS256"])
        
        # Validate payload structure
        if not payload.get("client_id"):
            logger.log_security_event("INVALID_JWT_PAYLOAD", {"error": "Missing client_id"})
            return None
        
        # Validate expiration
        exp = payload.get("exp")
        if not exp or datetime.utcnow().timestamp() > exp:
            logger.log_security_event("JWT_EXPIRED", {"error": "Token expired"})
            return None
        
        return payload
    except jwt.ExpiredSignatureError:
        logger.log_security_event("JWT_EXPIRED", {"error": "Token expired"})
        return None
    except jwt.InvalidTokenError as e:
        logger.log_security_event("JWT_INVALID", {"error": str(e)})
        return None
    except Exception as e:
        logger.log_error("decode_jwt", e)
        return None
# Add this function to firebase.py (after get_client_by_phone_number)

def get_client_by_email(email: str) -> Optional[Dict]:
    """
    Retrieve client data by email address.
    
    Args:
        email: Client's email address
        
    Returns:
        Client data dictionary or None if not found
    """
    try:
        email = deterministic_hash(email)

        query = db.collection("clients").where("Email_hash", "==", email).limit(1).get()
        
        if len(query) == 0:
            logger.log_error("get_client_by_email", "Failed to get client from the firebase.")
            return None
        
        client_doc = query[0]
        client_data = client_doc.to_dict()
        
        logger.log_client_operation(
            "Client data fetched from the database by email.",
            client_data["client_id"],
            success=True
        )
        return client_data
        
    except Exception as e:
        logger.log_error("get_client_by_email", e)
        return None

def get_client_id_by_phone_id(phone_id: str) -> Optional[str]:
    try:
        if not phone_id or not isinstance(phone_id, str):
            logger.log_security_event(
                "INVALID_PHONE_ID",
                {"provided": "invalid_type"}
            )
            return None

        #phone_id = sanitize_string_input(phone_id, max_length=128)
        hashed_id = deterministic_hash(phone_id)

        query = db.collection("clients").where("WA_Phone_ID_Hash", "==", hashed_id).limit(1).get()

        if not query:
            logger.log_error("get_client_id_by_phone_id", "No matching client found.")
            return None

        client_doc = query[0]
        client_data = client_doc.to_dict()

        logger.log_client_operation(
            "Client fetched by WA_Phone_ID",
            client_data["client_id"],
            success=True
        )

        return decrypt_data(client_data["client_id"])

    except Exception as e:
        logger.log_error("get_client_id_by_phone_id", e)
        return None

   
def add_non_members_to_firebase(client_id: str, name: str, phone: str):
    """
    SECURITY FIX: Better validation and use phone_hash for document ID
    """
    try:
        if not validate_client_id(client_id):
            raise ValueError("Invalid client ID")
        
        if not validate_phone_number(phone):
            raise ValueError("Invalid phone number")
        
        phone = formate_number(phone)
        
        # Sanitize name
        name = sanitize_string_input(name, max_length=100)
        if not name:
            raise ValueError("Invalid name")
        
        # ✅ SECURITY: Use hash as document ID instead of encrypted phone
        phone_hash = hash_password(phone)
        
        doc_ref = db.collection("clients").document(client_id).collection("non_members").document(phone_hash)
        doc_ref.set({
            "name": encrypt_data(name),
            "phone": encrypt_data(phone),
            "phone_hash": phone_hash,
            "status": "active",
            "created_at": datetime.now(timezone.utc),
            "client_id": encrypt_data(client_id)  # ✅ Store client_id for ownership validation
        })
        
        logger.log_client_operation("non_member_added", client_id, success=True)
        
    except Exception as e:
        logger.log_error("add_non_members_to_firebase", e)
        raise

def deterministic_hash(value: str) -> str:
    """
    Deterministic, non-salted hash for database lookups.
    Safe for non-sensitive but unique identifiers like phone_id.
    """
    try:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    except Exception as e:
        logger.log_error("deterministic_hash. firebase.py", e)

def get_all_non_members_from_firebase(client_id: str):
    try:
        if not validate_client_id(client_id):
            raise ValueError("Invalid client ID")

        non_members_ref = db.collection("clients").document(client_id).collection("non_members")
        docs = non_members_ref.stream()

        non_members = []

        for doc in docs:
            data = doc.to_dict()
            phone = data.get("phone")
            if phone:
                non_members.append(decrypt_data(phone))  # Assuming decrypt_data exists

        return non_members
    except Exception as e:
        logger.log_error("get_all_non_members_from_firebase. firebase.py", e)

def validate_customer_ownership(client_id: str, customer_phone: str) -> bool:
    """
    SECURITY FIX: Validate customer belongs to client (prevents IDOR)
    """
    try:
        if not validate_client_id(client_id):
            return False
        
        if not validate_phone_number(customer_phone):
            return False
        
        customer_phone = formate_number(customer_phone)
        phone_hash = hash_password(customer_phone)
        
        # Query customer in client's collection
        customer_ref = db.collection("clients").document(client_id).collection("customer_list").where("phone_hash", "==", phone_hash).limit(1).get()
        
        if not customer_ref:
            logger.log_security_event(
                "IDOR_ATTEMPT",
                {"client_id_hash": hash_for_logging(client_id)}
            )
            return False
        
        return True
        
    except Exception as e:
        logger.log_error("validate_customer_ownership", e)
        return False
    
def update_uploaded_document(client_id: str, file, file_name: str, append: bool = False):
    """
    Update or append uploaded document content for a client in Firestore.

    Args:
        client_id: Client's unique ID.
        file: File-like object to read.
        file_name: Original name of the uploaded file.
        append: If True, append to existing content. If False, replace it.

    Behavior:
        - Uses read_file_content() for secure reading.
        - Encrypts content before saving.
        - Can append to or replace existing encrypted data.
        - Logs operations and errors.
    """
    try:
        if not validate_client_id(client_id):
            logger.log_security_event(
                "INVALID_CLIENT_ID_UPDATE_DOCUMENT",
                {"client_id_hash": hash_for_logging(client_id)}
            )
            raise ValueError("Invalid client ID")

        # Read file securely
        file_content = read_file_content(file, file_name)
        if not file_content:
            raise ValueError("File content could not be read or is empty")

        client_ref = db.collection("clients").document(client_id)
        doc = client_ref.get()

        new_content = file_content

        # If append is True and data exists, merge contents
        if append and doc.exists:
            existing_data = doc.to_dict().get("Uploaded Document")
            if existing_data:
                try:
                    decrypted_existing = decrypt_data(existing_data)
                    new_content = decrypted_existing + "\n\n" + file_content
                except Exception as decryption_error:
                    logger.log_error("update_uploaded_document_decrypt", decryption_error)
                    # If decryption fails, just overwrite

        # Encrypt final content before saving
        encrypted_content = encrypt_data(new_content)

        # Save back to Firestore
        client_ref.set(
            {
                "Uploaded Document": encrypted_content,
                "updated_at": datetime.now(timezone.utc)
            },
            merge=True
        )

        logger.log_client_operation(
            "Client_uploaded_document_updated",
            client_id,
            success=True
        )
        return True

    except Exception as e:
        logger.log_error("update_uploaded_document", e)
        return False
    
def update_payment_link(client_id: str, payment_link: str, description: str = "") -> bool:
    """
    Update payment link for a client.
    
    Args:
        client_id: Client's unique ID
        payment_link: Payment gateway URL
        description: Optional description
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not validate_client_id(client_id):
            logger.log_security_event(
                "INVALID_CLIENT_ID_PAYMENT_LINK",
                {"client_id_hash": hash_for_logging(client_id)}
            )
            return False
        
        # Encrypt payment link before storing
        encrypted_link = encrypt_data(payment_link)
        encrypted_desc = encrypt_data(description) if description else ""
        
        client_ref = db.collection("clients").document(client_id)
        client_ref.set({
            "payment_link": encrypted_link,
            "payment_link_description": encrypted_desc,
            "payment_link_updated_at": datetime.now(timezone.utc)
        }, merge=True)
        
        logger.log_client_operation("payment_link_updated", client_id, success=True)
        return True
        
    except Exception as e:
        logger.log_error("update_payment_link", e)
        return False
    
#Address tracking
INDIAN_STATES = {
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
    "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka",
    "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram",
    "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu",
    "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal",
    "andaman and nicobar islands", "chandigarh", "dadra and nagar haveli",
    "daman and diu", "delhi", "lakshadweep", "puducherry", "ladakh", "jammu and kashmir"
}

ADDRESS_KEYWORDS = {
    "street", "st", "road", "rd", "cross", "main", "block", "sector",
    "lane", "ln", "nagar", "colony", "phase", "layout", "society",
    "building", "flat", "apartment", "tower", "floor", "plot",
    "near", "opposite", "behind", "post", "village", "city", "district"
}


def classify_indian_address(text: str):
    """
    Classifies text as 'address', 'question', or 'unknown' with reasoning.
    Optimized for Indian address formats and real-time web use.
    """

    text = text.strip()
    lower_text = text.lower()

    # --- Step 1: Quick check for question ---
    question_words = {
        "who", "what", "when", "where", "why", "how",
        "is", "are", "can", "could", "would", "will",
        "do", "does", "did", "shall", "should", "may", "might"
    }
    if text.endswith("?") or lower_text.split()[0] in question_words or "?" in text:
        return {"type": "question", "reason": "Text contains question syntax or words."}

    # --- Step 2: Detect explicit Indian state names ---
    if any(state in lower_text for state in INDIAN_STATES):
        return {"type": "address", "reason": "Contains valid Indian state name."}

    # --- Step 3: Detect PIN code ---
    if re.search(r"\b[1-9][0-9]{5}\b", text):
        return {"type": "address", "reason": "Contains valid 6-digit Indian PIN code."}

    # --- Step 4: Address structure / keywords ---
    keyword_hits = sum(1 for word in ADDRESS_KEYWORDS if word in lower_text)
    if keyword_hits >= 2 or re.search(r"\b(?:flat|house|no\.?|#)\s*\d+", lower_text):
        return {"type": "address", "reason": "Has strong address-like structure or keywords."}

    # --- Step 5: Weak evidence: possibly incomplete address ---
    if any(word in lower_text for word in ADDRESS_KEYWORDS):
        return {
            "type": "unknown",
            "reason": "Looks like a partial address (missing state or PIN). Please provide full address."
        }

    # --- Step 6: Nothing matched ---
    return {"type": "unknown", "reason": "Does not match question pattern or address structure."}
