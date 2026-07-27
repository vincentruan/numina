"""MCP server 管理路由（per-family）。"""

import json
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult, require_owner
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.family_mcp_server import FamilyMCPServer
from apps.backend.app.models.user import User
from apps.backend.app.services.ai_crypto import decrypt_api_key, encrypt_api_key

router = APIRouter(prefix="/ai/mcp", tags=["ai-mcp"])
logger = logging.getLogger(__name__)

ALLOWED_TRANSPORTS = {"sse", "stdio"}


# ── Schemas ──────────────────────────────────────────────────────────────────

class MCPServerCreate(BaseModel):
    name: str
    url: str
    transport: str = "sse"
    env_vars: dict[str, str] | None = None
    is_enabled: bool = True
    mcp_type: str = "general"


class MCPServerUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    transport: str | None = None
    env_vars: dict[str, str] | None = None
    is_enabled: bool | None = None
    mcp_type: str | None = None


class MCPServerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    url: str
    transport: str
    env_vars: dict[str, str]  # empty dict when not set or caller lacks permission
    is_enabled: bool
    mcp_type: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _decrypt_env_vars(server: FamilyMCPServer) -> dict[str, str]:
    """Decrypt env_vars JSON; returns empty dict if not set or decryption fails."""
    if not server.env_vars_encrypted:
        return {}
    raw = decrypt_api_key(server.env_vars_encrypted)
    if not raw:
        return {}
    try:
        parsed: dict[str, str] = json.loads(raw)
        return parsed
    except Exception:
        return {}


def _to_response(server: FamilyMCPServer, include_env: bool = False) -> MCPServerResponse:
    return MCPServerResponse(
        id=server.id,
        name=server.name,
        url=server.url,
        transport=server.transport,
        env_vars=_decrypt_env_vars(server) if include_env else {},
        is_enabled=server.is_enabled,
        mcp_type=server.mcp_type or "general",
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[MCPServerResponse])
def list_mcp_servers(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> list[MCPServerResponse]:
    """列出当前家庭所有 MCP server（env_vars 仅 owner 可见）。"""
    servers = (
        db.query(FamilyMCPServer)
        .filter(FamilyMCPServer.family_id == current_user.family_id)
        .order_by(FamilyMCPServer.id)
        .all()
    )
    is_owner = current_user.role == "owner"
    return [_to_response(s, include_env=is_owner) for s in servers]


@router.post("", response_model=MCPServerResponse, status_code=201)
def create_mcp_server(
    payload: MCPServerCreate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> MCPServerResponse:
    """创建 MCP server（仅 owner）。"""
    if payload.transport not in ALLOWED_TRANSPORTS:
        raise AppError(ErrorCode.VALIDATION_ERROR, f"transport 必须是 {ALLOWED_TRANSPORTS} 之一")

    # [Security] Prevent users from creating servers with mcp_type="backend",
    # which is reserved for system-created internal MCP servers only.
    if payload.mcp_type == "backend":
        raise AppError(ErrorCode.FORBIDDEN, "mcp_type 'backend' 为系统保留类型")

    env_encrypted: str | None = None
    if payload.env_vars:
        env_encrypted = encrypt_api_key(json.dumps(payload.env_vars))

    server = FamilyMCPServer(
        family_id=current_user.family_id,
        name=payload.name,
        url=payload.url,
        transport=payload.transport,
        env_vars_encrypted=env_encrypted,
        is_enabled=payload.is_enabled,
        mcp_type=payload.mcp_type,
    )
    db.add(server)
    db.commit()
    db.refresh(server)
    return _to_response(server, include_env=True)


@router.put("/{server_id}", response_model=MCPServerResponse)
def update_mcp_server(
    server_id: int,
    payload: MCPServerUpdate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> MCPServerResponse:
    """更新 MCP server（仅 owner）。"""
    server = db.query(FamilyMCPServer).filter(
        FamilyMCPServer.id == server_id,
        FamilyMCPServer.family_id == current_user.family_id,
    ).first()
    if not server:
        raise AppError(ErrorCode.NOT_FOUND)

    # [Security] Protect backend-type MCP servers from frontend modification.
    # The "Numina Backend MCP" server is auto-created and its URL must remain
    # internal to prevent agent auth token leakage or data exfiltration.
    if server.mcp_type == "backend":
        raise AppError(ErrorCode.FORBIDDEN, "系统内置 MCP 服务器不可修改")

    if payload.transport is not None:
        if payload.transport not in ALLOWED_TRANSPORTS:
            raise AppError(ErrorCode.VALIDATION_ERROR, f"transport 必须是 {ALLOWED_TRANSPORTS} 之一")
        server.transport = payload.transport
    if payload.name is not None:
        server.name = payload.name
    if payload.url is not None:
        server.url = payload.url
    if payload.env_vars is not None:
        server.env_vars_encrypted = encrypt_api_key(json.dumps(payload.env_vars))
    if payload.is_enabled is not None:
        server.is_enabled = payload.is_enabled
    if payload.mcp_type is not None:
        server.mcp_type = payload.mcp_type

    db.commit()
    db.refresh(server)
    return _to_response(server, include_env=True)


@router.delete("/{server_id}", status_code=204)
def delete_mcp_server(
    server_id: int,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> None:
    """删除 MCP server（仅 owner）。"""
    server = db.query(FamilyMCPServer).filter(
        FamilyMCPServer.id == server_id,
        FamilyMCPServer.family_id == current_user.family_id,
    ).first()
    if not server:
        raise AppError(ErrorCode.NOT_FOUND)

    # [Security] Protect backend-type MCP servers from deletion.
    if server.mcp_type == "backend":
        raise AppError(ErrorCode.FORBIDDEN, "系统内置 MCP 服务器不可删除")

    db.delete(server)
    db.commit()
