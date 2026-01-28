-- +goose Up
-- Disable checks briefly for structural changes
SET FOREIGN_KEY_CHECKS=0;

-- 1. Add timestamps only where they are missing
ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE memberships ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE items ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Note: Skipping 'bin' as the error confirmed it already has 'created_at'

-- 2. Create the Activity Log table
CREATE TABLE IF NOT EXISTS activity_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    household_id INT NOT NULL,
    action_type VARCHAR(50) NOT NULL, -- 'ADD', 'MOVE', 'DELETE'
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE
);

SET FOREIGN_KEY_CHECKS=1;

-- +goose Down
DROP TABLE IF EXISTS activity_log;
ALTER TABLE items DROP COLUMN IF EXISTS created_at;
ALTER TABLE memberships DROP COLUMN IF EXISTS created_at;
ALTER TABLE users DROP COLUMN IF EXISTS created_at;
