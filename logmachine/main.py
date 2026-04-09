import atexit
import json
import logging
import os
import queue
import re
import requests
import sys
import time
import webbrowser
from logging.handlers import QueueHandler, QueueListener


try:
    """
    We've removed the socketio and websockets dependency from the core of LogMachine to make it more lightweight and avoid forcing users to install it.
    The Logger will use socketio if available in the environment, otherwise it will fall back to HTTP requests for log transport.
    Socketio is generally more efficient for real-time log transport,
    while HTTP can be used as a fallback for environments where socketio is not available or not desired.
    Socketio takes precedence over HTTP if both are available, as it provides a more robust and efficient transport mechanism for real-time logging.
    """

    import socketio
except ImportError:
    pass


LM_CREDS_PATH = os.path.expanduser("~/.LM_CREDS")


def _auth_headers(headers=None):
    auth_token = os.getenv("lm_auth_token")
    merged = dict(headers or {})
    if auth_token and "Authorization" not in merged and "authorization" not in merged:
        merged["Authorization"] = f"Bearer {auth_token}"
    return merged


def _persist_lm_creds(username=None, auth_token=None):
    current = {}
    if os.path.exists(LM_CREDS_PATH):
        with open(LM_CREDS_PATH, "r") as f:
            for line in f.read().splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    current[key.strip()] = value.strip()

    if username:
        current["lm_username"] = username
        os.environ["lm_username"] = username
    if auth_token:
        current["lm_auth_token"] = auth_token
        os.environ["lm_auth_token"] = auth_token

    with open(LM_CREDS_PATH, "w") as f:
        for key, value in current.items():
            f.write(f"{key}={value}\n")


def _sdk_login_via_device_flow(central_url, timeout_seconds=180):
    start_url = f"{central_url.rstrip('/')}/api/auth/device/start"
    start_response = requests.post(start_url, timeout=(5, 10))
    if start_response.status_code != 200:
        raise RuntimeError(f"Failed to start device login flow: {start_response.text}")

    payload = start_response.json()
    device_code = payload.get("device_code")
    verification_uri_complete = payload.get("verification_uri_complete")
    user_code = payload.get("user_code")
    interval = max(int(payload.get("interval", 3)), 1)

    if not device_code or not verification_uri_complete:
        raise RuntimeError("Device flow did not return the required login details")

    web_base = central_url.rstrip("/")
    if web_base.endswith("/api"):
        web_base = web_base[:-4]

    fallback_url = verification_uri_complete
    if not fallback_url.startswith("http"):
        fallback_url = f"{web_base}/{verification_uri_complete.lstrip('/')}"

    opened = webbrowser.open(fallback_url)
    if not opened:
        print("Open this URL on any device to log in:")
        print(f"  {fallback_url}")

    if verification_uri_complete:
        print("To authenticate this device:")
        print(f"  1) Open: {verification_uri_complete}")
        print(f"  2) Enter code: {user_code} (if not auto-filled)")

    started_at = time.time()
    poll_url = f"{central_url.rstrip('/')}/api/auth/device/poll"

    while time.time() - started_at < timeout_seconds:
        response = requests.post(poll_url, json={"device_code": device_code}, timeout=(5, 10))
        if response.status_code != 200:
            raise RuntimeError(f"Device login polling failed: {response.text}")

        result = response.json()
        status = result.get("status")
        if status == "approved":
            return {
                "token": result.get("token"),
                "username": (result.get("user") or {}).get("username"),
                "provider": result.get("provider"),
            }
        if status == "expired":
            raise TimeoutError("Login code expired before authentication completed")

        time.sleep(interval)

    raise TimeoutError("Timed out waiting for device login to complete")


def creds_file_to_dict():
    try:
        creds_path = LM_CREDS_PATH
        if os.path.exists(creds_path):
            with open(creds_path, 'r') as f:
                creds_content = f.read().strip()
                for line in creds_content.splitlines():
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
        os.environ['LM_LOADED'] = 'true'
    except Exception:
        os.environ['LM_LOADED'] = 'false'


