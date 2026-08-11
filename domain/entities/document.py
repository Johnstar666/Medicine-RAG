from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class Document:
    """文档实体"""
    content: str
    metadata: Dict[str, Any]
    
    @property
    def source(self) -> str:
        return self.metadata.get("source", "")
    
    def __hash__(self):
        return hash((self.content, str(self.metadata)))
    
    def __eq__(self, other):
        if not isinstance(other, Document):
            return False
        return self.content == other.content and self.metadata == other.metadata