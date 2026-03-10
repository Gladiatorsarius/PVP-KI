# Documentation Archive

This folder contains **historical documentation** for reference only. These files document earlier phases of the project and are no longer current.

## Why These Files Are Archived

The PVP KI project evolved significantly from its initial design to the current **Protocol v1** distributed architecture. These archived documents reflect earlier approaches that have been superseded by the current implementation.

## Archived Files

### Planning Documents (Historical)

- **Plan.md** (German planning document)
  - Early project planning and prompts
  - Describes original LAN setup concept
  - Contains Agent 0 freeze notice (still relevant conceptually)
  - **Status**: Superseded by current README.md and TRAINING_GUIDE.md

- **Aufgabenfokus.md** (German focus document)
  - "MINECRAFT PVP KI (1.21.10 - LAN-SETUP)"
  - Original module descriptions
  - Early architecture concepts
  - **Status**: Superseded by current README.md

- **full-plan.md** (Detailed system design)
  - Contains agent ownership model (Agents 0-4)
  - Describes pre-Protocol v1 implementation details
  - References outdated port allocation (9999, 10001, 10002, etc.)
  - Mentions client-side frame capture (now handled by VM runtime)
  - **Status**: Partially outdated; agent ownership model still conceptually valid, but implementation details superseded

- **IPC_FIX_SUMMARY.md** (Legacy IPC documentation)
  - Documents 2026 IPC socket fix (pre-Protocol v1)
  - Problem: Broken Java object access from Python
  - Solution: Bidirectional socket communication
  - **Status**: Explicitly marked as deprecated in the file itself
  - **Note**: "For current work, use TRAINING_GUIDE.md Protocol v1"

### Implementation Tracking (Completed Phases)

- **IMPLEMENTATION_PROGRESS.md** (March 3, 2026)
  - Detailed technical record of Phases 1-3 implementation
  - 53 fixes across security, QA, integration, performance, maintainability
  - Line-level code changes with references
  - Performance metrics: 98% system call reduction, 40% bandwidth savings, 5-10x GAE speedup
  - Validation evidence (syntax checks)
  - **Status**: Phases 1-3 complete; archived as reference for completed work

- **IMPLEMENTATION_SUMMARY.md** (March 3, 2026)
  - Executive summary of 5 specialist review fixes
  - Table of fixes by category
  - Performance impact summary
  - Phase 4 roadmap (maintainability refactoring)
  - **Status**: Companion summary to IMPLEMENTATION_PROGRESS.md; archived with Phase 1-3 completion

## Current Documentation

For up-to-date information, refer to these **active** documents:

### Primary References

1. **[README.md](../../README.md)** - Main project overview and quick start
2. **[doc/TRAINING_GUIDE.md](../TRAINING_GUIDE.md)** - Canonical Protocol v1 contract + complete training walkthrough
3. **[python/README.md](../../python/README.md)** - Python runtime quick start
4. **[python/ACTIVE_PATHS.md](../../python/ACTIVE_PATHS.md)** - Active vs legacy code paths (critical for developers)

### Key Differences: Old vs Current Architecture

#### Old Architecture (Pre-Protocol v1)
- Client-side Minecraft mod captured frames directly
- Direct TCP sockets per agent (ports 9999, 10001, 10002, etc.)
- Client-side event detection
- `training_loop.py` as main entry point

#### Current Architecture (Protocol v1)
- **Distributed runtime**: Main machine (coordinator + model) + VM machines (capture + input)
- **WebSocket coordinator** on single port (8765)
- **Server-authoritative events** (HIT, DEATH, RESET from server mod)
- **Command bridge** on port 9998 for event ingestion
- **VM thin clients** (`client.py`) handle screen capture and input execution
- **Main machine** (`main.py`) runs coordinator, trainer, model, UI
- **Grayscale + JPEG** frame encoding (was RGB in old design)
- **PyQt6 UI** for agent management

## When to Reference Archive

These archived documents may be useful for:

- **Understanding project evolution**: How the system evolved from initial design to current state
- **Historical context**: Why certain architectural decisions were made
- **Implementation tracking**: What specific fixes were applied in Phases 1-3
- **Learning from past approaches**: Understanding what was tried before current architecture

## DO NOT Use Archive For

- ❌ **Current implementation work**: Use TRAINING_GUIDE.md Protocol v1 contract instead
- ❌ **Port configuration**: Archived docs have outdated port numbers
- ❌ **Training workflows**: Use current TRAINING_GUIDE.md walkthrough
- ❌ **Code structure references**: Use ACTIVE_PATHS.md to identify active vs legacy code

## Archive Date

Files archived: March 9, 2026

As part of documentation consolidation to reduce fragmentation and eliminate confusion between pre-Protocol v1 and current architecture.

---

**For all current development, training, and usage, refer to the active documentation listed above.**
