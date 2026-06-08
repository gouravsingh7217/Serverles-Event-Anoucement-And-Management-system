-- ============================================================
--  EventPulse — Complete MySQL Database Schema
--  
--  HOW TO USE THIS FILE IN MYSQL WORKBENCH:
--  1. Open MySQL Workbench
--  2. Connect to your server (local or AWS RDS)
--  3. File → Open SQL Script → select this file
--  4. Press Ctrl+Shift+Enter (Run All)
--  5. Done — all tables created with seed data
-- ============================================================

-- ─────────────────────────────────────────────
--  STEP 1: Create and select the database
-- ─────────────────────────────────────────────
DROP DATABASE IF EXISTS eventpulse;
CREATE DATABASE eventpulse
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE eventpulse;

-- ─────────────────────────────────────────────
--  STEP 2: TABLE — users
--  Stores both regular users and admin accounts
-- ─────────────────────────────────────────────
CREATE TABLE users (
  id              INT           NOT NULL AUTO_INCREMENT,
  full_name       VARCHAR(100)  NOT NULL,
  email           VARCHAR(150)  NOT NULL,
  password_hash   VARCHAR(255)  NOT NULL,        -- bcrypt hash, NEVER plain text
  role            ENUM('user', 'admin')
                                NOT NULL DEFAULT 'user',
  is_active       TINYINT(1)    NOT NULL DEFAULT 1,
  sns_subscribed  TINYINT(1)    NOT NULL DEFAULT 1,  -- opted in to email alerts
  created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  UNIQUE  KEY uq_users_email  (email),
  INDEX         idx_users_role   (role),
  INDEX         idx_users_active (is_active)
);

