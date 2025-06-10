-- PostgreSQL Schema for DOI-URL Mapping
-- Optimized for fast lookups and efficient storage
-- Updated for Migration 003: Uses unpaywall schema namespace

-- Create unpaywall schema
CREATE SCHEMA IF NOT EXISTS unpaywall;

-- Main table for DOI to URL mappings
CREATE TABLE IF NOT EXISTS unpaywall.doi_urls (
    id BIGSERIAL PRIMARY KEY,
    doi TEXT NOT NULL,
    url TEXT NOT NULL,
    pdf_url TEXT,
    openalex_id BIGINT,
    title TEXT,
    publication_year INTEGER,
    location_type TEXT NOT NULL,
    version TEXT,
    license TEXT,
    host_type TEXT,
    oa_status TEXT,
    is_oa BOOLEAN DEFAULT FALSE,
    work_type TEXT,
    is_retracted BOOLEAN DEFAULT FALSE,
    url_quality_score INTEGER DEFAULT 50,
    last_verified TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_doi ON unpaywall.doi_urls(doi);
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_url ON unpaywall.doi_urls(url);
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_pdf_url ON unpaywall.doi_urls(pdf_url) WHERE pdf_url IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_doi_location_type ON unpaywall.doi_urls(doi, location_type);
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_oa_status ON unpaywall.doi_urls(oa_status) WHERE is_oa = TRUE;
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_host_type ON unpaywall.doi_urls(host_type);
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_publication_year ON unpaywall.doi_urls(publication_year);
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_work_type ON unpaywall.doi_urls(work_type);
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_is_retracted ON unpaywall.doi_urls(is_retracted);
CREATE INDEX IF NOT EXISTS idx_unpaywall_doi_urls_openalex_work_id ON unpaywall.doi_urls(openalex_id);

        -- Unique constraint to prevent duplicate DOI-URL pairs
        DO $$ 
        BEGIN
            BEGIN
                ALTER TABLE doi_urls ADD CONSTRAINT unique_doi_url UNIQUE(doi, url);
            EXCEPTION
                WHEN duplicate_table THEN
                    -- Constraint already exists
                    NULL;
            END;
        END $$;

