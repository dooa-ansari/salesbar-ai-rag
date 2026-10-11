---
name: no-comments
description: Write or edit code in this project without adding any comments. Use whenever creating or modifying source, config, or test files (Python, TypeScript, YAML, Dockerfiles, etc.).
---

# No comments

When writing or changing code in this repository, do not add comments.

## Rules

- Do not add inline comments, block comments, or `TODO`/`NOTE` markers.
- Do not add docstrings to new functions, classes, or modules.
- Do not add explanatory comments to config files (`docker-compose*.yml`, `Dockerfile`, `pyproject.toml`, `.env*`, `nginx.conf`).
- Make the code self-explanatory instead: clear names, small functions, obvious structure.
- Explain anything non-obvious in the response or the commit message, not in the code.

## Existing comments

- Leave existing comments alone unless the user asks for them to be removed.
- If a line you are editing carries a comment that your change makes wrong, update or delete that comment rather than leaving it stale.

## Exceptions

- Tool directives that are functional, not explanatory (`# noqa`, `# type: ignore`, `// eslint-disable-next-line`, `// @ts-expect-error`, shebangs) may be kept or added when required.
- Comments the user explicitly asks for.
