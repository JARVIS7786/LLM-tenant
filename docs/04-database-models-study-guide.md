# 📚 Database Models - Complete Study Guide

## Quick Reference Card

### The Three Models

```python
Tenant          APIKey              UsageRecord
├─ id           ├─ id               ├─ id
├─ name         ├─ tenant_id (FK)   ├─ tenant_id (FK)
├─ tier         ├─ key_hash         ├─ request_id
├─ created_at   ├─ key_prefix       ├─ prompt_tokens
├─ updated_at   ├─ name             ├─ completion_tokens
├─ is_active    ├─ created_at       ├─ total_tokens
│               ├─ last_used_at     ├─ latency_ms
└─ Relationships├─ is_active        ├─ model_name
   ├─ api_keys  │                   ├─ created_at
   └─ usage_records └─ Relationship  │
                   └─ tenant         └─ Relationship
                                        └─ tenant
```

---

## Key Concepts Cheat Sheet

### 1. Primary Key
```python
id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
```
- **What:** Unique identifier for each row
- **Why UUID:** Globally unique, unpredictable, distributed-system friendly
- **Auto-generated:** Don't need to set it manually

### 2. Foreign Key
```python
tenant_id: Mapped[UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("tenants.id", ondelete="CASCADE"),
    nullable=False
)
```
- **What:** Link to another table
- **CASCADE:** If parent deleted, children deleted too
- **Enforced:** Database prevents orphaned records

### 3. Unique Constraint
```python
name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
```
- **What:** No two rows can have same value
- **Example:** Two tenants can't have same name
- **Database enforced:** Raises error on duplicate

### 4. Nullable vs Not Nullable
```python
# Required field
name: Mapped[str] = mapped_column(String(255), nullable=False)

# Optional field
name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
```
- **nullable=False:** Must provide value
- **nullable=True:** Can be None/NULL

### 5. Default Values
```python
# Python default (set when object created)
tier: Mapped[SLATier] = mapped_column(Enum(SLATier), default=SLATier.BRONZE)

# Database default (set when row inserted)
created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```
- **default:** Python sets it
- **server_default:** Database sets it

