#!/usr/bin/env python3
"""
Master Database Initialization Script

Initializes the complete database with all schemas in proper order.
Supports migrations and fresh installs.

Usage:
    python init_db.py                  # Initialize/update database
    python init_db.py --fresh          # Drop and recreate (with backup)
    python init_db.py --db mydb.db     # Use different database
    python init_db.py --list           # List all tables
"""

import sqlite3
import sys
import os
from pathlib import Path
from datetime import datetime
import shutil


class DatabaseInitializer:
    """Manages database initialization and migrations"""
    
    def __init__(self, db_path: str = "tfso-data.db"):
        self.db_path = db_path
        
        # Resolve paths relative to this script
        script_dir = Path(__file__).resolve().parent
        self.db_dir = script_dir
        self.schemas_dir = script_dir / "schemas"
        self.migrations_dir = script_dir / "migrations"
        
        # Debug: print paths
        if not self.schemas_dir.exists():
            print(f"\n⚠️  Warning: schemas directory not found at {self.schemas_dir}")
            print(f"   Script location: {script_dir}")
            print(f"   Please ensure you're running from project root or database/ folder")
        
    def backup_database(self):
        """Create timestamped backup"""
        if not os.path.exists(self.db_path):
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.db_path}.backup_{timestamp}"
        
        print(f"📦 Creating backup: {backup_path}")
        shutil.copy2(self.db_path, backup_path)
        return backup_path
    
    def run_sql_file(self, conn: sqlite3.Connection, filepath: Path):
        """Execute SQL from a file"""
        print(f"  📄 Running {filepath.name}...")
        
        if not filepath.exists():
            print(f"    ⚠️  File not found: {filepath}")
            return False
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                sql = f.read()
            
            # Use executescript which handles multiple statements properly
            conn.executescript(sql)
            conn.commit()
            
            # Count statements for reporting
            statements = len([s for s in sql.split(';') if s.strip() and not s.strip().startswith('--')])
            print(f"    ✓ Executed {statements} statements")
            return True
            
        except Exception as e:
            print(f"    ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def init_core_schema(self, conn: sqlite3.Connection):
        """Initialize core tables"""
        print("\n1️⃣  Core Schema (Invoices, Customers, Transactions)")
        schema_file = self.schemas_dir / "core_schema.sql"
        return self.run_sql_file(conn, schema_file)
    
    def init_metrics_schema(self, conn: sqlite3.Connection):
        """Initialize dashboard metrics tables"""
        print("\n2️⃣  Dashboard Metrics Schema")
        schema_file = self.schemas_dir / "metrics_schema.sql"
        return self.run_sql_file(conn, schema_file)
    
    def init_ml_schema(self, conn: sqlite3.Connection):
        """Initialize ML predictions tables"""
        print("\n3️⃣  ML Predictions Schema")
        schema_file = self.schemas_dir / "ml_schema.sql"
        return self.run_sql_file(conn, schema_file)
    
    def apply_migrations(self, conn: sqlite3.Connection):
        """Apply all pending migrations"""
        print("\n4️⃣  Applying Migrations")
        
        if not self.migrations_dir.exists():
            print("    No migrations directory")
            return True
        
        # Get list of migrations
        migrations = sorted(self.migrations_dir.glob("*.sql"))
        
        if not migrations:
            print("    No migrations found")
            return True
        
        # Track applied migrations
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS _migrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT UNIQUE NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        except:
            pass
        
        # Get already applied migrations
        cur = conn.cursor()
        cur.execute("SELECT filename FROM _migrations")
        applied = {row[0] for row in cur.fetchall()}
        
        # Apply pending migrations
        success = True
        for migration in migrations:
            if migration.name in applied:
                print(f"    ⏭️  Skipping {migration.name} (already applied)")
                continue
            
            print(f"    🔄 Applying {migration.name}...")
            if self.run_sql_file(conn, migration):
                conn.execute("INSERT INTO _migrations (filename) VALUES (?)", (migration.name,))
                conn.commit()
            else:
                success = False
                print(f"    ❌ Migration {migration.name} failed!")
                break
        
        return success
    
    def verify_database(self, conn: sqlite3.Connection):
        """Verify database structure"""
        print("\n5️⃣  Verifying Database")
        
        cur = conn.cursor()
        
        # Get all tables
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cur.fetchall()]
        
        # Expected core tables
        expected = {
            'invoices_sync': 'Core',
            'companies_sync': 'Core',
            'transactions_sync': 'Core',
            'accounts_sync': 'Core',
            'dashboard_metrics': 'Dashboard',
            'dashboard_alerts': 'Dashboard',
            'ml_predictions': 'ML',
            'ml_model_performance': 'ML',
        }
        
        print(f"\n    📊 Database Statistics:")
        print(f"    {'Table':<30} {'Type':<12} {'Rows':<10}")
        print(f"    {'-'*52}")
        
        for table in tables:
            if table.startswith('_'):
                continue  # Skip internal tables
            
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            table_type = expected.get(table, 'Other')
            
            print(f"    {table:<30} {table_type:<12} {count:<10}")
        
        # Check for missing critical tables
        missing = [t for t in expected.keys() if t not in tables]
        
        if missing:
            print(f"\n    ⚠️  Missing tables: {', '.join(missing)}")
            return False
        
        print(f"\n    ✓ All critical tables present ({len(tables)} total)")
        return True
    
    def initialize(self, fresh: bool = False):
        """Main initialization process"""
        print("\n" + "="*70)
        print("  DATABASE INITIALIZATION")
        print("="*70)
        print(f"  Database: {self.db_path}")
        print(f"  Mode: {'FRESH INSTALL' if fresh else 'UPDATE'}")
        print("="*70)
        
        # Backup and remove if fresh
        if fresh:
            if os.path.exists(self.db_path):
                self.backup_database()
                print(f"🗑️  Removing old database...")
                os.remove(self.db_path)
        
        # Connect
        conn = sqlite3.connect(self.db_path)
        
        try:
            # Run initialization steps
            steps = [
                self.init_core_schema,
                self.init_metrics_schema,
                self.init_ml_schema,
                self.apply_migrations,
                self.verify_database,
            ]
            
            for step in steps:
                if not step(conn):
                    print(f"\n❌ Step failed: {step.__name__}")
                    return False
            
            # Success!
            print("\n" + "="*70)
            print("  ✅ DATABASE INITIALIZATION COMPLETE")
            print("="*70)
            print(f"\n  📁 Database: {self.db_path}")
            print(f"  📊 Ready for use!")
            print("="*70 + "\n")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            conn.close()
    
    def list_tables(self):
        """List all tables and their row counts"""
        if not os.path.exists(self.db_path):
            print(f"❌ Database not found: {self.db_path}")
            return
        
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cur.fetchall()]
        
        print("\n" + "="*70)
        print("  DATABASE TABLES")
        print("="*70)
        print(f"\n  Database: {self.db_path}\n")
        print(f"  {'Table':<35} {'Rows':<15}")
        print(f"  {'-'*50}")
        
        for table in tables:
            if not table.startswith('_'):
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                print(f"  {table:<35} {count:<15,}")
        
        print(f"\n  Total tables: {len(tables)}")
        print("="*70 + "\n")
        
        conn.close()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Initialize complete database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python init_db.py                    # Initialize/update database
  python init_db.py --fresh            # Fresh install with backup
  python init_db.py --db test.db       # Use different database
  python init_db.py --list             # List all tables
        """
    )
    
    parser.add_argument('--db', type=str, default='tfso-data.db',
                       help='Database path (default: tfso-data.db)')
    parser.add_argument('--fresh', action='store_true',
                       help='Drop and recreate database (creates backup first)')
    parser.add_argument('--list', action='store_true',
                       help='List all tables and row counts')
    
    args = parser.parse_args()
    
    initializer = DatabaseInitializer(args.db)
    
    if args.list:
        initializer.list_tables()
        sys.exit(0)
    
    success = initializer.initialize(fresh=args.fresh)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()