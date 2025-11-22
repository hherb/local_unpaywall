# Local Unpaywall User Manual

Welcome to the Local Unpaywall User Manual. This guide will help you set up and use your own local mirror of open access publication URLs.

## Table of Contents

1. [Introduction](01-introduction.md) - What is Local Unpaywall and why use it
2. [Installation](02-installation.md) - System requirements and setup
3. [Configuration](03-configuration.md) - Database and environment setup
4. [Extracting URLs](04-extracting-urls.md) - Getting DOI-URL pairs from OpenAlex
5. [Importing Data](05-importing-data.md) - Loading data into PostgreSQL
6. [Downloading PDFs](06-downloading-pdfs.md) - Fetching full-text articles
7. [Querying Data](07-querying-data.md) - Finding and using your data
8. [Maintenance](08-maintenance.md) - Updates, backups, and monitoring
9. [Troubleshooting](09-troubleshooting.md) - Solving common problems
10. [FAQ](10-faq.md) - Frequently asked questions

## Quick Navigation

### Getting Started
If you're new to Local Unpaywall, start with the [Introduction](01-introduction.md) and then follow the [Installation](02-installation.md) guide.

### Daily Operations
For routine tasks, see:
- [Extracting URLs](04-extracting-urls.md) - Processing new OpenAlex data
- [Querying Data](07-querying-data.md) - Finding URLs for DOIs
- [Downloading PDFs](06-downloading-pdfs.md) - Getting full-text articles

### Administration
For system maintenance:
- [Maintenance](08-maintenance.md) - Keeping your system healthy
- [Troubleshooting](09-troubleshooting.md) - When things go wrong

## Document Conventions

Throughout this manual:

- `monospace text` indicates commands or code
- **Bold text** indicates important terms or UI elements
- > Blockquotes indicate tips or important notes
- Code blocks show complete examples you can copy and run

## Getting Help

- Check the [FAQ](10-faq.md) for common questions
- Review [Troubleshooting](09-troubleshooting.md) for error solutions
- See the [Developer Documentation](../../DEVELOPERS.md) for technical details
- Report issues at https://github.com/hherb/local_unpaywall/issues

## Version Information

This manual covers Local Unpaywall with:
- Normalized database schema (unpaywall namespace)
- SQLite-based file tracking
- Resume capability for all operations
- Python 3.12+ support
