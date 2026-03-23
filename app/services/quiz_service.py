import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.ai_service import call_novita_api
from app.core.logger import logger
from app.models.quiz import Quiz, Question
from app.models.usage import Usage
from sqlalchemy import select

async def generate_quiz_task(db: AsyncSession, user_id: int, topic: str, difficulty: str, num_questions: int):
    # Async wrapper meant to be easily transitioned to Celery worker later
    logger.info(f"Starting async quiz generation for topic: {topic}")
    
    prompt = f"Generate {num_questions} multiple choice questions about {topic} at {difficulty} difficulty. Output strict JSON format: [{{\"question_text\": \"...\", \"options\": {{\"A\": \"...\", \"B\": \"...\", \"C\": \"...\", \"D\": \"...\"}}, \"correct_answer\": \"A\"}}]"
    
    response = await call_novita_api(prompt)
    if not response:
        logger.error("AI call failed. Quiz generation aborted.")
        return
        
    try:
        data = json.loads(response)
        
        new_quiz = Quiz(user_id=user_id, topic=topic, difficulty=difficulty)
        db.add(new_quiz)
        await db.commit()
        await db.refresh(new_quiz)
        
        for q in data:
            question = Question(
                quiz_id=new_quiz.id,
                question_text=q["question_text"],
                options=q["options"],
                correct_answer=q["correct_answer"]
            )
            db.add(question)
            
        usage = await db.scalar(select(Usage).where(Usage.user_id == user_id).order_by(Usage.created_at.desc()))
        if usage:
            usage.tokens_used += len(response) // 4
            
        await db.commit()
        logger.info(f"Quiz {new_quiz.id} generated successfully")
        
    except json.JSONDecodeError:
        logger.error(f"Failed to parse AI JSON response: {response}")
