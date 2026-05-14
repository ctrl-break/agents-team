# QA Strategy Report: Kids Chore Tracker

**Status**: Final  
**Based on**: `docs/specs/latest-plan.md` — approved specification  
**References**: Backend Implementation Plan, Frontend Implementation Plan  
**QA Engineer**: Senior QA Engineer  
**Date**: 2025-04-15

---

## 1. Executive Summary

This QA strategy validates the **Kids Chore Tracker** — an SPA/PWA web application for children and parents to manage daily chores, track completions, receive push notifications, and generate reports. The application stack is **Angular 17+ (frontend)**, **NestJS (backend)**, **PostgreSQL 16**, containerized via **Docker Compose**, with **Google OAuth 2.0** authentication and **JWT** session management.

The strategy covers all **10 user stories** (US-01 through US-10), all **8 acceptance criteria**, and all **4 delivery sprints**. It includes test scenarios, happy paths, edge cases, negative scenarios, regression risks, and release blockers.

**Overall Release Readiness**: The specification and implementation plans are thorough. However, several architectural risks (timezone handling near midnight, iOS push limitations, offline sync conflicts) warrant focused testing before any release.

---

## 2. Test Scope Overview

### 2.1 In Scope

| Layer | What | How |
|-------|------|-----|
| Unit Tests | NestJS services, Angular components, stores, pipes, interceptors | Jest / Jasmine |
| Integration Tests | API endpoints with real PostgreSQL test DB, service+store+component | NestJS testing + Angular TestBed |
| E2E Tests | Full user flows across all roles | Playwright |
| PWA Tests | Installability, offline mode, service worker caching | Lighthouse + manual |
| API Contract Tests | Request/response shapes, error codes, Swagger spec | OpenAPI validation |
| Security Tests | Role-based access, family isolation, JWT expiry/refresh, CORS | Manual + automated |
| Accessibility Tests | Keyboard navigation, screen reader, color contrast | axe-core + manual |

### 2.2 Out of Scope (Post-MVP)

- Load/stress testing
- Penetration testing
- Cross-region multi-datacenter failover
- Email deliverability testing (invitation emails)

---

## 3. Test Scenarios by User Story

### US-01: Parent Registers via Google

| # | Scenario | Type | Priority |
|---|----------|------|----------|
| US-01-H1 | Parent clicks "Войти через Google", completes OAuth consent, is redirected to `/dashboard` with JWT tokens stored | Happy Path | P0 |
| US-01-H2 | Returning parent with valid refresh token lands directly on `/dashboard` without re-authentication | Happy Path | P0 |
| US-01-E1 | Parent's access token expires mid-session; next API call triggers silent refresh via interceptor, original request retried successfully | Edge Case | P0 |
| US-01-E2 | Parent has multiple Google accounts; Google shows account chooser (`prompt=select_account`), parent selects correct account | Edge Case | P1 |
| US-01-E3 | Parent opens app in two browser tabs; one tab refreshes token, second tab picks up new token via `localStorage` | Edge Case | P1 |
| US-01-N1 | Parent cancels Google OAuth consent screen → redirected back to `/login` with no tokens, no error crash | Negative | P1 |
| US-01-N2 | Google OAuth callback returns error (`?error=access_denied`) → frontend shows user-friendly message "Вход отменён" | Negative | P1 |
| US-01-N3 | Refresh token expired (7 days) → any API call returns 401, interceptor fails refresh, user redirected to `/login` with message "Сессия истекла. Войдите снова." | Negative | P0 |
| US-01-N4 | Backend Google OAuth client secret misconfigured → backend returns 500, frontend shows snackbar "Ошибка авторизации. Попробуйте позже." | Negative | P1 |
| US-01-N5 | Network failure during token refresh → refresh fails, user stays on current page, next action shows auth error | Negative | P1 |

### US-02: Parent Adds Child Email

| # | Scenario | Type | Priority |
|---|----------|------|----------|
| US-02-H1 | Parent navigates to `/kids`, clicks "Добавить", enters valid child email not in any family, submits → child appears in list | Happy Path | P0 |
| US-02-H2 | Parent adds second child → both children appear in list, each with correct name and stats | Happy Path | P0 |
| US-02-E1 | Child email belongs to existing user with `role=child` and `parent_id=null` → child is linked to this parent | Edge Case | P0 |
| US-02-E2 | Child email does not yet exist in system → backend creates "pending" user record, child later logs in via Google to activate | Edge Case | P0 |
| US-02-E3 | Parent adds child with email containing uppercase letters → normalized to lowercase, no duplicate | Edge Case | P1 |
| US-02-E4 | Parent adds child, then child logs in via Google with different email → mismatch; child cannot join family | Edge Case | P1 |
| US-02-N1 | Parent enters email already belonging to another family → backend returns 409 Conflict, frontend shows "Этот email уже привязан к другой семье" | Negative | P0 |
| US-02-N2 | Parent enters invalid email format (`"notanemail"`) → client-side validation rejects, submit button disabled | Negative | P1 |
| US-02-N3 | Parent enters own email → backend rejects (parent cannot be a child), returns 422 | Negative | P1 |
| US-02-N4 | Parent enters empty email → form validation shows "Email обязателен" | Negative | P2 |
| US-02-N5 | Parent attempts to add child while not authenticated → 401, redirected to login | Negative | P0 |

### US-03: Child Logs In via Google

| # | Scenario | Type | Priority |
|---|----------|------|----------|
| US-03-H1 | Child (with pre-created user record from US-02) clicks "Войти через Google", completes OAuth, lands on `/dashboard` showing only own chores | Happy Path | P0 |
| US-03-H2 | Child with no pre-created record logs in → backend creates user with `role=child`, no family, child sees empty dashboard with prompt "Попросите родителя добавить вас" | Happy Path | P1 |
| US-03-E1 | Child logs in on mobile device → PWA install prompt shown, child installs app | Edge Case | P1 |
| US-03-E2 | Child uses shared family tablet → logs out, sibling logs in; no data leakage between siblings | Edge Case | P0 |
| US-03-N1 | Child attempts to access `/kids` or `/reports` directly via URL → RoleGuard redirects to `/dashboard`, route not accessible | Negative | P0 |
| US-03-N2 | Child's account deleted by parent → child's refresh token invalidated, next request 401, redirected to login, login shows "Аккаунт не найден" | Negative | P1 |
| US-03-N3 | Unauthorized user (no family, no parent) logs in → sees own dashboard but cannot view any chores (none assigned), sees guidance message | Negative | P2 |

