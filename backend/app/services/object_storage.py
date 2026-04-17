from __future__ import annotations

from io import BytesIO
from pathlib import Path
from time import sleep
from typing import Protocol

from minio import Minio
from minio.error import S3Error

from app.core.config import settings


class ObjectStorage(Protocol):
    """对象存储协议。

    让上层只关心“保存原始文件并拿到一个路径”，不关心它到底是本地目录还是 MinIO。
    """

    def save_bytes(self, filename: str, raw: bytes) -> str: ...


class LocalObjectStorage:
    """本地文件对象存储回退实现。"""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or settings.storage_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, filename: str, raw: bytes) -> str:
        target = self.base_dir / filename
        target.write_bytes(raw)
        return str(target)


class MinioObjectStorage:
    """MinIO 对象存储实现。"""

    def __init__(self) -> None:
        self.bucket = settings.minio_bucket
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """确保 bucket 存在。

        MinIO 可能比应用启动稍慢，因此这里做有限次重试。
        """
        last_error: Exception | None = None
        for _ in range(10):
            try:
                exists = self.client.bucket_exists(self.bucket)
                if not exists:
                    self.client.make_bucket(self.bucket)
                return
            except S3Error as exc:
                last_error = exc
                sleep(1)
        raise RuntimeError(f'MinIO bucket check failed: {last_error}') from last_error

    def save_bytes(self, filename: str, raw: bytes) -> str:
        self.client.put_object(self.bucket, filename, BytesIO(raw), len(raw), content_type='application/octet-stream')
        return f's3://{self.bucket}/{filename}'