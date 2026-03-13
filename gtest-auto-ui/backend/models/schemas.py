"""
Pydantic v2 models for all API request/response bodies.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Session / Upload
# ---------------------------------------------------------------------------

class SessionResponse(BaseModel):
    session_id: str


class UploadedFile(BaseModel):
    filename: str
    type: str   # "library" | "header"
    path: str


class UploadResponse(BaseModel):
    uploaded: list[UploadedFile]


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------

class ParseRequest(BaseModel):
    header_filename: str
    include_dirs: list[str] = Field(default_factory=list)
    compiler_args: list[str] = Field(default_factory=lambda: ["-x", "c++"])


class ParseResponse(BaseModel):
    parse_id: str
    status: str
    functions: list[dict[str, Any]]
    parse_errors: list[str]


# ---------------------------------------------------------------------------
# Run / Test configuration
# ---------------------------------------------------------------------------

class ParamConfig(BaseModel):
    name: str
    value: str
    as_null: bool = False


class ExpectedReturn(BaseModel):
    enabled: bool
    comparator: str
    value: str


class TestConfig(BaseModel):
    test_id: str
    function_name: str
    params: list[ParamConfig]
    expected_return: ExpectedReturn
    output_params: list[str] = Field(default_factory=list)


class RunOptions(BaseModel):
    cmake_path: str = "cmake"
    build_type: str = "Debug"
    test_timeout: int = 30
    build_timeout: int = 600
    cmake_extra_args: list[str] = Field(default_factory=list)


class RunRequest(BaseModel):
    parse_id: str
    library_filename: str
    test_configs: list[TestConfig]
    options: RunOptions = Field(default_factory=RunOptions)


class RunResponse(BaseModel):
    run_id: str
    status: str


# ---------------------------------------------------------------------------
# History / Results
# ---------------------------------------------------------------------------

class RunSummary(BaseModel):
    run_id: str
    run_at: str
    overall_status: str
    summary: dict[str, Any]


class HistoryResponse(BaseModel):
    runs: list[RunSummary]
