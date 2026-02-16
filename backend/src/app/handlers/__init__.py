"""
Email assistant event handlers

Import this module to register all handlers with the event system.
"""
from .message_handlers import *
from .task_handlers import *
from .scheduling_handlers import *
from .notification_handlers import *
from .task_handlers import *
from .webhook_handlers import *
from .vault_handlers import *

# Import this module in main.py to register all handlers
# Example: from app.handlers import *

