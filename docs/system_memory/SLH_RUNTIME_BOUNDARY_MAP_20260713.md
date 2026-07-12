# SLH Runtime Boundary Map

Date:
2026-07-13

Status:
ACTIVE DOCUMENTATION

Purpose:
Define system ownership boundaries before SLH ecosystem broadcast.

================================================

CURRENT PRODUCTION RUNTIME

Telegram Layer:

Owner:
bot_stable.py

Responsibilities:
- Telegram connection
- User message receiving
- Handler loading
- User interaction flow

Restriction:
No external developer access.

================================================

HANDLER LAYER

Location:
handlers/
root handlers

Responsibilities:
- Commands
- User actions
- Features
- Business logic entry points

Restriction:
Changes require validation.

================================================

KERNEL LAYER

Current architecture contains:

1.
SLH_KERNEL.py

2.
core/kernel.py


Decision:

No migration until architecture plan exists.

Reason:
Avoid duplicate runtime ownership.

================================================

GATEWAY LAYER

Current file:

SLH_GATEWAY.py


Current status:

Architecture foundation.

Future responsibility:

Protected integration boundary.


Future flow:

External Service

        |

SLH Gateway API

        |

Audit

        |

Validation

        |

Kernel

        |

Modules


================================================

EXTERNAL DEVELOPER MODEL

SLH Academy developers receive:

- Sandbox access
- API access
- Documentation
- Integration tools


They do NOT receive:

- Production Telegram access
- Core database access
- Internal secrets
- Direct module control


================================================

MICROSERVICE PRINCIPLE

Every external service must be:

REQUEST
 ->
AUDIT
 ->
VALIDATION
 ->
GATEWAY
 ->
KERNEL
 ->
MODULE
 ->
JOURNAL


================================================

BROADCAST READINESS CHECK

Before public broadcast:

[ ] Runtime stable
[ ] Gateway architecture documented
[ ] Academy model documented
[ ] Security boundaries documented
[ ] No production changes pending


================================================

VISION

SLH becomes an ecosystem where developers build compatible services without risking the core system.

The Gateway connects innovation while protecting stability.
