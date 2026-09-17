# KNOWN LIMITATIONS

- The deterministic fallback has strict lexical boundaries. While hardened against true-but-irrelevant facts by enforcing explicit procedural/causal intent markers, valid queries lacking these markers may result in the engine abstaining when the LLM is down.
- There is no public cloud SSL/HTTPS termination natively configured inside the Docker stack. It must be run behind a trusted reverse proxy (e.g., Render managed TLS).
- The evaluated release path rejects unsupported claims before the final response under the tested conditions, but relies heavily on OpenAI's structured output syntax.