### US-04: Create Chore with Weekday Binding

| # | Scenario | Type | Priority |
|---|----------|------|----------|
| US-04-H1 | Parent creates `daily_weekday` chore for child: title "Заправить кровать", weekdays Mon-Fri (bitmask 31), assigned to child → 201 Created, chore appears in child's list | Happy Path | P0 |
| US-04-H2 | Child creates `daily_weekday` chore for themselves: title "Сделать зарядку", weekdays Mon-Wed-Fri (bitmask 21) → 201 Created, assigned_to auto-set to self | Happy Path | P0 |
| US-04-H3 | Parent creates chore with description, all 7 days (bitmask 127) → chore visible every day of week | Happy Path | P1 |
| US-04-H4 | Parent creates chore with is_active=false → chore saved but not visible on dashboard | Happy Path | P1 |
| US-04-E1 | Parent sets weekdays to only Sunday (bitmask 64) → chore appears only on Sunday dashboard | Edge Case | P1 |
| US-04-E2 | Parent sets weekdays to only Monday (bitmask 1) → chore appears only on Monday | Edge Case | P1 |
| US-04-E3 | Parent creates chore with maximum length title (200 chars) → accepted | Edge Case | P2 |
| US-04-E4 | Parent creates chore with maximum length description (1000 chars) → accepted | Edge Case | P2 |
| US-04-N1 | Child attempts to create chore assigned to another child → backend returns 403 Forbidden | Negative | P0 |
| US-04-N2 | Title field empty → client-side validation rejects, shows "Название обязательно" | Negative | P1 |
| US-04-N3 | Title exceeds 200 characters → client-side validation rejects | Negative | P1 |
| US-04-N4 | weekdays bitmask = 0 (no days selected) → validation error "Выберите хотя бы один день" | Negative | P1 |
| US-04-N5 | weekdays bitmask > 127 → validation error "Неверная маска дней" | Negative | P1 |
| US-04-N6 | assigned_to UUID not a valid user → 404 Not Found | Negative | P1 |
| US-04-N7 | assigned_to user not in same family → 403 Forbidden (or 404 for info leak prevention) | Negative | P0 |

### US-05: Create "Weekly" Chore

| # | Scenario | Type | Priority |
|---|----------|------|----------|
| US-05-H1 | Parent creates `weekly` chore: "Убраться в комнате", assigned to child → weekdays auto-set to 127, appears on dashboard every day of week | Happy Path | P0 |
| US-05-H2 | Child creates `weekly` chore for themselves → 201 Created, schedule_type='weekly' | Happy Path | P0 |
| US-05-E1 | Weekly chore completed on Monday → completion recorded; chore still appears on Tuesday (weekly = any day, not one-time) | Edge Case | P0 |
| US-05-E2 | Weekly chore completed on Sunday (last day of ISO week) → completion recorded for Sunday | Edge Case | P1 |
| US-05-E3 | Switching chore type from `weekly` to `daily_weekday` in edit → weekdays field becomes editable, must select at least one day | Edge Case | P1 |
| US-05-N1 | Creating `weekly` chore with specific weekday subset → should not be possible; weekly always implies all days (127) | Negative | P1 |
| US-05-N2 | Same validation rules as US-04 (title required, description max length) apply | Negative | P1 |

### US-06: Mark Chore as Completed

| # | Scenario | Type | Priority |
|---|----------|------|----------|
| US-06-H1 | Child taps checkbox on a daily chore on the correct weekday → optimistic checkmark appears, API toggle succeeds, progress bar updates | Happy Path | P0 |
| US-06-H2 | Child taps checkbox on an already-completed chore → completion is undone (toggled off), progress bar decreases | Happy Path | P0 |
| US-06-H3 | Child completes a weekly chore on any day of the week → toggle succeeds | Happy Path | P0 |
| US-06-H4 | Parent marks completion for a child (acting on behalf) → toggle succeeds, user_id = child's ID | Happy Path | P1 |
| US-06-E1 | Child rapidly double-taps checkbox → first tap disables checkbox (`isToggling` flag), second tap ignored, only one API call sent | Edge Case | P0 |
| US-06-E2 | Child marks completion at 23:59 local time, then navigates to next day → completion recorded for the correct date (UTC boundary handled) | Edge Case | P1 |
| US-06-E3 | Child marks completion for a past date (correction) → backend allows for past dates with correct weekday match | Edge Case | P1 |
| US-06-E4 | Child marks completion while offline → optimistic update applied, queued in IndexedDB, synced on reconnect | Edge Case | P0 |
| US-06-E5 | Two offline completions queued, then device goes online → both synced in order, no duplicates | Edge Case | P1 |
| US-06-E6 | Offline completion conflicts with server state (already toggled by parent from another device) → 409 Conflict resolved by removing queue item silently | Edge Case | P1 |
| US-06-N1 | Child attempts to mark daily chore on wrong weekday → backend returns 422, frontend reverts optimistic update, shows "Отметка недоступна для этого дня" | Negative | P0 |
| US-06-N2 | Child attempts to mark chore for a future date → backend returns 422 Unprocessable Entity | Negative | P0 |
| US-06-N3 | Child attempts to mark chore that doesn't belong to them → 403 Forbidden | Negative | P0 |
| US-06-N4 | API call fails (network error) after optimistic update → revert optimistic update, show error snackbar, checkbox returns to original state | Negative | P0 |
| US-06-N5 | Child attempts to mark completion for a chore belonging to another family → 404 (info leak prevention) | Negative | P1 |
| US-06-N6 | Deleted chore completion toggle attempted → 404 Not Found | Negative | P1 |
| US-06-N7 | Chore is inactive → dashboard doesn't show it, toggle not possible (API would reject) | Negative | P1 |

### US-07: Parent Views Children's Status Today

