import atexit
import os
import re
import json
import logging
import requests
import socketio
import queue
from logging.handlers import QueueHandler, QueueListener


def get_login():
    """
    Get the current user's login name.
    :return: The login name of the current user.
    """
    try:
        if not os.path.exists(os.path.expanduser("~/.cl_username")):
            return os.getlogin()
        else:
            with open(os.path.expanduser("~/.cl_username"), 'r') as f:
                os.environ['CL_USERNAME'] = f.read().strip()
            return os.environ['CL_USERNAME']
    except Exception:
        return os.environ.get('USER', 'unknown')


class HTTPTransporter(logging.StreamHandler):
    """
    A class to handle the transport of log messages using HTTP requests.
    This class sends log messages to a central server via HTTP POST requests.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the RequestsTransporter with optional log parser and central configuration.
        :param args: Positional arguments for the parent class.
        :param kwargs: Keyword arguments including 'log_parser' and 'central' configuration.
        """
        super().__init__()
        self.parse_log = kwargs.get('log_parser')
        self.central = kwargs.get('central', None)

    def emit(self, record):
        try:
            msg = self.format(record)
            super().emit(record)
            if not self.central or not self.central.get('room'):
                raise ValueError("""Central configuration must include 'room' for log transport.
                    Example: {'url': 'http://central-server/api/logs', 'room': 'my_organization_name'}""")

            log_data = self.parse_log(msg)
            if log_data:
                response = requests.post(
                    f"{self.central.get('url', '') + self.central.get('endpoint', '/api/logs')}?room={self.central.get('room', '')}",
                    json=log_data,
                    headers={"Content-Type": "application/json", **self.central.get('headers', {})}
                )
                if response.status_code != 200:
                    raise Exception(f"Failed to send log to central: {response.text}")

        except Exception:
            self.handleError(record)


class SocketIOTransporter(logging.StreamHandler):
    """
    A class to handle the transport of log messages.
    This class is responsible for sending log messages to a central server.
    """
    def __init__(self, *args, **kwargs):
        super().__init__()
        self.parse_log = kwargs.get('log_parser')
        self.central = kwargs.get('central', None)
        self.sio = socketio.Client()
        if self.central:
            self.sio.connect(self.central.get('url', ''), headers=self.central.get('headers', {}), socketio_path=self.central.get('socketio_path', '/api/socket.io/'))

    def emit(self, record):
        try:
            msg = self.format(record)
            super().emit(record)
            if self.central:
                if not self.central.get('room'):
                    raise ValueError("""
                                     Central configuration must include 'room' for log transport.
                                        Example: {'url': 'http://central-server.com/api/logs', 'room': 'my_organization_name'}
                                     """)

                log_data = self.parse_log(msg)
                if log_data:
                    self.sio.emit('log', {'room': self.central.get('room'), 'data': log_data})

        except Exception:
            self.handleError(record)


