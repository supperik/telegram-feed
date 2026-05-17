-- Runs once on Postgres container's first boot.
-- The default DB is already created via POSTGRES_DB env. This script
-- exists for future extensions and to keep the mount point stable.
\echo 'Postgres container initialized for telegram-feed.'
