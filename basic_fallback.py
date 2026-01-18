from encryption_utils import get_logger

logger = get_logger()

def chatbot_response(user_input):
    try:
        user_input = user_input.lower().strip()

        # Greetings
        if user_input in ["hi", "hello", "hey", "yo", "hiya"]:
            return "Hello! How are you today?"
        elif user_input in ["good morning", "morning"]:
            return "Good morning! Did you sleep well?"
        elif user_input in ["good afternoon", "afternoon"]:
            return "Good afternoon! How's your day going?"
        elif user_input in ["good evening", "evening"]:
            return "Good evening! How was your day?"
        elif user_input in ["good night", "night"]:
            return "Good night! Sleep tight and have sweet dreams!"

        # Asking about the bot
        elif user_input in ["how are you", "how's it going", "how do you do"]:
            return "I'm just a bot, but I'm feeling great! How about you?"
        elif user_input in ["what is your name", "who are you", "tell me your name"]:
            return "I'm ChatPy, your friendly Python chatbot!"
        elif user_input in ["how old are you", "age"]:
            return "I'm timeless! I exist as long as this code runs."

        # Farewells
        elif user_input in ["bye", "goodbye", "see you", "later", "catch you later"]:
            return "Goodbye! Take care and have a wonderful day."
        elif user_input in ["see you soon", "talk later"]:
            return "Sure! I'll be here whenever you want to chat."

        # Asking for help
        elif user_input in ["help", "what can you do", "assist me"]:
            return ("I can chat with you, tell jokes, motivate you, "
                    "or just keep you company. Try saying 'joke' or 'motivate me'!")

        # Feelings
        elif user_input in ["i am fine", "i'm fine", "good", "doing well"]:
            return "That's great! What are you up to today?"
        elif user_input in ["not good", "sad", "bad", "angry", "tired"]:
            return "I'm sorry to hear that. Do you want to talk about it?"
        elif user_input in ["happy", "excited", "awesome"]:
            return "That's wonderful! Keep that positive energy going!"

        # Hobbies
        elif user_input in ["what are your hobbies", "hobbies"]:
            return "I enjoy chatting with people and learning from our conversations!"
        elif "i like" in user_input:
            return "That's cool! It's great to have hobbies you enjoy."
        elif "i love" in user_input:
            return "Love makes life colorful! I'm glad you have something you love."

        # Work / Study
        elif "i am studying" in user_input or "i study" in user_input:
            return "Studying is important! Keep up the hard work."
        elif "i am working" in user_input or "i work" in user_input:
            return "Work keeps us busy! Make sure to take breaks when needed."
        elif "i am tired" in user_input:
            return "Rest is important. Don't overwork yourself."

        # Weather / Time / Date
        elif "weather" in user_input:
            return "I can't check the weather, but I hope it's nice where you are!"
        elif "time" in user_input:
            return "I don't have a clock, but you can check your device for the current time."
        elif "date" in user_input or "day" in user_input:
            return "I can't see the calendar, but I hope you're having a great day today!"

        # Location
        elif "where are you" in user_input or "your location" in user_input:
            return "I exist wherever you run this code! I'm everywhere and nowhere."
        elif "where am i" in user_input:
            return "I can't see your location, but I hope you're somewhere nice!"

        # Motivation
        elif "motivate me" in user_input or "inspire me" in user_input:
            return "Keep going! Every step you take brings you closer to your goals."
        elif "i feel like giving up" in user_input:
            return "Don't give up! Tough times make you stronger and smarter."

        # Jokes / Fun
        elif "joke" in user_input or "funny" in user_input:
            return "Why did the computer go to the doctor? Because it caught a virus!"
        elif "tell me something funny" in user_input:
            return "I would tell you a UDP joke, but you might not get it."

        # Simple Math / Logic
        elif "add" in user_input or "sum" in user_input:
            return "I can't calculate exact numbers without more context, but I can chat!"
        elif "subtract" in user_input or "minus" in user_input:
            return "I could guide you step by step if you want!"

        # Generic responses for greetings/questions with keywords
        elif "hi" in user_input or "hello" in user_input:
            return "Hello there! How's your day?"
        elif "thank you" in user_input or "thanks" in user_input:
            return "You're welcome! I'm happy to help."
        elif "sorry" in user_input:
            return "No worries! Everything is okay."

        # Encouragement
        elif "i am stressed" in user_input or "stressed" in user_input:
            return "Take a deep breath. Everything will be alright, one step at a time."
        elif "i am anxious" in user_input or "anxious" in user_input:
            return "It's okay to feel anxious. Try to focus on what you can control."

        # Compliments
        elif "you are smart" in user_input or "you are clever" in user_input:
            return "Thank you! I try my best to help you."
        elif "you are funny" in user_input:
            return "Thanks! I like making people smile."

        # Questions about life
        elif "meaning of life" in user_input:
            return "Some say 42, but for humans, the meaning is what you make of it!"
        elif "advice" in user_input:
            return "Always keep learning and take care of yourself along the way."

        # Catch-all responses
        else:
            return "Sorry, I didn't quite understand that. Can you try asking differently?"
    
    except Exception as e:
        logger.log_error("chatbot_response. basic_fallback.py", e)