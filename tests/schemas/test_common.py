"""tests for schemas.common.ApiResponse."""

from typing import Any

from pydantic import BaseModel

from schemas.common import ApiResponse


class TestApiResponseInstantiation:
    """测试 ApiResponse 基本实例化。"""

    def test_instantiate_with_all_fields(self) -> None:
        """T05: 实例化 ApiResponse 并传入全部字段。"""
        resp = ApiResponse(code=200, message="success", data={"key": "val"})
        assert resp.code == 200
        assert resp.message == "success"
        assert resp.data == {"key": "val"}

    def test_instantiate_without_data_defaults_to_none(self) -> None:
        """T06: 不传 data 时，data 默认为 None。"""
        resp = ApiResponse(code=404, message="not found")
        assert resp.code == 404
        assert resp.message == "not found"
        assert resp.data is None

    def test_instantiate_with_data_none_explicit(self) -> None:
        """显式传入 data=None。"""
        resp = ApiResponse(code=400, message="bad request", data=None)
        assert resp.code == 400
        assert resp.message == "bad request"
        assert resp.data is None


class TestApiResponseModelDump:
    """测试 model_dump 输出格式。"""

    def test_model_dump_with_data_dict(self) -> None:
        """验证 .model_dump() 输出格式正确，data 为 dict。"""
        resp = ApiResponse(code=200, message="success", data={"key": "val"})
        dumped = resp.model_dump()
        assert dumped == {"code": 200, "message": "success", "data": {"key": "val"}}

    def test_model_dump_with_data_none(self) -> None:
        """验证 .model_dump() 在 data=None 时输出格式正确。"""
        resp = ApiResponse(code=404, message="not found")
        dumped = resp.model_dump()
        assert dumped == {"code": 404, "message": "not found", "data": None}

    def test_model_dump_with_data_list(self) -> None:
        """验证 data 为列表时的 model_dump。"""
        resp = ApiResponse(code=200, message="success", data=[1, 2, 3])
        dumped = resp.model_dump()
        assert dumped == {"code": 200, "message": "success", "data": [1, 2, 3]}

    def test_model_dump_with_data_str(self) -> None:
        """验证 data 为字符串时的 model_dump。"""
        resp = ApiResponse(code=200, message="success", data="hello")
        dumped = resp.model_dump()
        assert dumped == {"code": 200, "message": "success", "data": "hello"}

    def test_model_dump_with_data_pydantic_model(self) -> None:
        """验证 data 为 Pydantic 模型时的 model_dump。"""
        class InnerModel(BaseModel):
            name: str
            value: int

        inner = InnerModel(name="test", value=42)
        resp = ApiResponse(code=200, message="success", data=inner)
        dumped = resp.model_dump()
        assert dumped["code"] == 200
        assert dumped["message"] == "success"
        assert dumped["data"] == {"name": "test", "value": 42}


class TestApiResponseModelDumpJson:
    """测试 model_dump_json 输出。"""

    def test_model_dump_json_basic(self) -> None:
        """验证 JSON 序列化输出格式。"""
        resp = ApiResponse(code=200, message="success", data={"key": "val"})
        json_str = resp.model_dump_json()
        assert '"code":200' in json_str
        assert '"message":"success"' in json_str
        assert '"key":"val"' in json_str

    def test_model_dump_json_with_none_data(self) -> None:
        """验证 data=None 时的 JSON 序列化。"""
        resp = ApiResponse(code=404, message="not found")
        json_str = resp.model_dump_json()
        assert '"code":404' in json_str
        assert '"data":null' in json_str


class TestApiResponseTypeAnnotations:
    """验证类型注解正确性。"""

    def test_code_is_int(self) -> None:
        """code 字段为 int 类型。"""
        resp = ApiResponse(code=200, message="ok")
        assert isinstance(resp.code, int)

    def test_message_is_str(self) -> None:
        """message 字段为 str 类型。"""
        resp = ApiResponse(code=200, message="success")
        assert isinstance(resp.message, str)

    def test_data_is_optional(self) -> None:
        """data 为 Optional，默认值为 None。"""
        resp = ApiResponse(code=200, message="ok")
        assert resp.data is None

    def test_data_accepts_any_type(self) -> None:
        """data 接受任意类型 (Any)。"""
        # dict
        resp = ApiResponse(code=200, message="ok", data={"a": 1})
        assert isinstance(resp.data, dict)
        # list
        resp = ApiResponse(code=200, message="ok", data=[1, 2, 3])
        assert isinstance(resp.data, list)
        # str
        resp = ApiResponse(code=200, message="ok", data="string")
        assert isinstance(resp.data, str)
        # int
        resp = ApiResponse(code=200, message="ok", data=42)
        assert isinstance(resp.data, int)
        # None
        resp = ApiResponse(code=200, message="ok")
        assert resp.data is None


class TestApiResponseEdgeCases:
    """边界情况测试。"""

    def test_empty_message(self) -> None:
        """message 可以为空字符串。"""
        resp = ApiResponse(code=500, message="", data=None)
        assert resp.message == ""

    def test_very_long_message(self) -> None:
        """message 可以是长字符串。"""
        long_msg = "error: " + "x" * 1000
        resp = ApiResponse(code=500, message=long_msg, data=None)
        assert len(resp.message) == len(long_msg)

    def test_nested_data(self) -> None:
        """data 支持嵌套结构。"""
        nested: dict[str, Any] = {"level1": {"level2": {"level3": "deep"}}}
        resp = ApiResponse(code=200, message="success", data=nested)
        data = resp.data
        assert data is not None
        assert data["level1"]["level2"]["level3"] == "deep"

    def test_data_as_empty_dict(self) -> None:
        """data 可以是空 dict。"""
        resp = ApiResponse(code=200, message="success", data={})
        assert resp.data == {}

    def test_data_as_empty_list(self) -> None:
        """data 可以是空 list。"""
        resp = ApiResponse(code=200, message="success", data=[])
        assert resp.data == []


class TestApiResponseNoConflictWithRagQuery:
    """验证 schemas/common.py 与 schemas/rag_query.py 的 ApiResponse 各自独立。"""

    def test_separate_modules_independent_imports(self) -> None:
        """两个 ApiResponse 来自不同模块，各自独立使用。"""
        from schemas.common import ApiResponse as CommonApiResponse
        from schemas.rag_query import ApiResponse as RagApiResponse

        assert CommonApiResponse is not RagApiResponse

    def test_common_api_response_data_is_any(self) -> None:
        """common.ApiResponse.data 为 Optional[Any]，接受任意值。"""
        resp = ApiResponse(code=200, message="ok", data=["any", "type"])
        assert resp.data == ["any", "type"]

    def test_rag_api_response_data_is_rag_response(self) -> None:
        """rag_query.ApiResponse.data 为 Optional[RAGResponse]。"""
        from schemas.rag_query import ApiResponse as RagApiResponse
        from schemas.rag_query import RAGResponse

        rag_data = RAGResponse(
            question="test?",
            answer="test answer",
            sources=["src1"],
            keywords="kw",
        )
        resp = RagApiResponse(code=200, message="success", data=rag_data)
        assert resp.data is not None
        assert resp.data.answer == "test answer"
