# Agrisynthia Backlog

Items found but not yet decided, and decisions taken but not yet implemented. The
A-nnn audit identifiers used in commit subjects are not tracked in this
repository, so entries here carry no identifier until one is assigned.

Every citation below was verified against commit e154c3b. Entries describe what
is wrong and why it matters. They do not prescribe a fix; that is designed when
the work is scheduled.

## Open: the two environment lists in settings.py disagree

Found 2026-10-01, while making the chatbot model identifier required outside
development and test. Extended 2026-10-09: there are three ideas of production
in one file, not two.

`agrisynthia/settings.py` carries three different answers to the question of
which environment names count as production:

- `validate_environment()` computes `env_type` as production unless
  `IS_DEVELOPMENT`, so every name except `development` takes the production
  branch. `test` lands there too and must supply `DJANGO_SECRET_KEY` and
  `DJANGO_ALLOWED_HOSTS`.
- `_EXEMPT_ENVIRONMENTS` is `("development", "test")` and governs the database
  and Redis guards, so `test` is exempt from those.
- `settings.py:22` defaults an absent `DJANGO_ENVIRONMENT` to `development`, so
  a machine with the variable unset is treated as development by both of the
  above.
- `settings.py:803` reads `os.environ.get("DJANGO_ENVIRONMENT")` raw rather than
  through `ENVIRONMENT`, so for the model identifier guard alone an absent or
  unrecognised name counts as production.

The effect is that `DJANGO_ENVIRONMENT=test` is held to the stricter rule for
the secret key and allowed hosts and the looser rule for the database and Redis
credentials, while an unset variable is development for two guards and
production for a third. A deployment that names itself `test`, or that forgets
to name itself at all, gets a different answer from each guard.

This is also why `agrisynthia/test_settings.py` supplies a placeholder model
identifier instead of naming the environment `test`. Naming it would push
`validate_environment()` into its production branch and stop the test suite
loading.

Nothing is changed in code. Which of the lists is authoritative is a decision
for the owner.

# Phase 1

## Open: multi_detection_image never saves its results

`detection/views.py:544` calls `DetectionResult.objects.create(...)`, but
`DetectionResult` is not in scope. The module imports only `DetectionTask` and
`ModelVersion` at `detection/views.py:36`, and the function, which begins at
`detection/views.py:429`, contains no imports of its own.

The view is routed at `detection/urls.py:9` as `mcti/`, and no test references
it. Any request that reaches the create raises `NameError`, so a multi image
detection run produces no stored result at all.

## Open: the gettext alias is shadowed, so translated errors raise

`detection/views.py:39` imports `gettext_lazy as _`. Inside
`multi_detection_image`, `detection/views.py:526` assigns to `_` as a throwaway
in `_, total_count = predict_tree.multi_predictor(...)`, which makes `_` a local
name for the whole function. The earlier call at `detection/views.py:442` then
raises `UnboundLocalError` instead of returning a translated message.

`dron_map/views.py` has the same shape: `dron_map/views.py:445` assigns `_` from
`predict_tree.predict(...)` and `dron_map/views.py:436` calls `_()` before it.

Both sites are error paths, so the failure replaces a useful message with a
server error exactly when something has already gone wrong.

## Open: drone outputs bypass media authorization

Drone results are written under `static/results/<task_id>/`
(`dron_map/views.py:83`) and referenced in the template through the static tag
(`templates/map.html:415`). Static files are served directly, so these outputs
never pass through `detection.views.serve_media_file`
(`detection/views.py:150`) and its owner check at `detection/views.py:115`.

Detection media is gated by owner and drone output is not, so the weaker of the
two paths decides who can read a survey.

## Open: the task ownership row is written after the task is dispatched

`async_detection` calls `process_image_detection.delay(...)` and only then
creates the `DetectionTask` binding, at `detection/views.py:798` and
`detection/views.py:806` respectively.

Between those two statements the task exists with no owner. A poll arriving in
that window finds no binding and is refused, and a worker fast enough to finish
first would run with no ownership record at all.

## Open: the prediction cache key is not scoped to a user

`get_prediction_cache_key` at `detection/cache_utils.py:21` formats
`prediction:{image_hash}:{fruit_type}`. The key carries no user, so one tenant's
cached prediction answers another tenant's request for the same image bytes.

## Open: project deletion happens on GET

The delete branch of `add_projects` in `dron_map/views.py` calls
`projes.delete()` with no method check. `dron_map/views.py` declares no
`require_POST` or `require_http_methods` anywhere, so a GET to the delete URL
deletes the project. It is gated on `is_staff`, which limits who can trigger it
but not how.

Any link prefetch, crawler or browser history visit by a staff user is enough.

## Open: a real drone survey cannot be uploaded

The upload handler reads every file from one request at
`dron_map/views.py:243` through `request.FILES.getlist("picture")`, and nginx
caps a request body at 100M (`nginx.conf:28`).

