-- +goose Up
-- +goose StatementBegin
CREATE TABLE locations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT
);
-- +goose StatementEnd

-- +goose StatementBegin
CREATE TABLE parts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    quantity INT DEFAULT 0,
    location_id INT,
    highres_path VARCHAR(512),
    lowres_path VARCHAR(512),
    FOREIGN KEY (location_id) REFERENCES locations(id)
);
-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin
DROP TABLE parts;
-- +goose StatementEnd
-- +goose StatementBegin
DROP TABLE locations;
-- +goose StatementEnd
