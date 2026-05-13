# Database Setup - Learning Guide

## What We Just Built

We created a complete database layer using SQLAlchemy ORM and Alembic migrations. Here's what each component does:

---

## 1. SQLAlchemy Models (`src/shared/models.py`)

### What is an ORM?
**ORM (Object-Relational Mapping)** lets you work with database tables as Python classes:
- **Without ORM**: `cursor.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,))`
- **With ORM**: `db.query(Tenant).filter(Tenant.id == tenant_id).first()`

### Our Models

#### **Tenant Model**
Represents a customer/organization:
```python
tenant = Tenant(name="Acme Corp", tier=SLATier.GOLD)
db.add(tenant)
db.commit()
```

**Key Features:**
- `UUID` primary key (better than auto-increment for distributed systems)
- `tier` enum (Gold/Silver/Bronze) for SLA-based routing
- `created_at`/`updated_at` timestamps (auto-managed)
- Relationships to `api_keys` and `usage_records`

#### **APIKey Model**
Authentication credentials:
```python
api_key = APIKey(
    tenant_id=tenant.id,
    key_hash=hash_key(raw_key),  # Never store raw keys!
    key_prefix="sk_live_abc"  # For display/logging
)
```

**Security Pattern:**
- Store `key_hash` (bcrypt/argon2), never the raw key
- Store `key_prefix` for user-friendly display
- Track `last_used_at` for security auditing

#### **UsageRecord Model**
Billing and analytics:
```python
usage = UsageRecord(
    tenant_id=tenant.id,
    request_id="req_123",
    prompt_tokens=50,
    completion_tokens=100,
    total_tokens=150,
    latency_ms=234
)
```

**Why track this?**
- **Billing**: Charge per token (like OpenAI)
- **Analytics**: Identify slow requests, popular models
- **Quotas**: Enforce usage limits per tier

---

## 2. Relationships (Foreign Keys)

```python
# One-to-Many: One tenant has many API keys
tenant.api_keys  # List of APIKey objects
api_key.tenant   # Parent Tenant object

# Cascade delete: When tenant is deleted, all their API keys are auto-deleted
cascade="all, delete-orphan"
```

