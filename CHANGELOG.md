# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.4.0] - 2026-05-01
- **Python**: Re-introduced python-socketio as a dependency for better WebSocket support and real-time features.
- **Python**: Updated `SocketIOTransporter` to use receive logs from the server in real-time, allowing for more interactive logging experiences.
- **Python**: Added API_KEY support inside the central configuration for easier authentication management.
- **Python**: Improved error handling in `SocketIOTransporter`
- **Python**: Added better authentication management using environment
- **Python**: Added support for token refresh in the authentication flow to maintain long-lived sessions without requiring frequent logins.
- **Python**: Removed `get_username_endpoint` configuration key as it is no longer needed with the new authentication flow.

## [2.3.2] - 2026-04-05

- **Python**: Refactored `HTTPTransporter` and `SocketIOTransporter` to directly construct log data in `emit` methods, removing dependency on `parse_log`.
- **Python**: Changed verbose flag to check command line arguments for `--verbose` instead of configuration parameter.
- **Python**: Added maxsize to logging queue to prevent unbounded memory growth.
- **Python**: Added timeout to username endpoint HTTP request for better reliability.
- **Python**: Added wait_timeout to SocketIO connection to prevent hanging connections.
- **Python**: Changed initialization message to use `sys.stdout.write` instead of logging to avoid circular dependency.
- **Python**: Added comprehensive docstring to `success` method.
- **Python**: Added `sys` import for command line argument checking.</content>

## [2.3.1] - 2026-04-03

### Changed
- **Python**: Made `socketio` dependency optional. The logger now falls back to HTTP transport if `socketio` is not available in the environment.
- **Python**: Removed `websocket-client` and `python-socketio` from build system requirements to make the package more lightweight.
- **Python**: Improved error handling in `SocketIOTransporter` with better connection error messages.
- **Python**: Updated `SocketIOTransporter` to use `endpoint` configuration key instead of `socketio_path`.
- **Python**: Reordered headers in `HTTPTransporter` for consistency.
- **Python**: Enhanced username endpoint configuration with customizable `get_username_endpoint`.
<parameter name="filePath">/home/nicola/Lab/logmachine/python/CHANGELOG.md
