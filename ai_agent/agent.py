import openai
from core.models import User
from core.database import async_session

openai.api_key = os.getenv("OPENAI_API_KEY")

class AIAgent:
    async def suggest_response(self, user_id: int, message: str):
        async with async_session() as session:
            user = await session.get(User, user_id)
            if not user:
                return "Пользователь не найден."

        prompt = f"""
        Ты — психологический консультант. Пользователь {user.first_name} написал: "{message}".
        Ответь ему дружелюбно, поддерживающе, но профессионально.
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content