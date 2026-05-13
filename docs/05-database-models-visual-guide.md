# 🎓 Database Models - Visual Learning Summary

## The Big Picture: What Problem Are We Solving?

```
❌ WITHOUT DATABASE MODELS:
┌─────────────────────────────────────────────────────────┐
│ Customer data scattered everywhere:                     │
│ - Excel spreadsheets                                    │
│ - Text files                                            │
│ - Hardcoded in code                                     │
│ - No relationships                                      │
│ - No validation                                         │
│ - Manual SQL queries                                    │
└─────────────────────────────────────────────────────────┘

✅ WITH DATABASE MODELS:
┌─────────────────────────────────────────────────────────┐
│ Structured, validated, relational data:                 │
│ - Type-safe Python classes                              │
│ - Automatic validation                                  │
│ - Relationships handled automatically                   │
│ - No SQL needed                                         │
│ - IDE autocomplete                                      │
│ - Easy to test                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Visual: The Three Models

```
┌──────────────────────────────────────────────────────────────┐
│                         TENANT                               │
│  "A customer/organization using our AI platform"             │
├──────────────────────────────────────────────────────────────┤
│  id: UUID                    [Auto-generated unique ID]      │
│  name: str                   [Company name, must be unique]  │
│  tier: SLATier               [GOLD/SILVER/BRONZE]            │
│  created_at: datetime        [When they signed up]           │
│  updated_at: datetime        [Last modification]             │
│  is_active: bool             [Can they use the service?]     │
│                                                              │
│  Relationships:                                              │
│  ├─ api_keys: list[APIKey]   [Their authentication keys]    │
│  └─ usage_records: list[...]  [Their AI request history]    │
└──────────────────────────────────────────────────────────────┘
                    │
                    │ One tenant has many...
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌─────────────────────┐  ┌─────────────────────┐
│      API KEY        │  │   USAGE RECORD      │
│  "Authentication"   │  │   "Billing data"    │
├─────────────────────┤  ├─────────────────────┤
│ id: UUID            │  │ id: UUID            │
│ tenant_id: UUID ────┼──┤ tenant_id: UUID     │
│ key_hash: str       │  │ request_id: str     │
│ key_prefix: str     │  │ prompt_tokens: int  │
│ name: str           │  │ completion_tokens   │
│ created_at          │  │ total_tokens: int   │
│ last_used_at        │  │ latency_ms: int     │
│ is_active: bool     │  │ model_name: str     │
│                     │  │ created_at          │
│ Relationship:       │  │                     │
│ └─ tenant: Tenant   │  │ Relationship:       │
└─────────────────────┘  │ └─ tenant: Tenant   │
                         └─────────────────────┘
```

---

## Visual: Real Data Example

```
TENANTS TABLE:
┌──────────────────────────────┬─────────────┬────────┬─────────────────────┬──────────┐
│ id                           │ name        │ tier   │ created_at          │ is_active│
├──────────────────────────────┼─────────────┼────────┼─────────────────────┼──────────┤
│ 550e8400-e29b-41d4-a716-...  │ Acme Corp   │ GOLD   │ 2026-01-15 10:30:00 │ true     │
│ 6ba7b810-9dad-11d1-80b4-...  │ Beta Inc    │ SILVER │ 2026-02-20 14:15:00 │ true     │
│ 7c9e6679-7425-40de-944b-...  │ Gamma LLC   │ BRONZE │ 2026-03-10 09:00:00 │ false    │
└──────────────────────────────┴─────────────┴────────┴─────────────────────┴──────────┘
                    ▲
                    │ Foreign Key Link
                    │
API_KEYS TABLE:
┌──────────────────────────────┬──────────────────────────────┬──────────────┬──────────────┐
│ id                           │ tenant_id                    │ key_hash     │ key_prefix   │
├──────────────────────────────┼──────────────────────────────┼──────────────┼──────────────┤
│ 123e4567-e89b-12d3-a456-...  │ 550e8400-e29b-41d4-a716-...  │ $2b$12$...  │ sk_live_abc  │
│ 234f5678-f90c-23e4-b567-...  │ 550e8400-e29b-41d4-a716-...  │ $2b$12$...  │ sk_test_xyz  │
│ 345g6789-g01d-34f5-c678-...  │ 6ba7b810-9dad-11d1-80b4-...  │ $2b$12$...  │ sk_live_def  │
└──────────────────────────────┴──────────────────────────────┴──────────────┴──────────────┘
                    ▲
                    │ Foreign Key Link
                    │
