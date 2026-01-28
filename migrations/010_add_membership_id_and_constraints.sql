-- +goose Up
-- Disable checks to allow restructuring the primary key
SET FOREIGN_KEY_CHECKS=0;

-- 1. Remove the current composite primary key
ALTER TABLE memberships DROP PRIMARY KEY;

-- 2. Add the new auto-incrementing ID as the primary key
ALTER TABLE memberships ADD COLUMN id INT AUTO_INCREMENT PRIMARY KEY FIRST;

-- 3. Add a unique constraint to prevent duplicate access
ALTER TABLE memberships ADD UNIQUE (user_id, household_id);

-- Re-enable checks
SET FOREIGN_KEY_CHECKS=1;

-- +goose Down
SET FOREIGN_KEY_CHECKS=0;
ALTER TABLE memberships DROP COLUMN id;
ALTER TABLE memberships ADD PRIMARY KEY (user_id, household_id);
SET FOREIGN_KEY_CHECKS=1;
