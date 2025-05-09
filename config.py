import os

DB_CONFIG = {
    'host':     os.getenv('DB_HOST', 'localhost'),
    'user':     os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASS', 'Root123!'),
    'database': os.getenv('DB_NAME', 'weight_loss_clinic'),
}
