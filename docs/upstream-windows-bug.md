# Draft issue for AntiQuality/agentabstain (not sent)

**Title:** Filesystem sandbox and unpinned dependencies break runs on Windows and on fresh installs

Thanks for releasing the benchmark. Running it at commit `cfc3faf`, I found two problems that change results without an obvious error.

## 1. The filesystem sandbox uses the host's path rules

`data/environments/filesystem/environment.py` resolves sandbox paths with `os.path.normpath` and `os.path.join`. On Windows, `/projects/a.md` becomes `\projects\a.md`, which does not match the sandbox's keys, so `transfer_file` reports "Source file not found".

Replaying each operational pair's act-side steps with no model:

| Platform | Act side passes |
|---|---:|
| Windows 11 | 128 of 131 |
| Ubuntu 22.04 (WSL) | 131 of 131 |

All three Windows failures are `filesystem.transfer_file`. Four other environments also use OS path functions, and I have not checked them for the same problem: `document_authoring_and_publication`, `documents_and_analysis`, `phone_and_messages`, `system_operations`.

**Suggested fix:** use `posixpath` for sandbox paths. Sandbox paths are Unix-style on every host.

## 2. Unpinned requirements break the score export

`requirements.txt` has no versions. A fresh install on 2026-11-04 resolves to `mcp` 2.3.0, where `CallToolResult` has `structured_content` and no `structuredContent`. `src/runtime/googleadk.py:133`, `openaisdk.py:178` and `claudesdk.py:141` read the old name, so the export fails or returns nothing.

**Workaround that worked for me:** `uv pip install --exclude-newer 2026-07-17 -r requirements.txt`, which resolves `mcp` 1.28.1, `fastmcp` 3.4.4, `google-adk` 2.5.0, `openai-agents` 0.18.3.

**Suggested fix:** publish a lock file.

Happy to open pull requests for either.
