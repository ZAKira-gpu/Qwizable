from pydantic import BaseModel

class TutorRequest(BaseModel):
    message: str
    quiz_context_id: int

class TutorResponse(BaseModel):
    reply: str
