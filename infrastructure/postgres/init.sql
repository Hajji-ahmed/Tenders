-- Exécuté une seule fois à la création du volume PostgreSQL.
CREATE EXTENSION IF NOT EXISTS vector;

-- Base dédiée aux tests (même conteneur, données isolées).
CREATE DATABASE tender_test OWNER tender;
\c tender_test
CREATE EXTENSION IF NOT EXISTS vector;
