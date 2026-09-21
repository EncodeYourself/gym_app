from app.interface.ui.sidebar import render_grouped_sidebar
from app.interface.utils.logging import setup_logging

setup_logging()

def main() -> None:
    render_grouped_sidebar()

if __name__ == "__main__":
    main()