### 6. Enum (Limited Choices)
```python
tier: Mapped[SLATier] = mapped_column(Enum(SLATier, name="sla_tier"))
```
- **What:** Field with predefined options
- **Example:** GOLD, SILVER, BRONZE (can't be "PLATINUM")
- **Type safe:** IDE autocomplete, prevents typos

### 7. Relationships (One-to-Many)
```python
# In Tenant model
api_keys: Mapped[list["APIKey"]] = relationship(
    "APIKey",
    back_populates="tenant",
    cascade="all, delete-orphan"
)

# In APIKey model
tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="api_keys")
```
- **What:** Navigate between related tables
- **Usage:** `tenant.api_keys` or `api_key.tenant`
- **Cascade:** Delete children when parent deleted

### 8. Timestamps
```python
created_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now()
)

updated_at: Mapped[datetime] = mapped_column(
    DateTime(timezone=True),
    server_default=func.now(),
    onupdate=func.now()  # Auto-updates on change!
)
```
- **timezone=True:** Store with timezone (always UTC)
- **server_default:** Database sets on INSERT
- **onupdate:** Database updates on UPDATE

---

## Common Operations

### Creating Records

```python
from src.shared.database import get_db_context
from src.shared.models import Tenant
from src.shared.types import SLATier

with get_db_context() as db:
    # Create tenant
    tenant = Tenant(
        name="Acme Corp",
        tier=SLATier.GOLD
    )
    
    # Save to database
    db.add(tenant)
    db.commit()
    
    # Now tenant.id is set!
    print(tenant.id)
```

### Querying Records

```python
with get_db_context() as db:
    # Get one tenant by ID
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    
    # Get all Gold tenants
    gold_tenants = db.query(Tenant).filter(Tenant.tier == SLATier.GOLD).all()
    
    # Get active tenants only
    active = db.query(Tenant).filter(Tenant.is_active == True).all()
    
    # Count tenants
    count = db.query(Tenant).count()
    
    # Order by name
    sorted_tenants = db.query(Tenant).order_by(Tenant.name).all()
```

### Updating Records

```python
with get_db_context() as db:
    tenant = db.query(Tenant).filter(Tenant.name == "Acme Corp").first()
    
    # Update field
    tenant.tier = SLATier.SILVER
    
    # Save changes
    db.commit()
    
    # updated_at is automatically updated!
```

### Deleting Records

```python
with get_db_context() as db:
    tenant = db.query(Tenant).filter(Tenant.name == "Acme Corp").first()
    
    # Delete tenant (and all API keys/usage records due to cascade)
    db.delete(tenant)
    db.commit()
```

### Using Relationships

```python
with get_db_context() as db:
    tenant = db.query(Tenant).filter(Tenant.name == "Acme Corp").first()
    
    # Access API keys through relationship
    for key in tenant.api_keys:
        print(f"Key: {key.key_prefix}")
    
    # Access usage records
    total_tokens = sum(record.total_tokens for record in tenant.usage_records)
    print(f"Total usage: {total_tokens} tokens")
    
    # Go backwards: from key to tenant
    first_key = tenant.api_keys[0]
    print(f"This key belongs to: {first_key.tenant.name}")
```

---

## Database Schema Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         TENANTS                             │
├─────────────────────────────────────────────────────────────┤
│ id (UUID, PK)                                               │
│ name (VARCHAR, UNIQUE)                                      │
│ tier (ENUM: gold/silver/bronze)                             │
│ created_at (TIMESTAMP)                                      │
│ updated_at (TIMESTAMP)                                      │
│ is_active (BOOLEAN)                                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ One-to-Many
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌─────────────────────┐   ┌─────────────────────┐
│     API_KEYS        │   │   USAGE_RECORDS     │
├─────────────────────┤   ├─────────────────────┤
│ id (UUID, PK)       │   │ id (UUID, PK)       │
│ tenant_id (UUID, FK)│   │ tenant_id (UUID, FK)│
│ key_hash (VARCHAR)  │   │ request_id (VARCHAR)│
│ key_prefix (VARCHAR)│   │ prompt_tokens (INT) │
│ name (VARCHAR)      │   │ completion_tokens   │
│ created_at          │   │ total_tokens (INT)  │
│ last_used_at        │   │ latency_ms (INT)    │
│ is_active (BOOLEAN) │   │ model_name (VARCHAR)│
└─────────────────────┘   │ created_at          │
                          └─────────────────────┘
```

---

## Real-World Example: Complete Flow

### Scenario: New customer signs up

```python
from src.shared.database import get_db_context
from src.shared.models import Tenant, APIKey
from src.shared.types import SLATier
import bcrypt

with get_db_context() as db:
    # 1. Create tenant
    tenant = Tenant(
        name="Startup Inc",
        tier=SLATier.BRONZE  # Free tier
    )
    db.add(tenant)
    db.flush()  # Get tenant.id without committing
    
    # 2. Generate API key
    raw_key = f"sk_live_{uuid4().hex}"
    key_hash = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()
    
    api_key = APIKey(
        tenant_id=tenant.id,
        key_hash=key_hash,
        key_prefix=raw_key[:11],  # "sk_live_abc"
        name="Default Key"
    )
    db.add(api_key)
    
    # 3. Commit everything
    db.commit()
    
    # 4. Show user their key (ONLY ONCE!)
    print(f"Welcome to our platform!")
    print(f"Your API key: {raw_key}")
    print(f"Save it now - we can't show it again!")
```

### Scenario: User makes AI request

```python
from src.shared.models import UsageRecord

with get_db_context() as db:
    # After processing LLM request
    usage = UsageRecord(
        tenant_id=tenant.id,
        request_id="req_abc123",
        prompt_tokens=25,
        completion_tokens=150,
        total_tokens=175,
        latency_ms=450,
        model_name="TinyLlama-1.1B"
    )
    db.add(usage)
    db.commit()
```

### Scenario: Monthly billing

```python
from sqlalchemy import func
from datetime import datetime, timedelta

with get_db_context() as db:
    # Calculate usage for last month
    start_date = datetime.utcnow() - timedelta(days=30)
    
    usage_by_tenant = db.query(
        Tenant.name,
        Tenant.tier,
        func.count(UsageRecord.id).label('request_count'),
        func.sum(UsageRecord.total_tokens).label('total_tokens')
    ).join(UsageRecord).filter(
        UsageRecord.created_at >= start_date
    ).group_by(Tenant.id, Tenant.name, Tenant.tier).all()
    
    # Generate bills
    for name, tier, count, tokens in usage_by_tenant:
        # Pricing: $0.002 per 1K tokens
        cost = (tokens / 1000) * 0.002
        
        print(f"\n{name} ({tier.value}):")
        print(f"  Requests: {count}")
        print(f"  Tokens: {tokens:,}")
        print(f"  Cost: ${cost:.2f}")
```

---

## Common Mistakes & Solutions

### ❌ Mistake 1: Forgetting to commit

```python
# Wrong
tenant = Tenant(name="Acme")
db.add(tenant)
# Forgot db.commit()!
```

```python
# Right
tenant = Tenant(name="Acme")
db.add(tenant)
db.commit()  # ✅
```

### ❌ Mistake 2: Using wrong session

```python
# Wrong
tenant = Tenant(name="Acme")
db1.add(tenant)
db1.commit()

# Later, in different session
db2.query(Tenant).filter(Tenant.id == tenant.id)  # Error!
```

```python
# Right - use same session or reload
with get_db_context() as db:
    tenant = Tenant(name="Acme")
    db.add(tenant)
    db.commit()
    
    # Use within same session
    loaded = db.query(Tenant).filter(Tenant.id == tenant.id).first()
```

### ❌ Mistake 3: Not handling duplicates

```python
# Wrong
tenant1 = Tenant(name="Acme")
tenant2 = Tenant(name="Acme")  # Same name!
db.add_all([tenant1, tenant2])
db.commit()  # Error: unique constraint violation
```

```python
# Right - check first
existing = db.query(Tenant).filter(Tenant.name == "Acme").first()
if not existing:
    tenant = Tenant(name="Acme")
    db.add(tenant)
    db.commit()
```

### ❌ Mistake 4: Forgetting foreign key

```python
# Wrong
api_key = APIKey(
    key_hash="hash",
    key_prefix="sk_"
    # Missing tenant_id!
)
db.add(api_key)
db.commit()  # Error: nullable=False
```

```python
# Right
api_key = APIKey(
    tenant_id=tenant.id,  # ✅
    key_hash="hash",
    key_prefix="sk_"
)
```

---

## Testing Your Knowledge

### Quiz 1: What happens here?

```python
tenant = Tenant(name="Test Corp", tier=SLATier.GOLD)
print(tenant.id)
```

<details>
<summary>Answer</summary>

The UUID is generated immediately when the object is created (because of `default=uuid4`), even before saving to database. So this prints a UUID like `550e8400-e29b-41d4-a716-446655440000`.

</details>

### Quiz 2: What happens here?

```python
tenant = Tenant(name="Test Corp")
db.add(tenant)
db.delete(tenant)
db.commit()
```

<details>
<summary>Answer</summary>

Nothing is saved to the database! The tenant is added then deleted before commit, so the operations cancel out. The database is unchanged.

</details>

### Quiz 3: What happens here?

```python
tenant = Tenant(name="Test Corp")
db.add(tenant)
db.commit()

db.delete(tenant)
# Forgot to commit!

# Later...
loaded = db.query(Tenant).filter(Tenant.name == "Test Corp").first()
print(loaded)
```

<details>
<summary>Answer</summary>

The tenant still exists in the database! The delete wasn't committed, so it was rolled back. `loaded` will be the tenant object.

</details>

### Quiz 4: What happens here?

```python
tenant = Tenant(name="Test Corp")
db.add(tenant)
db.commit()

# Delete tenant
db.delete(tenant)
db.commit()

# What about the API keys?
```

<details>
<summary>Answer</summary>

All API keys for this tenant are automatically deleted too! This is because of `cascade="all, delete-orphan"` in the relationship definition.

</details>

---

## Next Steps

Now that you understand database models, you can:

1. **Run the tutorial script:**
   ```bash
   # Start PostgreSQL
   docker-compose up -d postgres
   
   # Run migrations
   alembic upgrade head
   
   # Run tutorial
   python scripts/tutorial_models.py
   ```

2. **Experiment:**
   - Add a new field to Tenant (e.g., `email`)
   - Create a migration for it
   - Query tenants by email

3. **Build the API Gateway:**
   - Use these models to authenticate users
   - Record usage after each request
   - Query billing data

---

## Summary

**You've learned:**
- ✅ What database models are (Python classes → database tables)
- ✅ Primary keys (unique identifiers)
- ✅ Foreign keys (relationships between tables)
- ✅ Constraints (unique, nullable, defaults)
- ✅ Relationships (one-to-many, cascade delete)
- ✅ Timestamps (created_at, updated_at)
- ✅ CRUD operations (Create, Read, Update, Delete)
- ✅ Querying with filters and joins

**Key takeaway:**
> SQLAlchemy ORM lets you work with database tables as if they were Python objects. No SQL required!

---

**Ready to continue?** Next we'll build the API Gateway that uses these models! 🚀
