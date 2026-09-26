# SLH Trust Layer — Commercial Product v1 — 2026-09-26

## Product

SLH Trust Layer is a security gateway for AI agents, chatbots, Mini Apps and
Web3 applications. It evaluates untrusted input and requested actions before
they reach sensitive execution paths.

## Core value

Customers get:
- credential-leak prevention
- prompt-injection detection
- untrusted-content classification
- transaction-risk checks
- audit-ready decision records
- an integration contract that does not require replacing their AI model

## API shape

POST /v1/trust/scan

Input:
- content
- optional authenticated subject
- optional requested action metadata

Output:
- risk_level
- recommended_action
- indicators
- request_fingerprint
- content_stored=false
- content_returned=false

The production API must authenticate callers, rate-limit requests and avoid
returning the submitted sensitive content.

## Action protection

A separate action gate should accept:
- authenticated principal
- requested action
- target
- chain/network
- amount
- risk result
- authorization scope
- user confirmation

The AI output alone must never be treated as authorization.

## Monetization

Start with three plans rather than many:

### Free
For testing and small personal projects.
A capped number of scans per month.

### Pro
For developers and small teams.
Higher scan limits, API access, transaction simulation and basic audit history.

### Business
For companies and agent platforms.
Higher limits, team controls, policy configuration, audit retention and
support/SLA terms.

Usage-based overages can be added after real demand is measured.

## Global payments

For web/API customers, use ordinary payment providers/merchant-of-record
infrastructure appropriate to the customer's jurisdiction.

For Telegram digital goods/services, use Telegram Stars where required by
Telegram's platform rules.

On-chain assets such as BNB or TON can later be supported as payment rails,
but payment acceptance must be a separate, fully verified accounting path.

## First measurable business metrics

- active paying organizations
- scans per active customer
- high-risk events detected
- prevented sensitive actions
- protected transaction simulations
- conversion from free to paid
- monthly recurring revenue
- infrastructure cost per 1,000 scans

## Safety/business boundary

Do not monetize by selling user secrets, raw prompts, private keys, seed
phrases, personally identifying data, or sensitive detection payloads.

Do not claim that a detection guarantees that fraud has occurred. The service
provides risk signals and controls.
