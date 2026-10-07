"""PostgreSQL-backed durable jobs for analyses that exceed the inline wait budget."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

from app.config import Settings
from app.decision.pipeline import AnalysisResult, DecisionPipeline
from app.privacy.email import preprocess_email
from app.privacy.pii import scrub_pii
from app.schemas import AnalyzeTicketResponse, PiiReport, TicketFlags
from app.services.entitlements import EntitlementService
from app.services.tenants import TenantContext
from app.services.usage import UsageDetails, UsageMeter

logger = logging.getLogger(__name__)

_INSERT_SQL = """
INSERT INTO analysis_jobs (
    tenant_id, api_key_id, idempotency_key, request_hash, external_id,
    anonymized_text, anonymized_subject, pii_entities, order_reference_detected,
    billable, expires_at
)
VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8::jsonb, $9, $10, $11)
ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
RETURNING id::text, status::text, result, error_code, created_at, expires_at
"""
_GET_BY_IDEMPOTENCY_SQL = """
SELECT id::text, request_hash, status::text, result, error_code, created_at, expires_at
FROM analysis_jobs
WHERE tenant_id = $1::uuid AND idempotency_key = $2 AND expires_at > now()
"""
_GET_JOB_SQL = """
SELECT id::text, status::text, result, error_code, created_at, expires_at
FROM analysis_jobs
WHERE id = $1::uuid AND tenant_id = $2::uuid AND expires_at > now()
"""
_DELETE_EXPIRED_SQL = "DELETE FROM analysis_jobs WHERE expires_at <= now()"
_FAIL_EXHAUSTED_SQL = """
UPDATE analysis_jobs
SET status = 'FAILED', error_code = 'max_attempts_exceeded',
    anonymized_text = NULL, anonymized_subject = NULL, pii_entities = '{}'::jsonb,
    lease_expires_at = NULL, lease_token = NULL, updated_at = now()
WHERE attempts >= $1
  AND (status = 'QUEUED' OR (status = 'PROCESSING' AND lease_expires_at <= now()))
