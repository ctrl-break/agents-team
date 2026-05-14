# Architecture & DevOps Review: Kids Chore Tracker

**Reviewer**: Principal Architect / DevOps Engineer  
**Date**: 2025-04-15  
**Documents Reviewed**:
- `docs/specs/latest-plan.md` — Approved Technical Specification
- `docs/implementation/backend-plan.md` — Backend Implementation Plan
- `docs/implementation/frontend-plan.md` — Frontend Implementation Plan
- `docs/qa/qa-report.md` — QA Strategy Report

---

## 1. Executive Summary

The **Kids Chore Tracker** solution is well-architected for its target scale (family groups, moderate data volume). The three-tier Docker Compose deployment (Angular/Nginx frontend, NestJS backend, PostgreSQL 16) is appropriate for an MVP and small-to-medium production use. The modular NestJS design, clean REST API contracts, bitmask-based weekday encoding, optimistic UI with offline queue, and family-scoped data isolation are sound architectural decisions.

**Overall Verdict**: **Approved with recommendations**. The design is implementation-ready. However, several DevOps gaps (CI/CD, secrets management, backups, HTTPS termination, monitoring) must be addressed before production deployment. The timezone strategy has a known design trade-off that needs explicit stakeholder acceptance.

---

## 2. Architecture Quality Assessment

### 2.1 Strengths

| Area | Assessment | Rating |
|------|-----------|--------|
| **Layered Separation** | Clear three-tier: Presentation (Angular SPA), Application (NestJS REST API), Data (PostgreSQL). Each tier is independently containerized. | ★★★★★ |
| **Backend Modularity** | NestJS modules (`AuthModule`, `UsersModule`, `ChoresModule`, `CompletionsModule`, `ReportsModule`, `NotificationsModule`, `HealthModule`) follow single-responsibility principle. Common cross-cutting concerns (guards, interceptors, decorators, filters, pipes) are properly extracted into `common/`. | ★★★★★ |
| **Frontend Structure** | Feature-based organization (`auth/`, `dashboard/`, `chores/`, `kids/`, `reports/`, `settings/`) with shared components, core services, and state stores. Follows Angular style guide conventions. | ★★★★☆ |
| **Data Model** | Six well-normalized entities (`families`, `users`, `chores`, `chore_completions`, `push_subscriptions`, `notification_preferences`) with appropriate foreign keys, unique constraints, and composite indexes. UUID v4 PKs prevent sequential ID guessing. | ★★★★★ |
| **API Design** | RESTful, resource-oriented, consistent error response shape (`ApiErrorResponse`), proper HTTP status code usage including `409 Conflict` and `422 Unprocessable Entity`. OpenAPI/Swagger auto-generation. | ★★★★☆ |
| **Security by Design** | Family-scoped data isolation via `family_id` in JWT payload, refresh token rotation with hashed storage, 404-for-403 info-leak prevention, CORS configuration, `@nestjs/throttler` rate limiting on auth endpoints. | ★★★★☆ |

### 2.2 Concerns & Gaps

| Area | Issue | Severity |
|------|-------|----------|
| **Timezone Strategy** | UTC-only backend + local-date frontend. Frontend sends local `YYYY-MM-DD` as the canonical "date" string. Near midnight in timezones far from UTC (e.g., UTC+10 at 01:00 Wednesday → UTC is still Tuesday), the dashboard shows Wednesday's chores but the backend evaluates against UTC Tuesday's weekday. Both the frontend plan and QA report flag this as "acceptable" — but it is a **design trade-off, not a bug fix**. Stakeholders must explicitly accept this behavior. | **HIGH** |
| **API Versioning** | No API versioning strategy (no `/api/v1/` prefix, no header-based versioning). Backend changes could break the frontend if both are deployed independently. | MEDIUM |
| **Refresh Token Storage** | Refresh token stored in `localStorage`, which is accessible to any JavaScript running on the origin (XSS risk). An `HttpOnly` cookie would be more secure, though it complicates the SPA token refresh flow. The backend plan mentions this as an option but the frontend plan commits to `localStorage`. | MEDIUM |
| **Push Notification Scheduler** | `@Cron(CronExpression.EVERY_MINUTE)` queries the database every 60 seconds. At low scale this is fine; at higher scale with many notification preferences, a job queue (Bull/BullMQ with Redis) would be more efficient and provide retry capabilities. | LOW (MVP) |
| **No Email Service** | The specification states "система отправляет приглашение на почту" but the backend plan creates "pending" user records without an email service integration. This needs clarification — is email invitation deferred to post-MVP? | MEDIUM |

