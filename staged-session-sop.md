---
name: staged-session-sop
description: "Monopoly runs projects as a strict phase SOP, each phase in its own Claude session — so the deliverable is often a handoff prompt, not the work itself"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 420cee18-6da0-4013-ba54-9fa3d05df32a
  modified: 2026-07-23T09:00:01.986Z
---

Monopoly works through a fixed SOP, one Claude session (sometimes one Claude *account*) per
phase:

```
BRAINSTORM CONCEPT -> RESEARCH HOW IT REALLY WORKS -> LOCK DIRECTION
  -> R&D PLANNING -> CODING EXECUTION
```

**Why:** he wants each phase done deliberately and does not want a session racing ahead into
work that belongs to a later phase. He said it plainly: "now is researching and knowledge
capturing... after R&D planning, only move on to the real coding execute. It is like a
process SOP."

**How to apply:** first establish which phase you are in, then confine yourself to it. When he
is about to move to another session or account, the deliverable is usually a **self-contained
handoff prompt** carrying the accumulated context forward — not the work product itself. Ask
before starting expensive execution: on 2026-07-23 he killed four background research agents
because he wanted the research *prompt*, not the research. Write handoff prompts so a fresh
session with zero context can run them.

He also asks direct questions and wants direct answers — he invited blunt pushback on the
weak parts of his own plan rather than agreement. See [[tcm-pulse-project]] for the project
these phases currently apply to.
