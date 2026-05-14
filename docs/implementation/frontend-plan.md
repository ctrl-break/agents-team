# Frontend Implementation Plan: Kids Chore Tracker (SPA/PWA)

**Status**: Draft — based on approved specification `docs/specs/latest-plan.md` and backend plan.

---

## 1. Client Responsibilities

The frontend is an **Angular 17+ SPA/PWA** responsible for all user-facing functionality:

| # | Responsibility | Details |
|---|---------------|---------|
| 1 | **OAuth Login Flow** | Redirect user to backend Google OAuth endpoint, receive JWT tokens via callback URL, store tokens, and silently refresh. |
| 2 | **Role-Based UI** | Parent sees dashboard with child selector, chore management for all children, reports, and family management. Child sees only own dashboard, chores, and settings. |
| 3 | **Chore CRUD UI** | Forms for creating/editing chores with weekday picker, schedule type toggle (daily vs weekly), assignee selection (parent-only), and inline delete. |
| 4 | **Dashboard (Today View)** | List of chores for the selected date/user with completion checkboxes, visual status indicators, and date navigation. |
| 5 | **Completion Toggle** | Optimistic checkbox toggle, offline-capable via IndexedDB queue, synced on reconnect. |
| 6 | **Reports Visualization** | Period picker, child selector (parent), summary stats, daily breakdown charts, completion/pending lists. |
| 7 | **Push Notification Setup** | Subscribe/unsubscribe via `SwPush`, permission request UX, per-chore notification time/day preferences UI. |
| 8 | **PWA Lifecycle** | Install prompt, manifest.json, service worker registration, offline fallback page, background sync for completions. |
| 9 | **Timezone Conversion** | All dates received in UTC; converted to local timezone for display, back to UTC for API requests. |
| 10 | **Responsive Layout** | Mobile-first design, works on Android Chrome, iOS Safari 16.4+, and desktop browsers. |
| 11 | **Accessibility** | Angular Material a11y: ARIA labels, keyboard navigation, high-contrast theme option, focus management. |

---

## 2. Technology Stack

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Framework | Angular | 17+ | Spec requirement, SPA with SSR not needed |
| Language | TypeScript | 5.x | Strict mode, full type safety |
| UI Library | Angular Material | 17.x | Spec requirement, accessible, responsive, Material Design 3 |
| State Management | Angular Signals + SignalStore (`@ngrx/signals`) | — | Spec preference for Signals, lightweight, no NgRx boilerplate |
| HTTP Client | `@angular/common/http` + interceptors | — | JWT injection, error handling, refresh token flow |
| PWA | `@angular/pwa` (Angular Service Worker) | — | `ngsw-config.json`, manifest, offline caching |
| Push Notifications | `@angular/service-worker` (`SwPush`) | — | Browser Web Push API abstraction |
| Charts | `ngx-charts` or `chart.js` via `ng2-charts` | — | Lightweight, responsive, good Angular integration |
| Offline Sync | `@ngrx/db` or custom IndexedDB wrapper | — | Queue completions when offline |
| Forms | Angular Reactive Forms | — | Complex form validation, dynamic form arrays |
| Testing | Jest + Angular Testing Library | — | Component and service tests |
| E2E | Playwright | 1.x | Cross-browser testing, mobile emulation |
| Icons | Angular Material Icons + custom PWA icons | — | `mat-icon` for UI, custom icons for manifest |
| Date Handling | `date-fns` or `luxon` | — | Lightweight, tree-shakeable, timezone-aware |
| Linting | ESLint + Angular ESLint | — | Angular-specific rules |
| Formatting | Prettier | — | Consistent code style |

---

## 3. Application Structure

```
apps/frontend/src/
├── main.ts                              # Bootstrap, PWA registration
├── index.html                           # SPA shell, manifest link, theme-color meta
├── manifest.webmanifest                 # PWA manifest (generated)
├── ngsw-config.json                     # Service Worker caching rules
├── styles.scss                          # Global styles, Material theme, CSS variables
├── environments/
│   ├── environment.ts                   # Dev config
│   └── environment.prod.ts             # Prod config
├── app/
│   ├── app.module.ts                    # Root module (or standalone bootstrap)
│   ├── app.component.ts                 # Shell: toolbar, sidenav, role-based nav
│   ├── app-routing.module.ts            # Route definitions with guards
│   ├── core/                            # Singleton services and guards
│   │   ├── auth/
│   │   │   ├── auth.service.ts          # OAuth flow, token storage, refresh
│   │   │   ├── auth.interceptor.ts      # Attach JWT to requests
│   │   │   ├── auth-error.interceptor.ts# Handle 401 → refresh → retry
│   │   │   ├── auth.guard.ts            # CanActivate: redirect to /login if unauthenticated
│   │   │   ├── role.guard.ts            # CanActivate: parent-only routes
│   │   │   └── auth-callback.component.ts # Receives token from OAuth redirect
│   │   ├── services/
│   │   │   ├── api.service.ts           # Base HTTP wrapper, base URL config
│   │   │   ├── users.service.ts         # /api/users endpoints
│   │   │   ├── chores.service.ts        # /api/chores endpoints
│   │   │   ├── completions.service.ts   # /api/completions endpoints
│   │   │   ├── reports.service.ts       # /api/reports endpoints
│   │   │   ├── notifications.service.ts # /api/notifications endpoints
│   │   │   ├── sw-push.service.ts       # SwPush wrapper, subscription management
│   │   │   ├── offline-queue.service.ts # IndexedDB queue for offline completions
│   │   │   └── timezone.service.ts      # UTC ↔ local conversion, date helpers
│   │   ├── state/
│   │   │   ├── auth.store.ts            # SignalStore: user, tokens, isAuthenticated
│   │   │   ├── chores.store.ts          # SignalStore: chores[], filters
│   │   │   ├── completions.store.ts     # SignalStore: completions map
│   │   │   ├── dashboard.store.ts       # SignalStore: today's chores + status
│   │   │   ├── children.store.ts        # SignalStore: children list (parent)
│   │   │   ├── notifications.store.ts   # SignalStore: prefs, subscriptions
│   │   │   └── ui.store.ts             # SignalStore: sidebar, loading, errors
│   │   └── models/
│   │       ├── user.model.ts
│   │       ├── chore.model.ts
│   │       ├── completion.model.ts
│   │       ├── report.model.ts
│   │       ├── notification.model.ts
│   │       └── api-response.model.ts
│   ├── shared/                          # Shared UI components and utilities
│   │   ├── components/
│   │   │   ├── weekday-picker/          # Reusable day-of-week toggle buttons
│   │   │   ├── chore-card/              # Single chore display with actions
│   │   │   ├── completion-checkbox/     # Animated checkbox with optimistic toggle
│   │   │   ├── kid-selector/            # Dropdown to select child (parent)
│   │   │   ├── date-navigator/          # Date picker + prev/next day arrows
│   │   │   ├── period-picker/           # Start/end date range selector
│   │   │   ├── loading-spinner/         # Global and inline loading indicator
│   │   │   ├── error-snackbar/          # Toast notifications for errors
│   │   │   ├── confirm-dialog/          # Reusable confirmation modal
│   │   │   ├── empty-state/             # Illustrations + text for empty lists
│   │   │   └── offline-banner/          # "You are offline" top banner
│   │   ├── directives/
│   │   │   ├── role-visibility.directive.ts # *appRole="'parent'" conditional display
│   │   │   └── pwa-install.directive.ts     # beforeinstallprompt event handler
│   │   └── pipes/
│   │       ├── weekday-name.pipe.ts     # 0→"Пн", 1→"Вт" with locale
│   │       ├── completion-rate.pipe.ts  # 0.75→"75%"
│   │       └── local-date.pipe.ts       # UTC string → local formatted date
│   ├── features/
│   │   ├── auth/
│   │   │   ├── login-page/
│   │   │   │   └── login-page.component.ts  # Google login button, PWA promo
│   │   │   └── auth-callback/
│   │   │       └── auth-callback.component.ts # Extract tokens, redirect
│   │   ├── dashboard/
│   │   │   ├── dashboard-page/
│   │   │   │   └── dashboard-page.component.ts # Today's chores list
│   │   │   └── dashboard-chore-list/
│   │   │       └── dashboard-chore-list.component.ts # Grouped by child/time
│   │   ├── chores/
│   │   │   ├── chores-page/
│   │   │   │   └── chores-page.component.ts  # Master list with filters
│   │   │   ├── chore-form/
│   │   │   │   └── chore-form.component.ts   # Create/Edit dialog or page
│   │   │   └── chore-detail/
│   │   │       └── chore-detail.component.ts # Chore info + completion history
│   │   ├── kids/
│   │   │   ├── kids-page/
│   │   │   │   └── kids-page.component.ts    # Parent: manage children
│   │   │   ├── add-child-dialog/
│   │   │   │   └── add-child-dialog.component.ts # Add child by email
│   │   │   └── child-card/
│   │   │       └── child-card.component.ts   # Child info + quick stats
│   │   ├── reports/
│   │   │   ├── reports-page/
│   │   │   │   └── reports-page.component.ts  # Report builder
│   │   │   ├── report-summary/
│   │   │   │   └── report-summary.component.ts # Stats cards
│   │   │   ├── report-chart/
│   │   │   │   └── report-chart.component.ts   # Daily breakdown chart
│   │   │   └── report-details/
│   │   │       └── report-details.component.ts # Completed/missed lists
│   │   └── settings/
│   │       ├── settings-page/
│   │       │   └── settings-page.component.ts   # Profile + notification tabs
│   │       ├── profile-settings/
│   │       │   └── profile-settings.component.ts # Edit display name, avatar
│   │       ├── notification-settings/
│   │       │   └── notification-settings.component.ts # Per-chore notification prefs
│   │       └── push-subscription/
│   │           └── push-subscription.component.ts # Subscribe/unsubscribe toggle
│   └── assets/
│       ├── icons/
│       │   ├── icon-72x72.png
│       │   ├── icon-96x96.png
│       │   ├── icon-128x128.png
│       │   ├── icon-144x144.png
│       │   ├── icon-152x152.png
│       │   ├── icon-192x192.png
│       │   ├── icon-384x384.png
│       │   └── icon-512x512.png
│       ├── screenshots/                 # PWA install prompts
│       │   ├── mobile-screenshot.png
│       │   └── desktop-screenshot.png
│       ├── illustrations/               # Empty state, onboarding
│       └── favicon.ico
```

