-- CreateEnum
CREATE TYPE "AnalysisJobStatus" AS ENUM ('QUEUED', 'PROCESSING', 'SUCCEEDED', 'DEGRADED', 'FAILED');

-- CreateTable
CREATE TABLE "analysis_jobs" (
    "id" UUID NOT NULL DEFAULT gen_random_uuid(),
    "tenant_id" UUID NOT NULL,
    "api_key_id" UUID,
    "idempotency_key" TEXT,
    "request_hash" TEXT NOT NULL,
    "external_id" TEXT,
    "anonymized_text" TEXT,
    "anonymized_subject" TEXT,
    "pii_entities" JSONB NOT NULL,
    "order_reference_detected" BOOLEAN NOT NULL DEFAULT false,
    "status" "AnalysisJobStatus" NOT NULL DEFAULT 'QUEUED',
    "billable" BOOLEAN NOT NULL DEFAULT false,
    "result" JSONB,
    "error_code" TEXT,
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "available_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "lease_expires_at" TIMESTAMPTZ(3),
    "lease_token" UUID,
    "expires_at" TIMESTAMPTZ(3) NOT NULL,
    "created_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "analysis_jobs_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "analysis_jobs_tenant_id_idempotency_key_key" ON "analysis_jobs"("tenant_id", "idempotency_key");
CREATE INDEX "analysis_jobs_status_available_at_created_at_idx" ON "analysis_jobs"("status", "available_at", "created_at");
CREATE INDEX "analysis_jobs_tenant_id_status_created_at_idx" ON "analysis_jobs"("tenant_id", "status", "created_at");

-- AddForeignKey
ALTER TABLE "analysis_jobs" ADD CONSTRAINT "analysis_jobs_tenant_id_fkey" FOREIGN KEY ("tenant_id") REFERENCES "tenants"("id") ON DELETE CASCADE ON UPDATE CASCADE;
ALTER TABLE "analysis_jobs" ADD CONSTRAINT "analysis_jobs_api_key_id_fkey" FOREIGN KEY ("api_key_id") REFERENCES "api_keys"("id") ON DELETE SET NULL ON UPDATE CASCADE;