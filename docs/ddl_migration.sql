-- pubmed_articles 表 Schema 迁移
-- 项目: Medicine_RAG_Project
-- 日期: 2026-08-11
-- 执行: psql -U postgres -d medicineKB -f docs/ddl_migration.sql

-- 新增字段（幂等：IF NOT EXISTS）
ALTER TABLE pubmed_articles
ADD COLUMN IF NOT EXISTS ingestion_status VARCHAR(20) DEFAULT 'uningested';

ALTER TABLE pubmed_articles
ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMP;

ALTER TABLE pubmed_articles
ADD COLUMN IF NOT EXISTS chunk_count INTEGER;

ALTER TABLE pubmed_articles
ADD COLUMN IF NOT EXISTS vector_ids JSONB;

ALTER TABLE pubmed_articles
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();

ALTER TABLE pubmed_articles
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();

ALTER TABLE pubmed_articles
ADD COLUMN IF NOT EXISTS search_query TEXT;

ALTER TABLE pubmed_articles
ADD COLUMN IF NOT EXISTS ingestion_error TEXT;

ALTER TABLE pubmed_articles
ADD COLUMN IF NOT EXISTS raw_response JSONB;

-- 索引（幂等）
CREATE INDEX IF NOT EXISTS idx_pubmed_ingestion_status ON pubmed_articles(ingestion_status);
CREATE INDEX IF NOT EXISTS idx_pubmed_created_at ON pubmed_articles(created_at);
CREATE INDEX IF NOT EXISTS idx_pubmed_article_gin ON pubmed_articles USING GIN (article_info jsonb_path_ops);