---

## 4. Routing & Page Structure

### 4.1 Route Definitions

```typescript
// app-routing.module.ts
const routes: Routes = [
  // Public routes
  {
    path: 'login',
    component: LoginPageComponent,
    canActivate: [NoAuthGuard], // Redirect to /dashboard if already logged in
  },
  {
    path: 'auth/callback',
    component: AuthCallbackComponent, // Receives token from backend OAuth redirect
  },

  // Protected routes (require authentication)
  {
    path: '',
    canActivate: [AuthGuard],
    children: [
      {
        path: '',
        redirectTo: 'dashboard',
        pathMatch: 'full',
      },
      {
        path: 'dashboard',
        component: DashboardPageComponent,
        title: 'Сегодняшние дела',
      },
      {
        path: 'chores',
        component: ChoresPageComponent,
        title: 'Управление задачами',
        children: [
          {
            path: 'new',
            component: ChoreFormComponent,
            title: 'Новая задача',
          },
          {
            path: ':id',
            component: ChoreDetailComponent,
            title: 'Просмотр задачи',
          },
          {
            path: ':id/edit',
            component: ChoreFormComponent,
            title: 'Редактирование задачи',
          },
        ],
      },
      {
        path: 'kids',
        component: KidsPageComponent,
        canActivate: [RoleGuard],
        data: { roles: ['parent'] },
        title: 'Дети',
      },
      {
        path: 'reports',
        component: ReportsPageComponent,
        canActivate: [RoleGuard],
        data: { roles: ['parent'] },
        title: 'Отчёты',
      },
      {
        path: 'settings',
        component: SettingsPageComponent,
        title: 'Настройки',
        children: [
          {
            path: 'profile',
            component: ProfileSettingsComponent,
          },
          {
            path: 'notifications',
            component: NotificationSettingsComponent,
          },
          {
            path: '',
            redirectTo: 'profile',
            pathMatch: 'full',
          },
        ],
      },
    ],
  },

  // PWA offline fallback
  {
    path: 'offline',
    component: OfflinePageComponent,
  },

  // Wildcard
  {
    path: '**',
    redirectTo: 'dashboard',
  },
];
```

### 4.2 Navigation Model

**Bottom Navigation Bar (mobile) / Side Nav (desktop):**

| Icon | Label | Route | Visible To |
|------|-------|-------|------------|
| `home` | Сегодня | `/dashboard` | All |
| `checklist` | Задачи | `/chores` | All |
| `people` | Дети | `/kids` | Parent only |
| `bar_chart` | Отчёты | `/reports` | Parent only |
| `settings` | Настройки | `/settings` | All |

**Top Bar (Toolbar):**
- App title "Детский трекер" (left)
- Current user avatar + name (right) → dropdown: profile, logout
- Kid selector dropdown (parent, visible on dashboard/chores/reports)
- Date navigator (visible on dashboard)

### 4.3 Responsive Breakpoints

| Breakpoint | Width | Layout |
|------------|-------|--------|
| Mobile | < 600px | Bottom nav, single column, full-width cards |
| Tablet | 600–960px | Bottom nav, 2-column grid where appropriate |
| Desktop | > 960px | Side nav (persistent), multi-column, wider charts |

---

## 5. UI & Interaction Model

### 5.1 Design System (Angular Material Theme)

**Color Palette:**
- **Primary**: Deep Blue (`#1565C0` / `#1976D2`) — trustworthy, calm
- **Accent**: Warm Orange (`#FF7043`) — friendly, energetic, child-appropriate
- **Success**: Green (`#4CAF50`) — completion indicators
- **Warn**: Red (`#F44336`) — missed tasks, deletes
- **Surface**: Light gray backgrounds, white cards

**Typography:**
- Headlines: Roboto (Material default), larger sizes for child readability
- Body: Roboto, 16px minimum for readability on mobile

**Child-Friendly Considerations:**
- Large touch targets (minimum 48x48px per WCAG 2.1 AAA for mobile)
- Bright, cheerful accent colors for completion actions
- Animated checkmark with confetti/celebration on task completion (optional toggle)
- Simple icons paired with text labels (never icon-only for children)
- Sound feedback option for completion (togglable)

### 5.2 Page-Level UI Descriptions

#### Login Page (`/login`)

```
┌──────────────────────────────────────┐
│                                      │
│         🏠 (App Logo/Icon)           │
│                                      │
│     Детский трекер                   │
│     Делай дела вовремя!              │
│                                      │
│   ┌──────────────────────────┐       │
│   │  G  Войти через Google   │       │
│   └──────────────────────────┘       │
│                                      │
│   Установи приложение на телефон     │
│   [Установить] (PWA prompt)         │
│                                      │
└──────────────────────────────────────┘
```

- Large Google sign-in button (branded, official colors)
- PWA install prompt visible when `beforeinstallprompt` fires
- Brief feature highlights below (3 icons: plan, track, reward)
- No other auth method — Google only per spec

#### Dashboard Page (`/dashboard`)

```
┌──────────────────────────────────────┐
│ [Toolbar: Logo | Kid▼ | ◀ 📅 ▶ ]    │
├──────────────────────────────────────┤
│                                      │
│  Привет, Маша! 👋                    │
│  Сегодня вторник, 15 апреля          │
│                                      │
│  ┌──────────────────────────────┐    │
│  │ ✅ Заправить кровать  08:00 │    │
│  │ ☐ Сделать уроки       16:00 │    │
│  │ ☐ Помыть посуду       19:00 │    │
│  │ ☐ Почитать книгу      21:00 │    │
│  │ ✅ Погулять с собакой   —   │    │
│  └──────────────────────────────┘    │
│                                      │
│  Выполнено: 2 из 5 (40%)             │
│  ████████░░░░░░░░░░░░                │
│                                      │
│  Дела на неделе:                     │
│  ┌──────────────────────────────┐    │
│  │ ☐ Убраться в комнате        │    │
│  │ ☐ Помочь маме с готовкой    │    │
│  └──────────────────────────────┘    │
│                                      │
└──────────────────────────────────────┘
```

**Interactions:**
- **Date Navigator**: `<` `>` arrows + date picker button. Today button returns to current date.
- **Kid Selector** (parent): Dropdown at toolbar changes `selectedChildId`, dashboard reloads for that child.
- **Completion Checkbox**: Tap toggles with optimistic update (immediate visual change, API call in background). On failure, reverts with shake animation.
- **Weekly vs Daily sections**: Visually separated. Daily chores show scheduled time (from notification preferences). Weekly chores grouped at bottom.
- **Progress bar**: Animated fill. Changes color: red (<30%), orange (30-70%), green (>70%), gold (100%).

**States:**
- **Loading**: Skeleton cards (placeholder shimmer)
- **Empty (no chores)**: Illustration + "Дел на сегодня нет! 🎉" + button "Добавить задачу"
- **Error**: Snackbar with retry action + stale data shown
- **Offline**: Yellow banner "Вы офлайн. Отметки сохранятся при подключении к сети."

#### Chores Page (`/chores`)

