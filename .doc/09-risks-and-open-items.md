# Risks and open items

## Needs a decision before anything ships

Each of these needs someone at Rittman Analytics to decide, not someone to
build.

| Item | Why it blocks | Who decides |
|---|---|---|
| Repository visibility | The repository is public. The planned support model assumes it is not, and Hunter is developed by running it against client repositories | Owner |
| Where the code lives | Currently a personal account. The requirement specifies an organisation | Owner |
| How a client repository runs Hunter | A private repository cannot share a composite action across organisations, so the answer changes with the visibility decision | Owner, then the client |
| Licence review | The proprietary notice is drafting, not legal advice | Legal, before the first paying client |
| What a support plan covers | Cannot invoice against an undefined scope | Commercial |
| A second maintainer | One named owner on a supported product is a delivery risk | Delivery leadership |
| Whether a client may run Hunter themselves | Determines whether the package can be installed in a client repository at all | Legal and commercial |

The visibility change is a settings change on the repository and takes a minute.
Nothing client-derived is committed either way, and a check enforces that, but
it should happen before the first release tag.

## Risks, with what is already done about them

| Risk | What it would cost | Mitigation in place |
|---|---|---|
| A pinned parser breaks or lags its format | Design reading fails, and the conformance area dies | Version pinned exactly, wrapped behind Hunter's own interface, fixture tests catch it at upgrade. Already happened once: the pilot's main design file needed a normalising pass |
| Design files go stale relative to the repository | The reconciliation reports false off-plan builds | The design file's modification date is recorded. A stale design is itself a finding worth surfacing |
| Names diverge between levels | Everything looks off-plan | Normalised matching, then an explicit mapping in the register. Ambiguous matches are reported rather than resolved |
| Producing the manifest needs warehouse access | Every run needs a credential, and installing gets expensive per client | Three fallbacks: parse with a stub profile, parse with a read-only credential, or read the manifest from wherever the client's own job already writes it. The third removes the dependency for anyone already running dbt in CI |
| A client will not grant a credential or add an Action | The engagement stalls | The command line runs locally against a clone with no dependency on client CI |
| Comment noise on first install | The tool is muted within days | New findings only, advisory by default, a committed baseline, and every rule run against a real repository before it was trusted. Nine were wrong and were fixed |
| Weights look arbitrary | The score is dismissed | Weights in configuration, the whole ruleset published on the site, a grade per area, and every deduction naming its rule and file |
| Entity inference produces false positives | Trust lost early | Confidence published, low-confidence judgements excluded from the score, and the confidence ceiling lowered where warehouse evidence is absent |
| Attribution used punitively | Contributors game the tool | Reported by team and domain. No per-person ranking, by design |
| Overlap with existing dbt tools | Reads as reinvention | The overlap is real and acknowledged. Hunter's own effort goes on the joins those tools do not cross. Wrapping them as inputs is not yet done |

## Risks with nothing done about them yet

| Risk | Why it is open |
|---|---|
| Confidence is uncalibrated | A 0.8 is computed from signal agreement, not measured against outcomes. Calibrating it needs a body of findings someone has judged right or wrong, which does not exist yet |
| The score has not been tested against a second repository | Every threshold was set against one. A second repository will move some of them, and the golden file makes that movement visible rather than silent |
| Nobody non-technical has read the site | The plain-language layer is written for an audience that has not seen it. It needs one real reader |
| MkDocs 2.0 will break the theme and every plugin, with no migration path | Both dependencies are pinned below the major version, so nothing breaks today. It becomes a real problem when the pins need moving |
| The window report attributes debt by touched table, not by date | Getting it right needs a stored report per window, which is M1 |

## What to check before the first client run

Five minutes each, and each one avoids a false start.

1. Run `hunter init` and read what it detected. If the design files or the
   reporting layer are in an unusual place, the ruleset it wrote will say so in
   its notes.
2. Run `dbt parse` with a stub profile and no credential. If it works, the whole
   install needs no warehouse access.
3. Run `hunter score` and read the "what was not checked" page first. It says
   what the number is and is not based on.
4. Run `hunter baseline` and commit it, before anyone sees the score. An
   existing repository should start where it starts.
5. Leave the mode on advisory for the first few weeks. A tool that fails builds
   in its first week is switched off in its second.

## What to watch after it is running

| Signal | What it means |
|---|---|
| The same finding argued with twice | The rule is wrong, or its consequence line does not explain itself. Fix the rule, not the repository |
| Silences accumulating | Either the ruleset is wrong for this project, in which case override it and record why, or the work is not being done |
| Expired silences | The exception was never revisited. The finding is back, and the register says who agreed it |
| The score flat across a sprint | Either nothing improved, or Hunter is measuring the wrong things for this team |
| A systemic gap staying systemic | Nobody has taken the decision. That is a conversation, not a task |
