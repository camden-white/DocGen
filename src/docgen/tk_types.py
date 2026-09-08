"""Precise contracts for Tk APIs whose upstream stubs leave arguments untyped."""

from collections.abc import Callable
from typing import Protocol, overload


class TclCommands(Protocol):
    """Register a no-argument application callback with the Tcl interpreter."""

    def createcommand(self, name: str, callback: Callable[[], None], /) -> None: ...


class Scrollable(Protocol):
    """Tk view methods query a range or accept string arguments from a scrollbar."""

    @overload
    def xview(self) -> tuple[float, float]: ...
    @overload
    def xview(self, command: str, *args: str) -> None: ...

    @overload
    def yview(self) -> tuple[float, float]: ...
    @overload
    def yview(self, command: str, *args: str) -> None: ...


class IconWindow(Protocol):
    """Window-manager icon API used when launching on Windows."""

    def iconbitmap(self, bitmap: str) -> str: ...
