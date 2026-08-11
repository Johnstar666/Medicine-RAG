import jieba
import jieba.posseg as pseg
from domain.services.keyword_extraction_service import KeywordExtractionService

# 加载停用词（可自行下载通用停用词表）
stop_words = {'的', '了', '吗', '我', '你', '要', '想', '在', '是'}

class RuleBasedKeywordExtractor(KeywordExtractionService):
    """基于规则的关键词提取实现"""
    
    def extract_keywords(self, text: str) -> str:
        """从文本中提取关键词
        
        Args:
            text: 输入文本
            
        Returns:
            提取的关键词，用逗号分隔
        """
        words = pseg.cut(text)
        keywords = []
        keep_pos = ['n', 'v', 'nz', 'ns', 'nt']
        for word, flag in words:
            if flag in keep_pos and word not in stop_words and len(word) > 1:
                keywords.append(word)
        keyword_set = list(set(keywords))
        return "，".join(keyword_set) if keywords else text