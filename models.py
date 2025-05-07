from pydantic import BaseModel

class Quiz(BaseModel):
  question: str
  answer: str 