from dataclasses import dataclass
from typing import List

@dataclass
class RAGResponse:
    """RAG响应实体"""
    question: str
    answer: str
    sources: List[str]
    keywords: str
    
    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "answer": self.answer,
            "sources": self.sources,
            "keywords": self.keywords
        }