-- ─────────────────────────────────────────────
--  STEP 3: TABLE — events
--  All upcoming and past events
-- ─────────────────────────────────────────────
CREATE TABLE events (
  id              INT           NOT NULL AUTO_INCREMENT,
  title           VARCHAR(200)  NOT NULL,
  description     TEXT,
  event_date      DATE          NOT NULL,
  event_time      TIME,
  venue           VARCHAR(200),
  category        VARCHAR(100),
  status          ENUM('upcoming', 'past', 'cancelled')
                                NOT NULL DEFAULT 'upcoming',
  created_by      INT           NOT NULL,         -- FK → users.id (admin)
  announced       TINYINT(1)    NOT NULL DEFAULT 0,
  announced_at    DATETIME,
  created_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  INDEX   idx_events_status     (status),
  INDEX   idx_events_date       (event_date),
  INDEX   idx_events_created_by (created_by),
  CONSTRAINT fk_events_creator
    FOREIGN KEY (created_by) REFERENCES users(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

-- ─────────────────────────────────────────────
--  STEP 4: TABLE — announcements
--  Log of every SNS email announcement sent
-- ─────────────────────────────────────────────
CREATE TABLE announcements (
  id              INT           NOT NULL AUTO_INCREMENT,
  event_id        INT           NOT NULL,         -- FK → events.id
  subject         VARCHAR(255)  NOT NULL,
  message_body    TEXT          NOT NULL,
  sent_by         INT           NOT NULL,         -- FK → users.id (admin who sent)
  sns_message_id  VARCHAR(255),                   -- AWS SNS MessageId for tracking
  sent_at         DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  INDEX   idx_ann_event_id (event_id),
  INDEX   idx_ann_sent_by  (sent_by),
  CONSTRAINT fk_ann_event
    FOREIGN KEY (event_id) REFERENCES events(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_ann_sender
    FOREIGN KEY (sent_by) REFERENCES users(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

-- ─────────────────────────────────────────────
--  STEP 5: TABLE — ai_generations
--  Logs every AI-generated announcement + poster
-- ─────────────────────────────────────────────
CREATE TABLE ai_generations (
  id                  INT           NOT NULL AUTO_INCREMENT,
  event_id            INT,                          -- optional FK → events.id
  generated_by        INT           NOT NULL,       -- FK → users.id
  input_title         VARCHAR(200)  NOT NULL,
  input_date          VARCHAR(50),
  input_venue         VARCHAR(200),
  input_description   TEXT,
  generated_text      TEXT,                         -- LLM output
  generated_subject   VARCHAR(255),                 -- LLM subject line
  poster_theme        VARCHAR(50),                  -- theme name used
  generation_time_ms  INT,                          -- how long it took
  created_at          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  INDEX   idx_aigen_event    (event_id),
  INDEX   idx_aigen_user     (generated_by),
  CONSTRAINT fk_aigen_event
    FOREIGN KEY (event_id) REFERENCES events(id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_aigen_user
    FOREIGN KEY (generated_by) REFERENCES users(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

-- ─────────────────────────────────────────────
--  STEP 6: TABLE — sessions
--  JWT session tokens (optional, if not using stateless JWT)
-- ─────────────────────────────────────────────
CREATE TABLE sessions (
  id          INT           NOT NULL AUTO_INCREMENT,
  user_id     INT           NOT NULL,
  token       VARCHAR(512)  NOT NULL,
  expires_at  DATETIME      NOT NULL,
  created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  UNIQUE KEY  uq_sessions_token   (token(255)),
  INDEX       idx_sessions_user   (user_id),
  INDEX       idx_sessions_expiry (expires_at),
  CONSTRAINT fk_sessions_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE ON UPDATE CASCADE
);

-- ─────────────────────────────────────────────
--  STEP 7: TABLE — event_registrations  (BONUS)
--  Tracks which users registered for which events
-- ─────────────────────────────────────────────
CREATE TABLE event_registrations (
  id           INT       NOT NULL AUTO_INCREMENT,
  event_id     INT       NOT NULL,
  user_id      INT       NOT NULL,
  registered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id),
  UNIQUE KEY  uq_reg (event_id, user_id),
  INDEX       idx_reg_event (event_id),
  INDEX       idx_reg_user  (user_id),
  CONSTRAINT fk_reg_event
    FOREIGN KEY (event_id) REFERENCES events(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_reg_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE ON UPDATE CASCADE
);

-- ─────────────────────────────────────────────
--  STEP 8: SEED DATA — Insert demo records
-- ─────────────────────────────────────────────

-- Admin user (password = admin123, bcrypt hashed)
INSERT INTO users (full_name, email, password_hash, role) VALUES
('Admin User', 'admin@demo.com',
 '$2b$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'admin');

-- Regular user (password = user123, bcrypt hashed)
INSERT INTO users (full_name, email, password_hash, role) VALUES
('Alex Johnson', 'user@demo.com',
 '$2b$10$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uheWG/igi', 'user');

-- Upcoming events
INSERT INTO events (title, description, event_date, event_time, venue, category, status, created_by)
VALUES
('Tech Summit 2025',
 'Annual technology conference featuring keynotes, workshops, and networking sessions.',
 '2025-08-15', '09:00:00', 'Main Auditorium', 'Technology', 'upcoming', 1),

('Design Hackathon',
 'A 48-hour design sprint to solve real-world UX challenges with top designers.',
 '2025-09-02', '10:00:00', 'Innovation Hub', 'Design', 'upcoming', 1),

('AI Workshop Series',
 'Hands-on workshops exploring practical applications of artificial intelligence.',
 '2025-09-20', '11:00:00', 'Lab Block B', 'AI/ML', 'upcoming', 1);

-- Past events
INSERT INTO events (title, description, event_date, event_time, venue, category, status, created_by)
VALUES
('Product Launch 2024',
 'Unveiling of our flagship product to stakeholders and press.',
 '2024-11-10', '14:00:00', 'Conference Hall 1', 'Product', 'past', 1),

('Annual Gala',
 'An evening of celebration, awards, and networking for our community.',
 '2024-12-20', '18:00:00', 'Grand Ballroom', 'Social', 'past', 1);


SHOW TABLES;

SELECT 'users' AS table_name, COUNT(*) AS row_count FROM users
UNION ALL
SELECT 'events', COUNT(*) FROM events
UNION ALL
SELECT 'announcements', COUNT(*) FROM announcements
UNION ALL
SELECT 'ai_generations', COUNT(*) FROM ai_generations
UNION ALL
SELECT 'sessions', COUNT(*) FROM sessions
UNION ALL
SELECT 'event_registrations', COUNT(*) FROM event_registrations;SELECT 'users' AS table_name, COUNT(*) AS row_count FROM users
UNION ALL
SELECT 'events', COUNT(*) FROM events
UNION ALL
SELECT 'announcements', COUNT(*) FROM announcements
UNION ALL
SELECT 'ai_generations', COUNT(*) FROM ai_generations
UNION ALL
SELECT 'sessions', COUNT(*) FROM sessions
UNION ALL
SELECT 'event_registrations', COUNT(*) FROM event_registrations;