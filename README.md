# 🧠 LogMachine

> Collaborative, beautiful logging system for distributed developers

**logmachine** helps teams log smarter. It’s a fully pluggable logging system that supports colored output, JSON parsing, structured log forwarding via **HTTP or Socket.IO**, and log centralization — all from a standard Python logging interface.

---

## 🚀 Features

- 🔥 **Color-coded terminal logs** (DEBUG, INFO, WARNING, ERROR, SUCCESS)
- 📤 **Log forwarding** to a central HTTP or Socket.IO server
- 🪵 **Custom log levels** (add your own with `.new_level(...)`)
- 👥 **User identity tracking** for team-based logs
- 🧩 **Pluggable backends**: send logs to a central server or local files
- 📦 **Simple JSON output** for web dashboards or collectors
- 🧽 Strips ANSI escape codes from logs for clean parsing
- 🧠 Automatically resolves usernames and session tokens in `~/.LM_CREDS`

---

## ⚙️ Installation

```bash
pip install logmachine
```

---

## 🧰 Usage

### Basic Setup

```python
from logmachine import LogMachine

# Create a simple logger without central logging
# Providing a non-empty string initializes the logger with that name, else the root logger is used to collect every single log in the python process.
logger = LogMachine("myapp", debug_level=1)

logger.info("Hello, world!")
logger.error("An error occurred!")
logger.success("Operation completed successfully!")
logger.debug("Debugging information here.")
logger.warning("This is a warning message.")
```

### With Central Logging (HTTP or Socket.IO)

You can use the default logger with central logging pointing to "https://logmachine.bufferpunk.com"  

```python
from logmachine import default_logger
logger = default_logger()
logger.info("This log is sent to the LogMachine default central server!")
```

This is the default central logging server for logmachine, and you can create your own room there for free.
To use your own central logging server, provide the configuration as shown below:

```python
logger_config = {
    "url": "https://logmachine.bufferpunk.com",  # Base server URL
    "room": "team_alpha",                # Your organization or room
    "endpoint": "/api/logs",             # Optional, defaults to /api/logs for HTTP or /api/socket.io/ for Socket.IO transport.
    "headers": {"Authorization": "Bearer token"}, # The central server should know your username based on the token you provide here. This is optional and depends on your central server's authentication mechanism.
}
logger = LogMachine("with_central", debug_level=0, central=logger_config, socketio=True)
logger.success("Central logging is working!")
```

### Browser Login for Central Logging

If your central server supports LogMachine auth endpoints, you can open a browser login flow
directly from the SDK. The provider selection (Google/GitHub) happens in the browser UI.

```python
from logmachine import LogMachine

logger = LogMachine("with_central", central={
    "url": "https://logmachine.bufferpunk.com",
    "room": "team_alpha",
}).login()

logger.info("Now logging as an authenticated user")
```

What `.login()` does:

* Opens your browser to the central auth page
* Waits for a localhost callback to complete authentication
* Stores `lm_auth_token` and `lm_username` in `~/.LM_CREDS` for reuse
* Automatically attaches `Authorization: Bearer ...` to central log transport

### Non-Interactive Server Login (API Key)

For headless environments, generate an API key from your LogMachine profile page and pass it to `.login()`:

```python
from logmachine import LogMachine

logger = LogMachine("with_central", central={
    "url": "https://logmachine.bufferpunk.com",
    "room": "team_alpha",
}).login(api_key="lmk_your_api_key")

logger.info("Authenticated without browser interaction")
```

You can also use `LM_API_KEY` as an environment variable instead of passing `api_key` directly.

---

## 🎨 Log Format

Every log includes:

* ✅ Username (resolved automatically or via server)
* 📁 Module directory
* ⏱️ Timestamp
* 📦 Level (INFO, ERROR, etc.)
* 📝 Message

Sample (terminal):

```
(username @ myapp) 🤌 CL Timing: [ 2025-08-04T11:23:52 ]
[ INFO ] Server started on port 8000
🏁
```

---

## 🛠️ Advanced

### Add Your Own Log Level

```python
logger.new_level("CRITICAL_HACK", 60)
logger.new_level("CRITICAL_HACK", 60, color="\033[38;5;13m")  # Optional color... does your girlfriend love pink? Maybe you should be in a relationship with your terminal.
logger.critical_hack("Zero day found!")
```

---

## 📤 Parse & Export

### Convert Logs to JSON

This is useful for sending logs to web dashboards or log collectors that expect JSON.
It reads the your log files, parses the log entries, and outputs them as JSON objects.

```python
json_logs = log.jsonifier()
for entry in json_logs:
    print(entry)
```

---

## 📡 Central Server Compatibility

To use Socket.IO, your central server must support this event:

* `log`: Receives log payloads: `{ room: string, data: object }`

For central username resolution, your server should expose an endpoint like:

* `GET /api/get_username?base=localname`: Returns `{ "username": "..." }`

For browser auth with `.login()`, your server should also expose:

* `GET /api/auth/providers`
* `GET /api/auth/start/{provider}`
* `GET /api/auth/callback/{provider}`
* `GET /api/auth/session`

---

## 🤖 Environment Variables

* `lm_username`: Username override used by formatter and transport payload
* `lm_auth_token`: Bearer token automatically sent to central server when present
* Credentials are persisted in `~/.LM_CREDS`

---

## 🔐 Security

* HTTP headers (e.g. `Authorization`) can be injected
* Central log transmission is fully customizable

---

## 🔧 Configuration Summary

| Param           | Type   | Description                                        |
| --------------- | ------ | -------------------------------------------------- |
| `url`           | `str`  | Central server base URL                            |
| `room`          | `str`  | Logical group or org name                          |
| `endpoint`      | `str`  | HTTP endpoint for POST logs (default: `/api/logs` or `/api/socket.io/` for Socket.IO) |
| `headers`       | `dict` | Extra headers to send (e.g. auth token)            |

---

## 📄 License

MIT License

---

## 🙋‍♂️ Author

Mugabo Gusenga
[logmachine.bufferpunk.com](https://logmachine.bufferpunk.com)
[GitHub](https://github.com/logmachine/python)

---

## ❤️ Contribute

PRs and issues are welcome!
This tool is built for devs who want **beautiful logs with distributed brains**.
Let’s make debugging fun again.
