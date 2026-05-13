"""Interactive tutorial: Working with database models.

Run this script to learn how to use SQLAlchemy models!

Prerequisites:
1. Start PostgreSQL: docker-compose up -d postgres
2. Run migrations: alembic upgrade head
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
from uuid import uuid4

from src.shared.database import get_db_context
from src.shared.models import Tenant, APIKey, UsageRecord
from src.shared.types import SLATier


def lesson_1_create_tenant():
    """Lesson 1: Creating a tenant."""
    print("\n" + "="*60)
    print("LESSON 1: Creating a Tenant")
    print("="*60)

    with get_db_context() as db:
        # Create a new tenant
        tenant = Tenant(
            name="Tutorial Corp",
            tier=SLATier.GOLD
        )

        print(f"\n📝 Created tenant object: {tenant}")
        print(f"   ID: {tenant.id}")
        print(f"   Name: {tenant.name}")
        print(f"   Tier: {tenant.tier}")
        print(f"   Created at: {tenant.created_at}")

        # Save to database
        db.add(tenant)
        db.commit()

        print("\n✅ Tenant saved to database!")

        return tenant.id


def lesson_2_create_api_keys(tenant_id):
    """Lesson 2: Creating API keys for a tenant."""
    print("\n" + "="*60)
    print("LESSON 2: Creating API Keys")
    print("="*60)

    with get_db_context() as db:
        # Create multiple API keys
        keys = [
            APIKey(
                tenant_id=tenant_id,
                key_hash="hash_production_key_12345",
                key_prefix="sk_live_abc",
                name="Production Key"
            ),
            APIKey(
                tenant_id=tenant_id,
                key_hash="hash_testing_key_67890",
                key_prefix="sk_test_xyz",
                name="Testing Key"
            )
        ]

        db.add_all(keys)
        db.commit()

        print(f"\n✅ Created {len(keys)} API keys:")
        for key in keys:
            print(f"   - {key.name}: {key.key_prefix}...")

        return [key.id for key in keys]


def lesson_3_relationships(tenant_id):
    """Lesson 3: Using relationships to navigate between models."""
    print("\n" + "="*60)
    print("LESSON 3: Relationships (The Magic!)")
    print("="*60)

    with get_db_context() as db:
        # Load tenant
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

        print(f"\n📊 Tenant: {tenant.name}")

        # Access API keys through relationship
        print(f"\n🔑 API Keys (via relationship):")
        for key in tenant.api_keys:
            print(f"   - {key.name}: {key.key_prefix}...")

        # Go backwards: from key to tenant
        if tenant.api_keys:
            first_key = tenant.api_keys[0]
            print(f"\n🔄 Reverse relationship:")
            print(f"   Key '{first_key.name}' belongs to tenant '{first_key.tenant.name}'")


def lesson_4_create_usage_records(tenant_id):
    """Lesson 4: Recording usage for billing."""
    print("\n" + "="*60)
    print("LESSON 4: Usage Records (Billing)")
    print("="*60)

    with get_db_context() as db:
        # Simulate 5 AI requests
        usage_records = []
        for i in range(5):
            usage = UsageRecord(
                tenant_id=tenant_id,
                request_id=f"req_{uuid4().hex[:8]}",
                prompt_tokens=10 + i * 5,
                completion_tokens=50 + i * 10,
                total_tokens=60 + i * 15,
                latency_ms=200 + i * 50,
                model_name="TinyLlama-1.1B"
            )
            usage_records.append(usage)

        db.add_all(usage_records)
        db.commit()

        print(f"\n✅ Created {len(usage_records)} usage records")

        # Calculate total usage
        total_tokens = sum(u.total_tokens for u in usage_records)
        avg_latency = sum(u.latency_ms for u in usage_records) / len(usage_records)

        print(f"\n📊 Usage Summary:")
        print(f"   Total tokens: {total_tokens}")
        print(f"   Average latency: {avg_latency:.0f}ms")
        print(f"   Estimated cost: ${total_tokens * 0.002 / 1000:.6f}")


def lesson_5_queries():
    """Lesson 5: Querying the database."""
    print("\n" + "="*60)
    print("LESSON 5: Querying Data")
    print("="*60)

    with get_db_context() as db:
        # Query 1: Get all Gold tier tenants
        print("\n🥇 Gold Tier Tenants:")
        gold_tenants = db.query(Tenant).filter(Tenant.tier == SLATier.GOLD).all()
        for tenant in gold_tenants:
            print(f"   - {tenant.name}")

        # Query 2: Count API keys per tenant
        print("\n🔑 API Keys per Tenant:")
        tenants = db.query(Tenant).all()
        for tenant in tenants:
            key_count = len(tenant.api_keys)
            print(f"   - {tenant.name}: {key_count} keys")

        # Query 3: Find recently used API keys
        print("\n⏰ Recently Used API Keys:")
        recent_keys = db.query(APIKey).filter(
            APIKey.last_used_at.isnot(None)
        ).order_by(APIKey.last_used_at.desc()).limit(5).all()

        if recent_keys:
            for key in recent_keys:
                print(f"   - {key.name}: {key.last_used_at}")
        else:
            print("   (No keys have been used yet)")

        # Query 4: Total usage by tenant
        print("\n📊 Total Usage by Tenant:")
        from sqlalchemy import func
        usage_by_tenant = db.query(
            Tenant.name,
            func.count(UsageRecord.id).label('request_count'),
            func.sum(UsageRecord.total_tokens).label('total_tokens')
        ).join(UsageRecord).group_by(Tenant.name).all()

        for name, count, tokens in usage_by_tenant:
            print(f"   - {name}: {count} requests, {tokens} tokens")


def lesson_6_updates():
    """Lesson 6: Updating records."""
    print("\n" + "="*60)
    print("LESSON 6: Updating Records")
    print("="*60)

    with get_db_context() as db:
        # Find Tutorial Corp
        tenant = db.query(Tenant).filter(Tenant.name == "Tutorial Corp").first()

        if tenant:
            print(f"\n📝 Before update:")
            print(f"   Tier: {tenant.tier}")
            print(f"   Updated at: {tenant.updated_at}")

            # Update tier
            tenant.tier = SLATier.SILVER
            db.commit()

            # Refresh to get updated timestamp
            db.refresh(tenant)

            print(f"\n✅ After update:")
            print(f"   Tier: {tenant.tier}")
            print(f"   Updated at: {tenant.updated_at}")
            print(f"   (Notice updated_at changed automatically!)")


def lesson_7_cascade_delete():
    """Lesson 7: Cascade delete (cleanup)."""
    print("\n" + "="*60)
    print("LESSON 7: Cascade Delete")
    print("="*60)

    with get_db_context() as db:
        # Find Tutorial Corp
        tenant = db.query(Tenant).filter(Tenant.name == "Tutorial Corp").first()

        if tenant:
            key_count = len(tenant.api_keys)
            usage_count = len(tenant.usage_records)

            print(f"\n📊 Before delete:")
            print(f"   Tenant: {tenant.name}")
            print(f"   API Keys: {key_count}")
            print(f"   Usage Records: {usage_count}")

            # Delete tenant
            db.delete(tenant)
            db.commit()

            print(f"\n✅ Tenant deleted!")
            print(f"   All {key_count} API keys automatically deleted (cascade)")
            print(f"   All {usage_count} usage records automatically deleted (cascade)")


def main():
    """Run all lessons."""
    print("\n" + "🎓"*30)
    print("DATABASE MODELS TUTORIAL")
    print("🎓"*30)

    try:
        # Run lessons in order
        tenant_id = lesson_1_create_tenant()
        lesson_2_create_api_keys(tenant_id)
        lesson_3_relationships(tenant_id)
        lesson_4_create_usage_records(tenant_id)
        lesson_5_queries()
        lesson_6_updates()
        lesson_7_cascade_delete()

        print("\n" + "="*60)
        print("🎉 TUTORIAL COMPLETE!")
        print("="*60)
        print("\nYou've learned:")
        print("  ✅ Creating records")
        print("  ✅ Relationships (one-to-many)")
        print("  ✅ Querying data")
        print("  ✅ Updating records")
        print("  ✅ Cascade deletes")
        print("\nNext: Try modifying this script to experiment!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure:")
        print("  1. PostgreSQL is running: docker-compose up -d postgres")
        print("  2. Migrations are applied: alembic upgrade head")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
