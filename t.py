from logmachine import LogMachine

logger = LogMachine()

logger.success("Logger initialized")
logger.info("This is an info message")
logger.warning("This is a warning message")
logger.error("This is an error message")
logger.debug("This is a debug message")

logger.info("You can capture all logs from your app!")
