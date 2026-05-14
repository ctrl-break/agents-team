# Backend Implementation Plan: Kids Chore Tracker

**Status**: Draft — based on approved specification `docs/specs/latest-plan.md`

---

## 1. Backend Responsibilities

The backend is a NestJS REST API server responsible for:

| # | Responsibility | Details |
|---|---------------|---------|
| 1 | **Authentication & Authorization** | Google OAuth 2.0 flow via Passport, JWT access + refresh tokens, role-based guards (`parent` / `child`), family-scoped data access enforcement. |
| 2 | **User & Family Management** | Parent registration, child invitation by email, family group creation, user profile CRUD, parent↔child binding. |
| 3 | **Chore Lifecycle** | Full CRUD for chores with schedule type (`daily_weekday` / `weekly`), weekday bitmask, active/inactive toggling, creator and assignee tracking. |
| 4 | **Completion Tracking** | Record and query daily completions per chore per user, idempotent toggle (mark done / undo), date-bounded validation (today-only for daily chores, week-bound for weekly). |
| 5 | **Report Aggregation** | Period-based aggregation queries: completion rate, missed tasks, per-day breakdown for chart data; role-filtered (parent sees any child, child sees self only). |
| 6 | **Push Notification Delivery** | Store Web Push subscriptions, CRUD for per-chore notification preferences (time, days, enabled flag), scheduled cron job to dispatch push payloads via `web-push` library. |
| 7 | **Health & Observability** | Docker healthcheck endpoint, structured JSON logging, OpenAPI/Swagger auto-documentation. |
| 8 | **Timezone Boundary** | All dates stored and processed in UTC; server is timezone-agnostic — the `date` field represents the UTC calendar date; frontend adjusts to local. |

---

## 2. Technology Stack

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Runtime | Node.js | 20 LTS | Required by spec, long-term support |
| Framework | NestJS | 10.x | Spec requirement, mature DI, modular architecture |
| Language | TypeScript | 5.x | Strict mode, full type safety |
| ORM | TypeORM | 0.3.x | First-class NestJS integration, migrations, repository pattern |
| Database | PostgreSQL | 16 | Spec requirement, JSONB for flexible schedules |
| Auth | Passport + `@nestjs/passport` | — | Google OAuth 2.0 strategy, JWT strategy |
| JWT | `@nestjs/jwt` | 10.x | Access (15 min) + Refresh (7 days) token pair |
| Push | `web-push` | 3.x | VAPID-based Web Push Protocol |
| Scheduling | `@nestjs/schedule` | 4.x | Cron decorators for push notification dispatch |
| Validation | `class-validator` + `class-transformer` | — | DTO validation pipes |
| OpenAPI | `@nestjs/swagger` | 7.x | Auto-generated Swagger docs |
| Testing | Jest (built-in NestJS) | 29.x | Unit + integration + e2e |

---

## 3. Data Model (PostgreSQL + TypeORM Entities)

### 3.1 Entity-Relationship Diagram (Logical)

```
┌──────────────┐       ┌─────────────────┐       ┌──────────────┐
│   families   │       │     users       │       │   chores     │
├──────────────┤       ├─────────────────┤       ├──────────────┤
│ id (PK)      │◄──────│ family_id (FK)  │       │ id (PK)      │
│ name         │  1:N  │ id (PK)         │──┐    │ title        │
│ created_at   │       │ google_id       │  │    │ description  │
│ updated_at   │       │ email           │  │    │ schedule_type│
└──────────────┘       │ display_name    │  │    │ weekdays     │
                       │ role (enum)     │  │    │ is_active    │
                       │ avatar_url      │  │    │ created_by   │
                       │ refresh_token   │  │    │ assigned_to  │
                       │ created_at      │  │    │ created_at   │
                       │ updated_at      │  │    │ updated_at   │
                       └─────────────────┘  │    └──────────────┘
                                            │          │
                                            │    ┌─────┘
                                            │    │ 1:N
                                            │    ▼
                               ┌────────────┴───────────┐
                               │    chore_completions    │
                               ├────────────────────────┤
                               │ id (PK)                │
                               │ chore_id (FK)          │
                               │ user_id (FK)           │
                               │ date (DATE)            │
                               │ completed_at (TIMESTAMPTZ)│
                               │ created_at             │
                               └────────────────────────┘

┌──────────────────────┐    ┌──────────────────────────────┐
│ push_subscriptions   │    │ notification_preferences     │
├──────────────────────┤    ├──────────────────────────────┤
│ id (PK)              │    │ id (PK)                      │
│ user_id (FK)         │    │ user_id (FK)                 │
│ endpoint             │    │ chore_id (FK, nullable)      │
│ p256dh               │    │ time (TIME)                  │
│ auth                 │    │ days (bitmask/INT2)          │
│ device_info          │    │ enabled (BOOLEAN)            │
│ created_at           │    │ created_at / updated_at      │
│ updated_at           │    └──────────────────────────────┘
└──────────────────────┘
```

### 3.2 Detailed Entity Definitions

#### `Family`

```typescript
@Entity('families')
export class Family {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ length: 100 })
  name: string; // default: parent's display_name + " Family"

  @OneToMany(() => User, (user) => user.family)
  members: User[];

  @CreateDateColumn({ type: 'timestamptz' })
  created_at: Date;

  @UpdateDateColumn({ type: 'timestamptz' })
  updated_at: Date;
}
```

#### `User`

