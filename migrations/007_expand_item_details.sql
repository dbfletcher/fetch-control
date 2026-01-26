-- +goose Up
-- +goose StatementBegin
ALTER TABLE items 
ADD COLUMN item_url VARCHAR(512) AFTER description,
ADD COLUMN high_res_image VARCHAR(255) AFTER item_url,
ADD COLUMN low_res_image VARCHAR(255) AFTER high_res_image;
-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin
ALTER TABLE items 
DROP COLUMN low_res_image,
DROP COLUMN high_res_image,
DROP COLUMN item_url;
-- +goose StatementEnd
