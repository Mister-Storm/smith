import logging

from smith.core.logging import setup_logging


def test_setup_logging_verbose():
    setup_logging(verbose=True)
    assert logging.getLogger().level == logging.DEBUG


def test_setup_logging_default():
    setup_logging(verbose=False)
    assert logging.getLogger().level == logging.INFO
