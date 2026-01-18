#--------------------
#IMPORTS
#--------------------
import httpx
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
from fastapi.responses import PlainTextResponse, JSONResponse
from firebase import get_client_id_by_phone_id, get_client, get_all_non_members_from_firebase, formate_number, get_client_by_email, decrypt_client_data, create_jwt, read_file_content, add_universal_client, add_customer_to_firebase, add_non_members_to_firebase, update_uploaded_document, decode_jwt, initialize_firebase
from handle_all_things import handle_user_message, handle_user_message_restaurents, handle_user_message_bakery, handle_user_message_free_version, handle_user_message_cloth_store
from Rag import RAGBot
from functools import lru_cache
from datetime import datetime, timedelta, date
import time
from encryption_utils import get_logger, validate_phone_number, hash_for_logging, sanitize_string_input, sanitize_input, decrypt_data, verify_password
from contextlib import asynccontextmanager
import asyncio
import firebase_admin
from firebase_admin import credentials, firestore
import logging
from typing import Dict
from rate_limiter import RateLimiter
from fastapi import Depends, Header
import json
from get_secreats import load_env_from_secret, get_secret_json, unwrap_secret
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, EmailStr, validator
from typing import Optional, Tuple
from fastapi import File, UploadFile, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from we_are import we_are
from threading import Lock
import re
from fallback import fallback
import os
import sys
from collections import deque

global_http_client: httpx.AsyncClient = None

rate_limiter = RateLimiter()

log = logging.getLogger(__name__)

logger = get_logger()

load_dotenv()

ADMIN_API_KEY = load_env_from_secret("ADMIN_API_KEY")

# Initialize Firebase on module load
initialize_firebase()

# Get Firestore client
db = firestore.client()

#Security
if not ADMIN_API_KEY:
    error_msg = "FATAL CONFIG ERROR: ADMIN_API_KEY not set. Shutting down."
    logger.log_security_event("FATAL_CONFIG_ERROR", {"error": error_msg, "system": "MAIN"})
    log.critical(error_msg) 

try:
    app = FastAPI(title="Simple WhatsApp Bot")

    app.mount("/static", StaticFiles(directory="static"), name="static")

    templates = Jinja2Templates(directory="templates") 

    _CLIENT_ID_PATTERN = re.compile(r'^[A-Za-z0-9_-]{8,64}$')  # allowlist: letters, digits, dash, underscore

    processed_messages = deque(maxlen=100) 
except Exception as e:
    logger.log_error("app, template, _CLIENT_ID_PATTERN. app.py", e)

#------------_Imports Over _-------------


#Modles
#--------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class CustomerRequest(BaseModel):
    name: str
    phone: str
    plan_end_date: str

class NonMemberRequest(BaseModel):
    name: str
    phone: str

#Caching
class RAGCacheManager:
    """
    Secure RAG bot caching with TTL and thread-safe operations.
    Avoids logging sensitive data and ensures safe Firebase queries.
    """
    def __init__(self, ttl_minutes: int = 30, max_cache_size: int = 100):
        self._cache = {}  # {client_id: {'rag': RAGBot, 'client_data': dict, 'expires_at': timestamp}}
        self._ttl_seconds = ttl_minutes * 60
        self._max_cache_size = max_cache_size
        self._hits = 0
        self._misses = 0
        self._lock = Lock()  # ✅ CRITICAL: This creates the lock object, don't call it

    def get_or_create_rag(self, client_id: str, phone_id: str, sender_number: str) -> Tuple[RAGBot, dict]:
        """Safely get RAG bot from cache or create new one."""
        try:
            current_time = time.time()
           
            # ✅ CORRECT: Use 'with self._lock:' NOT 'self._lock()'
            with self._lock:
                cached_item = self._cache.get(client_id)
                
                if cached_item and current_time < cached_item['expires_at']:
                    self._hits += 1
                    log.info(f"✓ Cache HIT - hits: {self._hits}, misses: {self._misses}")
                    return cached_item['rag'], cached_item['client_data']
                
                self._misses += 1
                log.info(f"✗ Cache MISS - hits: {self._hits}, misses: {self._misses}")
            
            # Fetch client data OUTSIDE the lock
            client_data = get_client(client_id)
    
            if not client_data or client_data == None:
                logger.log_error("client_data. get_or_create_rag. whatsapp.py", "Client_data not found.")
                return None, None
            
            try:
                str_client_data = {}

                for key, value in client_data.items():
                    unwrap_values = unwrap_secret(value)
                    str_client_data[key] = unwrap_values

                client_data.clear()

                client_data = str_client_data
            
            except Exception as e:
                logger.log_error("str_client_data. get_or_create_rag. RAGCacheManager. app.py", e)
            
            uploaded_doc = client_data.get("Uploaded Document")
         
            if not uploaded_doc or not isinstance(uploaded_doc, str):
                logger.log_error("uploaded_doc. get_or_create_rag. whatsapp.py", "Invalid or missing Uploaded Document")
                return None, None

            if len(uploaded_doc.strip()) < 10:
                logger.log_error("uploaded_doc. get_or_create_rag. whatsapp.py", "Document too short or empty after processing")
                return None, None
            
            uploaded_doc = uploaded_doc + str(we_are())
           
            # Initialize RAG bot
            rag = RAGBot(client_id=str(client_id), document_text=str(uploaded_doc), sender_number=str(sender_number))
            
            if not rag:
                logger.log_error("rag. get_or_create_rag. whatsapp.py", "Failed to create RAG.")
                return None, None

            # ✅ CORRECT: Store in cache using context manager
            with self._lock:
                self._cache[client_id] = {
                    'rag': rag,
                    'client_data': client_data,
                    'expires_at': current_time + self._ttl_seconds
                }

                if len(self._cache) > self._max_cache_size:
                    self._evict_oldest()
           
            return rag, client_data
        except Exception as e:
            logger.log_error("get_or_create_rag. whatsapp.py", e)
            return None, None

    def _evict_oldest(self):
        """Evict the oldest cache entry safely."""
        try:
            if not self._cache:
                return
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k]['expires_at'])
            del self._cache[oldest_key]
        except Exception as e:
            logger.log_error("_evict_oldest. whatsapp.py", e)

    def invalidate(self, client_id: str):
        """Invalidate cache safely."""
        try:
            # ✅ CORRECT: Use context manager
            with self._lock:
                if client_id in self._cache:
                    del self._cache[client_id]
        except Exception as e:
            logger.log_error("invalidate. whatsapp.py", e)

    def cleanup_expired(self):
        """Remove expired entries safely."""
        try:
            current_time = time.time()
            # ✅ CORRECT: Use context manager
            with self._lock:
                expired_keys = [k for k, v in self._cache.items() if current_time >= v['expires_at']]
                for k in expired_keys:
                    del self._cache[k]
        except Exception as e:
            logger.log_error("cleanup_expired. whatsapp.py", e)

    def get_stats(self) -> dict:
        """Get cache statistics safely."""
        try:
            # ✅ CORRECT: Use context manager for thread-safe read
            with self._lock:
                total_requests = self._hits + self._misses
                hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
                return {
                    'cache_size': len(self._cache),
                    'hits': self._hits,
                    'misses': self._misses,
                    'hit_rate': f"{hit_rate:.2f}%",
                    'total_requests': total_requests
                }
        except Exception as e:
            logger.log_error("get_stats. whatsapp.py", e)
            return {}

