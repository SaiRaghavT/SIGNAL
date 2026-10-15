# Shared edge cases

This folder contains synthetic FHIR bundles for edge-case workflows that should
be easy for the whole team to find and reuse.

- `Emily_Carter_measles_false_positive_FHIR.json`: measles-like symptoms with
  a negative PCR and positive IgG from prior immunity. Seed it with
  `backend/scripts/seed_measles_false_positive.py`.
