-- +goose Up
-- +goose StatementBegin
ALTER TABLE items ADD COLUMN price DECIMAL(10, 2) DEFAULT 0.00 AFTER quantity;
-- +goose StatementEnd

-- +goose StatementBegin
DROP TABLE IF EXISTS parts;
-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin
ALTER TABLE items DROP COLUMN price;
-- +goose StatementEnd