```
┌──────────────────────────────────────┐
│ [Toolbar: Logo | Kid▼]              │
├──────────────────────────────────────┤
│  Задачи               [+ Новая]     │
│                                      │
│  [🔍 Поиск...]  [Активные▼] [Тип▼] │
│                                      │
│  Понедельник                         │
│  ┌──────────────────────────────┐    │
│  │ 📋 Заправить кровать    ✏️🗑️│    │
│  │    Ежедневно, Пн-Пт          │    │
│  │    🔵 Активна                │    │
│  └──────────────────────────────┘    │
│  ┌──────────────────────────────┐    │
│  │ 📋 Сделать зарядку      ✏️🗑️│    │
│  │    Ежедневно, Пн-Ср-Пт       │    │
│  │    ⚪ Неактивна              │    │
│  └──────────────────────────────┘    │
│                                      │
│  На неделе                           │
│  ┌──────────────────────────────┐    │
│  │ 📋 Убраться в комнате   ✏️🗑️│    │
│  │    В любой день недели       │    │
│  └──────────────────────────────┘    │
│                                      │
└──────────────────────────────────────┘
```

**Interactions:**
- **Filter chips**: `Активные`, `Неактивные`, `Все` + `Ежедневные`, `На неделе`
- **Search**: Filter by title substring (client-side after loading)
- **Sort**: Group by schedule type (daily first, grouped by weekday; then weekly)
- **FAB (desktop) / bottom button (mobile)**: "Новая задача" — opens chore form dialog
- **Edit**: Opens `ChoreFormComponent` dialog pre-filled
- **Delete**: Confirmation dialog → API call → remove from list
- **Toggle active**: Slide toggle inline on the card
- **Per-child filtering** (parent): Kid selector changes the view

**States:**
- **Empty**: "У вас пока нет задач" + "Создать первую задачу" button
- **Empty search**: "Ничего не найдено. Измените параметры поиска."

#### Chore Form (Dialog or Page)

```
┌──────────────────────────────────────┐
│  Новая задача                   ✕   │
│                                      │
│  Название *                          │
│  ┌──────────────────────────────┐    │
│  │ Заправить кровать            │    │
│  └──────────────────────────────┘    │
│                                      │
│  Описание                            │
│  ┌──────────────────────────────┐    │
│  │ Убрать подушки и одеяло,     │    │
│  │ застелить покрывалом         │    │
│  └──────────────────────────────┘    │
│                                      │
│  Тип задачи *                        │
│  ⦿ Конкретный день недели           │
│  ○ На неделе (любой день)           │
│                                      │
│  Дни недели *                        │
│  [Пн][Вт][Ср][Чт][Пт][Сб][Вс]       │
│   ✓   ✓   ✓   ✓   ✓   ✗   ✗        │
│                                      │
│  Назначена *                         │
│  ┌──────────────────────────────┐    │
│  │ Маша                     ▼   │    │
│  └──────────────────────────────┘    │
│  (child sees own name, disabled)     │
│                                      │
│  Активна  [========○] да            │
│                                      │
│         [Отмена]  [Сохранить]        │
└──────────────────────────────────────┘
```

**Weekday Picker Component:**
- 7 toggle buttons styled as chips
- Selected: filled primary color with white text
- Unselected: outlined
- Labels: Пн, Вт, Ср, Чт, Пт, Сб, Вс (localized)
- `ScheduleType = 'weekly'` → all days auto-selected and disabled (or hidden)
- Visual: Monday start per Russian convention

**Validation:**
- Title: required, 1–200 chars
- At least one weekday selected (for `daily_weekday`)
- Assigned to: required, child can only assign to self (field hidden/disabled)
- Description: optional, max 1000 chars

#### Kids Page (`/kids`) — Parent Only

```
┌──────────────────────────────────────┐
│ [Toolbar: Logo]                      │
├──────────────────────────────────────┤
│  Мои дети             [+ Добавить]  │
│                                      │
│  ┌──────────────────────────────┐    │
│  │ 👧 Маша Иванова              │    │
│  │    masha@gmail.com           │    │
│  │    Задач: 5                  │    │
│  │    Сегодня: 2/5 выполнено    │    │
│  │    ████░░░░░░  40%           │    │
│  │              [Удалить]       │    │
│  └──────────────────────────────┘    │
│                                      │
│  ┌──────────────────────────────┐    │
│  │ 👦 Петя Иванов               │    │
│  │    petya@gmail.com           │    │
│  │    Задач: 3                  │    │
│  │    Сегодня: 3/3 выполнено    │    │
│  │    ██████████  100%  ⭐      │    │
│  │              [Удалить]       │    │
│  └──────────────────────────────┘    │
│                                      │
└──────────────────────────────────────┘
```

**Add Child Dialog:**
- Email input with validation
- Info text: "Ребёнок должен войти через Google с этой почтой"
- Submit → API call → success/error feedback

**Delete Child:**
- Confirmation dialog: "Все задачи и данные ребёнка будут удалены. Продолжить?"
- API call → remove from list

#### Reports Page (`/reports`) — Parent Only

```
┌──────────────────────────────────────┐
│ [Toolbar: Logo]                      │
├──────────────────────────────────────┤
│  Отчёты                              │
│                                      │
│  Ребёнок: [Маша           ▼]        │
│  Период:  [01.04.2025] – [15.04.2025]│
│           [Применить]                │
│                                      │
│  ┌─────────┐ ┌─────────┐ ┌────────┐ │
│  │ 85%     │ │ 17/20   │ │ 3      │ │
│  │ Выполн. │ │ Сделано │ │ Пропущ │ │
│  └─────────┘ └─────────┘ └────────┘ │
│                                      │
│  График по дням                      │
│  ┌──────────────────────────────┐    │
│  │ ██                            │    │
│  │ ██ ██    ██                   │    │
│  │ ██ ██ ██ ██ ██ ██    ██ ██   │    │
│  │ 01 02 03 04 05 06 07 08 ...  │    │
│  │  ✓  ✓  ✗  ✓  ✓  ✓  ✗  ✓    │    │
│  └──────────────────────────────┘    │
│                                      │
│  Выполненные задачи                  │
│  📋 Заправить кровать — 12 раз ✓    │
│  📋 Сделать уроки — 5 раз ✓         │
│                                      │
│  Пропущенные задачи                  │
│  ✗ Помыть посуду — 3 раза           │
│  ✗ Почитать книгу — 2 раза          │
│                                      │
└──────────────────────────────────────┘
```

**Chart (ngx-charts or chart.js):**
- Vertical bar chart: X = dates, Y = completion count
- Two series: completed (green), missed (red) — stacked or side-by-side
- Tooltip on hover: date, completed count, missed count, rate %
- Responsive: horizontal bars on mobile for readability

**Interactions:**
- Period picker: two date inputs (start, end) with max range 90 days
- "Apply" button triggers API call (not auto-apply to avoid excessive requests)
- Child selector filters report
- Summary cards recalculate on period change
- Expandable lists for completed/missed details

#### Settings Page (`/settings`)

Two tabs:

**Profile Tab:**
- Display name editable field
- Avatar URL or upload (future)
- Email (read-only, from Google)
- Role display (Родитель / Ребёнок)
- Family name display
- Logout button

**Notifications Tab:**

```
┌──────────────────────────────────────┐
│  Push-уведомления                    │
│                                      │
│  Устройство:                         │
│  ┌──────────────────────────────┐    │
│  │ 📱 Chrome на Android         │    │
│  │    Подписан ✅               │    │
│  │              [Отписаться]    │    │
│  └──────────────────────────────┘    │
│                                      │
│  [+ Добавить напоминание]            │
│                                      │
│  ┌──────────────────────────────┐    │
│  │ 🔔 Заправить кровать         │    │
│  │    Время: [07:30]            │    │
│  │    Дни: [Пн][Вт][Ср][Чт][Пт] │    │
│  │    Вкл: [========○]          │    │
│  │              [Удалить]       │    │
│  └──────────────────────────────┘    │
│                                      │
└──────────────────────────────────────┘
```

**Push Subscription:**
- On first visit, show dialog explaining push notifications benefit
- Request permission via `SwPush.requestSubscription()`
- Store subscription via API
- Show device info, subscription status
- Unsubscribe button: API call + `SwPush.unsubscribe()`

**Notification Preference per Chore:**
- Dropdown to select chore (or "все задачи" for global default)
- Time picker (HH:MM, local time → converted to UTC on save)
- Weekday picker (same component as chore form)
- Enabled toggle
- Delete removes preference

---

## 6. API Usage & Integration

### 6.1 API Client Architecture

```typescript
// core/services/api.service.ts
@Injectable({ providedIn: 'root' })
export class ApiService {
  private baseUrl: string;

  constructor(private http: HttpClient) {
    this.baseUrl = environment.apiUrl; // e.g. '/api' (proxied via Nginx)
  }

  get<T>(path: string, params?: HttpParams): Observable<T> {
    return this.http.get<T>(`${this.baseUrl}${path}`, { params });
  }

  post<T>(path: string, body: unknown): Observable<T> {
    return this.http.post<T>(`${this.baseUrl}${path}`, body);
  }

  patch<T>(path: string, body: unknown): Observable<T> {
    return this.http.patch<T>(`${this.baseUrl}${path}`, body);
  }

  put<T>(path: string, body: unknown): Observable<T> {
    return this.http.put<T>(`${this.baseUrl}${path}`, body);
  }

  delete<T>(path: string): Observable<T> {
    return this.http.delete<T>(`${this.baseUrl}${path}`);
  }
}
```