A survey is hundreds of images of several megabytes each, so the feature cannot
accept the input it exists for. The cap is not the defect by itself; the
single request shape is.

## Open: band order is assumed, with no band count check

Bands are read positionally as 1 red, 2 green, 3 blue, 4 near infrared at
`agrisynthia/histogram.py:342-345` and `dron_map/api_views.py:60-61`. Nothing
checks how many bands the raster has before reading band 4.
`agrisynthia/histogram.py:25` does read a band count, but only for tiling
metadata, never as a guard.

A three band orthophoto raises on the band 4 read. A multispectral set whose
band order differs produces a plausible looking index computed from the wrong
data, which is worse than an error because nothing surfaces it.

## Open: NDRE is computed with the NDVI formula

`agrisynthia/histogram.py:96-99` defines NDRE as `(nir - red) / (nir + red)`,
which is NDVI. Its own docstring states the red edge formula it does not
implement, and no red edge band exists anywhere in tracked project code.

The index is offered by name and returns a different index's values.

## Open: ten pinned dependencies carry known advisories

`pip-audit -r requirements.txt` reports 75 rows covering 43 distinct advisories
across ten packages: pillow 11.3.0 with 18, urllib3 2.2.3 with 8, sqlparse
0.5.3 with 6, anyio 4.11.0, Django 5.2.16, djangorestframework 3.16.1 and
requests 2.32.3 with 2 each, and idna 3.10, pygments 2.19.2 and python-dotenv
1.1.1 with 1 each.

Django and djangorestframework being on the list matters most, since they
handle every request. This step is blocking in the gate.

## Open: the inference dependency is unpinned

`requirements.txt` pins neither torch nor torchvision. They arrive only as
transitive dependencies of `ultralytics==8.0.196`, and no tracked project code
imports ultralytics at all. Inference uses the vendored tree under
`detection/yolo/` instead.

Measured on 2026-10-09: three environments resolved three different versions of
the library that runs the model. A fresh install is therefore not reproducible
in the one dependency that decides what the models output.

## Open: the two upload extension sets disagree, and the form offers a rejected type

`detection/constants.py:33` allows jpg, jpeg, png and bmp for detection.
`detection/constants.py:34` allows jpg, jpeg, png, tif and tiff for drone
uploads. Both paths now receive drone imagery.

`templates/form2.html:38` sets `accept="image/jpeg,image/png,image/tiff"`, so
the detection form invites a TIFF that the backend then refuses. The public
product page also states that TIFF output is supported.

## Open: stale and duplicated configuration

- `MAX_UPLOAD_SIZE` at `agrisynthia/settings.py:312` is referenced nowhere else
  in tracked code. The limits actually enforced are
  `MAX_DETECTION_FILE_SIZE` and `MAX_DRONE_FILE_SIZE` from
  `detection/constants.py:30-31`.
- `DATA_UPLOAD_MAX_NUMBER_FIELDS` is assigned twice, at
  `agrisynthia/settings.py:311` and `agrisynthia/settings.py:334`, to the same
  value. The second wins, so a change to the first would be discarded in
  silence.
- `FRUIT_MODEL_PATHS` at `detection/constants.py:25` is live but its values are
  stale. It points at a flat `models/<fruit>.pt` layout that
  `migrate_model_files` moves away from, and the paths do not exist. Only its
  keys are used, at `detection/views.py:45` to build `FRUIT_MODELS`, which gates
  fruit type validity at `detection/views.py:265`, `:474` and `:733`. A reader
  reasonably assumes the paths are usable.

## Open: the vendored loader can fetch weights over the network

`attempt_download` at `detection/yolo/utils/google_utils.py:26-48` is called by
`attempt_load` for every weights path. When the file is absent it requests
`https://api.github.com/repos/WongKinYiu/yolov7/releases/latest` and falls back
to a hardcoded list of upstream release assets.

Nothing in that function prevents the request. The only reason it never fires is
call order: `agrisynthia/predict_tree.py:90` checks `model_path.exists()` and
raises `FileNotFoundError` before `attempt_load` is reached at
`predict_tree.py:124`.

That is a guard by accident of sequence, not by design. Any future caller that
reaches `attempt_load` directly, or any reordering of those checks, opens a path
where a missing project model is silently replaced by a generic upstream one,
and the first symptom would be wrong counts rather than an error. An offline or
air-gapped installation must never reach the network for weights at all, so the
download path needs a guard of its own rather than relying on an earlier caller
to have checked.

## Open: the checksum command reports problems and exits zero

`detection/management/commands/verify_model_checksums.py:77-82` prints the
problem count but only raises `SystemExit(1)` when `--strict` is passed.

Without that flag a caller sees a success exit while mismatches are on screen.
It is not yet a gate step, and should be added as one with `--strict`, since it
is the check that detects weights on disk no longer matching their recorded
digest.

