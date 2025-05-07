from pydantic import BaseModel
from typing import List, Dict

class Quiz(BaseModel):
  question: str
  answer: str 

class ExplanationUpdateItem(BaseModel):
    field: str
    explanation: str

class ComprehensionUpdateSuggestion(BaseModel):
    levelUpField: List[str]
    updateExplanation: List[ExplanationUpdateItem]