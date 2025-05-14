from pydantic import BaseModel
from typing import List, Dict

class Quiz(BaseModel):
  question: str
  answer: str 