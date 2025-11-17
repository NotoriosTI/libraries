TODO
====

- Add a persistence toggle or pluggable adapter that lets the processor operate in “no storage” mode (e.g., replace `MockDBAdapter` with a no-op implementation when persistence is not needed).
- Ensure the outbound worker adapts to non-persistent operation (skip DB fetch/update and flush queued messages directly via an alternate queue/transport).
- Document configuration for persistence-free mode in `README.md`, including any environment flags and expected behaviour.
