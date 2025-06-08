-- PostgreSQL Schema for DOI-URL Mapping
-- Optimized for fast lookups and efficient storage

-- Main table for DOI to URL mappings
        CREATE TABLE IF NOT EXISTS doi_urls (
            id BIGSERIAL PRIMARY KEY,
            doi TEXT NOT NULL,
            url TEXT NOT NULL,
            pdf_url TEXT,
            openalex_id TEXT,
            title TEXT,
            publication_year INTEGER,
            location_type TEXT NOT NULL,
            version TEXT,
            license TEXT,
            host_type TEXT,
            oa_status TEXT,
            is_oa BOOLEAN DEFAULT FALSE,
            url_quality_score INTEGER DEFAULT 50,
            last_verified TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Indexes for efficient querying
        CREATE INDEX IF NOT EXISTS idx_doi_urls_doi ON doi_urls(doi);
        CREATE INDEX IF NOT EXISTS idx_doi_urls_url ON doi_urls(url);
        CREATE INDEX IF NOT EXISTS idx_doi_urls_pdf_url ON doi_urls(pdf_url) WHERE pdf_url IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_doi_urls_doi_location_type ON doi_urls(doi, location_type);
        CREATE INDEX IF NOT EXISTS idx_doi_urls_oa_status ON doi_urls(oa_status) WHERE is_oa = TRUE;
        CREATE INDEX IF NOT EXISTS idx_doi_urls_host_type ON doi_urls(host_type);
        CREATE INDEX IF NOT EXISTS idx_doi_urls_publication_year ON doi_urls(publication_year);

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

        -- Optional metadata table
        CREATE TABLE IF NOT EXISTS doi_metadata (
            doi TEXT PRIMARY KEY,
            openalex_id TEXT UNIQUE,
            title TEXT,
            publication_year INTEGER,
            work_type TEXT,
            is_retracted BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_doi_metadata_year ON doi_metadata(publication_year);
        CREATE INDEX IF NOT EXISTS idx_doi_metadata_type ON doi_metadata(work_type);