
#Be sure these were already ran prior should be on regular schema though 
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
-- add section for unique drugs 
ALTER TABLE pharmacy_inventory
    ADD CONSTRAINT unique_pharmacy_drug UNIQUE (pharmacy_id, drug_name);

#to display specific pharmacy id of login
select * from pharmacies;

#Insert prescriptions query. can copy paste to change name or status or pharmacy_id etc.

INSERT INTO prescriptions (
  prescription_id, doctor_id, patient_id, pharmacy_id,
  medication_name, dosage, instructions, status
) VALUES (
  17, 1, 6, 2, 'amoxicillin', '100mg', 'Take once daily', 'pending'
);
INSERT INTO prescriptions (
  prescription_id, doctor_id, patient_id, pharmacy_id,
  medication_name, dosage, instructions, status
) VALUES (
  18, 1, 6, 2, 'testMed', '100mg', 'Take once daily', 'pending'
);
INSERT INTO prescriptions (
  prescription_id, doctor_id, patient_id, pharmacy_id,
  medication_name, dosage, instructions, status
) VALUES (
  19, 1, 6, 2, 'ibuprofin', '100mg', 'Take once daily', 'pending'
);
