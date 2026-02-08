# PostgreSQL Migration Guide for StudyVerse

## ✅ What Has Been Done

1. **Updated `.env` file** - PostgreSQL is now active, SQLite is commented out
2. **Created initialization script** - `init_postgres_db.py` to set up the database schema
3. **Dependencies verified** - `psycopg2-binary` is already in `requirements.txt`

## 📋 Prerequisites

Before running the application with PostgreSQL, ensure:

### 1. PostgreSQL Installation
- **Download**: https://www.postgresql.org/download/windows/
- **Install PostgreSQL** (recommended version 14 or later)
- Make sure to remember the password you set for the `postgres` user during installation

### 2. Create the Database
After installing PostgreSQL:

**Option A: Using pgAdmin (GUI)**
1. Open pgAdmin (installed with PostgreSQL)
2. Connect to your local server (usually localhost)
3. Right-click on "Databases" → "Create" → "Database"
4. Name it: `StudyVerse_Final`
5. Click "Save"

**Option B: Using Command Line**
```powershell
# Add PostgreSQL to PATH or navigate to PostgreSQL bin folder
# Example: C:\Program Files\PostgreSQL\15\bin

# Create the database
psql -U postgres -c "CREATE DATABASE StudyVerse_Final;"
```

### 3. Verify Database Credentials
Check that the credentials in `.env` match your PostgreSQL setup:
```
DATABASE_URL=postgresql://postgres:Daksh%40007@localhost:5432/StudyVerse_Final
```

Breaking this down:
- `postgres` = username
- `Daksh%40007` = password (@ symbol is encoded as %40)
  - Actual password: `Daksh@007`
- `localhost:5432` = server and port
- `StudyVerse_Final` = database name

**⚠️ If your PostgreSQL password is different**, update the `.env` file accordingly.

## 🚀 Running the Migration

### Step 1: Ensure PostgreSQL is Running
- On Windows, PostgreSQL service usually starts automatically
- Check in Services (Win + R → `services.msc`)
- Look for "postgresql-x64-XX" service - it should be "Running"

### Step 2: Initialize the Database Schema
Run the initialization script:
```powershell
python init_postgres_db.py
```

This will:
- Drop any existing tables (if any)
- Create all tables based on your SQLAlchemy models
- Set up the complete schema

**⚠️ Note**: This will create an empty database. Any data in your SQLite database will need to be migrated separately if needed.

### Step 3: Start Your Application
```powershell
python app.py
```

## 🔄 Migrating Data from SQLite (Optional)

If you have existing data in SQLite that you want to migrate to PostgreSQL:

### Option 1: Manual Export/Import (for small datasets)
1. Export data from SQLite to CSV or JSON
2. Import into PostgreSQL using custom scripts

### Option 2: Using a Migration Script
Create a script to read from SQLite and write to PostgreSQL:

```python
# migrate_data.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# SQLite connection
sqlite_engine = create_engine('sqlite:///StudyVerse.db')
SQLiteSession = sessionmaker(bind=sqlite_engine)
sqlite_session = SQLiteSession()

# PostgreSQL connection
postgres_engine = create_engine('postgresql://postgres:Daksh@007@localhost:5432/StudyVerse_Final')
PostgresSession = sessionmaker(bind=postgres_engine)
postgres_session = PostgresSession()

# Migrate each table...
# (Custom logic based on your models)
```

## 🔧 Troubleshooting

### Connection Errors
If you get connection errors:
1. Verify PostgreSQL service is running
2. Check credentials in `.env`
3. Ensure the `StudyVerse_Final` database exists
4. Check firewall settings (port 5432 should be accessible)

### Password Authentication Failed
- Double-check the password in `.env`
- Remember special characters need URL encoding:
  - `@` becomes `%40`
  - `#` becomes `%23`
  - etc.

### Database Does Not Exist
Run this command to create it:
```sql
CREATE DATABASE StudyVerse_Final;
```

## 📊 Verifying the Migration

After initialization, you can verify the tables were created:

**Using pgAdmin:**
1. Open pgAdmin
2. Navigate to: Servers → PostgreSQL → Databases → StudyVerse_Final → Schemas → public → Tables
3. You should see all your application tables

**Using psql:**
```powershell
psql -U postgres -d StudyVerse_Final -c "\dt"
```

## 🎯 Next Steps

1. Run `python init_postgres_db.py` to set up the schema
2. Start your application with `python app.py`
3. Register a new user or log in to test the connection
4. Check that data is being saved to PostgreSQL

## 💡 Benefits of PostgreSQL

- **Better for production**: More robust and scalable than SQLite
- **Concurrent access**: Multiple users can access simultaneously
- **Advanced features**: Better support for complex queries and transactions
- **Cloud deployment**: Easily deploy to platforms like Heroku, Render, etc.

---

Need help? Check the PostgreSQL documentation: https://www.postgresql.org/docs/