```typescript
export enum UserRole {
  PARENT = 'parent',
  CHILD = 'child',
}

@Entity('users')
@Unique(['email'])
@Unique(['google_id'])
export class User {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ length: 255, unique: true })
  google_id: string; // Google OAuth sub claim

  @Column({ length: 320, unique: true })
  email: string;

  @Column({ length: 150 })
  display_name: string;

  @Column({ type: 'enum', enum: UserRole })
  role: UserRole;

  @Column({ length: 500, nullable: true })
  avatar_url: string;

  @Column({ length: 500, nullable: true })
  refresh_token_hash: string; // bcrypt-hashed refresh token

  @ManyToOne(() => Family, (family) => family.members, { nullable: false })
  @JoinColumn({ name: 'family_id' })
  family: Family;

  @Column({ name: 'family_id' })
  family_id: string;

  // For children: which parent manages them
  @ManyToOne(() => User, { nullable: true })
  @JoinColumn({ name: 'parent_id' })
  parent: User;

  @Column({ name: 'parent_id', nullable: true })
  parent_id: string;

  @CreateDateColumn({ type: 'timestamptz' })
  created_at: Date;

  @UpdateDateColumn({ type: 'timestamptz' })
  updated_at: Date;
}
```

#### `Chore`

```typescript
export enum ScheduleType {
  DAILY_WEEKDAY = 'daily_weekday', // Конкретный день недели
  WEEKLY = 'weekly',               // На неделе (без фиксации дня)
}

@Entity('chores')
export class Chore {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ length: 200 })
  title: string;

  @Column({ type: 'text', nullable: true })
  description: string;

  @Column({ type: 'enum', enum: ScheduleType })
  schedule_type: ScheduleType;

  /**
   * Bitmask for weekdays (1=Mon, 2=Tue, 4=Wed, 8=Thu, 16=Fri, 32=Sat, 64=Sun).
   * For WEEKLY type, this is set to 127 (all days) and interpreted as "any day this week".
   * For DAILY_WEEKDAY, only the checked bits are relevant.
   * Stored as smallint (INT2) for efficiency.
   */
  @Column({ type: 'smallint', default: 0 })
  weekdays: number;

  @Column({ default: true })
  is_active: boolean;

  @ManyToOne(() => User, { nullable: false })
  @JoinColumn({ name: 'created_by' })
  created_by_user: User;

  @Column({ name: 'created_by' })
  created_by: string;

  @ManyToOne(() => User, { nullable: false })
  @JoinColumn({ name: 'assigned_to' })
  assigned_to_user: User;

  @Column({ name: 'assigned_to' })
  assigned_to: string;

  @CreateDateColumn({ type: 'timestamptz' })
  created_at: Date;

  @UpdateDateColumn({ type: 'timestamptz' })
  updated_at: Date;
}
```

#### `ChoreCompletion`

```typescript
@Entity('chore_completions')
@Unique(['chore_id', 'user_id', 'date']) // One completion per chore per user per day
export class ChoreCompletion {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @ManyToOne(() => Chore, { nullable: false, onDelete: 'CASCADE' })
  @JoinColumn({ name: 'chore_id' })
  chore: Chore;

  @Column({ name: 'chore_id' })
  chore_id: string;

  @ManyToOne(() => User, { nullable: false })
  @JoinColumn({ name: 'user_id' })
  user: User;

  @Column({ name: 'user_id' })
  user_id: string;

  @Column({ type: 'date' })
  date: string; // UTC date string YYYY-MM-DD

  @Column({ type: 'timestamptz' })
  completed_at: Date;

  @CreateDateColumn({ type: 'timestamptz' })
  created_at: Date;
}
```

#### `PushSubscription`

```typescript
@Entity('push_subscriptions')
@Unique(['user_id', 'endpoint']) // One subscription per device per user
export class PushSubscription {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @ManyToOne(() => User, { nullable: false, onDelete: 'CASCADE' })
  @JoinColumn({ name: 'user_id' })
  user: User;

  @Column({ name: 'user_id' })
  user_id: string;

  @Column({ type: 'text' })
  endpoint: string;

  @Column({ type: 'text' })
  p256dh: string;

  @Column({ type: 'text' })
  auth: string;

  @Column({ length: 300, nullable: true })
  device_info: string; // User-Agent or device name

  @Column({ type: 'timestamptz', nullable: true })
  last_used_at: Date;

  @CreateDateColumn({ type: 'timestamptz' })
  created_at: Date;

  @UpdateDateColumn({ type: 'timestamptz' })
  updated_at: Date;
}
```

#### `NotificationPreference`

```typescript
@Entity('notification_preferences')
@Unique(['user_id', 'chore_id']) // One preference per chore per user
export class NotificationPreference {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @ManyToOne(() => User, { nullable: false, onDelete: 'CASCADE' })
  @JoinColumn({ name: 'user_id' })
  user: User;

  @Column({ name: 'user_id' })
  user_id: string;

  @ManyToOne(() => Chore, { nullable: true, onDelete: 'CASCADE' })
  @JoinColumn({ name: 'chore_id' })
  chore: Chore;

  @Column({ name: 'chore_id', nullable: true })
  chore_id: string; // null = global default notification setting

  @Column({ type: 'time' })
  time: string; // HH:MM in UTC, e.g. "07:00"

  /**
   * Bitmask for days when notification should fire (same encoding as Chore.weekdays).
   */
  @Column({ type: 'smallint', default: 127 })
  days: number;

  @Column({ default: true })
  enabled: boolean;

  @CreateDateColumn({ type: 'timestamptz' })
  created_at: Date;

  @UpdateDateColumn({ type: 'timestamptz' })
  updated_at: Date;
}
```

