"""
Schema v1.0.0 - Complete metadata specification for Cursor MCP
Based on ChatGPT recommendations 2025-11-05
"""

from typing import Literal, Optional, List, Dict, Any
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from timestamps import iso_utc, unix_timestamp
from hashing import hash_content
from deterministic_ids import generate_upsert_id
from runtime import get_runtime_versions, get_git_info, get_env_context

SCHEMA_VERSION = "1.0.0"

INTENT_ENUM = Literal["ask", "write", "refactor", "fix", "plan", "decide"]
CATEGORY_ENUM = Literal["config", "code", "bug", "decision", "architecture", "docs", "command"]
PRIORITY_ENUM = Literal["high", "medium", "low"]
ROLE_ENUM = Literal["user", "assistant"]
CURSOR_MODE_ENUM = Literal["chat", "composer"]
INPUT_METHOD_ENUM = Literal["keyboard", "voice", "paste", "tool"]
UI_SURFACE_ENUM = Literal["chat", "inline", "composer"]
PII_PRESENCE_ENUM = Literal["none", "possible", "confirmed"]
RETENTION_POLICY_ENUM = Literal["dev", "stage", "prod", "purge_after_30d"]
GDPR_BASIS_ENUM = Literal["consent", "legitimate_interest", "contract"]
WRITE_STATUS_ENUM = Literal["ok", "retry", "fail"]
SIMILARITY_METRIC_ENUM = Literal["cosine", "dot", "euclid"]

def build_complete_metadata(
	text: str,
	chat_id: str,
	turn_id: int,
	role: ROLE_ENUM = "assistant",
	intent: INTENT_ENUM = "ask",
	category: CATEGORY_ENUM = "code",
	priority: PRIORITY_ENUM = "medium",
	cursor_mode: CURSOR_MODE_ENUM = "chat",
	project_root: str = "C:\\DEV",
	ai_model: str = "claude-sonnet-4.5",
	ai_provider: str = "anthropic",
	tags: Optional[List[str]] = None,
	topic: Optional[str] = None,
	recent_hour_context: Optional[str] = None,
	**kwargs
) -> Dict[str, Any]:

	ts = iso_utc()
	unix_ts = unix_timestamp()
	content_hash = hash_content(text)
	upsert_id = generate_upsert_id(chat_id, turn_id)

	runtime = get_runtime_versions()
	git = get_git_info(Path(project_root))
	env = get_env_context()

	metadata = {
		"schema_version": SCHEMA_VERSION,

		"content_sha256": content_hash,
		"upsert_id": upsert_id,
		"redacted": kwargs.get("redacted", False),

		"ai_model": ai_model,
		"ai_model_version": kwargs.get("ai_model_version", "4.5.2025-10-15"),
		"ai_provider": ai_provider,
		"ai_provider_region": kwargs.get("ai_provider_region", "us-east-1"),
		"cursor_mode": cursor_mode,
		"system_prompt_sha256": kwargs.get("system_prompt_sha256"),

		"sampling": {
			"temperature": kwargs.get("temperature", 0.7),
			"top_p": kwargs.get("top_p", 0.9),
			"max_tokens": kwargs.get("max_tokens", 4096)
		},

		"token_usage": {
			"input": kwargs.get("input_tokens", 0),
			"output": kwargs.get("output_tokens", 0),
			"total": kwargs.get("total_tokens", 0)
		},

		"latency_ms": kwargs.get("latency_ms", 0),
		"cost_usd": kwargs.get("cost_usd", 0.0),
		"safety_events": kwargs.get("safety_events", []),

		"ts": ts,
		"unix_timestamp": unix_ts,
		"date": datetime.fromisoformat(ts.replace('Z', '+00:00')).strftime("%Y-%m-%d"),
		"time": datetime.fromisoformat(ts.replace('Z', '+00:00')).strftime("%H:%M:%S"),

		"tools_used": kwargs.get("tools_used", []),

		"runtime": runtime,

		"project": {
			"root": project_root,
			"name": kwargs.get("project_name", Path(project_root).name),
			"subproject": kwargs.get("subproject"),
			"workspace": kwargs.get("workspace"),
			"workspace_fingerprint": kwargs.get("workspace_fingerprint")
		},

		"git": git if git else {},

		"file": kwargs.get("file"),
		"code": kwargs.get("code"),

		"environment": env,

		"intent": intent,
		"category": category,
		"topic": topic,
		"priority": priority,
		"tags": tags or [],

		"role": role,
		"chat_id": chat_id,
		"turn_id": turn_id,
		"conversation_length": kwargs.get("conversation_length", 1),

		"recent_hour_context": recent_hour_context,
		"window": kwargs.get("window", "last_1h"),
		"items_considered": kwargs.get("items_considered", 0),
		"topics": kwargs.get("topics", []),
		"decisions": kwargs.get("decisions", []),
		"todos": kwargs.get("todos", []),

		"user_id_pseudonymous": kwargs.get("user_id_pseudonymous"),
		"input_method": kwargs.get("input_method", "keyboard"),
		"ui_surface": kwargs.get("ui_surface", "chat"),
		"keyboard_layout": kwargs.get("keyboard_layout"),
		"locale": kwargs.get("locale", "en-US"),
		"timezone": kwargs.get("timezone", "America/New_York"),

		"mcp": {
			"server": kwargs.get("mcp_server", "mcp-server-qdrant"),
			"version": kwargs.get("mcp_version", "0.5.2"),
			"transport": kwargs.get("mcp_transport", "sse"),
			"server_instance_id": kwargs.get("mcp_instance_id"),
			"tool_latency_ms": kwargs.get("tool_latency_ms", {})
		},

		"qdrant_write_status": kwargs.get("qdrant_write_status", "ok"),
		"retry": {
			"count": kwargs.get("retry_count", 0),
			"backoff_ms": kwargs.get("retry_backoff_ms", 0)
		},

		"embedding_model": kwargs.get("embedding_model", "fast-all-minilm-l6-v2"),
		"embedding_dim": kwargs.get("embedding_dim", 384),
		"similarity_metric": kwargs.get("similarity_metric", "cosine"),
		"chunking": {
			"strategy": kwargs.get("chunking_strategy", "by_turn"),
			"max_chars": kwargs.get("chunking_max_chars", 4000),
			"overlap": kwargs.get("chunking_overlap", 128)
		},

		"content_length": len(text),
		"truncated": kwargs.get("truncated", False),
		"language": kwargs.get("language", "en"),
		"citations": kwargs.get("citations", []),

		"pii_presence": kwargs.get("pii_presence", "none"),
		"retention_policy": kwargs.get("retention_policy", "dev"),
		"gdpr_basis": kwargs.get("gdpr_basis", "legitimate_interest"),
		"redaction_rules": {
			"emails": True,
			"secrets": True
		},

		"dev_container": {
			"active": kwargs.get("dev_container_active", False),
			"image": kwargs.get("dev_container_image")
		},
		"language_server": kwargs.get("language_server"),
		"build_target": kwargs.get("build_target"),
		"test_scope": kwargs.get("test_scope"),
		"commands_ran": kwargs.get("commands_ran", []),
		"artifacts": kwargs.get("artifacts", []),
		"guardrails": {
			"passed": kwargs.get("guardrails_passed", []),
			"failed": kwargs.get("guardrails_failed", [])
		},
		"rollback_hint": kwargs.get("rollback_hint")
	}

	metadata = {k: v for k, v in metadata.items() if v is not None and v != {} and v != []}

	return metadata

