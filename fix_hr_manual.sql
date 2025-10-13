-- Manual SQL Fix for HR Management Production Issue
-- Run this SQL command directly on your production database

-- Check if the notes column already exists
SELECT COLUMN_NAME 
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_SCHEMA = DATABASE() 
AND TABLE_NAME = 'workers' 
AND COLUMN_NAME = 'notes';

-- If the above query returns no results, run this command to add the missing column:
ALTER TABLE workers ADD COLUMN notes TEXT NULL AFTER emergency_contact_phone;

-- Verify the column was added successfully:
DESCRIBE workers;

-- Test that HR queries will work:
SELECT id, employee_id, first_name, last_name, notes FROM workers LIMIT 1;