### 3.3 Indexing Strategy

| Table | Index | Type | Purpose |
|-------|-------|------|---------|
| `users` | `email` | UNIQUE BTREE | Login lookup, duplicate prevention |
| `users` | `google_id` | UNIQUE BTREE | OAuth lookup |
| `users` | `family_id` | BTREE | Family-scoped queries |
| `users` | `parent_id` | BTREE | "Get all children of parent" |
| `chores` | `assigned_to` | BTREE | User-scoped chore listing |
| `chores` | `(assigned_to, is_active)` | BTREE | Active chores for dashboard |
| `chore_completions` | `(chore_id, user_id, date)` | UNIQUE BTREE | Idempotency guarantee |
| `chore_completions` | `(user_id, date)` | BTREE | Report aggregation per user per period |
| `push_subscriptions` | `(user_id, endpoint)` | UNIQUE BTREE | Deduplication |
| `notification_preferences` | `(user_id, chore_id)` | UNIQUE BTREE | Lookup per user per chore |

### 3.4 Weekday Bitmask Convention

```
Mon = 1   (0b0000001 = 1)
Tue = 2   (0b0000010 = 2)
Wed = 4   (0b0000100 = 4)
Thu = 8   (0b0001000 = 8)
Fri = 16  (0b0010000 = 16)
Sat = 32  (0b0100000 = 32)
Sun = 64  (0b1000000 = 64)

All  = 127 (0b1111111)
```

Helper utility (server-side):

```typescript
// Check if a bitmask includes a given weekday (0=Mon ... 6=Sun)
export function isWeekdaySet(bitmask: number, weekdayIndex: number): boolean {
  return (bitmask & (1 << weekdayIndex)) !== 0;
}

// Get ISO weekday index from bit position (0=Mon)
export function isoWeekdayToBitIndex(isoWeekday: number): number {
  // ISO: 1=Mon ... 7=Sun → bit index: 0=Mon ... 6=Sun
  return isoWeekday - 1;
}
```

---

## 4. Module Architecture

```
apps/backend/src/
├── main.ts                          # Bootstrap, global pipes, swagger, CORS
├── app.module.ts                    # Root module imports
├── common/
│   ├── decorators/
│   │   ├── current-user.decorator.ts    # @CurrentUser() param decorator
│   │   └── roles.decorator.ts           # @Roles('parent','child')
│   ├── guards/
│   │   ├── jwt-auth.guard.ts            # JWT verification
│   │   ├── google-oauth.guard.ts        # Google OAuth guard
│   │   └── roles.guard.ts               # Role-based access
│   ├── filters/
│   │   └── http-exception.filter.ts     # Standardized error responses
│   ├── interceptors/
│   │   └── family-scope.interceptor.ts  # Injects family_id into query context
│   ├── pipes/
│   │   └── date-validation.pipe.ts      # Validates date string formats
│   └── utils/
│       ├── weekday-bitmask.util.ts      # Bitmask helpers
│       └── date-utils.ts               # UTC date boundary helpers
├── auth/
│   ├── auth.module.ts
│   ├── auth.controller.ts           # GET /auth/google, GET /auth/google/callback,
│   │                                # POST /auth/refresh, POST /auth/logout
│   ├── auth.service.ts              # OAuth flow, JWT issuance, token rotation
│   ├── strategies/
│   │   ├── google.strategy.ts       # Passport Google OAuth 2.0
│   │   └── jwt.strategy.ts          # Passport JWT (access token)
│   └── dto/
│       ├── google-auth.dto.ts
│       └── token-response.dto.ts    # { access_token, refresh_token, expires_in }
├── users/
│   ├── users.module.ts
│   ├── users.controller.ts          # GET /users/me, PATCH /users/me,
│   │                                # GET /users/children (parent),
│   │                                # POST /users/children (parent adds child),
│   │                                # DELETE /users/children/:id
│   ├── users.service.ts             # Profile management, child linking
│   └── dto/
│       ├── update-profile.dto.ts
│       ├── add-child.dto.ts         # { email: string }
│       └── user-response.dto.ts
├── chores/
│   ├── chores.module.ts
│   ├── chores.controller.ts         # GET /chores, POST /chores, GET /chores/:id,
│   │                                # PATCH /chores/:id, DELETE /chores/:id,
│   │                                # GET /chores/dashboard?date=&user_id=
│   ├── chores.service.ts            # CRUD + authorization checks
│   └── dto/
│       ├── create-chore.dto.ts
│       ├── update-chore.dto.ts
│       ├── chore-query.dto.ts       # Filters: assigned_to, is_active, schedule_type
│       └── chore-response.dto.ts
├── completions/
│   ├── completions.module.ts
│   ├── completions.controller.ts    # POST /completions (toggle),
│   │                                # GET /completions?chore_id=&date=&user_id=
│   │                                # DELETE /completions/:id
│   ├── completions.service.ts       # Toggle logic, date validation, uniqueness
│   └── dto/
│       ├── toggle-completion.dto.ts # { chore_id, date }
│       └── completion-response.dto.ts
├── reports/
│   ├── reports.module.ts
│   ├── reports.controller.ts        # GET /reports?user_id=&start_date=&end_date=
│   │                                # GET /reports/summary?user_id=&start_date=&end_date=
│   ├── reports.service.ts           # Aggregation queries, percentage calculation
│   └── dto/
│       ├── report-query.dto.ts
│       └── report-response.dto.ts   # { summary, daily_breakdown[], completions[], missed[] }
├── notifications/
│   ├── notifications.module.ts
│   ├── notifications.controller.ts  # POST /notifications/subscribe,
│   │                                # DELETE /notifications/subscribe/:id,
│   │                                # GET /notifications/preferences,
│   │                                # PUT /notifications/preferences/:id
│   ├── notifications.service.ts     # Subscription management, preferences CRUD
│   ├── notifications.scheduler.ts   # @Cron every minute: query due notifications, dispatch
│   ├── push.service.ts              # web-push sendNotification wrapper, VAPID config
│   └── dto/
│       ├── push-subscription.dto.ts # { endpoint, keys: { p256dh, auth } }
│       ├── notification-preference.dto.ts
│       └── update-preference.dto.ts
└── health/
    ├── health.module.ts             # Terminus-based health checks
    └── health.controller.ts         # GET /health → { status, db, uptime }
```

