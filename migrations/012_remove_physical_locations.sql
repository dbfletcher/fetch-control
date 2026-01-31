-- +goose Up
-- 1. Remove the foreign key constraint using the specific name from SHOW CREATE TABLE
ALTER TABLE `bin` DROP FOREIGN KEY `fk_bin_location`;

-- 2. Drop the location_id column
ALTER TABLE `bin` DROP COLUMN `location_id`;

-- 3. Drop the locations table entirely
-- Note: Your output showed the table as `locations` (plural) in the constraint
DROP TABLE `locations`;

-- +goose Down
-- Recreate the locations table
CREATE TABLE `locations` (
    `id` int(11) NOT NULL AUTO_INCREMENT,
    `name` varchar(255) NOT NULL,
    `description` text DEFAULT NULL,
    `membership_id` int(11) DEFAULT NULL,
    `created_at` timestamp NULL DEFAULT current_timestamp(),
    PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Re-add the column and constraint to the bin table
ALTER TABLE `bin` ADD COLUMN `location_id` int(11) DEFAULT NULL;

ALTER TABLE `bin` 
ADD CONSTRAINT `fk_bin_location` 
FOREIGN KEY (`location_id`) REFERENCES `locations` (`id`) ON DELETE SET NULL;
