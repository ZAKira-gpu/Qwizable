from sqlalchemy.ext.asyncio import AsyncSession
from app.services.document_service import extract_text_from_file, chunk_text
from app.services.quiz_generation_service import generate_quiz_from_chunk, merge_and_deduplicate_quizzes
from app.models.quiz import Quiz, Question
from app.models.task import BackgroundTask
from app.models.usage import Usage
from app.models.result import Result
from sqlalchemy import select, func
from datetime import datetime
import asyncio
from typing import Optional
from app.core.logger import logger

async def get_smart_difficulty(db: AsyncSession, user_id: int, requested_difficulty: str) -> str:
    if requested_difficulty != "auto":
        return requested_difficulty
        
    query = select(func.avg(Result.score)).where(Result.user_id == user_id)
    avg_score = await db.scalar(query)
    
    if avg_score is None:
        return "medium"
    if avg_score > 85:
        return "hard"
    if avg_score < 50:
        return "easy"
    return "medium"

async def process_document_and_generate_quiz(
    db: AsyncSession, 
    task_id: int, 
    user_id: int, 
    file_bytes: bytes, 
    filename: str, 
    difficulty: str, 
    num_questions: int,
    thread_id: Optional[str] = None,
    instructions: Optional[str] = None,
    start_page: Optional[int] = None,
    end_page: Optional[int] = None
):
    task = await db.get(BackgroundTask, task_id)
    if not task: return
    
    task.status = "processing"
    await db.commit()
    
    try:
        full_text = await extract_text_from_file(file_bytes, filename, start_page, end_page)
        if not full_text:
            raise ValueError("No text could be extracted from the document bounds.")
            
        chunks = chunk_text(full_text, max_tokens=800)
        chunks = sorted(chunks, key=lambda c: len(set(c.split())), reverse=True)[:10]
        
        actual_diff = await get_smart_difficulty(db, user_id, difficulty)
        
        # Build Thread Context
        past_questions_context = ""
        if thread_id:
            query = select(Question).join(Quiz).where(Quiz.thread_id == thread_id).where(Quiz.user_id == user_id)
            result = await db.execute(query)
            past_qs = [q.question_text for q in result.scalars().all()]
            if past_qs:
                past_questions_context = "PREVIOUS THREAD QUESTIONS (Do not duplicate these):\n" + "\n".join(f"- {q}" for q in past_qs)
        
        questions_per_chunk = max(1, (num_questions // len(chunks)) + 1)
        tasks = [generate_quiz_from_chunk(chunk, actual_diff, questions_per_chunk, instructions, past_questions_context) for chunk in chunks]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_questions = []
        failed_chunks = 0
        for res in results:
            if isinstance(res, Exception):
                logger.warning(f"Chunk generation partial failure: {res}")
                failed_chunks += 1
            else:
                all_questions.extend(res)
                
        if failed_chunks == len(chunks):
            raise ValueError("All AI chunk executions failed. Cannot generate quiz.")
            
        final_questions = await merge_and_deduplicate_quizzes(all_questions, num_questions)
        if not final_questions:
            raise ValueError("Failed to aggregate valid deductive quiz data from the document.")
            
        new_quiz = Quiz(user_id=user_id, topic=f"Generated from {filename}", difficulty=actual_diff, thread_id=thread_id)
        db.add(new_quiz)
        await db.commit()
        await db.refresh(new_quiz)
        
        for q in final_questions:
            options_dict = q.get("options", {})
            if isinstance(options_dict, list):
                options_dict = {chr(65+i): opt for i, opt in enumerate(options_dict)}
                
            question = Question(
                quiz_id=new_quiz.id,
                question_text=q.get("question", "Unknown"),
                options=options_dict,
                correct_answer=q.get("correct_answer", "A")
            )
            db.add(question)
            
        usage = await db.scalar(select(Usage).where(Usage.user_id == user_id).order_by(Usage.created_at.desc()))
        if usage:
            usage.tokens_used += sum([len(c) for c in chunks]) // 4
            
        task.status = "completed"
        if failed_chunks > 0:
            task.error_message = f"Warning: {failed_chunks}/{len(chunks)} chunks dropped to API failure. Degraded completion."
            
        task.updated_at = datetime.utcnow()
        await db.commit()
        logger.info(f"Document Quiz {new_quiz.id} generated natively in thread {thread_id}.")
        
    except Exception as e:
        logger.error(f"Document AI Pipeline Failed: {str(e)}")
        task = await db.get(BackgroundTask, task_id)
        if task:
            task.status = "failed"
            task.error_message = str(e)
            task.updated_at = datetime.utcnow()
            await db.commit()
