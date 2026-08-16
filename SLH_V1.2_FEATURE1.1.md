SLH OS v1.2 FEATURE 1.1

NAME:
Deployment Metadata Layer

BASE:
v1.2-feature1-control-center-live

GOAL:
Replace git runtime detection with stable deployment identity.

OUTPUT:
Control Center shows:
- commit
- branch
- environment
- deployment id

IMPLEMENTATION:
1.
2.
3.

ACCEPTANCE:
GET /control-center returns deployment metadata.
