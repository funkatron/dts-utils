"""Serialize model index records for MCP tool responses."""

from __future__ import annotations

from dataclasses import asdict

from dts_utils.model_index.parse import ModelRecord


def model_record_to_dict(record: ModelRecord) -> dict[str, object]:
    return {
        "id": record.id,
        "name": record.name,
        "type": record.type,
        "model_family": record.model_family,
        "source_url": record.source_url,
        "huggingface_repo_id": record.huggingface_repo_id,
        "download_url": record.download_url,
        "author": record.author,
        "license": record.license,
        "tags": list(record.tags),
        "sha256": record.sha256,
        "metadata_path": record.metadata_path,
        "downloads": record.downloads,
        "likes": record.likes,
        "warnings": list(record.warnings),
    }
