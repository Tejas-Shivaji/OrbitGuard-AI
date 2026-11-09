# OrbitGuard-AI — Performance and reliability changes

## Dashboard performance

- Orbital animation is now disabled by default. Users can still enable it from the dashboard.
- The textured Earth mesh is reduced from 512 × 256 to 256 × 128 points. This retains the textured 3D globe while reducing the surface mesh to one quarter of its former point count.
- Parsed SGP4 records are reused across repeated propagation calls.
- The last conjunction screen is retained in the Streamlit session when the selected TLEs and screening settings are unchanged; a **Run Screening Now** control starts a fresh scan.
- The selected-pair distance timeline is cached against the exact epoch of that retained scan.
- The SGP4 `Satrec` object is cached by TLE, avoiding repeated parsing of identical TLE lines.
- Current satellite positions are reused for the 3D spacecraft markers instead of being propagated a second time. Current-position timestamps remain exact rather than being rounded to create cache hits.
- Satellite health records are built once and reused by the audit and health sections.
- The audit trail avoids adding duplicate rows for the same scan when a dashboard widget causes a Streamlit rerun.

## Screening reliability

- Pairwise screening now receives only satellites that passed the current-position propagation check.
- The expected pair count and the screened pair count therefore refer to the same eligible satellite set.
- The existing partial/blocked integrity reporting is retained.

## Dependencies and tests

- `requirements.txt` is now UTF-8 and lists runtime dependencies rather than a full environment freeze.
- `requirements-dev.txt` adds pytest for the offline test suite.
- Tests use the bundled TLE cache and mocked positions where appropriate; no live TLE download is required by the tests.

## Validation performed during this review

- Python compilation succeeded for all project Python files.
- All eight bundled TLEs propagated successfully using the SGP4 pure-Python fallback available in the review environment.
- Offline cache loading, TLE parsing, closest-approach logic, three-pair screening and NORAD-ID validation passed manual checks.
- In a local pure-Python SGP4 benchmark with eight satellites, 28 pairs, a 180-minute window and 60-second samples, reusing the parsed SGP4 records took about 0.08 seconds versus about 0.35 seconds when reparsing the TLE on every sample. This is a calculation-only benchmark, not an end-to-end dashboard timing guarantee.
- The Earth surface trace JSON measured about 4.43 MiB at 512 × 256 and 1.11 MiB at 256 × 128 in the review environment.

The complete pytest suite and interactive Streamlit/browser rendering could not be run in this review environment because Streamlit and pytest are not installed here and package-network access is unavailable. Install `requirements-dev.txt` locally and run `python -m pytest -q` to execute the full suite.
