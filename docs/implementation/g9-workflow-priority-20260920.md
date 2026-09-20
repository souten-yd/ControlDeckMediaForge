# G9 installed workflow admission correction — 2026-09-20

After PR581/582, signed 0.28.89 was published from merge
`9318fd35f3329c3f4774d28af37c3e83c558040d` and installed through
`./deck.sh feature update media-forge` (exit 0). The downloaded 31,818,476-byte
bundle matched SHA `ffec585d6a1168ac35289972a6857a0dfebada411109ff8e3548f9906f952644`;
independent signature/tamper checks and fresh-directory startup passed.
The installed service is healthy, with rollback 0.28.88 retained. All 16 database
tables, 2724 asset-file attributes and the Blender registry matched before/after
update. Existing three Library GLB bytes still match their recorded hashes.
Evidence: `maintenance/release-0.28.89-20260920/`.

The measured TRELLIS 512 receipt was installed only after rehashing its exact
runtime/model files and the independent validation described in
[generation evaluation](g9-real-generation-20260920.md). Live capability now offers
TRELLIS 512 experimentally; 1024 and Pixal remain unavailable. This runtime
measurement does not prove the complete Host job path works.

The ordinary authenticated invocation of `media.scene.from_image` returned Host
Job `2cff5b00e413`, with detached child `7846ed3eb4cc` and MediaForge Job
`job_e4c1fb0821734ca8a54ffb3f3a0b9622`. The parent invocation succeeded, but the
actual scene job failed at GPU admission with HTTP 422 and published no assets.
Live Host journal identifies the cause exactly: workflow priority must be at
most 15, while the adapter sent 20. No GPU execution or lease was started for
that failed scene job. A successful parent invocation is not generation success.

The shared adapter now uses default priority 0 for both engines, preserving the
existing workflow class. This is within the Host workflow ceiling. Both engine
regressions check that value. A public authenticated resource request generated
from the corrected adapter body returned HTTP 202/granted for 9,522,905,088 bytes;
it was not activated and its lease was explicitly released. The public probe is
not a substitute for the Add-on Runtime route's stricter validation; that route
will be rechecked after the signed 0.28.90 update. No Host changes or API/schema
changes are needed.

NOT TESTED at preparation: 0.28.90 publication/installation, successful installed
image→3D→Library, authenticated browser creation/viewer acceptance, completed
Pixal trained generation, bones/animation.

`./mf.sh test`: **2279 passed, 2 warnings, 272.22 seconds, exit 0**.
