from sqlalchemy.ext.asyncio import AsyncSession
from app.services.document_service import extract_text_from_file, chunk_text
from app.services.quiz_generation_service import generate_quiz_from_chunk, merge_and_deduplicate_quizzes
from app.models.quiz import Quiz, Question
from app.models.task import BackgroundTask
from app.models.usage import Usage
from sqlalchemy import select
from datetime import datetime
import asyncio
from app.core.logger import logger

async def process_document_and_generate_quiz(
    db: AsyncSession, 
    task_id: int, 
    user_id: int, 
    file_bytes: bytes, 
    filename: str, 
    difficulty: str, 
    num_questions: int
):
    task = await db.get(BackgroundTask, task_id)
    if not task: return
    
    task.status = "processing"
    await db.commit()
    
    try:
        # 1. Pipeline Extract & Clean
        full_text = await extract_text_from_file(file_bytes, filename)
        if not full_text:
            raise ValueError("No text could be extracted from the document.")
            
        # 2. Chunking
        chunks = chunk_text(full_text, max_tokens=800)
        
        # 3. Asynchronously generate quizzes per chunk
        questions_per_chunk = max(1, (num_questions // len(chunks)) + 1)
        
        tasks = [generate_quiz_from_chunk(chunk, difficulty, questions_per_chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks)
        
        all_questions = []
        for res in results:
            all_questions.extend(res)
            
        # 4. Merging
        final_questions = await merge_and_deduplicate_quizzes(all_questions, num_questions)
        if not final_questions:
            raise ValueError("Failed to generate valid quiz data from the document.")
            
        # 5. Database Save
        new_quiz = Quiz(user_id=user_id, topic=f"Generated from {filename}", difficulty=difficulty)
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
            
        # 6. Usage Tracking
        usage = await db.scalar(select(Usage).where(Usage.user_id == user_id).order_by(Usage.created_at.desc()))
        if usage:
            usage.tokens_used += sum([len(c) for c in chunks]) // 4
            
        task.status = "completed"
        task.updated_at = datetime.utcnow()
        await db.commit()
        logger.info(f"Document Quiz {new_quiz.id} generated successfully")
        
    except Exception as e:
        logger.error(f"Document AI Pipeline Failed: {str(e)}")
        task = await db.get(BackgroundTask, task_id)
        if task:
            task.status = "failed"
            task.error_message = str(e)
            task.updated_at = datetime.utcnow()
            await db.commit()
