import json
import asyncio
from typing import List, Dict, Any
from app.services.ai_service import call_novita_api
from app.core.logger import logger

def jaccard_similarity(str1: str, str2: str) -> float:
    """Calculates semantic overlap of words using Jaccard Similarity"""
    set1, set2 = set(str1.lower().split()), set(str2.lower().split())
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return float(intersection) / union if union != 0 else 0.0

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
    """Merges chunk quizzes using semantic Jaccard deduplication."""
    final_quiz = []
    
    for q in all_questions:
        q_text = q.get("question", "").strip()
        if not q_text: continue
        
        is_duplicate = False
        for f_q in final_quiz:
            if jaccard_similarity(q_text, f_q.get("question", "")) > 0.65:
                is_duplicate = True
                break
                
        if not is_duplicate:
            final_quiz.append(q)
            
        if len(final_quiz) >= target_num:
            break
            
    return final_quiz