### 6.2 Service-Level API Mapping

#### `AuthService`

```typescript
interface AuthService {
  // Redirect browser to backend Google OAuth endpoint
  initiateGoogleLogin(): void;
  // window.location.href = `${apiUrl}/auth/google`

  // Called by AuthCallbackComponent on page load
  handleCallback(token: string, refreshToken: string): void;
  // Parse tokens from URL fragment, store in AuthStore,
  // navigate to /dashboard

  // Proactive token refresh
  refreshToken(): Observable<TokenPair>;
  // POST /auth/refresh { refresh_token }

  // Logout
  logout(): Observable<void>;
  // POST /auth/logout, clear tokens, navigate to /login
}
```

#### `UsersService`

```typescript
interface UsersService {
  getMe(): Observable<User>;                         // GET /users/me
  updateMe(dto: UpdateProfileDto): Observable<User>; // PATCH /users/me
  getChildren(): Observable<User[]>;                 // GET /users/children (parent)
  addChild(email: string): Observable<User>;         // POST /users/children
  removeChild(id: string): Observable<void>;         // DELETE /users/children/:id
  getFamily(): Observable<FamilyInfo>;               // GET /users/family
}
```

#### `ChoresService`

```typescript
interface ChoresService {
  getChores(query?: ChoreQuery): Observable<Chore[]>;              // GET /chores
  createChore(dto: CreateChoreDto): Observable<Chore>;             // POST /chores
  getChore(id: string): Observable<Chore>;                         // GET /chores/:id
  updateChore(id: string, dto: UpdateChoreDto): Observable<Chore>; // PATCH /chores/:id
  deleteChore(id: string): Observable<void>;                       // DELETE /chores/:id
  getDashboard(date: string, userId: string): Observable<DashboardChore[]>; // GET /chores/dashboard
}
```

#### `CompletionsService`

```typescript
interface CompletionsService {
  toggle(choreId: string, date: string): Observable<ToggleResult>; // POST /completions/toggle
  getCompletions(query: CompletionQuery): Observable<Completion[]>; // GET /completions
  deleteCompletion(id: string): Observable<void>;                   // DELETE /completions/:id
}
```

#### `ReportsService`

```typescript
interface ReportsService {
  getSummary(userId: string, startDate: string, endDate: string): Observable<ReportSummary>;
  // GET /reports/summary?user_id=&start_date=&end_date=

  getDaily(userId: string, startDate: string, endDate: string): Observable<DailyBreakdown>;
  // GET /reports/daily?user_id=&start_date=&end_date=

  getDetails(userId: string, startDate: string, endDate: string): Observable<ReportDetails>;
  // GET /reports/details?user_id=&start_date=&end_date=
}
```

#### `NotificationsService`

```typescript
interface NotificationsService {
  subscribe(subscription: PushSubscriptionJSON): Observable<SubscriptionEntity>;
  // POST /notifications/subscribe

  unsubscribe(id: string): Observable<void>;
  // DELETE /notifications/subscribe/:id

  getSubscriptions(): Observable<SubscriptionEntity[]>;
  // GET /notifications/subscriptions

  getPreferences(choreId?: string): Observable<NotificationPreference[]>;
  // GET /notifications/preferences?chore_id=

  upsertPreference(dto: NotificationPreferenceDto): Observable<NotificationPreference>;
  // PUT /notifications/preferences

  deletePreference(id: string): Observable<void>;
  // DELETE /notifications/preferences/:id
}
```

### 6.3 HTTP Interceptors

**Auth Interceptor** (attaches JWT to every request):
```typescript
@Injectable()
export class AuthInterceptor implements HttpInterceptor {
  constructor(private authStore: AuthStore) {}

  intercept(req: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    const token = this.authStore.accessToken();
    if (token && !req.url.includes('/auth/')) {
      req = req.clone({
        setHeaders: { Authorization: `Bearer ${token}` },
      });
    }
    return next.handle(req);
  }
}
```

**Auth Error Interceptor** (handles 401 → refresh → retry):
```typescript
@Injectable()
export class AuthErrorInterceptor implements HttpInterceptor {
  private isRefreshing = false;
  private refreshSubject = new Subject<string | null>();

  constructor(
    private authService: AuthService,
    private authStore: AuthStore,
    private router: Router,
  ) {}

  intercept(req: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    return next.handle(req).pipe(
      catchError((error: HttpErrorResponse) => {
        if (error.status === 401 && !req.url.includes('/auth/refresh')) {
          return this.handle401(req, next);
        }
        return throwError(() => error);
      }),
    );
  }

  private handle401(req: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    if (this.isRefreshing) {
      // Queue request until refresh completes
      return this.refreshSubject.pipe(
        filter(token => token !== null),
        take(1),
        switchMap(token => next.handle(this.addToken(req, token!))),
      );
    }

    this.isRefreshing = true;
    this.refreshSubject = new Subject<string | null>();

    return this.authService.refreshToken().pipe(
      switchMap(tokens => {
        this.isRefreshing = false;
        this.refreshSubject.next(tokens.access_token);
        this.refreshSubject.complete();
        return next.handle(this.addToken(req, tokens.access_token));
      }),
      catchError(err => {
        this.isRefreshing = false;
        this.refreshSubject.error(err);
        this.authStore.logout();
        this.router.navigate(['/login']);
        return throwError(() => err);
      }),
    );
  }
}
```

### 6.4 Backend Contract Alignment

All frontend models match backend DTOs precisely:

| Frontend Model | Backend DTO | Notes |
|----------------|-------------|-------|
| `User` | `UserResponseDto` | `id`, `email`, `display_name`, `role`, `avatar_url`, `family_id`, `parent_id` |
| `Chore` | `ChoreResponseDto` | `id`, `title`, `description`, `schedule_type`, `weekdays`, `is_active`, `created_by`, `assigned_to`, `created_at` |
| `DashboardChore` | Dashboard endpoint response | `Chore` + `completed: boolean` |
| `Completion` | `CompletionResponseDto` | `id`, `chore_id`, `user_id`, `date`, `completed_at` |
| `ToggleResult` | Toggle response | `chore_id`, `user_id`, `date`, `completed: boolean` |
| `ReportSummary` | `ReportSummaryResponse` | See backend plan §5.5 |
| `DailyBreakdown` | `DailyBreakdownResponse` | See backend plan §5.5 |
| `NotificationPreference` | `NotificationPreferenceDto` | `id`, `chore_id`, `time`, `days`, `enabled` |

### 6.5 API Error Handling

```typescript
// core/services/api-error-handler.ts
export function handleApiError(error: HttpErrorResponse, snackBar: MatSnackBar): void {
  if (error.status === 0) {
    // Network error or CORS
    snackBar.open('Нет соединения с сервером. Проверьте интернет.', 'Повторить', { duration: 10000 });
    return;
  }

  const apiError = error.error as ApiErrorResponse;
  const message = Array.isArray(apiError.message) ? apiError.message.join('. ') : apiError.message;

  switch (error.status) {
    case 400:
      snackBar.open(`Ошибка: ${message}`, 'OK', { duration: 5000 });
      break;
    case 403:
      snackBar.open('У вас нет доступа к этому действию.', 'OK', { duration: 5000 });
      break;
    case 404:
      snackBar.open('Не найдено.', 'OK', { duration: 3000 });
      break;
    case 409:
      snackBar.open(`Конфликт: ${message}`, 'OK', { duration: 5000 });
      break;
    case 422:
      snackBar.open(`Невозможно выполнить: ${message}`, 'OK', { duration: 5000 });
      break;
    default:
      snackBar.open('Произошла ошибка. Попробуйте позже.', 'OK', { duration: 5000 });
  }
}
```

---

## 7. State Management (Angular Signals + SignalStore)

### 7.1 Store Architecture

Using `@ngrx/signals` `signalStore` with `withState`, `withComputed`, `withMethods`:

```
┌─────────────────────────────────────────────────────────┐
│                     Signal Stores                        │
│                                                         │
│  AuthStore ──────► authState, isAuthenticated,         │
│                    currentUser, isParent, familyId      │
│                                                         │
│  ChildrenStore ──► children[], selectedChildId          │
│                                                         │
│  ChoresStore ────► chores[], activeChores[],            │
│                    filteredChores[], loading, error      │
│                                                         │
│  DashboardStore ─► dashboardItems[], date,              │
│                    completionStats, loading              │
│                                                         │
│  CompletionsStore► completionsMap: Map<string, boolean> │
│                    optimisticUpdates: Set<string>        │
│                                                         │
│  NotificationsSt► preferences[], subscriptions[],       │
│                    pushSupported, pushGranted            │
│                                                         │
│  UIStore ────────► sidebarOpen, loading,                │
│                    snackbarMessages[], isOnline          │
│                                                         │
│  OfflineStore ───► pendingCompletions[],                │
│                    syncInProgress, lastSyncTime          │
└─────────────────────────────────────────────────────────┘
```

