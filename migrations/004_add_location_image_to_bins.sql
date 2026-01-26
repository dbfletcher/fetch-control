-- +goose Up
-- +goose StatementBegin
ALTER TABLE bin ADD COLUMN location_image VARCHAR(255) AFTER name;
-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin
ALTER TABLE bin DROP COLUMN location_image;
-- +goose StatementEnd
