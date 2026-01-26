-- +goose Up
-- +goose StatementBegin
ALTER TABLE bin 
ADD COLUMN parent_bin_id INT NULL AFTER location_image,
ADD CONSTRAINT fk_parent_bin 
    FOREIGN KEY (parent_bin_id) 
    REFERENCES bin(id) 
    ON DELETE SET NULL;
-- +goose StatementEnd

-- +goose Down
-- +goose StatementBegin
ALTER TABLE bin DROP FOREIGN KEY fk_parent_bin;
ALTER TABLE bin DROP COLUMN parent_bin_id;
-- +goose StatementEnd
