---
name: tcm-pulse-resources
description: Repos Monopoly found for the TCM pulse project — five TCM LLM projects plus an Apple Health MCP server
metadata: 
  node_type: memory
  type: reference
  originSessionId: 420cee18-6da0-4013-ba54-9fa3d05df32a
  modified: 2026-07-23T09:00:10.608Z
---

Resources gathered for [[tcm-pulse-project]], not yet evaluated in depth (that is Phase 2's job).

**TCM / Chinese medicine LLM projects** — all appear to be text-in/text-out syndrome
differentiation (辨证) work, so they likely serve the *reasoning* layer, not the signal layer:

- https://github.com/yasenstar/Chinese_Medicine
- https://github.com/JuneYaooo/nihaisha-nishi-tcm
- https://github.com/QLU-NLP/BianCang
- https://github.com/TCMAI-BJTU/LingdanLLM
- https://github.com/jangviktor-web/nihaixia

**Pipeline shortcut** — https://github.com/the-momentum/apple-health-mcp-server
MIT-licensed Python/FastMCP server, ~233 stars, v0.1.0 released 2025-10-22. Loads an exported
Apple Health XML file into DuckDB and exposes MCP tools (structure analysis, record search,
type extraction, summaries and trends) so an LLM can query health data over MCP. Batch XML
export only, not live sync; the README points to a successor platform called "Open Wearables"
for continuous sync. Monopoly found this himself and expects it to "save lots of effort" —
the open question is whether it reaches the ECG voltage CSVs inside Apple's export bundle and
whether batch export latency ruins the on-demand 把脉 session feel.
