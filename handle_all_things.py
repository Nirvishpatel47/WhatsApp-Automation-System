from datetime import datetime, timezone
from firebase_admin import firestore, credentials
import firebase_admin
from encryption_utils import encrypt_data, logger, sanitize_input
from dotenv import load_dotenv
import os
from Rag import RAGBot
from Features import EfficientTranslator
import random
from get_secreats import get_secret_json
import json
from manager import SmartGoalExtractor
from typing import Optional


logger = logger()

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
        
        # Validate credential path
        cred_path = get_secret_json("FIREBASE_CREDENTIALS_PATH")

        if not cred_path:
            error_msg = "FIREBASE_CREDENTIALS_PATH environment variable not set"
            logger.log_security_event("CONFIG_ERROR", {"error": error_msg})
            raise RuntimeError(error_msg)
        
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

    translator = EfficientTranslator()

except Exception as e:
    logger.log_error("initialze_firebase. handle_all_things.py", e)

import re

PREDEFINED_RESPONSES = {
    "hello": [
        "Hello! 👋 How's your day going? 😄",
        "Hi! 😊 How can I make your day better?",
        "Hey there! 😎 Ready to conquer the day?",
        "Hello! 🙌 Nice to see you again!",
        "Hiya! 😃 How can I assist you today?",
        "Hey! 👋 What’s up? 😁",
        "Yo! 😎 Hope you’re having a fun day!"
    ],
    "hi": [
        "Hi! 😄 How's everything?",
        "Hey! 👋 How's your day going?",
        "Hi there! 😊 What can I do for you?",
        "Hello! 😎 Nice to see you!",
        "Hey! 😁 Ready for some fun?",
        "Hiya! 😃 How’s it going?",
        "Yo! 👋 Hope you’re having an awesome day!"
    ],
    "hey": [
        "Hey! 😄 How’s it going?",
        "Hey there! 👋 Good to see you!",
        "Yo! 😎 What’s up?",
        "Hey! 😊 How can I help you today?",
        "Hey hey! 😁 Hope you’re having fun!",
        "Hi! 👋 Ready to chat?"
    ],
    "bye": [
        "Bye! 👋 Have an amazing day! 😎",
        "Goodbye! 😄 Take care!",
        "See you later! 😊 Keep smiling! 😁",
        "Bye-bye! 👋 Don’t forget to have fun today! 🎉",
        "Farewell! 😎 Until next time! 🚀",
        "Catch you later! 😁 Keep rocking! 🤘"
    ],
    "goodbye": [
        "Goodbye! 👋 Stay awesome! 😄",
        "See you soon! 😊 Take care!",
        "Bye! 😎 Have a fantastic day! 🌟",
        "Farewell! 👋 Wishing you the best! 😁",
        "Catch you later! 😃 Until next time!"
    ],
    "see ya": [
        "See ya! 👋 Have a great day! 😄",
        "Catch you later! 😊 Stay happy! 😁",
        "See you soon! 😎 Keep rocking!",
        "Bye for now! 👋 Take care! 😃"
    ],
    "farewell": [
        "Farewell! 😎 Until next time! 🚀",
        "Goodbye! 👋 Wishing you well! 😄",
        "See you soon! 😊 Stay amazing!",
        "Bye! 😁 Take care and stay safe!"
    ]
}

def convert_bold_to_dash(text: str) -> str:
    """Convert **Title** → - Title:"""
    return re.sub(r'\*\*([^*]+)\*\*', r'- \1:', text)

def get_predefined_response(user_message: str) -> str | None:
    msg_lower = user_message.lower().strip()
    for key, responses in PREDEFINED_RESPONSES.items():
        if key in msg_lower:
            return random.choice(responses)
    return None

def safe_firestore_key(value: str) -> str:
    """Allow only alphanumeric, underscore, and dash in Firestore paths."""
    if not isinstance(value, str):
        return "unknown"
    sanitized = re.sub(r'[^A-Za-z0-9_-]', '_', value)
    return sanitized


# ============================================================================
# CRITICAL FIXES for handle_all_things.py
# ============================================================================

# 1. REMOVE/COMMENT OUT THIS LINE (Line 9):
# from Rag import EmojiEnhancer
# emojie = EmojiEnhancer()

# 2. REMOVE/COMMENT OUT PREDEFINED_RESPONSES (Lines 53-111)
# This prevents "hello/hi/hey" from triggering greetings instead of RAG queries
# Delete or comment out the entire PREDEFINED_RESPONSES dictionary

# 3. REMOVE/COMMENT OUT get_predefined_response function (Lines 113-118)

# 4. REPLACE THE ENTIRE handle_user_message FUNCTION with this fixed version:

async def handle_user_message(client_id: str, sender_number: str, message: str, rag):
    """
    Enhanced message handler with:
    - No emoji injection
    - Proper RAG responses
    - Complete translations
    - Structured output
    """
    try:
        # Make it safe
        client_id = safe_firestore_key(client_id)
        sender_number = safe_firestore_key(sender_number)
        message = sanitize_input(message) 

        """ if not client_id or not sender_number or not message or not message_:
            logger.log_error("id, no, msg, msg_. handle_user_message. handle_all_things.py", "failed to get all client_id, sender_number, message and cleaned_message.") """

        # Get user reference
        from firebase import formate_number
        from encryption_utils import hash_for_FB, hash_for_logging

        doc_id = hash_for_FB(formate_number(sender_number))

        user_ref = db.collection("clients").document(client_id).collection("customer_list").document(doc_id)

        user_doc = user_ref.get()

        if not user_doc.exists:
            # New user
            user_ref.set({
                "status": "awaiting_name",
                "created_at": datetime.now(timezone.utc)
            })
            logger.log_client_operation(client_id=hash_for_logging(client_id), operation="status updated for awaiting name.", success=True)
            
            response = "Hi there! What's your name? "
            return response

        user_data = user_doc.to_dict()
        status = user_data.get("status")

        # ---- Feedback Trigger ----
        ask_for = ["thanks", "thankyou", "thank you", "thank"]
        if any(word in message.lower() for word in ask_for):
            if user_data.get("feedback"):
                response = "You've already given us feedback, thank you!"
                return response
            
            user_ref.update({
                "status": "ask_feedback",
                "last_message": message,
                "updated_at": datetime.now(timezone.utc)
            })
            response = "Thank you! Could you please rate us from 1-5 and share your thoughts?"
            return response

        # ---- Name Collection ----
        if status == "awaiting_name":
            # Try to extract name from message
            name = extract_name_regex(message)
            
            if name:
                # Name found - save it and process the query
                user_ref.update({
                    "name": encrypt_data(name),
                    "status": "get_goals",
                    "last_message": message,
                    "joined_at": datetime.now(timezone.utc)
                })
                
                # Check if the message also contains a query (not just name)
                message_lower = message.lower()
                is_just_name = any([
                    message_lower.startswith("my name is"),
                    message_lower.startswith("i am"),
                    message_lower.startswith("i'm") # Short messages like "John" or "I'm John"
                ])
                
                if is_just_name:
                    # Just name provided
                    response = f"Nice to meet you, {name} ☺️! Can you please tell me your goals?"
                    return response
                else:
                    # Name + query in same message - answer the query using RAG
                    rag_response = await rag.invoke(message)
                    
                    if rag_response:
                        rag_response = rag_response.replace('\n\n', '\n')
                        rag_response = rag_response.replace('\n\n\n', '\n')
                    
                    if not rag_response or len(rag_response.strip()) < 10:
                        rag_response = "I'm sorry 🙇, I couldn't find that information."
                    
                    # Add personal touch with name
                    response = f"{rag_response}\n\nBy the way, nice to meet you, {name} ☺️!"
                    
                    return response
            
            else:
                # No name detected - answer query but still ask for name
                rag_response = await rag.invoke(message)
                
                if rag_response:
                    rag_response = rag_response.replace('\n\n', '\n')
                    rag_response = rag_response.replace('\n\n\n', '\n')
                
                if not rag_response or len(rag_response.strip()) < 10:
                    rag_response = "I'm sorry 🙇, I couldn't find that information."
                
                # Combine answer with name request
                response = f"{rag_response}\n\nBy the way, what's your name?"

                return response

        elif status == "get_goals":
            from manager import extract_name_from_FB
            name = extract_name_from_FB(mobile_number=sender_number, client_id=client_id)

            if not name or name.lower() == "user":
                logger.log_error("name. status=get_goals. handle_user_message. handle_all_things.py", "Error in get name.")

            set_goals = SmartGoalExtractor(client_id=client_id, sender_number=sender_number)

            ans = set_goals.extract_goals(message)
            if ans:
                user_ref.update({
                    "status": "active",
                    "last_message": message,
                    "joined_at": datetime.now(timezone.utc)
                })
                response = f"Thank you {name} ☺️. How can i help you today?"
                return response
            else:
                response = await rag.invoke(message)
                response = response + "\n Can you please tell me your fitness goals?"
                return response

        # ---- Feedback Collection ----
        elif status == "ask_feedback":
            feedback_data = extract_feedback(message)
            rating = feedback_data["rating"]
            reason = feedback_data["reason"]

            if not rating:
                response = "Please provide a rating between 1 and 5 (e.g., '4 because the service was great')."
                return response

            user_ref.update({
                "feedback": {
                    "rating": encrypt_data(rating),
                    "reason": encrypt_data(reason),
                    "timestamp": datetime.now(timezone.utc)
                },
                "status": "active",
                "last_message": message
            })

            if rating == 3:
                response = "Thank you for your feedback. We appreciate your honesty and will continue working to improve our service."
            elif rating == 2:
                response = "We're sorry your experience didn't meet expectations. Your feedback helps us do better next time."
            elif rating == 1:
                response = "We sincerely apologize for the poor experience. Please let us know how we can make things right."
            else:
                response = "Thank you so much for your positive feedback! We're thrilled you had a great experience."
            return response

        # ---- RAG Query (Default) ----
        else:
            user_ref.update({
                "last_message": message,
                "updated_at": datetime.now(timezone.utc)
            })

            # Get RAG response (in English)
            rag_response = await rag.invoke(message)

            # CRITICAL: Ensure complete response before translation
            if not rag_response or len(rag_response.strip()) < 3:
                rag_response = "I'm sorry, I couldn't process your request. Could you rephrase?"
  
            return convert_bold_to_dash(rag_response)

    except Exception as e:
        logger.log_error("handle_user_message", e)
        return "I'm sorry, something went wrong. Please try again."
    
