<!-- Copyright (c) 2026 Ashutosh Sinha <ajsinha@gmail.com>. All rights reserved. Drishti platform. Proprietary: see LICENSE. -->
# Compatibility

Which version of each repository belongs to which platform release. The machine-readable source is [platform.yaml](platform.yaml);
this table is its readable copy.

| Platform release | Tools | Rachana | Lake | Elements | Drishti | Status |
|---|---|---|---|---|---|---|
| i7n | 1.1.0 (`v1.1.0-ide3`) | 1.0.1 (`v1.0.1-ide4`) | 0.9.1 (`v0.9.1-ide3`) | 3.3.2 (`v3.3.2-ide3`) | `v2.9.11.i_7n` | released 2026-11-25 (documentation: guides and tutorials reorganised; the last i7 release) |
| i7m | 1.1.0 (`v1.1.0-ide3`) | 1.0.1 (`v1.0.1-ide4`) | 0.9.1 (`v0.9.1-ide3`) | 3.3.2 (`v3.3.2-ide3`) | `v2.9.11.i_7m` | released 2026-11-25 (documentation: offline Help for the product docs, planned material to plans; no product change) |
| i7l | 1.1.0 (`v1.1.0-ide3`) | 1.0.1 (`v1.0.1-ide4`) | 0.9.1 (`v0.9.1-ide3`) | 3.3.2 (`v3.3.2-ide3`) | `v2.9.11.i_7l` | released 2026-11-25 (documentation across the platform; no product change) |
| i7k | 1.1.0 (`v1.1.0-ide2`) | 1.0.1 (`v1.0.1-ide3`) | 0.9.1 (`v0.9.1-ide2`) | 3.3.2 (`v3.3.2-ide2`) | `v2.9.11.i_7k` | released 2026-11-24 (documentation consolidated and generated; Windows test and product fixes; platform-first description) |
| i7j | 1.1.0 (`v1.1.0-ide2`) | 1.0.1 (`v1.0.1-ide2`) | 0.9.1 (`v0.9.1-ide2`) | 3.3.2 (`v3.3.2-ide2`) | `v2.9.11.i_7j` | released 2026-11-24 (launchers --list / --run; documentation) |
| i7i | 1.1.0 (`v1.1.0-ide1`) | 1.0.1 (`v1.0.1-ide1`) | 0.9.1 (`v0.9.1-ide1`) | 3.3.2 (`v3.3.2-ide1`) | `v2.9.11.i_7i` | released 2026-11-24 (launcher groups; no code change) |
| i7b | 1.1.0 (`v1.1.0`) | 1.0.1 (`v1.0.1`) | 0.9.1 (`v0.9.1`) | 3.3.2 (`v3.3.2`) | `v2.9.11.i_7b` | released 2026-11-22 |

Rules: install in the order tools, Rachana, Lake, Drishti (Elements has no Java build; Drishti vendors its bundles). A release names
exactly one tag per repository; use `clone_all.py --release <name>` to get that set, never a mix.
