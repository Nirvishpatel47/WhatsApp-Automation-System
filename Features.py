import re
from deep_translator import GoogleTranslator
from functools import lru_cache
from encryption_utils import get_logger, sanitize_input

logger = get_logger()

# Cache for translations to avoid repeated API calls
@lru_cache(maxsize=500)
def cached_translate(text: str, source_lang: str, target_lang: str) -> str:
    """Cache translations to improve speed."""
    try:
        return GoogleTranslator(source=source_lang, target=target_lang).translate(text)
    except Exception as e:
        return text  # Return original on failure


class EfficientTranslator:
    """
    High-performance multi-language translator with caching and smart detection.
    Supports Hindi, Gujarati, Hinglish, and English.
    NO external dependencies except deep_translator!
    """
    
    # Language code mappings
    LANG_CODES = {
        'hindi': 'hi',
        'gujarati': 'gu',
        'english': 'en',
        'hinglish': 'en'  # Treat Hinglish as Hindi for translation
    }
    
    # Script patterns for accurate detection (pre-compiled for speed)
    HINDI_PATTERN = re.compile(r'[\u0900-\u097F]+')
    GUJARATI_PATTERN = re.compile(r'[\u0A80-\u0AFF]+')
    LATIN_PATTERN = re.compile(r'[A-Za-z]+')
    DIGIT_PATTERN = re.compile(r'\d+')
    
    # Common Hinglish words (expanded list for better detection)
    HINGLISH_INDICATORS = {
        # Common Hindi words in Roman script
        'hai', 'h', 'ho', 'hoon', 'hain', 'hu', 'hun',
        'kya', 'kyun', 'kyu', 'kaise', 'kaisa', 'kese', 'kesa',
        'gaya', 'gayi', 'gaye', 'gayi',
        'kar', 'karo', 'kara', 'kari', 'kare', 'karna', 'karke',
        'raha', 'rahi', 'rahe', 'rahe',
        'tha', 'thi', 'the', 'thee',
        'tum', 'tumhara', 'tumhari', 'tumhe', 'tumko',
        'main', 'mein', 'mai', 'mera', 'meri', 'mere', 'mujhe', 'mujhko',
        'hum', 'humara', 'humari', 'humare', 'humko', 'humhe',
        'tera', 'teri', 'tere', 'tujhe', 'tujhko',
        'uska', 'uski', 'uske', 'usne', 'usको',
        'accha', 'acha', 'achha', 'achchha',
        'thik', 'theek', 'thīk', 'ṭhīk',
        'nahi', 'nahin', 'nai', 'na',
        'haan', 'han', 'haa', 'ha',
        'bol', 'bola', 'boli', 'bole', 'bolte', 'bolna',
        'dekh', 'dekha', 'dekhi', 'dekhe', 'dekho', 'dekhna',
        'suna', 'suno', 'suni', 'sune', 'sunna', 'sunna',
        'kaha', 'kaho', 'kahi', 'kahe', 'kahna',
        'aur', 'or',
        'ya', 'yaa',
        'ki', 'ka', 'ke', 'ko', 'se', 'ne', 'pe', 'par', 'me', 'mein',
        'wala', 'wali', 'wale', 'waala', 'waali', 'waale',
        'abhi', 'ab', 'abi',
        'phir', 'fir', 'fer',
        'jab', 'tab',
        'kuch', 'kuchh', 'kucch', 'koi',
        'aise', 'ese', 'vaise', 'vese',
        'bahut', 'bohot', 'bahot', 'bohat',
        'bhi', 'bi',
        'to', 'toh',
        'jo', 'joh',
        'vo', 'woh', 'wo',
        'yeh', 'ye', 'yah', 'ya',
        'kab', 'kahan', 'kaha', 'kidhar',
        'kyunki', 'kyunke', 'kyuki', 'kyuke',
        'lekin', 'par', 'magar',
        'aap', 'ap', 'apka', 'apki', 'apke',
        'sabhi', 'sab', 'saare', 'saara', 'saari',
        'thoda', 'thodi', 'thode',
        'zyada', 'jyada', 'jyaada', 'zyaada',
        'bilkul', 'bilkool', 'ekdum',
        'pata', 'pta', 'malum', 'maloom',
        'chalo', 'chal', 'chale', 'chalte',
        'aao', 'aana', 'aaiye', 'aiye',
        'jao', 'jaana', 'jaaiye', 'jaiye',
        'karo', 'karna', 'kariye', 'kijiye',
        'milna', 'mila', 'mile', 'mili', 'milo',
        'lena', 'liya', 'liye', 'li', 'lo',
        'dena', 'diya', 'diye', 'di', 'do',
        'pakka', 'paka', 'pukka',
        'achanak', 'achnak',
        'shayad', 'sayad', 'shayd',
        'zaroor', 'jarur', 'zarur',
        'matlab', 'mtlb', 'yaani', 'yani',
    }
    
    # Common English words (to distinguish from Hinglish)
    COMMON_ENGLISH = {
        'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'should', 'could', 'can', 'may', 'might', 'must',
        'what', 'where', 'when', 'why', 'how', 'who', 'which',
        'this', 'that', 'these', 'those',
        'a', 'an', 'and', 'or', 'but', 'if', 'then',
        'very', 'so', 'too', 'just', 'only', 'also',
        'about', 'after', 'before', 'because', 'through',
        'for', 'with', 'from', 'into', 'during', 'including',
        'i', 'you', 'he', 'she', 'it', 'we', 'they',
        'my', 'your', 'his', 'her', 'its', 'our', 'their',
        'me', 'him', 'us', 'them'
    }
    
    def __init__(self):
        """Initialize translator with cache."""
        self.translation_cache = {}
        
    def _calculate_script_ratio(self, text: str) -> dict:
        """Calculate the ratio of different scripts in text."""
        # Remove digits and punctuation for analysis
        try:
            text_clean = re.sub(r'[\d\s\.,!?;:\-\'\"()\[\]{}]+', '', text)
            total_chars = len(text_clean)
            
            if total_chars == 0:
                return {'hindi': 0, 'gujarati': 0, 'latin': 0}
            
            hindi_matches = self.HINDI_PATTERN.findall(text_clean)
            gujarati_matches = self.GUJARATI_PATTERN.findall(text_clean)
            latin_matches = self.LATIN_PATTERN.findall(text_clean)
            
            hindi_chars = sum(len(match) for match in hindi_matches)
            gujarati_chars = sum(len(match) for match in gujarati_matches)
            latin_chars = sum(len(match) for match in latin_matches)
            
            return {
                'hindi': hindi_chars / total_chars if total_chars > 0 else 0,
                'gujarati': gujarati_chars / total_chars if total_chars > 0 else 0,
                'latin': latin_chars / total_chars if total_chars > 0 else 0
            }
        except Exception as e:
            logger.log_error("_calculate_script_ratio. Features.py", e)
    
    def _is_hinglish(self, text: str) -> bool:
        """
        Detect if text is Hinglish using multiple heuristics.
        
        Args:
            text: Input text
            
        Returns:
            bool: True if text appears to be Hinglish
        """
        try:
            # Extract words and normalize
            words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
            if not words or len(words) < 2:
                return False
            
            # Count Hinglish indicator words
            hinglish_count = sum(1 for word in words if word in self.HINGLISH_INDICATORS)
            english_count = sum(1 for word in words if word in self.COMMON_ENGLISH)
            
            hinglish_ratio = hinglish_count / len(words)
            english_ratio = english_count / len(words)
            
            # Advanced patterns for Hinglish
            # 1. Repeated characters (yaaar, heyyy, okkk)
            has_repeated_chars = bool(re.search(r'([a-z])\1{2,}', text.lower()))
            
            # 2. Mix of Hindi transliterations and English
            # If has both Hinglish words and English words, likely Hinglish
            has_both = hinglish_count > 0 and english_count > 0
            
            # 3. Common Hinglish sentence patterns
            hinglish_patterns = [
                r'\b(kya|kyun|kaise)\b.*\?',  # Question words
                r'\bhai\b.*\b(kya|yaar|bhai)\b',  # Common combinations
                r'\b(mein|main|hum)\b.*\b(kar|ho|hai)\b',  # Subject-verb patterns
            ]
            has_pattern = any(re.search(pattern, text.lower()) for pattern in hinglish_patterns)
            
            # Decision logic:
            # Strong Hinglish indicators
            if hinglish_ratio > 0.2:  # 20%+ Hinglish words
                return True
            
            # Moderate indicators with supporting evidence
            if hinglish_ratio > 0.1 and (has_repeated_chars or has_pattern):
                return True
            
            # Has both English and Hinglish, but more Hinglish
            if has_both and hinglish_count >= english_count:
                return True
            
            # If mostly English words, it's English
            if english_ratio > 0.4:
                return False
            
            # Default to Hinglish if some indicators present
            return hinglish_count > 0 and hinglish_ratio > 0.05
        except Exception as e:
            logger.log_error("_is_hinglish. Features.py", e)
        
    def detect_language(self, text: str) -> str:
        """
        Detect language with high accuracy using pure regex approach.
        
        Args:
            text: Input text
            
        Returns:
            Language name: 'English', 'Hindi', 'Gujarati', or 'Hinglish'
        """
        try:
            if not text or not text.strip():
                return "English"
            
            text_clean = text.strip()
            
            # Step 1: Script-based detection (fastest and most reliable)
            script_ratios = self._calculate_script_ratio(text_clean)
            
            # If primarily Hindi script (>30% Hindi characters)
            if script_ratios['hindi'] > 0.3:
                return "Hindi"
            
            # If primarily Gujarati script (>30% Gujarati characters)
            if script_ratios['gujarati'] > 0.3:
                return "Gujarati"
            
            # If mixed scripts with some Hindi/Gujarati (5-30%)
            if 0.05 < script_ratios['hindi'] < 0.3:
                return "Hindi"  # Treat as Hindi
            if 0.05 < script_ratios['gujarati'] < 0.3:
                return "Gujarati"
            
            # Step 2: Latin script - distinguish between English and Hinglish
            if script_ratios['latin'] > 0.5 or (script_ratios['hindi'] == 0 and script_ratios['gujarati'] == 0):
                if self._is_hinglish(text_clean):
                    return "Hinglish"
                return "English"
            
            # Default to English for unknown cases
            return "English"
        except Exception as e:
            logger.log_error("detect_launguage. Features.py", e)
    
    def translate_to_english(self, text: str) -> tuple:
        """
        Translate text to English if needed.
        
        Args:
            text: Input text
            
        Returns:
            tuple: (translated_text, source_language)
        """
        try:

            if not text or not isinstance(text, str):
                return "", "English"
            
            text = text.strip()
            
            # ✅ SECURITY: Prevent translation of excessively long text (DoS prevention)
            MAX_TRANSLATE_LENGTH = 5000
            if len(text) > MAX_TRANSLATE_LENGTH:
                logger.log_security_event(
                    "TRANSLATION_TEXT_TOO_LONG",
                    {"length": len(text), "max": MAX_TRANSLATE_LENGTH}
                )
                # Truncate instead of rejecting
                text = text[:MAX_TRANSLATE_LENGTH]

            text = sanitize_input(text)

            if not text or not text.strip():
                return text, "English"
            
            # Detect source language
            source_lang = self.detect_language(text)
            
            # Skip translation if already English
            if source_lang == "English":
                return text, source_lang
            
            # Check cache first
            cache_key = f"to_en_{text}_{source_lang}"
            if cache_key in self.translation_cache:
                return self.translation_cache[cache_key], source_lang
            
            # Get language code
            lang_code = self.LANG_CODES.get(source_lang.lower(), 'auto')
            
            try:
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("Translation timeout")
                
                # Set 10 second timeout
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(10)
                # Translate to English
                translated = GoogleTranslator(source=lang_code, target='en').translate(text)
                
                # Cache the result
                self.translation_cache[cache_key] = translated
                
                return translated, source_lang
                
            except Exception as e:
                print(f"Translation to English failed: {e}")
                return text, source_lang
        except Exception as e:
            logger.log_error("translate_to_english. Features.py", e)
    
    def translate_from_english(self, text: str, target_lang: str) -> str:
        """
        Translate English text back to target language.
        
        Args:
            text: English text
            target_lang: Target language name
            
        Returns:
            Translated text
        """
        try:
            if not text or not isinstance(text, str):
                return text
            
            if not target_lang or not isinstance(target_lang, str):
                return text
            
            text = text.strip()
            
            # ✅ SECURITY: Validate target language
            valid_langs = ['english', 'hindi', 'gujarati', 'hinglish', 'en', 'gu', 'hi']
            if target_lang.lower() not in valid_langs:
                logger.log_security_event(
                    "INVALID_TARGET_LANGUAGE",
                    {"target": target_lang}
                )
                return text
            if not text or not text.strip():
                return text
            
            # Skip if target is English
            if target_lang.lower() == "english":
                return text
            
            MAX_TRANSLATE_LENGTH = 5000
            if len(text) > MAX_TRANSLATE_LENGTH:
                text = text[:MAX_TRANSLATE_LENGTH]

            # Check cache first
            cache_key = f"from_en_{text}_{target_lang}"
            if cache_key in self.translation_cache:
                return self.translation_cache[cache_key]
            
            # Get language code
            target_code = self.LANG_CODES.get(target_lang.lower(), 'en')
            
            try:
                # ✅ SECURITY: Timeout protection
                import signal
                
                def timeout_handler(signum, frame):
                    raise TimeoutError("Translation timeout")
                
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(10)
                
                try:
                    translated = GoogleTranslator(source='en', target=target_code).translate(text)
                finally:
                    signal.alarm(0)
                
                # ✅ SECURITY: Validate output
                if not translated or not isinstance(translated, str):
                    return text
                
                # Cache with size limit
                if len(self.translation_cache) < 1000:
                    self.translation_cache[cache_key] = translated
                
                return translated
                
            except TimeoutError:
                logger.log_error("translate_from_english", "Translation timeout")
                return text
            except Exception as e:
                logger.log_error("translate_from_english", e)
                return text
        except Exception as e:
            logger.log_error("translate_from_english. features.py", e)

    def process_query(self, text: str) -> tuple:
        """
        Complete translation pipeline: detect -> translate to English -> return both.
        
        Args:
            text: Input text in any supported language
            
        Returns:
            tuple: (english_text, source_language, original_text)
        """
        try:
            original_text = text
            english_text, source_lang = self.translate_to_english(text)
            return english_text, source_lang, original_text
        except Exception as e:
            logger.log_error("process_query. Features.py", e)
    
    def process_response(self, english_response: str, target_lang: str) -> str:
        """
        Translate English response back to user's language.
        Enhanced to prevent truncation issues.
        
        Args:
            english_response: Response in English
            target_lang: Target language (detected from user query)
            
        Returns:
            Translated response
        """
        try:
            # Validate input
            if not english_response or not english_response.strip():
                return "I'm sorry, I couldn't generate a response."
            
            english_response = english_response.strip()
            
            # Skip if target is English
            if target_lang.lower() == "english":
                return english_response
            
            # Check cache first
            cache_key = f"from_en_{english_response}_{target_lang}"
            if cache_key in self.translation_cache:
                return self.translation_cache[cache_key]
            
            # Get language code
            target_code = self.LANG_CODES.get(target_lang.lower(), 'en')
            
            # Translate from English
            translated = GoogleTranslator(source='en', target=target_code).translate(english_response)
            
            # Validate translation didn't truncate
            if not translated or len(translated) < len(english_response) * 0.5:
                # Translation might have failed - return English
                logger.log_error(
                    "process_response_translation",
                    f"Translation possibly truncated. Original: {len(english_response)}, Translated: {len(translated) if translated else 0}"
                )
                return english_response
            
            # Cache the result
            self.translation_cache[cache_key] = translated
            
            # Log translation
            logger.log_security_event(
                "BACK_TRANSLATION",
                {
                    "target_lang": target_lang,
                    "original_length": len(english_response),
                    "translated_length": len(translated)
                }
            )
            
            return translated
            
        except Exception as e:
            logger.log_error("Translation from English failed", e)
            # Fallback to English on error
            return english_response
    
    def clear_cache(self):
        """Clear translation cache safely."""
        try:
            cache_size = len(self.translation_cache)
            self.translation_cache.clear()
            logger.log_client_operation(
                "translation_cache_cleared",
                "system",
                success=True
            )
        except Exception as e:
            logger.log_error("clear_cache", e)
    
    def get_cache_size(self) -> int:
        """Get current cache size safely."""
        try:
            return len(self.translation_cache)
        except Exception:
            return 0
    

if __name__ == "__main__":
    translator = EfficientTranslator()

    while True:
        test_text = input("ask anything: ")
        # Detect and translate to English
        english_text, source_lang, original = translator.process_query(test_text)
        print(f"  Detected Language: {source_lang}")
        print(f"  English Translation: {english_text}")

        # Translate back to original language
        if source_lang != "English":
            back_translated = translator.process_response(english_text, source_lang)
            print(f"  Back Translation ({source_lang}): {back_translated}")
