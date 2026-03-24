from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Any
from app.db.session import get_db
from app.models.user import User
from app.models.quiz import Quiz, Question
from app.models.task import BackgroundTask
from app.models.usage import Usage
from app.schemas.quiz import QuizRequest, QuizPaginatedResponse, QuizResponse, QuestionResponse, QuizSubmitRequest, ResultResponse
from app.api.v1.user import get_current_user
from app.services.quiz_service import generate_quiz_task
from app.services.evaluation_service import evaluate_answers
from app.services.user_service import increment_usage
from app.services.document_ai_service import process_document_and_generate_quiz
from app.core.rate_limit import rate_limiter
from datetime import datetime

router = APIRouter()

async def get_usage_envelope(db: AsyncSession, current_user: User, plan_remaining_uploads: Any) -> dict:
    total_tokens_query = select(func.sum(Usage.tokens_used)).where(Usage.user_id == current_user.id)
    total_tokens = await db.scalar(total_tokens_query) or 0
    return {
        "remaining_free_uploads": plan_remaining_uploads,
        "tokens_used": int(total_tokens)
    }

@router.post("/generate", status_code=202)
async def generate_quiz(
    request: QuizRequest, 
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    await increment_usage(db, current_user.id)
    
    task = BackgroundTask(job_name=f"generate_quiz_{current_user.id}_{request.topic}")
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    background_tasks.add_task(
        generate_quiz_task, db, task.id, current_user.id, request.topic, request.difficulty, request.num_questions
    )
    
    usage_info = await get_usage_envelope(db, current_user, "unlimited")
    return {
        "success": True, 
        "data": {"message": "Quiz generation started.", "task_id": task.id}, 
        "error": None,
        "usage": usage_info
    }

from typing import Optional

@router.post("/generate-from-file", status_code=202)
async def generate_from_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    difficulty: str = Form("medium"),
    num_questions: int = Form(5),
    thread_id: Optional[str] = Form(None),
    instructions: Optional[str] = Form(None),
    start_page: Optional[int] = Form(None),
    end_page: Optional[int] = Form(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    file_bytes = await file.read()
    
    limits = await rate_limiter.check_upload_limits(db, current_user.id, current_user.plan, len(file_bytes))
    
    usage_query = select(Usage).where(Usage.user_id == current_user.id).order_by(Usage.created_at.desc()).limit(1)
    usage_record = await db.scalar(usage_query)
    
    if usage_record and usage_record.created_at.date() == datetime.utcnow().date():
        usage_record.docs_uploaded += 1
    else:
        usage_record = Usage(user_id=current_user.id, docs_uploaded=1)
        db.add(usage_record)
    await db.commit()
    
    await increment_usage(db, current_user.id)
    
    task = BackgroundTask(
        job_name=f"document_quiz_{current_user.id}_{file.filename}",
        task_metadata={"user_id": current_user.id, "filename": file.filename, "difficulty": difficulty, "num_questions": num_questions, "thread_id": thread_id, "instructions": instructions}
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    background_tasks.add_task(
        process_document_and_generate_quiz, db, task.id, current_user.id, file_bytes, file.filename, difficulty, num_questions, thread_id, instructions, start_page, end_page
    )
    
    usage_info = await get_usage_envelope(db, current_user, limits["remaining"])
    return {
        "success": True, 
        "data": {"message": "Document Quiz generation started.", "task_id": task.id}, 
        "error": None,
        "usage": usage_info
    }

@router.get("/", response_model=QuizPaginatedResponse)
async def get_quizzes(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * size
    
    total_query = select(func.count(Quiz.id)).where(Quiz.user_id == current_user.id).where(Quiz.deleted_at.is_(None))
    total = await db.scalar(total_query)
    
    query = select(Quiz).where(Quiz.user_id == current_user.id).where(Quiz.deleted_at.is_(None)).order_by(Quiz.created_at.desc()).offset(offset).limit(size)
    result = await db.execute(query)
    quizzes = result.scalars().all()
    
    return QuizPaginatedResponse(items=quizzes, total=total, page=page, size=size)

@router.post("/{quiz_id}/submit")
async def submit_quiz(
    quiz_id: int,
    submission: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    quiz = await db.get(Quiz, quiz_id)
    if not quiz or quiz.user_id != current_user.id or quiz.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Quiz not found")
        
    result = await evaluate_answers(db, quiz_id, submission.answers)
    
    usage_info = await get_usage_envelope(db, current_user, "unlimited")
    return {"success": True, "data": result, "error": None, "usage": usage_info}
