# LogMachine Python Logger

[![PyPI version](https://badge.fury.io/py/logmachine.svg)](https://badge.fury.io/py/logmachine)[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> Collective, beautiful logging system for distributed developers

It is an improvement over the standard Python logging module, with a focus on team-based logging, centralization and better log formatting.
It is designed to be easy to use, with a simple interface that allows developers to log messages in a structured and consistent way.

**logmachine** helps teams log smarter. All from a standard Python logging interface.

---

## Features

- **Color-coded terminal logs** (DEBUG, INFO, WARNING, ERROR, SUCCESS, etc)
- **Log forwarding** to a central server
- **Custom log levels** (add your own with `.new_level(...)`)
- **Custom log formatting** via `log_format` and `datefmt`
- **User identity tracking** for team-based logs
- **Pluggable backends**: send logs to a central server or local files
- **Simple JSON output** for web dashboards or collectors
- Strips ANSI escape codes from logs for clean parsing
- Automatically resolves usernames and session tokens in `~/.logmachine`

---

## Installation

```bash
pip install logmachine
```

---

## Usage

### Basic Setup

```python
from logmachine import LogMachine

# Create a simple logger without central logging
# Providing a non-empty string initializes the logger with that name, else the root logger is used to collect every single log in the python process.
logger = LogMachine("myapp", level=1)

logger.info("Hello, world!")
logger.error("An error occurred!")
logger.success("Operation completed successfully!")
logger.debug("Debugging information here.")
logger.warning("This is a warning message.")
```

### Custom Log Formatting

```python
from logmachine import LogMachine

logger = LogMachine(
    "myapp",
    level=1,
    format="({username} @ {module}) [ {timestamp} ] {level} {message}",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger.info("Hello with a custom format!")
```

The `log_format` string supports:
* `{username}`
* `{timestamp}`
* `{level}`
* `{message}`
* `{color}`
* `{reset}`
* Plus all other values in a `LogRecord` like `pathname`, `filename`, `lineno`, `module`, `funcName`, etc. (See [Python Logging LogRecord](https://docs.python.org/3/library/logging.html#logrecord-attributes))

### With Central Logging

You can use the default logger with central logging pointing to "https://logmachine.org"  

```python
from logmachine import default_logger
logger = default_logger()
logger.info("This log is sent to the LogMachine default central server!")
```

This is the default central logging server for logmachine, and you can create your own room there for free.
To use your own central logging server, provide the configuration as shown below:

```python
logger_config = {
    "url": "https://logmachine.org",  # Base server URL
    "room": "team_alpha",             # Your organization or room. This is optional and defaults to your username
    "endpoint": "/api/socket.io/",    # Optional. Defaults to /api/socket.io/ for Socket.IO transport.
    "api_key": "your_api_key",        # Optional. This is for the best authentication experience
    "headers": {"Authorization": "Bearer token"}, # Optional. The central server should know your username based on the token you provide here.
}
logger = LogMachine("with_central", level=0, central=logger_config)
logger.success("Central logging is working!")
```

### Browser Login for Central Logging

If your central server supports LogMachine auth endpoints, you can open a browser login flow
directly from the SDK. The provider selection (Google/GitHub) happens in the browser UI.

```python
from logmachine import LogMachine

logger = LogMachine("with_central", central={
    "url": "https://logmachine.org",
    "room": "team_alpha",
})
# LogMachine opens a browser session, then waits for you to log in.

logger.info("Now logging as an authenticated user")
```

What LogMachine does:

* Opens your browser to the central auth page or uses your API KEY if provided
* Waits for user to complete authentication (if using browser login)
* Stores the authentication, and continues to logging

### Non-Interactive Server Login using an API Key (Recommended)

For headless environments, generate an API key from your LogMachine profile page and put it in your env or pass it directly into the config. This allows you to authenticate without any browser interaction while still associating logs with your user identity.

```python
from logmachine import LogMachine

logger = LogMachine("with_central", central={
    "url": "https://logmachine.org",
    "room": "team_alpha",
    "api_key": "your_api_key_here"
})

logger.info("Authenticated without browser interaction")
```

We recommend setting the `LM_API_KEY` environment variable instead of passing `api_key` directly.

---

## Log Format

Every log includes:

* Username (resolved automatically or via server)
* Module directory
* Timestamp
* Level (INFO, ERROR, etc.)
* Message

Sample (terminal):

```
(you @ your_app) 🤌 CL Timing: [ 2025-08-04T11:23:52 ]
[ INFO ] Server started on port 8000
🏁
```

<img width="732" height="570" alt="Image" src="https://github.com/user-attachments/assets/cfb6b01d-0749-4e71-9881-c2e702a5c2c7" />

---

## Advanced

### Add Your Own Log Level

```python
logger.new_level("CRITICAL_HACK", 60)
logger.new_level("CRITICAL_HACK", 60, ansi_color="\033[38;5;13m")  # Optional color... does your girlfriend love pink? Maybe you should be in a relationship with your terminal.
logger.critical_hack("Zero day found!")
```

---

## Parse & Export

### Convert Logs to JSON

This is useful for sending logs to web dashboards or log collectors that expect JSON.
It reads the your log files, parses the log entries, and outputs them as JSON objects.

```python
json_logs = logger.jsonifier()
for entry in json_logs:
    print(entry)
    # Or even send them to a web dashboard or log collector!
```

---

## 📡 Central Server Compatibility

For central logging, your server should expose an endpoint for Socket.IO transport like:
* `/api/socket.io/` (for Socket.IO transport, expects auth token in connection handshake and processes logs accordingly)

To use Socket.IO transport, your central server must support this event:

* `log`: Receives log payloads: `{ room: string, data: object }`

---

## Security

* HTTP headers (e.g. `Authorization`) can be injected
* Central log transmission is fully customizable

---

## Configuration Summary

| Param           | Type   | Description                                        |
| --------------- | ------ | -------------------------------------------------- |
| `url`           | `str`  | Central server base URL                            |
| `room`          | `str`  | Logical group or org name                          |
| `endpoint`      | `str`  | Socket.IO endpoint path for central transport (default: `/api/socket.io/`) |
| `log_format`    | `str`  | Custom message template for log output             |
| `datefmt`       | `str`  | Timestamp format for log messages (default: `%Y-%m-%dT%H:%M:%S`) |
| `api_key`       | `str`  | API key for non-interactive auth (optional)        |
| `headers`       | `dict` | Extra headers to send (e.g. auth token)            |

---

## License

MIT License

---

## Author

[Buffer Punk](https://bufferpunk.com)
[Log Machine](https://logmachine.org)
[GitHub](https://github.com/logmachine/python)

---

## ❤️ Contribute

PRs and issues are welcome!
This tool is built for devs who want **beautiful logs with distributed brains**.
Let’s make debugging fun again.
