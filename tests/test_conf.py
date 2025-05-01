# tests/conftest.py

import sys
import types

# Create a fake 'mysql' module and its 'mysql.connector' submodule


def _create_mysql_stub():
    mysql_mod = types.ModuleType('mysql')
    connector_mod = types.ModuleType('mysql.connector')
    # Provide a dummy Error exception
    connector_mod.Error = Exception
    # Default connect raises an OperationalError to simulate absence

    def connect_stub(**kwargs):
        raise connector_mod.Error("MySQL Connection not available.")
    connector_mod.connect = connect_stub
    mysql_mod.connector = connector_mod
    # Insert into sys.modules
    sys.modules['mysql'] = mysql_mod
    sys.modules['mysql.connector'] = connector_mod


_create_mysql_stub()
