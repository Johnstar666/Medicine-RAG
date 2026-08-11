# DEPRECATED: 请使用 infrastructure.persistence.postgres_db
# 该文件保留仅用于向后兼容，新功能请使用新模块。
import json
import psycopg2

from utils.logger_handler import logger
from utils.config_handler import postgre_conf


class PostgresDB:
    """PostgreSQL数据库工具类：实现查重、插入"""
    def __init__(self):
        self.conn_params = {
            "host": postgre_conf["PG_HOST"],
            "port": postgre_conf["PG_PORT"],
            "user": postgre_conf["PG_USER"],
            "password": postgre_conf["PG_PASSWORD"],
            "database": postgre_conf["PG_DATABASE"],
            "options": "-c client_encoding=utf8"  # 新增：强制客户端编码为UTF-8
        }
        self.table = postgre_conf["PG_TABLE"]
        self.conn = None
        self.cur = None

    def connect(self):
        """建立数据库连接（修复编码问题）"""
        try:
            # 手动转换参数编码（兼容Windows GBK）
            for key in self.conn_params:
                if isinstance(self.conn_params[key], str):
                    # 先按Windows默认编码（gbk）解码，再按utf8编码
                    self.conn_params[key] = self.conn_params[key].encode('gbk').decode('utf8', errors='ignore')

            self.conn = psycopg2.connect(**self.conn_params)
            self.cur = self.conn.cursor()
            logger.info("PostgreSQL数据库连接成功")
        except Exception as e:
            logger.error(f"数据库连接失败：{str(e)}", exc_info=True)
            raise

    def close(self):
        """关闭数据库连接"""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        logger.info("PostgreSQL数据库连接已关闭")

    # 插入文章 ---------------------------------------------------------------------------

    def is_pmid_exist(self, pmid):
        """判断PMID是否存在，存在返回True，否则返回False"""
        try:
            sql = f"SELECT 1 FROM {self.table} WHERE pmid = %s LIMIT 1"
            self.cur.execute(sql, (pmid,))
            return self.cur.fetchone() is not None
        except Exception as e:
            logger.error(f"PMID查重失败（pmid={pmid}）：{str(e)}", exc_info=True)
            self.conn.rollback()
            raise

    def insert_article(self, article_data):
        """插入单篇文献数据（字段与数据库表严格对应）"""
        try:
            # 插入SQL（字段顺序与数据库表一致，排除自增id和自动维护的时间字段）
            sql = f"""
                INSERT INTO {self.table} (pmid, article_info, study_groups, results_info, objectives, is_free_download)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            # 组装参数：pmid/JSONB/数组/布尔值（psycopg2自动适配PostgreSQL类型）
            params = (
                article_data["pmid"],
                json.dumps(article_data["article_info"]),  # 自动转为JSONB
                article_data["study_groups"],              # 自动转为TEXT[]
                json.dumps(article_data["results_info"]) if article_data["results_info"] else None,
                article_data["objectives"],
                article_data["is_free_download"]
            )
            self.cur.execute(sql, params)
            self.conn.commit()
            logger.info(f"文献插入成功（pmid={article_data['pmid']}）")
        except Exception as e:
            logger.error(f"文献插入失败（pmid={article_data['pmid']}）：{str(e)}", exc_info=True)
            self.conn.rollback()
            raise e


# 单例模式：避免重复创建数据库连接
PostgresDB_singleton = PostgresDB()