def get_login():
    """
    Get the current user's login name.
    :return: The login name of the current user.
    """
    try:
        if os.getenv('LM_LOADED') != 'true':
            creds_file_to_dict()

        return os.getenv('lm_username') or os.getlogin()
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
        self.central = kwargs.get('central', None)
        self.session = requests.Session()  # Use a session for connection pooling

    def close(self):
        try:
            self.session.close()
        except Exception:
            pass
        return super().close()

    def emit(self, record):
        try:
            super().emit(record)
            if not self.central or not self.central.get('room'):
                raise ValueError("""Central configuration must include 'room' for log transport.
                    Example: {'url': 'http://central-server/api/logs', 'room': 'my_organization_name'}""")

            if record:
                response = self.session.post(
                    f"{self.central.get('url', '') + self.central.get('endpoint', '/api/logs')}?room={self.central.get('room', '')}",
                    json={
                        'user': get_login(),
                        'module': os.path.basename(os.path.dirname(record.pathname)) if record.pathname != '<stdin>' else 'stdin',
                        'level': record.levelname,
                        'timestamp': self.formatter.formatTime(record, self.formatter.datefmt),
                        'message': record.getMessage()
                    },
                    timeout=(3, 3),
                    headers={**_auth_headers(self.central.get('headers', {})), 'Content-Type': 'application/json'}
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
        self.central = kwargs.get('central', {})
        self.sio = socketio.Client()
        if not self.central:
            raise ValueError("""Central configuration must be provided for SocketIOTransporter.
                Example: {'url': 'http://central-server.com/api/socket.io/', 'room': 'my_organization_name'}
            """)
        try:
            self.sio.connect(self.central.get('url', ''),
                headers=_auth_headers(self.central.get('headers', {})),
                socketio_path=self.central.get('endpoint', '/api/socket.io/'),
                wait_timeout=3
            )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to central server via SocketIO: {e}")

    def close(self):
        try:
            if self.sio.connected:
                self.sio.disconnect()
        except Exception:
            pass
        return super().close()

    def emit(self, record):
        try:
            super().emit(record)
            if self.central and self.sio.connected and record:
                if not self.central.get('room'):
                    raise ValueError("""Central configuration must include 'room' for log transport.
                        Example: {'url': 'http://central-server.com/api/socket.io/', 'room': 'my_organization_name'}
                    """)

                self.sio.emit('log', {'room': self.central.get('room'), 'data': {
                    'user': get_login(),
                    'module': os.path.basename(os.path.dirname(record.pathname)) if record.pathname != '<stdin>' else 'stdin',
                    'level': record.levelname,
                    'timestamp': self.formatter.formatTime(record, self.formatter.datefmt),
                    'message': record.getMessage()
                }, 'auth_token': os.getenv('lm_auth_token')})

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
        username = get_login()

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


class DebugLevelFilter(logging.Filter):
    def __init__(self, debug_level):
        super().__init__()
        self.debug_level = debug_level
        self.level_map = {
            1: ['ERROR'],
            2: ['SUCCESS'],
            3: ['WARNING'],
            4: ['INFO'],
            5: ['ERROR','WARNING'],
            6: ['INFO','SUCCESS'],
            7: ['ERROR','WARNING','INFO']
        }

    def filter(self, record):
        if self.debug_level == 0:
            return True

        allowed = self.level_map.get(self.debug_level, [])
        return record.levelname in allowed


class LogMachine(logging.Logger):
    def __init__(self, name="", *args, **kwargs) -> None:
        super().__init__(name, *args, level=int(kwargs.get('debug_level', 0)))
        logging.addLevelName(25, "SUCCESS")
        self.log_file = kwargs.get('log_file', 'logs.log')
        self.error_file = kwargs.get('error_file', 'errors.log')
        self.debug_level = int(kwargs.get('debug_level', 0))
        self.verbose = sys.argv[1:] and '--verbose' in sys.argv[1:]
        self.central = kwargs.get('central', None)
        self.queue = queue.Queue(maxsize=10000)

        if os.getenv('LM_LOADED') != 'true':
            creds_file_to_dict()

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
               After getting the username, we store it in the user's home directory in a file named `.LM_CREDS`.
               This way, the user can change it at any time, and it will be used in all future logs without needing to request it again.
            """
            self.login()
            if not self.central.get('room'):
                self.central['room'] = f"{get_login()}_logs"

            if 'socketio' not in globals():
                ch = HTTPTransporter(central=self.central)
            else:
                ch = SocketIOTransporter(central=self.central)
        else:
            ch = logging.StreamHandler()

        ch.setLevel(logging.DEBUG)

        self.formatter = CustomFormatter('%(asctime)s %(levelname)s %(message)s', datefmt='%Y-%m-%dT%H:%M:%S%z')
        fh.setFormatter(self.formatter)
        eh.setFormatter(self.formatter)
        ch.setFormatter(self.formatter)
        self.addHandler(QueueHandler(self.queue))

        # Filter console output based on debug_level
        self.debug_filter = DebugLevelFilter(self.debug_level if not self.verbose else 0)
        ch.addFilter(self.debug_filter)
        self.listener = QueueListener(self.queue, fh, eh, ch)
        self.listener.start()
        atexit.register(self.listener.stop)
        sys.stdout.write("LogMachine initialized with debug level {} with{}\n".format(
                self.debug_level,
                self.central and
                f" central logging to {self.central.get('url', '')} in room: {self.central.get('room')}" or
                "out central logging"
            )
        )

    def _sync_identity_from_session(self):
        if not self.central:
            return

        token = os.getenv('lm_auth_token')
        if not token:
            return

        try:
            session_url = f"{self.central.get('url', '').rstrip('/')}/api/auth/session"
            response = requests.get(
                session_url,
                headers=_auth_headers(self.central.get('headers', {})),
                timeout=(3, 3),
            )
            if response.status_code == 200:
                payload = response.json()
                user = payload.get('user', {})
                username = user.get('username')
                if username:
                    _persist_lm_creds(username=username, auth_token=token)
        except Exception:
            pass

    def login(self, timeout_seconds=180, api_key=None):
        """
        Authenticate logger with either an API key or device flow.

        :param timeout_seconds: Maximum time to wait for browser callback.
        :param api_key: Optional API key for non-interactive environments.
        :return: self
        """
        if not self.central or not self.central.get('url'):
            raise ValueError("Login requires central logging configuration with a 'url'.")

        if os.getenv('lm_auth_token') and os.getenv('lm_username'):
            sys.stdout.write("Already logged in with central server. Using existing credentials.\n")

        direct_api_key = api_key or os.getenv('LM_API_KEY') or os.getenv('lm_api_key')
        if direct_api_key:
            _persist_lm_creds(auth_token=direct_api_key)
            self.central.setdefault('headers', {})
            self.central['headers']['Authorization'] = f"Bearer {direct_api_key}"
            self._sync_identity_from_session()
            return self
        
        elif self.central.get("headers", {}).get("Authorization") or os.getenv('lm_auth_token'):
            self._sync_identity_from_session()

        else:
            result = _sdk_login_via_device_flow(self.central.get('url', ''), timeout_seconds=timeout_seconds)
            token = result.get('token')
            if not token:
                raise RuntimeError("Login completed without an auth token.")

            username = result.get('username')
            _persist_lm_creds(username=username, auth_token=token)
            self.central.setdefault('headers', {})
            if 'Authorization' not in self.central['headers'] and 'authorization' not in self.central['headers']:
                self.central['headers']['Authorization'] = f"Bearer {token}"

            self._sync_identity_from_session()

        return self

    def logout(self) -> None:
        """
        Clear stored credentials and log out from central server.
        """
        _persist_lm_creds(username='', auth_token='')
        self.central["headers"] = {k: v for k, v in self.central.get("headers", {}).items() if k.lower() != "authorization"}
        sys.stdout.write("Logged out and cleared credentials.\n")

    def success(self, msg, *args, **kwargs) -> None:
        """
        Log a message with level SUCCESS (25).
        This level is built in because it's commonly used for indicating successful operations that are more significant than INFO but not as critical as WARNING.
        And we like to celebrate successes! 🟢

        :param msg: The message to log.
        :param args: Additional arguments for the log message.
        :param kwargs: Additional keyword arguments for the log message.
        """
        if self.isEnabledFor(25):
            self._log(25, msg, args, stacklevel=2, **kwargs)

    def new_level(self, level_name: str, level_num: int, ansi_color="\x1b[37m", filter_num=None) -> None:
        """
        Dynamically add a new logging level.
        :param level_name: Name of the new logging level.
        :param level_num: Numeric value of the new logging level.
        :param method_name: Optional method name for the new level.
        """
        if not hasattr(self, level_name):
            logging.addLevelName(level_num, level_name)
            setattr(self, level_name.lower(), lambda msg, *args, **kwargs: self._log(level_num, msg, args, stacklevel=2, **kwargs))
            self.setLevel(min(self.level, level_num))  # Ensure the logger's level is set appropriately
            self.formatter.set_color(level_name, ansi_color) # Add color formatting for the new level
            if filter_num is not None:
                self.debug_filter.level_map[filter_num] = self.debug_filter.level_map.get(filter_num, []) + [level_name]

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
    return LogMachine('default_logger', debug_level=0, verbose=False, central={ 'url': 'https://logmachine.bufferpunk.com' }).login()


logging.setLoggerClass(LogMachine)
