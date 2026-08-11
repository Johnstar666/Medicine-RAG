import os
import sys

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from fastapi import APIRouter, HTTPException

from application.services.rag_query_service import RAGQueryService
from domain.entities.query import Query as DomainQuery
from schemas.rag_query import ApiResponse, QueryRequest, RAGResponse

router = APIRouter(prefix="/rag")

# 这里需要一个依赖注入容器来获取服务实例
# 暂时使用全局实例，后续可以替换为依赖注入框架
rag_query_service = None

@router.post("/query")
async def query_rag(request: QueryRequest):
    try:
        if not rag_query_service:
            raise HTTPException(status_code=500, detail="Service not initialized")
            
        # 转换为领域查询对象
        domain_query = DomainQuery(
            question=request.question,
            top_k=request.top_k
        )
        
        # 调用应用服务处理查询
        response = rag_query_service.process_query(domain_query)
        
        # 转换为API响应对象
        result = RAGResponse(
            question=request.question,
            answer=response.answer,
            sources=response.sources,
            keywords=response.keywords
        )
        return ApiResponse(
            code=200,
            message="success",
            data=result
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def set_rag_query_service(service: RAGQueryService):
    """设置RAG查询服务实例
    
    Args:
        service: RAG查询服务实例
    """
    global rag_query_service
    rag_query_service = service