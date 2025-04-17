-- Insert test user
INSERT INTO users (email, password_hash, user_type)
VALUES ('test_patient@example.com', 'testpass', 'patient');

-- Insert matching patient (get correct user_id manually if needed)
-- Run this to get the new user's ID:
-- SELECT user_id FROM users WHERE email = 'test_patient@example.com';

-- Assuming user_id = 999 just for mock purposes:
INSERT INTO patients (
  user_id, first_name, last_name, address, phone_number, zip_code, is_active
) VALUES (
  999, 'Test', 'Patient', '999 Example Rd', '555-0999', '99999', TRUE
);

--  Insert prescription for patient
INSERT INTO prescriptions (
  prescription_id, doctor_id, patient_id, pharmacy_id,
  medication_name, dosage, instructions, status
) VALUES (
  999, 1, 999, 1, 'TestMed', '100mg', 'Take once daily', 'pending'
);

--  Insert inventory to match prescription
INSERT INTO pharmacy_inventory (pharmacy_id, drug_name, stock_quantity)
VALUES (1, 'TestMed', 10);
