# -*- coding: utf-8 -*-
"""Application entry point."""
from __future__ import annotations

from .gui.app import create_app


def main() -> None:
    app = create_app()
    app.mainloop()


if __name__ == "__main__":
    main()
