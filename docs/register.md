# Mark a table temporary, verified or permanent

<p class="lede">The register is the file people actually edit. It records what
your team decided about particular tables: which are temporary on purpose,
which have been confirmed, who owns what, and what is on its way out.</p>

## The three statuses

Every built table carries one of three words on the dashboard.

| Status | Meaning | Where it comes from |
|---|---|---|
| **Temporary** | A working step, or a table only ever meant to run once. Carries a review date so it cannot quietly become permanent | Declared here, or inferred from the layer |
| **Verified** | Meant to stay, and a named person has confirmed it should. The table to build on | Declared here only, with `verified_by` |
| **Permanent** | Meant to stay | Inferred from the layer and materialisation |

Hunter can infer temporary and permanent. It can never infer verified, because
verified means a person looked. That is the point of the word: on the roadmap
and the table list, a verified table is one somebody has checked, and a
permanent one is one Hunter assumed.

```yaml
models:
  wh_commerce__order_fact:
    persistence: verified
    verified_by: sav
    verified_on: 2026-09-08
    reason: signed off at the design review as the order fact of record
```

`permanent` is also accepted where you want to override an inference of
temporary, for instance a finished table that lives in a working layer. It
needs a reason, like any override.

## Lifecycle status, for the roadmap

Separate from the three words above, and plain information: no reason needed.

```yaml
models:
  wh_commerce__legacy_fact:
    status: deprecated        # planned, building, live, deprecated, retired
    review_by: 2027-03-31     # the date it should be gone by
```

The roadmap on the dashboard places every table in one lane: planned, being
built, live, temporary by design, being phased out, retired. A status declared
here decides the lane. Without one, Hunter places the table by where it sits
between the design and the build.

`hunter.yml` says what correct looks like and changes rarely. The register
records decisions about individual tables and changes constantly. Different
owners, different rates of change, so two files.

