"""PostgreSQL 数据库工具类。

提供 PubMed 文献的 CRUD 操作, 支持上下文管理器和显式连接两种使用方式。

Usage:
    1. 上下文管理器 (推荐):
       with PostgresDB() as db:
           db.is_pmid_exist("12345678")

    2. 显式 connect/close (向后兼容):
       db = PostgresDB()
       db.connect()
       db.is_pmid_exist("12345678")
       db.close()
"""

from __future__ import annotations

import json
from typing import Any, Literal

import psycopg2
from psycopg2.extras import RealDictCursor

from infrastructure.utils.config_handler import postgre_conf
from infrastructure.utils.logger_handler import get_logger

logger = get_logger(name="postgres_db")

# ── SQL 注入白名单 ───────────────────────────────────────────
ALLOWED_SORT: set[str] = {"created_at", "updated_at", "pmid"}
ALLOWED_ORDER: set[str] = {"asc", "desc"}


class PostgresDB:
    """PostgreSQL 数据库工具类。

    支持两种使用方式：

    1. 上下文管理器（推荐）:
       with PostgresDB() as db:
           db.is_pmid_exist("12345678")

    2. 显式 connect/close（向后兼容）:
       db = PostgresDB()
       db.connect()
       db.is_pmid_exist("12345678")
       db.close()
    """

    def __init__(self) -> None:
        self.conn_params: dict[str, Any] = {
            "host": postgre_conf["PG_HOST"],
            "port": postgre_conf["PG_PORT"],
            "user": postgre_conf["PG_USER"],
            "password": postgre_conf["PG_PASSWORD"],
            "database": postgre_conf["PG_DATABASE"],
            "options": "-c client_encoding=utf8",
        }
        self.table: str = postgre_conf["PG_TABLE"]
        self.conn: Any = None
        self.cur: Any = None

    # ── 上下文管理器 ─────────────────────────────────────────
    def __enter__(self) -> PostgresDB:
        """进入上下文管理器时自动建立连接。

        Returns:
            self: 已连接的 PostgresDB 实例。
        """
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> Literal[False]:
        """退出上下文管理器时自动关闭连接。

        Args:
            exc_type: 异常类型 (无异常时为 None)。
            exc_val: 异常值 (无异常时为 None)。
            exc_tb: traceback 对象。

        Returns:
            False: 不吞异常，让调用方正常处理异常。
        """
        self.close()
        return False

    # ── 连接管理 ─────────────────────────────────────────────
    def connect(self) -> None:
        """建立数据库连接。重复调用时先关闭旧连接。"""
        if self.conn:
            self.close()
        try:
            # 手动转换参数编码（兼容 Windows GBK）
            for key in list(self.conn_params.keys()):
                if isinstance(self.conn_params[key], str):
                    self.conn_params[key] = (
                        self.conn_params[key]
                        .encode("gbk", errors="ignore")
                        .decode("utf8", errors="ignore")
                    )

            self.conn = psycopg2.connect(**self.conn_params)
            self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
            logger.info("PostgreSQL 连接成功")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise

    def close(self) -> None:
        """关闭数据库连接。"""
        if self.cur:
            self.cur.close()
            self.cur = None
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("PostgreSQL 连接已关闭")

    def _ensure_connected(self) -> None:
        """确保连接有效；若已断开则自动重连。"""
        if not self.conn or self.conn.closed:
            self.connect()

    # ── 查重 ─────────────────────────────────────────────────
    def is_pmid_exist(self, pmid: str) -> bool:
        """判断 PMID 是否已存在。

        Args:
            pmid: PubMed 唯一标识符。

        Returns:
            True 表示该 PMID 已存在于数据库。
        """
        self._ensure_connected()
        try:
            sql = f"SELECT 1 FROM {self.table} WHERE pmid = %s LIMIT 1"
            self.cur.execute(sql, (pmid,))
            return self.cur.fetchone() is not None
        except Exception as e:
            logger.error(f"PMID 查重失败 (pmid={pmid}): {e}")
            self.conn.rollback()
            raise

    # ── 插入 ─────────────────────────────────────────────────
    def insert_article(self, article_data: dict[str, Any]) -> None:
        """插入单篇文献。包含 search_query 和 raw_response 字段。

        Args:
            article_data: 文献数据字典，至少应包含 pmid, article_info 字段。

        Raises:
            Exception: 插入失败时抛出（包括唯一约束冲突）。
        """
        self._ensure_connected()
        try:
            sql = f"""
                INSERT INTO {self.table}
                    (pmid, article_info, study_groups, results_info,
                     objectives, is_free_download, ingestion_status,
                     search_query, raw_response)
                VALUES (%s, %s, %s, %s, %s, %s, 'uningested', %s, %s)
            """
            params: tuple = (
                article_data["pmid"],
                json.dumps(article_data["article_info"]),
                article_data.get("study_groups", []),
                json.dumps(article_data["results_info"])
                if article_data.get("results_info")
                else None,
                article_data.get("objectives", ""),
                article_data.get("is_free_download", False),
                article_data.get("search_query", ""),
                json.dumps(article_data.get("raw_response"))
                if article_data.get("raw_response")
                else None,
            )
            self.cur.execute(sql, params)
            self.conn.commit()
            logger.info(f"文献插入成功 (pmid={article_data['pmid']})")
        except Exception as e:
            logger.error(f"文献插入失败 (pmid={article_data['pmid']}): {e}")
            self.conn.rollback()
            raise

    # ── 查询方法 ─────────────────────────────────────────────
    def get_article_by_pmid(self, pmid: str) -> dict[str, Any] | None:
        """获取单篇文献完整数据。

        Args:
            pmid: PubMed 唯一标识符。

        Returns:
            文献 dict (RealDictCursor 结果)，不存在时返回 None。
        """
        self._ensure_connected()
        try:
            sql = f"SELECT * FROM {self.table} WHERE pmid = %s"
            self.cur.execute(sql, (pmid,))
            return self.cur.fetchone()
        except Exception as e:
            logger.error(f"查询文献失败 (pmid={pmid}): {e}")
            raise

    def list_articles(
        self,
        page: int = 1,
        page_size: int = 20,
        search: str | None = None,
        ingestion_status: str = "all",
        sort_by: str = "created_at",
        order: str = "desc",
    ) -> tuple[list[dict[str, Any]], int]:
        """分页查询文献列表。

        支持按标题/摘要模糊搜索 (ILIKE)，按 ingestion_status 过滤。
        使用 RealDictCursor 返回字典列表。
        sort_by 和 order 参数经过 SQL 注入白名单校验。

        Args:
            page: 页码 (从 1 开始)。
            page_size: 每页条数。
            search: 搜索关键词，在 title 和 abstract 中 ILIKE 模糊匹配。
            ingestion_status: 过滤状态，"all" 表示不过滤。
            sort_by: 排序字段，仅允许 created_at / updated_at / pmid。
            order: 排序方向，仅允许 asc / desc。

        Returns:
            (rows: List[Dict], total_count: int)
        """
        self._ensure_connected()
        try:
            # 构建 WHERE 条件
            conditions: list[str] = []
            params: list[Any] = []

            if search:
                conditions.append(
                    "(article_info->>'title' ILIKE %s "
                    "OR article_info->>'abstract' ILIKE %s)"
                )
                like_pattern = f"%{search}%"
                params.extend([like_pattern, like_pattern])

            if ingestion_status != "all":
                conditions.append("ingestion_status = %s")
                params.append(ingestion_status)

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            # 排序白名单校验（防止 SQL 注入）
            sort_col: str = sort_by if sort_by in ALLOWED_SORT else "created_at"
            sort_order: str = order if order in ALLOWED_ORDER else "desc"

            # 总数查询
            count_sql = f"SELECT COUNT(*) as cnt FROM {self.table} {where_clause}"
            self.cur.execute(count_sql, params)
            total_row: Any = self.cur.fetchone()
            total: int = total_row["cnt"] if total_row else 0

            # 分页查询
            offset = (page - 1) * page_size
            data_sql = f"""
                SELECT pmid, article_info, study_groups, objectives,
                       is_free_download, ingestion_status, ingested_at,
                       created_at
                FROM {self.table}
                {where_clause}
                ORDER BY {sort_col} {sort_order}
                LIMIT %s OFFSET %s
            """
            self.cur.execute(data_sql, params + [page_size, offset])
            rows: list[dict[str, Any]] = self.cur.fetchall()

            return rows, total
        except Exception as e:
            logger.error(f"查询文献列表失败: {e}")
            raise

    # ── 更新方法 ─────────────────────────────────────────────
    def update_ingestion_status(
        self,
        pmid: str,
        status: str,
        error: str | None = None,
        chunk_count: int | None = None,
        vector_ids: list[str] | None = None,
    ) -> None:
        """更新文献的向量索引状态。

        动态构建 SET 子句，仅更新传入的非 None 参数。
        status="ingested" 时自动设置 ingested_at = NOW() 并清除 error。
        status="failed" 时设置 ingestion_error。

        Args:
            pmid: 文献 PMID。
            status: 目标状态 ("ingesting" | "ingested" | "failed")。
            error: 失败原因（status="failed" 时填写）。
            chunk_count: 生成的 chunk 数量。
            vector_ids: ChromaDB 分配的 chunk ID 列表。
        """
        self._ensure_connected()
        try:
            set_parts: list[str] = ["ingestion_status = %s", "updated_at = NOW()"]
            params: list[Any] = [status]

            if status == "ingested":
                set_parts.append("ingested_at = NOW()")
            if chunk_count is not None:
                set_parts.append("chunk_count = %s")
                params.append(chunk_count)
            if vector_ids is not None:
                set_parts.append("vector_ids = %s")
                params.append(json.dumps(vector_ids))
            if error is not None:
                set_parts.append("ingestion_error = %s")
                params.append(error)
            elif status == "ingested":
                # 成功时清除旧的错误信息
                set_parts.append("ingestion_error = NULL")

            set_clause = ", ".join(set_parts)
            sql = f"UPDATE {self.table} SET {set_clause} WHERE pmid = %s"
            params.append(pmid)

            self.cur.execute(sql, params)
            self.conn.commit()
            logger.info(
                f"更新摄入状态成功 (pmid={pmid}, status={status}, "
                f"chunks={chunk_count})"
            )
        except Exception as e:
            logger.error(f"更新摄入状态失败 (pmid={pmid}): {e}")
            self.conn.rollback()
            raise

    # ── 统计方法 ─────────────────────────────────────────────
    def count_articles_by_status(self) -> dict[str, int]:
        """按 ingestion_status 统计文献数量。

        Returns:
            {"total": N, "ingested": N, "uningested": N, "failed": N}
        """
        self._ensure_connected()
        try:
            status_col = "ingestion_status"
            sql = f"""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE {status_col} = 'ingested') as ingested,
                    COUNT(*) FILTER (WHERE {status_col} = 'uningested') as uningested,
                    COUNT(*) FILTER (WHERE {status_col} = 'failed') as failed
                FROM {self.table}
            """
            self.cur.execute(sql)
            row: Any = self.cur.fetchone()
            return {
                "total": row["total"] or 0,
                "ingested": row["ingested"] or 0,
                "uningested": row["uningested"] or 0,
                "failed": row["failed"] or 0,
            }
        except Exception as e:
            logger.error(f"统计文献数量失败: {e}")
            raise

    def count_all(self) -> int:
        """返回文献总数。

        Returns:
            pubmed_articles 表中的文献总数。
        """
        self._ensure_connected()
        try:
            sql = f"SELECT COUNT(*) as cnt FROM {self.table}"
            self.cur.execute(sql)
            row: Any = self.cur.fetchone()
            return row["cnt"] if row else 0
        except Exception as e:
            logger.error(f"统计总数失败: {e}")
            raise

    # ── 删除方法 ─────────────────────────────────────────────
    def delete_article(self, pmid: str) -> bool:
        """删除单篇文献记录。

        Args:
            pmid: PubMed 唯一标识符。

        Returns:
            True 表示成功删除至少 1 行，False 表示 PMID 不存在。
        """
        self._ensure_connected()
        try:
            sql = f"DELETE FROM {self.table} WHERE pmid = %s"
            self.cur.execute(sql, (pmid,))
            self.conn.commit()
            deleted: bool = self.cur.rowcount > 0
            logger.info(
                f"删除文献 (pmid={pmid}): {'成功' if deleted else 'PMID不存在'}"
            )
            return deleted
        except Exception as e:
            logger.error(f"删除文献失败 (pmid={pmid}): {e}")
            self.conn.rollback()
            raise


# 单例：供 pubmed/paper_search.py 等旧代码过渡使用
PostgresDB_singleton = PostgresDB()
