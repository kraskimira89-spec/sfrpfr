from sfrfr.core.config import get_settings
from sfrfr.services.documents_schema import (
    documents_has_ingest_columns,
    document_ingest_jobs_available,
)

s = get_settings()
print("async", s.document_ingest_async)
print("ingest_cols", documents_has_ingest_columns())
print("jobs", document_ingest_jobs_available())