---

## 3. Component Boundaries Analysis

### 3.1 Boundary Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Docker Compose Network                        │
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐        │
│  │   Frontend   │    │   Backend    │    │  PostgreSQL  │        │
│  │  (Nginx +    │───▶│  (NestJS)    │───▶│  (Postgres   │        │
│  │   Angular)   │    │              │    │   16-alpine) │        │
│  │              │    │  Port: 3000  │    │  Port: 5432  │        │
│  │  Port: 80    │    │              │    │              │        │
│  └──────────────┘    └──────────────┘    └──────────────┘        │
│         │                    │                    │               │
│         ▼                    ▼                    ▼               │
│  /api/* proxied       Google OAuth           pgdata volume       │
│  to backend           (external)             (persisted)         │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Boundary Evaluation

| Boundary | Mechanism | Quality |
|----------|-----------|---------|
| **Frontend ↔ Backend** | REST API over HTTP, proxied by Nginx (`proxy_pass`). Single origin in production avoids CORS. API contracts documented via OpenAPI/Swagger. | ★★★★☆ |
| **Backend ↔ Database** | TypeORM repository pattern with `DataSource`. Connection pooling handled by TypeORM driver. | ★★★★☆ |
| **Auth Boundary** | Google OAuth 2.0 (external) → JWT (internal). `family_id` embedded in JWT payload for downstream data scoping. | ★★★★★ |
| **Push Boundary** | Web Push Protocol (external browser vendors) via `web-push` library. VAPID keys for server identity. Subscription management in app DB. | ★★★★☆ |
| **Offline Boundary** | IndexedDB queue (frontend) + Service Worker cache (Angular `ngsw`). Sync on `window.online` event. No Background Sync API usage (limited browser support). | ★★★☆☆ |

### 3.3 Boundary Recommendations

1. **API Versioning**: Add `/api/v1/` prefix to all endpoints now, before any client is built. This costs nothing and prevents future breaking-change headaches. NestJS supports this trivially via `app.setGlobalPrefix('api/v1')`.

2. **Backend Database Connection**: The backend plan doesn't specify connection pool sizing. Recommend configuring TypeORM connection pool explicitly:
   ```
   DB_POOL_MIN=2
   DB_POOL_MAX=10
   ```
   For Docker Compose single-instance deployment, 10 connections is appropriate.

3. **Nginx as API Gateway**: The Nginx config correctly proxies `/api/` to backend. Consider adding:
   - **Request size limit**: `client_max_body_size 1m;` (prevents large payload attacks)
   - **Rate limiting** on `/api/auth/` endpoints at the Nginx level as a second defense layer
   - **Upstream keepalive** connections: `keepalive 32;` in the `upstream` block for connection reuse

---

## 4. Data Architecture Deep Dive

### 4.1 Schema Review

The entity design is thorough. Notable observations:

| Element | Observation |
|---------|-------------|
| **`weekdays` as `smallint` (INT2)** | Efficient bitmask approach. Bitwise queries in PostgreSQL (`weekdays & :bit > 0`) are fast and indexable via expression indexes if needed. However, the plans only create BTREE indexes on `weekdays` directly — a `WHERE (weekdays & :bit > 0)` filter won't use a standard BTREE index. This is acceptable for the expected data volume per family (tens of chores, not millions). |
| **`chore_completions.date` as `DATE` (not `TIMESTAMPTZ`)** | Correct decision per the UTC-date-as-canonical-day strategy. The `completed_at` column as `TIMESTAMPTZ` provides exact timestamp for audit. |
| **`refresh_token_hash` in `users` table** | Good: tokens are bcrypt-hashed before storage. However, storing a single hash means only one refresh token per user. If the user logs in on two devices, the second login invalidates the first device's refresh token. This is acceptable for a family app but should be documented. If multi-device support is needed, move refresh token hashes to a separate `refresh_tokens` table. |
| **`notification_preferences.time` as `TIME`** | Stored in UTC per spec. The cron job matches `HH:MM` against current UTC time. This is correct. Frontend converts local time to UTC before saving. |
| **UNIQUE constraint on `(user_id, chore_id)` for notifications** | Prevents duplicate preferences per chore per user. The `chore_id=NULL` case (global default) needs careful handling — PostgreSQL treats NULLs as distinct in UNIQUE constraints. The backend plan acknowledges this by allowing `nullable: true`. Verify that only one row with `chore_id=NULL` can exist per user (enforced at the application layer or via a partial unique index). |

### 4.2 Indexing Strategy Review

| Index | Verdict |
|-------|---------|
| `users(email)` UNIQUE | Essential for login lookup |
| `users(google_id)` UNIQUE | Essential for OAuth lookup |
| `users(family_id)` | Correct for family-scoped member queries |
| `users(parent_id)` | Correct for "get all children of parent" |
| `chores(assigned_to)` | Correct for user-scoped chore listing |
| `chores(assigned_to, is_active)` | Correct for dashboard active chores query |
| `chore_completions(chore_id, user_id, date)` UNIQUE | Idempotency guarantee + toggle lookup. Perfect. |
| `chore_completions(user_id, date)` | Report aggregation per user per period. Essential. |
| `push_subscriptions(user_id, endpoint)` UNIQUE | Deduplication per device. Good. |
| `notification_preferences(user_id, chore_id)` UNIQUE | Fast lookup. See note above about NULL handling. |

**Recommendation**: Add a partial unique index for global default notification preferences:
```sql
CREATE UNIQUE INDEX idx_notification_pref_global_default
ON notification_preferences (user_id)
WHERE chore_id IS NULL;
```
This ensures only one global default per user at the database level.

### 4.3 Migration Strategy

The TypeORM migration approach (`migration:generate` → `migration:run`) is standard and appropriate. However, the plan does not address:

- **Zero-downtime migrations**: For a family app, brief downtime during `migration:run` is acceptable for MVP. Document this in runbooks.
- **Rollback procedure**: `migration:revert` exists but needs to be tested in staging before any production use.
- **Migration in CI/CD**: Migrations should run automatically as part of the deployment pipeline (see §7).

---

## 5. Scalability & Maintainability

### 5.1 Scalability Assessment

| Dimension | Current Design | MVP Limit | Scaling Path |
|-----------|---------------|-----------|--------------|
| **Users** | Single PostgreSQL instance | ~10,000 families | Read replicas for reports; connection pooling via PgBouncer |
| **Chores/Completions** | Indexed queries, 90-day report cap | ~100 chores/child, ~1000 completions/child | Partition `chore_completions` by `date` range |
| **Push Notifications** | Per-minute cron, in-process | ~1,000 notifications/minute | Extract to job queue (BullMQ + Redis); dedicated worker |
| **Frontend** | Nginx static serving, single container | Sufficient for SPA | CDN for static assets (Cloudflare, etc.) |
| **API Throughput** | Single NestJS instance | ~100 req/s | Horizontal scaling behind load balancer; stateless JWT enables any-instance handling |

**Verdict**: The architecture scales vertically well for the target use case. The 90-day report cap and per-minute cron are appropriate guardrails for MVP. Horizontal scaling considerations are deferred to post-MVP, which is acceptable.

### 5.2 Maintainability Assessment

| Factor | Rating | Notes |
|--------|--------|-------|
| **Code Organization** | ★★★★★ | Clear NestJS module structure; Angular feature-based layout |
| **Type Safety** | ★★★★☆ | TypeScript strict mode on both tiers; shared DTOs would benefit from a shared types package |
| **Testability** | ★★★★★ | Services are injectable and mockable; stores are testable via Signals; comprehensive test scenarios in QA plan |
| **Configuration** | ★★★★☆ | Environment variables via `.env`; no configuration schema validation (consider `joi` or `zod` for config validation at startup) |
| **Documentation** | ★★★★☆ | OpenAPI/Swagger for API; implementation plans are thorough; missing: runbooks, on-call guides |

**Recommendation**: Extract shared TypeScript types (DTOs, API response shapes) into a `packages/shared-types/` package. This ensures compile-time contract verification between frontend and backend, rather than relying solely on the table in the frontend plan (§6.4) that maps models to DTOs manually.

---

## 6. Observability & Logging

### 6.1 Current State

| Signal | Implementation | Rating |
|--------|---------------|--------|
| **Health Check** | `GET /api/health` — database ping + uptime. Docker healthcheck uses `curl`. | ★★★☆☆ |
| **Structured Logging** | NestJS Logger with JSON format in production. | ★★★☆☆ |
| **Error Tracking** | Not mentioned. | ✗ Missing |
| **Metrics** | Not mentioned. | ✗ Missing |
| **Tracing** | Not mentioned. | ✗ Missing |
| **Push Delivery Monitoring** | Errors logged; 410 subscriptions cleaned up. No success/failure metrics. | ★★☆☆☆ |

### 6.2 Gaps & Recommendations

**Critical (before production)**:

1. **Centralized Logging**: JSON logs are only useful if aggregated. Recommend:
   - Docker `json-file` log driver with `max-size` and `max-file` rotation to prevent disk exhaustion
   - For production: ship logs to a centralized system (Loki, ELK, or at minimum `docker logs` + log rotation)
   - Add correlation IDs (`X-Request-ID`) to track requests across frontend→backend→database

2. **Push Notification Monitoring**: The silent nature of push failures is concerning. Add:
   - Counter metric: `push_notifications_sent_total`
   - Counter metric: `push_notifications_failed_total` (by reason: 410, network_error, other)
   - Gauge metric: `push_subscriptions_active`
   - Alert if failure rate > 20% over 5 minutes

3. **Health Check Depth**: Current check is shallow (DB ping only). Add:
   - External service health (Google OAuth endpoint reachability)
   - Migration status (are there pending migrations?)
   - Disk space on PostgreSQL volume

**Recommended (post-MVP)**:

4. **Metrics Export**: Add `prom-client` (or `@willsoto/nestjs-prometheus`) for Prometheus-compatible metrics:
   - HTTP request duration histogram (by route, method, status)
   - Database query duration
   - Active user sessions
   - Completion toggle rate

5. **Error Tracking**: Integrate Sentry or similar for both frontend and backend JavaScript error tracking.

6. **Uptime Monitoring**: External health check ping (e.g., UptimeRobot, BetterStack) on `GET /api/health` every 60 seconds.

### 6.3 Recommended Log Format

```json
{
  "timestamp": "2025-04-15T07:30:00.000Z",
  "level": "info",
  "message": "Push notification sent",
  "context": "NotificationsScheduler",
  "requestId": "req_abc123",
  "userId": "uuid-parent-a",
  "choreId": "uuid-chore-1",
  "duration_ms": 245
}
```

---

## 7. CI/CD Pipeline Recommendations

### 7.1 Current State

The plans describe Docker Compose for local development and production deployment, but **no CI/CD pipeline is defined**. This is the most significant DevOps gap.

### 7.2 Recommended Pipeline (GitHub Actions or GitLab CI)

```
┌─────────┐    ┌──────────┐    ┌──────────┐    ┌────────────┐    ┌───────────┐
│  Lint   │───▶│   Test   │───▶│  Build   │───▶│  Security  │───▶│  Deploy   │
│         │    │          │    │          │    │   Scan     │    │           │
└─────────┘    └──────────┘    └──────────┘    └────────────┘    └───────────┘
```

#### Stage 1: Lint & Type Check (on every push)
```yaml
lint-backend:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with: { node-version: '20' }
    - run: npm ci
      working-directory: apps/backend
    - run: npm run lint
      working-directory: apps/backend
    - run: npm run type-check
      working-directory: apps/backend

lint-frontend:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with: { node-version: '20' }
    - run: npm ci
      working-directory: apps/frontend
    - run: npm run lint
      working-directory: apps/frontend
    - run: npx ng build --configuration production --dry-run  # type check
      working-directory: apps/frontend
```

#### Stage 2: Test (on every push to main, every PR)
```yaml
test-backend:
  needs: [lint-backend]
  services:
    postgres:
      image: postgres:16-alpine
      env:
        POSTGRES_DB: test_db
        POSTGRES_USER: test_user
        POSTGRES_PASSWORD: test_pass
      ports: ['5432:5432']
  steps:
    - run: npm run test:unit -- --coverage
    - run: npm run test:integration
    - run: npm run test:e2e
  coverage:
    backend-unit: '>=80%'
    backend-integration: all endpoints

test-frontend:
  needs: [lint-frontend]
  steps:
    - run: npm run test:unit -- --coverage
    - run: npm run test:integration
  coverage:
    frontend-unit: '>=80%'
```

#### Stage 3: Build & Containerize (on merge to main)
```yaml
build-and-push:
  needs: [test-backend, test-frontend]
  steps:
    - name: Build backend image
      run: docker build -t registry.example.com/kids-chores-backend:${{ github.sha }} -f apps/backend/Dockerfile apps/backend/
    - name: Build frontend image
      run: docker build -t registry.example.com/kids-chores-frontend:${{ github.sha }} -f apps/frontend/Dockerfile apps/frontend/
    - name: Push images
      run: |
        docker push registry.example.com/kids-chores-backend:${{ github.sha }}
        docker push registry.example.com/kids-chores-frontend:${{ github.sha }}
    - name: Tag as latest
      if: github.ref == 'refs/heads/main'
      run: |
        docker tag registry.example.com/kids-chores-backend:${{ github.sha }} registry.example.com/kids-chores-backend:latest
        docker push registry.example.com/kids-chores-backend:latest
```

#### Stage 4: Security Scan
```yaml
security-scan:
  needs: [build-and-push]
  steps:
    - name: Trivy vulnerability scan (backend)
      run: trivy image registry.example.com/kids-chores-backend:${{ github.sha }} --severity HIGH,CRITICAL
    - name: Trivy vulnerability scan (frontend)
      run: trivy image registry.example.com/kids-chores-frontend:${{ github.sha }} --severity HIGH,CRITICAL
    - name: npm audit (backend)
      run: npm audit --audit-level=high
      working-directory: apps/backend
    - name: npm audit (frontend)
      run: npm audit --audit-level=high
      working-directory: apps/frontend
    - name: Lighthouse PWA audit
      run: npx lighthouse-ci --score=90
```

#### Stage 5: Deploy
```yaml
deploy-staging:
  needs: [security-scan]
  environment: staging
  steps:
    - name: Copy docker-compose.prod.yml to server
      run: scp docker-compose.prod.yml user@staging-server:/app/
    - name: Run database migrations
      run: ssh user@staging-server 'cd /app && docker compose run --rm backend npm run typeorm migration:run'
    - name: Deploy services
      run: ssh user@staging-server 'cd /app && docker compose pull && docker compose up -d --remove-orphans'
    - name: Health check
      run: |
        for i in $(seq 1 30); do
          curl -f http://staging-server/api/health && exit 0
          sleep 2
        done
        exit 1
    - name: Smoke test
      run: |
        curl -f http://staging-server/api/health | jq .status
        curl -f http://staging-server/ | grep '<title>Детский трекер'

deploy-production:
  needs: [deploy-staging]
  environment: production
  if: github.ref == 'refs/heads/main'
  steps:
    # Same as staging but with production server and .env
    # Requires manual approval in GitHub Environments settings
```

### 7.3 CI/CD Critical Requirements

1. **Migration Automation**: Database migrations MUST run automatically as part of deployment, BEFORE new application code starts. The deploy script should:
   ```bash
   # Run migrations with the NEW backend image before rolling the service
   docker compose run --rm backend node dist/scripts/run-migrations.js
   # Then roll the service
   docker compose up -d backend
   ```

2. **Health Check + Rollback**: If the health check fails after deployment, automatically roll back to the previous image tag:
   ```bash
   DEPLOY_TAG=${{ github.sha }}
   PREVIOUS_TAG=$(docker inspect registry.example.com/kids-chores-backend:latest --format '{{.RepoDigests}}')
   # Deploy new version
   # If health check fails:
   docker compose up -d backend frontend  # redeploys previous :latest
   ```

3. **Secret Management**: Never store `.env` files in the repository. Use:
   - **GitHub Actions Secrets** for CI/CD variables
   - **Docker secrets** or **HashiCorp Vault** for production
   - `.env.example` committed (with placeholder values), `.env` in `.gitignore`

4. **Environment Separation**: Maintain separate `.env` files per environment:
   ```
   .env.example          # Committed — template
   .env.development      # Local dev
   .env.staging          # CI staging
   .env.production       # Production (never committed)
   ```

---

## 8. Deployment Architecture

### 8.1 Docker Compose Review

The defined `docker-compose.yml` covers the three core services. Review findings:

| Aspect | Current | Recommendation |
|--------|---------|----------------|
| **Frontend exposure** | Port 80 | Add port mapping `"80:80"` or `"443:443"` if TLS handled by Nginx |
| **Backend exposure** | Port 3000 mapped to host | In production, backend should NOT be directly exposed. Remove `ports` or bind to `127.0.0.1:3000:3000` |
| **Database exposure** | Port 5432 mapped to host | Remove in production. Access via Docker network only |
| **Postgres healthcheck** | `pg_isready` | Good, but add `--username` flag: `pg_isready -U ${DB_USER}` |
| **Backend healthcheck** | `curl -f http://localhost:3000/api/health` | Good. Add `start_period: 15s` to allow NestJS bootstrap |
| **Restart policy** | Not defined | Add `restart: unless-stopped` to all services |
| **Log rotation** | Not defined | Add `logging` config to prevent disk exhaustion |

### 8.2 Recommended Production `docker-compose.prod.yml`

```yaml
version: '3.8'

services:
  frontend:
    image: registry.example.com/kids-chores-frontend:latest
    restart: unless-stopped
    ports:
      - '80:80'
      # - '443:443'  # When TLS is added
    networks:
      - app-network
    logging:
      driver: json-file
      options:
        max-size: '50m'
        max-file: '3'
    healthcheck:
      test: ['CMD', 'curl', '-f', 'http://localhost:80/']
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

  backend:
    image: registry.example.com/kids-chores-backend:latest
    restart: unless-stopped
    expose:
      - '3000'  # Internal only, not exposed to host
    env_file:
      - .env.production
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - app-network
    logging:
      driver: json-file
      options:
        max-size: '50m'
        max-file: '3'
    healthcheck:
      test: ['CMD', 'curl', '-f', 'http://localhost:3000/api/health']
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s

  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    expose:
      - '5432'  # Internal only
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./backups:/backups  # Mount for pg_dump
    networks:
      - app-network
    logging:
      driver: json-file
      options:
        max-size: '50m'
        max-file: '3'
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -U ${DB_USER} -d ${DB_NAME}']
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

volumes:
  pgdata:
    driver: local

networks:
  app-network:
    driver: bridge
```

### 8.3 HTTPS/TLS Termination

**The plan does not address HTTPS.** This is a critical gap for any production deployment, especially one handling Google OAuth tokens.

**Recommendation**: Add a Let's Encrypt + Nginx or Traefik reverse proxy:

**Option A — Traefik (recommended for Docker Compose)**:
```yaml
traefik:
  image: traefik:v3.0
  command:
    - --providers.docker
    - --entrypoints.web.address=:80
    - --entrypoints.websecure.address=:443
    - --certificatesresolvers.letsencrypt.acme.email=admin@example.com
    - --certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json
    - --certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web
  ports:
    - '80:80'
    - '443:443'
  volumes:
    - /var/run/docker.sock:/var/run/docker.sock:ro
    - letsencrypt:/letsencrypt

frontend:
  labels:
    - 'traefik.http.routers.frontend.rule=Host(`kids-chores.example.com`)'
    - 'traefik.http.routers.frontend.tls.certresolver=letsencrypt'
```

**Option B — Nginx with certbot** (simpler, manual cert renewal):
Add a `certbot` service to `docker-compose.yml` and configure Nginx with SSL certificates.

### 8.4 Backup Strategy

**No backup strategy is defined.** This is a critical gap.

**Recommendation**:

```bash
# Add to cron on host (daily at 02:00 UTC):
0 2 * * * docker exec kids-chores-postgres-1 pg_dump -U ${DB_USER} -d ${DB_NAME} \
  --format=custom --file=/backups/kids-chores-$(date +\%Y\%m\%d).dump

# Retention: keep 30 daily backups, 12 monthly
find /path/to/backups -name 'kids-chores-*.dump' -mtime +30 -delete
```

For additional safety:
- Mount the backup directory to a cloud-synced volume (S3, Google Drive, etc.)
- Test restoration quarterly: `pg_restore --clean --dbname=test_restore backup.dump`

---

## 9. Security Review

### 9.1 Security Posture Assessment

| Area | Status | Recommendation |
|------|--------|----------------|
| **OAuth Flow** | Google OAuth 2.0 via Passport. `prompt=select_account` for account chooser. ✅ | Ensure `GOOGLE_CLIENT_SECRET` is never in frontend code or committed to repository |
| **JWT Tokens** | Access (15 min) + Refresh (7 days) with rotation. ✅ | Consider adding JWT ID (`jti`) claim for token revocation capability |
| **Refresh Token Storage** | `localStorage` in browser. ⚠️ | Prefer HttpOnly cookie. If localStorage is chosen, document the XSS risk and ensure strict Content Security Policy (CSP) |
| **Password Hashing** | bcrypt for refresh token hashes. ✅ | Verify bcrypt cost factor ≥ 10 |
| **CORS** | Single origin in production (Nginx proxy). ✅ | The backend CORS config should be `origin: process.env.FRONTEND_URL` in production. Verify this is a strict exact match, not a wildcard. |
| **Rate Limiting** | `@nestjs/throttler` on `/auth/refresh` only. ⚠️ | Extend rate limiting to `/auth/google`, `/users/children` POST, and `/completions/toggle` to prevent abuse |
| **Input Validation** | `class-validator` DTOs with `whitelist: true`, `forbidNonWhitelisted: true`. ✅ | Also validate on frontend (already planned with Angular Reactive Forms) |
| **SQL Injection** | TypeORM parameterized queries. ✅ | Verify no raw queries use string interpolation |
| **XSS** | Angular auto-sanitizes templates. ✅ | Add Content Security Policy header in Nginx |
| **Docker Security** | Images run as `node` user (not `root`). Verify. ⚠️ | Add `USER node` in backend Dockerfile after `COPY` commands |

### 9.2 Recommended Nginx Security Headers

Add to `nginx.conf`:
```nginx
# Content Security Policy
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https://*.googleusercontent.com; connect-src 'self' https://accounts.google.com; frame-src 'self' https://accounts.google.com;" always;

# Additional security headers (already partially in plan)
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
```

### 9.3 Secrets Checklist

Before any deployment, ensure these secrets exist and are NOT in version control:

```
☐ GOOGLE_CLIENT_ID
☐ GOOGLE_CLIENT_SECRET
☐ JWT_ACCESS_SECRET (random, ≥ 32 chars)
☐ JWT_REFRESH_SECRET (random, ≥ 32 chars)
☐ VAPID_PRIVATE_KEY
☐ DB_PASSWORD
```

Generate strong secrets:
```bash
# JWT secrets
node -e "console.log(require('crypto').randomBytes(64).toString('hex'))"

# DB password
openssl rand -base64 32
```

---

## 10. Operational Readiness

### 10.1 Runbook Requirements

The following runbooks should be documented before production deployment:

| Runbook | Priority |
|---------|----------|
| **Deployment procedure** (manual fallback if CI/CD fails) | P0 |
| **Database backup and restore** | P0 |
| **Database migration rollback** | P1 |
| **SSL certificate renewal** (if not automated) | P1 |
| **Push notification troubleshooting** (VAPID key rotation, 410 handling) | P1 |
| **Google OAuth configuration changes** (client ID/secret rotation) | P2 |
| **Disaster recovery** (full system restore from backups) | P2 |

### 10.2 Monitoring Checklist

| What to Monitor | How | Alert Threshold |
|-----------------|-----|-----------------|
| Backend health check | External ping (1 min) | 3 consecutive failures → alert |
| Database health check | `pg_isready` in Docker healthcheck | Container unhealthy → restart |
| Push notification success rate | Application metrics | < 80% success rate over 5 min → alert |
| Disk space (PostgreSQL volume) | Host monitoring | > 80% full → warning; > 90% → critical |
| API error rate (5xx) | Nginx access logs or app metrics | > 5% of requests → alert |
| Container restarts | Docker daemon or `docker ps` | > 3 restarts in 10 min → alert |

### 10.3 Docker Compose Startup Order

The backend plan uses `depends_on` with `condition: service_healthy` for the postgres dependency. This is correct. However, note that:

1. The frontend Nginx container should also wait for the backend to be healthy before serving traffic (or start immediately and return 502 for API calls until backend is up — which is acceptable for an SPA).
2. Add `restart: unless-stopped` to ensure containers survive Docker daemon restarts.

---

## 11. Technical Debt Radar

Items that are acceptable for MVP but should be addressed post-MVP:

| Item | Priority | Effort |
|------|----------|--------|
| API versioning (`/api/v1/`) | HIGH | Low — one-line change before first deploy |
| Centralized logging (Loki/ELK) | MEDIUM | Medium |
| Prometheus metrics export | MEDIUM | Medium |
| Job queue for push notifications (BullMQ) | LOW | Medium |
| Email invitation service | MEDIUM | High (new service integration) |
| Materialized view for report summaries | LOW | Medium |
| CDN for frontend static assets | LOW | Low |
| PgBouncer connection pooling | LOW | Low |
| Horizontal scaling (multiple backend instances) | LOW | Medium |
| End-to-end encryption for sensitive data | LOW | High |
| A/B testing framework for child engagement | LOW | High |

---

## 12. Final Recommendations

### 12.1 Must-Fix Before Production (Blockers)

1. **HTTPS/TLS**: Deploy with Let's Encrypt or a valid SSL certificate. Google OAuth redirects and JWT tokens MUST travel over HTTPS.

2. **Production Docker Compose**: Remove direct port exposure for backend (3000) and database (5432). Use internal Docker network only. Add `restart: unless-stopped`, log rotation, and resource limits.

3. **Secrets Management**: Ensure all secrets are externalized from the codebase. Use `.env` files excluded from Git, or a secrets manager.

4. **Database Backups**: Implement automated daily `pg_dump` with retention policy. Test restoration.

5. **Timezone Strategy Acceptance**: Formally document the UTC-only behavior near midnight (TZ-01, TZ-02 from the QA report) and get written acceptance from the product owner. This is a design trade-off, not a bug.

6. **CI/CD Pipeline**: Implement at minimum: lint → test → build → deploy pipeline with health checks and rollback capability.

### 12.2 Should-Fix Before Production (High Priority)

7. **Content Security Policy**: Add CSP headers in Nginx to mitigate XSS risk, especially important given `localStorage` token storage.

8. **Rate Limiting Expansion**: Add rate limiting to OAuth initiation, child creation, and completion toggle endpoints.

9. **Health Check Depth**: Add migration status check and external dependency status to the health endpoint.

10. **Partial Unique Index**: Add database-level enforcement for the one-global-default-per-user rule on `notification_preferences`.

11. **API Versioning Prefix**: Add `/api/v1/` before any client code is written. This is a one-line change (`app.setGlobalPrefix('api/v1')`) with enormous future value.

12. **Refresh Token Multi-Device**: Document the single-refresh-token limitation. If multi-device support is required, plan migration to a `refresh_tokens` table.

### 12.3 Nice-to-Have (Post-MVP)

13. **Shared Type Package**: Extract DTOs into `packages/shared-types/` for compile-time frontend-backend contract verification.

14. **Prometheus Metrics**: Add application metrics for request duration, push delivery rate, and business metrics (daily active users, completions per day).

15. **Distributed Tracing**: Add OpenTelemetry instrumentation for cross-service request tracking.

16. **Load Testing**: Before scaling beyond 1,000 families, run load tests on the report aggregation and push notification dispatch paths.

---

## 13. Architectural Decision Record (ADR) — Timezone Strategy

**Title**: UTC-Only Backend with Local-Date Frontend Canonical Day Representation

**Status**: Proposed — requires stakeholder acceptance

**Context**: The backend stores all dates as UTC `DATE` type. The frontend sends the user's local `YYYY-MM-DD` as the canonical "day" identifier. The backend treats this string as a UTC calendar date and evaluates weekday matching against it.

**Decision**: The `date` field represents the **user's local calendar date**, not the UTC instant. For users in timezones close to UTC (±4 hours), this works intuitively. For users in extreme timezones (UTC+10, UTC-8), there is a window near midnight where the local day differs from the UTC day. In these cases, the dashboard may show chores for the "wrong" weekday relative to the backend's UTC evaluation.

**Consequences**:
- **Positive**: No timezone logic on the backend. Simpler queries, no timezone conversion bugs in report aggregation.
- **Negative**: Users in UTC+10 may see Wednesday's chores labeled but evaluated against Tuesday's UTC weekday during the 00:00–10:00 UTC window (10:00–00:00 local). This affects weekday-specific chores during those hours.

**Mitigation**: Document this behavior in the user-facing help. For the primary target audience (Russian-speaking families, predominantly UTC+2 to UTC+12), the window of confusion is during early morning hours (midnight to ~10 AM local) when children are typically not using the app.

---

## 14. Summary

The **Kids Chore Tracker** implementation plans are thorough, well-structured, and architecturally sound for the target use case. The modular NestJS backend, Signal-based Angular frontend, PostgreSQL data model, and Docker Compose deployment provide a solid foundation.

**Key architectural strengths**:
- Clean separation of concerns across all layers
- Family-scoped data isolation via JWT claims
- Efficient bitmask encoding for weekday scheduling
- Optimistic UI with offline-first completion tracking
- Comprehensive QA strategy with 50 P0 test scenarios

**Critical DevOps gaps to address**:
1. CI/CD pipeline definition and automation
2. HTTPS/TLS termination
3. Database backup and restore procedures
4. Secrets management hardening
5. Timezone strategy stakeholder acceptance
6. Production Docker Compose hardening (port exposure, restart policies, log rotation)

With these gaps addressed, the solution is **ready for Sprint 1 implementation** and can progress through the four-sprint delivery plan with confidence.