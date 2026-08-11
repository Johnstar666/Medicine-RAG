"""tests/domain/test_constants.py --- 测试 domain/constants.py 中的枚举类."""

from __future__ import annotations

import io
import sys

from domain.constants import (
    ErrorCode,
    IngestionStatus,
    IngestResultStatus,
    SearchItemStatus,
    _run_self_test,
)

# ---------------------------------------------------------------------------
# IngestionStatus
# ---------------------------------------------------------------------------

class TestIngestionStatus:
    """测试 IngestionStatus 枚举。"""

    def test_member_count(self) -> None:
        """应包含 4 个成员。"""
        members = list(IngestionStatus)
        assert len(members) == 4

    def test_values(self) -> None:
        """验证每个成员的字符串值。"""
        assert IngestionStatus.UNINGESTED.value == "uningested"
        assert IngestionStatus.INGESTING.value == "ingesting"
        assert IngestionStatus.INGESTED.value == "ingested"
        assert IngestionStatus.FAILED.value == "failed"

    def test_is_string_enum(self) -> None:
        """验证基类是 str 和 Enum。"""
        assert issubclass(IngestionStatus, str)
        from enum import Enum as _Enum
        assert issubclass(IngestionStatus, _Enum)

    def test_db_field_values(self) -> None:
        """T07: 验证与数据库 ingestion_status 字段的可选值完全一致。"""
        allowed_db_values = {"uningested", "ingesting", "ingested", "failed"}
        actual_values = {m.value for m in IngestionStatus}
        assert actual_values == allowed_db_values

    def test_member_access_by_value(self) -> None:
        """验证可以通过字符串值访问成员。"""
        assert IngestionStatus("uningested") == IngestionStatus.UNINGESTED
        assert IngestionStatus("ingesting") == IngestionStatus.INGESTING
        assert IngestionStatus("ingested") == IngestionStatus.INGESTED
        assert IngestionStatus("failed") == IngestionStatus.FAILED


# ---------------------------------------------------------------------------
# ErrorCode
# ---------------------------------------------------------------------------

class TestErrorCode:
    """测试 ErrorCode 枚举。"""

    def test_success_members(self) -> None:
        """验证成功类错误码。"""
        assert ErrorCode.SUCCESS.value == 200

    def test_client_error_members(self) -> None:
        """验证客户端错误码 (400-499)。"""
        assert ErrorCode.BAD_REQUEST.value == 400
        assert ErrorCode.PMID_NOT_FOUND.value == 404

    def test_server_error_members(self) -> None:
        """验证服务端错误码 (500-599)。"""
        assert ErrorCode.INTERNAL_ERROR.value == 500
        assert ErrorCode.SERVICE_NOT_INITIALIZED.value == 500
        assert ErrorCode.PUBMED_API_UNAVAILABLE.value == 503
        assert ErrorCode.PG_UNAVAILABLE.value == 503
        assert ErrorCode.CHROMADB_UNAVAILABLE.value == 503

    def test_business_error_members(self) -> None:
        """验证业务级部分失败错误码 (1000+)。"""
        assert ErrorCode.INGESTION_PARTIAL_FAILURE.value == 1001
        assert ErrorCode.SEARCH_PARTIAL_FAILURE.value == 1002

    def test_is_int_enum(self) -> None:
        """验证基类是 int 和 Enum。"""
        assert issubclass(ErrorCode, int)
        from enum import Enum as _Enum
        assert issubclass(ErrorCode, _Enum)

    def test_unique_semantic_names(self) -> None:
        """T08: 验证 ErrorCode 中 HTTP 状态码与 FastAPI HTTPException 的对应关系。

        同值成员（如 INTERNAL_ERROR 和 SERVICE_NOT_INITIALIZED 均为 500）
        虽然 Python Enum 中后者是前者的别名，但各自的语义名称应存在。
        """
        # 主成员（非别名）应可直接访问
        assert ErrorCode.INTERNAL_ERROR.value == 500
        assert ErrorCode.PUBMED_API_UNAVAILABLE.value == 503

        # 别名成员应可解析
        assert ErrorCode.SERVICE_NOT_INITIALIZED.value == 500
        assert ErrorCode.PG_UNAVAILABLE.value == 503
        assert ErrorCode.CHROMADB_UNAVAILABLE.value == 503

    def test_http_code_ranges(self) -> None:
        """验证错误码范围符合约定的 HTTP 状态码区间。"""
        assert 200 <= ErrorCode.SUCCESS.value <= 299
        assert 400 <= ErrorCode.BAD_REQUEST.value <= 499
        assert 400 <= ErrorCode.PMID_NOT_FOUND.value <= 499
        assert 500 <= ErrorCode.INTERNAL_ERROR.value <= 599
        assert ErrorCode.INGESTION_PARTIAL_FAILURE.value >= 1000
        assert ErrorCode.SEARCH_PARTIAL_FAILURE.value >= 1000


