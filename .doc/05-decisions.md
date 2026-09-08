# Decisions

Each entry says what was decided, why, and what it rules out. Decisions taken
during the build are marked as such: they were not in the specification and are
open to being revisited.

## Scope

**Milestone M0 only.** The full requirement runs to M4. M0 is a complete
working tool covering the sources that need no credential. Rules it out: cost
reporting, production drift, live Droughty, score history, client theming.

**No warehouse access at this version.** Every source Hunter reads is in the
repository. Rules it out: row counts, uniqueness ratios, partitioning checks,
spend, and knowing what is actually deployed. Those are four of the seven areas
the specification lists as warehouse-dependent, and they are milestone M2.

The gain is large: installing at a client becomes a configuration change rather
than a security review. That is worth more at this stage than the areas it
costs.

## Architecture

**Hunter does not import dbt.** It reads a manifest file and shells out to
`dbt parse` only when asked. Keeps the dependency tree small and avoids adapter
version conflicts. Rules out: reading anything dbt only exposes through its
Python API.

**One normalised internal model, and no check reads a raw source.** Adding
Snowflake or another semantic layer touches one file in `ingest/`. Rules out
nothing, and costs one extra layer of types.

**Every reader is defensive.** A file Hunter cannot parse produces a finding,
not an exception. This was not a precaution: the pilot's main design file does
not parse with the pinned library as written.

**Third-party parsers are pinned exactly and wrapped.** `pydbml` and `lkml` are
small-maintainer projects parsing formats that shift. Pinning means a break
surfaces at upgrade rather than in a client run, and wrapping means the fix is
in one file.

**The command line is the only place logic lives.** The Action and the site are
thin wrappers. Rules out: Action-only behaviour, which would make CI and local
runs diverge.

## Configuration

**Nothing is hardcoded.** Every threshold is a typed field on a configuration
model. Rules out: a rule nobody can find the number for.

**The Rittman Analytics house standard is version-pinned per project.** A project names
`ra-house@1` and stays there until someone bumps it. Rules out: changing the
standard and moving every client's score at once.

**Unknown keys in a project file are an error.** A typo must not silently
disable a rule. Rules out: forgiving configuration files.

**Reasons are required for exceptions, not for information.** Declaring an
owner needs no justification. Silencing a rule needs a reason and an end date.
An earlier draft required a reason for every register entry, which would have
made recording an owner annoying enough that nobody would.

## Scoring

**Per-rule weighting rather than per-area totals.** Decided during the build.
The alternative lets a rule examining many objects dilute every other rule in
its area, so adding a rule raises the score. See
[04-the-score.md](04-the-score.md).

**Unmeasured areas are excluded and declared.** Not scored as zero, which would
report a failure where there was no measurement, and not silently dropped, which
would score out of less than 100.

**Systemic gaps reported above the number.** Decided during the build, after
reading a real result where the score was 89.6 and no table had an owner.

**Key coverage, not test count.** One repository has 3,926 tests, of which 3,492
are the same weak check and 100 are uniqueness tests. Counting tests scores it
well while its keys go unverified. `at_least_one` is recorded and never credited
as key cover.

**Vendored code is reported and never scored.** Models from an installed package
are not the client's code to change. Holding a team to their conventions on code
they would have to fork to fix produces findings nobody can act on. 57 of 299
models in the pilot.

## The register

**Two files, not one.** The ruleset says what correct looks like and changes
rarely; the register records decisions about particular tables and is edited
constantly. Different owners, different rates of change.

**`hunter init` pre-fills the register.** It lists the tables Hunter would flag,
each with a blank reason. Handing someone an empty file and asking them to
document their exceptions does not work. Handing them the list and asking for a
reason against each does.

**Nothing in the register hides a finding.** An approved exception still appears
on the site with its reason and review date. Rules out: using the register to
make a number look better.

**The register reports its own staleness.** An entry for a table that no longer
exists, an overdue review, an expired silence and a misspelt rule name are all
findings. A register nobody prunes stops being a record and becomes a hiding
place.

## The model levels

**Hunter draws the diagrams rather than only embedding the authored ones.**
Decided during the build. The authored conceptual diagram encodes build status
as fill colour across 88 hand-maintained style lines, and 21 of its 107 claims
were out of date. Hunter knows the real state, so it draws that and reports the
disagreement.

**The authored diagram's status is a claim, not an input.** Rules out: trusting
a hand-maintained diagram, which is the thing that went wrong.

**The colour code is learnt from the diagram's own legend.** A project that
recolours its legend still reads correctly. Rules out: hardcoded colours.

**An ambiguous name match is reported, not resolved.** Picking one of two
candidates silently produces a wrong reconciliation row that reads as fact.
Rules out: higher match coverage.

**Pipeline position is declared per layer.** An earlier version used the order
layers appeared in the configuration file, which produced "skips the seeds layer
to read a warehouse table". Declaration order is not pipeline order.

## Output

**Plain language above the detail, on the same page.** Not a separate mode. A
mode a non-technical reader has to find is a mode they will not find, and two
documents means one is always out of date.

**No generated prose.** Every consequence line is a template filled from a
finding's own evidence. Rules out: a language model writing the findings, which
would mean no guarantee that a sentence has a deterministic check behind it.
Narrative generation is milestone M3 and even then never introduces a fact.

**The graph is drawn collapsed by default.** 280 models in one flowchart is not
a diagram. Per-area detail sits underneath.

**Every path in the output is repository-relative.** Decided during the build,
after finding local absolute paths reaching a pull request comment. Unreadable,
and a small leak of whoever ran it.

**The attribution is on every published artifact.** The site, the report and the
comment. A licence term, not a preference.

## Distribution

**A standalone package, separate from any other framework.** Machine-readable
JSON output keeps a future wrapper possible without coupling now.

**The Action is pinned to a version, never referenced at `@main`.** A client's
score must not move because someone pushed a commit.

**MkDocs is invoked through the running interpreter.** Decided during the build.
A bare `mkdocs` command depends on PATH, which is not reliable inside a virtual
environment or in CI, and Hunter would report it missing when it is installed.

**The proprietary licence replaces MIT.** MIT lets anyone use, change and resell
the tool, which contradicts the planned support model. This is drafting and
needs review before the first paying client.

**Client content never reaches a tracked file, enforced by a check.** Hunter is
developed by running it against real client repositories, so the rule is
enforced rather than remembered.

## Left open

| Question | Why it is still open |
|---|---|
| How a client repository runs Hunter | The client conversation has not happened, and a private repository cannot share a composite action across organisations, so any answer now would be provisional |
| Where the site is hosted | Depends on the answer above and on the client's GitHub plan |
| What a support plan covers | Cannot invoice against an undefined scope |
| A second maintainer | One owner on a supported product is a delivery risk |
| Whether a client may run Hunter themselves | Determines whether the package can be installed in a client repository at all |
