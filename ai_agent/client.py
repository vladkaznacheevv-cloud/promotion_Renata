import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class AIClient:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.assistant_name = os.getenv("AI_ASSISTANT_NAME", "Mimo")
        self.system_prompt = os.getenv(
            "AI_PERSONALITY",
            "Ты дружелюбный ассистент проекта Renata Promotion. "
            "Отвечай кратко, по делу и вежливо."
        )
    
    async def get_response(self, user_message: str, chat_history: list = None) -> str:
        """Получить ответ от AI"""
        messages = [{"role": "system", "content": self.system_prompt}]
        
        if chat_history:
            messages.extend(chat_history[-10:])
        
        messages.append({"role": "user", "content": user_message})
        
        try:
            response = self.client.chat.completions.create(
                model="mimo-v2-flash",
                messages=messages,
                max_tokens=1000,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"❌ Ошибка AI: {str(e)}"

ai_client = AIClient()