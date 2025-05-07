from pydantic import BaseModel

class Quiz(BaseModel):
  question: str
  answer: str 

class ComprehensionUpdateSuggestion(BaseModel):
  levelUpField: list[str]
  updateExplanation: dict[str, str]