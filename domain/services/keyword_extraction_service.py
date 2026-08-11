from abc import ABC, abstractmethod

class KeywordExtractionService(ABC):
    """关键词提取服务接口"""
    
    @abstractmethod
    def extract_keywords(self, text: str) -> str:
        """从文本中提取关键词
        
        Args:
            text: 输入文本
            
        Returns:
            提取的关键词，用逗号分隔
        """
        pass