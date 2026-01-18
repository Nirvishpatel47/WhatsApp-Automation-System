from encryption_utils import get_logger, hash_for_FB, hash_for_logging
from firebase import db, formate_number
from rapidfuzz import fuzz
import re
from datetime import datetime, timezone

logger = get_logger()

class SmartGoalExtractor:
    def __init__(self, client_id: str, sender_number: str):
        self.client_id = client_id
        self.sender_number = sender_number

        self.goal_map = {
            "weight_loss": [
                "lose fat", "lose weight", "reduce fat", "burn fat",
                "cut", "shred", "lean", "drop weight", "get slimmer"
            ],
            "muscle_gain": [
                "gain muscle", "build muscle", "bulk", "increase muscle",
                "get bigger", "grow muscles", "add mass", "gain size",
                "get strong", "stronger body", "get jacked"
            ],
            "strength": [
                "gain strength", "be strong", "stronger", "lift heavy",
                "increase power", "build power", "improve strength"
            ],
            "toning": [
                "tone", "shape body", "define", "abs", "six pack",
                "flat stomach", "tighten body", "sculpt", "lean look"
            ],
            "endurance": [
                "stamina", "endurance", "cardio", "run longer",
                "increase energy", "improve fitness level"
            ],
            "recovery": [
                "recover", "rehab", "heal", "injury", "pain", "muscle recovery"
            ],
            "mental_health": [
                "mental", "peace", "calm", "stress", "relax", "mind", "focus"
            ],
            "flexibility": [
                "flexibility", "mobility", "stretch", "yoga", "movement"
            ],
            "fitness_general": [
                "fit", "healthy", "get in shape", "stay active", "better body"
            ]
        }

        self.keywords = {kw: goal for goal, kws in self.goal_map.items() for kw in kws}

        self.patterns = {
            "weight_loss": re.compile(r'\b(lose|burn|reduce|cut|drop|shred|lean)\b.*\b(fat|weight)\b', re.I),
            "muscle_gain": re.compile(r'\b(build|gain|grow|increase|bulk|get)\b.*\b(muscle|mass|size|big|strong)\b', re.I),
            "strength": re.compile(r'\b(strength|power|lift|strong)\b', re.I),
            "toning": re.compile(r'\b(tone|abs|define|shape|sculpt|tighten)\b', re.I),
            "endurance": re.compile(r'\b(stamina|endurance|cardio|energy|fitness)\b', re.I),
            "recovery": re.compile(r'\b(recover|rehab|heal|injury|pain)\b', re.I),
            "mental_health": re.compile(r'\b(stress|relax|calm|mental|focus|mind)\b', re.I),
            "flexibility": re.compile(r'\b(flexibility|mobility|stretch|yoga)\b', re.I),
            "fitness_general": re.compile(r'\b(fit|healthy|shape|active)\b', re.I)
        }

    # ——————————————————————————————————————————

    def extract_goals(self, text: str):
        try:
            if not text or not isinstance(text, str):
                return False

            text = text.lower().strip()
            detected = set()

            # Regex detection
            for goal, pattern in self.patterns.items():
                if pattern.search(text):
                    detected.add(goal)

            # Fuzzy matching
            for phrase, goal in self.keywords.items():
                if fuzz.partial_ratio(phrase, text) >= 90:
                    detected.add(goal)

            # Combo intent
            if any(w in text for w in ["fat", "weight"]) and any(w in text for w in ["muscle", "strong", "bulk"]):
                detected.update(["weight_loss", "muscle_gain"])

            # Merge logic
            if "muscle_gain" in detected and "strength" in detected:
                detected.discard("strength")

            if not detected:
                logger.log_error("detected. extract_goals. SmartGoalExtractor. manager.py", "Failed to extract goals.")
                return False
            # ——————— Firebase Update ———————
            try:
                doc_id = hash_for_FB(formate_number(self.sender_number))
                user_ref = (
                    db.collection("clients")
                    .document(self.client_id)
                    .collection("customer_list")
                    .document(doc_id)
                )

                user_doc = user_ref.get()
                user_data = user_doc.to_dict() if user_doc.exists else {}

                existing_goals = set(user_data.get("goals", []))

                from encryption_utils import encrypt_data
                goals_str = ", ".join(str(g) for g in detected)
                # Only update if new goals found
                if detected and detected != existing_goals:
                    user_ref.update({
                        "goals": encrypt_data(goals_str),
                        "updated_at": datetime.now(timezone.utc)
                    })

                return detected
            except Exception as e:
                return False
            
        except Exception as e:
            logger.log_error("extract_goals. SmartGoalExtractor. manager.py", e)
            return False

