import logging
from typing import List, Optional
from openai import OpenAI
from core.ai.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

class AIService:
    """Сервис AI-ассистента Mimo"""
    
    def __init__(self, api_key: str = None, model: str = "mimo-v2-flash"):
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.model = model
        self.system_prompt = SYSTEM_PROMPT
    
    async def get_response(
        self, 
        user_message: str, 
        history: List[dict] = None,
        max_tokens: int = 1024,
        temperature: float = 0.3
    ) -> str:
        """Получить ответ от AI"""
        if not self.client:
            return "AI не настроен. Обратитесь к администратору."
        
        messages = [{"role": "system", "content": self.system_prompt}]
        
        if history:
            messages.extend(history[-10:])
        
        messages.append({"role": "user", "content": user_message})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_completion_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"AI error: {e}")
            return "Извините, произошла ошибка. Попробуйте позже."
    
    async def chat(self, user_message: str, chat_history: List[dict] = None) -> tuple[str, List[dict]]:
        """Полный цикл чата с историей"""
        response = await self.get_response(user_message, chat_history)
        
        # Обновляем историю
        new_history = chat_history or []
        new_history.extend([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": response}
        ])
        
        return response, new_history