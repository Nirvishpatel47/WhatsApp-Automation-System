import json
import os
from functools import lru_cache
from google.cloud import secretmanager
from dotenv import dotenv_values, load_dotenv
import io
import logging

try:
    client = secretmanager.SecretManagerServiceClient(transport="rest")
except Exception as e:
    logging.error(f"client. get_secrete.py: {e}")

def unwrap_secret(value):
    """
    Unwrap SecretStr to plain string.
    ✅ Handles Pydantic v1, v2, and plain strings
    """
    try:
        if value is None:
            return None
        
        # Already a plain string
        if isinstance(value, str):
            return value
        
        # Handle Pydantic v1 SecretStr
        if hasattr(value, "get_secret_value"):
            unwrapped = value.get_secret_value()
            # ✅ Recursive unwrap in case get_secret_value returns another SecretStr
            return str(unwrap_secret(unwrapped))
        
        # Handle Pydantic v2 SecretStr
        if hasattr(value, "_secret_value"):
            return str(value._secret_value)
        
        # ✅ Force conversion to string for any other type
        result = str(value)
        
        # ✅ Final validation
        if not isinstance(result, str):
            logging.error(f"unwrap_secret failed to convert to string: {type(result)}")
            raise TypeError(f"Cannot convert {type(value)} to string")
        
        return result
        
    except Exception as e:
        logging.error(f"unwrap_secret error: {e}")
        # Return string representation as fallback
        return str(value)

@lru_cache(maxsize=32)
def load_env_from_secret(value: str, secret_id: str = "Crevoxega"):
    """
    Load environment variable with fallback priority.
    ✅ CRITICAL: Always returns plain string, never SecretStr
    """
    try:
        # First priority: Check environment variables
        load_dotenv()
        env_value = os.getenv(value)
        
        if env_value is not None:
            # ✅ Unwrap and force string conversion
            unwrapped = unwrap_secret(env_value)
            return str(unwrapped)  # Ensure it's a string
        
        # Second priority: Try GCP Secret Manager
        try:
            name = f"projects/501658036383/secrets/{secret_id}/versions/latest"
            response = client.access_secret_version(name=name)
            secret_value = response.payload.data.decode("utf-8")
            stream_data = io.StringIO(secret_value)
            env_var = dotenv_values(stream=stream_data)
            
            raw_value = env_var.get(value)
            if raw_value is None:
                raise ValueError(f"Key '{value}' not found in secret")
            
            logging.info(f"Getting value from secret manager for: {value}")
            
            # ✅ CRITICAL: Triple unwrap to ensure plain string
            unwrapped = unwrap_secret(raw_value)
            
            # ✅ Force string conversion
            result = str(unwrapped)
            
            # ✅ Validate it's actually a string
            if not isinstance(result, str):
                logging.error(f"Failed to convert {value} to string, got {type(result)}")
                raise TypeError(f"Value must be string, got {type(result)}")
            
            return result
        
        except Exception as e:
            raise ValueError(f"Could not load {value} from environment or Secret Manager: {e}")
    
    except Exception as e:
        logging.error(f"load_env_from_secret error: {e}")
        raise
 

def get_secret_json(value: str) -> dict:
    """
    Load and parse JSON from secret
    
    Args:
        value: The key name to retrieve
    
    Returns:
        Parsed JSON as dictionary
    """
    try:
        value_str = load_env_from_secret(value)
        return json.loads(value_str)
    except Exception as e:
        logging.error(f"get_secrete_json. get_secrete.py: {e}")
        return None