## Open: task time limits may not fit a drone job

`agrisynthia/settings.py:663` sets a hard Celery time limit of 30 minutes and
`:664` a soft limit of 25. `agrisynthia/settings.py:668` restarts a worker
after 10 tasks, which discards the process local model cache in
`agrisynthia/predict_tree.py:32` and reloads weights from disk.

Neither value has been measured against a real survey, so whether a job fits
inside the limit is unknown, and the restart cadence trades memory safety for
repeated load cost without a measurement behind it.

## Open: two weaknesses in the gate itself

- `scripts/gate-checks/weights-present.py:26` hardcodes `VERSION = "v1"` rather
  than reading the active `ModelVersion.weights_path`, which is the field the
  loader actually uses. Activating a v2 would leave the check inspecting a path
  nothing loads.
- `scripts/gate` runs the inference tests twice, once inside the full suite at
  `scripts/gate:88` and again as its own step at `scripts/gate:93`. The second
  run reloads every model from disk for no additional coverage.

## Open: the commit message hook checks less than the rules require

`commit-msg` in the shared hook directory runs the naming scan and a trailer
check only. The one line form, the conventional prefix and the absence of dash
glyphs are not checked, so those remain habits rather than gates.

## Open: the container image has never been built

`docker compose build` has not been run. `Dockerfile:33` is
`RUN pip install --no-cache-dir GDAL==$(gdal-config --version)`, an exact
version pin against whatever the index happens to publish, and is the likely
first failure.

Until the image builds, the deployment path is unverified end to end, and no
release should be tagged against it.

## Open: public copy makes claims the code does not support

Two separate problems, and copy changes need owner approval before any edit.

Capture method. The copy describes images taken with a phone or handheld
camera, while all imagery is captured by drone. Sites:
`templates/website/product.html:76`, `website/views.py:59`,
`website/views.py:83`, `website/views.py:127`, and the matching entries in
`locale/en/LC_MESSAGES/django.po` at lines 1910, 2231, 2255, 2276, 2329 and
2342. `website/views.py:76` and `templates/website/home.html:76` imply handheld
capture without naming a phone.

Unsourced figures. `templates/website/home.html:76`,
`templates/website/product.html:135` and `website/views.py:188` claim counting
accuracy above 94 percent. `templates/website/home.html:81` and
`website/views.py:323` claim yield predicted to within 25 percent.
`templates/website/product.html:195` claims testing with more than 50 drone
models. `website/views.py:127` claims 71 percent smartphone ownership.

The repository contains no benchmark, no validation set and no evaluation
output supporting the accuracy or precision figures, and
`detection/test_inference.py` asserts shapes and error paths rather than
accuracy.

## Open: the chatbot answer lists fruits the system does not support

`website/views.py:320` answers the supported crop question with mandarin,
orange, lemon, apple, pomegranate and olive. The models that exist are mandarin,
apple, pear, peach, pomegranate and tree, enumerated at
`detection/constants.py:6`.

So the answer names three crops with no model behind them, orange, lemon and
olive, and omits two that do have one, pear and peach. It also states that new
types are added continuously. This reaches users through the chatbot rather than
a page, so it is not caught by reading the site.

## Open: the gate is red on three static steps

Measured on 2026-10-09 at e154c3b: ruff reports 735 findings, 93 files would be
reformatted, and mypy in strict mode reports 1488 errors across 123 files.

These are blocking steps, so the gate fails until they are worked through. That
is the intended state rather than something to configure away.

# Phase 2

## Open: full audit

A complete pass over types, security, run based testing, concurrency, templates
and client side scripts, and duplication and dead code. The run based part
matters most: several defects recorded above were found by executing code rather
than reading it, and the same method has not been applied to the whole tree.

Also measure the wall clock time of a full drone job, separately on processor
only and on a machine with a graphics processor, so the task time limits above
can be set against a number instead of a guess.

# Phase 3

## Open: structural work

- Typed configuration, so settings are validated once at startup rather than
  read as strings at each use.
- Tenancy enforced at the query layer rather than in each view and action, so a
  new endpoint is scoped by default instead of by review.
- The broad exception handlers. There are 110 in tracked project code, and each
  one can turn a real error into a default.
- Consolidation of duplicated code, starting with the per fruit enumerations.
  Nine tracked files carry one, and four of those spell the same six item
  list as `FRUIT_TYPES`: `detection/models.py:8`,
  `detection/migrations/0012_seed_model_versions.py:8`,
  `detection/management/commands/migrate_model_files.py:19` and
  `detection/test_migrations.py:34`. The others are the two dicts in
  `detection/constants.py:6` and `:15`, a colour map at
  `dron_map/views.py:751`, yield parameters at `dron_map/yield_predictor.py:21`
  and display names at `reports/generators/pdf_detection.py:64`.
- Add complexity limits to the gate once the existing static steps are green.
