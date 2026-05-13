"""Database management CLI script."""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from sqlalchemy import text

from src.shared.database import engine, init_db, get_db_context
from src.shared.models import Tenant, APIKey
from src.shared.types import SLATier


@click.group()
def cli():
    """Database management commands."""
    pass


@cli.command()
def create_tables():
    """Create all database tables (for testing only - use migrations in production)."""
    click.echo("Creating database tables...")
    init_db()
    click.echo("✓ Tables created successfully!")


@cli.command()
def check_connection():
    """Test database connection."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            click.echo(f"✓ Connected to PostgreSQL!")
            click.echo(f"  Version: {version}")
    except Exception as e:
        click.echo(f"✗ Connection failed: {e}", err=True)
        sys.exit(1)


@cli.command()
def seed_data():
    """Seed database with sample data for testing."""
    click.echo("Seeding database with sample data...")

    with get_db_context() as db:
        # Check if data already exists
        if db.query(Tenant).count() > 0:
            click.echo("⚠ Database already has data. Skipping seed.")
            return

        # Create sample tenants
        tenants = [
            Tenant(name="Acme Corp", tier=SLATier.GOLD, is_active=True),
            Tenant(name="Beta Inc", tier=SLATier.SILVER, is_active=True),
            Tenant(name="Gamma LLC", tier=SLATier.BRONZE, is_active=True),
        ]
        db.add_all(tenants)
        db.flush()  # Get IDs without committing

        click.echo(f"✓ Created {len(tenants)} tenants")

        # Note: API keys would be created through the API with proper hashing
        click.echo("✓ Database seeded successfully!")


@cli.command()
def list_tenants():
    """List all tenants in the database."""
    with get_db_context() as db:
        tenants = db.query(Tenant).all()

        if not tenants:
            click.echo("No tenants found.")
            return

        click.echo(f"\nFound {len(tenants)} tenant(s):\n")
        for tenant in tenants:
            status = "✓" if tenant.is_active else "✗"
            click.echo(f"  {status} {tenant.name}")
            click.echo(f"    ID: {tenant.id}")
            click.echo(f"    Tier: {tenant.tier.value}")
            click.echo(f"    Created: {tenant.created_at}")
            click.echo()


@cli.command()
def reset():
    """Drop all tables and recreate them (DESTRUCTIVE!)."""
    if not click.confirm("⚠ This will DELETE ALL DATA. Continue?"):
        click.echo("Aborted.")
        return

    click.echo("Dropping all tables...")
    from src.shared.models import Base
    Base.metadata.drop_all(bind=engine)

    click.echo("Recreating tables...")
    init_db()

    click.echo("✓ Database reset complete!")


if __name__ == "__main__":
    cli()
