from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from f2.app import F2Commander


class WithF2App:
    """Provides a typed property for F2Commander App."""

    @property
    def app_(self) -> "F2Commander":
        return self.app  # type: ignore