**Why relationships matter:**
- Type-safe navigation: `tenant.api_keys[0].key_prefix`
- Automatic JOIN queries
- Referential integrity (can't create API key for non-existent tenant)

---

## 3. Database Connection (`src/shared/database.py`)

### Connection Pooling
```python
engine = create_engine(
    settings.database_url,
    pool_size=10,      # Keep 10 connections ready
    max_overflow=20,   # Allow 20 more if needed
    pool_pre_ping=True # Check connection health before using
)
```

**Why pooling?**
- Creating connections is slow (~50ms)
- Reusing connections is fast (~0.1ms)
- Prevents "too many connections" errors

### Session Management

**Option 1: FastAPI Dependency (Recommended)**
```python
@app.get("/tenants")
def get_tenants(db: Session = Depends(get_db)):
    return db.query(Tenant).all()
```
- Auto-closes session after request
- Handles errors gracefully

**Option 2: Context Manager**
```python
with get_db_context() as db:
    tenant = db.query(Tenant).first()
    # Auto-commits on success, rolls back on error
```

---

## 4. Alembic Migrations

### Why Migrations?

**Without migrations:**
- Change model → manually write SQL → hope you didn't miss anything
- No version history
- Can't roll back changes

**With migrations:**
- Change model → `alembic revision --autogenerate` → review SQL → apply
- Git-like history of schema changes
- Can roll back: `alembic downgrade -1`

### Migration Workflow

```bash
# 1. Change your models in src/shared/models.py
# 2. Generate migration
alembic revision --autogenerate -m "Add email to tenants"

# 3. Review generated file in alembic/versions/
# 4. Apply migration
alembic upgrade head

# 5. Rollback if needed
alembic downgrade -1
```

### Our First Migration (`001_initial_schema.py`)

Creates:
- `sla_tier` enum type
- `tenants`, `api_keys`, `usage_records` tables
- Indexes for fast queries
- Trigger to auto-update `updated_at`

---

## 5. Key Concepts Explained

### UUIDs vs Auto-Increment IDs

**Auto-increment (1, 2, 3...):**
- ✓ Simple, small (4 bytes)
- ✗ Predictable (security risk)
- ✗ Conflicts in distributed systems

**UUIDs (550e8400-e29b-41d4-a716-446655440000):**
- ✓ Globally unique (no conflicts)
- ✓ Unpredictable (better security)
- ✗ Larger (16 bytes)
- ✓ Can generate client-side

### Indexes

```python
op.create_index('idx_api_keys_key_hash', 'api_keys', ['key_hash'])
```

**Without index:**
- Query: `SELECT * FROM api_keys WHERE key_hash = 'abc'`
- Database scans ALL rows (slow for 1M+ rows)

**With index:**
- Database uses B-tree lookup (fast even for billions of rows)
- Trade-off: Slower writes, faster reads

### Timestamps with Timezone

```python
created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),  # Stores UTC, converts to local
    server_default=func.now()  # Database sets value
)
```

**Why timezone-aware?**
- Users in different timezones
- Daylight saving time handling
- Always store UTC, display in user's timezone

---

## 6. Database Management Script

We created `scripts/manage_db.py` for common tasks:

```bash
# Test connection
python scripts/manage_db.py check-connection

# Create tables (testing only)
python scripts/manage_db.py create-tables

# Seed sample data
python scripts/manage_db.py seed-data

# List all tenants
python scripts/manage_db.py list-tenants

# Reset database (DESTRUCTIVE!)
python scripts/manage_db.py reset
```

---

## 7. Next Steps: Using the Database

### In API Gateway (coming next):
```python
from fastapi import Depends
from src.shared import get_db, Tenant

@app.post("/tenants")
def create_tenant(name: str, tier: str, db: Session = Depends(get_db)):
    tenant = Tenant(name=name, tier=tier)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)  # Get auto-generated ID
    return tenant
```

### In Worker Manager:
```python
from src.shared import get_db_context, UsageRecord

with get_db_context() as db:
    usage = UsageRecord(
        tenant_id=tenant_id,
        request_id=request_id,
        total_tokens=tokens,
        latency_ms=latency
    )
    db.add(usage)
    # Auto-commits when context exits
```

---

## 8. Try It Out (Once Docker is Running)

```bash
# 1. Start PostgreSQL
docker-compose up -d postgres

# 2. Run migrations
alembic upgrade head

# 3. Seed data
python scripts/manage_db.py seed-data

# 4. List tenants
python scripts/manage_db.py list-tenants

# 5. Connect with psql
docker-compose exec postgres psql -U postgres -d mtai_platform
```

---

## Common Patterns

### Query Examples
```python
# Get all gold tier tenants
gold_tenants = db.query(Tenant).filter(Tenant.tier == SLATier.GOLD).all()

# Get tenant with API keys (JOIN)
tenant = db.query(Tenant).options(joinedload(Tenant.api_keys)).first()

# Count usage by tenant
from sqlalchemy import func
usage_count = db.query(
    Tenant.name,
    func.count(UsageRecord.id)
).join(UsageRecord).group_by(Tenant.name).all()
```

### Transaction Example
```python
try:
    tenant = Tenant(name="New Corp")
    db.add(tenant)
    db.flush()  # Get ID without committing
    
    api_key = APIKey(tenant_id=tenant.id, key_hash="...")
    db.add(api_key)
    
    db.commit()  # Both saved atomically
except Exception:
    db.rollback()  # Neither saved
    raise
```

---

## Architecture Recap

```
Application Code
       ↓
SQLAlchemy ORM (models.py)
       ↓
SQLAlchemy Core (SQL generation)
       ↓
psycopg (PostgreSQL driver)
       ↓
PostgreSQL Database
```

**Benefits:**
- Write Python, not SQL
- Type safety and IDE autocomplete
- Database-agnostic (can switch to MySQL/SQLite)
- Automatic query optimization