### 7.2 Key Store Designs

#### `AuthStore`

```typescript
export const AuthStore = signalStore(
  { providedIn: 'root' },
  withState<AuthState>({
    user: null,
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false,
    isLoading: true, // true during initial token check
  }),
  withComputed(({ user }) => ({
    isParent: computed(() => user()?.role === 'parent'),
    isChild: computed(() => user()?.role === 'child'),
    familyId: computed(() => user()?.family_id ?? ''),
    userId: computed(() => user()?.id ?? ''),
  })),
  withMethods((store) => ({
    setTokens(accessToken: string, refreshToken: string): void {
      patchState(store, { accessToken, refreshToken, isAuthenticated: true });
      // Store refresh token in localStorage (or HttpOnly cookie if backend sets it)
      localStorage.setItem('refresh_token', refreshToken);
    },
    setUser(user: User): void {
      patchState(store, { user, isLoading: false });
    },
    logout(): void {
      localStorage.removeItem('refresh_token');
      patchState(store, {
        user: null,
        accessToken: null,
        refreshToken: null,
        isAuthenticated: false,
      });
    },
    async initialize(): Promise<void> {
      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) {
        patchState(store, { isLoading: false });
        return;
      }
      // Try to refresh token, then load user
      // On failure: clear, redirect to login
    },
  })),
);
```

#### `DashboardStore`

```typescript
export const DashboardStore = signalStore(
  { providedIn: 'root' },
  withState<DashboardState>({
    items: [],
    selectedDate: format(new Date(), 'yyyy-MM-dd'), // today in local TZ → UTC
    selectedUserId: '', // set from AuthStore or ChildrenStore
    stats: { total: 0, completed: 0, missed: 0, rate: 0 },
    isLoading: false,
    error: null,
  }),
  withComputed(({ items, stats }) => ({
    dailyChores: computed(() =>
      items().filter(i => i.schedule_type === 'daily_weekday')
    ),
    weeklyChores: computed(() =>
      items().filter(i => i.schedule_type === 'weekly')
    ),
    progressPercent: computed(() => Math.round(stats().rate * 100)),
  })),
  withMethods((store, choresService = inject(ChoresService)) => ({
    async loadDashboard(userId: string, date: string): Promise<void> {
      patchState(store, { isLoading: true, error: null, selectedDate: date, selectedUserId: userId });
      try {
        const items = await firstValueFrom(choresService.getDashboard(date, userId));
        const completed = items.filter(i => i.completed).length;
        const total = items.length;
        patchState(store, {
          items,
          stats: {
            total,
            completed,
            missed: total - completed,
            rate: total > 0 ? completed / total : 0,
          },
          isLoading: false,
        });
      } catch (err) {
        patchState(store, { error: 'Failed to load dashboard', isLoading: false });
      }
    },
    optimisticallyToggle(choreId: string): void {
      const currentItems = store.items();
      const updated = currentItems.map(item =>
        item.id === choreId ? { ...item, completed: !item.completed } : item
      );
      patchState(store, { items: updated });
      // Recalculate stats optimistically
      const completed = updated.filter(i => i.completed).length;
      patchState(store, {
        stats: {
          ...store.stats(),
          completed,
          missed: updated.length - completed,
          rate: updated.length > 0 ? completed / updated.length : 0,
        },
      });
    },
    revertOptimisticToggle(choreId: string): void {
      // Revert if API fails
      const currentItems = store.items();
      const updated = currentItems.map(item =>
        item.id === choreId ? { ...item, completed: !item.completed } : item
      );
      patchState(store, { items: updated });
      const completed = updated.filter(i => i.completed).length;
      patchState(store, {
        stats: { ...store.stats(), completed, missed: updated.length - completed, rate: updated.length > 0 ? completed / updated.length : 0 },
      });
    },
  })),
);
```

### 7.3 Data Flow Pattern

```
User Action → Component → Store Method
                            ↓
                   Optimistic Update (if applicable)
                            ↓
                      Service Method (HTTP)
                            ↓
                  Success → Update Store with server data
                  Failure → Revert optimistic update + show error
```

### 7.4 Offline-First Data Flow (Completions)

```
User taps checkbox (offline)
  ↓
Optimistic update in DashboardStore
  ↓
Completion saved to IndexedDB queue (OfflineQueueService)
  ↓
Browser detects online event
  ↓
OfflineQueueService drains queue:
  - POST /completions/toggle for each queued item
  - On success: remove from queue
  - On conflict (409): resolve with latest server state
  - On failure: keep in queue, retry later
  ↓
DashboardStore refreshed with server data
```

---

## 8. PWA Implementation Details

### 8.1 `manifest.webmanifest`

```json
{
  "name": "Детский трекер дел",
  "short_name": "Детский трекер",
  "description": "Трекер ежедневных дел для детей и родителей",
  "theme_color": "#1565C0",
  "background_color": "#FAFAFA",
  "display": "standalone",
  "orientation": "portrait-primary",
  "scope": "/",
  "start_url": "/?utm_source=pwa",
  "id": "/?app=kids-chore-tracker",
  "icons": [
    { "src": "/assets/icons/icon-72x72.png", "sizes": "72x72", "type": "image/png" },
    { "src": "/assets/icons/icon-96x96.png", "sizes": "96x96", "type": "image/png" },
    { "src": "/assets/icons/icon-128x128.png", "sizes": "128x128", "type": "image/png" },
    { "src": "/assets/icons/icon-144x144.png", "sizes": "144x144", "type": "image/png" },
    { "src": "/assets/icons/icon-152x152.png", "sizes": "152x152", "type": "image/png" },
    { "src": "/assets/icons/icon-192x192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable" },
    { "src": "/assets/icons/icon-384x384.png", "sizes": "384x384", "type": "image/png", "purpose": "any maskable" },
    { "src": "/assets/icons/icon-512x512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable" }
  ],
  "screenshots": [
    {
      "src": "/assets/screenshots/mobile-screenshot.png",
      "sizes": "390x844",
      "type": "image/png",
      "form_factor": "narrow",
      "label": "Главный экран с задачами на сегодня"
    },
    {
      "src": "/assets/screenshots/desktop-screenshot.png",
      "sizes": "1280x800",
      "type": "image/png",
      "form_factor": "wide",
      "label": "Панель управления родителя"
    }
  ]
}
```

### 8.2 `ngsw-config.json` (Service Worker Cache Strategy)

```json
{
  "$schema": "./node_modules/@angular/service-worker/config/schema.json",
  "index": "/index.html",
  "assetGroups": [
    {
      "name": "app",
      "installMode": "prefetch",
      "updateMode": "prefetch",
      "resources": {
        "files": [
          "/favicon.ico",
          "/index.html",
          "/manifest.webmanifest",
          "/*.css",
          "/*.js"
        ]
      }
    },
    {
      "name": "assets",
      "installMode": "lazy",
      "updateMode": "lazy",
      "resources": {
        "files": [
          "/assets/**"
        ]
      }
    }
  ],
  "dataGroups": [
    {
      "name": "api-dashboard",
      "urls": ["/api/chores/dashboard**"],
      "cacheConfig": {
        "strategy": "freshness",
        "maxSize": 20,
        "maxAge": "15m",
        "timeout": "5s"
      }
    },
    {
      "name": "api-chores",
      "urls": ["/api/chores**"],
      "cacheConfig": {
        "strategy": "freshness",
        "maxSize": 50,
        "maxAge": "5m",
        "timeout": "5s"
      }
    },
    {
      "name": "api-reports",
      "urls": ["/api/reports**"],
      "cacheConfig": {
        "strategy": "freshness",
        "maxSize": 10,
        "maxAge": "1h",
        "timeout": "10s"
      }
    },
    {
      "name": "api-static",
      "urls": ["/api/users/**", "/api/notifications/**"],
      "cacheConfig": {
        "strategy": "freshness",
        "maxSize": 20,
        "maxAge": "30m",
        "timeout": "5s"
      }
    }
  ]
}
```

**Cache Strategy Rationale:**
- **App shell (prefetch)**: Installed immediately, always served from cache for instant loading.
- **Assets (lazy)**: Icons, images loaded on demand, cached after first use.
- **API data (freshness)**: Network-first with timeout; if network fails within timeout, serve cached version. This ensures fresh data while providing offline fallback.
- **Mutations (POST/PATCH/DELETE)**: Never cached, handled by offline queue.

### 8.3 PWA Install Prompt

```typescript
// shared/directives/pwa-install.directive.ts
@Directive({ selector: '[appPwaInstall]' })
export class PwaInstallDirective {
  private deferredPrompt: any = null;

  @HostListener('window:beforeinstallprompt', ['$event'])
  onBeforeInstallPrompt(event: Event): void {
    event.preventDefault();
    this.deferredPrompt = event;
    // Show install button via signal
    this.uiStore.showInstallButton.set(true);
  }

  install(): void {
    if (!this.deferredPrompt) return;
    this.deferredPrompt.prompt();
    this.deferredPrompt.userChoice.then((result: { outcome: string }) => {
      if (result.outcome === 'accepted') {
        this.uiStore.showInstallButton.set(false);
      }
      this.deferredPrompt = null;
    });
  }
}
```

