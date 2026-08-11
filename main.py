import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from infrastructure.utils.config_handler import fastapi_conf
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers.rag_router import router as rag_router, set_rag_query_service
from infrastructure.services.service_factory import ServiceFactory

# 初始化FastAPI
app = FastAPI()

# 初始化服务工厂
factory = ServiceFactory()

# 初始化RAG查询服务并设置到路由中
rag_query_service = factory.get_rag_query_service()
set_rag_query_service(rag_query_service)

# 加载API路由
app.include_router(rag_router)

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