| # | Scenario | Type | Priority |
|---|----------|------|----------|
| US-07-H1 | Parent opens `/dashboard`, selects child from dropdown → sees that child's chores for today with completion status | Happy Path | P0 |
| US-07-H2 | Parent sees progress bar and stats (total/completed/missed/rate) for selected child | Happy Path | P0 |
| US-07-H3 | Parent navigates to a past date via date navigator → sees historical completion status for that child on that date | Happy Path | P1 |
| US-07-H4 | Parent navigates to a future date → sees scheduled chores but completion checkboxes disabled with tooltip | Happy Path | P1 |
| US-07-E1 | Parent has only one child → kid selector shows child name, no dropdown needed, or dropdown with single option | Edge Case | P2 |
| US-07-E2 | Parent has multiple children, switches between them rapidly → each load cancels previous in-flight request, no flickering/stale data | Edge Case | P1 |
| US-07-E3 | Parent views dashboard at midnight → date rolls over, dashboard refreshes for the new day | Edge Case | P2 |
| US-07-N1 | Parent attempts to view dashboard for a non-existent child ID → empty state or error | Negative | P1 |
| US-07-N2 | Selected child has no chores for today → empty state "У {имя} пока нет задач на сегодня" | Negative | P1 |
| US-07-N3 | Parent tries to toggle completion from parent dashboard → should work (parent can mark for child) | Happy Path (verify) | P1 |

### US-08: Parent Builds Report

| # | Scenario | Type | Priority |
|---|----------|------|----------|
| US-08-H1 | Parent selects child, period (e.g., last 7 days), clicks "Применить" → summary cards show correct completion_rate, chart renders daily bars, detail lists populated | Happy Path | P0 |
| US-08-H2 | Parent views report where child has 100% completion → rate = 1.0, gold/star indicator shown | Happy Path | P1 |
| US-08-H3 | Parent views report where child has 0% completion → rate = 0.0, all items in "missed" list | Happy Path | P1 |
| US-08-H4 | Parent views report with mixed results → correct completed/missed categorization, chart bars proportional | Happy Path | P0 |
| US-08-E1 | Period is exactly 1 day → summary shows single-day stats, chart has one bar | Edge Case | P1 |
| US-08-E2 | Period spans month boundary (e.g., Jan 28 – Feb 5) → date handling correct across month boundary | Edge Case | P1 |
| US-08-E3 | Period spans DST change → UTC-based storage prevents issues; 24h day boundaries maintained | Edge Case | P1 |
| US-08-E4 | Period is maximum allowed (90 days) → report still loads within acceptable time (< 3 seconds) | Edge Case | P1 |
| US-08-E5 | Chart displays many days (90 bars) → bars are narrow but readable, no overlapping labels | Edge Case | P2 |
| US-08-E6 | Child has weekly chores — each completion counted correctly per day in report | Edge Case | P1 |
| US-08-N1 | Parent attempts to view report for child not in their family → 403 Forbidden | Negative | P0 |
| US-08-N2 | start_date > end_date → validation error "Дата начала должна быть раньше даты окончания" | Negative | P1 |
| US-08-N3 | Period > 90 days → backend rejects (or client-side caps range), shows validation message | Negative | P1 |
| US-08-N4 | start_date in the future → report returns empty data, "Нет данных за выбранный период" | Negative | P1 |
| US-08-N5 | Child has no chores at all in the selected period → report shows 0% with "В этом периоде не было задач" | Negative | P1 |
| US-08-N6 | No completions exist but chores do → 0% rate, all chores in missed list | Negative | P1 |
| US-08-N7 | Child user attempts to access `/reports` → RoleGuard blocks, redirects | Negative | P0 |

### US-09: Configure Push Notifications

| # | Scenario | Type | Priority |
|---|----------|------|----------|
| US-09-H1 | User opens notification settings, subscribes to push → browser permission prompt appears, user grants, subscription saved to backend, status shows "Подписан ✅" | Happy Path | P0 |
| US-09-H2 | User adds notification preference for specific chore: time 07:30, days Mon-Fri → preference saved, notification fires at 07:30 UTC on weekdays | Happy Path | P0 |
| US-09-H3 | User enables/disables notification preference via toggle → preferences updated, cron job respects enabled flag | Happy Path | P1 |
| US-09-H4 | User deletes notification preference → preference removed, no more notifications for that chore | Happy Path | P1 |
| US-09-H5 | User unsubscribes from push → subscription deleted from backend, status shows unsubscribed | Happy Path | P1 |
| US-09-E1 | User has multiple devices → multiple push subscriptions stored, notification sent to all devices | Edge Case | P1 |
| US-09-E2 | Browser push subscription expires (keys rotated) → backend scheduler receives 410 Gone, deletes subscription, frontend prompts re-subscribe on next visit | Edge Case | P0 |
| US-09-E3 | User configures notification time in local timezone → frontend converts to UTC before saving; notification fires at correct local time | Edge Case | P0 |
| US-09-E4 | Notification preference with chore_id=null → global default notification for all chores | Edge Case | P1 |
| US-09-E5 | User clicks on push notification → browser opens/focuses PWA, navigates to `/dashboard?date=...` | Edge Case | P1 |
| US-09-E6 | Cron job fires at exact minute → notification sent within 60 seconds of configured time | Edge Case | P1 |
| US-09-N1 | User denies browser notification permission → subscription not created, UI shows "Вы можете включить уведомления позже в настройках" | Negative | P1 |
| US-09-N2 | Browser doesn't support Web Push (iOS Safari < 16.4, or older browsers) → notification settings hidden, informational message shown | Negative | P1 |
| US-09-N3 | Push service returns error (not 410) → scheduler logs error, continues to next subscription, doesn't crash | Negative | P1 |
| US-09-N4 | VAPID keys misconfigured on backend → push sending fails, error logged, user never receives notification (no crash) | Negative | P2 |
| US-09-N5 | User adds notification preference with time but no chore selected → what happens? Server should handle nullable chore_id gracefully | Negative | P1 |
| US-09-N6 | Multiple preferences for same chore → upsert (PUT) replaces existing, unique constraint (user_id, chore_id) enforced | Negative | P1 |

### US-10: Install PWA

