-- +goose Up
-- +goose StatementBegin
CREATE TABLE items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bin_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    quantity INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_item_bin FOREIGN KEY (bin_id) REFERENCES bin(id) ON DELETE CASCADE
);
-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin
DROP TABLE items;
-- +goose StatementEnd