---

## 5. API Design (REST Endpoints)

### 5.1 Authentication (`/api/auth`)

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| `GET` | `/auth/google` | None | — | Redirect to Google OAuth consent screen |
| `GET` | `/auth/google/callback` | None | — | Google OAuth callback, returns JWT pair |
| `POST` | `/auth/refresh` | None | — | Body: `{ refresh_token }` → new token pair |
| `POST` | `/auth/logout` | JWT | any | Invalidate refresh token |

**OAuth Flow Details:**

1. Frontend redirects browser to `GET /api/auth/google`.
2. Backend (Passport Google Strategy) redirects to Google.
3. Google redirects back to `GET /api/auth/google/callback?code=...`.
4. Backend exchanges code for Google profile, upserts user, creates family if first-time parent.
5. Backend issues JWT `access_token` (15 min) and `refresh_token` (7 days, stored hashed).
6. Backend redirects to frontend URL `FRONTEND_URL/auth/callback?token=...&refresh_token=...`.

**Token Payload:**

```typescript
interface JwtPayload {
  sub: string;        // user.id
  email: string;
  role: 'parent' | 'child';
  family_id: string;
  iat: number;
  exp: number;
}
```

### 5.2 Users (`/api/users`)

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| `GET` | `/users/me` | JWT | any | Get current user profile |
| `PATCH` | `/users/me` | JWT | any | Update display_name, avatar_url |
| `GET` | `/users/children` | JWT | parent | List all children in my family |
| `POST` | `/users/children` | JWT | parent | Add child by email (invite flow) |
| `DELETE` | `/users/children/:id` | JWT | parent | Remove child from family |
| `GET` | `/users/family` | JWT | any | Get family info (members list) |

**POST /users/children logic:**

1. Parent sends `{ email: "child@gmail.com" }`.
2. Service checks email not already in another family.
3. If user with that email exists with role `child` and no parent → link to this parent.
4. If user doesn't exist → create a "pending" user record (still needs to log in via Google to activate).
5. Return child user object.

