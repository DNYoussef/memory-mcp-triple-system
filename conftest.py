"""
Root test configuration.
Disables pytest-flask which conflicts with FastAPI testing.
"""

# Disable pytest-flask plugin globally
pytest_plugins = []
