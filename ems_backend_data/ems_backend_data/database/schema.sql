CREATE TABLE IF NOT EXISTS alarms (
    id BIGSERIAL PRIMARY KEY,
    device_id TEXT NOT NULL,
    tag_name TEXT NOT NULL,
    value NUMERIC,
    time_stamp TIMESTAMP NOT NULL,
    severity TEXT NOT NULL,
    alarm_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    remark TEXT NOT NULL DEFAULT '',
    clr_timestamp TIMESTAMP,
    UNIQUE (device_id, tag_name, time_stamp, alarm_type)
);

CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    device_id TEXT NOT NULL,
    tag_name TEXT NOT NULL,
    value NUMERIC,
    time_stamp TIMESTAMP NOT NULL,
    severity TEXT NOT NULL,
    alarm_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    remark TEXT NOT NULL DEFAULT '',
    clr_timestamp TIMESTAMP,
    UNIQUE (device_id, tag_name, time_stamp, alarm_type)
);