USAGE_RECORDS TABLE:
┌──────────────────────────────┬──────────────────────────────┬─────────────┬───────────────┬──────────────┐
│ id                           │ tenant_id                    │ request_id  │ prompt_tokens │ total_tokens │
├──────────────────────────────┼──────────────────────────────┼─────────────┼───────────────┼──────────────┤
│ 456h7890-h12e-45g6-d789-...  │ 550e8400-e29b-41d4-a716-...  │ req_001     │ 25            │ 175          │
│ 567i8901-i23f-56h7-e890-...  │ 550e8400-e29b-41d4-a716-...  │ req_002     │ 30            │ 200          │
│ 678j9012-j34g-67i8-f901-...  │ 6ba7b810-9dad-11d1-80b4-...  │ req_003     │ 15            │ 100          │
└──────────────────────────────┴──────────────────────────────┴─────────────┴───────────────┴──────────────┘
```

**Notice:** 
- Acme Corp (550e8400...) has 2 API keys and 2 usage records
- Beta Inc (6ba7b810...) has 1 API key and 1 usage record
- Gamma LLC (7c9e6679...) is inactive (is_active=false)

---

## Visual: How Relationships Work

### Python Code:
```python
tenant = db.query(Tenant).filter(Tenant.name == "Acme Corp").first()

# Access API keys through relationship
for key in tenant.api_keys:
    print(key.key_prefix)
```

### What SQLAlchemy Does Behind the Scenes:
```sql
-- First query: Get tenant
SELECT * FROM tenants WHERE name = 'Acme Corp';

-- Second query: Get API keys (automatic JOIN)
SELECT * FROM api_keys WHERE tenant_id = '550e8400-e29b-41d4-a716-...';
```

### Result:
```
tenant.api_keys = [
    <APIKey(prefix=sk_live_abc)>,
    <APIKey(prefix=sk_test_xyz)>
]
```

**You wrote Python, SQLAlchemy wrote SQL!** 🎉

---

## Visual: Cascade Delete

### Before Delete:
```
Tenant: Acme Corp (id: 550e8400...)
   │
   ├─── APIKey: sk_live_abc (id: 123e4567...)
   ├─── APIKey: sk_test_xyz (id: 234f5678...)
   │
   └─── UsageRecord: req_001 (id: 456h7890...)
        UsageRecord: req_002 (id: 567i8901...)
```

### Execute Delete:
```python
db.delete(tenant)
db.commit()
```

### After Delete:
```
(All gone! 💨)

Tenant: Acme Corp ❌ DELETED
   │
   ├─── APIKey: sk_live_abc ❌ DELETED (cascade)
   ├─── APIKey: sk_test_xyz ❌ DELETED (cascade)
   │
   └─── UsageRecord: req_001 ❌ DELETED (cascade)
        UsageRecord: req_002 ❌ DELETED (cascade)
```

**One delete = everything related is deleted!**

---

## Visual: Field Types Explained

```python
class Tenant(Base):
    # UUID - Unique identifier
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    #      ↑                          ↑                   ↑
    #      Type hint                  Database type       Constraint
    
    # String with max length
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    #                                  ↑            ↑            ↑
    #                                  Max 255 chars No duplicates Required
    
    # Enum - Limited choices
    tier: Mapped[SLATier] = mapped_column(Enum(SLATier), default=SLATier.BRONZE)
    #                                      ↑               ↑
    #                                      Only GOLD/      Default if
    #                                      SILVER/BRONZE   not specified
    
    # Timestamp with timezone
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    #                                             ↑                        ↑
    #                                             Store with timezone      Database sets value
    
    # Boolean flag
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    #                                        ↑        ↑
    #                                        True/False Default to True
```

---

## Visual: Complete CRUD Operations

### CREATE
```python
┌─────────────────────────────────────────────────────────┐
│ Python Code:                                            │
│                                                         │
│ tenant = Tenant(name="Acme", tier=SLATier.GOLD)        │
│ db.add(tenant)                                          │
│ db.commit()                                             │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ SQL Generated:                                          │
│                                                         │
│ INSERT INTO tenants (id, name, tier, created_at, ...)  │
│ VALUES ('550e8400-...', 'Acme', 'gold', NOW(), ...);   │
└─────────────────────────────────────────────────────────┘
```

### READ
```python
┌─────────────────────────────────────────────────────────┐
│ Python Code:                                            │
│                                                         │
│ tenant = db.query(Tenant).filter(                      │
│     Tenant.name == "Acme"                               │
│ ).first()                                               │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ SQL Generated:                                          │
│                                                         │
│ SELECT * FROM tenants WHERE name = 'Acme' LIMIT 1;     │
└─────────────────────────────────────────────────────────┘
```

### UPDATE
```python
┌─────────────────────────────────────────────────────────┐
│ Python Code:                                            │
│                                                         │
│ tenant.tier = SLATier.SILVER                            │
│ db.commit()                                             │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ SQL Generated:                                          │
│                                                         │
│ UPDATE tenants                                          │
│ SET tier = 'silver', updated_at = NOW()                │
│ WHERE id = '550e8400-...';                              │
└─────────────────────────────────────────────────────────┘
```

### DELETE
```python
┌─────────────────────────────────────────────────────────┐
│ Python Code:                                            │
│                                                         │
│ db.delete(tenant)                                       │
│ db.commit()                                             │
└─────────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────┐
│ SQL Generated:                                          │
│                                                         │
│ DELETE FROM usage_records WHERE tenant_id = '550e...'; │
│ DELETE FROM api_keys WHERE tenant_id = '550e...';      │
│ DELETE FROM tenants WHERE id = '550e8400-...';         │
└─────────────────────────────────────────────────────────┘
```

---

## Visual: Common Query Patterns

### Filter (WHERE clause)
```python
# Get Gold tier tenants
gold = db.query(Tenant).filter(Tenant.tier == SLATier.GOLD).all()

