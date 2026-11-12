---
name: frigate-ai-proxy
description: Deploy, configure, and operate Frigate AI Proxy as a high-efficiency OpenAI-compatible Generative AI gateway for Frigate NVR.
---

# Skill: frigate-ai-proxy

Use this skill when configuring, deploying, or troubleshooting an AI proxy gateway between Frigate NVR and vision-language / threat-classification models.

## Core Capabilities

1. **OpenAI API Emulation**: Exposes `/v1/chat/completions` and `/v1/models` matching Frigate 0.14+ Generative AI expectations.
2. **Frigate Config Passthrough**: Preserves user-defined `activity_context_prompt`, `additional_concerns`, and sequence metadata straight from Frigate's `config.yml`.
3. **Structured Review Generation**: De-duplicates repetitive title/scene/summary outputs into concise titles (<= 70 chars), 1-2 sentence push summaries (<= 280 chars), and detailed scene narratives.
4. **Threat Intelligence Scoring**: Computes deterministic 0-2 threat levels and confidence scores via TypeSafe System 1 / Jev or heuristic fallback.
5. **Frame Subsampling**: Downsamples frame bursts (e.g., 100+ frames down to 15-20) to maintain low token latency and cloud API costs.

## Integration Contract

### Frigate NVR `config.yml`

```yaml
genai:
  proxy:
    provider: openai
    base_url: http://frigate-ai-proxy:8000/v1
    api_key: unused
    model: glimpse
    roles:
      - descriptions

review:
  genai:
    enabled: true
    alerts: true
    detections: false
    image_source: preview
    activity_context_prompt: |
      Define normal daytime behavior vs suspicious perimeter loitering.
```

### Verification Steps

1. Verify proxy health:
   ```bash
   curl -s http://localhost:8000/health
   # Returns: true
   ```
2. Verify models list for Frigate UI:
   ```bash
   curl -s http://localhost:8000/v1/models
   # Returns: {"object":"list","data":[{"id":"glimpse",...}]}
   ```