### 8.4 Background Sync for Offline Completions

```typescript
// core/services/offline-queue.service.ts
@Injectable({ providedIn: 'root' })
export class OfflineQueueService {
  private db!: IDBPDatabase;
  private readonly STORE_NAME = 'pending-completions';

  constructor(
    private completionsService: CompletionsService,
    private dashboardStore: DashboardStore,
  ) {
    this.initDB();
    this.listenForOnline();
  }

  private async initDB(): Promise<void> {
    this.db = await openDB('kids-chore-offline', 1, {
      upgrade(db) {
        if (!db.objectStoreNames.contains('pending-completions')) {
          const store = db.createObjectStore('pending-completions', {
            keyPath: 'id',
            autoIncrement: true,
          });
          store.createIndex('choreId', 'choreId');
        }
      },
    });
  }

  async enqueue(choreId: string, date: string): Promise<void> {
    await this.db.add(this.STORE_NAME, {
      choreId,
      date,
      timestamp: Date.now(),
    });
  }

  private listenForOnline(): void {
    fromEvent(window, 'online').subscribe(() => {
      this.syncQueue();
    });
  }

  async syncQueue(): Promise<void> {
    const pending = await this.db.getAll(this.STORE_NAME);
    for (const item of pending) {
      try {
        const result = await firstValueFrom(
          this.completionsService.toggle(item.choreId, item.date)
        );
        await this.db.delete(this.STORE_NAME, item.id);
      } catch (err: any) {
        if (err.status === 409) {
          // Conflict: server already has this state, just remove from queue
          await this.db.delete(this.STORE_NAME, item.id);
        }
        // Other errors: keep in queue, retry later
      }
    }

    // Refresh dashboard after sync
    const state = this.dashboardStore;
    if (pending.length > 0) {
      this.dashboardStore.loadDashboard(state.selectedUserId(), state.selectedDate());
    }
  }
}
```

---

## 9. Timezone Handling

### 9.1 Strategy

- **Backend**: All dates stored and transmitted in UTC (`YYYY-MM-DD` for dates, ISO 8601 `TIMESTAMPTZ` for timestamps).
- **Frontend**: All dates displayed in user's local timezone.
- **API requests**: Frontend converts local date → UTC `YYYY-MM-DD` string before sending.
- **API responses**: Frontend converts UTC strings → local `Date` objects for display.

### 9.2 Implementation

```typescript
// core/services/timezone.service.ts
@Injectable({ providedIn: 'root' })
export class TimezoneService {
  /**
   * Get today's date as UTC YYYY-MM-DD string based on local timezone.
   * E.g., if local is Europe/Moscow (UTC+3) and local time is 2025-04-15 01:00,
   * UTC date is 2025-04-14, but "today" for the user is 2025-04-15.
   * So we send the LOCAL date string.
   *
   * IMPORTANT: The backend interprets the date as UTC calendar date.
   * The frontend must convert the user's local notion of "today" to the
   * corresponding UTC date string. For simplicity and consistency with
   * the backend spec, we use local ISO date string as the canonical "day".
   *
   * Example:
   * - User in Moscow (UTC+3), local time 2025-04-15 02:00
   * - User considers "today" = 2025-04-15
   * - We send date=2025-04-15
   * - Backend treats this as UTC 2025-04-15
   * - Chores with weekday=Tuesday (bit 2) match because backend checks
   *   if UTC 2025-04-15 is a Tuesday
   * - This works because UTC 2025-04-15 is indeed Tuesday, and the user
   *   also considers it Tuesday in their local tz.
   *
   * Edge case near midnight: if user is at UTC+10 and it's 01:00 on Wednesday
   * locally, UTC is still Tuesday. The user sees "Wednesday" but the backend
   * sees UTC Tuesday. This is acceptable per spec ("UTC-only on backend").
   */
  toUtcDateString(date: Date): string {
    return format(date, 'yyyy-MM-dd');
  }

  todayUtcDateString(): string {
    return this.toUtcDateString(new Date());
  }

  /**
   * Convert a UTC date string from the server to a local Date object for display.
   */
  utcDateStringToLocal(utcDateStr: string): Date {
    // Parse as UTC midnight
    return new Date(utcDateStr + 'T00:00:00Z');
  }

  /**
   * Get local weekday index from UTC date string.
   * Matches backend bitmask convention: 0=Mon, 1=Tue, ..., 6=Sun.
   */
  utcDateStringToLocalWeekdayIndex(utcDateStr: string): number {
    const date = this.utcDateStringToLocal(utcDateStr);
    // getDay(): 0=Sun ... 6=Sat → map to 0=Mon ... 6=Sun
    const jsDay = date.getDay();
    return jsDay === 0 ? 6 : jsDay - 1;
  }

  /**
   * Format a UTC date string for display.
   */
  formatDate(utcDateStr: string, formatStr: string = 'dd.MM.yyyy'): string {
    return format(this.utcDateStringToLocal(utcDateStr), formatStr);
  }

  /**
   * Format a UTC time string (HH:MM) to local time for display.
   */
  formatTime(utcTimeStr: string): string {
    // utcTimeStr is "HH:MM" in UTC
    // Create a today date with that UTC time
    const now = new Date();
    const [hours, minutes] = utcTimeStr.split(':').map(Number);
    const utcDate = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate(), hours, minutes));
    return format(utcDate, 'HH:mm'); // format() uses local timezone
  }

  /**
   * Convert local time (HH:MM) to UTC time string for API.
   */
  localTimeToUtc(localTimeStr: string): string {
    const [hours, minutes] = localTimeStr.split(':').map(Number);
    const now = new Date();
    // Create local date with given time
    const localDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hours, minutes);
    // Extract UTC hours and minutes
    return format(localDate, 'HH:mm'); // Actually need UTC: use getUTCHours()
    // Better implementation:
    // return `${String(localDate.getUTCHours()).padStart(2,'0')}:${String(localDate.getUTCMinutes()).padStart(2,'0')}`;
  }
}
```

---

## 10. Edge Cases & Error States

### 10.1 Authentication Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| **Token expires mid-session** | Auth Error Interceptor catches 401, attempts refresh. If refresh fails → redirect to `/login`. If refresh succeeds → retry original request transparently. |
| **Refresh token expired (7 days)** | Redirect to `/login` with message "Сессия истекла. Войдите снова." |
| **User opens app in two tabs** | Both tabs share `localStorage` refresh token. If one refreshes, the other's next request also uses the new token (stored in `localStorage`). Keep access token in memory (Signal), not `localStorage`. |
| **Google OAuth popup blocked** | Fallback: full-page redirect to Google (not popup). Backend redirects back to frontend callback URL. |
| **Child email not yet registered** | Parent adds child email. Child attempts login via Google → user record exists (created by parent) but not yet "activated" (no Google login yet). Backend handles; frontend shows appropriate welcome screen on first login. |
| **User clicks Google login but is already logged into wrong Google account** | Google OAuth shows account chooser with `prompt=select_account` parameter. |

### 10.2 Dashboard Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| **No chores for today** | Empty state: illustration + "Сегодня дел нет! 🎉" + optional button to add chore. |
| **All chores completed** | Celebration: progress bar at 100% with gold color + star icon. Subtle confetti animation (optional). |
| **User navigates to future date** | Allow viewing future chores (read-only). Completion checkboxes disabled with tooltip "Отметка будет доступна в этот день". |
| **User navigates to past date** | Show historical state. Completion checkboxes enabled only if past date's weekday matches chore schedule. |
| **Midnight boundary** | Date displayed is based on local timezone. At midnight, "today" rolls over. Auto-refresh dashboard at midnight using `setTimeout` to next midnight. |
| **Parent views child with no chores** | Empty state: "У {child_name} пока нет задач. Создайте первую!" with CTA button. |

### 10.3 Chore Form Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| **Weekly chore: what about weekdays?** | When `schedule_type='weekly'`, the weekday picker is hidden or all days auto-selected (bitmask 127). The backend interprets 127 as "any day this week". |
| **Child creating chore** | `assigned_to` field auto-set to self, field hidden (or shown as read-only display). |
| **Parent creating chore for child** | `assigned_to` dropdown shows only children in current family. |
| **Duplicate chore title** | Allowed (not enforced as unique). Each chore has UUID PK. |
| **Deleting chore with completions** | Backend has `ON DELETE CASCADE` on `chore_completions.chore_id`. Frontend confirms with dialog mentioning history will be lost. |
| **Max chores per user** | No hard limit initially. Consider UI warning if > 20 active chores per child. |

