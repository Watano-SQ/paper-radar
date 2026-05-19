from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from src.ranking.config import merge_scoring_config


DEFAULT_APP_CONFIG: dict[str, Any] = {
    "app": {
        "data_dir": "data",
        "raw_dir": "data/raw",
        "exports_dir": "data/exports",
        "reports_dir": "data/reports",
        "logs_dir": "logs",
        "database_path": "data/papers.sqlite",
    },
    "files": {
        "export_filename_template": "candidates_{week}.jsonl",
        "weekly_report_filename_template": "weekly_candidates_{week}.md",
        "reject_log_filename_template": "rejected_candidates_{week}.md",
        "score_audit_filename_template": "score_audit_{week}.md",
    },
    "obsidian": {
        "enabled": False,
        "vault_dir": "",
        "weekly_report_dir": "Knowledge Radar/Weekly",
        "export_dir": "Knowledge Radar/Exports",
    },
}


ENV_CONFIG_DIR = "PAPER_RADAR_CONFIG_DIR"
ENV_DATA_DIR = "PAPER_RADAR_DATA_DIR"
ENV_REPORTS_DIR = "PAPER_RADAR_REPORTS_DIR"
ENV_EXPORTS_DIR = "PAPER_RADAR_EXPORTS_DIR"
ENV_LOGS_DIR = "PAPER_RADAR_LOGS_DIR"
ENV_DATABASE_PATH = "PAPER_RADAR_DATABASE_PATH"


@dataclass(frozen=True)
class AppPaths:
    project_root: Path
    config_dir: Path
    sources_config_path: Path
    topics_config_path: Path
    app_config_path: Path
    scoring_config_path: Path
    data_dir: Path
    raw_dir: Path
    exports_dir: Path
    reports_dir: Path
    logs_dir: Path
    database_path: Path


@dataclass(frozen=True)
class RuntimeConfig:
    paths: AppPaths
    app: dict[str, Any]
    sources: dict[str, Any]
    topics: dict[str, Any]
    scoring: dict[str, Any]


def load_runtime_config(
    *,
    config_dir: Path | str | None = None,
    project_root: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> RuntimeConfig:
    env = environ if environ is not None else os.environ
    resolved_project_root = _resolve_project_root(project_root)
    resolved_config_dir = _resolve_config_dir(config_dir, resolved_project_root, env)
    if project_root is None and (config_dir is not None or env.get(ENV_CONFIG_DIR)):
        resolved_project_root = resolved_config_dir.parent

    app_config_path = resolved_config_dir / "app.yaml"
    sources_config_path = resolved_config_dir / "sources.yaml"
    topics_config_path = resolved_config_dir / "topics.yaml"
    scoring_config_path = resolved_config_dir / "scoring.yaml"

    app_config = _deep_merge(DEFAULT_APP_CONFIG, _load_yaml(app_config_path))
    sources_config = _load_yaml(sources_config_path)
    topics_config = _load_yaml(topics_config_path)
    scoring_config = merge_scoring_config(_load_yaml(scoring_config_path))

    paths = _build_paths(
        project_root=resolved_project_root,
        config_dir=resolved_config_dir,
        app_config_path=app_config_path,
        sources_config_path=sources_config_path,
        topics_config_path=topics_config_path,
        scoring_config_path=scoring_config_path,
        app_config=app_config,
        env=env,
    )
    return RuntimeConfig(
        paths=paths,
        app=app_config,
        sources=sources_config.get("sources", {}),
        topics=topics_config.get("lanes", {}),
        scoring=scoring_config,
    )


def _resolve_project_root(project_root: Path | str | None) -> Path:
    if project_root is not None:
        return Path(project_root).expanduser().resolve()
    cwd = Path.cwd()
    if (cwd / "config" / "sources.yaml").exists():
        return cwd.resolve()
    return Path(__file__).resolve().parents[2]


def _resolve_config_dir(
    config_dir: Path | str | None,
    project_root: Path,
    env: Mapping[str, str],
) -> Path:
    value = config_dir or env.get(ENV_CONFIG_DIR)
    if value is None:
        return project_root / "config"
    return _resolve_path(Path(value).expanduser(), project_root)


def _build_paths(
    *,
    project_root: Path,
    config_dir: Path,
    app_config_path: Path,
    sources_config_path: Path,
    topics_config_path: Path,
    scoring_config_path: Path,
    app_config: dict[str, Any],
    env: Mapping[str, str],
) -> AppPaths:
    app = app_config.get("app", {})
    default_app = DEFAULT_APP_CONFIG["app"]
    data_dir = _resolve_path(Path(env.get(ENV_DATA_DIR, app.get("data_dir", default_app["data_dir"]))), project_root)

    raw_dir = _resolve_related_data_path(
        value=app.get("raw_dir", default_app["raw_dir"]),
        default_value=default_app["raw_dir"],
        data_dir=data_dir,
        fallback_name="raw",
        project_root=project_root,
    )
    exports_dir = _resolve_related_data_path(
        value=env.get(ENV_EXPORTS_DIR, app.get("exports_dir", default_app["exports_dir"])),
        default_value=default_app["exports_dir"],
        data_dir=data_dir,
        fallback_name="exports",
        project_root=project_root,
    )
    reports_dir = _resolve_related_data_path(
        value=env.get(ENV_REPORTS_DIR, app.get("reports_dir", default_app["reports_dir"])),
        default_value=default_app["reports_dir"],
        data_dir=data_dir,
        fallback_name="reports",
        project_root=project_root,
    )
    database_path = _resolve_related_data_path(
        value=env.get(ENV_DATABASE_PATH, app.get("database_path", default_app["database_path"])),
        default_value=default_app["database_path"],
        data_dir=data_dir,
        fallback_name="papers.sqlite",
        project_root=project_root,
    )
    logs_dir = _resolve_path(Path(env.get(ENV_LOGS_DIR, app.get("logs_dir", default_app["logs_dir"]))), project_root)

    return AppPaths(
        project_root=project_root,
        config_dir=config_dir,
        sources_config_path=sources_config_path,
        topics_config_path=topics_config_path,
        app_config_path=app_config_path,
        scoring_config_path=scoring_config_path,
        data_dir=data_dir,
        raw_dir=raw_dir,
        exports_dir=exports_dir,
        reports_dir=reports_dir,
        logs_dir=logs_dir,
        database_path=database_path,
    )


def _resolve_related_data_path(
    *,
    value: str | Path,
    default_value: str,
    data_dir: Path,
    fallback_name: str,
    project_root: Path,
) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    if str(value).replace("\\", "/") == default_value:
        return (data_dir / fallback_name).resolve()
    return (project_root / path).resolve()


def _resolve_path(path: Path, project_root: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (project_root / path).resolve()


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
