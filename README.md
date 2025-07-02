# LipC - Real-Time Lip‑Reading Transcription for Secure Video Calls



> **LipC** is an end‑to‑end system that combines a Python back‑end, a custom TensorFlow lip‑reading model, and a Flutter client to deliver accurate, real‑time transcripts for peer‑to‑peer video calls – even when the audio channel is noisy, muffled, or completely unavailable.

---

## Table of Contents

1. [Key Features](#key-features)
2. [Architecture Overview](#architecture-overview)
3. [Tech Stack](#tech-stack)
4. [Project Structure](#project-structure)
5. [Getting Started](#getting-started)
   - [Prerequisites](#prerequisites)
   - [Back‑end Setup](#back-end-setup)
   - [Front‑end Setup](#front-end-setup)
6. [Configuration](#configuration)
7. [Running Tests](#running-tests)
8. [Contributing](#contributing)

---

## Key Features

- **Real‑time lip‑reading** (LipNet‑inspired Bi‑LSTM + CTC model) – 75‑frame visual window, \~200 ms latency.
- **Optional Vosk STT** fallback for high‑quality audio scenarios.
- **End‑to‑end encryption**
  - TLS‑secured `wss` transport (X25519 + AES‑256‑GCM envelope).
  - SRTP‑encrypted WebRTC media.
  - Short‑lived JWT **access tokens** and rotating **refresh tokens** stored in Flutter Secure Storage.
- **Peer‑to‑peer video** via WebRTC with self‑hosted signalling.
- **MongoDB** persistence – users, contacts, call history (& transcripts), revoked tokens.
- **Full Flutter UI** (Android, iOS, desktop & web) with Riverpod state management.
- **Accessibility‑first UX** – large captions, contrast‑aware palette and haptics.

## Architecture Overview

```text
┌────────┐          TLS/WSS          ┌────────────┐            SRTP             ┌────────┐
│Flutter │◄──────────────────────────►  Python    │◄───────────────────────────►│ Flutter│
│ Client │   JSON + AES‑GCM frames   │  Signalling│     Encrypted Media         │ Client │
└────────┘                           │  Server    │                             └────────┘
                                     │(FastAPI/ws)│
                  ┌────────────┐     └────┬───────┘
                  │ Lip‑Reading│          │ Async I/O   ┌──────────┐
                  │  Model     │          └────────────►│ MongoDB  │
                  └────────────┘                        └──────────┘
```

## Tech Stack

| Layer        | Technology                                            |
| ------------ | ----------------------------------------------------- |
| **Client**   | Flutter 3.29 · Dart · flutter\_webrtc · Riverpod      |
| **Server**   | Python 3.10 · FastAPI · websockets · aiortc · asyncio |
| **ML & DSP** | TensorFlow 2 (Keras) · MediaPipe · Vosk               |
| **Database** | MongoDB 6 · Motor (async driver)                      |
| **Security** | TLS 1.3 · X25519 · AES‑256‑GCM · JWT (RS256)          |

## Project Structure

```text
app/           # Flutter application (Android/iOS/desktop/web)
model/
  ├─ final_model.keras    # Trained lip‑reading model
  └─ model training code
server/          # Python signalling server, cryptography utils, models
```

## Getting Started

### Prerequisites

- **Back‑end**: Python ≥ 3.10, `virtualenv`, OpenSSL, Nvidia or AMD GPU (optional but recommended).
- **Front‑end**: Flutter ≥ 3.29, Android/iOS SDK *or* desktop toolchain.
- **Database**: MongoDB ≥ 6 locally or in the cloud.

### Back‑end Setup

```bash
# 1. Clone the repo
$ git clone https://github.com/MrYoavon/lipc.git && cd lipc/server

# 2. Create & activate a virtual environment
$ python -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
$ pip install -r requirements.txt

# 4. Configure secrets
$ cp .env.example .env        # then edit values (Mongo URI, JWT keys, cert paths)

# 5. Run the server
$ python app.py                  # serves WSS on port 8765 by default
```

### Front‑end Setup

```bash
# From repo root
$ cd app
$ flutter pub get

# Pass server host as a compile‑time constant (or edit lib/core/constants.dart)
$ flutter run --dart-define=SERVER_HOST=ws://<server-ip>:8765
```

> **Tip 💡** For local P2P calls start the app twice (emulator + device) or run the desktop build.

## Configuration

| Variable                           | Description                                      |
| ---------------------------------- | ------------------------------------------------ |
| `WEBSOCKET_HOST`                   | Public interface for WSS server (e.g. `0.0.0.0`) |
| `WEBSOCKET_PORT`                   | Port (default `8765`)                            |
| `MONGODB_URI`                      | Mongo connection string                          |
| `JWT_RSA_PRIVATE_KEY / PUBLIC_KEY` | 2048‑bit RSA keypair for token signing           |
| `ACCESS_TOKEN_EXPIRE_MINUTES`      | Short‑lived access token TTL (default 15)        |
| `REFRESH_TOKEN_EXPIRE_DAYS`        | Refresh token TTL (default 7)                    |
| `SSL_CERT_FILE / SSL_KEY_FILE`     | Paths to TLS certificate & key                   |

Additional tunables live in `server/constants.py`.

## Running Tests

```bash
# Back‑end unit & integration tests
$ pytest -q

# Static analysis
$ flutter analyze             # in client/
```

## Security Design

- Mutual authentication with short‑lived JWTs – every WebSocket frame carries a token.
- Ephemeral X25519 key‑exchange → per‑connection AES‑256‑GCM envelope.
- All media encrypted with SRTP (handled by WebRTC).
- Rate‑limiter & heartbeat watchdog mitigate brute‑force and stale connections.
- Comprehensive **JSON Schema** validation blocks NoSQL injection.

## Contributing

All contributions – code, documentation, tests, design – are **welcome**!.

> © 2025 Yoav Lavee – Final year cyber‑security project, Blich High School