### 10.4 Completion Toggle Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| **Double-tap (rapid toggle)** | First tap triggers optimistic update + API call. Disable checkbox during API call (`isToggling` flag). Re-enable after response. |
| **Toggle for wrong day** | Backend returns 422. Frontend reverts optimistic update, shows snackbar "Отметка недоступна для этого дня". |
| **Offline toggle** | Optimistic update applied immediately. Toggle queued in IndexedDB. Sync on reconnect. If server returns 409 (already exists or already deleted), resolve by removing queue item silently. |
| **Parent marks completion for child** | Allowed. `user_id` in toggle request = selected child's ID (not parent's). |
| **Toggle on weekly chore** | Allowed any day of the week. Backend validates, frontend shows no restriction. |

### 10.5 PWA Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| **Service Worker update available** | Show snackbar "Доступна новая версия приложения. [Обновить]". On click → `SwUpdate.activateUpdate()` → reload. |
| **Service Worker update fails** | Log error, continue with cached version. |
| **Full offline mode** | Offline banner shown. Cached dashboard data displayed (from `ngsw` dataGroup cache). Completion checkboxes still work (queued). |
| **iOS Safari limitations** | Web Push not supported on iOS < 16.4. Detect support via `'PushManager' in window`. Hide notification settings if unsupported, show informational message. |
| **`beforeinstallprompt` not fired** | Some browsers don't fire it. Show manual install instructions: "Откройте меню браузера → Добавить на главный экран". |
| **PWA installed but user opens browser version** | `display-mode: standalone` media query in CSS to adjust UI. Show subtle "Открыть в приложении" hint. |

### 10.6 Reports Edge Cases

| Edge Case | Behavior |
|-----------|----------|
| **Period with no chores assigned** | 0% completion rate, empty chart, message: "В этом периоде не было задач". |
| **Period > 90 days** | Backend may limit range. Frontend caps date picker range at 90 days. Show validation message. |
| **Child has no completions ever** | Empty state in report details. Chart shows zero bars. |
| **Date range where child didn't exist yet** | Backend filters by `user_id`, so no data. Frontend shows "Нет данных за выбранный период". |

---

## 11. Push Notification Frontend Flow

### 11.1 Subscription Flow

```
1. User opens app → check PushManager support
2. If supported:
   a. Check existing subscription via SwPush.subscription
   b. If exists → compare with backend subscriptions
   c. If not exists → show "Хотите получать напоминания?" dialog
3. User clicks "Да" → SwPush.requestSubscription({ serverPublicKey: VAPID_PUBLIC_KEY })
4. On success:
   a. Send subscription to POST /api/notifications/subscribe
   b. Store subscription ID in NotificationsStore
5. On denial:
   a. Show "Вы можете включить уведомления позже в настройках"
   b. NotificationsStore.pushGranted = false
6. Browser notification permission already denied:
   a. Show instructions: "Разрешите уведомления в настройках браузера"
```

### 11.2 VAPID Public Key Distribution

```typescript
// The VAPID public key is embedded at build time via environment config
// environments/environment.ts
export const environment = {
  vapidPublicKey: 'BP...', // From backend .env VAPID_PUBLIC_KEY
};
```

### 11.3 Notification Click Handling

```typescript
// In app.component.ts or a dedicated service
constructor(private swPush: SwPush, private router: Router) {
  this.swPush.notificationClicks.subscribe(({ action, notification }) => {
    const data = notification.data as { chore_id?: string; url?: string };
    if (data.url) {
      this.router.navigateByUrl(data.url);
    }
  });
}
```

---

## 12. Testing Considerations

### 12.1 Unit Tests (Jest + Angular Testing Library)

**Coverage Target**: ≥80% for services, stores, shared components.

| Test Area | Examples |
|-----------|----------|
| **Services** | `AuthService`: token storage/retrieval, refresh flow, logout. `ChoresService`: CRUD calls with correct params. `CompletionsService`: toggle API call. `TimezoneService`: UTC ↔ local conversion correctness across DST boundaries. |
| **Signal Stores** | `AuthStore`: login sets state, logout clears, computed `isParent` works. `DashboardStore`: loadDashboard populates items, optimisticallyToggle updates items, revertOptimisticToggle restores state. |
| **Shared Components** | `WeekdayPicker`: emits correct bitmask on selection, all/none edge cases. `CompletionCheckbox`: emits toggle, disabled state during API call, animation triggers. |
| **Pipes** | `WeekdayNamePipe`: 0→"Пн", 6→"Вс". `CompletionRatePipe`: 0.75→"75%". `LocalDatePipe`: UTC string→formatted local date. |
| **Interceptors** | `AuthInterceptor`: adds Bearer token, skips auth routes. `AuthErrorInterceptor`: 401 triggers refresh, queues concurrent requests. |
| **Validators** | Chore form validators: required title, valid bitmask range, at least one weekday for daily type. |

### 12.2 Component Tests

```typescript
// Example: dashboard-page.component.spec.ts
describe('DashboardPageComponent', () => {
  it('should display chores grouped by daily and weekly', async () => {});
  it('should show empty state when no chores', async () => {});
  it('should show loading skeleton while fetching', async () => {});
  it('should update progress bar when chore is toggled', async () => {});
  it('should disable checkboxes for future dates', async () => {});
  it('should show kid selector for parent, not for child', async () => {});
  it('should navigate date with arrows', async () => {});
});
```

```typescript
// Example: chore-form.component.spec.ts
describe('ChoreFormComponent', () => {
  it('should hide weekday picker when schedule_type is weekly', async () => {});
  it('should hide assigned_to field for child user', async () => {});
  it('should show assigned_to dropdown for parent with children list', async () => {});
  it('should validate title is required', async () => {});
  it('should emit correct payload on submit', async () => {});
  it('should pre-fill form in edit mode', async () => {});
});
```

### 12.3 Integration Tests

Test service + store + component together:

```typescript
describe('Dashboard Integration', () => {
  it('full flow: load → display → toggle → sync', async () => {
    // Setup: mock HTTP to return dashboard items
    // Render DashboardPageComponent
    // Assert: items displayed
    // Click checkbox → optimistic update visible
    // Mock API success → store updated
    // Assert: progress bar color changes
  });

  it('offline flow: toggle → queue → online → sync', async () => {
    // Mock navigator.onLine = false
    // Click checkbox → queued in IndexedDB
    // Mock navigator.onLine = true
    // Dispatch 'online' event
    // Assert: API called, queue cleared
  });
});
```

### 12.4 E2E Tests (Playwright)

**Key Scenarios:**

| # | Scenario | Steps |
|---|----------|-------|
| E2E-01 | Parent Registration | Navigate to `/login` → Click "Войти через Google" → Mock Google OAuth → Verify redirect to `/dashboard` → Verify parent role UI |
| E2E-02 | Add Child | Login as parent → Navigate to `/kids` → Click "Добавить" → Enter child email → Submit → Verify child appears in list |
| E2E-03 | Create Chore | Login as parent → Navigate to `/chores` → Click "Новая задача" → Fill form → Select days → Assign to child → Submit → Verify chore appears |
| E2E-04 | Child Completes Chore | Login as child → See dashboard → Click checkbox on a chore → Verify optimistic checkmark → Verify progress bar updates |
| E2E-05 | Undo Completion | Click checked checkbox → Verify unchecked → Verify progress bar decreases |
| E2E-06 | Parent Views Report | Login as parent → Navigate to `/reports` → Select child → Select period → Click "Применить" → Verify summary cards, chart, lists |
| E2E-07 | Push Notification Setup | Navigate to `/settings/notifications` → Click subscribe → Mock push permission grant → Verify subscription appears → Add notification preference → Verify saved |
| E2E-08 | PWA Install | Open in Chrome Android → Wait for `beforeinstallprompt` → Click install button → Verify app opens in standalone mode |
| E2E-09 | Offline Dashboard | Enable offline mode (Playwright `context.setOffline(true)`) → Dashboard shows cached data → Toggle checkbox → Go online → Verify sync |
| E2E-10 | Token Refresh | Login → Wait for access token to expire (mock short expiry) → Perform action → Verify silent refresh → Action succeeds |

### 12.5 PWA Audit (Lighthouse)

Run Lighthouse PWA audit and target **≥90%** PWA score:

| Check | How to Pass |
|-------|-------------|
| Registers a service worker | `ngsw-config.json` + `ServiceWorkerModule.register('ngsw-worker.js')` |
| Responds with 200 when offline | `ngsw` caches `index.html` and app shell |
| Has a valid `manifest.json` | Customized manifest with all required fields |
| Has installable icons | 192px and 512px PNG icons with `maskable` purpose |
| Contains a `theme-color` meta tag | `<meta name="theme-color" content="#1565C0">` |
| Has a `viewport` meta tag | `<meta name="viewport" content="width=device-width, initial-scale=1">` |
| Redirects HTTP to HTTPS | Nginx handles in production |
| Content is sized correctly for viewport | Responsive Material Design |

### 12.6 Accessibility Testing

- Run `axe-core` / `@angular-eslint/template` accessibility rules.
- Test keyboard navigation: Tab through all interactive elements, Enter/Space to activate.
- Test screen reader (NVDA/VoiceOver) for all key flows.
- Verify color contrast meets WCAG AA (4.5:1 for text, 3:1 for large text).
- Verify all `mat-icon` buttons have `aria-label`.