Both sit in `.hunter/` at the repository root. See
[where the files go](configuration.md#where-the-files-go).

## Four things Hunter cannot work out on its own

| | Why it needs a person |
|---|---|
| **That something is temporary on purpose** | Hunter infers persistence from the layer and the materialisation. Sometimes that is wrong, and a person saying so outranks a guess |
| **That an off-plan build is accepted** | A table built ahead of its design is a finding. Sometimes it is one somebody already agreed to |
| **Who owns what, and what one row means** | Neither is in the manifest or the design. Both are what make a finding routable and a table understandable |
| **That a rule is being left for now** | With a reason and an end date |

## Reasons: where they are needed

This is the rule that makes the file usable.

| Entry | Needs a reason | Why |
|---|---|---|
| An owner, a grain, a business name, a domain | No | It is information, not an exception |
| A persistence declaration | Yes | It overrides a signal Hunter computed |
| Any approval | Yes, and a named approver | Somebody is accepting something |
| A silenced rule | Yes, and an end date | Otherwise it goes quiet permanently |

??? note "Why not require a reason for everything"

    An earlier draft did. That made recording an owner annoying enough that
    nobody would, which defeats the point of the file.

## Marking a table temporary

The most common reason to open this file.

```yaml
models:
  int_shop__orders:
    persistence: temporary
    reason: a working step feeding the order fact, not for reporting from
    review_by: 2027-01-31
```

The table is then not judged as a finished table: no consumer-facing
description expected, no owner, no key tests, and no complaint that reports do
not read from it.

<div class="key" markdown>
**A declaration here beats every signal Hunter can compute.** It sits first in
the [precedence chain](concepts.md#3-temporary-verified-or-permanent), which is why
it costs a written reason. The report says which signal decided, so the answer
can be argued with.
</div>

## Recording plain information

No reason needed. This closes the "no identifiable owner" finding and puts the
grain in plain English on the report.

```yaml
models:
  wh_commerce__order_fact:
    owner: commerce
    grain: one row per order
    business_name: Orders
    domain: sales
```

??? note "Everything a table entry accepts"

    ```yaml
    models:
      # Lifecycle, and metadata the design cannot express.
      wh_commerce__forecast_fact:
        status: building        # planned, building, live, deprecated, retired
        persistence: verified   # temporary, verified or permanent
        verified_by: sav        # required with verified
        verified_on: 2026-09-08
        reason: confirmed at the forecast review
        owner: commerce
        entity_type: fact      # fact, dimension, aggregate, bridge, mapping
        grain: one row per product per week
        scd_type: 2
        source_of_truth: the forecasting service
        business_name: Forecast
        domain: sales

      # Where the built name and the designed name differ and normalised
      # matching cannot bridge it. This settles the reconciliation row.
      wh_commerce__orders_v2:
        implements: wh_commerce__order_fact
    ```

## Accepting an off-plan build

Still appears on the report, as an approved exception rather than a fault.

```yaml
off_plan_approved:
  - model: wh_commerce__legacy_fact
    reason: kept from the previous warehouse while reports move across
    approved_by: sav
    approved_on: 2026-09-08
    review_by: 2026-12-31
```

## Silencing a finding, with an end date

```yaml
ignores:
  - rule: documentation.model_description_missing
    models: ['stg_legacy__*']       # globs accepted
    reason: legacy staging, scheduled for removal this quarter
    expires: 2027-01-31
```

`expires` is required and has no "never" value. On that date the finding comes
back on its own.

??? note "Declaring business entities with no conceptual diagram"

    ```yaml
    conceptual:
      - name: returns
        business_name: Returns
        domain: sales
        note: agreed at the design review, not designed yet
    ```

## Nothing here hides a finding

An approved exception appears as an approved exception, with its reason and
review date. A silenced finding appears as silenced, with the date it comes
back.

The register changes how a finding is classified and reported. It cannot make
one disappear. Otherwise it would become the place a score goes to be improved
without anything improving.

## It reports its own staleness

A register nobody prunes stops being a record of decisions and becomes a hiding
place, so Hunter checks it against the repository.

| Finding | When |
|---|---|
| `register.entry_matches_no_model` | An entry for a table that no longer exists |
| `register.approval_matches_no_model` | An approval covering nothing |
| `register.review_overdue` | A review date that has passed |
| `register.approval_review_overdue` | An approval whose review date has passed |
| `register.ignore_expired` | A silence that has expired. The finding is back |
| `register.ignore_names_unknown_rule` | A misspelt or renamed rule, silencing nothing |

The last matters more than it looks. A silence naming a rule that does not
exist silences nothing, and without this check it would sit there looking as
though it were doing something.

## Let `hunter init` fill it in

```bash
hunter init
```

Where a manifest is present, this scores the repository and lists the tables it
would flag, each with a blank field.

```yaml
models:
  # Hunter found no owner for these. Fill in a team name against each.
  wh_master__customer_dim:
    owner:            # who to ask about this table
    grain:            # what one row of it means, in plain words

off_plan_approved: []
  # Built and on no design. Either add each one to the design, or approve it
  # here: uncomment the block, fill in the reason and the approver, and delete
  # the [] on the line above.
  # - model: wh_commerce__legacy_fact
  #   reason:
  #   approved_by:
  #   review_by: 2027-09-08
```

The off-plan tables are listed as comments rather than entries, because an
approval is only valid with a reason and a named approver, and a file that is
not valid stops `hunter score` from running. Empty sections are written as
`{}` or `[]` for the same reason.

Filling in blanks against a list works. Authoring a file from nothing does not.

## Advice from use

| | |
|---|---|
| **Owners first** | The most common systemic gap, and the one that makes every other finding routable. A finding with no owner is one nobody picks up |
| **Write grain in plain words** | "One row per store per day", not `store_pk + date_pk`. It is the most useful thing a non-technical reader can be told about a table |
| **Set review dates you mean** | An overdue review is a finding. That is the point: an exception nobody revisits has quietly become permanent |
| **Prefer `hunter.yml` for a rule that does not fit you** | Disabling a rule that is genuinely wrong for you is straightforward. Silencing it again and again is paperwork |
