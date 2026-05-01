---
type: reference
subtype: tabular
name: tool-deep-review
category: tool
tags: [mcp, tool, workflow]
aliases: [end-to-end review, PR review before merging, comprehensive code review, thorough review, deep dive review]
source: src/attune/mcp/tool_schemas.py
---

# Reference: Tool: Deep Review

Multi-pass deep code review: security, quality, and test gap analysis with prioritized findings.

**Group:** workflow

## Parameters

| Parameter | Type | Description | Constraints | Default |
| --------- | ---- | ----------- | ----------- | ------- |
| `path` | string | Path to directory or file to review |  | required |

## Usage

`deep_review(path="...")`

## Related Topics
- **Reference**: Tool: Security Audit — Run security audit workflow on codebase. Detects vulnerabili...
- **Reference**: Tool: Bug Predict — Run bug prediction workflow. Analyzes code patterns and pred...
- **Reference**: Tool: Code Review — Run code review workflow. Provides comprehensive code qualit...
