-- CreateTable
CREATE TABLE "api_rate_limit_buckets" (
    "api_key_id" UUID NOT NULL,
    "tokens" DOUBLE PRECISION NOT NULL,
    "updated_at" TIMESTAMPTZ(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "api_rate_limit_buckets_pkey" PRIMARY KEY ("api_key_id")
);

-- CreateIndex
CREATE INDEX "api_rate_limit_buckets_updated_at_idx" ON "api_rate_limit_buckets"("updated_at");

-- AddForeignKey
ALTER TABLE "api_rate_limit_buckets" ADD CONSTRAINT "api_rate_limit_buckets_api_key_id_fkey" FOREIGN KEY ("api_key_id") REFERENCES "api_keys"("id") ON DELETE CASCADE ON UPDATE CASCADE;