class CustomFormatter(logging.Formatter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.colors = {
            'DEBUG': '\x1b[36m',
            'INFO': '\x1b[34m',
            'WARNING': '\x1b[33m',
            'ERROR': '\x1b[31m',
            'SUCCESS': '\x1b[32m'
        }
        self.reset = '\x1b[0m'
        self.bold = '\x1b[1m'
        self.level_formats = {
            'DEBUG': self.bold + '[ DEBUG ]' + self.reset,
            'INFO': self.bold + '[ INFO ]' + self.reset,
            'WARNING': self.bold + '[ WARNING ]' + self.reset,
            'ERROR': self.bold + '[ ERROR ]' + self.reset,
            'SUCCESS': self.bold + '[ SUCCESS ]' + self.reset
        }

    def set_color(self, levelname: str, color_code: str):
        """
        Set a custom color for a specific log level.
        :param levelname: The name of the log level (e.g., 'DEBUG', 'INFO').
        :param color_code: The ANSI color code to use for the specified log level.
        """
        self.colors[levelname] = color_code
        self.level_formats[levelname] = f"{self.bold}[ {levelname} ]{self.reset}"

    def format(self, record) -> str:
        username = os.environ.get('CL_USERNAME') or get_login()

        levelname = record.levelname
        color = self.colors.get(levelname, '')
        level_fmt = self.level_formats.get(levelname, f'{levelname}')
        level_fmt = f"{color}{level_fmt}{self.reset}"
        record.asctime = self.formatTime(record, self.datefmt)
        module_file = record.pathname
        parent_dir = os.path.basename(os.path.dirname(record.pathname)) if module_file != '<stdin>' else 'stdin'

        return f"""{self.colors.get('DEBUG')}({username}{self.reset} @ {self.colors.get('WARNING') + parent_dir + self.reset}) 🤌 CL Timing: {color}[ {record.asctime} ]{self.reset}
{level_fmt} {record.getMessage()}
🏁"""

class LogMachine(logging.Logger):
    def __init__(self, name="", *args, **kwargs) -> None:
        super().__init__(name, *args, level=int(kwargs.get('debug_level', 0)))
        logging.addLevelName(25, "SUCCESS")
        self.log_file = kwargs.get('log_file', 'logs.log')
        self.error_file = kwargs.get('error_file', 'errors.log')
        self.debug_level = int(kwargs.get('debug_level', 0))
        self.verbose = kwargs.get('verbose', False)
        self.central = kwargs.get('central', None)
        self.queue = queue.Queue()

        # Remove existing handlers
        for h in self.handlers[:]:
            self.removeHandler(h)

        # File handlers
        fh = logging.FileHandler(self.log_file)
        fh.setLevel(self.debug_level)
        eh = logging.FileHandler(self.error_file)
        eh.setLevel(logging.ERROR)

        # Console handler
        if self.central:
            """
               The central uses usernames to group logs.
               OS usernames are used to identify the user, meaning names can clash.
               Therefore, we avoid a user having to define a username, rather, ask the central server to provide it.
               After getting the username, we store it in the user's home directory in a file named `.cl_username`.
               This way, the user can change it at any time, and it will be used in all future logs without needing to request it again.
            """
            if not os.path.exists(os.path.expanduser("~/.cl_username")):
                try:
                    login = get_login()
                    response = requests.get(f"{self.central.get('url', '')}/api/get_username?base={login}")
                    if response.status_code == 200:
                        os.environ['CL_USERNAME'] = response.json().get('username') or 'unknown' # Unknown will probably never be reached, but it's a fallback.
                        if os.environ.get('CL_USERNAME') != 'unknown':
                            with open(os.path.expanduser("~/.cl_username"), 'w') as f:
                                f.write(os.environ['CL_USERNAME'])
                    else:
                        os.environ['CL_USERNAME'] = 'unknown'
                except Exception:
                    os.environ['CL_USERNAME'] = 'unknown'
            else:
                get_login()

            if not kwargs.get('attached', False) and not self.central.get('socketio', False):
                ch = HTTPTransporter(log_parser=self.parse_log, central=self.central)
            else:
                ch = SocketIOTransporter(log_parser=self.parse_log, central=self.central)
        else:
            ch = logging.StreamHandler()

        ch.setLevel(logging.DEBUG)

        self.formatter = CustomFormatter('%(asctime)s %(levelname)s %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
        fh.setFormatter(self.formatter)
        eh.setFormatter(self.formatter)
        ch.setFormatter(self.formatter)
        self.addHandler(QueueHandler(self.queue))

        # Filter console output based on debug_level
        class DebugLevelFilter(logging.Filter):
            def __init__(self, debug_level):
                super().__init__()
                self.debug_level = debug_level

            def filter(self, record):
                if self.debug_level == 0:
                    return True

                level_map = {
                    1: ['ERROR'],
                    2: ['SUCCESS'],
                    3: ['WARNING'],
                    4: ['INFO'],
                    5: ['ERROR','WARNING'],
                    6: ['INFO','SUCCESS'],
                    7: ['ERROR','WARNING','INFO']
                }
                allowed = level_map.get(self.debug_level, [])
                return record.levelname in allowed

        ch.addFilter(DebugLevelFilter(self.debug_level if not self.verbose else 0))
        self.listener = QueueListener(self.queue, fh, eh, ch)
        self.listener.start()
        atexit.register(self.listener.stop)
        self.info("LogMachine initialized with debug level {} with{}".format(
                self.debug_level,
                self.central and
                f" central logging to {self.central.get('url', '')}" or
                "out central logging"
            )
        )

    def success(self, msg, *args, **kwargs) -> None:
        if self.isEnabledFor(25):
            self._log(25, msg, args, stacklevel=2, **kwargs)

    def new_level(self, level_name: str, level_num: int, ansi_color="\x1b[37m") -> None:
        """
        Dynamically add a new logging level.
        :param level_name: Name of the new logging level.
        :param level_num: Numeric value of the new logging level.
        :param method_name: Optional method name for the new level.
        """
        if not hasattr(logging, level_name):
            logging.addLevelName(level_num, level_name)
            setattr(self, level_name.lower(), lambda msg, *args, **kwargs: self._log(level_num, msg, args, stacklevel=2, **kwargs))
            self.setLevel(min(self.level, level_num))  # Ensure the logger's level is set appropriately
            self.formatter.set_color(level_name, ansi_color) # Add color formatting for the new level

    def parse_log(self, log_text) -> dict | None:
        log_text = log_text.strip()
        ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
        end_escape = re.compile(r'🏁')
        clean = ansi_escape.sub('', log_text)

        # Match `(username @ folder) 🤌 CL Timing: [timestamp]`
        header_pattern = r"\((.*?) @ (.*?)\) 🤌 CL Timing: \[ (.*?) \]"
        header_match = re.search(header_pattern, clean)

        if not header_match:
            return

        user, module, timestamp = header_match.groups()
        lines = clean.splitlines()
        level_line = ' '.join(lines[1:]).strip() if len(lines) > 1 else ''

        level_match = re.match(r'\[(\s?\w+\s?)\]\s?(.*)', level_line)
        level = level_match.group(1) if level_match else "UNKNOWN"
        message = level_match.group(2) if level_match else ''

        return {
            "user": user,
            "module": module,
            "level": level.strip(),
            "timestamp": timestamp,
            "message": end_escape.sub('', message).strip()
        }

    def jsonifier(self) -> list:
        """
        Reads the log file and returns a list of JSON objects representing each log entry.
        Reserved for central web collection, intentionally not used in CLI.
        Returns:
            list: A list of JSON objects, each representing a log entry.
        """
        log_entries = []
        with open(self.log_file, 'r') as file:
            content = file.read()
            log_lines = content.split('\n🏁\n')  # Split by double newlines to separate
            for line in log_lines:
                if line.strip():
                    log_entry = self.parse_log(line)
                    if log_entry:
                        log_entries.append(json.dumps(log_entry))

        return log_entries


def default_logger():
    return LogMachine('default_logger', debug_level=0, verbose=False, central={
        'url': 'https://logmachine.bufferpunk.com',
        'room': f'{get_login()}_logs',
        'headers': {}
    })


logging.setLoggerClass(LogMachine)
