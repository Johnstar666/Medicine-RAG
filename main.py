import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers.knowledge_router import (
    router as knowledge_router,
)
from api.routers.knowledge_router import (
    set_knowledge_management_service as set_km_for_knowledge,
)
from api.routers.pubmed_router import (
    router as pubmed_router,
)
from api.routers.pubmed_router import (
    set_knowledge_management_service as set_km_for_pubmed,
)
from api.routers.pubmed_router import (
    set_pubmed_search_service,
)
from api.routers.rag_router import router as rag_router
from api.routers.rag_router import set_rag_query_service
from infrastructure.services.service_factory import ServiceFactory
from infrastructure.utils.config_handler import fastapi_conf

# 初始化FastAPI
app = FastAPI()

# 初始化服务工厂
factory = ServiceFactory()

# 初始化RAG查询服务并设置到路由中
rag_query_service = factory.get_rag_query_service()
set_rag_query_service(rag_query_service)

# 初始化PubMed搜索服务并注入 pubmed_router
pubmed_search_service = factory.get_pubmed_search_service()
set_pubmed_search_service(pubmed_search_service)

# 初始化知识库管理服务并注入 pubmed_router + knowledge_router
knowledge_mgmt_service = factory.get_knowledge_management_service()
set_km_for_pubmed(knowledge_mgmt_service)
set_km_for_knowledge(knowledge_mgmt_service)

# 加载API路由
app.include_router(rag_router)
app.include_router(pubmed_router)
app.include_router(knowledge_router)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=fastapi_conf["FASTAPI_HOST"],
        port=fastapi_conf["FASTAPI_PORT"],
    )


