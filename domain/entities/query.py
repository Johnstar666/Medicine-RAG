from dataclasses import dataclass


@dataclass
class Query:
    """查询实体"""
    question: str
    top_k: int | None = 6
    keywords: str | None = None
    
    def with_keywords(self, keywords: str) -> "Query":
        return Query(
            question=self.question,
            top_k=self.top_k,
            keywords=keywords
        )