# SQL: SELECT * FROM tenants WHERE tier = 'gold';
```

### Order By
```python
# Sort by name
sorted_tenants = db.query(Tenant).order_by(Tenant.name).all()

# SQL: SELECT * FROM tenants ORDER BY name;
```

### Count
```python
# Count active tenants
count = db.query(Tenant).filter(Tenant.is_active == True).count()

# SQL: SELECT COUNT(*) FROM tenants WHERE is_active = true;
```

### Join (through relationships)
```python
# Get tenant with their API keys
tenant = db.query(Tenant).options(
    joinedload(Tenant.api_keys)
).first()

# SQL: SELECT * FROM tenants 
#      LEFT JOIN api_keys ON tenants.id = api_keys.tenant_id;
```

### Aggregate
```python
# Total tokens per tenant
from sqlalchemy import func

usage = db.query(
    Tenant.name,
    func.sum(UsageRecord.total_tokens)
).join(UsageRecord).group_by(Tenant.name).all()

# SQL: SELECT tenants.name, SUM(usage_records.total_tokens)
#      FROM tenants
#      JOIN usage_records ON tenants.id = usage_records.tenant_id
#      GROUP BY tenants.name;
```

---

## Memory Aid: The "Restaurant" Analogy

```
Database Models = Restaurant Management System

┌─────────────────────────────────────────────────────────┐
│ TENANT = Customer                                       │
│ - id = Customer ID card                                 │
│ - name = Customer name                                  │
│ - tier = Membership level (VIP/Regular/Basic)           │
│ - is_active = Are they still a member?                  │
└─────────────────────────────────────────────────────────┘
                    │
                    │ has many...
                    │
        ┌───────────┴───────────┐
        │                       │
        ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│ APIKEY = Badge  │    │ USAGE = Receipt │
│ - For entry     │    │ - What they ate │
│ - Can have many │    │ - How much      │
│ - Can revoke    │    │ - When          │
└─────────────────┘    └─────────────────┘
```

---

## Quick Decision Tree: Which Field Type?

```
Need to store...
│
├─ Unique ID? → UUID (primary_key=True)
│
├─ Text?
│  ├─ Short (< 255 chars)? → String(255)
│  └─ Long? → Text
│
├─ Number?
│  ├─ Whole number? → Integer
│  └─ Decimal? → Float or Numeric
│
├─ True/False? → Boolean
│
├─ Date/Time? → DateTime(timezone=True)
│
├─ Limited choices? → Enum
│
└─ Link to another table? → ForeignKey
```

---

## Summary: What You've Mastered

✅ **Concepts:**
- Database models = Python classes that map to tables
- ORM = Write Python, get SQL automatically
- Relationships = Navigate between related data
- Migrations = Version control for database schema

✅ **Skills:**
- Create models with proper types
- Define relationships (one-to-many)
- Use foreign keys and constraints
- Query data without writing SQL
- Update and delete records safely

✅ **Best Practices:**
- Use UUIDs for primary keys
- Hash sensitive data (API keys)
- Use enums for limited choices
- Add timestamps (created_at, updated_at)
- Implement soft deletes (is_active flag)
- Use cascade delete for cleanup

---

## What's Next?

Now that you understand database models, you're ready to:

1. **Run the tutorial:**
   ```bash
   python scripts/tutorial_models.py
   ```

2. **Build the API Gateway:**
   - Use Tenant model for authentication
   - Use APIKey model to validate requests
   - Use UsageRecord model for billing

3. **Experiment:**
   - Add new fields to models
   - Create new relationships
   - Write complex queries

---

**You're now a database models expert! 🎓**

Ready to build the API Gateway? Let me know! 🚀
