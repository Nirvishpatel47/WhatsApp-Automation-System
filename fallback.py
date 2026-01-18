from langchain_google_genai.chat_models import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate
from get_secreats import load_env_from_secret
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from encryption_utils import get_logger
from basic_fallback import chatbot_response
import os

os.environ["GOOGLE_API_USE_REST_TRANSPORT"] = "true"
os.environ["GOOGLE_CLOUD_DISABLE_GRPC"] = "1"

logger = get_logger()
try:

    GEMINI_API_KEY = load_env_from_secret("GEMINI_API_KEY")

    if hasattr(GEMINI_API_KEY, "get_secret_value"):
        GEMINI_API_KEY = GEMINI_API_KEY.get_secret_value()

    parser = StrOutputParser()
except Exception as e:
    logger.log_error("GEMINIAPIKEY. fallback.py", e)

def fallback(question: str) -> str:
    try:
        return chatbot_response(question)
    except Exception as e:
        logger.log_error("fallback. fallback.py", "Using basic fallback.")
        logger.log_error("fallback. fallback.py", e)
        return chatbot_response(question)





