<!-- Copyright (c) 2026 Ashutosh Sinha <ajsinha@gmail.com>. All rights reserved. Drishti platform. Proprietary: see LICENSE. -->
# Compatibility

Which version of each repository belongs to which platform release. The machine-readable source is [platform.yaml](platform.yaml);
this table is its readable copy.

| Platform release | Tools | Rachana | Lake | Elements | Drishti | Status |
|---|---|---|---|---|---|---|
| i7b | 1.1.0 (`v1.1.0`) | 1.0.0 (`v1.0.0`) | 0.9.1 (`v0.9.1`) | 3.3.1 (`v3.3.1`) | `v2.9.11.i_7b` | pending (Drishti tag after the drill) |

Rules: install in the order tools, Rachana, Lake, Drishti (Elements has no Java build; Drishti vendors its bundles). A release names
exactly one tag per repository; use `clone_all.py --release <name>` to get that set, never a mix.
