import os
import time

from Bio import Entrez
from utils.config_handler import pubmed_conf
from utils.logger_handler import logger


class PubMedRetriever:
    """PubMed检索工具类（修复XML解析错误版）"""

    def __init__(self):
        # 初始化Entrez，强制指定返回XML（Entrez.read原生支持）
        Entrez.email = pubmed_conf['email']
        Entrez.api_key = pubmed_conf['api_key']
        Entrez.max_tries = pubmed_conf["max_tries"]  # 增加重试次数
        Entrez.sleep_between_tries = 3  # 重试间隔3秒
        self.max_results = pubmed_conf["max_results"]
        # 补充请求头（NCBI要求）
        Entrez.tool = "Python"

    def fetch_article_details(self, pmid):
        """根据PMID获取文献详情（简化版，保证能解析）"""
        try:
            handle = Entrez.efetch(
                db="pubmed",
                id=pmid,
                rettype="xml",
                retmode="text"
            )
            records = Entrez.read(handle)
            handle.close()

            # 基础数据提取（保证不报错）
            article = records["PubmedArticle"][0]["MedlineCitation"]["Article"]
            abstract = article.get("Abstract", {}).get("AbstractText", "")
            abstract = " ".join(abstract) if isinstance(abstract, list) else str(abstract)

            # 组装数据库所需字段
            return {
                "pmid": pmid,
                "article_info": {
                    "title": article.get("ArticleTitle", ""),
                    "authors": [f"{a.get('LastName', '')} {a.get('ForeName', '')}" for a in
                                article.get("AuthorList", [])],
                    "abstract": abstract,
                    "journal": article.get("Journal", {}).get("Title", "")
                },
                "study_groups": [],  # 先默认空数组，后续可扩展
                "results_info": {"raw_abstract": abstract[:200]},
                "objectives": abstract[:200] if abstract else "未明确研究目标",
                "is_free_download": False  # 先默认，后续可从PMC标识解析
            }
        except Exception as e:
            logger.error(f"提取文献详情失败（pmid={pmid}）：{str(e)}", exc_info=True)
            raise

    def search_pubmed(self, query):
        """修复：移除retmode="json"，按XML解析，补充请求头"""
        try:
            # 1. 构建检索参数（移除retmode，默认返回XML）
            handle = Entrez.esearch(
                db="pubmed",
                term=query,
                retmax=self.max_results,
                sort="relevance",
                # 关键：移除retmode="json"，改用默认XML格式
                usehistory="y"  # 启用历史记录，提升后续efetch效率
            )
            # 2. 按XML解析返回数据（Entrez.read原生支持）
            result = Entrez.read(handle)
            handle.close()

            pmids = result["IdList"]
            if not pmids:
                logger.warning(f"查询词「{query}」未检索到文献")
                return []
            logger.info(f"检索到{len(pmids)}篇文献，PMID：{pmids}")
            return pmids
        except Exception as e:
            logger.error(f"PubMed检索失败（query={query}）：{str(e)}", exc_info=True)
            # 手动重试（针对网络波动）
            time.sleep(3)
            try:
                handle = Entrez.esearch(
                    db="pubmed",
                    term=query,
                    retmax=self.max_results,
                    sort="relevance",
                    usehistory="y"
                )
                result = Entrez.read(handle)
                handle.close()
                return result["IdList"]
            except Exception as e2:
                logger.error(f"重试后仍失败：{str(e2)}", exc_info=True)
                raise

    @staticmethod
    def _parse_authors(author_list):
        """解析作者列表"""
        authors = []
        for author in author_list:
            if "LastName" in author and "ForeName" in author:
                authors.append({
                    "last_name": author["LastName"],
                    "first_name": author["ForeName"]
                })
        return authors

    @staticmethod
    def _parse_abstract(abstract_data):
        """解析摘要"""
        if "AbstractText" in abstract_data:
            abstract_text = abstract_data["AbstractText"]
            if isinstance(abstract_text, list):
                return " ".join([str(para) for para in abstract_text])
            return str(abstract_text)
        return ""

    @staticmethod
    def _parse_publish_date(date_data):
        """解析发表时间：返回YYYY-MM-DD格式，无则为空"""
        year = date_data.get("Year", "")
        month = date_data.get("Month", "01")
        day = date_data.get("Day", "01")
        if year:
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        return ""

    @staticmethod
    def _parse_doi(article_id_list):
        """解析DOI号"""
        for aid in article_id_list:
            if aid.attributes.get("IdType") == "doi":
                return str(aid)
        return ""

    @staticmethod
    def _parse_study_groups(abstract):
        """从摘要提取研究分组：匹配对照组/试验组/观察组等关键词，返回数组"""
        group_keywords = ["对照组", "试验组", "观察组", "治疗组", "安慰剂组", "模型组"]
        study_groups = [kw for kw in group_keywords if kw in abstract]
        return study_groups if study_groups else []

    @staticmethod
    def _parse_results_info(abstract):
        """从摘要提取研究结果：返回{endpoints: 终点指标, stats: 统计结果}，无则为None"""
        if not abstract:
            return None
        # 简单提取：可根据需求替换为NLP解析（如提取P值、置信区间、HR值等）
        return {
            "endpoints": "从摘要提取的核心终点指标（可扩展NLP解析）",
            "stats": "从摘要提取的统计结果（如P<0.05、HR=0.67等）",
            "raw_abstract": abstract[:200] + "..." if len(abstract) > 200 else abstract
        }

    @staticmethod
    def _parse_objectives(abstract):
        """从摘要提取研究目标：匹配研究目的/旨在/探究等关键词，返回字符串"""
        if not abstract:
            return None
        # 简单提取：可根据需求扩展NLP解析逻辑
        objective_keywords = ["研究目的", "旨在", "探究", "探讨", "评估", "分析", "验证"]
        for kw in objective_keywords:
            if kw in abstract:
                idx = abstract.index(kw)
                # 提取关键词后200个字符作为研究目标（可调整长度）
                return abstract[idx:idx+200].replace("\n", "").strip()
        return None

    @staticmethod
    def _is_free_download(article_id_list):
        """
        判断文献是否可免费下载：
        - 存在 PMC 标识（IdType = 'pmc'） → 可免费下载 → 返回 True
        - 否则 → 返回 False
        """
        for aid in article_id_list:
            if aid.attributes.get("IdType") == "pmc":
                return True
        return False