### 5.3 Chores (`/api/chores`)

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| `GET` | `/chores` | JWT | any | List chores (child: own only; parent: all children's, filtered by `?assigned_to=`) |
| `POST` | `/chores` | JWT | any | Create chore (parent can assign to any child; child can only assign to self) |
| `GET` | `/chores/:id` | JWT | any | Get single chore (with ownership check) |
| `PATCH` | `/chores/:id` | JWT | any | Update chore (parent: any child's chore; child: own chore only) |
| `DELETE` | `/chores/:id` | JWT | any | Delete chore (same ownership rules) |
| `GET` | `/chores/dashboard` | JWT | any | Get chores for a specific date with completion status. Query: `?date=YYYY-MM-DD&user_id=` |

**Dashboard endpoint logic:**

```sql
-- For given user_id and date:
-- 1. Get all active chores assigned to user
-- 2. For daily_weekday: filter by date's weekday in bitmask
-- 3. For weekly: always included (any day of the week)
-- 4. LEFT JOIN completions WHERE date = :date
-- 5. Return chores with { completed: boolean }
```

**Authorization matrix for Chores:**

| Action | Parent (own family) | Child (own chores) | Child (other's chores) |
|--------|---------------------|--------------------|------------------------|
| Create | ✅ Any child | ✅ Self-assigned | ❌ |
| Read | ✅ All family chores | ✅ Own only | ❌ |
| Update | ✅ All family chores | ✅ Own only | ❌ |
| Delete | ✅ All family chores | ✅ Own only | ❌ |

### 5.4 Completions (`/api/completions`)

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| `POST` | `/completions/toggle` | JWT | child/parent | Toggle completion for a chore on a date. Body: `{ chore_id, date }` |
| `GET` | `/completions` | JWT | any | List completions. Query: `?user_id=&chore_id=&date=&start_date=&end_date=` |
| `DELETE` | `/completions/:id` | JWT | child/parent | Remove a completion record |

**Toggle logic (POST /completions/toggle):**

1. Validate chore exists and user has access.
2. Validate that date is valid for this chore:
   - `daily_weekday`: date must be today (UTC) or a past date (for corrections). The weekday must be in chore's bitmask.
   - `weekly`: date must be within the current ISO week (Mon–Sun), or a past date within a previous week.
3. Check if completion already exists for `(chore_id, user_id, date)`:
   - If exists → DELETE it (undo completion).
   - If not exists → INSERT (mark completed).
4. Return the new state: `{ chore_id, user_id, date, completed: boolean }`.

### 5.5 Reports (`/api/reports`)

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| `GET` | `/reports/summary` | JWT | parent (all children) / child (self) | Aggregated summary. Query: `?user_id=&start_date=&end_date=` |
| `GET` | `/reports/daily` | JWT | parent/child | Daily breakdown. Query: `?user_id=&start_date=&end_date=` |
| `GET` | `/reports/details` | JWT | parent/child | List of all completions and missed chores. Query: `?user_id=&start_date=&end_date=` |

**Summary response:**

```typescript
interface ReportSummary {
  user_id: string;
  period: { start_date: string; end_date: string };
  total_assigned: number;       // total chore-day combinations expected
  total_completed: number;
  total_missed: number;
  completion_rate: number;      // 0.0 – 1.0
  by_weekday: {                 // breakdown by day of week
    day: number;                // 1=Mon ... 7=Sun
    assigned: number;
    completed: number;
    rate: number;
  }[];
}
```

**Daily breakdown response:**

```typescript
interface DailyBreakdown {
  user_id: string;
  days: {
    date: string;               // YYYY-MM-DD
    total: number;
    completed: number;
    missed: number;
    rate: number;
  }[];
}
```

**Implementation approach:** Single SQL query using a generated date series + chores × dates cross-join, then LEFT JOIN on completions. This avoids N+1 queries.

### 5.6 Notifications (`/api/notifications`)

| Method | Path | Auth | Role | Description |
|--------|------|------|------|-------------|
| `POST` | `/notifications/subscribe` | JWT | any | Register push subscription. Body: `{ endpoint, keys: { p256dh, auth } }` |
| `DELETE` | `/notifications/subscribe/:id` | JWT | any | Remove push subscription |
| `GET` | `/notifications/subscriptions` | JWT | any | List my subscriptions |
| `GET` | `/notifications/preferences` | JWT | any | List notification preferences (query: `?chore_id=`) |
| `PUT` | `/notifications/preferences` | JWT | any | Upsert preference. Body: `{ chore_id?, time, days, enabled }` |
| `DELETE` | `/notifications/preferences/:id` | JWT | any | Remove preference |

**Cron Job (every minute):**

```
1. Query notification_preferences WHERE enabled=true
   AND time = current UTC time (rounded to minute) HH:MM
   AND (days bitmask includes today's weekday)
2. For each preference, find the related chore and user
3. Look up user's push_subscriptions
4. For each subscription, call webPush.sendNotification()
5. On 410 Gone → delete subscription
6. On other errors → log, continue
```

---

## 6. Validation & Error Handling

### 6.1 DTO Validation (Global Pipe)

```typescript
// main.ts
app.useGlobalPipes(
  new ValidationPipe({
    whitelist: true,           // Strip unknown properties
    forbidNonWhitelisted: true, // Throw on unknown properties
    transform: true,            // Auto-transform types
    transformOptions: {
      enableImplicitConversion: true,
    },
  }),
);
```

### 6.2 Per-DTO Validation Rules

**CreateChoreDto:**

```typescript
export class CreateChoreDto {
  @IsString()
  @Length(1, 200)
  title: string;

  @IsOptional()
  @IsString()
  @MaxLength(1000)
  description?: string;

  @IsEnum(ScheduleType)
  schedule_type: ScheduleType;

  @IsInt()
  @Min(1)
  @Max(127)
  weekdays: number; // validated as valid bitmask

  @IsOptional()
  @IsBoolean()
  is_active?: boolean;

  @IsUUID('4')
  assigned_to: string; // must be self (child) or any family member (parent)

  @Validate(IsValidWeekdayBitmask) // Custom validator
  validateWeekdays(): void {}
}
```

**ToggleCompletionDto:**

```typescript
export class ToggleCompletionDto {
  @IsUUID('4')
  chore_id: string;

  @Matches(/^\d{4}-\d{2}-\d{2}$/)
  date: string; // YYYY-MM-DD, validated against chore schedule in service layer
}
```

**ReportQueryDto:**

```typescript
export class ReportQueryDto {
  @IsUUID('4')
  user_id: string;

  @Matches(/^\d{4}-\d{2}-\d{2}$/)
  start_date: string;

  @Matches(/^\d{4}-\d{2}-\d{2}$/)
  end_date: string;

  @Validate(IsEndAfterStart)
  validateDateRange(): void {}
}
```

### 6.3 Standardized Error Responses

```typescript
// All errors follow this shape:
interface ApiErrorResponse {
  statusCode: number;
  error: string;          // HTTP status text
  message: string | string[]; // Human-readable or array of validation messages
  timestamp: string;      // ISO-8601
  path: string;           // Request URL
}
```

**HTTP Status Code Map:**

| Scenario | Status |
|----------|--------|
| Validation failure | `400 Bad Request` |
| Missing/invalid JWT | `401 Unauthorized` |
| Insufficient role | `403 Forbidden` |
| Resource not found | `404 Not Found` |
| Duplicate (email, completion) | `409 Conflict` |
| Invalid date for chore | `422 Unprocessable Entity` |
| Internal error | `500 Internal Server Error` |

### 6.4 Business Logic Validation in Services

| Rule | Where | Error |
|------|-------|-------|
| Child cannot add another child | `UsersService.addChild()` | 403 |
| Email already in another family | `UsersService.addChild()` | 409 |
| Child can only create chores for self | `ChoresService.create()` | 403 |
| Cannot toggle completion for future date | `CompletionsService.toggle()` | 422 |
| Cannot toggle completion for chore on wrong weekday | `CompletionsService.toggle()` | 422 |
| Parent can only see children in own family | `ReportsService.getSummary()` | 403 |
| Chore must belong to current user's family | All chore endpoints | 403/404 |

---

## 7. Security Design

### 7.1 Family-Level Data Isolation (Row-Level Security)

Every query that returns user-scoped data must filter by `family_id` from the JWT:

```typescript
// In services, after extracting family_id from JWT:
async findChoreById(id: string, familyId: string): Promise<Chore> {
  const chore = await this.choreRepo.findOne({
    where: { id },
    relations: ['assigned_to_user'],
  });

  if (!chore) throw new NotFoundException('Chore not found');

  // Row-level check: chore's assigned user must be in same family
  if (chore.assigned_to_user.family_id !== familyId) {
    throw new NotFoundException('Chore not found'); // 404, not 403 (info leak prevention)
  }

  return chore;
}
```

### 7.2 JWT Token Strategy

| Token | Lifetime | Storage | Rotation |
|-------|----------|---------|----------|
| Access Token | 15 minutes | Memory (Angular Signal/state) | Issued on login + refresh |
| Refresh Token | 7 days | HttpOnly cookie or secure localStorage | Rotated on each use; old token invalidated |

**Refresh token rotation:** On each `POST /auth/refresh`, the old refresh token is invalidated (hash removed/replaced). This limits the damage window if a refresh token is stolen.

### 7.3 CORS Configuration

```typescript
// In production:
app.enableCors({
  origin: process.env.FRONTEND_URL, // e.g. https://kids-chores.example.com
  credentials: true,
  methods: ['GET', 'POST', 'PATCH', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization'],
});
```

### 7.4 Rate Limiting

Apply `@nestjs/throttler` on auth endpoints:

```typescript
@Throttle({ default: { limit: 5, ttl: 60000 } }) // 5 requests/min
@Post('refresh')
async refresh() {}
```

---

## 8. Push Notification Scheduler (Detailed Design)

### 8.1 Cron Job Flow

```typescript
@Injectable()
export class NotificationsScheduler {
  private readonly logger = new Logger(NotificationsScheduler.name);

  constructor(
    private readonly notificationsService: NotificationsService,
    private readonly pushService: PushService,
  ) {}

  @Cron(CronExpression.EVERY_MINUTE)
  async dispatchScheduledNotifications(): Promise<void> {
    const now = new Date();
    const currentUtcTime = now.toISOString().substring(11, 16); // "HH:MM"
    const currentWeekdayBit = 1 << ((now.getUTCDay() + 6) % 7); // Mon=0 → bit 0

    const duePreferences = await this.notificationsService.findDuePreferences(
      currentUtcTime,
      currentWeekdayBit,
    );

    for (const pref of duePreferences) {
      const subscriptions = await this.notificationsService.getSubscriptionsForUser(pref.user_id);

      for (const sub of subscriptions) {
        try {
          await this.pushService.send({
            subscription: sub,
            payload: {
              title: pref.chore?.title ?? 'Напоминание',
              body: pref.chore?.description ?? 'Пора выполнить задачу!',
              icon: '/assets/icons/icon-192x192.png',
              data: {
                chore_id: pref.chore_id,
                url: `/dashboard?date=${now.toISOString().substring(0, 10)}`,
              },
            },
          });
          sub.last_used_at = new Date();
        } catch (err) {
          if (err.statusCode === 410 || err.statusCode === 404) {
            // Subscription expired or unsubscribed
            await this.notificationsService.removeSubscription(sub.id);
            this.logger.warn(`Removed expired subscription ${sub.id}`);
          } else {
            this.logger.error(`Push failed for sub ${sub.id}: ${err.message}`);
          }
        }
      }
    }
  }
}
```

### 8.2 VAPID Configuration

```typescript
// In push.service.ts
import * as webPush from 'web-push';

@Injectable()
export class PushService {
  constructor() {
    webPush.setVapidDetails(
      'mailto:admin@example.com',
      process.env.VAPID_PUBLIC_KEY,
      process.env.VAPID_PRIVATE_KEY,
    );
  }

  async send(params: { subscription: PushSubscriptionEntity; payload: object }): Promise<void> {
    await webPush.sendNotification(
      {
        endpoint: params.subscription.endpoint,
        keys: {
          p256dh: params.subscription.p256dh,
          auth: params.subscription.auth,
        },
      },
      JSON.stringify(params.payload),
    );
  }
}
```

Generate VAPID keys once:
```bash
npx web-push generate-vapid-keys
# → store in .env: VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY
```

---

## 9. Database Migration Strategy

Using TypeORM migrations:

```bash
# Generate migration from entity changes
npm run typeorm migration:generate -- -d src/data-source.ts -n AddNotificationPreferences

# Run migrations
npm run typeorm migration:run -- -d src/data-source.ts

# Revert last migration
npm run typeorm migration:revert -- -d src/data-source.ts
```

**Migration execution order:**

1. `CreateFamiliesTable`
2. `CreateUsersTable`
3. `CreateChoresTable`
4. `CreateChoreCompletionsTable`
5. `CreatePushSubscriptionsTable`
6. `CreateNotificationPreferencesTable`
7. `AddIndexes`
8. `SeedDefaultData` (optional dev seed)

### Seed Data (for development)

```typescript
// seeds/001-dev-seed.ts
// Creates:
// - 1 parent user
// - 2 child users
// - 5 sample chores per child
// - Some completions in the past week
```

---

## 10. Environment Configuration

```bash
# .env.example
NODE_ENV=development
PORT=3000

# Database
DB_HOST=postgres
DB_PORT=5432
DB_NAME=kids_chores
DB_USER=kids_chores_user
DB_PASSWORD=secure_password

# Google OAuth
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxx
GOOGLE_CALLBACK_URL=http://localhost:3000/api/auth/google/callback

# JWT
JWT_ACCESS_SECRET=at-least-32-chars-random-string
JWT_REFRESH_SECRET=at-least-32-chars-random-string
JWT_ACCESS_EXPIRES_IN=15m
JWT_REFRESH_EXPIRES_IN=7d

# VAPID (Web Push)
VAPID_PUBLIC_KEY=BP...
VAPID_PRIVATE_KEY=xxx...
VAPID_SUBJECT=mailto:admin@example.com

# Frontend URL (for OAuth redirect and CORS)
FRONTEND_URL=http://localhost:4200
```

---

## 11. Docker Compose Integration

```yaml
# docker-compose.yml (backend portion)
services:
  backend:
    build:
      context: ./apps/backend
      dockerfile: Dockerfile
    ports:
      - '3000:3000'
    environment:
      - NODE_ENV=production
    env_file:
      - .env
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - app-network
    healthcheck:
      test: ['CMD', 'curl', '-f', 'http://localhost:3000/api/health']
      interval: 30s
      timeout: 5s
      retries: 3

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - '5432:5432'
    networks:
      - app-network
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -U ${DB_USER} -d ${DB_NAME}']
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  pgdata:

networks:
  app-network:
    driver: bridge
```

**Backend Dockerfile:**

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package*.json ./
EXPOSE 3000
CMD ["node", "dist/main.js"]
```

---

## 12. Testing Strategy

### 12.1 Unit Tests

**Coverage target:** ≥80% for services and utilities.

```typescript
// Example: chores.service.spec.ts
describe('ChoresService', () => {
  describe('create()', () => {
    it('should allow parent to create chore for any child in family', async () => {});
    it('should allow child to create chore for themselves only', async () => {});
    it('should throw 403 when child tries to create chore for another child', async () => {});
    it('should validate weekdays bitmask range (1-127)', async () => {});
  });

  describe('findDashboard()', () => {
    it('should return only chores scheduled for given weekday', async () => {});
    it('should include weekly chores regardless of weekday', async () => {});
    it('should include completion status for the requested date', async () => {});
    it('should exclude inactive chores', async () => {});
  });
});
```

```typescript
// Example: completions.service.spec.ts
describe('CompletionsService', () => {
  describe('toggle()', () => {
    it('should create completion when none exists', async () => {});
    it('should delete completion when one exists (undo)', async () => {});
    it('should throw 422 when date is in the future', async () => {});
    it('should throw 422 when weekday does not match daily_weekday chore', async () => {});
    it('should allow completion on any weekday for weekly chore', async () => {});
    it('should enforce uniqueness per (chore_id, user_id, date)', async () => {});
  });
});
```

```typescript
// Example: reports.service.spec.ts
describe('ReportsService', () => {
  describe('getSummary()', () => {
    it('should calculate correct completion rate', async () => {});
    it('should only include data for the specified user', async () => {});
    it('should filter by date range', async () => {});
    it('should return 0% for period with no chores', async () => {});
    it('should return 100% when all chores completed', async () => {});
  });
});
```

### 12.2 Integration Tests

Test each module with a real PostgreSQL test database (Dockerized or in-memory via `pg-mem` for speed):

```typescript
// Use @nestjs/testing Test.createTestingModule with TypeOrmModule.forRoot({ database: ':memory:' or test DB })
describe('ChoresController (integration)', () => {
  let app: INestApplication;

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({
      imports: [AppModule],
    })
      .overrideProvider(DataSource)
      .useValue(testDataSource)
      .compile();

    app = moduleRef.createNestApplication();
    await app.init();
  });

  it('POST /api/chores → 201 with valid body', async () => {
    return request(app.getHttpServer())
      .post('/api/chores')
      .set('Authorization', `Bearer ${parentToken}`)
      .send({ title: 'Test', schedule_type: 'daily_weekday', weekdays: 31, assigned_to: childId })
      .expect(201);
  });

  it('POST /api/chores → 403 for child assigning to another child', async () => {
    return request(app.getHttpServer())
      .post('/api/chores')
      .set('Authorization', `Bearer ${childToken}`)
      .send({ title: 'Test', schedule_type: 'daily_weekday', weekdays: 31, assigned_to: otherChildId })
      .expect(403);
  });
});
```

### 12.3 E2E Tests

Implemented with Playwright or Cypress at the frontend level. Backend E2E considerations:

- Spin up full Docker Compose environment.
- Use a dedicated test Google OAuth account (or mock the Google endpoint).
- Test the full flow: OAuth → create child → create chore → toggle completion → generate report → configure notification.

### 12.4 Contract Testing (OpenAPI)

NestJS Swagger auto-generates OpenAPI 3.0 spec from decorators. Validate that:

- All DTOs have `@ApiProperty()` decorators.
- All controllers have `@ApiTags()`, `@ApiOperation()`, `@ApiResponse()`.
- Frontend team can generate an API client from `GET /api/docs-json`.

---

## 13. Observability

### 13.1 Structured Logging

```typescript
// Use NestJS built-in Logger with JSON format in production:
// main.ts
app.useLogger(
  process.env.NODE_ENV === 'production'
    ? new Logger({ format: 'json' })
    : new Logger({ format: 'pretty' }),
);
```

### 13.2 Health Check

```typescript
// health.controller.ts
@Controller('health')
export class HealthController {
  constructor(
    private health: HealthCheckService,
    private db: TypeOrmHealthIndicator,
  ) {}

  @Get()
  @HealthCheck()
  check() {
    return this.health.check([
      () => this.db.pingCheck('database', { timeout: 3000 }),
      () => ({ uptime: { status: 'up', uptime: process.uptime() } }),
    ]);
  }
}
```

### 13.3 Performance Considerations

- Use `QueryBuilder` for report aggregation to avoid loading all rows into memory.
- Add pagination to `/chores` and `/completions` endpoints (cursor-based or offset-based).
- Index the `chore_completions(user_id, date)` composite for report queries.
- Consider materialized view for report summaries if data volume grows (post-MVP).

---

## 14. Sprint-Aligned Implementation Sequence

### Sprint 1: Foundation (Auth + Users + Family)

**Backend tasks:**
- Initialize NestJS project with TypeORM, config, health module.
- Set up Docker Compose with postgres service.
- Implement `Family` and `User` entities + migrations.
- Implement Google OAuth strategy + JWT issuance.
- Implement `UsersModule`: `/users/me`, `/users/children` (add/list).
- Write unit tests for AuthService and UsersService.

**Deliverable:** Working Google login, parent can add child emails, JWT-secured endpoints.

### Sprint 2: Chores + Completions

**Backend tasks:**
- Implement `Chore` and `ChoreCompletion` entities + migrations.
- Implement `ChoresModule`: full CRUD with authorization matrix.
- Implement `CompletionsModule`: toggle logic with date/weekday validation.
- Implement `/chores/dashboard` endpoint.
- Write unit + integration tests.
- Add API decorators for Swagger docs.

**Deliverable:** Parent and child can create chores, child can mark them done.

### Sprint 3: Push Notifications

**Backend tasks:**
- Implement `PushSubscription` and `NotificationPreference` entities + migrations.
- Implement `NotificationsModule`: subscribe/unsubscribe, preferences CRUD.
- Implement `PushService` with web-push library.
- Implement `NotificationsScheduler` cron job.
- Handle expired subscription cleanup.
- Add VAPID key generation to setup docs.

**Deliverable:** Push notifications fire at configured times.

### Sprint 4: Reports + Polish

**Backend tasks:**
- Implement report aggregation queries in `ReportsService`.
- Implement `/reports/summary`, `/reports/daily`, `/reports/details`.
- Performance optimization: query tuning, index verification.
- Full integration test suite.
- Swagger documentation complete.
- Final Docker Compose validation.

**Deliverable:** Reports work, API documented, production-ready.

---

## 15. Key Design Decisions & Rationale

| Decision | Rationale |
|----------|-----------|
| **Weekdays as bitmask (smallint)** | More efficient than JSONB for this use case; bitwise operations are fast in PostgreSQL; easy to query (`weekdays & bit > 0`). |
| **UUID v4 for all primary keys** | Avoids sequential ID guessing; safe for client-side ID generation if needed later. |
| **Refresh token stored as hash** | If DB is compromised, attackers cannot use raw refresh tokens. |
| **Separate `PushSubscription` and `NotificationPreference`** | One user can have multiple devices; preferences are device-agnostic but per-chore. |
| **Toggle pattern for completions** | POST `/completions/toggle` is simpler than separate mark/unmark endpoints; idempotent; returns new state. |
| **UTC-only on backend** | Avoids timezone ambiguity; frontend is responsible for local time display; scheduled notifications use UTC time stored by the user (they configure in local time, frontend converts to UTC before saving). |
| **Family-based isolation via `family_id` in JWT** | Every query can be scoped without extra DB lookups; prevents cross-family data leaks at the service layer. |
| **TypeORM over Prisma** | First-class NestJS integration (`@nestjs/typeorm`); mature migration system; repository pattern aligns with NestJS service design. |

---

## 16. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Google OAuth token expiration during session | User logged out unexpectedly | Refresh token rotation; silent refresh in HTTP interceptor |
| Web Push not supported on iOS Safari <16.4 | iOS child users don't get notifications | Graceful degradation; detect support on frontend, hide notification settings if unsupported |
| Push subscription expiration (browser rotates keys) | Silent delivery failure | Handle 410 Gone in scheduler; prompt re-subscribe on frontend |
| Report query performance with large date ranges | Slow API response | Add pagination; consider materialized views for post-MVP; limit max range to 90 days |
| Child email collision (two parents try to add same child) | Data integrity violation | `UNIQUE(email)` constraint + 409 Conflict response; clear error message |
| Docker volume data loss | All data lost | Document backup procedures; consider pg_dump cron in post-MVP |

---

This plan provides a complete, implementation-ready backend design covering all modules, data models, API contracts, validation rules, security patterns, and testing strategies as specified in the approved specification `docs/specs/latest-plan.md`. The architecture is aligned with the sprint-based delivery plan and ready for immediate implementation.