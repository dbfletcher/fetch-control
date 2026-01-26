-- +goose NO TRANSACTION
-- +goose Up

-- 1. Create the join table
CREATE TABLE memberships (
    user_id INT,
    household_id INT,
    role VARCHAR(50) DEFAULT 'member', -- Optional: e.g., 'admin' or 'viewer'
    PRIMARY KEY (user_id, household_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE
);

-- 2. Remove the old single-link column from users
-- Note: We must drop the foreign key constraint first
ALTER TABLE users DROP FOREIGN KEY users_ibfk_1;
ALTER TABLE users DROP COLUMN household_id;

-- +goose Down
ALTER TABLE users ADD COLUMN household_id INT;
ALTER TABLE users ADD CONSTRAINT users_ibfk_1 FOREIGN KEY (household_id) REFERENCES households(id);
DROP TABLE memberships;
