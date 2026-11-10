CREATE TABLE IF NOT EXISTS clima.registration_profiles(uid BIGINT PRIMARY KEY,payload TEXT NOT NULL);
ALTER TABLE clima.registration_profiles ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON clima.registration_profiles FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON clima.registration_profiles TO clima_app;
CREATE POLICY backend_only ON clima.registration_profiles FOR ALL TO clima_app USING(true) WITH CHECK(true);
