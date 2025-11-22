# Installation Guide

This guide walks you through installing Local Unpaywall and all its dependencies.

## System Requirements

### Hardware Requirements

| Component | Minimum | Recommended | Full Dataset |
|-----------|---------|-------------|--------------|
| CPU | 2 cores | 4+ cores | 8+ cores |
| RAM | 4 GB | 8 GB | 16+ GB |
| Disk Space | 50 GB | 200 GB | 1 TB+ |
| Disk Type | HDD | SSD | NVMe SSD |

> **Note**: Disk requirements depend on how much data you process. Processing only recent publications (2020+) requires significantly less space.

### Software Requirements

- **Operating System**: Linux (recommended), macOS, or Windows with WSL2
- **Python**: 3.12 or higher
- **PostgreSQL**: 13 or higher
- **AWS CLI**: For downloading OpenAlex data (optional)

## Step 1: Install Python

### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip
```

### Linux (Fedora/RHEL)
```bash
sudo dnf install python3.12 python3-pip
```

### macOS
```bash
# Using Homebrew
brew install python@3.12
```

### Windows
Download Python 3.12+ from [python.org](https://www.python.org/downloads/) and run the installer. Make sure to check "Add Python to PATH".

### Verify Installation
```bash
python3 --version
# Should output: Python 3.12.x or higher
```

## Step 2: Install PostgreSQL

### Linux (Ubuntu/Debian)
```bash
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Linux (Fedora/RHEL)
```bash
sudo dnf install postgresql-server postgresql-contrib
sudo postgresql-setup --initdb
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### macOS
```bash
# Using Homebrew
brew install postgresql@15
brew services start postgresql@15
```

### Windows
Download PostgreSQL from [postgresql.org](https://www.postgresql.org/download/windows/) and run the installer.

### Verify Installation
```bash
psql --version
# Should output: psql (PostgreSQL) 15.x or similar
```

## Step 3: Create Database User and Database

### Connect to PostgreSQL
```bash
# Linux - switch to postgres user
sudo -u postgres psql

# macOS - connect directly
psql postgres
```

### Create User and Database
```sql
-- Create a user for Local Unpaywall
CREATE USER unpaywall_user WITH PASSWORD 'your_secure_password';

-- Create the database
CREATE DATABASE unpaywall OWNER unpaywall_user;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE unpaywall TO unpaywall_user;

-- Exit psql
\q
```

### Test Connection
```bash
psql -h localhost -U unpaywall_user -d unpaywall -c "SELECT 1;"
```

## Step 4: Download Local Unpaywall

### Option A: Clone from GitHub
```bash
git clone https://github.com/hherb/local_unpaywall.git
cd local_unpaywall
```

### Option B: Download Release
```bash
# Download latest release
wget https://github.com/hherb/local_unpaywall/archive/refs/heads/main.zip
unzip main.zip
cd local_unpaywall-main
```

## Step 5: Set Up Python Environment

### Create Virtual Environment
```bash
# Create virtual environment
python3 -m venv .venv

# Activate it
# Linux/macOS:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate
```

### Install Dependencies

#### Option A: Using uv (Recommended)
```bash
# Install uv if not installed
pip install uv

# Install all dependencies
uv sync
```

#### Option B: Using pip
```bash
pip install psycopg2-binary tqdm requests python-dotenv
```

### Verify Installation
```bash
python -c "import psycopg2; import tqdm; import requests; print('All dependencies installed!')"
```

## Step 6: Install AWS CLI (Optional)

The AWS CLI is needed to download OpenAlex snapshot data.

### Linux
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install
```

### macOS
```bash
brew install awscli
```

### Windows
Download from [AWS CLI website](https://aws.amazon.com/cli/) and run the installer.

### Verify Installation
```bash
aws --version
```

> **Note**: You don't need AWS credentials to download OpenAlex data - it's publicly available.

## Step 7: Create Database Schema

### Configure Environment
Create a `.env` file in the project root:
```bash
cat > .env << 'EOF'
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=unpaywall
POSTGRES_USER=unpaywall_user
POSTGRES_PASSWORD=your_secure_password
EOF
```

### Run Schema Creation
```bash
python db/create_db.py
```

You should see output like:
```
INFO - Loaded database configuration from .env file
INFO - Connected to database successfully
INFO - Created schema: unpaywall
INFO - Created lookup tables
INFO - Created main table: unpaywall.doi_urls
INFO - Created indexes
INFO - Schema creation complete
```

## Step 8: Verify Installation

Run a quick test to ensure everything is working:

```bash
# Test database connection
python -c "
from db.create_db import DatabaseCreator
creator = DatabaseCreator.from_env_or_args()
if creator.test_connection():
    print('Database connection successful!')
"

# Test file tracker
python -c "
from helpers.file_tracker import FileTracker
tracker = FileTracker('/tmp/test_tracker.db')
print('File tracker working!')
import os; os.remove('/tmp/test_tracker.db')
"

# Test CSV utilities
python -c "
from helpers.csv_utils import count_lines_fast
print('CSV utilities working!')
"
```

## Installation Complete!

You now have Local Unpaywall installed and ready to use.

## Next Steps

1. [Configuration](03-configuration.md) - Fine-tune your settings
2. [Extracting URLs](04-extracting-urls.md) - Download and process OpenAlex data

## Troubleshooting Installation

### Python Version Too Old
```
Error: Python 3.12+ required
```
**Solution**: Install Python 3.12 or higher using your system's package manager or pyenv.

### PostgreSQL Connection Refused
```
Error: could not connect to server: Connection refused
```
**Solution**:
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Start it if not running
sudo systemctl start postgresql
```

### Permission Denied on Database
```
Error: permission denied for database unpaywall
```
**Solution**: Ensure the user has proper privileges:
```sql
GRANT ALL PRIVILEGES ON DATABASE unpaywall TO unpaywall_user;
```

### psycopg2 Installation Fails
```
Error: pg_config executable not found
```
**Solution**: Install PostgreSQL development headers:
```bash
# Ubuntu/Debian
sudo apt install libpq-dev

# Fedora/RHEL
sudo dnf install postgresql-devel

# macOS
brew install postgresql
```

### Virtual Environment Not Activating
**Solution**: Ensure you're using the correct activation command for your shell:
```bash
# bash/zsh
source .venv/bin/activate

# fish
source .venv/bin/activate.fish

# Windows PowerShell
.venv\Scripts\Activate.ps1
```
