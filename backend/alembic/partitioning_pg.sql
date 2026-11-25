-- ============================================================================
-- LOGIPULSE Production PostgreSQL Partitioning DDL
-- High-Volume Telematics Time-Series Range Partitioning
-- ============================================================================

-- 1. Vehicle Locations Table (Partitioned by recorded_at timestamp)
CREATE TABLE IF NOT EXISTS vehicle_locations_partitioned (
    id VARCHAR(36) NOT NULL,
    vehicle_id VARCHAR(36) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    speed_kmph DOUBLE PRECISION,
    heading_degrees DOUBLE PRECISION,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(32) NOT NULL DEFAULT 'SIMULATION',
    CONSTRAINT pk_vehicle_locations_partitioned PRIMARY KEY (id, recorded_at),
    CONSTRAINT check_valid_location_lat CHECK (latitude >= -90.0 AND latitude <= 90.0),
    CONSTRAINT check_valid_location_lon CHECK (longitude >= -180.0 AND longitude <= 180.0),
    CONSTRAINT check_valid_location_speed CHECK (speed_kmph IS NULL OR speed_kmph >= 0.0),
    CONSTRAINT check_valid_location_heading CHECK (heading_degrees IS NULL OR (heading_degrees >= 0.0 AND heading_degrees <= 360.0))
) PARTITION BY RANGE (recorded_at);

-- Monthly partitions for 2026-2027
CREATE TABLE IF NOT EXISTS vehicle_locations_y2026m11 PARTITION OF vehicle_locations_partitioned
    FOR VALUES FROM ('2026-11-01 00:00:00+00') TO ('2026-12-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS vehicle_locations_y2026m12 PARTITION OF vehicle_locations_partitioned
    FOR VALUES FROM ('2026-12-01 00:00:00+00') TO ('2027-01-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS vehicle_locations_y2027m01 PARTITION OF vehicle_locations_partitioned
    FOR VALUES FROM ('2027-01-01 00:00:00+00') TO ('2027-02-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS vehicle_locations_default PARTITION OF vehicle_locations_partitioned DEFAULT;

-- Partition local compound indices
CREATE INDEX IF NOT EXISTS ix_vehicle_locations_p_veh_rec 
    ON vehicle_locations_partitioned (vehicle_id, recorded_at DESC);


-- 2. Simulation Telemetry Table (Partitioned by recorded_at timestamp)
CREATE TABLE IF NOT EXISTS simulation_telemetry_partitioned (
    id VARCHAR(36) NOT NULL,
    simulation_id VARCHAR(64) NOT NULL,
    vehicle_id VARCHAR(36) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    speed_kmph DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    heading_degrees DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(32) NOT NULL DEFAULT 'SIMULATION',
    CONSTRAINT pk_sim_telemetry_partitioned PRIMARY KEY (id, recorded_at),
    CONSTRAINT check_sim_telemetry_lat CHECK (latitude >= -90.0 AND latitude <= 90.0),
    CONSTRAINT check_sim_telemetry_lon CHECK (longitude >= -180.0 AND longitude <= 180.0),
    CONSTRAINT check_sim_telemetry_speed CHECK (speed_kmph >= 0.0)
) PARTITION BY RANGE (recorded_at);

-- Monthly partitions for 2026-2027
CREATE TABLE IF NOT EXISTS simulation_telemetry_y2026m11 PARTITION OF simulation_telemetry_partitioned
    FOR VALUES FROM ('2026-11-01 00:00:00+00') TO ('2026-12-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS simulation_telemetry_y2026m12 PARTITION OF simulation_telemetry_partitioned
    FOR VALUES FROM ('2026-12-01 00:00:00+00') TO ('2027-01-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS simulation_telemetry_y2027m01 PARTITION OF simulation_telemetry_partitioned
    FOR VALUES FROM ('2027-01-01 00:00:00+00') TO ('2027-02-01 00:00:00+00');

CREATE TABLE IF NOT EXISTS simulation_telemetry_default PARTITION OF simulation_telemetry_partitioned DEFAULT;

-- Partition local compound indices
CREATE INDEX IF NOT EXISTS ix_sim_telemetry_p_sim_veh_rec 
    ON simulation_telemetry_partitioned (simulation_id, vehicle_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS ix_sim_telemetry_p_sim_rec 
    ON simulation_telemetry_partitioned (simulation_id, recorded_at DESC);

