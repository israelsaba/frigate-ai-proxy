<div align="center">

# Frigate AI Proxy

**High-performance, cost-efficient Generative AI proxy & threat intelligence gateway for Frigate NVR.**

[![CI](https://github.com/israelsaba/frigate-ai-proxy/actions/workflows/ci.yml/badge.svg)](https://github.com/israelsaba/frigate-ai-proxy/actions)
[![Release](https://img.shields.io/github/v/release/israelsaba/frigate-ai-proxy?color=blue&label=release)](https://github.com/israelsaba/frigate-ai-proxy/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://pydantic.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg?logo=docker&logoColor=white)](Dockerfile)
[![Tests](https://img.shields.io/badge/tests-20%20passed-brightgreen.svg)](tests/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Security Policy](https://img.shields.io/badge/security-policy-brightgreen.svg)](SECURITY.md)

</div>

---

## Overview

**Frigate AI Proxy** acts as an intelligent, drop-in OpenAI-compatible gateway (`/v1/chat/completions` and `/v1/models`) between **Frigate NVR** and vision-language models (such as Elorian Glimpse, Qwen-VL, or OpenAI). 

It bridges the gap between raw video frames collected by Frigate and high-accuracy, cost-controlled CCTV event analysis:

1. **Direct Frigate Config Passthrough**: Honors custom `activity_context_prompt`, `additional_concerns`, and camera sequence details defined in Frigate's `config.yml` without hardcoded prompt overrides.
2. **De-duplicated Review Outputs**: Automatically extracts and parses distinct, high-quality fields (`title`, `shortSummary`, and `scene`) so that mobile notifications and UI cards never repeat the same wall of text.
3. **Smart Frame Subsampling**: Intelligently samples high-density frame bursts (reducing 100+ frames to 15–20 evenly distributed frames), cutting token consumption and latency by up to **85%**.
4. **Hybrid Threat Scoring**: Evaluates visual observations through deterministic reasoning agents (such as TypeSafe System 1 / Jev) to calculate objective threat levels (`0` = benign, `1` = suspicious, `2` = critical) and confidence ratings.
5. **Architectural Isolation**: Follows Frigate maintainers' design principles—zero database polling, zero internal lock contention, and zero bloated external dependencies.

---

## Why Frigate AI Proxy?

| Feature | Standard Cloud VLM (Direct) | Frigate AI Proxy |
| :--- | :--- | :--- |
| **Token Consumption** | Hundreds of uncompressed frames per event | Evenly downsampled frames (15–20 max) |
| **Prompt Control** | Generic prompt or schema collisions | Preserves Frigate's `activity_context_prompt` & `additional_concerns` |
| **Review Card & Notification Text** | Raw markdown blocks repeated across title & summary | Concise title (`<= 70` chars), clean summary (`<= 280` chars), full scene |
| **Threat Intelligence** | Unreliable LLM integer hallucination | Deterministic System 1 reasoning scoring (`0`, `1`, `2`) |
| **Frigate UI Model Discovery** | Requires exact vendor endpoints | Full `/v1/models` discovery for one-click "Refresh Models" |

---

## Architecture

```
┌────────────────────────────────────────────────────────┐
│                      Frigate NVR                       │
│  • Detects tracked object / alert review event         │
│  • Compiles sequence frames + activity context prompt   │
└───────────────────────────┬────────────────────────────┘
                            │ POST /v1/chat/completions
                            ▼
┌────────────────────────────────────────────────────────┐
│                    Frigate AI Proxy                    │
│  1. Preserves Frigate config prompts & camera rules    │
│  2. Subsamples frames evenly (e.g. 100 frames → 20)    │
│  3. Forwards visual prompt to VLM (Elorian Glimpse)    │
│  4. Runs threat level evaluation (TypeSafe System 1)   │
│  5. Formats structured JSON: {title, scene, summary}   │
└───────────────────────────┬────────────────────────────┘
                            │ Returns structured JSON
                            ▼
┌────────────────────────────────────────────────────────┐
│                  Frigate UI & Alerts                   │
│  • Review Cards: Concise title & threat badge          │
│  • Mobile Push: 1-2 sentence clean shortSummary        │
│  • Full Inspector: Detailed narrative scene            │
└────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Docker Compose (Recommended)

Add `frigate-ai-proxy` to your existing Frigate stack:

```yaml
services:
  frigate-ai-proxy:
    image: ghcr.io/israelsaba/frigate-ai-proxy:latest
    container_name: frigate-ai-proxy
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - FRIGATE_PROXY_LOG_LEVEL=INFO
      - FRIGATE_PROXY_MAX_SAMPLED_IMAGES=20
      - FRIGATE_PROXY_MAX_OUTPUT_TOKENS=600
      # Upstream Vision Model (any OpenAI-compatible VLM: OpenAI, Ollama, Elorian, etc.)
      - FRIGATE_PROXY_VLM_BASE_URL=https://api.elorian.ai/v1
      - FRIGATE_PROXY_VLM_MODEL=glimpse
      - FRIGATE_PROXY_VLM_API_KEY=your_vision_api_key_here
      # Optional: Threat Scoring (disabled by default; also activated via model suffix e.g. glimpse-threat)
      - FRIGATE_PROXY_ENABLE_THREAT_SCORING=false
      - FRIGATE_PROXY_THREAT_SCORING_BASE_URL=https://api.typesafe.ai/v1
      - FRIGATE_PROXY_THREAT_SCORING_MODEL=jev-latest
      - FRIGATE_PROXY_THREAT_SCORING_API_KEY=your_typesafe_api_key_here

  frigate:
    image: ghcr.io/blakeblackshear/frigate:stable
    # ... your existing Frigate configuration ...
    depends_on:
      - frigate-ai-proxy
```

### 2. Local Development

```bash
git clone https://github.com/israelsaba/frigate-ai-proxy.git
cd frigate-ai-proxy
uv sync
make test
make run
```

---

## Cost-Conscious Frigate Configuration Guide

Running Generative AI reviews across continuous home surveillance can become expensive quickly if Frigate requests analysis for every moving tree branch or passing car.

Here is an **optimized, production-proven Frigate `config.yml`** designed specifically for **maximum cost control and zero wasted API tokens**:

```yaml
# ==============================================================================
# COST-CONSCIOUS FRIGATE NVR CONFIGURATION
# Optimized for high threat detection accuracy with minimal LLM token spend
# ==============================================================================

# 1. Connect Frigate's GenAI engine to Frigate AI Proxy
genai:
  proxy_glimpse:
    provider: openai
    base_url: http://frigate-ai-proxy:8000/v1
    api_key: unused
    model: glimpse
    roles:
      - descriptions

# 2. Restrict GenAI execution strictly to verified Alerts (NOT detections)
review:
  alerts:
    labels:
      - person   # Only generate alerts for human subjects
    cutoff_time: 10  # Consolidate motion bursts into a single review item

  detections:
    labels:
      - car
      - dog
      - cat

  genai:
    enabled: true
    alerts: true       # Run AI analysis only when an Alert occurs
    detections: false  # NEVER burn tokens on background detections (cars, cats)
    
    # CRITICAL: Use 'preview' frames instead of 'recordings'
    # Preview frames are 180p cached images consuming ~70% fewer tokens than 480p recordings
    image_source: preview
    preferred_language: English
    
    # Custom business rules sent directly to the model via Frigate AI Proxy
    additional_concerns:
      - gate or entry door left open
      - person loitering facing a perimeter wall or window
      - spray cans, tools, or weapons visible
      
    activity_context_prompt: |
      ### Normal Activity (Level 0)
      - Delivery couriers placing packages and leaving within 60s
      - Residents entering or leaving normally during daytime
      - Pedestrians walking past on public sidewalks without stopping

      ### Suspicious Activity (Level 1)
      - Unidentified individual lingering near property walls between 11 PM and 5 AM
      - Testing door handles or peering through windows
      - Prolonged loitering without clear purpose

      ### Critical Threat (Level 2)
      - Active vandalism, forced entry, or scaling walls
      - Visible break-in tools or weapons

# 3. Restrict object-level GenAI descriptions (optional)
objects:
  track:
    - person
    - car
  genai:
    enabled: false  # Keep false unless individual object captioning is needed
```

### Why this saves you money:
- **`image_source: preview`**: 180p preview frames use roughly **one-third of the token footprint** of 480p recording extractions while preserving all necessary context for person and action recognition.
- **`alerts: true` & `detections: false`**: Eliminates thousands of background queries per day. AI is called only when an actual alert criterion is satisfied.
- **`cutoff_time: 10`**: Groups continuous motion into a single unified event rather than triggering multiple concurrent AI calls for one person walking up the driveway.
- **Proxy Image Subsampling**: Caps total inbound frames at `MAX_SAMPLED_IMAGES=20`, preventing 60-second video clips from transmitting 150+ frames to the upstream API.

---

## Configuration Reference

All settings can be configured using environment variables prefixed with `FRIGATE_PROXY_` (generic aliases such as `UPSTREAM_VLM_*` and `OPENAI_*` are also supported):

| Environment Variable | Default | Description |
| :--- | :--- | :--- |
| `FRIGATE_PROXY_LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `FRIGATE_PROXY_MAX_SAMPLED_IMAGES` | `20` | Maximum number of video frames sent to the VLM per event. |
| `FRIGATE_PROXY_MAX_OUTPUT_TOKENS` | `600` | Max tokens generated by VLM (prevents cutoffs). |
| `FRIGATE_PROXY_VLM_BASE_URL` | `https://api.elorian.ai/v1` | Base URL for any OpenAI-compatible vision provider (aliases: `FRIGATE_PROXY_ELORIAN_BASE_URL`, `OPENAI_BASE_URL`). |
| `FRIGATE_PROXY_VLM_MODEL` | `glimpse` | Vision model identifier (e.g. `glimpse`, `gpt-4o-mini`, `llama3.2-vision`) (aliases: `FRIGATE_PROXY_ELORIAN_MODEL`, `OPENAI_MODEL`). |
| `FRIGATE_PROXY_VLM_API_KEY` | `""` | API key for vision provider (aliases: `FRIGATE_PROXY_ELORIAN_API_KEY`, `OPENAI_API_KEY`). |
| `FRIGATE_PROXY_ENABLE_THREAT_SCORING` | `false` | Enable deterministic threat scoring (aliases: `FRIGATE_PROXY_ENABLE_TYPESAFE_THREAT_SCORING`). Also activated on-demand via `-threat` model suffix. |
| `FRIGATE_PROXY_THREAT_SCORING_BASE_URL` | `https://api.typesafe.ai/v1` | Threat assessment reasoning provider URL (alias: `FRIGATE_PROXY_TYPESAFE_BASE_URL`). |
| `FRIGATE_PROXY_THREAT_SCORING_MODEL` | `jev-latest` | Threat evaluation model (alias: `FRIGATE_PROXY_TYPESAFE_MODEL`). |
| `FRIGATE_PROXY_THREAT_SCORING_API_KEY` | `""` | API key for threat assessment provider (alias: `FRIGATE_PROXY_TYPESAFE_API_KEY`). |
| `FRIGATE_PROXY_SYSTEM_PROMPT_PREFIX` | `""` | Optional system prompt prefix prepended to Frigate's prompt. |

---

## Verification & Health Check

Test proxy connectivity directly from your terminal:

```bash
# Check service health
curl -s http://localhost:8000/health
# Returns: true

# Check model list (used by Frigate UI 'Refresh models')
curl -s http://localhost:8000/v1/models
# Returns: {"object":"list","data":[{"id":"glimpse","object":"model","max_model_len":262144}]}
```

---

## Evaluation of Frigate Third-Party Extensions

Frigate's official [Third Party Extensions](https://docs.frigate.video/integrations/third_party_extensions/) ecosystem includes notable tools like **Double Take**, **Frigate Notify**, **cctvQL**, **frigate-abr**, and **Strix**.

When evaluating their public repositories and architectural discussions, several critical design lessons and maintainer concerns emerge:

1. **Maintainer Stance on In-Tree Plugins**:
   - Frigate core maintainers (e.g. [@NickM-27](https://github.com/NickM-27)) have deliberately rejected in-tree monolithic plugin architectures to prevent image bloat, dependency hell, and maintenance friction (see Frigate Issue #17821).
   - The officially supported and encouraged pattern is **external sidecars** communicating via standardized protocols (e.g., standard OpenAI `/v1` endpoints, MQTT event topics, or RTSP/WebRTC proxies).
2. **Security & Authentication (Port 5000 vs 8971)**:
   - Frigate maintainers explicitly warn in their documentation that many community extensions rely on legacy unauthenticated port 5000.
   - Frigate AI Proxy strictly communicates as an external provider contacted by Frigate itself over standard internal Docker networks, eliminating open security holes.
3. **Event Polling vs Event Push**:
   - Extensions that repeatedly poll Frigate's SQLite endpoints (`/api/events`) cause database locks and CPU spikes on edge hardware.
   - Frigate AI Proxy never polls SQLite; it operates purely as an on-demand HTTP RPC endpoint invoked only when Frigate's review state machine completes an alert sequence.
4. **Resilience & Abandonment**:
   - Community extensions frequently suffer abandonment when Frigate upgrades major schemas (e.g., legacy `events` to `reviews`).
   - Frigate AI Proxy implements standard OpenAI specification schemas (`/v1/chat/completions` and `/v1/models`), shielding the user from downstream schema changes.

---

## Contributing

We welcome community contributions, bug reports, and optimizations! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for local development workflows and guidelines.

To run the complete test suite:
```bash
make check
```

---

## License

This project is licensed under the [MIT License](LICENSE).