# ---------------------------------------------------------------------------
# IngestResultStatus
# ---------------------------------------------------------------------------

class TestIngestResultStatus:
    """测试 IngestResultStatus 枚举。"""

    def test_member_count(self) -> None:
        """应包含 3 个成员。"""
        members = list(IngestResultStatus)
        assert len(members) == 3

    def test_values(self) -> None:
        """验证每个成员的字符串值。"""
        assert IngestResultStatus.INGESTED.value == "ingested"
        assert IngestResultStatus.ALREADY_INGESTED.value == "already_ingested"
        assert IngestResultStatus.FAILED.value == "failed"

    def test_is_string_enum(self) -> None:
        """验证基类是 str 和 Enum。"""
        assert issubclass(IngestResultStatus, str)
        from enum import Enum as _Enum
        assert issubclass(IngestResultStatus, _Enum)

    def test_member_access_by_value(self) -> None:
        """验证可以通过字符串值访问成员。"""
        assert IngestResultStatus("ingested") == IngestResultStatus.INGESTED
        assert (
            IngestResultStatus("already_ingested")
            == IngestResultStatus.ALREADY_INGESTED
        )
        assert IngestResultStatus("failed") == IngestResultStatus.FAILED


# ---------------------------------------------------------------------------
# SearchItemStatus
# ---------------------------------------------------------------------------

class TestSearchItemStatus:
    """测试 SearchItemStatus 枚举。"""

    def test_member_count(self) -> None:
        """应包含 4 个成员。"""
        members = list(SearchItemStatus)
        assert len(members) == 4

    def test_values(self) -> None:
        """验证每个成员的字符串值。"""
        assert SearchItemStatus.INGESTED.value == "ingested"
        assert SearchItemStatus.STORED.value == "stored"
        assert SearchItemStatus.SKIPPED.value == "skipped"
        assert SearchItemStatus.FAILED.value == "failed"

    def test_is_string_enum(self) -> None:
        """验证基类是 str 和 Enum。"""
        assert issubclass(SearchItemStatus, str)
        from enum import Enum as _Enum
        assert issubclass(SearchItemStatus, _Enum)

    def test_member_access_by_value(self) -> None:
        """验证可以通过字符串值访问成员。"""
        assert SearchItemStatus("ingested") == SearchItemStatus.INGESTED
        assert SearchItemStatus("stored") == SearchItemStatus.STORED
        assert SearchItemStatus("skipped") == SearchItemStatus.SKIPPED
        assert SearchItemStatus("failed") == SearchItemStatus.FAILED


# ---------------------------------------------------------------------------
# Integration / cross-enum checks
# ---------------------------------------------------------------------------

def test_error_code_importable() -> None:
    """验证 ErrorCode 可以当作 int 用于比较。"""
    assert ErrorCode.SUCCESS == 200
    assert ErrorCode.BAD_REQUEST == 400
    assert ErrorCode.PMID_NOT_FOUND == 404


def test_ingestion_status_string_comparison() -> None:
    """验证 IngestionStatus 可以当作 str 用于比较。"""
    assert IngestionStatus.INGESTED == "ingested"
    assert IngestionStatus.UNINGESTED == "uningested"


def test_ingest_result_status_string_comparison() -> None:
    """验证 IngestResultStatus 可以当作 str 用于比较。"""
    assert IngestResultStatus.ALREADY_INGESTED == "already_ingested"


def test_search_item_status_string_comparison() -> None:
    """验证 SearchItemStatus 可以当作 str 用于比较。"""
    assert SearchItemStatus.STORED == "stored"


def test_run_self_test_output() -> None:
    """T06: 验证 _run_self_test() 打印所有枚举成员且不抛异常。"""
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        _run_self_test()
    finally:
        sys.stdout = old_stdout
    output = captured.getvalue()
    # 验证每个枚举的标题都出现在输出中
    assert "=== IngestionStatus ===" in output
    assert "=== ErrorCode ===" in output
    assert "=== IngestResultStatus ===" in output
    assert "=== SearchItemStatus ===" in output
    # 验证具体成员值出现在输出中
    assert "UNINGESTED" in output
    assert "uningested" in output
    assert "SUCCESS" in output
    assert "INGESTION_PARTIAL_FAILURE" in output
    assert "ALREADY_INGESTED" in output
    assert "STORED" in output
