# Studio — Backend for Boutique Fitness Studios

A high-concurrency, double-entry ledger based booking core for boutique fitness studios built with **Django 5.x**, **Django REST Framework (DRF)**, and **PostgreSQL / SQLite**.

---

## Table of Contents

- [1. Overview & Architecture](#1-overview--architecture)
- [2. Business Rules & Implementation](#2-business-rules--implementation)
- [3. Design Patterns & Principles](#3-design-patterns--principles)
- [4. Quickstart & Docker](#4-quickstart--docker)
- [5. Running Linters & Tests](#5-running-linters--tests)
- [6. End-to-End Walkthrough](#6-end-to-end-walkthrough)
- [7. API Reference](#7-api-reference)
- [8. Deliverables & Artifacts](#8-deliverables--artifacts)

---

## 1. Overview & Architecture

Studio manages the full lifecycle of boutique fitness scheduling:
- **Studios**: Multi-location studios with independent IANA timezones and configurable cancellation cutoffs.
- **Classes**: Capacity-capped classes with credit costs and date-range scheduling.
- **Credit Packs & Double-Entry Ledger**: Member credits purchased or granted in packs, with FIFO expiry tracking, point-in-time balance reconstruction, and immutable audit trails.
- **Concurrency & Idempotency**: Zero overbooking guarantees under concurrent requests via row-level database locking and strict atomic transactions.
- **Waitlist & Auto-Promotion**: FIFO queue for full classes with dynamic promotion of eligible members upon cancellation.

```
┌────────────────────────────────────────────────────────┐
│                      Client Layer                      │
│       (Idempotency-Key header, JWT Authorization)      │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                    API / DRF Views                     │
│  accounts.views │ studios.views │ credits.views │ ...  │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                     Service Layer                      │
│      credits.services      │     bookings.services     │
│   - grant_credit_pack      │  - create_booking         │
│   - deduct_credits (FIFO)  │  - cancel_booking (Cutoff)│
│   - get_credit_balance     │  - _promote_waitlisted    │
│   - get_ledger             │                           │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│             Database Layer & State Store               │
│ (Transactions, SELECT FOR UPDATE, Check Constraints)   │
└────────────────────────────────────────────────────────┘
```

---

## 2. Business Rules & Implementation

| # | Business Rule | Implementation in Code |
|---|---|---|
| **1** | Studio has name, IANA timezone, cancellation cutoff hours (default 4). | Model `Studio` with `timezone_field.TimeZoneField`, validated via `zoneinfo.ZoneInfo`. Positive integer validator for cutoff hours. |
| **2** | Class has start time, duration, spots, and cost in whole credits. | Model `FitnessClass` with `CheckConstraint` guaranteeing positive duration, spots, and credit cost. Start times validated in future. |
| **3** | Staff grant credit packs with grant date and expiry date. Whole credits. | Model `CreditPack` and `grant_credit_pack` service. Only Staff/Admin can grant packs. Optional `granted_at` supported (defaults to `now`). |
| **4** | Credits are whole numbers. | Enforced as `PositiveIntegerField` on models and serializers. |
| **5** | FIFO credit deduction (expiring soonest spent first). Expired credits cannot be spent. | In `deduct_credits`, packs are locked and ordered by `expires_at ASC, granted_at ASC`. Filter `expires_at > now` strictly excludes expired packs. |
| **6** | Never confirm more bookings than spots under any concurrency. | Double protection: `select_for_update()` row-level locks on `FitnessClass`, atomic F-expression increment (`confirmed_count < spots`), and DB-level `CheckConstraint(confirmed_count <= spots)`. |
| **7** | Cancellation at/before cutoff refunds credits in full. After cutoff forfeits credits. | In `cancel_booking`, studio cutoff local time is calculated. If `now_local <= cutoff_local`, `_refund_booking_credits` restores credits to original packs; otherwise credits are forfeited. |
| **8** | Cutoff measured in studio local timezone, not server's. | Computed via `class_start_local = class.start_time.astimezone(studio_tz)` and `now_local = now.astimezone(studio_tz)` where `studio_tz = ZoneInfo(studio.timezone)`. |
| **9** | Waitlist for full classes. Promotion of longest-waiting member who can afford it. Unaffordable keep place. | FIFO ordering `order_by("booked_at", "id")`. In `_promote_waitlisted_member`, skips members with insufficient credits without modifying their waitlist record. When an eligible member is found, they are confirmed, charged, and spot is reserved. |
| **10** | Reconstruct balance at past moment & account for every credit movement with cause. | `get_credit_balance(as_of=...)` replays transaction history up to `as_of`. `Transaction` table records every CREDIT and DEBIT with cause (`PACK_GRANT`, `BOOKING_CHARGE`, `CANCELLATION_REFUND`). |
| **11** | Idempotency keys prevent duplicate bookings/charges on retry. | Header `Idempotency-Key` required. DB unique constraint `UniqueConstraint(member, idempotency_key)`. Replay returns existing booking without re-charging. |
| **12** | Members may only read and act on their own data. | Views enforce queryset scoping (`member=request.user`). Explicit check rejects non-staff attempting `?member=<other_id>` with 403 Forbidden. |
| **13** | A booking can be cancelled once. Repeated cancellation rejected. | Guard `if booking.status == CANCELLED: raise ValidationError`. DB unique constraint prevents duplicate refunds per booking and pack. |

---

## 3. Design Patterns & Principles

1. **Service Layer Pattern (`services.py`)**:
   - Thin views, fat domain services.
   - Encapsulates complex transaction boundaries, locking, credit deductions, and waitlist logic outside of HTTP request/response cycles.
2. **Double-Entry Ledger Pattern (`credits.models.Transaction`)**:
   - Every movement in a member's credit balance is backed by an immutable transaction record with a type (`C`/`D`), cause, amount, and timestamp.
   - Encapsulated via `CreditPack.add_transaction(...)` on the pack model, ensuring clean aggregate boundaries and eliminating boilerplate.
   - Enables auditable, deterministic point-in-time balance reconstruction at any historical timestamp `as_of`.
3. **Pessimistic Concurrency Control (`SELECT FOR UPDATE`)**:
   - Row-level database locks are acquired on classes and credit packs during booking, cancellation, and deduction to eliminate race conditions under high concurrent load.
4. **Idempotent Receiver Pattern**:
   - Handles network timeouts and client retries safely by indexing `(member, idempotency_key)`. Replaying the same request returns the original resource state without side effects.
5. **SOLID & DRY**:
   - Single Responsibility: Models represent domain state; services handle business logic; serializers validate input/output; views manage HTTP routing and permission guards.

---

## 4. Quickstart & Docker

### Option A: Docker (One command to run, one to test)

1. **Start the application**:
   ```bash
   docker compose up --build
   ```
   The API will be available at `http://127.0.0.1:8000/api/v1/`.

2. **Run tests in Docker**:
   ```bash
   docker compose run --rm test
   ```

### Option B: Local Setup (Python 3.13+)

1. **Create and activate a virtual environment**:
   ```bash
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\activate
   # Linux/macOS:
   source .venv/bin/activate
   ```

2. **Install pinned dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Apply migrations**:
   ```bash
   python manage.py migrate
   ```

4. **Create a superuser / admin**:
   ```bash
   python manage.py createsuperuser --phone_number "+919876500000"
   ```

5. **Start development server**:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

---

## 5. Running Linters & Tests

- **Run unit & integration test suite**:
  ```bash
  python manage.py test
  ```
- **Run Ruff linter**:
  ```bash
  ruff check .
  ```
- **Run Mypy static type checker**:
  ```bash
  mypy .
  ```

---

## 6. End-to-End Walkthrough

Follow this flow using cURL or the included Postman collection:

1. **Register & Login Staff User**:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/users/login/ \
     -H "Content-Type: application/json" \
     -d '{"phone_number": "+919876500000", "password": "AdminPass123!"}'
   ```
   Save the returned `access` token as `STAFF_TOKEN`.

2. **Register & Login Member User**:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/users/register/ \
     -H "Content-Type: application/json" \
     -d '{"phone_number": "+919876500001", "password_1": "MemberPass123!", "password_2": "MemberPass123!", "role": "MEMBER"}'

   curl -X POST http://127.0.0.1:8000/api/v1/users/login/ \
     -H "Content-Type: application/json" \
     -d '{"phone_number": "+919876500001", "password": "MemberPass123!"}'
   ```
   Save the returned `access` token as `MEMBER1_TOKEN`.

3. **Staff Creates Studio**:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/studios/ \
     -H "Authorization: Bearer $STAFF_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"name": "Brooklyn Strength Lab", "timezone": "America/New_York", "cancellation_cutoff_hours": 4}'
   ```

4. **Staff Schedules Class**:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/classes/ \
     -H "Authorization: Bearer $STAFF_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"studio": 1, "name": "HIIT 50", "start_time": "2026-10-25T10:00:00Z", "duration_minutes": 50, "spots": 1, "credit_cost": 2}'
   ```

5. **Staff Grants Credit Pack to Member**:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/credit-packs/ \
     -H "Authorization: Bearer $STAFF_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"member": 2, "granted_credits": 10, "expires_at": "2026-11-25T00:00:00Z"}'
   ```

6. **Member Books Class (Filling It)**:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/bookings/ \
     -H "Authorization: Bearer $MEMBER1_TOKEN" \
     -H "Idempotency-Key: idem-key-001" \
     -H "Content-Type: application/json" \
     -d '{"fitness_class": 1}'
   ```
   *Confirmed! Class is now full (`spots_available: 0`). Member credits balance is now 8.*

7. **Member 2 Joins Waitlist (Class Full)**:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/v1/bookings/ \
     -H "Authorization: Bearer $MEMBER2_TOKEN" \
     -H "Idempotency-Key: idem-key-wl-002" \
     -H "Content-Type: application/json" \
     -d '{"fitness_class": 1}'
   ```
   *Status: `WAITING_LIST`. Member 2 is NOT charged while on waitlist.*

8. **Member 1 Cancels Booking (Before Cutoff)**:
   ```bash
   curl -X DELETE http://127.0.0.1:8000/api/v1/bookings/1/ \
     -H "Authorization: Bearer $MEMBER1_TOKEN"
   ```
   *Automatic cascading actions:*
   - Member 1's credits are refunded in full (2 credits returned to pack, recorded in ledger).
   - Spot is released.
   - Longest-waiting waitlist member (Member 2) is auto-promoted to `CONFIRMED`, charged 2 credits, and spot is reserved.

9. **Audit Ledger & Historical Reconstruction**:
   ```bash
   # Current balance
   curl -X GET http://127.0.0.1:8000/api/v1/credit-packs/balance/ \
     -H "Authorization: Bearer $MEMBER1_TOKEN"

   # Reconstruct balance as of past date
   curl -X GET "http://127.0.0.1:8000/api/v1/credit-packs/balance/?as_of=2026-10-14T00:00:00Z" \
     -H "Authorization: Bearer $MEMBER1_TOKEN"

   # View transaction movements with causes
   curl -X GET http://127.0.0.1:8000/api/v1/credit-transactions/ \
     -H "Authorization: Bearer $MEMBER1_TOKEN"
   ```

---

## 7. API Reference

| Method | Endpoint | Description | Role / Auth |
|---|---|---|---|
| `POST` | `/api/v1/users/register/` | Register member (or staff if superadmin) | Public |
| `POST` | `/api/v1/users/login/` | Obtain JWT access/refresh tokens | Public |
| `POST` | `/api/v1/users/token/refresh/` | Refresh JWT access token | Public |
| `GET` | `/api/v1/users/me/` | Current user profile | Authenticated |
| `GET` | `/api/v1/users/` | List users (role filter supported) | Staff Only |
| `GET` | `/api/v1/studios/` | List studios | Authenticated |
| `POST` | `/api/v1/studios/` | Create studio (name, timezone, cutoff) | Staff Only |
| `GET` | `/api/v1/classes/` | Browse classes with `spots_available` (`?start_date=&end_date=`) | Authenticated |
| `POST` | `/api/v1/classes/` | Schedule fitness class | Staff Only |
| `GET` | `/api/v1/credit-packs/` | List credit packs | Member / Staff |
| `POST` | `/api/v1/credit-packs/` | Grant credit pack to member | Staff Only |
| `GET` | `/api/v1/credit-packs/balance/` | Balance breakdown (`?as_of=` for historical) | Member / Staff |
| `GET` | `/api/v1/credit-transactions/` | Ledger of all credit movements with cause | Member / Staff |
| `GET` | `/api/v1/bookings/` | List bookings (`?status=` supported, e.g. `WAITING_LIST`) | Member / Staff |
| `POST` | `/api/v1/bookings/` | Book class or join waitlist if full (`Idempotency-Key`) | Member |
| `DELETE`| `/api/v1/bookings/{id}/` | Cancel booking or leave waitlist (cutoff evaluation, refund, promo) | Member |

---

## 8. Deliverables & Artifacts

- **Postman Collection**: [`studio_postman_collection.json`](./studio_postman_collection.json) (Pre-configured end-to-end collection with environment variables and automated assertions).
- **Visual Postman Flow Blueprint**: [`studio_booking_flow.json`](./studio_booking_flow.json) and guide [`POSTMAN_FLOWS_GUIDE.md`](./POSTMAN_FLOWS_GUIDE.md) (Interactive visual node/canvas workflow definition).
- **OpenAPI 3.0 Specification**: [`openapi.yaml`](./openapi.yaml) (Full API schema specification).
- **Docker Stack**: [`Dockerfile`](./Dockerfile) and [`docker-compose.yml`](./docker-compose.yml).
- **CI / CD Pipeline**: [`.github/workflows/ci.yml`](./.github/workflows/ci.yml).
- **Configuration**: [`pyproject.toml`](./pyproject.toml) and [`requirements.txt`](./requirements.txt).
