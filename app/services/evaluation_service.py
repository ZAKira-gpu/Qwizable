import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.ai_service import call_novita_api
from app.models.quiz import Question
from app.models.result import Result
from sqlalchemy import select

async def evaluate_answers(db: AsyncSession, quiz_id: int, user_answers_data: list):
    result = await db.execute(select(Question).where(Question.quiz_id == quiz_id))
    questions = result.scalars().all()
    q_dict = {q.id: q for q in questions}
    
    correct_count = 0
    feedback_context = []
    
    for ans in user_answers_data:
        q = q_dict.get(ans.question_id)
        if not q: continue
            
        is_correct = ans.user_answer == q.correct_answer
        if is_correct: correct_count += 1
            
        feedback_context.append({
            "question": q.question_text,
            "user_answer": ans.user_answer,
            "correct_answer": q.correct_answer,
            "is_correct": is_correct
        })
        
    score = (correct_count / len(questions)) * 100 if questions else 0
    prompt = f"Analyze these quiz results and provide weak areas and feedback in strict JSON: {{\"weak_areas\": {{\"topic\": \"reason\"}}, \"feedback\": \"General advice\"}}. Results: {json.dumps(feedback_context)}"
    
    ai_resp = await call_novita_api(prompt)
    weak_areas = {}
    feedback = "Good job."
    if ai_resp:
        try:
            parsed = json.loads(ai_resp)
            weak_areas = parsed.get("weak_areas", {})
            feedback = parsed.get("feedback", "Good job.")
        except json.JSONDecodeError: pass
            
    new_result = Result(quiz_id=quiz_id, score=score, weak_areas=weak_areas, feedback=feedback)
    db.add(new_result)
    await db.commit()
    await db.refresh(new_result)
    
    return new_result
