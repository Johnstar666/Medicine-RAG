from dataclasses import dataclass
from typing import Optional

@dataclass
class Query:
    """查询实体"""
    question: str
    top_k: Optional[int] = 3
    keywords: Optional[str] = None
    
    def with_keywords(self, keywords: str) -> "Query":
        return Query(
            question=self.question,
            top_k=self.top_k,
            keywords=keywords
        )