import logging


def setup_logger():
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/server.log", mode="a"),
        ]
    )
