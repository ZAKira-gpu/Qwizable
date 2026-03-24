import json
import asyncio
from typing import List, Dict, Any
from app.services.ai_service import call_novita_api
from app.core.logger import logger

async def generate_quiz_from_chunk(chunk: str, difficulty: str, num_questions: int) -> List[Dict[str, Any]]:
    prompt = f"""
You are an expert educator.
Generate a high-quality quiz based ONLY on the provided content.

CONTENT:
{chunk}

Generate {num_questions} questions.

Rules:
- Difficulty: {difficulty}
- Focus on understanding, not memorization
- Avoid trivial questions

Return STRICT JSON:

{{
  "quiz": [
    {{
      "question": "...",
      "type": "mcq",
      "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
      "correct_answer": "A",
      "explanation": "Short explanation"
    }}
  ]
}}
"""
    response_text = await call_novita_api(prompt)
    if not response_text:
        return []
        
    try:
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        data = json.loads(response_text)
        if "quiz" in data:
            return data["quiz"]
        elif isinstance(data, list):
            return data
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Chunk Quiz JSON Decode failed: {e} -> {response_text}")
        return []

async def merge_and_deduplicate_quizzes(all_questions: List[Dict[str, Any]], target_num: int) -> List[Dict[str, Any]]:
    """Merges chunk quizzes and removes duplicate questions."""
    seen_questions = set()
    final_quiz = []
    
    for q in all_questions:
        q_text = q.get("question", "").strip().lower()
        if q_text and q_text not in seen_questions:
            seen_questions.add(q_text)
            final_quiz.append(q)
            
        if len(final_quiz) >= target_num:
            break
            
    return final_quiz
