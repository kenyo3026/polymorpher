import inspect
import sys

from .load import *
from .search import *
from .search_and_replace import *
from .attempt_completion import *
from .write import *
from .execute import *


_current_module = sys.modules[__name__]

TOOL_FUNCS = {
    name: func
    for name, func in _current_module.__dict__.items()
    if inspect.isfunction(func) and not name.startswith("__")
}