# Global cache manager instance
rag_cache = RAGCacheManager(ttl_minutes=30, max_cache_size=100)

#Security
if not rag_cache:
    logger.log_error("rag_cache variable. whatsapp.py", "rag_cache is not initialize properly.")

def authenticate_user(authorization: str = Header(None)):
    try:
        if not authorization:
            logger.log_security_event("MISSING_AUTH_HEADER", {})
            raise HTTPException(
                status_code=401,
                detail="Authorization header missing"
            )
        
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            logger.log_security_event("INVALID_AUTH_FORMATE", {})
            raise HTTPException(
                status_code=401,
                detail="Invalid authorization formate"
            )
        
        token = parts[1]

        payload = decode_jwt(token)
        if not payload:
            logger.log_security_event("INVALID_AUTH_FORMATE", {})
            raise HTTPException(
                status_code=401,
                detail="Invalid authorization formate"
            )
        
        client_id = payload.get("client_id")
        if not validate_client_id(client_id):
            logger.log_security_event(
                "INVALID_CLIENT_ID_IN_TOKEN",
                {"client_id_hash": hash_for_logging(client_id)}
            )
            raise HTTPException(
                status_code=401,
                detail="Invalid client identifier"
            )
        
        logger.log_client_operation(
            "user_authenticated",
            client_id,
            success=True
        )

        return client_id
    
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("authenticate_user. app.py", e)
        raise HTTPException(
            status_code=401,
            detail="Authentication failed"
        )

async def check_and_send_renuwal_reminders():
    """
    Renewal reminder system (safe, no duplicates per day).
    - Avoids index issues by using per-client queries
    - Skips members already reminded today
    - Sends WhatsApp messages concurrently
    """
    try:
        db = firestore.client()
        today = date.today()
        cutoff = today + timedelta(days=3)  # plans ending within next 3 days

        clients = db.collection("clients").stream()
        tasks = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for client_doc in clients:
                client_data = client_doc.to_dict()
                token = decrypt_data(client_data.get("Account Verify Token"))
                phone_id = decrypt_data(client_data.get("WA Phone ID"))
                try:
                    payment_link = decrypt_data(client_data.get("payment_link"))
                except Exception:
                    payment_link = None

                members_ref = (
                    db.collection("clients")
                    .document(client_doc.id)
                    .collection("members")
                )

                # Fetch only those with plan_end_date <= cutoff
                members = members_ref.where("plan_end_date", "<=", cutoff.isoformat()).stream()

                for doc in members:
                    data = doc.to_dict()
                    doc_ref = doc.reference

                    try:
                        plan_end = datetime.fromisoformat(str(data["plan_end_date"])).date()
                        days_left = (plan_end - today).days

                        # skip if already reminded today
                        last_reminder = data.get("last_reminder_date")
                        already_reminded_today = (last_reminder and datetime.fromisoformat(str(last_reminder)).date() == today)

                        if (days_left in (1, 2, 3) and not already_reminded_today):
                            name = decrypt_data(data["name"])
                            phone = decrypt_data(data["phone"])

                            message = (
                                f"Hey {name} 😊\n"
                                f"Your plan ends on {plan_end.strftime('%d %b %Y')} .\n"
                                f"Renew now to keep your progress going strong 🔥"
                            )

                            if payment_link:
                                message += f"\nPay now securely:\n{payment_link}"

                            # send WhatsApp message
                            tasks.append(
                                send_whatsapp_message(to_number=phone, text=message, WHATSAPP_TOKEN=token, WHATSAPP_PHONE_ID=phone_id,)
                            )

                            # update reminder status
                            doc_ref.update({
                                "last_reminder_date": today.isoformat(),
                                "reminder_sent": True
                            })

                    except Exception as inner:
                        logger.log_error(f"renewal_tasks.inner:", inner)

            if tasks:
                await asyncio.gather(*tasks)

        logger.info_(f"Processed {len(tasks)} renewal reminders.")

    except Exception as e:
        logger.log_error(f"renewal_tasks.main: ", e)

def authenticate_admin(admin_key: str = Header(None, alias="X-Admin-Key")):
    """Dependency to check for required admin key."""
    try:
        if not ADMIN_API_KEY or admin_key != ADMIN_API_KEY:
            raise HTTPException(
                status_code=401, 
                detail="Unauthorized: Invalid or missing X-Admin-Key"
            )
        return True # Return true on success
    except Exception as e:
        logger.log_error("authenticate_user. app.py", e)
    