| # | Scenario | Type | Priority |
|---|----------|------|----------|
| US-10-H1 | User visits app on Android Chrome, `beforeinstallprompt` fires, user clicks "Установить" → app installed on home screen, opens in standalone mode | Happy Path | P0 |
| US-10-H2 | User opens installed PWA → app shell loads instantly from service worker cache, no network dependency for UI shell | Happy Path | P0 |
| US-10-H3 | User is offline, opens PWA → cached dashboard data shown, offline banner displayed, completion toggles queued | Happy Path | P0 |
| US-10-H4 | Service worker update available → snackbar "Доступна новая версия. [Обновить]" shown, user clicks, app reloads with new version | Happy Path | P1 |
| US-10-E1 | User dismisses install prompt → prompt not shown again immediately (browser cooldown), user can install via browser menu | Edge Case | P1 |
| US-10-E2 | `beforeinstallprompt` not fired (Firefox desktop, some Safari) → manual install instructions shown "Откройте меню браузера → Добавить на главный экран" | Edge Case | P1 |
| US-10-E3 | PWA installed, user opens browser version → `display-mode: standalone` media query detects browser mode, shows subtle "Открыть в приложении" hint | Edge Case | P2 |
| US-10-E4 | PWA icon rendered as maskable → adaptive icon on Android, fits within device shape | Edge Case | P2 |
| US-10-N1 | Service worker fails to register → app still functions as SPA, PWA features unavailable, no crash | Negative | P1 |
| US-10-N2 | Service worker update fails → current version continues working, error logged | Negative | P2 |
| US-10-N3 | IndexedDB not available (Safari private browsing) → offline queue falls back to in-memory, warning shown "Оффлайн-отметки не сохранятся если вы закроете вкладку" | Negative | P1 |

---

## 4. Cross-Cutting Test Scenarios

### 4.1 Authentication & Authorization Matrix