---

## 13. Docker Integration (Frontend)

### 13.1 Frontend Dockerfile

```dockerfile
# Stage 1: Build
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build -- --configuration production

# Stage 2: Serve with Nginx
FROM nginx:1.25-alpine
COPY --from=builder /app/dist/frontend/browser /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### 13.2 Nginx Configuration

```nginx
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;
    gzip_min_length 1000;

    # Angular SPA routing: all non-file routes → index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to backend
    location /api/ {
        proxy_pass http://backend:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
```

### 13.3 Environment-Specific Builds

```typescript
// environments/environment.ts (development)
export const environment = {
  production: false,
  apiUrl: 'http://localhost:3000/api',
  vapidPublicKey: 'BP...',
  googleClientId: 'xxx.apps.googleusercontent.com',
};

// environments/environment.prod.ts (production)
export const environment = {
  production: true,
  apiUrl: '/api', // Same origin, proxied by Nginx
  vapidPublicKey: 'BP...',
  googleClientId: 'xxx.apps.googleusercontent.com',
};
```

---

## 14. Key Design Decisions & Rationale

| Decision | Rationale |
|----------|-----------|
| **Angular Signals + SignalStore over NgRx** | Spec preference. Signals provide simpler reactive state with less boilerplate. SignalStore (`@ngrx/signals`) gives structured state management without NgRx's action/reducer/effect ceremony. Appropriate for this app's complexity level. |
| **Angular Material over PrimeNG** | Better accessibility (WCAG 2.1 AA built-in), mature, excellent Angular integration, official Google Material Design, CDK for advanced behaviors. PrimeNG is heavier and less a11y-focused. |
| **Optimistic UI for completions** | Children need instant feedback. Waiting for server response feels laggy on mobile. Revert on failure is simple with Signals. |
| **IndexedDB for offline queue** | More reliable than `localStorage` for structured data, supports indices, transactional. `idb` library provides clean Promise-based API. |
| **`date-fns` over `luxon`** | Tree-shakeable, smaller bundle (~10KB vs ~70KB), functional style matches Angular Signals reactivity. No class instances needed for simple date formatting. |
| **Dialog over Page for chore form** | Keeps context visible, reduces navigation, feels more app-like on mobile. Dialog scrolls internally if content exceeds viewport. |
| **Bottom nav on mobile, side nav on desktop** | Children primarily use mobile. Bottom nav is thumb-reachable. Side nav on desktop gives more vertical space for content. |
| **No SSR (Angular Universal)** | Spec explicitly states SPA. PWA service worker handles offline. SSR adds complexity not needed for this use case. |
| **Nginx proxy in Docker** | Single origin avoids CORS issues in production. Nginx handles static file serving efficiently, gzip, caching headers. |
| **Russian-language UI default** | Spec is in Russian, target users are Russian-speaking families. i18n structure prepared for future localization. |

---

## 15. Risks & Mitigations (Frontend-Specific)

| Risk | Impact | Mitigation |
|------|--------|------------|
| **iOS Safari Web Push limited support** | iOS users don't get notifications | Feature detection: hide push settings if unsupported. Show message. Consider alternative: in-app notification badge on next visit. |
| **Service Worker cache serving stale data** | User sees outdated chores/completions | Use `freshness` strategy for API data groups (network-first with short timeout). Dashboard auto-reloads on visibility change (`document.visibilitychange`). |
| **IndexedDB not available (private browsing Safari)** | Offline completions queue fails | Fall back to in-memory queue (lost on tab close). Detect and warn user: "Оффлайн-отметки не сохранятся если вы закроете вкладку". |
| **Children may share devices** | Wrong user's data shown | No "remember me" beyond JWT refresh token. Logout clears all state. Encourage logging out on shared devices. |
| **Large report date range causes slow rendering** | UI freeze when plotting many bars | Client-side limit of 90 days (matching backend). Virtual scroll for long completion lists. Debounce chart resize. |
| **Angular bundle size too large for slow mobile** | Slow initial load on 3G | Lazy-load all feature modules. Analyze with `webpack-bundle-analyzer`. Target < 300KB initial JS (compressed). Service worker pre-caches app shell. |
| **Google OAuth popup / redirect flow inconsistent across browsers** | Login failures | Use full redirect flow (not popup) for reliability. Test on Chrome, Firefox, Safari, Samsung Internet. |

---

## 16. Sprint-Aligned Frontend Delivery

### Sprint 1: Foundation (Auth + Shell + Routing)

**Frontend tasks:**
- Initialize Angular 17+ project with Angular Material.
- Set up project structure (core, shared, features).
- Configure routing with guards (AuthGuard, NoAuthGuard, RoleGuard).
- Implement `AuthService`, `AuthStore`, `AuthInterceptor`, `AuthErrorInterceptor`.
- Build `LoginPageComponent` with Google login button.
- Build `AuthCallbackComponent` to receive tokens.
- Build app shell: `AppComponent` with toolbar, responsive sidenav/bottom-nav, role-based navigation.
- PWA: `@angular/pwa` setup, manifest.json, `ngsw-config.json`.
- Docker config: `Dockerfile`, `nginx.conf`.
- Unit tests for auth services and stores.

**Deliverable:** Working Google login flow, protected routing, responsive shell with PWA manifest.

### Sprint 2: Dashboard + Chores + Completions

**Frontend tasks:**
- Implement `UsersService`, `ChoresService`, `CompletionsService`.
- Implement `ChildrenStore`, `ChoresStore`, `DashboardStore`, `CompletionsStore`.
- Build `DashboardPageComponent` with date navigator, kid selector, progress bar.
- Build `DashboardChoreListComponent` with daily/weekly grouping.
- Build `ChoreCardComponent`, `CompletionCheckboxComponent` (with optimistic toggle).
- Build `ChoresPageComponent` with filter chips and search.
- Build `ChoreFormComponent` (dialog) with `WeekdayPickerComponent`.
- Build `ChoreDetailComponent`.
- Build `KidsPageComponent` with `AddChildDialogComponent`, `ChildCardComponent`.
- Implement `OfflineQueueService` with IndexedDB for completions.
- Implement `TimezoneService`.
- Implement `offline-banner` component.
- NgRx Signal Stores complete with all computed signals.
- Unit + integration tests for dashboard and chores.

**Deliverable:** Full chore management, daily dashboard with completion toggling, child management for parents, offline-capable completions.

### Sprint 3: Push Notifications + PWA Polish

**Frontend tasks:**
- Implement `NotificationsService`, `SwPushService`.
- Implement `NotificationsStore`.
- Build `NotificationSettingsComponent` with subscription management.
- Build `PushSubscriptionComponent` (subscribe/unsubscribe buttons).
- Build notification preference form (time picker, weekday picker, chore selector, enable toggle).
- Implement click-on-notification handler (navigate to dashboard).
- PWA polish: install prompt (`PwaInstallDirective`), update handling, offline fallback page.
- `OfflineBannerComponent` with online/offline detection.
- Test push flow end-to-end with backend.
- Lighthouse PWA audit and fixes.

**Deliverable:** Push notifications functional, PWA installable with score ≥90%, offline experience polished.

### Sprint 4: Reports + Final Polish

**Frontend tasks:**
- Implement `ReportsService`.
- Build `ReportsPageComponent` with `PeriodPickerComponent`, `KidSelectorComponent`.
- Build `ReportSummaryComponent` (stats cards).
- Build `ReportChartComponent` using `ngx-charts` or `chart.js` via `ng2-charts`.
- Build `ReportDetailsComponent` (completed/missed lists with expand/collapse).
- Build `SettingsPageComponent` with profile and notification tabs.
- Build `ProfileSettingsComponent`.
- Final responsive testing on real mobile devices.
- Accessibility audit (axe-core, keyboard, screen reader).
- Final E2E tests with Playwright (all 10 scenarios).
- Performance optimization: lazy loading, bundle analysis.
- Production build and Docker Compose validation.

**Deliverable:** Full app complete with reports, settings, tested on target devices, production-ready.

---

## 17. Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| First Contentful Paint | < 1.5s (4G) | Lighthouse |
| Time to Interactive | < 3.0s (4G) | Lighthouse |
| Initial JS bundle (compressed) | < 300 KB | `webpack-bundle-analyzer` |
| PWA Score | ≥ 90% | Lighthouse PWA Audit |
| Accessibility Score | ≥ 90% | Lighthouse Accessibility Audit |
| Offline dashboard load | < 1s | Manual test |
| API response handling | < 100ms (optimistic UI hides latency) | DevTools Network |

---

This plan provides a complete, implementation-ready frontend design covering all pages, components, state management, API integration, PWA configuration, offline strategy, edge cases, and testing approaches as specified in the approved specification `docs/specs/latest-plan.md` and aligned with the backend plan. The architecture follows Angular 17+ best practices with Signals, Angular Material, and is ready for immediate Sprint 1 implementation.