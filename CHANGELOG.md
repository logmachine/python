# Changelog

## 2026-04-03
- FEAT: Make socketio dependency optional and improve transporter logic

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.0] - 2026-04-03

### Changed
- **Python**: Made `socketio` dependency optional. The logger now falls back to HTTP transport if `socketio` is not available in the environment.
- **Python**: Removed `websocket-client` and `python-socketio` from build system requirements to make the package more lightweight.
- **Python**: Improved error handling in `SocketIOTransporter` with better connection error messages.
- **Python**: Updated `SocketIOTransporter` to use `endpoint` configuration key instead of `socketio_path`.
- **Python**: Reordered headers in `HTTPTransporter` for consistency.
- **Python**: Enhanced username endpoint configuration with customizable `get_username_endpoint`.</content>
<parameter name="filePath">/home/nicola/Lab/logmachine/python/CHANGELOG.md