"""
_CLAIM_SQL = """
WITH candidate AS (
    SELECT id
    FROM analysis_jobs
    WHERE expires_at > now()
      AND available_at <= now()
      AND attempts < $2
      AND (status = 'QUEUED' OR (status = 'PROCESSING' AND lease_expires_at <= now()))
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
UPDATE analysis_jobs AS job
SET status = 'PROCESSING', attempts = job.attempts + 1,
    lease_expires_at = now() + ($1::double precision * interval '1 second'),
    lease_token = gen_random_uuid(), updated_at = now()
FROM candidate
WHERE job.id = candidate.id
RETURNING job.*
"""
_COMPLETE_SQL = """
UPDATE analysis_jobs
SET status = $3::"AnalysisJobStatus", result = $4::jsonb, error_code = NULL,
    anonymized_text = NULL, anonymized_subject = NULL, pii_entities = '{}'::jsonb,
    lease_expires_at = NULL, lease_token = NULL, updated_at = now()
WHERE id = $1::uuid AND status = 'PROCESSING' AND lease_token = $2::uuid
"""
_RETRY_SQL = """
UPDATE analysis_jobs
SET status = $3::"AnalysisJobStatus", error_code = $4,
    available_at = CASE WHEN $3 = 'QUEUED'
        THEN now() + ($5::double precision * interval '1 second') ELSE available_at END,
    anonymized_text = CASE WHEN $3 = 'FAILED' THEN NULL ELSE anonymized_text END,
    anonymized_subject = CASE WHEN $3 = 'FAILED' THEN NULL ELSE anonymized_subject END,
    pii_entities = CASE WHEN $3 = 'FAILED' THEN '{}'::jsonb ELSE pii_entities END,
    lease_expires_at = NULL, lease_token = NULL, updated_at = now()
WHERE id = $1::uuid AND status = 'PROCESSING' AND lease_token = $2::uuid
"""


class AnalysisJobError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class AnalysisJobSnapshot:
    id: str
    status: str
    result: dict[str, Any] | None
    error_code: str | None
    created_at: datetime
    expires_at: datetime

    @property
    def public_id(self) -> str:
        return f"job_{uuid.UUID(self.id).hex}"

    @property
    def terminal(self) -> bool:
        return self.status in {"SUCCEEDED", "DEGRADED", "FAILED"}


def _decode_json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _snapshot(row: asyncpg.Record) -> AnalysisJobSnapshot:
    return AnalysisJobSnapshot(
        id=row["id"],
        status=row["status"].upper(),
        result=_decode_json(row["result"]) if row["result"] is not None else None,
        error_code=row["error_code"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
    )


def _database_id(public_id: str) -> str | None:
    if not public_id.startswith("job_"):
        return None
    try:
        return str(uuid.UUID(hex=public_id[4:]))
    except ValueError:
        return None


class AnalysisJobService:
    def __init__(
        self,
        pool: asyncpg.Pool,
        pipeline: DecisionPipeline,
        entitlements: EntitlementService,
        usage: UsageMeter,
        settings: Settings,
    ) -> None:
        self._pool = pool
        self._pipeline = pipeline
        self._entitlements = entitlements
        self._usage = usage
        self._settings = settings
        self._tasks: list[asyncio.Task[None]] = []

    async def submit(
        self,
        tenant: TenantContext,
        *,
        api_key_id: str,
        text: str,
        subject: str | None,
        external_id: str | None,
        idempotency_key: str | None,
    ) -> AnalysisJobSnapshot:
        body = scrub_pii(preprocess_email(text))
        scrubbed_subject = scrub_pii(preprocess_email(subject)) if subject else None
        entities = Counter(body.entities)
        if scrubbed_subject is not None:
            entities.update(scrubbed_subject.entities)
        safe_subject = scrubbed_subject.text if scrubbed_subject else None
        order_reference_detected = body.order_reference_detected or bool(
            scrubbed_subject and scrubbed_subject.order_reference_detected
        )
        request_hash = hashlib.sha256(
            json.dumps([body.text, safe_subject, external_id], ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        effective_idempotency_key = idempotency_key or (
            "auto:" + hashlib.sha256((external_id + "\0" + request_hash).encode()).hexdigest()
            if external_id is not None
            else None
        )
        expires_at = datetime.now(UTC) + timedelta(days=self._settings.analysis_job_retention_days)

        async with self._pool.acquire() as connection, connection.transaction():
            await connection.fetchrow("SELECT id FROM tenants WHERE id = $1::uuid FOR UPDATE", tenant.tenant_id)
            if effective_idempotency_key:
                await connection.execute(
                    "DELETE FROM analysis_jobs "
                    "WHERE tenant_id = $1::uuid AND idempotency_key = $2 AND expires_at <= now()",
                    tenant.tenant_id,
                    effective_idempotency_key,
                )
                existing = await connection.fetchrow(
                    _GET_BY_IDEMPOTENCY_SQL, tenant.tenant_id, effective_idempotency_key
                )
                if existing is not None:
                    if existing["request_hash"] != request_hash:
                        raise AnalysisJobError(
                            409,
                            "idempotency_key_reused",
                            "Dieser Idempotency-Key wurde bereits für eine andere Anfrage verwendet.",
                        )
                    return _snapshot(existing)

            pending = await connection.fetchval(
                """SELECT count(*) FROM analysis_jobs
                   WHERE tenant_id = $1::uuid AND status IN ('QUEUED', 'PROCESSING') AND expires_at > now()""",
                tenant.tenant_id,
            )
            if pending >= self._settings.analysis_max_pending_per_tenant:
                raise AnalysisJobError(
                    429,
                    "analysis_queue_full",
                    "Zu viele Analysen dieses Shops warten noch auf Verarbeitung.",
                )
            entitlement = await self._entitlements.check(tenant, connection=connection)
            if not entitlement.allowed:
                raise AnalysisJobError(
                    entitlement.status_code,
                    entitlement.error_code or "forbidden",
                    entitlement.message or "Analyse kann derzeit nicht angenommen werden.",
                )

            row = await connection.fetchrow(
                _INSERT_SQL,
                tenant.tenant_id,
                api_key_id,
                effective_idempotency_key,
                request_hash,
                external_id,
                body.text,
                safe_subject,
                json.dumps(dict(entities)),
                order_reference_detected,
                entitlement.billable,
                expires_at,
            )
            if row is None:
                row = await connection.fetchrow(_GET_BY_IDEMPOTENCY_SQL, tenant.tenant_id, effective_idempotency_key)
                if row is None:
                    raise RuntimeError("Idempotent job insert conflicted without a matching row")
                if row["request_hash"] != request_hash:
                    raise AnalysisJobError(
                        409,
                        "idempotency_key_reused",
                        "Dieser Idempotency-Key wurde bereits für eine andere Anfrage verwendet.",
                    )
                return _snapshot(row)
            return _snapshot(row)

    async def get(self, public_id: str, tenant_id: str) -> AnalysisJobSnapshot | None:
        database_id = _database_id(public_id)
        if database_id is None:
            return None
        row = await self._pool.fetchrow(_GET_JOB_SQL, database_id, tenant_id)
        return _snapshot(row) if row is not None else None

    async def wait(self, job_id: str, tenant_id: str, wait_seconds: float) -> AnalysisJobSnapshot | None:
        deadline = asyncio.get_running_loop().time() + wait_seconds
        while True:
            snapshot = await self.get(job_id, tenant_id)
            if snapshot is None or snapshot.terminal or asyncio.get_running_loop().time() >= deadline:
                return snapshot
            await asyncio.sleep(min(self._settings.analysis_job_poll_interval_seconds, 0.1))

    def start(self) -> None:
        if self._tasks:
            return
        self._tasks = [
            asyncio.create_task(self._run_worker(), name=f"analysis-job-worker-{index + 1}")
            for index in range(self._settings.analysis_worker_concurrency)
        ]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _run_worker(self) -> None:
        while True:
            try:
                job = await self._claim()
                if job is not None:
                    await self._process(job)
                    continue
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Analysis job worker iteration failed")
            await asyncio.sleep(self._settings.analysis_job_poll_interval_seconds)

    async def _claim(self) -> asyncpg.Record | None:
        async with self._pool.acquire() as connection, connection.transaction():
            await connection.execute(_DELETE_EXPIRED_SQL)
            await connection.execute(_FAIL_EXHAUSTED_SQL, self._settings.analysis_job_max_attempts)
            return await connection.fetchrow(
                _CLAIM_SQL,
                self._settings.analysis_job_lease_seconds,
                self._settings.analysis_job_max_attempts,
            )

    async def _process(self, job: asyncpg.Record) -> None:
        try:
            pii_entities = _decode_json(job["pii_entities"])
            result = await self._pipeline.analyze_preprocessed(
                job["anonymized_text"],
                job["anonymized_subject"],
                pii_entities=pii_entities,
                order_reference_detected=job["order_reference_detected"],
            )
            response = self._response(result, job["external_id"])
            await self._complete(job, result, response)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Analysis job failed id=%s attempt=%s", job["id"], job["attempts"])
            await self._retry(job)

    @staticmethod
    def _response(result: AnalysisResult, external_id: str | None) -> AnalyzeTicketResponse:
        decision = result.decision
        return AnalyzeTicketResponse(
            id=f"ana_{uuid.uuid4().hex}",
            external_id=external_id,
            category=decision.category,
            urgency=decision.urgency,
            flags=TicketFlags(
                is_cancellation_request=decision.is_cancellation_request,
                contains_order_number=decision.contains_order_number,
            ),
            confidence=round(decision.confidence, 3),
            engine=result.engine,
            degraded=result.degraded,
            latency_ms=result.latency_ms,
            pii=PiiReport(redacted=bool(result.pii_entities), entities=result.pii_entities),
            anonymized_text=result.anonymized_text,
        )

    async def _complete(
        self,
        job: asyncpg.Record,
        result: AnalysisResult,
        response: AnalyzeTicketResponse,
    ) -> None:
        status = "DEGRADED" if result.degraded else "SUCCEEDED"
        response_json = response.model_dump_json()
        async with self._pool.acquire() as connection, connection.transaction():
            current = await connection.fetchrow(
                "SELECT lease_token::text, status::text FROM analysis_jobs WHERE id = $1::uuid FOR UPDATE",
                job["id"],
            )
            if (
                current is None
                or current["status"] != "PROCESSING"
                or current["lease_token"] != str(job["lease_token"])
            ):
                return
            await self._usage.record(
                tenant_id=str(job["tenant_id"]),
                api_key_id=str(job["api_key_id"]) if job["api_key_id"] else None,
                operation_type="ANALYZE_TICKET",
                billable=job["billable"] and not result.degraded,
                details=UsageDetails(
                    category=result.decision.category.value,
                    urgency=result.decision.urgency,
                    engine=result.engine,
                    latency_ms=result.latency_ms,
                ),
                connection=connection,
            )
            updated = await connection.execute(
                _COMPLETE_SQL,
                job["id"],
                str(job["lease_token"]),
                status,
                response_json,
            )
            if updated.endswith(" 0"):
                raise RuntimeError("Analysis job lease was lost before completion")

    async def _retry(self, job: asyncpg.Record) -> None:
        attempts = int(job["attempts"])
        terminal = attempts >= self._settings.analysis_job_max_attempts
        status = "FAILED" if terminal else "QUEUED"
        delay = min(2**attempts, 30)
        async with self._pool.acquire() as connection:
            await connection.execute(
                _RETRY_SQL,
                job["id"],
                str(job["lease_token"]),
                status,
                "analysis_failed" if terminal else "analysis_retrying",
                delay,
            )