def validate_metadata(metadata: Dict[str, Any]) -> tuple[bool, List[str]]:
	errors = []

	if "schema_version" not in metadata:
		errors.append("Missing schema_version")

	required_fields = [
		"content_sha256", "upsert_id", "ai_model", "ai_provider",
		"ts", "unix_timestamp", "runtime", "project",
		"intent", "category", "role", "chat_id", "turn_id"
	]

	for field in required_fields:
		if field not in metadata:
			errors.append(f"Missing required field: {field}")

	if "intent" in metadata and metadata["intent"] not in ["ask", "write", "refactor", "fix", "plan", "decide"]:
		errors.append(f"Invalid intent: {metadata['intent']}")

	if "category" in metadata and metadata["category"] not in ["config", "code", "bug", "decision", "architecture", "docs", "command"]:
		errors.append(f"Invalid category: {metadata['category']}")

	if "role" in metadata and metadata["role"] not in ["user", "assistant"]:
		errors.append(f"Invalid role: {metadata['role']}")

	import json
	payload_size = len(json.dumps(metadata))
	if payload_size > 100000:  # 100KB limit
		errors.append(f"Payload too large: {payload_size} bytes (max 100KB)")

	return (len(errors) == 0, errors)

__all__ = [
	"build_complete_metadata",
	"validate_metadata",
	"SCHEMA_VERSION",
	"INTENT_ENUM",
	"CATEGORY_ENUM",
	"PRIORITY_ENUM",
	"ROLE_ENUM"
]
