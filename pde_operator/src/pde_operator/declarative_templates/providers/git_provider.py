from __future__ import annotations

import hashlib
import shutil
import threading
from pathlib import Path
from typing import Any

from git import Git, Repo
from git.exc import GitCommandError, GitError

from pde_operator.declarative_templates.contract.errors import DeclarativeOptionsProviderError
from pde_operator.declarative_templates.contract.models import EnumOption, FieldSpec


class GitRepoCache:
    """Shallow-clone cache keyed by url+ref; skips re-clone when remote tip SHA is unchanged."""

    _root = Path.home() / ".cache" / "pde-operator" / "git-provider"
    _locks: dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    @classmethod
    def ensure_checkout(cls, url: str, ref: str) -> Path:
        key = hashlib.sha256(f"{url}\0{ref}".encode()).hexdigest()[:24]
        path = cls._root / key
        lock = cls._lock_for(key)
        with lock:
            remote_sha = cls._remote_sha(url, ref)
            marker = path / ".pde-operator-commit"
            if path.is_dir() and marker.is_file() and marker.read_text(encoding="utf-8").strip() == remote_sha:
                return path
            if path.exists():
                shutil.rmtree(path)
            cls._root.mkdir(parents=True, exist_ok=True)
            try:
                Repo.clone_from(url, path, multi_options=["--depth", "1", "--branch", ref, "--single-branch"])
            except (GitCommandError, GitError) as exc:
                if path.exists():
                    shutil.rmtree(path, ignore_errors=True)
                raise DeclarativeOptionsProviderError(f"{GitFilesProvider.INTERFACE_NAME} clone failed for {url}@{ref}: {exc}") from exc
            marker.write_text(remote_sha, encoding="utf-8")
            return path

    @classmethod
    def _lock_for(cls, key: str) -> threading.Lock:
        with cls._locks_guard:
            lock = cls._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                cls._locks[key] = lock
            return lock

    @staticmethod
    def _remote_sha(url: str, ref: str) -> str:
        candidates = (ref, f"refs/heads/{ref}", f"refs/tags/{ref}")
        try:
            git = Git()
            for candidate in candidates:
                output = (git.ls_remote(url, candidate) or "").strip()
                if not output:
                    continue
                sha = output.splitlines()[0].split("\t", 1)[0].strip()
                if sha:
                    return sha
        except (GitCommandError, GitError) as exc:
            raise DeclarativeOptionsProviderError(f"{GitFilesProvider.INTERFACE_NAME} could not resolve {url}@{ref}: {exc}") from exc
        raise DeclarativeOptionsProviderError(f"{GitFilesProvider.INTERFACE_NAME} could not resolve ref '{ref}' at {url}")


class GitFilesProvider:
    INTERFACE_NAME = "GitFiles"

    @staticmethod
    def list_options(field: FieldSpec, context: dict[str, Any]) -> list[EnumOption]:
        _ = context
        data = field.data
        url = GitFilesProvider._require_str(data, "url")
        ref = GitFilesProvider._require_str(data, "ref")
        glob_pattern = GitFilesProvider._require_str(data, "glob")
        select_directories = bool(data.get("select_directories", False))
        strip_extension = bool(data.get("strip_extension", False))
        use_full_path = bool(data.get("use_full_path", False))

        root = GitRepoCache.ensure_checkout(url, ref)
        options: list[EnumOption] = []
        seen: set[str] = set()
        for path in sorted(root.glob(glob_pattern)):
            if GitFilesProvider._is_git_internal(root, path):
                continue
            if not (path.is_dir() if select_directories else path.is_file()):
                continue
            value = GitFilesProvider._option_value(root, path, strip_extension=strip_extension, use_full_path=use_full_path)
            if value in seen:
                continue
            seen.add(value)
            options.append(EnumOption(value=value, label=value))
        return options

    @staticmethod
    def _option_value(root: Path, path: Path, *, strip_extension: bool, use_full_path: bool) -> str:
        relative = path.relative_to(root)
        if use_full_path:
            display = relative.as_posix()
            if strip_extension and path.is_file():
                display = Path(display).with_suffix("").as_posix()
            return display
        name = path.name
        if strip_extension and path.is_file():
            name = path.stem
        return name

    @staticmethod
    def _is_git_internal(root: Path, path: Path) -> bool:
        try:
            return path.relative_to(root).parts[0] == ".git"
        except ValueError:
            return True

    @staticmethod
    def _require_str(data: dict[str, Any], key: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise DeclarativeOptionsProviderError(f"{GitFilesProvider.INTERFACE_NAME} data.{key} is required")
        return value.strip()
