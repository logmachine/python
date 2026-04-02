# 🧠 logmachine 2.1.0

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
- 🧠 Automatically resolves usernames and saves them in `~/.cl_username`

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

```python
logger_config = {
    "url": "https://logmachine.bufferpunk.com",  # Base server URL
    "room": "team_alpha",                # Your organization or room
    "endpoint": "/api/logs",             # Optional, defaults to /api/logs
    "headers": {"Authorization": "Bearer token"},
    "socketio": True,                    # Set False to use HTTP
    "socketio_path": "/api/socket.io/"  # Optional
}
logger = LogMachine("with_central", debug_level=0, central=logger_config, socketio=True)
logger.success("Central logging is working!")
```

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
log.new_level("CRITICAL_HACK", 60)
log.critical_hack("Zero day found!")
```

---

## 📤 Parse & Export

### Convert Logs to JSON

```python
json_logs = log.jsonifier()
for entry in json_logs:
    print(entry)
```

---

## 📡 Central Server Compatibility

To use Socket.IO, your central server must support these events:

* `log`: Receives log payloads: `{ room: string, data: object }`
* `GET /api/get_username?base=localname`: Returns `{ "username": "..." }`

---

## 🤖 Environment Variables

* `CL_USERNAME`: Manually override detected username
* Automatically stored in `~/.cl_username` for persistent identity

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
| `endpoint`      | `str`  | HTTP endpoint for POST logs (default: `/api/logs`) |
| `headers`       | `dict` | Extra headers to send (e.g. auth token)            |
| `socketio`      | `bool` | Whether to use Socket.IO instead of HTTP           |
| `socketio_path` | `str`  | Path to socket.io on the server                    |

---

## 📄 License

MIT License

---

## 🙋‍♂️ Author

Mugabo Gusenga
[logmachine.bufferpunk.com](https://logmachine.bufferpunk.com)
[GitHub](https://github.com/Scion-Kin/logmachine)

---

## ❤️ Contribute

PRs and issues are welcome!
This tool is built for devs who want **beautiful logs with distributed brains**.
Let’s make debugging fun again.
