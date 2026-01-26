-- +goose NO TRANSACTION
-- +goose Up

CREATE TABLE households (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    household_id INT,
    FOREIGN KEY (household_id) REFERENCES households(id)
);

-- Creating the BIN table from scratch here
CREATE TABLE bin (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL, -- e.g., "Bin A1" or "M3 Screws"
    location_id INT,
    household_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (location_id) REFERENCES locations(id),
    FOREIGN KEY (household_id) REFERENCES households(id)
);

-- +goose Down
DROP TABLE bin;
DROP TABLE users;
DROP TABLE households;