def get_current_user(authorization: str = Header(None)):
    """Verify JWT token and return client_id."""
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
        
        token = authorization.replace("Bearer ", "")
        payload = decode_jwt(token)
        
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        return payload.get("client_id")
    except Exception as e:
        logger.log_error("get_current_user. app.py", e)

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main frontend HTML page."""
    try:
        with open("static/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Frontend not found. Please create static/index.html</h1>", 
            status_code=404
        )
    
@app.api_route("/send-reminder", methods=["GET", "POST"])
async def send_reminder():
    try:
        await check_and_send_renuwal_reminders()
        return {"status": "done", "message": "Renewal reminders sent successfully."}
    except Exception as e:
        logger.log_error("send_reminders. app.py", e)

@app.post("/api/login")
async def login_endpoint(request: LoginRequest):
    """Authenticate user and return JWT token."""
    try:
        client_data = get_client_by_email(request.email)

        if not client_data:
            logger.log_security_event(
                "LOGIN_FAILED_NO_USER",
                {"email_hash": hash_for_logging(request.email)}
            )
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Get the stored password - try multiple possible field names
        stored_password = (
            client_data.get("password") or 
            client_data.get("Password") or 
            client_data.get("hashed_password")
        )
    
        if not stored_password:
            logger.log_error("login_endpoint", f"No password field found. Available fields: {list(client_data.keys())}")
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Debug: Log password type
        logger.log_security_event(
            "LOGIN_DEBUG_PASSWORD_TYPE",
            {"password_type": type(stored_password).__name__, "is_dict": isinstance(stored_password, dict)}
        )
   
        # Ensure stored_password is a string
        if not isinstance(stored_password, str):
            logger.log_error("login_endpoint", f"Password is not a string after decryption: {type(stored_password)}")
            raise HTTPException(status_code=500, detail="Invalid password format")
        
        # Now verify the password
        try:
            # verify_password expects (hashed_password, plain_password)
            password_matches = verify_password(stored_password, request.password)
          
        except TypeError as type_error:
            logger.log_error("login_endpoint_verify_type", f"stored_password type: {type(stored_password)}, value length: {len(stored_password) if stored_password else 0}")
            
        except Exception as verify_error:
            logger.log_error("login_endpoint_verify", str(verify_error))
            raise HTTPException(status_code=500, detail="Password verification failed")
        
        if not password_matches:
            logger.log_security_event(
                "LOGIN_FAILED_WRONG_PASSWORD",
                {"email_hash": hash_for_logging(request.email)}
            )
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        # Decrypt other client data
        decrypted_data = decrypt_client_data(client_data)
    
        if not decrypted_data:
            logger.log_error("login_endpoint", "Failed to decrypt client data")
            raise HTTPException(status_code=500, detail="Failed to decrypt client data")
        
        client_id = (
            decrypted_data.get("Client_ID") or 
            decrypted_data.get("client_id") 
        )
        
        if not client_id:
            logger.log_error("login_endpoint", f"No client_id found. Available fields: {list(decrypted_data.keys())}")
            raise HTTPException(status_code=500, detail="Invalid client data")
        
        jwt_token = create_jwt(client_id, expire_minitue=480)
        
        if not jwt_token:
            raise HTTPException(status_code=500, detail="Failed to create authentication token")
        
        logger.log_client_operation("LOGIN_SUCCESS", client_id, success=True)
    
        return {
            "status": "success",
            "token": jwt_token,
            "client_data": decrypted_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("login_endpoint", (e))
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/register")
async def register_endpoint( business_name: str = Form(...), business_type: str = Form(...), owner_name: str = Form(...), phone: str = Form(...), email: EmailStr = Form(...),password: str = Form(...), verify_token: str = Form(""),wa_phone_id: str = Form(""),wa_verify_token: str = Form(""),uploaded_file: Optional[UploadFile] = File(None)):
    """Register a new business."""
    try:
        if not all([business_name, business_type, owner_name, phone, email, password]):
            raise HTTPException(status_code=400, detail="All required fields must be filled")
        
        doc_info = "None uploaded"
        if uploaded_file:
            doc_info = read_file_content(uploaded_file.file, uploaded_file.filename)
            if not doc_info:
                raise HTTPException(status_code=400, detail="Failed to process uploaded document")
        
        business_data = {
            "Business Name": business_name,
            "Owner Name": owner_name,
            "Business Type": business_type,
            "Phone": phone,
            "Email": email,
            "password": password,
            "Account Verify Token": verify_token,
            "WA Phone ID": wa_phone_id,
            "WA Verify Token": wa_verify_token,
            "Uploaded Document": doc_info,
            "Plan": "free",
            "Plan Start Date": datetime.now().isoformat(),
            "WA_Phone_ID_Hash": wa_phone_id
        }
        
        try:
            add_universal_client(business_data)
        except Exception as e:
            logger.log_error("add_universal_client. resister_endpoint. app.py", e)
        
        logger.log_client_operation("REGISTRATION_SUCCESS", email, success=True)
        
        return {
            "status": "success",
            "message": f"Registration for {business_name} completed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("register_endpoint", e)
        raise HTTPException(status_code=500, detail="Registration failed")

@app.post("/api/add-customer")
async def add_customer_endpoint(request: CustomerRequest,client_id: str = Depends(get_current_user)):
    """Add a new customer to the authenticated client's database."""
    try:
        if not validate_client_id(client_id):
            raise HTTPException(status_code=400, detail="Invalid client ID")
        
        if not validate_phone_number(request.phone):
            raise HTTPException(status_code=400, detail="Invalid phone number format")
        
        name = sanitize_string_input(request.name, max_length=100)
        if not name:
            raise HTTPException(status_code=400, detail="Invalid customer name")
        
        try:
            plan_end_datetime = datetime.fromisoformat(request.plan_end_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")
        
        add_customer_to_firebase(client_id, name, request.phone, plan_end_datetime)
        
        logger.log_client_operation("CUSTOMER_ADDED", client_id, success=True)
        
        return {
            "status": "success",
            "message": f"Customer {name} added successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("add_customer_endpoint", e)
        raise HTTPException(status_code=500, detail="Failed to add customer")

@app.post("/api/add-non-member")
async def add_non_member_endpoint(request: NonMemberRequest,client_id: str = Depends(get_current_user)):
    """Add a new non-member to the authenticated client's exclusion list."""
    try:
        if not validate_client_id(client_id):
            raise HTTPException(status_code=400, detail="Invalid client ID")
        
        if not validate_phone_number(request.phone):
            raise HTTPException(status_code=400, detail="Invalid phone number format")
        
        name = sanitize_string_input(request.name, max_length=100)
        if not name:
            raise HTTPException(status_code=400, detail="Invalid name")
        
        add_non_members_to_firebase(client_id, name, request.phone)
        
        logger.log_client_operation("NON_MEMBER_ADDED", client_id, success=True)
        
        return {
            "status": "success",
            "message": f"Non-member {name} added successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("add_non_member_endpoint", e)
        raise HTTPException(status_code=500, detail="Failed to add non-member")

@app.get("/api/verify-session")
async def verify_session_endpoint(client_id: str = Depends(get_current_user)):
    """Verify if the current session is valid."""
    try:
        client_data = get_client(client_id)
        
        if not client_data:
            raise HTTPException(status_code=401, detail="Session invalid")
        
        decrypted_data = decrypt_client_data(client_data)
        
        return {
            "status": "valid",
            "client_data": decrypted_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("verify_session_endpoint", e)
        raise HTTPException(status_code=401, detail="Session verification failed")
    
@app.post("/api/upload-document")
async def upload_document( document_file: UploadFile = File(...), document_name: Optional[str] = Form(None), client_id: str = Depends(authenticate_user), authenticated: bool = Depends(get_current_user)):
    """
    Handles document upload for a specific client and processes it via the RAG Bot.
    """
    try:
        if not authenticated:
            raise HTTPException(status_code=401, detail="Not authorized")
            
        if not document_name:
            raise HTTPException(
                status_code=400,
                detail="Invalid filename"
            )
        update_uploaded_document(client_id, document_file.file, document_file.filename)

        logger.log_client_operation("update_uploaded_document", client_id, success=True)
    except Exception as e:
        logger.log_error("upload_document. app.py", e)

def validate_client_id(candidate: str) -> bool:
    """
    Return True if candidate is a valid client_id. Strict allowlist.
    - must be a str
    - must match pattern
    - must be within length limits (8-64 here)
    """
    try:
        if not isinstance(candidate, str):
            return False
        candidate = candidate.strip()
        if not candidate:
            return False
        if not _CLIENT_ID_PATTERN.fullmatch(candidate):
            return False
        return True
    except Exception as e:
        logger.log_error("validate_client_id. app.py", e)

@app.post("/api/update-payment-link")
async def update_payment_link(
    request: Request,
    client_id: str = Depends(authenticate_user),
    authenticated: bool = Depends(get_current_user)
):
    """Update payment link for a client."""
    try:
        if not authenticated:
            raise HTTPException(status_code=401, detail="Not authorized")
        
        data = await request.json()
        payment_link = data.get("payment_link", "").strip()
        description = data.get("description", "").strip()
        
        if not payment_link:
            raise HTTPException(status_code=400, detail="Payment link is required")
        
        # Validate URL format
        from urllib.parse import urlparse
        try:
            result = urlparse(payment_link)
            if not all([result.scheme, result.netloc]):
                raise ValueError("Invalid URL")
        except:
            raise HTTPException(status_code=400, detail="Invalid URL format")
        
        # Sanitize inputs
        payment_link = sanitize_string_input(payment_link, max_length=500)
        description = sanitize_string_input(description, max_length=200)
        
        if not payment_link:
            raise HTTPException(status_code=400, detail="Invalid payment link")
        
        # Update in Firebase
        from firebase import update_payment_link
        success = update_payment_link(client_id, payment_link, description)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update payment link")
        
        logger.log_client_operation("payment_link_updated", client_id, success=True)
        
        return {
            "status": "success",
            "message": "Payment link updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("update_payment_link", e)
        raise HTTPException(status_code=500, detail="Failed to update payment link")
#---------------------
# CLIENT DATA CACHING (Firebase reads optimization)
#---------------------

@lru_cache(maxsize=200)
def _get_cached_client_id_ttl(phone_id: str, period: int):
    """Internal function for TTL cache (period is always the current hour/minute)."""
    try:
        return get_client_id_by_phone_id(phone_id)
    except Exception as e:
        logger.log_error("_get_cached_client_id_ttl. app.py", e)

def get_cached_client_id(phone_id: str) -> str:
    """Cache phone_id to client_id mapping with a 5-minute TTL."""
    # The 'period' changes every 5 minutes, forcing a re-fetch
    try:
        period = int(time.time() // 300) # 300 seconds = 5 minutes
        return _get_cached_client_id_ttl(phone_id, period)
    except Exception as e:
        logger.log_error("get_cached_client_id. app.py", e)

# ============================================================================
# API Functions
# ============================================================================
def validate_sender_number(sender: str) -> bool:
    """
    Validate the sender number (WhatsApp number).
    Only allow digits, maybe with a leading '+'.
    """
    try:
        import re
        if not isinstance(sender, str):
            return False
        if not re.fullmatch(r'\+?\d{7,15}', sender):  # typical phone number lengths
            return False
        return True
    except Exception as e:
        logger.log_error("validate_sender_number. app.py", e)

# Add this to app.py
@app.get("/health")
async def health_check():
    """Simple endpoint for container health checks."""
    return {"status": "ok", "message": "Service is running"}

def extract_message_info(data: dict) -> tuple[str, str, str] | None:
    """Extracts sender number and message text safely from the webhook payload."""
    try:
        value = data.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {})
        messages = value.get('messages', [])

        if not messages:
            logger.info_("extract_message_info: No user message found in payload (probably a status update).")
            return None

        message_data = messages[0]
    
        # ✅ NEW: Check message age
        message_timestamp = message_data.get('timestamp')
        
        if message_timestamp:
            try:
                msg_time = int(message_timestamp)
                current_time = int(time.time())
                age_seconds = current_time - msg_time
                
                # Ignore messages older than 5 minutes (300 seconds)
                if age_seconds > 150:
                    logger.info_(f"extract_message_info: Message too old ({age_seconds}s) - ignoring")
                    return None
                
                # Also ignore messages from the future (clock skew/replay attack)
                if age_seconds < -60:
                    logger.info_(f"extract_message_info: Message timestamp in future - ignoring")
                    return None
                    
            except (ValueError, TypeError):
                logger.log_error("extract_message_info", "Invalid timestamp format")
                
        sender_number = message_data.get('from')
        
        # ✅ CRITICAL FIX: Get the business phone number ID
        phone_number_id = value.get('metadata', {}).get('phone_number_id')
        display_phone_number = value.get('metadata', {}).get('display_phone_number')

        if not sender_number or not validate_sender_number(sender_number):
            logger.log_error("sender_number.extract_message_info.whatsapp.py", "Invalid or missing sender number.")
            return None

        # ✅ CRITICAL: Ignore messages FROM the business (bot's own messages)
        # WhatsApp sends webhooks for both incoming AND outgoing messages
        if sender_number == phone_number_id or sender_number == display_phone_number:
            logger.info_(f"extract_message_info: Ignoring bot's own message from {sender_number}")
            return None
        
        # ✅ Also check if this is marked as sent by the business
        if message_data.get('from_me') is True:
            logger.info_("extract_message_info: Ignoring message sent by business (from_me=True)")
            return None

        # ✅ CRITICAL: Only process text messages
        if message_data.get('type') != 'text':
            msg_type = message_data.get('type', 'unknown')
            logger.info_(f"extract_message_info: Ignoring non-text message type: {msg_type}")
            return None
        
        # ✅ Get text content
        text_body = message_data.get('text', {}).get('body', '').strip()
        
        if not text_body:
            logger.log_error("incoming_message.extract_message_info.whatsapp.py", "Empty text body.")
            return None
        
        if not phone_number_id:
            logger.log_error("phone_number_id.extract_message_info.whatsapp.py", "Missing phone_number_id.")
            return None
            
        return phone_number_id, sender_number, text_body

    except Exception as e:
        logger.log_error("extract_message_info.whatsapp.py", str(e))
        return None

async def send_whatsapp_message(to_number: str, text: str, WHATSAPP_TOKEN: str, WHATSAPP_PHONE_ID: str) -> bool:
    """
    Securely send WhatsApp message with enhanced debugging.
    """
    try:
        # Validate inputs
        if not validate_phone_number(to_number):
            logger.log_security_event(
                "INVALID_RECIPIENT_PHONE",
                {"phone_hash": hash_for_logging(to_number)}
            )
            return False
        
        if text:
            text = text.replace('\n\n\n', '\n\n')
        
        # Sanitize message text
        #text = sanitize_string_input(text, max_length=4096)

        #text = EmojiEnhancer().add_emojis(text)
        
        if not text:
            logger.log_error("send_whatsapp_message", "Empty message after sanitization")
            return False
        
        # ✅ ENHANCED: Validate token before sending
        if not WHATSAPP_TOKEN or not isinstance(WHATSAPP_TOKEN, str):
            logger.log_error("send_whatsapp_message", "Missing or invalid WhatsApp token")
            return False
        
        if len(WHATSAPP_TOKEN) < 20:
            logger.log_error("send_whatsapp_message", f"Token too short: {len(WHATSAPP_TOKEN)} chars")
            return False
        
        # ✅ DEBUG: Log request details (without full token)
        logger.log_security_event(
            "WHATSAPP_API_REQUEST",
            {
                "phone_id": WHATSAPP_PHONE_ID,
                "to_hash": hash_for_logging(to_number),
                "message_length": len(text),
                "token_length": len(WHATSAPP_TOKEN),
                "token_start": WHATSAPP_TOKEN[:10]
            }
        )
        
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": text}
        }
        
        url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
        
        async with httpx.AsyncClient(timeout=30.0, verify=True) as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload
            )
        
        # ✅ ENHANCED: Log response details for debugging
        logger.log_security_event(
            "WHATSAPP_API_RESPONSE",
            {
                "status_code": response.status_code,
                "response_preview": str(response.text)[:200]
            }
        )
        
        response.raise_for_status()
        
        logger.log_client_operation(
            "message_sent",
            hash_for_logging(to_number),
            success=True
        )
        
        return True
        
    except httpx.HTTPStatusError as e:
        # ✅ ENHANCED: Log detailed error information
        logger.log_security_event(
            "WHATSAPP_API_ERROR",
            {
                "status_code": e.response.status_code,
                "error_body": str(e.response.text)[:500],
                "url": str(e.request.url),
                "token_length": len(WHATSAPP_TOKEN) if WHATSAPP_TOKEN else 0
            }
        )
        logger.log_error("send_whatsapp_message", str(e))
        return False
        
    except Exception as e:
        logger.log_error("send_whatsapp_message", str(e))
        return False

@app.get("/debug/credentials/{client_id}")
async def debug_credentials(client_id: str, authenticated: bool = Depends(authenticate_admin)):
    """
    Debug endpoint to check credential configuration.
    Only accessible with admin key.
    """
    try:
        if not validate_client_id(client_id):
            raise HTTPException(status_code=400, detail="Invalid client_id")
        
        # Get client data
        client_data = get_client(client_id)
        
        if not client_data:
            return {"error": "Client not found"}
        
        # Check which credential fields exist
        credential_fields = {
            "available_fields": list(client_data.keys()),
            "token_fields": {},
            "phone_id_fields": {}
        }
        
        # Check for token fields
        token_names = [
            'WA Access Token', 'WHATSAPP_ACCESS_TOKEN', 'Account Verify Token',
            'WhatsApp Access Token', 'access_token', 'Access Token'
        ]
        
        for field in token_names:
            if field in client_data:
                value = client_data[field]
                credential_fields["token_fields"][field] = {
                    "exists": True,
                    "type": type(value).__name__,
                    "length": len(value) if isinstance(value, str) else 0,
                    "prefix": value[:10] if isinstance(value, str) and value else "EMPTY"
                }
        
        # Check for phone ID fields
        phone_names = ['WA Phone ID', 'WHATSAPP_PHONE_ID', 'WhatsApp Phone ID']
        
        for field in phone_names:
            if field in client_data:
                value = client_data[field]
                credential_fields["phone_id_fields"][field] = {
                    "exists": True,
                    "value": value
                }
        
        return credential_fields
        
    except Exception as e:
        logger.log_error("debug_credentials", e)
        return {"error": str(e)}
    
# ============================================================================
# Webhook Endpoints
# ============================================================================

@app.get("/webhook")
async def verify_webhook(request: Request):
    try:
        VERIFY_TOKEN = load_env_from_secret("WHATSAPP_VERIFY_TOKEN")
        """Handles the initial webhook verification handshake with Meta."""
        mode = request.query_params.get("hub.mode")
        token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            log.info("WebHook verified.")
            return PlainTextResponse(content=challenge)
        
        raise HTTPException(status_code=403, detail="Verification failed.")
    except Exception as e:
        logger.log_error("verify_webhook. app.py", e)

def validation(data: Dict):
    value = data.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {})
    messages = value.get('messages', [])

    if not messages:
        logger.info_("extract_message_info: No user message found in payload.")
        return None
    
    # ✅ NEW: Check contacts field (only present for incoming messages)
    contacts = value.get('contacts', [])
    if not contacts:
        logger.info_("extract_message_info: No contacts field - likely outgoing message")
        return None

    return True
    
@app.post("/webhook")
async def handle_message(data: Dict):
    """Enhanced message handler with comprehensive credential debugging."""
    try:
        if data.get('object') != 'whatsapp_business_account':
            return {"status": "ok", "message": "Not a WhatsApp event"}
        if data.get('object') == 'whatsapp_business_account':
            try:
                if not validation:
                    logger.log_error("Failed to validate", "-----------")
                    return
                
                entry = data.get('entry', [{}])[0]
                changes = entry.get('changes', [{}])[0]
                value = changes.get('value', {})
                
                # Check if this is a status update (not a message)
                if 'statuses' in value and 'messages' not in value:
                    logger.info_("handle_message: Status update ignored")
                    return {"status": "ok", "message": "Status update ignored"}
                
                # Check if there are no messages
                if 'messages' not in value or not value.get('messages'):
                    logger.info_("handle_message: No messages in payload")
                    return {"status": "ok", "message": "No messages to process"}
                
            except Exception as e:
                logger.log_error("entry, changes, values. jandle_messages. app.py", e)
                pass
            
            result = extract_message_info(data)

            if not result or result == None or result is None:
                logger.log_error("result. handle_message. whatsapp.py", "Failed to get the result.")
                return {"status": "error", "message": "Failed to extract message info"}
            
            phone_id, sender_number, incoming_message = result

            client_id = get_cached_client_id(phone_id)
        
            if client_id:
                client_data_check = get_client(client_id)
                if client_data_check:
                    bot_phone = client_data_check.get('WA Phone ID')
                    if bot_phone and formate_number(sender_number) == formate_number(bot_phone):
                        logger.info_(f"handle_message: Ignoring message from bot itself")
                        return {"status": "ok", "message": "Bot's own message ignored"}

            try:
                message_id = data.get('entry', [{}])[0].get('changes', [{}])[0].get('value', {}).get('messages', [{}])[0].get('id')
            
                if message_id and message_id in processed_messages:
                    logger.info_(f"Duplicate message ignored: {message_id}")
                    return {"status": "ok", "message": "Duplicate message ignored"}
                
                if message_id:
                    processed_messages.append(message_id)
            except Exception as e:
                logger.log_error("message_id. handle_message. app.py", e)
                pass
    
            if not incoming_message or len(incoming_message.strip()) == 0:
                logger.log_error("incoming_message.handle_message", "Empty message after extraction")
                return {"status": "ok", "message": "Empty message ignored"}
            
            if not validate_phone_number(phone_id):
                logger.log_error("Phone_id. handle_message. whatsapp.py", "Phone_id failed validation.")
                return {"status": "error", "message": "Invalid phone ID"}
            
            # Use cached client_id lookup
            client_id = get_cached_client_id(phone_id)

            reply_text = None

            if not validate_client_id(candidate=client_id):
                logger.log_error("client_id. handle_message. whatsapp.py", "Client_id failed validation.")
                return {"status": "error", "message": "Invalid client ID"}

            if not client_id:
                logger.log_error("client_id. handle_message. whatsapp.py", "Failed to get client id.")
                return {"status": "error", "message": "Client not found"}

            non_members = get_all_non_members_from_firebase(client_id=client_id)

            if formate_number(sender_number) in non_members:
                logger.log_error("IGNORED", "Number is excluded so no message if gone.")
                return JSONResponse({
                    "status": "ignored",
                    "message": "Number is excluded"
                })
            
            if sender_number.endswith("@g.us"):
                logger.log_error("Ignoring", f"💬 Ignored message from group: {hash_for_logging(sender_number)}")
                return JSONResponse({
                    "status": "ignored",
                    "message": "Group messages are ignored"
                })
            
            # Get or create cached RAG bot - Get client_data BEFORE rate limiting
            result = rag_cache.get_or_create_rag(client_id, phone_id, sender_number=sender_number)
            
            if not result or result == (None, None):
                logger.log_error("rag_result. handle_message. whatsapp.py", "get_or_create_rag returned None")
                # ✅ Use fallback here and return immediately
                try:
                    client_data = get_client(client_id)
                    whatsapp_token = client_data.get('Account Verify Token')
                    whatsapp_phone_id = client_data.get('WA Phone ID') or phone_id
                    
                    if whatsapp_token and isinstance(whatsapp_token, str) and len(whatsapp_token) >= 20:
                        response = fallback(incoming_message)
                        await send_whatsapp_message(sender_number, response, whatsapp_token, whatsapp_phone_id)
                        return {"status": "success", "message": "Fallback response sent"}
                except Exception as fallback_error:
                    logger.log_error("fallback_in_rag_init", fallback_error)
                
                return {"status": "error", "message": "Failed to initialize RAG"}
            
            rag, client_data = result

            if not rag or not client_data:
                logger.log_error("rag. handle_message. whatsapp.py", "RAG or client_data is None.")
                return {"status": "error", "message": "Failed to initialize RAG"}

            # ✅ DEBUG: Log all available keys in client_data
            available_keys = list(client_data.keys())
    
            # ✅ ENHANCED: Get credentials with comprehensive fallback and debugging
            whatsapp_token = client_data.get('Account Verify Token')
            whatsapp_phone_id = client_data.get('WA Phone ID')
            
            # Fallback: use phone_id from webhook if not found in client_data
            if not whatsapp_phone_id:
                whatsapp_phone_id = phone_id
                logger.log_security_event(
                    "USING_WEBHOOK_PHONE_ID",
                    {"phone_id": phone_id}
                )
            
            # ✅ CRITICAL: Validate token
            if not whatsapp_token:
                logger.log_security_event(
                    "MISSING_WHATSAPP_TOKEN",
                    {
                        "client_id_hash": hash_for_logging(client_id),
                        "available_keys": available_keys
                    }
                )
                return {
                    "status": "error", 
                    "message": "WhatsApp access token not configured. Please add 'WA Access Token' field in registration."
                }
            
            if not isinstance(whatsapp_token, str):
                logger.log_security_event(
                    "INVALID_TOKEN_TYPE",
                    {
                        "token_type": type(whatsapp_token).__name__
                    }
                )
                return {"status": "error", "message": "Invalid token format"}
            
            # ✅ SECURITY: Validate token format
            token_length = len(whatsapp_token)
            
            if token_length < 20:
                logger.log_security_event(
                    "TOKEN_TOO_SHORT",
                    {
                        "token_length": token_length,
                        "minimum": 20
                    }
                )
                return {"status": "error", "message": "WhatsApp token too short - invalid configuration"}
            
            # ✅ DEBUG: Log token characteristics (without exposing full token)
            logger.log_security_event(
                "TOKEN_VALIDATION",
                {
                    "token_length": token_length,
                    "starts_with": whatsapp_token[:5],
                    "contains_pipe": "|" in whatsapp_token,
                    "is_alphanumeric": whatsapp_token.replace("|", "").replace("_", "").isalnum()
                }
            )
            
            if not whatsapp_phone_id:
                logger.log_error("credentials. handle_message. whatsapp.py", "Missing WhatsApp phone ID")
                return {"status": "error", "message": "Missing WhatsApp phone ID"}

            # Log successful credential retrieval
            logger.log_client_operation(
                "credentials_retrieved",
                client_id,
                success=True
            )

            # NOW check rate limit (with credentials available)
            allowed, reason, retry_after = rate_limiter.check_rate_limit(
                sender_number,
                client_id,
                incoming_message
            )
            
            if not allowed:
                rate_limit_msg = f"⚠️ {reason}"
                if retry_after:
                    rate_limit_msg += f" Please try again in {retry_after} seconds."
                
                # Send rate limit message
                await send_whatsapp_message(
                    sender_number, 
                    rate_limit_msg, 
                    whatsapp_token, 
                    whatsapp_phone_id
                )
                
                logger.log_error("rate_limit_exceed", f"🚫 Rate limit exceeded: {hash_for_logging(sender_number)}")
                
                return JSONResponse({
                    "status": "rate_limited",
                    "retry_after": retry_after
                })
            
            business_type = client_data.get("Business Type").lower()

            doc = client_data.get("Uploaded Document")

            business_plan = client_data.get("Plan", "free").lower()

            if business_plan.lower() == "free":
                result = await handle_user_message_free_version(message=incoming_message, rag=rag)
                if not result:
                    logger.log_error("result. business_plan. free. handle_message. app.py", "Failed to generate result")
                    result = fallback(incoming_message)
                reply_text = result
            
            elif business_plan.lower() in ["premium", "paid", "pro", "ultimate"]:
                if business_type.lower() == "gym":
                    # Process message
                    reply_text = await handle_user_message(
                        client_id, 
                        sender_number=sender_number, 
                        message=incoming_message, 
                        rag=rag
                    )

                elif business_type.lower() == "restaurant":
                    reply_text = await handle_user_message_restaurents(
                    client_id, 
                    sender_number=sender_number, 
                    message=incoming_message, 
                    rag=rag
                    )
                
                elif business_type.lower() == "bakery":
                    reply_text = await handle_user_message_bakery(
                        client_id, 
                        sender_number=sender_number, 
                        message=incoming_message, 
                        rag=rag,
                        document=doc
                    )
                
                elif business_type.lower() == "GENERAL".lower():
                    reply_text = await handle_user_message(
                        client_id, 
                        sender_number=sender_number, 
                        message=incoming_message, 
                        rag=rag
                    )
                
                elif business_type.lower() == "cloth_store":
                    reply_text = await handle_user_message_cloth_store(
                        client_id=client_id,
                        sender_number=sender_number,
                        message=incoming_message,
                        rag=rag
                    )

                else:
                    reply_text= "Sorry but your business haven't resistered yet. Please contect Crevoxega@gmail.com"
            
            else:
                reply_text = "Your business plan is not valid. Please contact support at Crevoxega@gmail.com"

            if not reply_text:
                logger.log_error("reply_text. handle_message. whatsapp.py", "Failed to generate reply.")
                reply_text = fallback(incoming_message)

            # Send reply
            success = await send_whatsapp_message(
                to_number=sender_number,
                text=reply_text,
                WHATSAPP_TOKEN=whatsapp_token,
                WHATSAPP_PHONE_ID=whatsapp_phone_id
            )

            if not success:
                logger.log_error("send_message. handle_message. whatsapp.py", "Failed to send message")
                return {"status": "error", "message": "Failed to send message"}

            return {
                "status": "success",
                "message": "Message processed.",
                "reply": reply_text
            }

        return {"status": "ok"}
        
    except Exception as e:
        # ✅ FIXED: Only use fallback if we haven't already sent a response
        logger.log_error("exception. handle_message. app.py", e)
        return {"status": "fail", "error": str(e)}

# Replace your existing get_orders endpoint with this:

# Add this to your app.py - REPLACE your existing /api/orders and /api/confirm-order endpoints

@app.get("/api/orders")
async def get_orders(client_id: str = Depends(get_current_user)):
    """Get all pending orders - UNIFIED for all business types"""
    try:
        from encryption_utils import decrypt_data
        
        client_data = get_client(client_id)
        
        if not client_data:
            raise HTTPException(status_code=403, detail="Access denied")
        
        business_type = client_data.get("Business Type", "").lower()
        
        all_orders = []
        
        customer_list_ref = db.collection("clients").document(client_id).collection("customer_list")
        
        for customer_doc in customer_list_ref.stream():
            customer_data = customer_doc.to_dict()
            customer_hash = customer_doc.id
            
            # Decrypt customer info
            customer_name = decrypt_data(customer_data.get("name", "Unknown"))
            customer_address = decrypt_data(customer_data.get("address", ""))
            
            encrypted_number = customer_data.get("sender_number", None)
            sender_number = decrypt_data(encrypted_number) if encrypted_number else "Unknown"
            
            # Get orders - query for "confirmed" status (pending confirmation from business)
            orders_ref = customer_list_ref \
                .document(customer_hash) \
                .collection("orders")
            
            # ✅ CRITICAL: Query for orders with status="confirmed" (awaiting business confirmation)
            for order_doc in orders_ref.where("status", "==", "confirmed").stream():
                order_data = order_doc.to_dict()
                order_id = order_doc.id
                
                # ✅ NEW: Unified order structure
                order_obj = {
                    "order_id": order_id,
                    "customer_hash": customer_hash,
                    "customer_phone": sender_number,
                    "customer_name": customer_name,
                    "customer_address": customer_address,
                    "timestamp": str(order_data.get("timestamp", "")),
                    "status": order_data.get("status", ""),
                    "Type": order_data.get("Type", "Not specified"),
                    "total": order_data.get("total", 0),
                    "items": []
                }
                
                # ✅ Parse items array (handles both custom cakes and regular items)
                raw_items = order_data.get("items", [])
                
                for item in raw_items:
                    item_type = item.get("type", "regular")
                    
                    if item_type == "custom_cake":
                        order_obj["items"].append({
                            "type": "custom_cake",
                            "weight": item.get("weight", "N/A"),
                            "flavour": item.get("flavour", "N/A"),
                            "cake_message": item.get("message", "N/A"),
                            "delivery_datetime": item.get("delivery_datetime", "ASAP"),
                            "price": item.get("price", 0),
                            "quantity": 1
                        })
                    else:
                        order_obj["items"].append({
                            "type": "regular",
                            "food_name": item.get("food_name", "Unknown"),
                            "quantity": item.get("quantity", 1),
                            "price": item.get("price", 0)
                        })
                
                all_orders.append(order_obj)
        
        logger.log_client_operation("get_orders", client_id, success=True)
        return {"orders": all_orders, "business_type": business_type}
        
    except Exception as e:
        logger.log_error("get_orders", e)
        raise HTTPException(status_code=500, detail="Failed to fetch orders")

@app.get("/api/confirmed-orders")
async def get_confirmed_orders(client_id: str = Depends(get_current_user)):
    """Get all confirmed orders - UNIFIED"""
    try:
        from encryption_utils import decrypt_data
        
        client_data = get_client(client_id)
        if not client_data:
            raise HTTPException(status_code=403, detail="Access denied")
        
        business_type = client_data.get("Business Type", "").lower()
        
        customer_list_ref = db.collection("clients") \
            .document(client_id) \
            .collection("customer_list")
        
        confirmed_orders = []
        
        for customer_doc in customer_list_ref.stream():
            customer_data = customer_doc.to_dict()
            customer_hash = customer_doc.id
            customer_name = decrypt_data(customer_data.get("name", "Unknown"))
            customer_address = decrypt_data(customer_data.get("address", ""))
            
            encrypted_number = customer_data.get("sender_number", None)
            sender_number = decrypt_data(encrypted_number) if encrypted_number else "Unknown"
            
            orders_ref = customer_list_ref \
                .document(customer_hash) \
                .collection("orders")
            
            # Query for confirmed_to_deliver orders
            for order_doc in orders_ref.where("status", "==", "confirmed_to_deliver").stream():
                order_data = order_doc.to_dict()
                order_id = order_doc.id
                
                order_obj = {
                    "order_id": order_id,
                    "customer_hash": customer_hash,
                    "customer_phone": sender_number,
                    "customer_name": customer_name,
                    "customer_address": customer_address,
                    "timestamp": str(order_data.get("timestamp", "")),
                    "status": order_data.get("status", ""),
                    "Type": order_data.get("Type", "Not specified"),
                    "total": order_data.get("total", 0),
                    "items": []
                }
                
                # Parse items
                raw_items = order_data.get("items", [])
                
                for item in raw_items:
                    item_type = item.get("type", "regular")
                    
                    if item_type == "custom_cake":
                        order_obj["items"].append({
                            "type": "custom_cake",
                            "weight": item.get("weight", "N/A"),
                            "flavour": item.get("flavour", "N/A"),
                            "cake_message": item.get("message", ""),
                            "delivery_datetime": item.get("delivery_datetime", "ASAP"),
                            "price": item.get("price", 0),
                            "quantity": 1
                        })
                    else:
                        order_obj["items"].append({
                            "type": "regular",
                            "food_name": item.get("food_name", "Unknown"),
                            "quantity": item.get("quantity", 1),
                            "price": item.get("price", 0)
                        })
                
                confirmed_orders.append(order_obj)
        
        return {"orders": confirmed_orders, "business_type": business_type}
        
    except Exception as e:
        logger.log_error("get_confirmed_orders", e)
        raise HTTPException(status_code=500, detail="Failed to fetch confirmed orders")


@app.post("/api/confirm-order/{order_id}")
async def confirm_order( order_id: str, customer_phone_hash: str = None, request: Request = None, client_id: str = Depends(get_current_user) ):
    """Confirm order - UNIFIED for all types"""
    try:
        from encryption_utils import decrypt_data
        
        # Get customer hash from query or body
        if not customer_phone_hash:
            try:
                body = await request.json()
                customer_phone_hash = body.get("customer_hash") or body.get("customer_phone_hash")
            except:
                pass
        
        if not order_id or order_id == "undefined":
            raise HTTPException(status_code=400, detail="Invalid order ID")
        
        if not customer_phone_hash or customer_phone_hash == "undefined":
            raise HTTPException(status_code=400, detail="Invalid customer hash")
        
        # Get client data
        client_data = get_client(client_id)
        if not client_data:
            raise HTTPException(status_code=403, detail="Client not found")
        
        # Get WhatsApp credentials
        token = client_data.get("Account Verify Token")
        phone_id = client_data.get("WA Phone ID")
        
        if not token or not phone_id:
            logger.log_error("confirm_order", "Missing WhatsApp credentials")
            raise HTTPException(status_code=400, detail="WhatsApp not configured")
        
        # Get customer data
        customer_ref = db.collection("clients") \
            .document(client_id) \
            .collection("customer_list") \
            .document(customer_phone_hash)
        
        customer_doc = customer_ref.get()
        
        if not customer_doc.exists:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        customer_data = customer_doc.to_dict()
        customer_name = decrypt_data(customer_data.get("name", "Customer"))
        
        # Get phone number
        customer_phone = None
        sender_num = customer_data.get("sender_number")
        if sender_num and isinstance(sender_num, str):
            customer_phone = decrypt_data(sender_num)
        elif customer_data.get("phone"):
            phone = customer_data.get("phone")
            if phone and isinstance(phone, str):
                customer_phone = decrypt_data(phone)
        
        if not customer_phone:
            raise HTTPException(status_code=400, detail="Customer phone not found")
        
        # Get order
        order_ref = customer_ref.collection("orders").document(order_id)
        order_doc = order_ref.get()
        
        if not order_doc.exists:
            raise HTTPException(status_code=404, detail="Order not found")
        
        order_data = order_doc.to_dict()
        
        # Get order Type
        order_type_value = order_data.get("Type", "Not specified")
        total = order_data.get("total", 0)
        items = order_data.get("items", [])
        
        # Update order status
        order_ref.update({"status": "confirmed_to_deliver"})
        
        # Build WhatsApp message
        message = f"Great news, {customer_name}! 🎉\n\n"
        message += "Your order has been confirmed!\n\n"
        message += "📋 Order Details:\n"
        
        for item in items:
            if item.get("type") == "custom_cake":
                weight = item.get("weight", "N/A")
                flavour = item.get("flavour", "N/A")
                cake_msg = item.get("cake_message", "")
                delivery = item.get("delivery_datetime", "ASAP")
                
                message += f"• Custom Cake ({weight}, {flavour})\n"
                if cake_msg:
                    message += f"  Message: '{cake_msg}'\n"
                message += f"  Delivery: {delivery}\n"
            else:
                food = item.get("food_name", "Unknown")
                quantity = item.get("quantity", 1)
                message += f"• {food} x{quantity}\n"
        
        message += f"\n*Total: ₹{total}*\n"
        message += f"Order Type: {order_type_value}\n\n"
        
        # Get language preference
        language = decrypt_data(customer_data.get("launguage", "English"))
        if not language:
            language = "English"
        
        # Add payment link if available
        payment_link = decrypt_data(client_data.get("payment_link", ""))
        
        if payment_link:
            message += "\n\nPay now:"
            message = await RAGBot(client_id=client_id).invoke_translation(message, language)
            message += f"\n{payment_link}"
        else:
            message += "\n\nPayment: Cash on Delivery"
            message = await RAGBot(client_id=client_id).invoke_translation(message, language)
        
        # Send WhatsApp message
        await send_whatsapp_message(
            to_number=customer_phone,
            text=message,
            WHATSAPP_TOKEN=token,
            WHATSAPP_PHONE_ID=phone_id
        )
        
        logger.log_client_operation("order_confirmed", client_id, success=True)
        
        return {
            "status": "success",
            "message": f"Order {order_id} confirmed",
            "customer_name": customer_name,
            "customer_phone": customer_phone
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.log_error("confirm_order", e)
        raise HTTPException(status_code=500, detail=f"Failed to confirm order: {str(e)}")
# ADD THIS NEW ENDPOINT for notifications:

@app.get("/api/new-orders")
async def check_new_orders(client_id: str = Depends(get_current_user)):
    """Check if there are any new unconfirmed orders."""
    try:
        from encryption_utils import decrypt_data
        
        customer_list_ref = db.collection("clients") \
            .document(client_id) \
            .collection("customer_list")
        
        # Check for any orders with status "confirmed" (pending restaurant confirmation)
        for customer_doc in customer_list_ref.stream():
            orders_ref = customer_doc.reference.collection("orders")
            
            for order_doc in orders_ref.where("status", "==", "confirmed").limit(1).stream():
                return {
                    "has_new_order": True,
                    "order_id": order_doc.id
                }
        
        return {"has_new_order": False}
        
    except Exception as e:
        logger.log_error("check_new_orders", e)
        return {"has_new_order": False}

@app.get("/api/dashboard-stats")
async def get_dashboard_stats(client_id: str = Depends(get_current_user)):
    """Get dashboard statistics for the client"""
    try:    
        # Get total customers
        customer_list_ref = db.collection("clients") \
            .document(client_id) \
            .collection("customer_list")
        
        total_customers = len(list(customer_list_ref.stream()))
        
        # Get orders
        pending_orders_count = 0
        total_orders_count = 0
        
        for customer_doc in customer_list_ref.stream():
            customer_hash = customer_doc.id
            orders_ref = customer_list_ref.document(customer_hash).collection("orders")
            
            # Count pending orders
            pending = list(orders_ref.where("status", "==", "confirmed").stream())
            pending_orders_count += len(pending)
            
            # Count all orders
            all_orders = list(orders_ref.stream())
            total_orders_count += len(all_orders)
        
        return {
            "total_customers": total_customers,
            "total_orders": total_orders_count,
            "pending_orders": pending_orders_count
        }
        
    except Exception as e:
        logger.log_error("dashboard_stats", e)
        return {
            "total_customers": 0,
            "total_orders": 0,
            "pending_orders": 0
        }


# Example usage
if __name__ == "__main__":
    result = asyncio.run(get_confirmed_orders(
        client_id="plAvSRm0Z4huJIJKZdO7"
    ))
    print(result)

# ============================================================================
# Admin Endpoints (Optional - for cache management)
# ============================================================================

@app.get("/cache/stats")
async def get_cache_stats(authenticated: bool = Depends(authenticate_admin)):
    """Get cache statistics."""
    return rag_cache.get_stats()

@app.post("/cache/clear/{client_id}")
async def clear_client_cache(client_id: str, authenticated: bool = Depends(authenticate_admin)):
    """Clear cache for specific client."""
    rag_cache.invalidate(client_id)
    return {"status": "success", "message": f"Cache cleared for {client_id}"}

@app.post("/cache/cleanup")
async def cleanup_cache(authenticated: bool = Depends(authenticate_admin)):
    """Manually trigger cache cleanup."""
    rag_cache.cleanup_expired()
    return {"status": "success", "message": "Expired caches cleaned up"}

@app.get("/rate-limit/stats/{phone_number}")
async def get_user_rate_limit_stats(phone_number: str, client_id: str, authenticated: bool = Depends(authenticate_admin)):
    """Get rate limit stats for a specific user."""
    stats = rate_limiter.get_user_stats(phone_number, client_id)
    return stats

@app.post("/rate-limit/reset/{phone_number}")
async def reset_user_rate_limit(phone_number: str, client_id: str, authenticated: bool = Depends(authenticate_admin)):
    """Reset rate limits for a user (admin only)."""
    rate_limiter.reset_user_limits(phone_number, client_id)
    return {"status": "reset_successful"}

@app.post("/rate-limit/unblock/{phone_number}")
async def unblock_user(phone_number: str, client_id: str, authenticated: bool = Depends(authenticate_admin)):
    """Manually unblock a user (admin only)."""
    success = rate_limiter.unblock_user(phone_number, client_id)
    return {"status": "unblocked" if success else "not_blocked"}

@app.get("/rate-limit/global-stats")
async def get_global_rate_limit_stats(authenticated: bool = Depends(authenticate_admin)):
    """Get global rate limiting statistics."""
    return rate_limiter.get_global_stats()

# Helper dependency for phone number validation in admin routes
def validate_admin_phone(phone_number: str):
    if not validate_phone_number(phone_number):
        raise HTTPException(status_code=400, detail="Invalid phone number format")
    return phone_number

# Helper dependency for client ID validation in admin routes
def validate_admin_client_id(client_id: str):
    if not validate_client_id(client_id):
        raise HTTPException(status_code=400, detail="Invalid client_id format")
    return client_id

if __name__ == "__main__":
    import asyncio
    result = asyncio.run(get_orders("plAvSRm0Z4huJIJKZdO7"))
    print(result)