| Action | Parent (own family) | Child (own chores) | Child (other's chores) | Unauthenticated |
|--------|---------------------|--------------------|------------------------|-----------------|
| GET /api/chores | ✅ All family chores | ✅ Own only | ❌ 403 | ❌ 401 |
| POST /api/chores | ✅ Assign to any child | ✅ Self-assign only | ❌ 403 | ❌ 401 |
| PATCH /api/chores/:id | ✅ Any family chore | ✅ Own chore only | ❌ 403 | ❌ 401 |
| DELETE /api/chores/:id | ✅ Any family chore | ✅ Own chore only | ❌ 403 | ❌ 401 |
| POST /api/completions/toggle | ✅ For any child | ✅ For self only | ❌ 403 | ❌ 401 |
| GET /api/reports | ✅ For any child | ❌ 403 | ❌ 403 | ❌ 401 |
| GET /api/users/children | ✅ Own children | ❌ 403 | ❌ 403 | ❌ 401 |
| POST /api/users/children | ✅ Add child | ❌ 403 | ❌ 403 | ❌ 401 |
| DELETE /api/users/children/:id | ✅ Own child | ❌ 403 | ❌ 403 | ❌ 401 |

**Test Approach**: For each cell marked `❌`, create a dedicated negative test. For `✅`, create a happy path test. Pay special attention to the "Child (other's chores)" column — the backend must return 403 (or 404 for info-leak prevention).

### 4.2 Family Data Isolation

| # | Scenario | Priority |
|---|----------|----------|
| ISO-01 | Parent A creates chore for Child A1. Parent B (different family) attempts to read it → 404 Not Found | P0 |
| ISO-02 | Parent A attempts to add Child B1 (belongs to Parent B) → 409 Conflict | P0 |
| ISO-03 | Child A1 attempts to see Child A2's chores (same family, different child) → 403 Forbidden | P0 |
| ISO-04 | Parent A builds report for Child B1 (different family) → 403 Forbidden | P0 |
| ISO-05 | JWT token for Family A used to query Family B data directly via API → family_id in JWT doesn't match, query returns empty or 404 | P0 |

### 4.3 JWT Token Lifecycle

| # | Scenario | Priority |
|---|----------|----------|
| JWT-01 | Access token valid → request proceeds normally | P0 |
| JWT-02 | Access token expired, refresh token valid → silent refresh, retry succeeds | P0 |
| JWT-03 | Access token expired, refresh token expired → redirect to `/login`, clear state | P0 |
| JWT-04 | Access token expired, refresh token valid, but refresh endpoint returns 401 (token revoked) → redirect to `/login` | P0 |
| JWT-05 | Refresh token rotation: old refresh token invalidated after use → cannot be reused | P0 |
| JWT-06 | Tampered JWT (invalid signature) → 401 Unauthorized | P1 |
| JWT-07 | JWT with valid signature but non-existent user_id → 401 Unauthorized | P1 |
| JWT-08 | Concurrent requests when token expires → all queued, only one refresh call, all retried with new token | P1 |

### 4.4 Timezone & Date Boundary

| # | Scenario | Priority |
|---|----------|----------|
| TZ-01 | User in UTC+10, local time is Wednesday 01:00, UTC is Tuesday → dashboard shows Wednesday's chores but backend evaluates against UTC Tuesday → **CRITICAL: needs clarification or fix**. Per spec, backend is UTC-only. The frontend Plan describes this as "acceptable." | P0 |
| TZ-02 | User in UTC-8, local time is Monday 23:00, UTC is Tuesday 07:00 → dashboard shows Monday, but backend evaluates Tuesday chores. Same issue reversed. | P0 |
| TZ-03 | Date navigation: user selects "2025-04-15" in date picker → frontend sends exact date string to API, no timezone conversion needed | P1 |
| TZ-04 | Completion marked at 23:59 local → stored as UTC date; verify the stored date matches user's intended day | P0 |
| TZ-05 | Report period spanning DST transition → all 24-hour days counted correctly, no double-counting or gaps | P1 |
| TZ-06 | Notification time configured as 07:00 local → correctly converted to UTC on save, fires at correct local time | P0 |

### 4.5 Offline & Sync

| # | Scenario | Priority |
|---|----------|----------|
| OFF-01 | Go offline → dashboard shows cached data (from ngsw dataGroup `freshness` cache) | P0 |
| OFF-02 | Toggle completion offline → optimistic update in UI, item queued in IndexedDB | P0 |
| OFF-03 | Go online → OfflineQueueService drains queue, each item sent to API, queue cleared | P0 |
| OFF-04 | Offline queue item conflicts with server (409) → removed from queue silently, server state wins | P0 |
| OFF-05 | Offline queue item fails with non-409 error → stays in queue, retried on next online event | P1 |
| OFF-06 | Multiple offline toggles of same chore → queue contains multiple items; they should resolve correctly in order | P1 |
| OFF-07 | App closed while offline with queued items → on next open (online), sync triggered | P1 |
| OFF-08 | IndexedDB unavailable (Safari private mode) → in-memory fallback, warning shown | P1 |
| OFF-09 | Service worker serves stale app shell → update check on navigation, update prompt shown | P1 |
| OFF-10 | API data group cache expired while online → network request made, fresh data cached | P1 |

---

## 5. Regression Risk Analysis

### 5.1 High Regression Risk Areas

| Area | Risk | Why | Mitigation |
|------|------|-----|------------|
| **Completions toggle logic** | HIGH | Central to the app. Toggle involves: optimistic UI, API call, weekday validation, date validation, offline queue, progress recalculation. Any change here can cascade. | Dedicated completions E2E suite (E2E-04, E2E-05, E2E-09). Unit tests for every branch in `CompletionsService.toggle()`. |
| **Auth interceptor chain** | HIGH | Token refresh, concurrent request queuing, 401 handling. Bugs here lock users out or cause silent auth failures. | Unit tests for `AuthErrorInterceptor` with simulated 401 responses. E2E-10 for full refresh flow. |
| **Family data isolation** | HIGH | Cross-family data leak is a critical security and trust issue. Every new query or endpoint must enforce family_id scoping. | Integration tests for every endpoint with cross-family assertions (ISO-01 through ISO-05). |
| **Weekday bitmask logic** | MEDIUM | Bitmask encoding (1=Mon through 64=Sun) used in both chores and notification preferences. Off-by-one errors are subtle. | Dedicated unit tests for `weekday-bitmask.util.ts` with all boundary values. Property-based testing for all 128 possible masks. |
| **Timezone conversion** | MEDIUM | UTC-only backend + local-time-frontend pattern. The frontend plan acknowledges edge cases near midnight as "acceptable" — this is a design risk, not just a bug risk. | Explicit TZ test scenarios (TZ-01 through TZ-06). Test with browser timezone set to UTC+12, UTC-12, and UTC+0. |

### 5.2 Medium Regression Risk Areas

| Area | Risk | Why | Mitigation |
|------|------|-----|------------|
| **Push notification scheduler** | MEDIUM | Cron timing, subscription expiry (410), VAPID config. Failures are silent (user just doesn't get notification). | Logging/monitoring on push failures. Integration test with mock web-push. Manual test with real browser. |
| **Report aggregation queries** | MEDIUM | Complex SQL: date series generation, cross-join chores×dates, LEFT JOIN completions, percentage calculations. Performance risk for large ranges. | Integration tests with seeded data. Validate report math manually. Test with 90-day range. |
| **PWA service worker caching** | MEDIUM | Cache invalidation is hard. Stale data shown to users. Wrong caching strategy can break the app. | Lighthouse audit. Manual test: change data on server, verify freshness strategy fetches new data. |
| **Child email uniqueness enforcement** | MEDIUM | Duplicate child email across families violates data integrity. Race condition if two parents add same email simultaneously. | DB-level UNIQUE constraint + 409 handling. Test concurrent add-child requests. |

### 5.3 Low Regression Risk Areas

| Area | Risk | Why |
|------|------|-----|
| **UI layout/rendering** | LOW | Angular Material is stable. Layout changes are visually obvious. |
| **Static page routes** | LOW | Angular routing is stable. Route guards are simple boolean checks. |
| **Settings page (profile)** | LOW | Simple CRUD on user profile. Low complexity. |

---

## 6. Release Blockers

A **release blocker** is any issue that prevents the application from meeting its core acceptance criteria or causes data loss/security breach. The following items MUST be resolved before any production release:

### 6.1 Critical (P0 — Blocks Any Release)

| # | Blocker | Acceptance Criteria Affected | Rationale |
|---|---------|------------------------------|-----------|
| B-01 | **Google OAuth flow fails on any target browser** (Chrome, Firefox, Safari, Samsung Internet) | Parent/Child registration | Users cannot log in. App is unusable. |
| B-02 | **Cross-family data leak** — any endpoint returns data from a different family | Security | Data privacy violation. Unacceptable for a family app. |
| B-03 | **Child can view/edit another child's chores** | Role model (US-03, US-04) | Authorization failure. Children's data must be private. |
| B-04 | **Completion marked on wrong day due to timezone bug** (child marks Tuesday chore but it's recorded as Monday) | Completion tracking (US-06) | Core functionality broken. Undermines trust in reports. |
| B-05 | **Refresh token not invalidated after use** — token reuse possible | Security | Stolen refresh token grants indefinite access. |
| B-06 | **Data loss on completion toggle** — marked complete but not persisted | Completion tracking (US-06) | Core data integrity issue. |
| B-07 | **Database migration fails** — cannot deploy to production | Infrastructure | Deployment blocked. |

### 6.2 High (P1 — Blocks GA Release)

| # | Blocker | Acceptance Criteria Affected | Rationale |
|---|---------|------------------------------|-----------|
| B-08 | **Push notification never arrives** on supported browsers | Push notifications (US-09) | Key feature missing. |
| B-09 | **Report shows incorrect completion rate** (off by > 5%) | Reports (US-08) | Undermines parent trust. |
| B-10 | **PWA fails Lighthouse audit** (score < 70%) | PWA (US-10) | PWA is a core spec requirement. |
| B-11 | **Offline completions lost** (not synced on reconnect) | PWA offline (US-10) | Data loss for offline users. |
| B-12 | **Parent cannot add child** (409 or 500 on valid email) | Parent-child link (US-02) | Blocks the core family setup flow. |
| B-13 | **Dashboard shows wrong chores** (wrong child, wrong day, inactive chores shown) | Dashboard (US-07) | Core UX failure. |
| B-14 | **Chore form saves with wrong weekdays** (bitmask encoding error) | Chore management (US-04) | Subtle data corruption. |
| B-15 | **iOS Safari < 16.4: app crashes or shows broken UI** for push-related features | Graceful degradation | Must degrade gracefully, not crash. |

### 6.3 Medium (P2 — Should Fix Before GA)

| # | Blocker | Rationale |
|---|---------|-----------|
| B-16 | **No empty state for any page** — blank screen instead of helpful message | Poor UX, user confusion |
| B-17 | **No loading indicators** — user sees nothing while data loads | Poor perceived performance |
| B-18 | **Keyboard navigation broken** — Tab order illogical, focus trapped | Accessibility requirement |
| B-19 | **No error messages in Russian** — English error messages shown | Spec requirement (Russian-language UI) |
| B-20 | **Docker Compose healthchecks fail** — containers restart loop | Deployment reliability |

---

## 7. Test Data Requirements

### 7.1 Seed Data

The test database must be seeded with:

| Entity | Count | Details |
|--------|-------|---------|
| Families | 3 | Family A (parent + 2 children), Family B (parent + 1 child), Family C (parent only, no children) |
| Users (parents) | 3 | One per family |
| Users (children) | 3 | 2 in Family A, 1 in Family B |
| Chores (daily) | 10 per child | Mix of different weekdays, some active, some inactive |
| Chores (weekly) | 3 per child | All active |
| Completions | ~50 per child | Spanning last 14 days, mixed completion patterns |
| Push subscriptions | 2 | One per parent for testing |
| Notification preferences | 3 | Various times and days |

### 7.2 Test Accounts

| Role | Email (mock) | Family | Notes |
|------|-------------|--------|-------|
| Parent | `parent.a@test.com` | Family A | Has 2 children |
| Parent | `parent.b@test.com` | Family B | Has 1 child |
| Parent | `parent.c@test.com` | Family C | No children |
| Child | `child.a1@test.com` | Family A | Has 10 daily + 3 weekly chores |
| Child | `child.a2@test.com` | Family A | Has 10 daily + 3 weekly chores |
| Child | `child.b1@test.com` | Family B | Has 10 daily + 3 weekly chores |

### 7.3 Test Dates

For reproducible testing, fix "today" to a known date:

```
TEST_TODAY = 2025-04-15 (Tuesday)
```

This allows deterministic testing of weekday-based chore visibility and completion validation.

---

## 8. QA Execution Plan by Sprint

### Sprint 1 QA: Foundation (Auth + Users + Family)

**Focus**: Google OAuth, JWT, user profiles, family/child management

| Test Type | Count | Key Scenarios |
|-----------|-------|---------------|
| Unit (backend) | ~25 | AuthService: OAuth flow, JWT issuance, token validation; UsersService: addChild, getChildren, uniqueness |
| Unit (frontend) | ~15 | AuthStore: login/logout/initialize; AuthInterceptor; RoleGuard |
| Integration | ~10 | Full OAuth redirect flow; POST /users/children; GET /users/me |
| E2E | 3 | E2E-01 (parent registration), E2E-02 (add child), E2E-10 (token refresh) |

**Sprint 1 QA Gate**: 
- [ ] Parent can register and login via Google
- [ ] Parent can add child email
- [ ] Child can login via Google
- [ ] JWT refresh works
- [ ] 401 redirects to login
- [ ] Role-based route protection works

### Sprint 2 QA: Chores + Completions

**Focus**: CRUD chores, dashboard, completion toggle, offline queue

| Test Type | Count | Key Scenarios |
|-----------|-------|---------------|
| Unit (backend) | ~30 | ChoresService: CRUD, authorization matrix, dashboard query; CompletionsService: toggle, date validation, uniqueness |
| Unit (frontend) | ~20 | DashboardStore: load, optimistic toggle, revert; ChoreForm validation; CompletionCheckbox |
| Integration | ~15 | Full chore lifecycle; toggle with date validation; dashboard with mixed daily/weekly; cross-family isolation |
| E2E | 4 | E2E-03 (create chore), E2E-04 (child completes), E2E-05 (undo), E2E-09 (offline dashboard) |

**Sprint 2 QA Gate**:
- [ ] Chore CRUD works for both roles
- [ ] Authorization matrix enforced (child can't assign to others)
- [ ] Dashboard shows correct chores for date/user
- [ ] Completion toggle works with optimistic UI
- [ ] Offline toggle queues and syncs
- [ ] Date/weekday validation enforced (422 for wrong day)
- [ ] No cross-family data leaks

### Sprint 3 QA: Push Notifications + PWA

**Focus**: Push subscription, notification preferences, cron delivery, PWA install/offline

| Test Type | Count | Key Scenarios |
|-----------|-------|---------------|
| Unit (backend) | ~15 | PushService: VAPID, sendNotification; NotificationsScheduler: findDuePreferences |
| Unit (frontend) | ~10 | SwPushService; NotificationSettings; PwaInstallDirective |
| Integration | ~10 | Subscribe → preference CRUD → cron trigger → notification received; 410 unsubscribe handling |
| E2E | 2 | E2E-07 (push setup), E2E-08 (PWA install) |
| PWA Audit | 1 | Lighthouse PWA audit ≥ 90% |

**Sprint 3 QA Gate**:
- [ ] Push subscription flow works end-to-end
- [ ] Notification fires at configured time
- [ ] Notification click navigates to dashboard
- [ ] Expired subscription (410) handled gracefully
- [ ] PWA Lighthouse score ≥ 90%
- [ ] PWA installs on Android Chrome
- [ ] Offline fallback page works
- [ ] Service worker caching delivers fresh data

### Sprint 4 QA: Reports + Final Polish

**Focus**: Report generation, charts, accessibility, full regression

| Test Type | Count | Key Scenarios |
|-----------|-------|---------------|
| Unit (backend) | ~15 | ReportsService: summary aggregation, daily breakdown, edge cases (0%, 100%, empty) |
| Unit (frontend) | ~10 | ReportChart; ReportSummary; PeriodPicker validation |
| Integration | ~10 | Report with various date ranges; report with mixed completion data; performance with 90-day range |
| E2E | 1 | E2E-06 (parent views report) |
| Accessibility | Full | axe-core scan on all pages; keyboard nav; screen reader |
| Regression | All | Full E2E suite (10 scenarios); all unit tests; all integration tests |

**Sprint 4 QA Gate (FINAL RELEASE GATE)**:
- [ ] All 6 release blockers (B-01 through B-06) resolved
- [ ] All 7 P1 blockers (B-08 through B-15) resolved
- [ ] All P0 test scenarios pass
- [ ] All P1 test scenarios pass
- [ ] E2E suite 100% pass
- [ ] Unit test coverage ≥ 80% (backend and frontend)
- [ ] Lighthouse PWA ≥ 90%
- [ ] Lighthouse Accessibility ≥ 90%
- [ ] No data loss scenarios reproducible
- [ ] Cross-family isolation verified
- [ ] Timezone edge cases documented (TZ-01/TZ-02) with accepted behavior
- [ ] Docker Compose `docker compose up` succeeds with all healthchecks green

---

## 9. Test Environment Requirements

### 9.1 Environments

| Environment | Purpose | Configuration |
|-------------|---------|---------------|
| **Local Dev** | Developer testing | `docker compose up` with `.env` overrides |
| **CI** | Automated test suite | GitHub Actions / GitLab CI, ephemeral PostgreSQL |
| **Staging** | Manual QA, E2E | Full Docker Compose, test Google OAuth app, test VAPID keys |
| **Production** | Live users | Full Docker Compose, production Google OAuth, production VAPID keys |

### 9.2 Browser Matrix

| Browser | Version | Platform | Priority |
|---------|---------|----------|----------|
| Chrome | Latest | Android 14 | P0 (primary child platform) |
| Chrome | Latest | Windows/macOS | P0 (parent desktop) |
| Safari | 16.4+ | iOS 16.4+ | P1 (child iOS) |
| Safari | Latest | macOS | P1 (parent Mac) |
| Firefox | Latest | Android | P1 |
| Firefox | Latest | Windows/macOS | P1 |
| Edge | Latest | Windows | P1 |
| Samsung Internet | Latest | Android | P2 |

### 9.3 Device Matrix

| Device | OS | Priority |
|--------|-----|----------|
| Google Pixel (or equivalent Android) | Android 14 | P0 |
| iPhone (Safari 16.4+) | iOS 17 | P1 |
| iPad | iPadOS 17 | P2 |
| Desktop 1920×1080 | Windows/macOS | P0 |
| Desktop 1366×768 (laptop) | Windows/macOS | P1 |

---

## 10. Automation Strategy

### 10.1 What to Automate

| Layer | Tool | When | Coverage Target |
|-------|------|------|-----------------|
| Backend Unit | Jest | Per-commit | ≥ 85% |
| Frontend Unit | Jest + Angular Testing Library | Per-commit | ≥ 80% |
| Backend Integration | Jest + supertest | Per-PR | All endpoints |
| Frontend Integration | Jest + TestBed | Per-PR | All stores + services |
| E2E | Playwright | Nightly + per-release | All 10 E2E scenarios |
| PWA Audit | Lighthouse CI | Per-PR | ≥ 90% PWA score |
| Accessibility | axe-core + pa11y | Per-PR | ≥ 90% a11y score |
| API Contract | OpenAPI validator | Per-PR | 0 schema violations |

### 10.2 What to Test Manually

| Area | Reason |
|------|--------|
| Google OAuth flow (real account) | Cannot fully mock Google in E2E |
| Push notification delivery (real browser) | Requires real browser + push service |
| PWA install on real devices | `beforeinstallprompt` behavior varies |
| Visual regression (multi-device) | Layout on real screen sizes |
| Timezone behavior (real TZ changes) | Simulating TZ in CI is unreliable |
| iOS Safari specific behaviors | WebKit differences, requires real device |

---

## 11. Risk-Based Test Prioritization

### Priority Definitions

| Priority | Definition | Must Pass Before |
|----------|------------|------------------|
| **P0** | Core functionality, security, data integrity. Failure = cannot release. | Every sprint, final release |
| **P1** | Important features, common edge cases. Failure = degraded experience. | Final release |
| **P2** | Nice-to-have, rare edge cases. Failure = minor inconvenience. | Post-release acceptable |

### P0 Test Count by Area

| Area | P0 Count |
|------|----------|
| Authentication (US-01) | 5 |
| Parent-Child Link (US-02, US-03) | 5 |
| Chore CRUD (US-04, US-05) | 6 |
| Completion Toggle (US-06) | 6 |
| Dashboard (US-07) | 2 |
| Reports (US-08) | 3 |
| Push Notifications (US-09) | 4 |
| PWA (US-10) | 3 |
| Cross-cutting (Isolation, JWT, TZ, Offline) | 16 |
| **Total P0** | **50** |

---

## 12. Defect Severity Classification

| Severity | Definition | Example |
|----------|------------|---------|
| **S1 — Critical** | Data loss, security breach, all users blocked | Cross-family data leak, login broken for all users, data not persisted |
| **S2 — Major** | Key feature broken, no workaround | Reports show wrong data, push notifications never arrive, offline sync fails |
| **S3 — Minor** | Feature works but has bug, workaround exists | Wrong color on progress bar, notification delayed by 2 minutes, empty state missing |
| **S4 — Trivial** | Cosmetic, no functional impact | Typo in Russian text, icon slightly misaligned, non-blocking console warning |

---

## 13. QA Sign-off Criteria

Before any release to production, the following must be true:

1. **All P0 test scenarios pass** (50 scenarios)
2. **All P1 test scenarios pass** (remaining scenarios)
3. **All Release Blockers resolved** — B-01 through B-15
4. **E2E suite 100% pass** — all 10 scenarios
5. **Unit test coverage** ≥ 80% backend, ≥ 80% frontend
6. **Integration test coverage** — all API endpoints have at least one happy path + one negative test
7. **Lighthouse PWA score** ≥ 90%
8. **Lighthouse Accessibility score** ≥ 90%
9. **Cross-browser smoke test** — Chrome Android, Chrome Desktop, Safari iOS, Firefox Desktop
10. **Offline smoke test** — airplane mode: dashboard loads, toggle queued, online sync works
11. **Docker Compose deployment** — `docker compose up` succeeds, all healthchecks green
12. **No S1 or S2 defects open**
13. **Timezone edge cases (TZ-01, TZ-02) documented and accepted** by product owner
14. **Security review** — family isolation verified, JWT rotation verified, no secrets in frontend code

---

## 14. Appendix A: E2E Test Script Outlines

### E2E-01: Parent Registration

```
1. Navigate to /login
2. Assert: "Войти через Google" button visible
3. Click button → redirected to mock Google OAuth
4. Mock returns authorization code
5. Backend exchanges code, returns JWT pair
6. Frontend stores tokens, navigates to /dashboard
7. Assert: Dashboard loaded, parent name visible, kid selector visible
8. Assert: Sidebar/bottom-nav shows all parent items (Дети, Отчёты)
```

### E2E-02: Add Child

```
1. Login as parent (E2E-01 steps 1-7)
2. Navigate to /kids
3. Assert: Empty state or existing children list
4. Click "Добавить"
5. Enter child email "child.test@example.com"
6. Submit
7. Assert: Child appears in list with correct email
8. Assert: Success snackbar shown
```

### E2E-03: Create Chore

```
1. Login as parent
2. Navigate to /chores
3. Click "Новая задача"
4. Fill: title="Заправить кровать", description="Убрать подушки", schedule_type="daily_weekday"
5. Select Mon, Tue, Wed, Thu, Fri in weekday picker
6. Select child from assigned_to dropdown
7. Click "Сохранить"
8. Assert: Chore appears in chores list
9. Assert: Chore card shows correct title, weekdays, child name
```

### E2E-04: Child Completes Chore

```
1. Login as child
2. Navigate to /dashboard
3. Assert: Today's chores visible, including "Заправить кровать" (if today is weekday)
4. Click unchecked checkbox on a chore
5. Assert: Checkmark appears immediately (optimistic)
6. Assert: Progress bar updates (count and percentage)
7. Wait for API response
8. Assert: Checkmark remains, no error snackbar
```

### E2E-05: Undo Completion

```
1. Continue from E2E-04 (chore is checked)
2. Click same checkbox again
3. Assert: Checkmark disappears
4. Assert: Progress bar decreases
```

### E2E-06: Parent Views Report

```
1. Login as parent
2. Navigate to /reports
3. Select child from dropdown
4. Set period: start=7 days ago, end=today
5. Click "Применить"
6. Assert: Summary cards show numbers (total, completed, missed, rate)
7. Assert: Chart renders with bars for each day
8. Assert: Completed list shows chores that were toggled in E2E-04
9. Assert: Missed list shows untoggled chores
```

### E2E-07: Push Notification Setup

```
1. Login as any user on Chrome (supports Web Push)
2. Navigate to /settings/notifications
3. Assert: Subscribe button visible
4. Click subscribe
5. Browser shows permission prompt → grant
6. Assert: Subscription status shows "Подписан ✅"
7. Add notification preference: select chore, time, days
8. Save
9. Assert: Preference appears in list
```

### E2E-08: PWA Install

```
1. Open app on Android Chrome
2. Wait for beforeinstallprompt event
3. Assert: Install button/prompt visible
4. Click install
5. Assert: App opens in standalone mode
6. Assert: Manifest icon appears on home screen
```

### E2E-09: Offline Dashboard

```
1. Login, load dashboard (ensure data cached)
2. Enable offline mode (Playwright context.setOffline(true))
3. Assert: Dashboard still shows cached chores
4. Assert: Offline banner visible
5. Click checkbox on a chore
6. Assert: Optimistic update applied
7. Disable offline mode (context.setOffline(false))
8. Assert: Offline banner disappears
9. Wait for sync
10. Assert: Completion persisted (refresh dashboard, checkbox still checked)
```

### E2E-10: Token Refresh

```
1. Login with short-lived access token (mock: 10 seconds)
2. Wait 11 seconds
3. Perform action (e.g., toggle completion)
4. Assert: Request returns 401
5. Assert: Interceptor triggers refresh
6. Assert: Refresh succeeds
7. Assert: Original request retried with new token
8. Assert: Action succeeds, no redirect to login
```

---

## 15. Appendix B: API Contract Test Cases

### Response Shape Validation

For every endpoint, validate that the response matches the expected DTO:

```typescript
// Example contract test
describe('GET /api/chores/:id', () => {
  it('should return ChoreResponseDto shape', async () => {
    const response = await request.get('/api/chores/' + choreId)
      .set('Authorization', `Bearer ${token}`)
      .expect(200);

    expect(response.body).toMatchObject({
      id: expect.any(String),
      title: expect.any(String),
      description: expect.any(String), // nullable
      schedule_type: expect.stringMatching(/^(daily_weekday|weekly)$/),
      weekdays: expect.any(Number),
      is_active: expect.any(Boolean),
      created_by: expect.any(String),
      assigned_to: expect.any(String),
      created_at: expect.any(String),
      updated_at: expect.any(String),
    });
  });
});
```

### Error Response Shape Validation

```typescript
describe('Error responses', () => {
  it('should return ApiErrorResponse shape on 404', async () => {
    const response = await request.get('/api/chores/nonexistent-id')
      .set('Authorization', `Bearer ${token}`)
      .expect(404);

    expect(response.body).toMatchObject({
      statusCode: 404,
      error: 'Not Found',
      message: expect.any(String),
      timestamp: expect.any(String),
      path: expect.any(String),
    });
  });
});
```

### Swagger Spec Validation

```
1. GET /api/docs-json returns valid OpenAPI 3.0 spec
2. Every endpoint has @ApiOperation summary
3. Every DTO property has @ApiProperty
4. Every endpoint has @ApiResponse for success and error cases
5. Frontend-generated API client matches spec
```

---

## 16. Final Assessment

**Overall Quality Assessment**: The specification and implementation plans are comprehensive and well-structured. The architecture decisions (bitmask weekdays, UUID PKs, UTC-only backend, optimistic UI with offline queue) are sound with clear rationales. 

**Key Concerns Requiring Attention**:

1. **Timezone near midnight** (TZ-01, TZ-02): The frontend plan acknowledges this as "acceptable" but it can cause confusion for users in timezones far from UTC (e.g., UTC+10 where early morning is still the previous UTC day). This should be explicitly documented and accepted by stakeholders.

2. **iOS Safari Push limitation**: A significant portion of the target audience (children with iPhones on iOS < 16.4) won't receive push notifications. The graceful degradation strategy is in place, but alternative engagement mechanisms may be needed.

3. **Offline sync conflict resolution**: The "server wins, remove queue item" strategy for 409 conflicts is simple but could lose a child's completion if a parent simultaneously un-completes the same chore. This edge case should be explicitly tested and documented.

4. **No email sending mentioned**: The specification says "система отправляет приглашение на почту" but the backend plan creates "pending" user records without an email service. This needs clarification — is email invitation required for MVP?

**Release Recommendation**: **Conditional Go** — proceed with Sprint 1-4 implementation. All P0 release blockers (B-01 through B-07) MUST be resolved. P1 blockers (B-08 through B-15) should be resolved before GA. The timezone edge cases (TZ-01, TZ-02) should be explicitly reviewed and accepted by the product owner before release.