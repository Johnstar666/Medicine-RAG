from Bio import Entrez

from utils.logger_handler import logger
from utils.postgres_db import PostgresDB_singleton
from pubmed.pubmed_retriever import PubMedRetriever
from utils.config_handler import pubmed_conf

Entrez.email = pubmed_conf["email"]  # 必须设置
Entrez.api_key = pubmed_conf["api_key"]  # 可选，提升至10 req/s
Entrez.max_tries=pubmed_conf["max_tries"]
Entrez.sleep_between_tries=pubmed_conf["sleep_between_tries"]

def main(pubmed_query):
    """主执行函数：检索→提取→查重→插入"""
    # 初始化工具类
    pubmed_retriever = PubMedRetriever()
    db = PostgresDB_singleton

    try:
        # 1. 建立数据库连接
        db.connect()
        # 2. PubMed检索：获取PMID列表
        pmids = pubmed_retriever.search_pubmed(pubmed_query)
        if not pmids:
            return
        # 3. 遍历PMID：提取数据→查重→插入
        for pmid in pmids:
            if db.is_pmid_exist(pmid):
                logger.info(f"文献已存在，跳过插入（pmid={pmid}）")
                continue
            # 提取文献数据
            article_data = pubmed_retriever.fetch_article_details(pmid)
            # 插入数据库
            db.insert_article(article_data)
    except Exception as e:
        logger.error(f"主程序执行失败：{str(e)}", exc_info=True)
    finally:
        # 确保数据库连接关闭
        db.close()

if __name__ == "__main__":
    # 测试：传入查询词，示例为「COVID-19 vaccination and cardiovascular disease」
    test_query = ("heart")
    main(test_query)

#
# keyword = input("Enter keywords: ")
# max_results = pubmed_conf["max_results"]
#
# handle = Entrez.esearch(db="pubmed", term=keyword, retmax=max_results)
# record = Entrez.read(handle)
# print("匹配的PMID列表：", record["IdList"])
# handle.close()