from functools import lru_cache
from encryption_utils import hash_password, decrypt_data

@lru_cache(maxsize=5000)
def _cached_name_lookup(client_id: str, formatted_mobile: str) -> str:
    """Internal helper that actually fetches from Firestore."""
    try:
        doc_ref = (
            db
            .collection("clients")
            .document(client_id)
            .collection("customer_list")
            .document(hash_for_FB(formatted_mobile))
        )

        doc = doc_ref.get()
        if not doc.exists:
            logger.log_error("doc. _cached_name_lookup. manager.py", "Failed to get the client from FB.")
            return "User"

        data = doc.to_dict()
        raw_name = data.get("name", {})

        if isinstance(raw_name, dict):
            encrypted_value = raw_name.get("value", "")
        else:
            encrypted_value = raw_name or ""

        user_name = decrypt_data(encrypted_value).strip() or "User"

        logger.logger.info(
            f"✓ Cached username for {hash_for_logging(formatted_mobile)}: {hash_for_logging(user_name)}"
        )

        return user_name

    except Exception as e:
        logger.log_error("_cached_name_lookup", e)
        return "User"


def extract_name_from_FB(mobile_number: str, client_id: str) -> str:
    """Public function to retrieve user name (cached automatically)."""
    try:
        if not mobile_number or not isinstance(mobile_number, str):
            logger.log_error("mobile_number. extract_name_from_FB. manager.py","Invalid mobile number provided.")
            return "User"

        formatted_mobile = formate_number(mobile_number)
        return _cached_name_lookup(client_id, formatted_mobile)

    except Exception as e:
        logger.log_error("extract_name_from_FB", e)

from functools import lru_cache

@lru_cache(maxsize=5000)
def _cached_goals_lookup(client_id: str, formatted_mobile: str) -> list:
    """Internal helper that fetches user goals from Firestore (cached)."""
    try:
        doc_ref = (
            db
            .collection("clients")
            .document(client_id)
            .collection("customer_list")
            .document(hash_for_FB(formatted_mobile))
        )

        doc = doc_ref.get()
        if not doc.exists:
            logger.log_error("doc._cached_goals_lookup.manager.py", "Failed to get the client from FB.")
            return []

        data = doc.to_dict()
        raw_goals = data.get("goals")
        
        # ✅ FIX: Handle None case
        if not raw_goals:
            logger.logger.info(f"No goals set for {hash_for_logging(formatted_mobile)}")
            return []

        # ✅ FIX: Decrypt first, then parse
        try:
            decrypted_goals = decrypt_data(raw_goals)
            
            # Handle different formats after decryption
            if isinstance(decrypted_goals, list):
                goals = decrypted_goals
            elif isinstance(decrypted_goals, str):
                # Try parsing as JSON if it's a stringified list
                import json
                try:
                    goals = json.loads(decrypted_goals)
                except:
                    goals = [decrypted_goals]
            else:
                goals = []
                
        except Exception as decrypt_error:
            logger.log_error("goals_decryption", decrypt_error)
            return []

        # Clean and validate
        goals = [str(g).strip() for g in goals if g]

        logger.logger.info(
            f"✅ Cached goals for {hash_for_logging(formatted_mobile)}: {goals}"
        )

        goals = str(goals)
        goals = goals.replace("[", "")
        goals = goals.replace("]", "")
        goals = goals.replace("'", "")
        return goals

    except Exception as e:
        logger.log_error("_cached_goals_lookup", e)
        return []

def extract_goals_from_FB(mobile_number: str, client_id: str) -> list:
    """Public function to retrieve user goals (cached automatically)."""
    try:
        if not mobile_number or not isinstance(mobile_number, str):
            logger.log_error("mobile_number.extract_goals_from_FB.manager.py", "Invalid mobile number provided.")
            return []

        formatted_mobile = formate_number(mobile_number)
        return _cached_goals_lookup(client_id, formatted_mobile)

    except Exception as e:
        logger.log_error("extract_goals_from_FB", e)
        return []

if __name__ == "__main__":
    print(extract_name_from_FB(mobile_number="8511150215", client_id="ZOGqRNdnjkWUoSbHH5RH"))
