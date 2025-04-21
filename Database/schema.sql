-- log prescription bills
CREATE TABLE pharmacy_logs (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    prescription_id INT NOT NULL,
    pharmacy_id INT NOT NULL,
    patient_id INT NOT NULL,
    amount_billed DECIMAL(10,2) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prescription_id) REFERENCES prescriptions(prescription_id),
    FOREIGN KEY (pharmacy_id) REFERENCES pharmacies(pharmacy_id),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);
-- add section for pricing inventory
ALTER TABLE pharmacy_inventory ADD COLUMN price DECIMAL(10,2) DEFAULT 0.00;

-- remove unused column on table
ALTER TABLE pharmacy_logs DROP COLUMN amount_billed;

-- add section for pharmacists to have a specific location column 
ALTER TABLE users ADD COLUMN pharmacy_id INT;