async def handle_user_message_restaurents(client_id: str, sender_number: str, message: str, rag):
    """
    Enhanced restaurant message handler with proper order flow and multi-item support.
    """
    try:
        # Make it safe
        client_id = safe_firestore_key(client_id)
        sender_number = safe_firestore_key(sender_number)
        message = sanitize_input(message)

        # Get user reference
        from firebase import formate_number
        from encryption_utils import hash_for_FB, hash_for_logging, decrypt_data

        doc_id = hash_for_FB(formate_number(sender_number))
        user_ref = db.collection("clients").document(client_id).collection("customer_list").document(doc_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            # New user
            user_ref.set({
                "status": "get_laungage",
                "created_at": datetime.now(timezone.utc),
                "sender_number": encrypt_data(sender_number)
            })
            logger.log_client_operation(client_id=hash_for_logging(client_id), operation="status updated for awaiting name.", success=True)
            return "🌐 Please choose your preferred language:\nEnglish, हिंदी (Hindi), ગુજરાતી (Gujarati), or Hinglish."

        user_data = user_doc.to_dict()
        status = user_data.get("status")
        launguage = decrypt_data(user_data.get("launguage", "English"))

        # ---- Help Command ----
        if message.lower() == "help":
            response = await rag.invoke_translation(
                text=(
                    "📋 *Commands:*\n"
                    "• 'change_default_address' - Update delivery address\n"
                    "• 'order' - Start placing an order\n"
                    "• 'view_order' - See your current order\n"
                    "• 'exit' - Complete your order.\n"
                    "• 'complain' - Submit a complaint\n"
                    "• 'ask_for_feature' - Suggest a new feature\n"
                    "• 'change_launguage' - Change the launguage\n"
                    "• 'change_name'- Change your name\n",
                    "• 'Dine-in' - Eat at the restaurant 🍽️\n"
                    "• 'Delivery' - Get food to your location 🚗\n"
                    "• 'Takeaway' - Pick up and eat elsewhere\n"
                    "• 'refresh' - to ask any question about system.\n"
                    "• Ask about menu items anytime!"
                ),
                target_language=launguage
            )
            return response

        if message.lower() == "developer_call_to_remove_status" or message.lower() == "refresh":
            user_ref.update({
                "status": "active"
            })
            return "Done."
        
        # ---- Feedback Trigger ----
        ask_for = ["thanks", "thankyou", "thank you", "thank"]
        if any(word in message.lower() for word in ask_for):
            if user_data.get("feedback"):
                result = await rag.invoke_translation(
                    text="You've already given us feedback, thank you! 🙏",
                    target_language=launguage
                )
                return result
            
            user_ref.update({
                "status": "ask_feedback",
                "last_message": message,
                "updated_at": datetime.now(timezone.utc)
            })
            result = await rag.invoke_translation(
                text="Thank you! 😊 Could you please rate us from 1-5 and share your thoughts?",
                target_language=launguage
            )
            return result

        # ---- Repeat Previous Order ----
        if message.lower() == "last_one":
            orders_ref = user_ref.collection("orders")

            # Get the most recent confirmed order
            last_order_query = (
                orders_ref
                .where("status", "==", "confirmed")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .limit(1)
            )
            last_order_docs = list(last_order_query.stream())

            if not last_order_docs:
                result = await rag.invoke_translation(
                    text="I couldn’t find any previous order to repeat. You can start a new one by typing 'order' 🙂",
                    target_language=launguage
                )
                return result

            last_order = last_order_docs[0].to_dict()
            items = last_order.get("items", [])
            total = last_order.get("total", 0)

            # Build order summary
            summary = "📋 *Your Previous Order:*\n\n"
            for item in items:
                food = item.get("food_name", "Unknown item")
                size = item.get("size", "")
                quantity = item.get("quantity", 1)
                price = item.get("price", 0)
                item_total = price * quantity

                summary += f"• {food}"
                if size:
                    summary += f" ({size})"
                summary += f" x{quantity} - ₹{item_total}\n"

            summary += f"\n*Total: ₹{total}*\n\nReply 'yes' to confirm or 'no' to cancel."

            # Update user data and reuse confirm logic
            user_ref.update({
                "status": "confirm",
                "cart_session": {"items": items},
                "updated_at": datetime.now(timezone.utc)
            })

            result = await rag.invoke_translation(text=summary, target_language=launguage)
            return result

        # ---- Complain Command ----
        if "complain" in message.lower():
            user_ref.update({"status": "complain"})
            result = await rag.invoke_translation(
                text="I'm sorry for the inconvenience you've experienced 😔. Please share the details of your complaint so We can solve that problem. 🙏",
                target_language=launguage
            )
            return result
        
        if message.lower() == "change_launguage":
            user_ref.update({
                "status": "change_launguage",
                "last_message": encrypt_data(message)  
                })
            return "🌐 Please choose your preferred language:\nEnglish, हिंदी (Hindi), ગુજરાતી (Gujarati), or Hinglish."
        
        if message.lower() == "waiting_list":
            from app import check_new_orders
            check_new_orders()
            result = await rag.invoke_translation(
                text="Thank you for your patience 🙏. We've notified the restaurant about your order, and you'll receive a response within two minutes.",
                target_language=launguage
            )
            return result
        
        if message.lower() == "ask_for_feature":
            user_ref.update({"status": "ask_for_feature"})
            result = await rag.invoke_translation(
                text="We'd love to hear your idea!\nWhich new feature would you like us to add? 🙂.",
                target_language=launguage
            )
            return result

        if message.lower() == "change_default_address":
            user_ref.update({"status": "get_new_address"})
            result = await rag.invoke_translation(
                text="📍 Please share your new delivery address.",
                target_language=launguage
            )
            return result

        if message.lower() == "change_name":
            user_ref.update({"status": "change_name"})
            result = await rag.invoke_translation(
                text="What is your name?",
                target_language=launguage
            )
            return result
        # ---- Start Order Command ----
        if message.lower() == "order":
            user_ref.update({"status": "get_order_type"})
            result = await rag.invoke_translation(
                text="Great! How would you like to enjoy your meal? Type 'Dine-in', 'Delivery', or 'Takeaway' 🙂",
                target_language=launguage
            )
            return result

        # ---- View Order Command ----
        if message.lower() == "view_order":
            orders_ref = user_ref.collection("orders")
            orders = list(orders_ref.where("status", "==", "pending").stream())
            
            if len(orders) == 0:
                result = await rag.invoke_translation(
                    text="🛒 Your cart is currently empty.\nType **order** to start adding delicious items! 😋",
                    target_language=launguage
                )
                return result
            
            summary = "🛒 *Your Current Order:*\n\n"
            total = 0
            for order_doc in orders:
                order_data = order_doc.to_dict()
                food = order_data.get("food_name", "Unknown")
                size = order_data.get("size", "")
                quantity = order_data.get("quantity", 1)
                price = order_data.get("price", 0)
                item_total = price * quantity
                total += item_total
                
                summary += f"• {food}"
                if size:
                    summary += f" ({size})"
                summary += f" x{quantity} - ₹{item_total}\n"
            
            summary += f"\n*Total: ₹{total}*"
            result = await rag.invoke_translation(text=summary, target_language=launguage)
            return result

        # ---- Update Address Flow ----
        if status == "get_new_address":
            from firebase import classify_indian_address

            address = classify_indian_address(message.lower())

            if address.get("Type") == "address" or address.get("type") == "address":
                user_ref.update({
                    "address": encrypt_data(message),
                    "status": "active",
                    "last_message": message,
                    "updated_at": datetime.now(timezone.utc)
                })
                result = await rag.invoke_translation(
                    text="✅ Your address has been updated successfully!",
                    target_language=launguage
                )
                return result
            else:
                reason = address.get("Reason") or address.get("reason") or "Invalid address format"
                result = await rag.invoke_translation(
                    text=f"{reason}\n\nPlease provide a valid delivery address 🏠",
                    target_language=launguage
                )
                return result

        # ---- Name Collection ----
        if status == "awaiting_name":
            name = extract_name_regex(message)
            
            if name:
                user_ref.update({
                    "name": encrypt_data(name),
                    "status": "get_address",
                    "last_message": message,
                    "joined_at": datetime.now(timezone.utc)
                })
                
                message_lower = message.lower()
                is_just_name = any([
                    message_lower.startswith("my name is"),
                    message_lower.startswith("i am"),
                    message_lower.startswith("i'm"),
                    len(message.split()) <= 3
                ])
                
                if is_just_name:
                    result = await rag.invoke_translation(
                        text=f"Nice to meet you, {name}! 😊\n\nPlease provide your delivery address 📍\n(Type 'help' for commands)",
                        target_language=launguage
                    )
                    return result
                else:
                    rag_response = await rag.invoke(message, launguage=launguage)
                    follow_up = await rag.invoke_translation(
                        text=f"By the way, nice to meet you, {name}! 😊\nPlease provide your delivery address.",
                        target_language=launguage
                    )
                    return rag_response + "\n" + follow_up
            else:
                rag_response = await rag.invoke(message, launguage=launguage)
                follow_up = await rag.invoke_translation(
                    text="By the way, may I know your name? 😊 ",
                    target_language=launguage
                )
                return rag_response + "\n" + follow_up

        elif status == "get_laungage":
            launguage_ = extract_language(message)
            
            if launguage_:
                user_ref.update({
                    "launguage": encrypt_data(launguage_),
                    "updated_at": datetime.now(timezone.utc),
                    "status": "awaiting_name"
                })
                result = await rag.invoke_translation(
                    text="Hi there! Welcome to our restaurant! 🍽️ What's your name?",
                    target_language=launguage_
                )
                return result
            else:
                result = await rag.invoke(message, launguage=launguage)
                follow_up = await rag.invoke_translation(
                    text="By the way, which language would you like to continue with? English, हिंदी (Hindi), ગુજરાતી (Gujarati), or Hinglish?",
                    target_language="English"
                )
                return result + "\n" + follow_up
        
        elif status == "change_name":
            name = extract_name_regex(message)
            if name:
                user_ref.update({
                    "name": encrypt_data(name),
                    "status": "active"
                })
            result = await rag.invoke_translation(text="Your name has been changed Now you can browse the menu.", target_language=launguage)
            return result
        
        elif status == "change_launguage":
            launguage_ = extract_language(message)
            if launguage_:
                user_ref.update({
                    "launguage": encrypt_data(launguage_),
                    "updated_at": datetime.now(timezone.utc),
                    "status": "active"
                })
            result = await rag.invoke_translation(text="Your launguage has been changed. You can start ordering by type 'order'", target_language=launguage_)
            return result

        # ---- Address Collection ----
        elif status == "get_address":
            from firebase import classify_indian_address

            address = classify_indian_address(message.lower())
            address_type = address.get("Type") or address.get("type")
            
            if address_type == "address":
                user_ref.update({
                    "address": encrypt_data(message),
                    "status": "active",
                    "last_message": message,
                    "updated_at": datetime.now(timezone.utc)
                })
                result = await rag.invoke_translation(
                    text="✅ Address saved! You can now browse our menu and place orders.\n\nType 'order' to start ordering 🍕",
                    target_language=launguage
                )
                return result
            else:
                reason = await rag.invoke(message, launguage=launguage)
                reason = reason + "\n" + await rag.invoke_translation(text="Buy the way please provide your")
                return result

        elif status == "get_order_type":
            if message.lower() in ["dine-in", "delivery", "takeaway"]:
                try:
                    user_ref.update({"status": "order", "Type": message.capitalize()})
                except Exception as e:
                    logger.log_error("user_ref. status=get_order_type. handle_user_message_restaurent. handle_all_things.py bypassing", e)
                    user_ref.update({"status": "order", "Type": message})
                result = await rag.invoke_translation(
                    text="Great! What would you like to order?\n\n💡 You can order multiple items at once!\nExample: 'I want paneer tikka and veg biryani'\n\nType 'exit' when done ordering.",
                    target_language=launguage
                )
                return result
            else:
                result = await rag.invoke_translation(
                    text="Please choose from 'Dine-in', 'Delivery', or 'Takeaway'. You can also type 'Help' for assistance. 🙂",
                    target_language=launguage
                )
                return result
        
        # ---- Order Flow ----
        elif status == "order":
            if "menu" in message.lower():
                response = await rag.invoke(message, launguage=launguage)
                return response
            
            if message.lower() == "exit":
                # Get current cart session
                cart_session = user_data.get("cart_session", {})
                
                if not cart_session or len(cart_session.get("items", [])) == 0:
                    user_ref.update({"status": "active"})
                    result = await rag.invoke_translation(
                        text="You haven't added any items yet. Type 'order' to start again! 🍕",
                        target_language=launguage
                    )
                    return result
                
                user_ref.update({
                    "status": "confirm",
                    "last_message": message,
                    "updated_at": datetime.now(timezone.utc)
                })
                
                # Show order summary from cart session
                items = cart_session.get("items", [])
                total = sum(item["price"] * item["quantity"] for item in items)
                
                summary = "📋 *Your Order:*\n\n"
                for item in items:
                    food = item["food_name"]
                    size = item.get("size", "")
                    quantity = item["quantity"]
                    price = item["price"]
                    item_total = price * quantity
                    
                    summary += f"• {food}"
                    if size:
                        summary += f" ({size})"
                    summary += f" x{quantity} - ₹{item_total}\n"
                
                summary += f"\n*Total: ₹{total}*\n\n"
                summary += "Reply 'yes' to confirm or 'no' to cancel."
                
                result = await rag.invoke_translation(text=summary, target_language=launguage)
                return result
            
            # Process items and add to cart session
            try:
                separators = [' and ', ',', ' & ', ' with ', '\n']
                items = [message]
                
                for sep in separators:
                    new_items = []
                    for item in items:
                        new_items.extend([x.strip() for x in item.split(sep)])
                    items = new_items
                
                items = [item for item in items if item and len(item.strip()) > 2]
                
                if len(items) <= 1:
                    items = [message]
                
                added_items = []
                failed_items = []
                
                # Process each item
                for item_text in items:
                    try:
                        response_dict = await rag.invoke_for_Res(item_text)
                        
                        if not response_dict or not isinstance(response_dict, dict):
                            failed_items.append((item_text, "Could not understand this item"))
                            continue
                        
                        if response_dict.get("status") is True:
                            order_data = {
                                "food_name": response_dict.get("food_name"),
                                "size": response_dict.get("size", "regular"),
                                "price": response_dict.get("price", 0),
                                "quantity": response_dict.get("quantity", 1)
                            }
                            
                            added_items.append(order_data)
                        else:
                            reason = response_dict.get("reason", "Missing details")
                            failed_items.append((item_text, reason))
                    
                    except Exception as item_error:
                        logger.log_error(f"processing_item_{item_text}", item_error)
                        failed_items.append((item_text, "Processing error"))
                
                # Update cart session in user document
                current_cart = user_data.get("cart_session", {"items": [], "created_at": datetime.now(timezone.utc)})
                current_cart["items"].extend(added_items)
                current_cart["updated_at"] = datetime.now(timezone.utc)
                
                user_ref.update({"cart_session": current_cart})
                
                # Build response
                if len(added_items) > 0:
                    response = "✅ *Added to cart:*\n\n"
                    cart_total = sum(item["price"] * item["quantity"] for item in current_cart["items"])
                    
                    for item in added_items:
                        food_name = item["food_name"]
                        size = item["size"]
                        quantity = item["quantity"]
                        price = item["price"]
                        item_total = price * quantity
                        
                        response += f"• {food_name}"
                        if size and size != "regular":
                            response += f" ({size})"
                        response += f" x{quantity} - ₹{item_total}\n"
                    
                    response += f"\n*Cart Total: ₹{cart_total}*\n"
                
                if len(failed_items) > 0:
                    if len(added_items) > 0:
                        response += "\n⚠️ *Could not add:*\n"
                    else:
                        response = "⚠️ *Could not process your order:*\n\n"
                    
                    for item_text, reason in failed_items:
                        response += f"• {item_text}: {reason}\n"
                
                if len(added_items) == 0 and len(failed_items) == 0:
                    result = await rag.invoke_translation(
                        text="I couldn't understand your order. Please try again or ask about our menu! 🍽️ Or type 'exit' to get answers of your questions.",
                        target_language=launguage
                    )
                    return result
                
                response += "\n💡 Add more items or type 'exit' to review your order!"
                result = await rag.invoke_translation(text=response, target_language=launguage)
                return result
                
            except Exception as e:
                logger.log_error("order_processing", e)
                result = await rag.invoke_translation(
                    text="Sorry, I had trouble processing your order. Please try again! 😅",
                    target_language=launguage
                )
                return result

        # ---- Order Confirmation ----
        elif status == "confirm":
            if message.lower() == "yes":
                cart_session = user_data.get("cart_session", {})
                items = cart_session.get("items", [])
                
                if not items:
                    user_ref.update({"status": "active"})
                    return "No items in cart."
                
                # Create a single order document with all items
                order_id = db.collection("clients") \
                    .document(client_id) \
                    .collection("customer_list") \
                    .document(doc_id) \
                    .collection("orders") \
                    .document()  # Auto-generate ID
                
                order_data = {
                    "items": items,
                    "total": sum(item["price"] * item["quantity"] for item in items),
                    "status": "confirmed",
                    "timestamp": datetime.now(timezone.utc)
                }
                
                order_id.set(order_data)
                
                # Clear cart session
                user_ref.update({
                    "status": "active",
                    "cart_session": firestore.DELETE_FIELD,
                    "last_order_date": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                })
                
                result = await rag.invoke_translation(
                    text="Thank you for your order ✅. Please allow up to two minutes for confirmation.\nIf the order is not confirmed within two minutes write 'waiting_list'. Thanks for your patience Would you like to know more about our restaurant 🙂?",
                    target_language=launguage
                )
                return result
                
            elif message.lower() == "no":
                # Clear cart session
                user_ref.update({
                    "status": "active",
                    "cart_session": firestore.DELETE_FIELD,
                    "updated_at": datetime.now(timezone.utc)
                })
                
                result = await rag.invoke_translation(
                    text="Order cancelled. Type 'order' to start a new one! 🍽️",
                    target_language=launguage
                )
                return result


        # ---- Feedback Collection ----
        elif status == "ask_feedback":
            feedback_data = extract_feedback(message)
            rating = feedback_data["rating"]
            reason = feedback_data["reason"]

            if not rating:
                result = await rag.invoke_translation(
                    text="Please provide a rating between 1 and 5 (e.g., '4 - food was great').",
                    target_language=launguage
                )
                return result

            user_ref.update({
                "feedback": {
                    "rating": encrypt_data(str(rating)),
                    "reason": encrypt_data(reason) if reason else "",
                    "timestamp": datetime.now(timezone.utc)
                },
                "status": "active",
                "last_message": message
            })

            responses = {
                5: "⭐⭐⭐⭐⭐ Thank you so much! We're thrilled you loved it!",
                4: "⭐⭐⭐⭐ Thanks for the great feedback! We appreciate it!",
                3: "⭐⭐⭐ Thank you for your honest feedback. We'll keep improving!",
                2: "⭐⭐ We're sorry we didn't meet expectations. We'll do better!",
                1: "⭐ We sincerely apologize. Please let us know how we can improve!"
            }
            
            result = await rag.invoke_translation(
                text=responses.get(rating, "Thank you for your feedback! 🙏"),
                target_language=launguage
            )
            return result

        elif status == "complain":
            user_ref.update({
                "complain": encrypt_data(message),
                "status": "active"
            })
            result = await rag.invoke_translation(
                text="Your complaint has been noted. Our team will review it and respond shortly. Thank you for your consent and cooperation 🙏",
                target_language=launguage
            )
            return result
        
        elif status == "ask_for_feature":
            user_ref.update({
                "feature_asked": encrypt_data(message),
                "status": "active"
            })
            result = await rag.invoke_translation(
                text="✅ Thank you for your suggestion!\nWe’ll review it carefully.",
                target_language=launguage
            )
            return result
            
        # ---- Default: Menu Questions / General Queries ----
        else:
            user_ref.update({
                "last_message": message,
                "updated_at": datetime.now(timezone.utc)
            })

            # Get RAG response - handles translation internally
            rag_response = await rag.invoke(message, launguage=launguage)

            if not rag_response or len(rag_response.strip()) < 3:
                result = await rag.invoke_translation(
                    text="I'm sorry, I couldn't find that information. Try asking about our menu! 🍽️",
                    target_language=launguage
                )
                return result

            return convert_bold_to_dash(rag_response)

    except Exception as e:
        logger.log_error("handle_user_message_restaurents", e)
        # Get language if available for error message
        try:
            launguage = decrypt_data(user_data.get("launguage", "English")) if 'user_data' in locals() else "English"
            result = await rag.invoke_translation(
                text="😔 Oops! Something didn’t go as planned. Could you please try again in a moment? or write 'refresh' to refresh..",
                target_language=launguage
            )
            return result
        except:
            return "😔 Oops! Something didn’t go as planned. Could you please try again in a moment? or write 'refresh' to refresh."

async def handle_user_message_bakery(client_id: str, sender_number: str, message: str, rag, document: Optional[str] = None):
    """
    Enhanced bakery message handler with custom cake orders and advance ordering.
    """
    try:
        # Make it safe
        client_id = safe_firestore_key(client_id)
        sender_number = safe_firestore_key(sender_number)
        message = sanitize_input(message)

        if document == None or document is None or document == "":
            return "🚧 This section is still under development — check back soon!\n📩 Need help right now? Contact us at: Crevoxega@gmail.com"
        
        document = sanitize_input(document)

        # Get user reference
        from firebase import formate_number
        from encryption_utils import hash_for_FB, hash_for_logging, decrypt_data
        from datetime import datetime, timedelta

        doc_id = hash_for_FB(formate_number(sender_number))
        user_ref = db.collection("clients").document(client_id).collection("customer_list").document(doc_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            # New user
            user_ref.set({
                "status": "active",
                "created_at": datetime.now(timezone.utc),
                "sender_number": encrypt_data(sender_number),
                "launguage": encrypt_data("English")
            })

            from firebase import get_client

            client_data = get_client(client_id=client_id)

            business_name = client_data.get("Business Name", "Our Bakery")
            logger.log_client_operation(client_id=hash_for_logging(client_id), operation="New bakery customer", success=True)

            return (
                f"🍰 *Welcome to {business_name}!* 🎂\n\n"
                "Ask me anything about our menu, or type:\n"
                "• 'order' - Quick buy 🛒\n"
                "• 'custom_cake' - Personalized cakes 🎨\n"
                "• 'menu' - See full menu 📋\n\n"
                "🌍 Language: Type 'change_language' to switch\n"
                "(English • हिंदी • ગુજરાતી • Hinglish)"
            )

        user_data = user_doc.to_dict()
        status = user_data.get("status")
        launguage = decrypt_data(user_data.get("launguage", "English"))

        def give_menu():
            try:
                from firebase import get_client

                client_data = get_client(client_id=client_id)

                menu = client_data.get("menu", "Menu not available.")
                menu = str(menu)

                if menu == "Menu not available.":
                    return ""

                # Clean whitespace + remove empty lines
                menu = "\n".join(
                    line.strip()
                    for line in menu.splitlines()
                    if line.strip()
                )

                return menu
            except Exception as e:
                logger.log_error("give_menu_bakery. handle_user_message_bakery. handle-all_things.py", e)
                return "Menu NOT available."
        
        if message.lower() == "menu":
            return give_menu()
        
        # ---- Help Command ----
        if message.lower() == "help":
            response = await rag.invoke_translation(
                text=(
                    "📋 *SweetCrust Commands:*\n\n"
                    "🛒 *Shopping:*\n"
                    "• 'order' - Browse & buy from menu\n"
                    "• 'custom_cake' - Design your cake 🎂\n"
                    "• 'view_order' - Check your cart\n"
                    "• 'confirm' - Complete purchase ✅\n\n"
                    "⚙️ *Settings:*\n"
                    "• 'change_launguage' - Switch language\n"
                    "• 'change_name' - Update name\n"
                    "• 'change_default_address' - Update address\n\n"
                    "💬 *Feedback:*\n"
                    "• 'complain' - Report issues\n"
                    "• 'ask_for_feature' - Request features\n\n"
                    "Just ask me anything about our bakery! 😊"
                ),
                target_language=launguage
            )
            return response

        if message.lower() == "complain":
            user_ref.update({"status": "complain"})
            result = await rag.invoke_translation(
                text="I'm sorry for the inconvenience you've experienced 😔. Please share the details of your complaint so We can solve that problem. 🙏",
                target_language=launguage
            )
            return result
        
        if message.lower() == "developer_call_to_remove_status" or message.lower() == "refresh":
            user_ref.update({"status": "active"})
            return "Done."

        if message.lower() == "ask_for_feature":
            user_ref.update({"status": "ask_for_feature"})
            return "We'd love to hear your idea! 💡 What feature should we add?"
        
        # ---- Feedback Trigger ----
        ask_for = ["thanks", "thankyou", "thank you", "thank"]
        if any(word in message.lower() for word in ask_for):
            if user_data.get("feedback"):
                result = await rag.invoke_translation(
                    text="You've already shared your feedback - we appreciate it! 💙",
                    target_language=launguage
                )
                return result
            
            user_ref.update({
                "status": "ask_feedback",
                "last_message": message,
                "updated_at": datetime.now(timezone.utc)
            })
            result = await rag.invoke_translation(
                text="Aww, thank you! 🥰 Would you rate us 1-5 stars and tell us what you loved (or didn't)? ⭐",
                target_language=launguage
            )
            return result

        # ---- Common Commands ----
        if message.lower() == "change_launguage" or message.lower() == "change_language":
            user_ref.update({"status": "change_launguage", "last_message": encrypt_data(message)})
            return (
                "🌍 *Choose Your Language:*\n\n"
                "• English\n"
                "• हिंदी (Hindi)\n"
                "• ગુજરાતી (Gujarati)\n"
                "• Hinglish\n\n"
                "Just type the language name! 😊"
            )
        
        if message.lower() == "change_default_address":
            user_ref.update({"status": "get_new_address"})
            result = await rag.invoke_translation(
                text="📍 Sure! What's your new delivery address?",
                target_language=launguage
            )
            return result

        if message.lower() == "change_name":
            user_ref.update({"status": "change_name"})
            result = await rag.invoke_translation(
                text="What should I call you? 😊",
                target_language=launguage
            )
            return result

        # ---- Custom Cake Order Command ----
        if message.lower() == "custom_cake":
            has_name = user_data.get("name", None)
            if not has_name or has_name is None:
                user_ref.update({"status": "awaiting_name", "last_state": "custom_cake"})
                result = await rag.invoke_translation(
                text="What is your name?🙂",
                    target_language=launguage
                )
                return result
            user_ref.update({
                "status": "custom_cake_weight",
                "custom_cake_data": {}
            })
            result = await rag.invoke_translation(
                text="🎂 Custom Cake Order.\nSelect your cake size: 500g, 1kg, 2kg, or more.",
                target_language=launguage
            )
            return result

        # ---- Regular Order Command ----
        if message.lower() == "order":
            
            has_name = user_data.get("name", None)

            if not has_name or has_name is None:
                user_ref.update({"status": "awaiting_name", "last_state": "order"})
                result = await rag.invoke_translation(
                text="What is your name?🙂",
                    target_language=launguage
                )
                return result
            user_ref.update({"status": "get_order_type"})
            result = await rag.invoke_translation(
                text="Great! How would you like to receive your order?\nType 'Delivery' or 'Pickup' 🙂",
                target_language=launguage
            )
            return result

        # ---- Advance Order Command ----
        if message.lower() == "advance_order":
            user_ref.update({"status": "advance_order_date"})
            result = await rag.invoke_translation(
                text="When would you like to receive your order?\nPlease provide date and time (e.g., '25 Dec 2024 3:00 PM') 📅",
                target_language=launguage
            )
            return result

        # ---- View Order Command ----
        if message.lower() == "view_order":
            cart_session = user_data.get("cart_session", {})
            items = cart_session.get("items", [])
            
            if len(items) == 0:
                result = await rag.invoke_translation(
                    text="🛒 Your cart is currently empty.\nType **order** for quick buy or **custom_cake** for personalized cakes! 😋",
                    target_language=launguage
                )
                return result
            
            summary = "🛒 *Your Current Cart:*\n\n"
            total = 0
            
            for item in items:
                item_type = item.get("type", "regular")
                
                if item_type == "custom_cake":
                    weight = item.get("weight")
                    flavour = item.get("flavour")
                    cake_message = item.get("message", "")
                    price = item.get("price", 0)
                    delivery_datetime = item.get("delivery_datetime", "")
                    
                    summary += f"🎂 *Custom Cake*\n"
                    summary += f"   Weight: {weight}\n"
                    summary += f"   Flavour: {flavour}\n"
                    if cake_message:
                        summary += f"   Message: '{cake_message}'\n"
                    if delivery_datetime:
                        summary += f"   Delivery: {delivery_datetime}\n"
                    summary += f"   Price: ₹{price}\n\n"
                    total += price
                else:
                    food = item.get("food_name", "Unknown")
                    quantity = item.get("quantity", 1)
                    price = item.get("price", 0)
                    item_total = price * quantity
                    
                    summary += f"• {food} x{quantity} - ₹{item_total}\n"
                    total += item_total
            
            summary += f"\n*Total: ₹{total}*"
            result = await rag.invoke_translation(text=summary, target_language=launguage)
            return result

        if message.lower() == "last_order":
            last_order_id = user_data.get("last_order_id", None)
            if not last_order_id or last_order_id is None:
                return "Order Not found please order first."
            
            order_doc = user_ref.collection("orders").document(last_order_id)
            if not order_doc.exists:
                return "Sorry 🙏. This section is under development. please try to contact Crevoxega@gmail.com"
            
            order_data = order_doc.get().to_dict()

            user_ref.update({"status": "last_order"})

            order_summary = " * Your Last Order: *\n\n"
            items = order_data.get("items", [])
            total = order_data.get("total", 0)
            for item in items:
                food = item.get("food_name", "Unknown")
                size = item.get("size", "")
                quantity = item.get("quantity", 1)
                price = item.get("price", 0)
                item_total = price * quantity
                
                order_summary += f"• {food}"
                if size:
                    order_summary += f" ({size})"
                order_summary += f" x{quantity} - ₹{item_total}\n"
                order_summary += f"\n*Total: ₹{total}*\n\n"

            order_summary += "Type 'yes' to reorder or 'no' to cancel."
            
            result = await rag.invoke_translation(text=order_summary, target_language=launguage)
            return result
        
        # ---- Language Selection Flow ---- 
        if status == "get_laungage":
            launguage_ = extract_language(message)
            if launguage_:
                user_ref.update({
                    "launguage": encrypt_data(launguage_),
                    "updated_at": datetime.now(timezone.utc),
                    "status": "awaiting_name"
                })
                result = await rag.invoke_translation(
                    text="Hi there! Welcome to our bakery! 🍰 What's your name?",
                    target_language=launguage_
                )
                return result
            else:
                result = await rag.invoke(message, launguage=launguage)
                follow_up = await rag.invoke_translation(
                    text="By the way, which language would you like to continue with?",
                    target_language="English"
                )
                return result + "\n" + follow_up

        elif status == "ask_for_feature":
            user_ref.update({"asked_for_feature": message, "status": "active"})
            return "Thanks for sharing your suggestion — really appreciate it. 🙂"

        elif status == "last_order":
            if message.lower() == "yes":
                order_doc = user_ref.collection("orders").document(last_order_id)
                if not order_doc.exists:
                    return "Sorry 🙏. This section is under development. please try to contact Crevoxega@gmail.com"
                order_doc.update({"status": "confirmed"})
                user_ref.update({"status": "active"})
                result = await rag.invoke_translation(text="Your order has been placed again! ✅\nPlease allow up to two minutes for confirmation.\nIf the order is not confirmed within two minutes write 'waiting_list'.\nThanks for your patience Would you like to know more about our bakery 🙂?", target_language=launguage)
                return result
            elif message.lower() == "no":
                user_ref.update({"status": "active"})
                result = await rag.invoke_translation(text="No problem! If you need anything else, just Let me know. 😊", target_language=launguage)
                return result
            else:
                result = await rag.invoke_translation(text="Please write 'yes' to confirm your order or 'no' to cancel it. 🙂", target_language=launguage)
                return result

        # ---- Name Collection ----
        elif status == "awaiting_name":
            name = extract_name_regex(message)
            if name:
                user_ref.update({
                    "name": encrypt_data(name),
                    "status": "get_address",
                    "last_message": message,
                    "joined_at": datetime.now(timezone.utc)
                })
                result = await rag.invoke_translation(
                    text=f"Nice to meet you, {name}! 😊\n\nPlease provide your delivery address 📍",
                    target_language=launguage
                )
                return result
            else:
                rag_response = await rag.invoke(message, launguage=launguage)
                follow_up = await rag.invoke_translation(
                    text="By the way, may I know your name? 😊",
                    target_language=launguage
                )
                return rag_response + "\n" + follow_up

        # ---- Address Collection ----
        elif status == "get_address":
            from firebase import classify_indian_address
            address = classify_indian_address(message.lower())
            address_type = address.get("Type") or address.get("type")
            
            if address_type == "address":
                user_ref.update({
                    "address": encrypt_data(message),
                    "status": user_data.get("last_state", "active"),
                    "last_message": message,
                    "updated_at": datetime.now(timezone.utc)
                })
                result = await rag.invoke_translation(
                    text="✅ Address saved! You may now continue with your order.",
                    target_language=launguage
                )
                return result
            else:
                reason = await rag.invoke(message, launguage=launguage)
                follow_up = await rag.invoke_translation(
                    text="\n\nPlease provide a valid delivery address 📍",
                    target_language=launguage
                )
                return reason + follow_up

        # ---- Custom Cake Flow: Weight ----
        elif status == "custom_cake_weight":
            # Extract weight from message
            weight_match = re.search(r'(\d+\.?\d*)\s*(kg|g|gram|kilogram)', message.lower())
            
            if weight_match:
                weight_value = float(weight_match.group(1))
                weight_unit = weight_match.group(2)
                
                # Normalize to kg
                if weight_unit in ['g', 'gram']:
                    weight_value = weight_value / 1000
                
                if weight_value < 0.5 or weight_value > 10:
                    result = await rag.invoke_translation(
                        text="Please provide a weight between 500g and 10kg.",
                        target_language=launguage
                    )
                    return result
                
                weight_display = f"{weight_value}kg" if weight_value >= 1 else f"{int(weight_value * 1000)}g"
                
                custom_cake_data = user_data.get("custom_cake_data", {})
                custom_cake_data["weight"] = weight_display
                
                user_ref.update({
                    "status": "custom_cake_flavour",
                    "custom_cake_data": custom_cake_data
                })
                
                result = await rag.invoke_translation(
                    text=f"Great! {weight_display} cake 🎂\n\nWhat flavour would you like? (Check our menu for available flavours)",
                    target_language=launguage
                )
                return result
            else:
                result = await rag.invoke_translation(
                    text="Please specify the weight (e.g., 500g, 1kg, 2kg)",
                    target_language=launguage
                )
                return result

        # ---- Custom Cake Flow: Flavour ----
        elif status == "custom_cake_flavour":
            # Validate flavour against menu using RAG
            flavours = parse_flavours(document)
            
            available_list = [f.lower() for f in flavours.keys()]

            # Simple validation: if response contains "not available" or "no", reject
            if message.lower() not in [available.lower() for available in available_list]:
                result = await rag.invoke_translation(
                    text=f"Sorry, {message} flavour is not available. Please choose from our menu.",
                    target_language=launguage
                )
                return result
            
            custom_cake_data = user_data.get("custom_cake_data", {})
            custom_cake_data["flavour"] = message.strip()
            
            user_ref.update({
                "status": "custom_cake_message",
                "custom_cake_data": custom_cake_data
            })
            
            result = await rag.invoke_translation(
                text="Perfect! 😊\n\nWhat message would you like on the cake? (Type 'skip' if none)",
                target_language=launguage
            )
            return result

        # ---- Custom Cake Flow: Message ----
        elif status == "custom_cake_message":
            custom_cake_data = user_data.get("custom_cake_data", {})
            
            if message.lower() != "skip":
                custom_cake_data["message"] = message.strip()
            
            user_ref.update({
                "status": "custom_cake_delivery_take",
                "custom_cake_data": custom_cake_data
            })
            
            result = await rag.invoke_translation(
                text="Write 'Delivery' to deliver and 'Take_away' to take away your custom cake. 🎂",
                target_language=launguage
            )
            return result

        elif status == "custom_cake_delivery_take":
            custom_cake_data = user_data.get("custom_cake_data", {})
            
            if message.lower() in ["delivery", "take_away", "take away"]:
                custom_cake_data["delivery_take"] = message.title()
            else:
                result = await rag.invoke_translation(message, launguage)
                return result
            
            result = await rag.invoke_translation("📅 When would you like your cake?\nProvide date and time (e.g., '25 Dec 2024 3:00 PM')\n\nOr type 'now' for ASAP")
            return result

        # ---- Custom Cake Flow: Delivery DateTime ----
        elif status == "custom_cake_delivery":
            from dateutil import parser as date_parser
            
            custom_cake_data = user_data.get("custom_cake_data", {})

            flavours = parse_flavours(document)

            delivery_datetime = None
            
            if message.lower() == "now":
                delivery_datetime = "ASAP"
            else:
                try:
                    # Parse date/time from message
                    parsed_date = date_parser.parse(message, fuzzy=True)
                    
                    # Validate: must be in future
                    if parsed_date < datetime.now():
                        result = await rag.invoke_translation(
                            text="Please provide a future date and time.",
                            target_language=launguage
                        )
                        return result
                    
                    # Validate: not more than 30 days ahead
                    if parsed_date > datetime.now() + timedelta(days=30):
                        result = await rag.invoke_translation(
                            text="We accept orders up to 30 days in advance.",
                            target_language=launguage
                        )
                        return result
                    
                    delivery_datetime = parsed_date.strftime("%d %b %Y %I:%M %p")
                    
                except:
                    result = await rag.invoke_translation(
                        text="I couldn't understand the date/time. Please try again (e.g., '25 Dec 2024 3:00 PM')",
                        target_language=launguage
                    )
                    return result
                
            custom_cake_data["delivery_datetime"] = delivery_datetime
            
            # Calculate price based on weight
            weight_str = custom_cake_data.get("weight", "1kg")
            weight_value = float(re.search(r'(\d+\.?\d*)', weight_str).group(1))
            if 'g' in weight_str and 'kg' not in weight_str:
                weight_value = weight_value / 1000
            
            flav_strip = custom_cake_data['flavour'].strip()
            flav_str = str(flav_strip).title()

            base_price_per_kg = flavours[flav_str] # Base price, can be adjusted
            
            calculated_price = int(weight_value * base_price_per_kg)
            custom_cake_data["price"] = calculated_price
            custom_cake_data["type"] = "custom_cake"

            # Add a temporary cart entry for confirmation summary
            cart_session = {"items": [{
                "type": "custom_cake",
                "weight": custom_cake_data.get("weight"),
                "flavour": custom_cake_data.get("flavour"),
                "message": custom_cake_data.get("message", ""),
                "delivery_datetime": delivery_datetime,
                "price": calculated_price
            }]}

            user_ref.update({
                "status": "confirm",
                "cart_session": cart_session,
                "last_message": message,
                "updated_at": datetime.now(timezone.utc),
                "custom_cake_data": firestore.DELETE_FIELD
            })


            # Move user to confirmation state
            user_ref.update({
                "status": "instruction_for_custom_cake",
                "last_message": message,
                "updated_at": datetime.now(timezone.utc),
                "custom_cake_data": firestore.DELETE_FIELD
            })

            summary = f"✅ *Custom Cake Added!*\n\n"
            summary += f"🎂 Weight: {custom_cake_data['weight']}\n"
            summary += f"🍰 Flavour: {custom_cake_data['flavour']}\n"
            if custom_cake_data.get("message"):
                summary += f"💌 Message: '{custom_cake_data['message']}'\n"
            summary += f"📅 Delivery: {delivery_datetime}\n"
            summary += f"💰 Price: ₹{calculated_price}\n\n"
            summary += "Any special instructions for your cake? 🙂"
            
            result = await rag.invoke_translation(text=summary, target_language=launguage)
            return result

        # ---- Advance Order Flow ----
        elif status == "advance_order_date":
            from dateutil import parser as date_parser
            
            try:
                parsed_date = date_parser.parse(message, fuzzy=True)
                
                if parsed_date < datetime.now() + timedelta(hours=24):
                    result = await rag.invoke_translation(
                        text="Advance orders must be at least 24 hours ahead.",
                        target_language=launguage
                    )
                    return result
                
                if parsed_date > datetime.now() + timedelta(days=30):
                    result = await rag.invoke_translation(
                        text="We accept orders up to 30 days in advance.",
                        target_language=launguage
                    )
                    return result
                
                delivery_datetime = parsed_date.strftime("%d %b %Y %I:%M %p")
                
                user_ref.update({
                    "status": "order",
                    "Type": "Advance",
                    "advance_delivery_datetime": delivery_datetime
                })
                
                result = await rag.invoke_translation(
                    text=f"📅 Advance order for {delivery_datetime}\n\nWhat would you like to order?\nType 'exit' when done.",
                    target_language=launguage
                )
                return result
                
            except:
                result = await rag.invoke_translation(
                    text="Please provide a valid date and time (e.g., '25 Dec 2024 3:00 PM')",
                    target_language=launguage
                )
                return result

        # ---- Order Type Selection ----
        elif status == "get_order_type":
            if message.lower() in ["delivery", "pickup"]:
                cart_session = user_data.get("cart_session", {"items": []})
                cart_session["Type"] = message.title()
                result = await rag.invoke_translation(
                    text="Great! What would you like to order?\n\n💡 You can order multiple items at once!\nType 'exit' when done ordering.",
                    target_language=launguage
                )

                result = result + "\n\nHere is Menu: \n" + give_menu()

                return result
            else:
                result = await rag.invoke_translation(
                    text="Please choose 'Delivery' or 'Pickup'. Type 'help' for assistance. 🙂",
                    target_language=launguage
                )
                return result

        elif status == "instruction_for_custom_cake":
            custom_cake_data = user_data.get("custom_cake_data", {})
            custom_cake_data["instructions"] = message.strip()
            user_ref.update({
                "custom_cake_data": custom_cake_data,
                "status": "confirm_order",
                "last_message": encrypt_data(message)
            })
            result = await rag.invoke_translation(
                text="✅ Instructions saved! \nConfirm Your order by typing 'yes' or 'no' to cancel.",
                target_language=launguage
            )
            return result

        elif status == "instructions_for_order":
            cart_session = user_data.get("cart_session", {"items": []})
            cart_session["instructions"] = message.strip()
            user_ref.update({
                "cart_session": cart_session,
                "status": "confirm_order",
                "last_message": encrypt_data(message)
            })
            result = await rag.invoke_translation(
                text="✅ Instructions saved! \nConfirm Your order by typing 'yes' or 'no' to cancel.",
                target_language=launguage
            )
            return result

        # ---- Order Flow (Regular Items) ----
        elif status == "order":
            if message.lower() in ["done", "checkout", "finish", "confirm", "exit"]:
                cart_session = user_data.get("cart_session", {})
                items = cart_session.get("items", [])
                
                if not items:
                    user_ref.update({"status": "active", "last_message": encrypt_data(message)})
                    result = await rag.invoke_translation(
                        text="Your cart is empty! Add items first by typing 'order' 🛒",
                        target_language=launguage
                    )
                    return result
                
                # Check name/address
                has_name = user_data.get("name")
                has_address = user_data.get("address")
                
                if not has_name:
                    user_ref.update({
                        "status": "collect_name",
                        "last_message": encrypt_data(message)
                    })
                    result = await rag.invoke_translation(
                        text="Before checkout, what's your name? 😊",
                        target_language=launguage
                    )
                    return result
                elif not has_address:
                    user_ref.update({
                        "status": "collect_address",
                        "last_message": encrypt_data(message)
                    })
                    result = await rag.invoke_translation(
                        text="Where should we deliver? 📍",
                        target_language=launguage
                    )
                    return result
                else:
                    # Show summary
                    total = sum(
                        item.get("price", 0) * item.get("quantity", 1) if item.get("type") != "custom_cake" 
                        else item.get("price", 0) 
                        for item in items
                    )
                    
                    summary = "🛒 *Order Summary:*\n\n"
                    for item in items:
                        if item.get("type") == "custom_cake":
                            summary += f"🎂 {item.get('weight')} {item.get('flavour')} - ₹{item.get('price')}\n"
                        else:
                            summary += f"• {item.get('food_name')} x{item.get('quantity')} - ₹{item.get('price') * item.get('quantity')}\n"
                    
                    summary += f"\n💰 *Total: ₹{total}*\n\n"
                    summary += "Any instructions for your order? 😊"
                    
                    user_ref.update({
                        "status": "instructions_for_order",
                        "last_message": encrypt_data(message)
                    })
                    
                    result = await rag.invoke_translation(text=summary, target_language=launguage)
                    return result
            
            # Process items
            try:
                separators = [' and ', ',', ' & ', ' with ', '\n']
                item_texts = [message]
                
                for sep in separators:
                    new_items = []
                    for item in item_texts:
                        new_items.extend([x.strip() for x in item.split(sep)])
                    item_texts = new_items
                
                item_texts = [item for item in item_texts if item and len(item.strip()) > 2]
                
                added = []
                failed = []
                
                for item_text in item_texts:
                    try:
                        result_dict = await rag.invoke_for_Res(item_text)
                        
                        if result_dict and result_dict.get("status") is True:
                            added.append({
                                "type": "regular",
                                "food_name": result_dict.get("food_name"),
                                "price": result_dict.get("price", 0),
                                "quantity": result_dict.get("quantity", 1)
                            })
                        else:
                            failed.append((item_text, result_dict.get("reason", "Not found")))
                    except:
                        failed.append((item_text, "Error processing"))
                
                if added:
                    cart_session = user_data.get("cart_session", {"items": []})
                    cart_session["items"].extend(added)
                    
                    user_ref.update({
                        "cart_session": cart_session,
                        "last_message": encrypt_data(message)
                    })
                    
                    response = "✅ *Added to cart:*\n\n"
                    for item in added:
                        response += f"• {item['food_name']} x{item['quantity']} - ₹{item['price'] * item['quantity']}\n"
                    
                    cart_total = sum(i['price'] * i['quantity'] for i in cart_session['items'])
                    response += f"\n🛒 Cart Total: ₹{cart_total}\n\n"
                    
                    if failed:
                        response += "\n⚠️ Couldn't add:\n"
                        for item_text, reason in failed:
                            response += f"• {item_text}: {reason}\n"
                    
                    response += "\nAdd more or type 'done' to checkout! 😊"
                    result = await rag.invoke_translation(text=response, target_language=launguage)
                    return result
                else:
                    response = "⚠️ Couldn't find those items.\n\n"
                    for item_text, reason in failed:
                        response += f"• {item_text}: {reason}\n"
                    response += "\nCheck the menu or try different names! 😊"
                    result = await rag.invoke_translation(text=response, target_language=launguage)
                    return result
                    
            except Exception as e:
                logger.log_error("order_items_processing", e)
                result = await rag.invoke_translation(
                    text="Oops, something went wrong 😅 Try again?",
                    target_language=launguage
                )
                return result

        # ---- Order Confirmation ----
        elif status == "confirm_order":
            if message.lower() in ["yes", "confirm", "place order", "ok", "sure", "done"]:
                cart_session = user_data.get("cart_session", {})
                items = cart_session.get("items", [])
                
                if not items:
                    user_ref.update({"status": "active", "last_message": encrypt_data(message)})
                    return "❌ No items to confirm."
                
                # ========== SINGLE ORDER DOCUMENT (CONSISTENT STORAGE) ==========
                total = sum(
                    item.get("price", 0) * item.get("quantity", 1) if item.get("type") != "custom_cake" 
                    else item.get("price", 0) 
                    for item in items
                )
                
                order_ref = user_ref.collection("orders").document()
                
                order_data = {
                    "status": "confirmed",
                    "timestamp": datetime.now(timezone.utc),
                    "total": total,
                    "items": [
                        {
                            "instructions": item.get("instructions", cart_session.get("instructions", None)),
                            "Type": user_data.get("Type", "Not Specified by user."),
                            "type": item.get("type", "regular"),
                            "food_name": item.get("food_name") if item.get("type") == "regular" else None,
                            "quantity": item.get("quantity", 1) if item.get("type") == "regular" else None,
                            "weight": item.get("weight") if item.get("type") == "custom_cake" else None,
                            "flavour": item.get("flavour") if item.get("type") == "custom_cake" else None,
                            "message": item.get("message") if item.get("type") == "custom_cake" else None,
                            "delivery_datetime": item.get("delivery_datetime") if item.get("type") == "custom_cake" else None,
                            "price": item.get("price", 0)
                        }
                        for item in items
                    ]
                }
                
                # Save order ONCE
                order_ref.set(order_data)

                user_ref.update({"last_order_id": order_ref.id})
                
                # Clear cart and reset status
                user_ref.update({
                    "status": "active",
                    "cart_session": firestore.DELETE_FIELD,
                    "custom_cake_data": firestore.DELETE_FIELD,
                    "last_order_date": datetime.now(timezone.utc),
                    "last_message": encrypt_data(message),
                    "Type": firestore.DELETE_FIELD
                })
                
                result = await rag.invoke_translation(
                    text=(
                        "🎉 *Order Confirmed!*\n\n"
                        "We'll get back to you within 2 minutes ⏱️\n\n"
                        "If you don't hear from us, type 'waiting_list'\n\n"
                        "Thank you for us! 💙"
                    ),
                    target_language=launguage
                )
                return result
                
            elif message.lower() in ["no", "cancel", "nope"]:
                user_ref.update({
                    "status": "active",
                    "cart_session": firestore.DELETE_FIELD,
                    "custom_cake_data": firestore.DELETE_FIELD,
                    "last_message": encrypt_data(message)
                })
                
                result = await rag.invoke_translation(
                    text="❌ Order cancelled. Type 'order' to start fresh! 😊",
                    target_language=launguage
                )
                return result
            else:
                result = await rag.invoke_translation(
                    text="Type 'yes' to confirm or 'no' to cancel 😊",
                    target_language=launguage
                )
                return result
        # ---- Feedback Collection ----
        elif status == "ask_feedback":
            feedback_data = extract_feedback(message)
            rating = feedback_data["rating"]
            reason = feedback_data["reason"]

            if not rating:
                result = await rag.invoke_translation(
                    text="Please rate us 1-5 (e.g., '4 - delicious cakes').",
                    target_language=launguage
                )
                return result

            user_ref.update({
                "feedback": {
                    "rating": encrypt_data(str(rating)),
                    "reason": encrypt_data(reason) if reason else "",
                    "timestamp": datetime.now(timezone.utc)
                },
                "status": "active"
            })

            responses = {
                5: "⭐⭐⭐⭐⭐ Thank you! We're delighted!",
                4: "⭐⭐⭐⭐ Thanks for the great feedback!",
                3: "⭐⭐⭐ Thank you! We'll keep improving!",
                2: "⭐⭐ Sorry we didn't meet expectations. We'll do better!",
                1: "⭐ We sincerely apologize. Please let us know how to improve!"
            }
            
            result = await rag.invoke_translation(
                text=responses.get(rating, "Thank you for your feedback! 🙏"),
                target_language=launguage
            )
            return result

        # ---- Complaint Handling ----
        elif status == "complain":
            user_ref.update({
                "complain": encrypt_data(message),
                "status": "active"
            })
            result = await rag.invoke_translation(
                text="We're sorry to hear that 😔 Please share your concern - we'll make it right! 🙏",
                target_language=launguage
            )
            return result

        # ---- Change Name ----
        elif status == "change_name":
            name = extract_name_regex(message)
            if name:
                user_ref.update({
                    "name": encrypt_data(name),
                    "status": "active"
                })
            result = await rag.invoke_translation(
                text="Your name has been updated. Browse our menu now! 🍰",
                target_language=launguage
            )
            return result
        
        # ---- Change Language ----
        elif status == "change_language":
            launguage_ = extract_language(message)
            if launguage_:
                user_ref.update({
                    "launguage": encrypt_data(launguage_),
                    "updated_at": datetime.now(timezone.utc),
                    "status": "active"
                })
            result = await rag.invoke_translation(
                text="Language changed! Start ordering by typing 'order'",
                target_language=launguage_
            )
            return result

        # ---- Update Address ----
        elif status == "get_new_address":
            from firebase import classify_indian_address
            address = classify_indian_address(message.lower())
            
            if address.get("Type") == "address" or address.get("type") == "address":
                user_ref.update({
                    "address": encrypt_data(message),
                    "status": "active",
                    "updated_at": datetime.now(timezone.utc)
                })
                result = await rag.invoke_translation(
                    text="✅ Address updated successfully!",
                    target_language=launguage
                )
                return result
            else:
                reason = address.get("Reason") or "Invalid address"
                result = await rag.invoke_translation(
                    text=f"{reason}\n\nPlease provide a valid address 📍",
                    target_language=launguage
                )
                return result

        # ---- Default: Menu Questions ----
        else:
            user_ref.update({
                "last_message": message,
                "updated_at": datetime.now(timezone.utc)
            })

            rag_response = await rag.invoke(message, launguage=launguage)

            if not rag_response or len(rag_response.strip()) < 3:
                result = await rag.invoke_translation(
                    text="I couldn't find that info. Ask about our menu! 🍰",
                    target_language=launguage
                )
                return result

            return convert_bold_to_dash(rag_response)

    except Exception as e:
        logger.log_error("handle_user_message_bakery", e)
        try:
            launguage = decrypt_data(user_data.get("launguage", "English")) if 'user_data' in locals() else "English"
            result = await rag.invoke_translation(
                text="😔 Oops! Something went wrong. Try again or type 'refresh'.",
                target_language=launguage
            )
            return result
        except:
            return "😔 Oops! Something went wrong. Try again or type 'refresh'."
        
async def handle_user_message_free_version(message: str, rag) -> str:
    response = await rag.invoke(message, "English")     

    if not response or len(response.strip()) < 3:
        response = "I couldn't find that info. Please try asking something else!"

    return response
        
async def handle_user_message_cloth_store(client_id: str, sender_number: str, message: str, rag, document: Optional[str] = None):
    """
    Enhanced cloth store message handler with multi-language support and proper order flow.
    Handles clothing items with attributes like size, color, and style.
    """
    try:
        # Make it safe
        client_id = safe_firestore_key(client_id)
        sender_number = safe_firestore_key(sender_number)
        message = sanitize_input(message)
        
        document = sanitize_input(document)

        # Get user reference
        from firebase import formate_number
        from encryption_utils import hash_for_FB, hash_for_logging, decrypt_data
        from datetime import datetime, timedelta

        doc_id = hash_for_FB(formate_number(sender_number))
        user_ref = db.collection("clients").document(client_id).collection("customer_list").document(doc_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            # New user
            user_ref.set({
                "status": "active",
                "created_at": datetime.now(timezone.utc),
                "sender_number": encrypt_data(sender_number),
                "launguage": encrypt_data("English")
            })

            from firebase import get_client
            client_data = get_client(client_id=client_id)
            business_name = client_data.get("Business Name", "Our Cloth Store")
            logger.log_client_operation(client_id=hash_for_logging(client_id), operation="New cloth store customer", success=True)

            return (
                f"👕 *Welcome to {business_name}!* 👗\n\n"
                "Ask me anything about our collection, or type:\n"
                "• 'order' - Start shopping 🛒\n"
                "• 'catalog' - View full collection 📋\n"
                "• 'size_guide' - Check sizing info 📏\n\n"
                "🌐 Language: Type 'change_language' to switch\n"
                "(English • हिंदी • ગુજરાતી • Hinglish)"
            )

        user_data = user_doc.to_dict()
        status = user_data.get("status")
        launguage = decrypt_data(user_data.get("launguage", "English"))

        def give_catalog():
            try:
                from firebase import get_client
                client_data = get_client(client_id=client_id)
                catalog = client_data.get("catalog", "Catalog not available.")
                catalog = str(catalog)

                if catalog == "Catalog not available.":
                    return ""

                # Clean whitespace + remove empty lines
                catalog = "\n".join(
                    line.strip()
                    for line in catalog.splitlines()
                    if line.strip()
                )
                return catalog
            except Exception as e:
                logger.log_error("give_catalog_cloth. handle_user_message_cloth_store. handle_all_things.py", e)
                return "Catalog NOT available."
        
        if message.lower() in ["catalog", "catalogue", "menu", "collection"]:
            return give_catalog()
        
        # ---- Help Command ----
        if message.lower() == "help":
            response = await rag.invoke_translation(
                text=(
                    "📋 *Cloth Store Commands:*\n\n"
                    "🛒 *Shopping:*\n"
                    "• 'order' - Browse & buy clothing\n"
                    "• 'view_order' - Check your cart\n"
                    "• 'confirm' - Complete purchase ✅\n"
                    "• 'catalog' - View full collection\n"
                    "• 'size_guide' - Sizing information\n\n"
                    "⚙️ *Settings:*\n"
                    "• 'change_launguage' - Switch language\n"
                    "• 'change_name' - Update name\n"
                    "• 'change_default_address' - Update address\n\n"
                    "💬 *Feedback:*\n"
                    "• 'complain' - Report issues\n"
                    "• 'ask_for_feature' - Request features\n\n"
                    "Just ask me anything about our clothing! 😊"
                ),
                target_language=launguage
            )
            return response

        if message.lower() == "complain":
            user_ref.update({"status": "complain"})
            result = await rag.invoke_translation(
                text="I'm sorry for the inconvenience you've experienced 😔. Please share the details of your complaint so we can solve that problem. 🙏",
                target_language=launguage
            )
            return result
        
        if message.lower() == "developer_call_to_remove_status" or message.lower() == "refresh":
            user_ref.update({"status": "active"})
            return "Done."

        if message.lower() == "ask_for_feature":
            user_ref.update({"status": "ask_for_feature"})
            return "We'd love to hear your idea! 💡 What feature should we add?"
        
        if message.lower() == "size_guide":
            result = await rag.invoke_translation(
                text=(
                    "📏 *Size Guide:*\n\n"
                    "• XS - Extra Small\n"
                    "• S - Small\n"
                    "• M - Medium\n"
                    "• L - Large\n"
                    "• XL - Extra Large\n"
                    "• XXL - Double Extra Large\n\n"
                    "For specific measurements, ask about any item!"
                ),
                target_language=launguage
            )
            return result
        
        # ---- Feedback Trigger ----
        ask_for = ["thanks", "thankyou", "thank you", "thank"]
        if any(word in message.lower() for word in ask_for):
            if user_data.get("feedback"):
                result = await rag.invoke_translation(
                    text="You've already shared your feedback - we appreciate it! 💙",
                    target_language=launguage
                )
                return result
            
            user_ref.update({
                "status": "ask_feedback",
                "last_message": message,
                "updated_at": datetime.now(timezone.utc)
            })
            result = await rag.invoke_translation(
                text="Aww, thank you! 🥰 Would you rate us 1-5 stars and tell us what you loved (or didn't)? ⭐",
                target_language=launguage
            )
            return result

        # ---- Common Commands ----
        if message.lower() == "change_launguage" or message.lower() == "change_language":
            user_ref.update({"status": "change_launguage", "last_message": encrypt_data(message)})
            return (
                "🌐 *Choose Your Language:*\n\n"
                "• English\n"
                "• हिंदी (Hindi)\n"
                "• ગુજરાતી (Gujarati)\n"
                "• Hinglish\n\n"
                "Just type the language name! 😊"
            )
        
        if message.lower() == "change_default_address":
            user_ref.update({"status": "get_new_address"})
            result = await rag.invoke_translation(
                text="📍 Sure! What's your new delivery address?",
                target_language=launguage
            )
            return result

        if message.lower() == "change_name":
            user_ref.update({"status": "change_name"})
            result = await rag.invoke_translation(
                text="What should I call you? 😊",
                target_language=launguage
            )
            return result

        # ---- Regular Order Command ----
        if message.lower() == "order":
            has_name = user_data.get("name", None)
            if not has_name or has_name is None:
                user_ref.update({"status": "awaiting_name", "last_state": "order"})
                result = await rag.invoke_translation(
                    text="What is your name? 🙂",
                    target_language=launguage
                )
                return result
            user_ref.update({"status": "get_order_type"})
            result = await rag.invoke_translation(
                text="Great! How would you like to receive your order?\nType 'Delivery' or 'Pickup' 🙂",
                target_language=launguage
            )
            return result

        # ---- View Order Command ----
        if message.lower() == "view_order":
            cart_session = user_data.get("cart_session", {})
            items = cart_session.get("items", [])
            
            if len(items) == 0:
                result = await rag.invoke_translation(
                    text="🛒 Your cart is currently empty.\nType **order** to start shopping! 🛍️",
                    target_language=launguage
                )
                return result
            
            summary = "🛒 *Your Current Cart:*\n\n"
            total = 0
            
            for item in items:
                item_name = item.get("item_name", "Unknown Item")
                size = item.get("size", "")
                color = item.get("color", "")
                quantity = item.get("quantity", 1)
                price = item.get("price", 0)
                item_total = price * quantity
                
                summary += f"• {item_name}"
                if size:
                    summary += f" (Size: {size})"
                if color:
                    summary += f" (Color: {color})"
                summary += f" x{quantity} - ₹{item_total}\n"
                total += item_total
            
            summary += f"\n*Total: ₹{total}*"
            result = await rag.invoke_translation(text=summary, target_language=launguage)
            return result

        if message.lower() == "last_order":
            last_order_id = user_data.get("last_order_id", None)
            if not last_order_id or last_order_id is None:
                return "Order Not found. Please order first."
            
            order_doc = user_ref.collection("orders").document(last_order_id)
            if not order_doc.exists:
                return "Sorry 🙏. This section is under development. Please try to contact Crevoxega@gmail.com"
            
            order_data = order_doc.get().to_dict()
            user_ref.update({"status": "last_order"})

            order_summary = "*Your Last Order:*\n\n"
            items = order_data.get("items", [])
            total = order_data.get("total", 0)
            
            for item in items:
                item_name = item.get("item_name", "Unknown")
                size = item.get("size", "")
                color = item.get("color", "")
                quantity = item.get("quantity", 1)
                price = item.get("price", 0)
                item_total = price * quantity
                
                order_summary += f"• {item_name}"
                if size:
                    order_summary += f" ({size})"
                if color:
                    order_summary += f" - {color}"
                order_summary += f" x{quantity} - ₹{item_total}\n"
            
            order_summary += f"\n*Total: ₹{total}*\n\n"
            order_summary += "Type 'yes' to reorder or 'no' to cancel."
            
            result = await rag.invoke_translation(text=order_summary, target_language=launguage)
            return result
        
        # ---- Language Selection Flow ----
        if status == "get_laungage":
            launguage_ = extract_language(message)
            if launguage_:
                user_ref.update({
                    "launguage": encrypt_data(launguage_),
                    "updated_at": datetime.now(timezone.utc),
                    "status": "awaiting_name"
                })
                result = await rag.invoke_translation(
                    text="Hi there! Welcome to our cloth store! 👕 What's your name?",
                    target_language=launguage_
                )
                return result
            else:
                result = await rag.invoke(message, launguage=launguage)
                follow_up = await rag.invoke_translation(
                    text="By the way, which language would you like to continue with?",
                    target_language="English"
                )
                return result + "\n" + follow_up

        elif status == "ask_for_feature":
            user_ref.update({"asked_for_feature": message, "status": "active"})
            return "Thanks for sharing your suggestion — really appreciate it. 🙂"

        elif status == "last_order":
            if message.lower() == "yes":
                order_doc = user_ref.collection("orders").document(last_order_id)
                if not order_doc.exists:
                    return "Sorry 🙏. This section is under development. Please try to contact Crevoxega@gmail.com"
                order_doc.update({"status": "confirmed"})
                user_ref.update({"status": "active"})
                result = await rag.invoke_translation(
                    text="Your order has been placed again! ✅\nWe'll process it shortly.\nThank you for shopping with us! 🙂",
                    target_language=launguage
                )
                return result
            elif message.lower() == "no":
                user_ref.update({"status": "active"})
                result = await rag.invoke_translation(
                    text="No problem! If you need anything else, just let me know. 😊",
                    target_language=launguage
                )
                return result
            else:
                result = await rag.invoke_translation(
                    text="Please write 'yes' to confirm your order or 'no' to cancel it. 🙂",
                    target_language=launguage
                )
                return result

        # ---- Name Collection ----
        elif status == "awaiting_name":
            name = extract_name_regex(message)
            if name:
                user_ref.update({
                    "name": encrypt_data(name),
                    "status": "get_address",
                    "last_message": message,
                    "joined_at": datetime.now(timezone.utc)
                })
                result = await rag.invoke_translation(
                    text=f"Nice to meet you, {name}! 😊\n\nPlease provide your delivery address 📍",
                    target_language=launguage
                )
                return result
            else:
                rag_response = await rag.invoke(message, launguage=launguage)
                follow_up = await rag.invoke_translation(
                    text="By the way, may I know your name? 😊",
                    target_language=launguage
                )
                return rag_response + "\n" + follow_up

        # ---- Address Collection ----
        elif status == "get_address":
            from firebase import classify_indian_address
            address = classify_indian_address(message.lower())
            address_type = address.get("Type") or address.get("type")
            
            if address_type == "address":
                user_ref.update({
                    "address": encrypt_data(message),
                    "status": user_data.get("last_state", "active"),
                    "last_message": message,
                    "updated_at": datetime.now(timezone.utc)
                })
                result = await rag.invoke_translation(
                    text="✅ Address saved! You may now continue with your order.",
                    target_language=launguage
                )
                return result
            else:
                reason = await rag.invoke(message, launguage=launguage)
                follow_up = await rag.invoke_translation(
                    text="\n\nPlease provide a valid delivery address 📍",
                    target_language=launguage
                )
                return reason + follow_up

        # ---- Order Type Selection ----
        elif status == "get_order_type":
            if message.lower() in ["delivery", "pickup"]:
                cart_session = user_data.get("cart_session", {"items": []})
                cart_session["Type"] = message.title()
                user_ref.update({"status": "order", "cart_session": cart_session})
                
                result = await rag.invoke_translation(
                    text=(
                        "Great! What would you like to order?\n\n"
                        "💡 You can order multiple items at once!\n"
                        "Example: 'I want a blue t-shirt size M and black jeans size 32'\n\n"
                        "Type 'exit' when done ordering."
                    ),
                    target_language=launguage
                )
                result = result + "\n\nHere is our Catalog:\n" + give_catalog()
                return result
            else:
                result = await rag.invoke_translation(
                    text="Please choose 'Delivery' or 'Pickup'. Type 'help' for assistance. 🙂",
                    target_language=launguage
                )
                return result

        elif status == "instructions_for_order":
            cart_session = user_data.get("cart_session", {"items": []})
            cart_session["instructions"] = message.strip()
            user_ref.update({
                "cart_session": cart_session,
                "status": "confirm_order",
                "last_message": encrypt_data(message)
            })
            result = await rag.invoke_translation(
                text="✅ Instructions saved!\nConfirm your order by typing 'yes' or 'no' to cancel.",
                target_language=launguage
            )
            return result

        # ---- Order Flow (Regular Items) ----
        elif status == "order":
            if message.lower() in ["done", "checkout", "finish", "confirm", "exit"]:
                cart_session = user_data.get("cart_session", {})
                items = cart_session.get("items", [])
                
                if not items:
                    user_ref.update({"status": "active", "last_message": encrypt_data(message)})
                    result = await rag.invoke_translation(
                        text="Your cart is empty! Add items first by typing 'order' 🛒",
                        target_language=launguage
                    )
                    return result
                
                # Check name/address
                has_name = user_data.get("name")
                has_address = user_data.get("address")
                
                if not has_name:
                    user_ref.update({
                        "status": "collect_name",
                        "last_message": encrypt_data(message)
                    })
                    result = await rag.invoke_translation(
                        text="Before checkout, what's your name? 😊",
                        target_language=launguage
                    )
                    return result
                elif not has_address:
                    user_ref.update({
                        "status": "collect_address",
                        "last_message": encrypt_data(message)
                    })
                    result = await rag.invoke_translation(
                        text="Where should we deliver? 📍",
                        target_language=launguage
                    )
                    return result
                else:
                    # Show summary
                    total = sum(item.get("price", 0) * item.get("quantity", 1) for item in items)
                    
                    summary = "🛒 *Order Summary:*\n\n"
                    for item in items:
                        item_name = item.get("item_name")
                        size = item.get("size", "")
                        color = item.get("color", "")
                        quantity = item.get("quantity", 1)
                        price = item.get("price", 0)
                        item_total = price * quantity
                        
                        summary += f"• {item_name}"
                        if size:
                            summary += f" ({size})"
                        if color:
                            summary += f" - {color}"
                        summary += f" x{quantity} - ₹{item_total}\n"
                    
                    summary += f"\n💰 *Total: ₹{total}*\n\n"
                    summary += "Any special instructions for your order? 😊"
                    
                    user_ref.update({
                        "status": "instructions_for_order",
                        "last_message": encrypt_data(message)
                    })
                    
                    result = await rag.invoke_translation(text=summary, target_language=launguage)
                    return result
            
            # Process items
            try:
                separators = [' and ', ',', ' & ', ' with ', '\n']
                item_texts = [message]
                
                for sep in separators:
                    new_items = []
                    for item in item_texts:
                        new_items.extend([x.strip() for x in item.split(sep)])
                    item_texts = new_items
                
                item_texts = [item for item in item_texts if item and len(item.strip()) > 2]
                
                added = []
                failed = []
                
                for item_text in item_texts:
                    try:
                        result_dict = await rag.invoke_for_Cloth(item_text)
                        
                        if result_dict and result_dict.get("status") is True:
                            added.append({
                                "type": "regular",
                                "item_name": result_dict.get("item_name"),
                                "size": result_dict.get("size", ""),
                                "color": result_dict.get("color", ""),
                                "price": result_dict.get("price", 0),
                                "quantity": result_dict.get("quantity", 1)
                            })
                        else:
                            failed.append((item_text, result_dict.get("reason", "Not found")))
                    except:
                        failed.append((item_text, "Error processing"))
                
                if added:
                    cart_session = user_data.get("cart_session", {"items": []})
                    cart_session["items"].extend(added)
                    
                    user_ref.update({
                        "cart_session": cart_session,
                        "last_message": encrypt_data(message)
                    })
                    
                    response = "✅ *Added to cart:*\n\n"
                    for item in added:
                        response += f"• {item['item_name']}"
                        if item['size']:
                            response += f" ({item['size']})"
                        if item['color']:
                            response += f" - {item['color']}"
                        response += f" x{item['quantity']} - ₹{item['price'] * item['quantity']}\n"
                    
                    cart_total = sum(i['price'] * i['quantity'] for i in cart_session['items'])
                    response += f"\n🛒 Cart Total: ₹{cart_total}\n\n"
                    
                    if failed:
                        response += "\n⚠️ Couldn't add:\n"
                        for item_text, reason in failed:
                            response += f"• {item_text}: {reason}\n"
                    
                    response += "\nAdd more or type 'done' to checkout! 😊"
                    result = await rag.invoke_translation(text=response, target_language=launguage)
                    return result
                else:
                    response = "⚠️ Couldn't find those items.\n\n"
                    for item_text, reason in failed:
                        response += f"• {item_text}: {reason}\n"
                    response += "\nCheck the catalog or try different names! 😊"
                    result = await rag.invoke_translation(text=response, target_language=launguage)
                    return result
                    
            except Exception as e:
                logger.log_error("order_items_processing", e)
                result = await rag.invoke_translation(
                    text="Oops, something went wrong 😅 Try again?",
                    target_language=launguage
                )
                return result

        # ---- Order Confirmation ----
        elif status == "confirm_order":
            if message.lower() in ["yes", "confirm", "place order", "ok", "sure", "done"]:
                cart_session = user_data.get("cart_session", {})
                items = cart_session.get("items", [])
                
                if not items:
                    user_ref.update({"status": "active", "last_message": encrypt_data(message)})
                    return "❌ No items to confirm."
                
                total = sum(item.get("price", 0) * item.get("quantity", 1) for item in items)
                
                order_ref = user_ref.collection("orders").document()
                
                order_data = {
                    "status": "confirmed",
                    "timestamp": datetime.now(timezone.utc),
                    "total": total,
                    "type": cart_session.get("Type", "Not Specified"),
                    "instructions": cart_session.get("instructions", None),
                    "items": [
                        {
                            "type": "regular",
                            "item_name": item.get("item_name"),
                            "size": item.get("size", ""),
                            "color": item.get("color", ""),
                            "quantity": item.get("quantity", 1),
                            "price": item.get("price", 0)
                        }
                        for item in items
                    ]
                }
                
                order_ref.set(order_data)
                user_ref.update({"last_order_id": order_ref.id})
                
                # Clear cart and reset status
                user_ref.update({
                    "status": "active",
                    "cart_session": firestore.DELETE_FIELD,
                    "last_order_date": datetime.now(timezone.utc),
                    "last_message": encrypt_data(message),
                    "Type": firestore.DELETE_FIELD
                })
                
                result = await rag.invoke_translation(
                    text=(
                        "🎉 *Order Confirmed!*\n\n"
                        "We'll process your order shortly 🛍️\n\n"
                        "Thank you for shopping with us! 💙"
                    ),
                    target_language=launguage
                )
                return result
                
            elif message.lower() in ["no", "cancel", "nope"]:
                user_ref.update({
                    "status": "active",
                    "cart_session": firestore.DELETE_FIELD,
                    "last_message": encrypt_data(message)
                })
                
                result = await rag.invoke_translation(
                    text="❌ Order cancelled. Type 'order' to start fresh! 😊",
                    target_language=launguage
                )
                return result
            else:
                result = await rag.invoke_translation(
                    text="Type 'yes' to confirm or 'no' to cancel 😊",
                    target_language=launguage
                )
                return result

        # ---- Feedback Collection ----
        elif status == "ask_feedback":
            feedback_data = extract_feedback(message)
            rating = feedback_data["rating"]
            reason = feedback_data["reason"]

            if not rating:
                result = await rag.invoke_translation(
                    text="Please rate us 1-5 (e.g., '4 - great quality clothes').",
                    target_language=launguage
                )
                return result

            user_ref.update({
                "feedback": {
                    "rating": encrypt_data(str(rating)),
                    "reason": encrypt_data(reason) if reason else "",
                    "timestamp": datetime.now(timezone.utc)
                },
                "status": "active"
            })

            responses = {
                5: "⭐⭐⭐⭐⭐ Thank you! We're delighted!",
                4: "⭐⭐⭐⭐ Thanks for the great feedback!",
                3: "⭐⭐⭐ Thank you! We'll keep improving!",
                2: "⭐⭐ Sorry we didn't meet expectations. We'll do better!",
                1: "⭐ We sincerely apologize. Please let us know how to improve!"
            }
            
            result = await rag.invoke_translation(
                text=responses.get(rating, "Thank you for your feedback! 🙏"),
                target_language=launguage
            )
            return result

        # ---- Complaint Handling ----
        elif status == "complain":
            user_ref.update({
                "complain": encrypt_data(message),
                "status": "active"
            })
            result = await rag.invoke_translation(
                text="We're sorry to hear that 😔 Your complaint has been noted. We'll address it promptly! 🙏",
                target_language=launguage
            )
            return result

        # ---- Change Name ----
        elif status == "change_name":
            name = extract_name_regex(message)
            if name:
                user_ref.update({
                    "name": encrypt_data(name),
                    "status": "active"
                })
            result = await rag.invoke_translation(
                text="Your name has been updated. Browse our collection now! 👕",
                target_language=launguage
            )
            return result
        
        # ---- Change Language ----
        elif status == "change_launguage":
            launguage_ = extract_language(message)
            if launguage_:
                user_ref.update({
                    "launguage": encrypt_data(launguage_),
                    "updated_at": datetime.now(timezone.utc),
                    "status": "active"
                })
            result = await rag.invoke_translation(
                text="Language changed! Start shopping by typing 'order'",
                target_language=launguage_
            )
            return result

        # ---- Update Address ----
        elif status == "get_new_address":
            from firebase import classify_indian_address
            address = classify_indian_address(message.lower())
            
            if address.get("Type") == "address" or address.get("type") == "address":
                user_ref.update({
                    "address": encrypt_data(message),
                    "status": "active",
                    "updated_at": datetime.now(timezone.utc)
                })
                result = await rag.invoke_translation(
                    text="✅ Address updated successfully!",
                    target_language=launguage
                )
                return result
            else:
                result = await rag.invoke_translation(
                    text="Sorry I don't get it. 😓",
                    target_language=launguage
                )
                return result
        else:
            result = await rag.invoke(message, launguage)
            return result
    except Exception as e:
        logger.log_error("handle_user_message_cloth_store. handle_all_things.py", e)
        try:
            launguage = decrypt_data(user_data.get("launguage", "English")) if 'user_data' in locals() else "English"
            result = await rag.invoke_translation(
                text="😔 Oops! Something went wrong. Try again or type 'refresh'.",
                target_language=launguage
            )
            return result
        except:
            return "😔 Oops! Something went wrong. Try again or type 'refresh'."
# Helper functions (keep these as-is)
import re

def extract_name_regex(text):
    """
    Extracts probable personal names, nicknames, titles, or handles from text using regex.
    Handles patterns like:
    - "My name is John Doe"
    - "I am A.J. Smith"
    - "This is José O'Neill"
    - "Call me Marie-Claire"
    - "I'm Mr. Patel"
    - "You can call me Nap"
    - "I go by @napster_92"
    - "People call me Chief"
    - "I'm the Designer"
    - "Nap Patel" (standalone)
    """

    try:
        text = text.strip()

        # Normalize whitespace and punctuation spacing
        text = re.sub(r'\s+', ' ', text)

        # Allow for accented letters, apostrophes, hyphens, initials, dots
        name_core = r"[A-ZÀ-ÖØ-öø-ÿ][a-zA-ZÀ-ÖØ-öø-ÿ'’\.-]+(?:\s+[A-ZÀ-ÖØ-öø-ÿ][a-zA-ZÀ-ÖØ-öø-ÿ'’\.-]+){0,3}"

        patterns = [
            # Explicit introductions
            rf"(?i)(?:\bmy name is\b|\bi am\b|\bi'm\b|\bthis is\b|\bcall me\b|\bpeople call me\b|\byou can call me\b)\s+(?:mr\.|mrs\.|ms\.|dr\.)?\s*({name_core})",
            # Titles + name
            rf"(?i)\bi[' ]?m\s+(?:mr\.|mrs\.|ms\.|dr\.)\s*({name_core})",
            # Online handles
            rf"(?i)(?:\bi go by\b|\bi'm known as\b|\bknown as\b)\s*([@]?[A-Za-z0-9_.\-]+)",
            # Roles or identifiers
            rf"(?i)\bi[' ]?m\s+the\s+([A-Za-zÀ-ÖØ-öø-ÿ'’\.-]+)",
            # Bare names at the start or entire input ("Nap Patel" or "Nap")
            rf"(?i)^(?:mr\.|mrs\.|ms\.|dr\.)?\s*({name_core})$",
            # Catch loose name fragments at end ("Your, name: nap patel")
            rf"(?i)(?:name[:\s]*)({name_core})$"
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                name = match.group(1).strip()

                # Reject obvious junk or short words
                bad_words = {
                    'hello','hi','hey','what','where','when','how','why',
                    'the','this','that','thanks','thank','please','man','bro','dude','am'
                }
                if name.lower() in bad_words or len(name) < 2:
                    continue

                # Handles: leave as-is
                if name.startswith('@') or re.match(r'^[A-Za-z0-9_.-]+$', name):
                    return name

                # Roles / "The Something"
                if re.match(r'(?i)^the\s+[A-Za-zÀ-ÖØ-öø-ÿ\'’\.-]+$', name):
                    return name.title()

                # Normal names
                return name.title()

        return None

    except Exception as e:
        print("Error in extract_name_regex:", e)
        return None


from typing import Dict, Any
def parse_flavours(text: str) -> Dict[str, Any]:
    
    # Phrases that are almost certainly headers, descriptions, or non-product items.
    EXCLUDE_PHRASES = [
        "What We Offer", "Fresh Cakes", "Standard Prices", "Theme Cakes",
        "Buns", "Snacks", "Desserts", "each", "extra", "Free", 
        "Fondant decorations", "Photo printing", "Midnight delivery", 
        "AM", "PM", "500g", "1kg", "2kg", "3kg", "pcs", 
        "Weight Options", "Flavour Prices", "Custom Cake Info", "Delivery Details"
    ]
    
    # --- UNIVERSAL PATTERN ---
    # This pattern is highly flexible and replaces the three-stage logic.
    # 
    # 1. ([\w\s\/()]+?)        -> Name: Captures one or more words/spaces/slashes non-greedily.
    # 2. \s*[\–\-,:\/]\s* -> Separator: Matches 0+ spaces, followed by a dash, comma, colon, or slash, 
    #                            followed by 0+ spaces. Handles: " - ", "-", ":", ", "
    # 3. [\₹\$\£]?\s*(\d{2,}(?:,\d{3})*) -> Price: Optional currency symbol, 0+ spaces, then 
    #                                      captures the price (Group 2), requiring at least two digits.
    # 4. (?:[^\w]|$).*?         -> Trailer: Non-capturing group to match up to the end of the entry, 
    #                              preventing the next product's name from being consumed.
    
    universal_pattern = re.compile(
        r'([\w\s\/()]+?)\s*[\–\-,:\/]\s*[\₹\$\£]?\s*(\d{2,}(?:,\d{3})*)(?:[^\w]|$).*?', 
        re.IGNORECASE | re.MULTILINE
    )

    matches = universal_pattern.findall(text)
    result = {}
    
    for name, price_str in matches:
        
        # --- Pre-processing Cleanup ---
        cleaned_name = name.strip().replace('\n', ' ')
        
        # Remove common pricing/weight identifiers like (500g), (6 pcs)
        cleaned_name = re.sub(r'\s*\([^)]*\)', '', cleaned_name).strip() 
        
        # Remove trailing characters like '/' or ':' left over from the regex capture
        cleaned_name = re.sub(r'[\s\/]+$', '', cleaned_name).strip()
        
        # Remove a numeric prefix (like '850 ') if it appears at the start of the name 
        # (Needed to handle residual numbers from previous lines)
        cleaned_name = re.sub(r'^\d+\s*[\.\/]?\s*', '', cleaned_name).strip()
        
        try:
            # Ensure price is a clean integer
            cleaned_price = int(price_str.replace(',', ''))
        except ValueError:
            cleaned_price = None

        if cleaned_name and cleaned_price is not None:
            is_excluded = False
            
            # --- Exclusion Check ---
            for phrase in EXCLUDE_PHRASES:
                # Check if the name IS the excluded phrase or STARTS with it
                if cleaned_name.lower() == phrase.lower() or cleaned_name.lower().startswith(phrase.lower()):
                    is_excluded = True
                    break
            
            if not is_excluded:
                # Retain the size filter to skip short, uninformative labels like 'to' or 'a'
                # We enforce that a name must be reasonably long or contain multiple words
                if len(cleaned_name.split()) >= 1 and len(cleaned_name) > 3:
                    # Final check: skip names that are purely numeric 
                    if not cleaned_name.replace(' ', '').isdigit():
                        result[cleaned_name] = cleaned_price
            
    return result

def extract_feedback(feedback):
    """
    Extracts rating (1-5) and reason from user feedback with comprehensive validation.
    
    Features:
    - Input validation & sanitization
    - Multiple rating formats (1-5, 1/5, 1 stars, ⭐⭐⭐, etc.)
    - Flexible reason extraction with 15+ keyword triggers
    - Length limits to prevent DOS attacks
    - Type coercion for non-string inputs
    - Always returns valid dict (never None)
    
    Args:
        feedback: User feedback text (str, int, or None)
        
    Returns:
        dict: {'rating': int|None, 'reason': str|None}
    """
    import re
    from typing import Dict, Optional
    
    # Default return - always valid dict
    default_result = {'rating': None, 'reason': None}
    
    try:
        # === INPUT VALIDATION ===
        if not feedback:
            return default_result
        
        # Type coercion - handle non-string inputs
        if not isinstance(feedback, str):
            feedback = str(feedback)
        
        # Sanitize - remove control characters & normalize whitespace
        feedback = ' '.join(feedback.split())
        feedback = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', feedback)
        
        # DOS prevention - limit input length
        MAX_LENGTH = 2000
        if len(feedback) > MAX_LENGTH:
            feedback = feedback[:MAX_LENGTH]
        
        # === RATING EXTRACTION (Multiple Formats) ===
        rating_patterns = [
            r'(?<!\d)([1-5])\s*(?:/|out\s+of)\s*5(?!\d)',      # "4/5" or "4 out of 5"
            r'(?<!\d)([1-5])\s*stars?(?!\d)',                   # "4 stars"
            r'(?:rating|rate|score)[\s:]*([1-5])(?!\d)',        # "rating: 4"
            r'([⭐★✨]{1,5})',                                    # "⭐⭐⭐⭐" (emoji stars)
            r'(?<!\d)([1-5])(?!\d)'                             # Standalone "4"
        ]
        
        rating = None
        rating_end_pos = 0
        
        # Try patterns in order of specificity
        for pattern in rating_patterns:
            match = re.search(pattern, feedback, re.IGNORECASE)
            if match:
                matched_value = match.group(1)
                
                # Handle emoji stars (count them)
                if matched_value[0] in '⭐★✨':
                    rating = min(len(matched_value), 5)
                else:
                    rating = int(matched_value)
                
                # Validate range
                if 1 <= rating <= 5:
                    rating_end_pos = match.end()
                    break
                else:
                    rating = None
        
        # No valid rating found
        if rating is None:
            return default_result
        
        # === REASON EXTRACTION ===
        post_rating = feedback[rating_end_pos:].strip()
        
        if not post_rating:
            return {'rating': rating, 'reason': None}
        
        # Reason trigger keywords/punctuation
        reason_keywords = [
            'because', 'as', 'since', 'cause', 'cuz', 'coz',
            'for', 'due to', 'owing to',
            'so', 'that', 'reason', 'why',
            '-', '–', '—', ':'
        ]
        
        # Build pattern from keywords
        keyword_pattern = '|'.join(re.escape(kw) for kw in reason_keywords)
        split_pattern = rf'\b(?:{keyword_pattern})\b'
        
        # Split on reason keywords
        parts = re.split(split_pattern, post_rating, maxsplit=1, flags=re.IGNORECASE)
        
        reason = None
        if len(parts) > 1:
            # Found keyword - extract text after it
            reason = parts[-1].strip()
        elif len(post_rating.strip(' .,!?;:')) > 3:
            # No keyword but meaningful text exists
            reason = post_rating
        
        # Clean reason
        if reason:
            reason = re.sub(r'^[^\w\s]+', '', reason)  # Remove leading punctuation
            reason = re.sub(r'[^\w\s]+$', '', reason)  # Remove trailing punctuation
            reason = ' '.join(reason.split())           # Normalize whitespace
            
            # Validate length
            if len(reason) < 2:
                reason = None
            elif len(reason) > 500:
                # Truncate at word boundary
                reason = reason[:500].rsplit(' ', 1)[0] + '...'
        
        return {'rating': rating, 'reason': reason}
    
    except ValueError as e:
        logger.log_error("extract_feedback.ValueError", f"{e}")
        return default_result
    
    except re.error as e:
        logger.log_error("extract_feedback.RegexError", f"{e}")
        return default_result
    
    except Exception as e:
        logger.log_error("extract_feedback.handle_all_things.py", f"{type(e).__name__}: {e}")
        return default_result

pattern = r'(english|इंग्लिश|hindi|हिंदी|hinglish|गुजराती|gujarati|मराठी|marathi|தமிழ்|tamil|తెలుగు|telugu|ಕನ್ನಡ|kannada|বাংলা|bengali|ਪੰਜਾਬੀ|punjabi|اردو|urdu|odia|ଓଡିଆ|malayalam|മലയാളം)'

lang_map = {
    "english": "English", "इंग्लिश": "English",
    "hindi": "Hindi", "हिंदी": "Hindi",
    "hinglish": "Hinglish",
    "gujarati": "Gujarati", "गुजराती": "Gujarati",
    "marathi": "Marathi", "मराठी": "Marathi",
    "tamil": "Tamil", "தமிழ்": "Tamil",
    "telugu": "Telugu", "తెలుగు": "Telugu",
    "kannada": "Kannada", "ಕನ್ನಡ": "Kannada",
    "bengali": "Bengali", "বাংলা": "Bengali",
    "punjabi": "Punjabi", "ਪੰਜਾਬੀ": "Punjabi",
    "urdu": "Urdu", "اردو": "Urdu",
    "odia": "Odia", "ଓଡିଆ": "Odia",
    "malayalam": "Malayalam", "മലയാളം": "Malayalam",
}

def extract_language(text):
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    key = match.group(1).lower()
    return lang_map.get(key)

if __name__ == "__main__":

    text ="""
✅ SWEETCRUST BAKERY INFORMATION (WITH PRICES)

Bakery Name: SweetCrust Bakery
Location: Near City Center Mall, Opp. Lotus Residency, Ahmedabad
Timings: 8:00 AM – 10:00 PM (Mon–Sun)
Contact: +91 98765 43210
Delivery: Available within 5 km
Pre-orders: 4–24 hours depending on cake design

🍰 What We Offer
Fresh Cakes (Standard Prices)

Black Forest – ₹450 (500g) / ₹850 (1kg)

Chocolate Truffle – ₹500 (500g) / ₹950 (1kg)

Red Velvet – ₹600 (500g) / ₹1100 (1kg)

Pineapple – ₹400 (500g) / ₹750 (1kg)

Butterscotch – ₹450 (500g) / ₹850 (1kg)

Blueberry – ₹550 (500g) / ₹1050 (1kg)

Photo Cake – Starting ₹900 (1kg)

Theme Cakes – ₹1200–₹3000/kg (design-based)

Breads & Buns

Brown Bread – ₹45

Garlic Bread – ₹80

Pav (6 pcs) – ₹30

Burger Buns (4 pcs) – ₹40

Sandwich Bread – ₹50

Snacks

Veg Puff – ₹25

Paneer Puff – ₹35

Pizza Slice – ₹60

Garlic Rolls – ₹50

Cheese Sticks – ₹40

Desserts

Brownies – ₹50–₹70 each

Pastries – ₹45–₹70 each

Cupcakes – ₹40–₹60 each

Donuts – ₹50 each

Fruit Tart – ₹70 each

🎂 Custom Cake Info

Weight Options:

500g, 1kg, 2kg, 3kg+

Flavour Prices (per 500g / 1kg):

Chocolate – ₹500

Red Velvet – ₹600

Vanilla – ₹350

Blueberry – ₹550 /

Butterscotch – ₹450

Mocha – ₹550 / ₹1000

Extras:

Message on cake – Free

Fondant decorations – ₹150–₹500 extra

Photo printing – ₹150 extra

Midnight delivery – ₹150–₹250 extra

Advance Booking:
12–24 hours recommended

🛵 Delivery Details

Delivery charges: ₹20–₹60 (depending on distance)

Free delivery above ₹800

Packaging included

Live order tracking for large orders

⭐ Why Customers Choose Us

Daily fresh stock

100% eggless options

Premium cream & real fruit puree

On-time delivery

Expert custom cake artists
"""
    tests = [
    "Chocolate-500, Red Velvet-233, Vanilla-674",
    "Flavours:\nBlueberry-550\nMocha-555\nButterscotch-676",
    "  Chocolate  -  500 | Red Velvet -233 | Vanilla-  674  ",
    "Some random text... Mocha-555 blah blah Chocolate-500 end.",
    "Butterscotch:676, Blueberry:550",  # also handles colon format
    ]

    print(parse_flavours(text))

    for i, t in enumerate(tests, start=1):
        print(f"Test {i}:")
        print(parse_flavours(t))
        print("-" * 40)
        print(parse_flavours("Flavours: Chocolate-500, Red Velvet-233, Vanilla-674, Blueberry-550, Butterscotch-676, Mocha-555"))