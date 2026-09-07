from __future__ import annotations

from uuid import UUID

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from pde_operator.config import Settings
from pde_operator.utils.artifact_utils import ArtifactKind, ArtifactUtils, ArtifactObject, ArtifactNotFoundError
from pde_operator.utils.input_crypto_utils import InputCryptoUtils, INPUT_CONTENT_TYPE


class ArtifactsService:
    def __init__(self, settings: Settings, s3_client: BaseClient | None = None) -> None:
        self._settings = settings
        self._s3 = s3_client

    def _client(self) -> BaseClient:
        if self._s3 is None:
            self._s3 = boto3.client(
                "s3",
                endpoint_url=self._settings.minio_endpoint,
                aws_access_key_id=self._settings.minio_access_key,
                aws_secret_access_key=self._settings.minio_secret_key,
                region_name=self._settings.minio_region,
            )
        return self._s3

    def put_artifact(self, run_id: UUID, kind: ArtifactKind, data: bytes) -> str:
        key = self._key(run_id, kind)
        self._put_bytes(key, data, ArtifactUtils.content_type(kind))
        return key

    def get_artifact(self, run_id: UUID, kind: str | ArtifactKind) -> ArtifactObject:
        parsed = kind if isinstance(kind, ArtifactKind) else ArtifactUtils.parse_artifact_kind(kind)
        return self._get_object(self._key(run_id, parsed))

    def put_run_input(self, run_id: UUID, data: bytes) -> str:
        key = InputCryptoUtils.input_key(run_id)
        self._put_bytes(key, data, INPUT_CONTENT_TYPE)
        return key

    def get_run_input_bytes(self, run_id: UUID) -> bytes:
        obj = self._get_object(InputCryptoUtils.input_key(run_id))
        try:
            return obj.body.read()
        finally:
            obj.body.close()

    def delete_run_artifacts(self, run_id: UUID) -> int:
        """Delete all objects under `{run_id}/`. Returns number of deleted keys."""
        prefix = f"{run_id}/"
        client = self._client()
        bucket = self._settings.minio_bucket
        deleted = 0
        continuation: str | None = None
        while True:
            kwargs: dict = {"Bucket": bucket, "Prefix": prefix}
            if continuation:
                kwargs["ContinuationToken"] = continuation
            response = client.list_objects_v2(**kwargs)
            keys = [{"Key": obj["Key"]} for obj in response.get("Contents") or []]
            if keys:
                client.delete_objects(Bucket=bucket, Delete={"Objects": keys, "Quiet": True})
                deleted += len(keys)
            if not response.get("IsTruncated"):
                break
            continuation = response.get("NextContinuationToken")
        return deleted

    # noinspection PyMethodMayBeStatic
    def _key(self, run_id: UUID, kind: ArtifactKind) -> str:
        return f"{run_id}/{ArtifactUtils.filename(kind)}"

    def _put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self._client().put_object(
            Bucket=self._settings.minio_bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def _get_object(self, key: str) -> ArtifactObject:
        try:
            response = self._client().get_object(Bucket=self._settings.minio_bucket, Key=key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                raise ArtifactNotFoundError(key) from exc
            raise
        return ArtifactObject(
            key=key,
            body=response["Body"],
            content_type=response.get("ContentType") or "application/octet-stream",
            content_length=response.get("ContentLength"),
        )
