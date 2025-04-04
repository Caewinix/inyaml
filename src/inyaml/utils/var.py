from typing import Dict, Any
import inspect


def back_locals() -> Dict[str, Any]:
    return inspect.currentframe().f_back.f_back.f_locals


def back_globals() -> Dict[str, Any]:
    return inspect.currentframe().f_back.f_back.f_globals