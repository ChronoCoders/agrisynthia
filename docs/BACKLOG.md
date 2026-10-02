# Agrisynthia Backlog

Items found but not yet decided, and decisions taken but not yet implemented. The
A-nnn audit identifiers used in commit subjects are not tracked in this
repository, so entries here carry no identifier until one is assigned.

## Open: the two environment lists in settings.py disagree

Found 2026-10-01, while making the chatbot model identifier required outside
development and test.

`agrisynthia/settings.py` carries two different ideas of which environment names
count as production:

- `validate_environment()` computes `env_type` as production unless
  `IS_DEVELOPMENT`, so every name except `development` takes the production
  branch. `test` lands there too and must supply `DJANGO_SECRET_KEY` and
  `DJANGO_ALLOWED_HOSTS`.
- `_EXEMPT_ENVIRONMENTS` is `("development", "test")` and governs the database
  and Redis guards, so `test` is exempt from those.

The effect is that `DJANGO_ENVIRONMENT=test` is held to the stricter rule for the
secret key and allowed hosts, and the looser rule for the database and Redis
credentials. A deployment that names itself `test` gets half of each.

This is also why `agrisynthia/test_settings.py` supplies a placeholder model
identifier instead of naming the environment `test`. Naming it would push
`validate_environment()` into its production branch and stop the test suite
loading.

Nothing is changed in code. Which of the two lists is authoritative is a decision
for the owner.
