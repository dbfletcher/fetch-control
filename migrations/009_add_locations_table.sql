-- +goose Up
-- +goose StatementBegin
CREATE TABLE locations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    household_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    CONSTRAINT fk_location_household FOREIGN KEY (household_id) REFERENCES households(id) ON DELETE CASCADE
);
-- +goose StatementEnd

-- +goose StatementBegin
ALTER TABLE bin 
ADD COLUMN location_id INT NULL AFTER name,
ADD CONSTRAINT fk_bin_location FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE SET NULL;
-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin
ALTER TABLE bin DROP FOREIGN KEY fk_bin_location;
ALTER TABLE bin DROP COLUMN location_id;
DROP TABLE locations;
-- +goose StatementEnd
