from pydantic import BaseModel
from typing import Optional, List

class QueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = 3

class RAGResponse(BaseModel):
    question: str
    answer: str
    sources: List[str]
    keywords: str

class ApiResponse(BaseModel):
    code: int
    message: str
    data: Optional[RAGResponse] = None
