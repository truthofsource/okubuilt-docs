# Placement Rules

## Main Rule

```text
Did this happen in the real homelab?
  yes -> infrastructure/
  no  -> cloud/
```

## Date Rule

Remove dates from:

- filenames
- visible headings
- indexes
- generated metadata
- runbook body content

Use logical event order instead of date order.

## Ordering Rule

Order documents by logical event flow inside each category.

```text
design/planning -> baseline setup -> configuration -> incident -> recovery -> hardening -> follow-up
```
