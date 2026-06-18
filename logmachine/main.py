import json
import logging
import os
import re
import requests
import socketio
import sys
import time
import webbrowser
from datetime import datetime, timedelta


LM_CREDS_PATH = os.path.expanduser("~/.logmachine")


def _auth_headers(headers=None):
    auth_token = os.getenv("lm_auth_token")
    merged = dict(headers or {})
    if auth_token and "Authorization" not in merged and "authorization" not in merged:
        merged["Authorization"] = f"Bearer {auth_token}"
    return merged


def _persist_lm_creds(username=None, auth_token=None, expiry=None):
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
    if expiry:
        current["lm_expiry"] = expiry
        os.environ["lm_expiry"] = expiry

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
        print("\x1b[1mNOTE: For a better experience, use an API KEY\x1b[0m\n")

    started_at = time.time()
    poll_url = f"{central_url.rstrip('/')}/api/auth/device/poll"

    while time.time() - started_at < timeout_seconds:
        response = requests.post(poll_url, json={"device_code": device_code}, timeout=(5, 10))
        if response.status_code != 200:
            raise RuntimeError(f"Device login polling failed: {response.text}")

        result = response.json()
        status = result.get("status")
        if status == "approved":
            print("Device login approved! Finalizing authentication...")
            return {
                "token": result.get("token"),
                "username": (result.get("user") or {}).get("username"),
                "provider": result.get("provider"),
                "expires_in": result.get("expires_in")
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


class CustomFormatter(logging.Formatter):
    def __init__(self, *args, **kwargs):
        args = args if args[0] else ("""({username} @ \x1b[33m{module}{reset}) 🤌 CL Timing: {color}[ {timestamp} ]{reset}\n{level} {message}\n🏁""",)
        kwargs.setdefault('style', '{')

        super().__init__(*args, **kwargs)
        self.colors = {
            'DEBUG': '\x1b[36m',
            'INFO': '\x1b[34m',
            'WARNING': '\x1b[33m',
            'ERROR': '\x1b[31m',
            'SUCCESS': '\x1b[32m',
            'CRITICAL': '\x1b[41m',
            '*': '\x1b[37m'
        }
        self.reset = '\x1b[0m'
        self.bold = '\x1b[1m'
        self.level_formats = {
            'DEBUG': f"{self.bold}[ DEBUG ]{self.reset}",
            'INFO': f"{self.bold}[ INFO ]{self.reset}",
            'WARNING': f"{self.bold}[ WARNING ]{self.reset}",
            'ERROR': f"{self.bold}[ ERROR ]{self.reset}",
            'SUCCESS': f"{self.bold}[ SUCCESS ]{self.reset}",
            'CRITICAL': f"{self.bold} CRITICAL {self.reset}",
            '*': f"{self.bold}[ UNKNOWN ]{self.reset}"
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
        color = self.colors.get(levelname) or self.colors['*']
        module = record.__dict__.get('module')
        level_fmt = self.level_formats.get(levelname) or self.level_formats['*']
        level_fmt = f"{color}{level_fmt}{self.reset}"
        record.asctime = self.formatTime(record, self.datefmt)

        return self._fmt.format(
            **{
                **record.__dict__,
                "reset": self.reset,
                "color": color,
                "username": f"{self.colors['DEBUG']}{username}{self.reset}",
                "level": level_fmt,  # If you use levelname in your format string, your log will appear uncolored because levelname is used by the logging module internally. Use {level} in your format string to get colored levels.
                "message": record.getMessage(),
                "timestamp": f"{color}{record.asctime}{self.reset}",
                "module": f"{self.colors['WARNING']}{module}{self.reset}"
            }
        )


class SocketIOTransporter(logging.StreamHandler):
    """
    A class to handle the transport of log messages.
    This class is responsible for sending log messages to a central server.
    """
    formatter: CustomFormatter

    def __init__(self, central):
        super().__init__()
        self.central: dict = central
        self.sio = socketio.Client()
        try:
            self.sio.connect(self.central.get('url', ''),
                socketio_path=self.central.get('endpoint', '/api/socket.io/'),
                retry=True,
                auth={'token': os.getenv('lm_auth_token')}
            )
            self.sio.emit('join', {'room': self.central.get('room')})
            self.sio.on('log', self.log)
            self.sio.on('error', print)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to central server: {e}")

    def log(self, data):
        """
        Handle incoming log messages from the central server and log them locally
        Without sending them back to the central to avoid infinite loops.
        :param data: The log data received from the central server.
        """
        record = logging.LogRecord(
            name="Central",
            level=getattr(logging, data.get('level', 'INFO').upper(), logging.INFO),
            pathname=data.get('module', 'unknown') + " :external",
            lineno=0,
            msg=data.get('message', ''),
            args=(),
            exc_info=None
        )
        print(self.formatter.format(record))

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
            if self.sio.connected and record:
                self.sio.emit('log', {'room': self.central.get('room'), 'data': {
                    'user': get_login(),
                    'module': os.path.basename(os.path.dirname(record.pathname)) if record.pathname != '<stdin>' else 'terminal',
                    'level': record.levelname,
                    'timestamp': self.formatter.formatTime(record, self.formatter.datefmt),
                    'message': record.getMessage()
                }, 'auth_token': os.getenv('lm_auth_token')})

        except Exception:
            self.handleError(record)


class LogMachine(logging.Logger):
    def __init__(self, name="", **kwargs) -> None:
        super().__init__(name, level=kwargs.get('level', logging.DEBUG))
        self.log_file = kwargs.get('log_file') or ('logs.log' if self.level == 0 else f"{(logging._levelToName.get(self.level) or 'LOGS').lower()}.log")
        self.central = kwargs.get('central', None)

        # File handler
        fh = logging.FileHandler(self.log_file)
        fh.setLevel(self.level)
        self.formatter = CustomFormatter(
            kwargs.get("log_format") or kwargs.get("format"),
            datefmt=kwargs.get('datefmt', '%Y-%m-%dT%H:%M:%S')
        )

        if os.getenv('LM_LOADED') != 'true':
            creds_file_to_dict()

        if self.central:
            self.login(api_key=self.central.get('API_KEY') or self.central.get('api_key'))
            if not self.central.get('room'):
                self.central['room'] = get_login()

            ch = SocketIOTransporter(central=self.central)
        else:
            ch = logging.StreamHandler()

        ch.setLevel(self.level)

        fh.setFormatter(self.formatter)
        ch.setFormatter(self.formatter)
        self.addHandler(fh)
        self.addHandler(ch)

        logging.addLevelName(25, "SUCCESS")
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

        direct_api_key = api_key or os.getenv('LM_API_KEY') or os.getenv('lm_api_key')
        if direct_api_key:
            _persist_lm_creds(auth_token=direct_api_key)
            self.central.setdefault('headers', {})
            self.central['headers']['Authorization'] = f"Bearer {direct_api_key}"
            self._sync_identity_from_session()

        elif self.central.get("headers", {}).get("Authorization"):
            self._sync_identity_from_session()

        elif os.getenv('lm_auth_token') and os.getenv('lm_expiry') and datetime.fromisoformat(os.getenv('lm_expiry', str(datetime.now()))) > datetime.now():
            self._sync_identity_from_session()

        else:
            result = _sdk_login_via_device_flow(self.central.get('url', ''), timeout_seconds=timeout_seconds)
            token = result.get('token')
            if not token:
                raise RuntimeError("Login completed without an auth token.")

            username = result.get('username')
            _persist_lm_creds(username=username, auth_token=token, expiry=(str(datetime.now() + timedelta(seconds=result.get('expires_in', 0)))))
            self.central.setdefault('headers', {})
            if 'Authorization' not in self.central['headers'] and 'authorization' not in self.central['headers']:
                self.central['headers']['Authorization'] = f"Bearer {token}"

            self._sync_identity_from_session()


    def logout(self) -> None:
        """
        Clear stored credentials and log out from central server.
        """
        if self.central:
            _persist_lm_creds(username='', auth_token='', expiry='')
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

    def new_level(self, level_name: str, level_num: int, ansi_color="\x1b[37m") -> None:
        """
        Dynamically add a new logging level.

        :param level_name: Name of the new logging level.
        :param level_num: Numeric value of the new logging level.
        :param ansi_color: The color in which the level's logs will appear
        """
        if level_num and logging._levelToName.get(level_num):
            raise Exception("The level you're trying to declare already exists")

        if not hasattr(self, level_name) and self.isEnabledFor(level_num):
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
    return LogMachine('default_logger', debug_level=0, verbose=False, central={ 'url': 'https://logmachine.org' })


logging.setLoggerClass(LogMachine)
