-- Runs once, when the postgres volume is first initialized.
-- Backend tests use this database so they never touch incident data in `incidents`.
CREATE DATABASE incidents_test;
