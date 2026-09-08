# The register

`.hunter/register.yml` is the file people actually edit. It records what the
team has decided about particular tables.

`hunter.yml` says what correct looks like, extending the Rittman Analytics
house standard, and changes rarely. The register records decisions about
individual tables and changes constantly. Different owners, different rates of
change, so two files.

## What it is for

Four things Hunter cannot work out on its own.

**That something is temporary on purpose.** Hunter infers persistence from the
layer and the materialisation. Sometimes that is wrong, and a person saying so
outranks a guess.

**That an off-plan build is accepted.** A table built ahead of its design is a
finding. Sometimes it is a finding somebody has already agreed to.

**Who owns what, and what one row means.** Neither is in the manifest or the
design, and both are what make a finding routable and a table understandable.

**That a rule is being left for now.** With a reason and an end date.

## Reasons: where they are needed and where they are not

This is the rule that makes the file usable.

| Entry | Needs a reason | Why |
|---|---|---|
| An owner, a grain, a business name, a domain | No | It is information, not an exception |
| A persistence declaration | Yes | It overrides a signal Hunter computed |
| Any approval | Yes, and a named approver | Somebody is accepting something |
| A silenced rule | Yes, and an end date | Otherwise it goes quiet permanently |

An earlier draft required a reason for every entry. That made recording an owner
annoying enough that nobody would, which defeats the point.

## The shape

```yaml
version: 1

models:
  # Plain information. No reason needed.
  wh_shop__order_fact:
    owner: commerce
    grain: one row per order
    business_name: Orders
    domain: sales

  # Overriding what Hunter inferred. Needs a reason.
  int_shop__orders:
    persistence: temporary
    reason: a working step feeding the order fact, not for reporting from
    review_by: 2027-01-31

  # Where the built name and the designed name differ, and normalised matching
  # cannot bridge it. This settles the reconciliation row.
  wh_shop__orders_v2:
    implements: wh_shop__order_fact
    owner: commerce

  # Lifecycle, and metadata the design cannot express.
  wh_shop__forecast_fact:
    status: building          # planned, building, live, deprecated, retired
    owner: commerce
    entity_type: fact
    grain: one row per product per week
    scd_type: 2
    source_of_truth: the forecasting service

# A table built ahead of its design, accepted. It still appears on the site, as
# an approved exception rather than as a fault.
off_plan_approved:
  - model: wh_shop__legacy_fact
    reason: kept from the previous warehouse while reports move across
    approved_by: sav
    approved_on: 2026-09-08
    review_by: 2026-12-31

# A finding somebody agreed to leave. It still appears, with this reason, and
# comes back automatically on the expiry date.
ignores:
  - rule: documentation.model_description_missing
    models: ['stg_legacy__*']
    reason: legacy staging, scheduled for removal this quarter
    expires: 2027-01-31

# Business entities, where there is no conceptual diagram to read them from.
conceptual:
  - name: returns
    business_name: Returns
    domain: sales
    note: agreed at the design review, not designed yet
```

## Nothing here hides a finding

An approved exception appears on the site as an approved exception, with its
reason and its review date. A silenced finding appears on the site as silenced,
with its reason and the date it comes back.

The register can change how a finding is classified and reported. It cannot make
one disappear. Otherwise it would become the place a score goes to be improved
without anything improving.

## It reports its own staleness

A register nobody prunes stops being a record of decisions and becomes a hiding
place. So Hunter checks it against the repository:

| Finding | When |
|---|---|
| `register.entry_matches_no_model` | An entry for a table that no longer exists |
| `register.approval_matches_no_model` | An approval covering nothing |
| `register.review_overdue` | A review date that has passed |
| `register.approval_review_overdue` | An approval whose review date has passed |
| `register.ignore_expired` | A silence that has expired. The finding is back |
| `register.ignore_names_unknown_rule` | A misspelt or renamed rule, silencing nothing |

The last one matters more than it looks. A silence naming a rule that does not
exist silences nothing, and without this check it would sit there looking like
it was doing something.

## Letting `hunter init` fill it in

```bash
hunter init
```

Where a manifest is present, this scores the repository and lists the tables it
would flag, each with a blank field:

```yaml
models:
  # Hunter found no owner for these. Fill in a team name against each.
  # Owner is plain information, so no reason is needed.
  wh_shop__customer_dim:
    owner:            # who to ask about this table
    grain:            # what one row of it means, in plain words
  wh_shop__daily_sales_xa:
    owner:
    grain:

off_plan_approved:
  # These are built and appear on no design. Either add them to the
  # design, or accept them here with a reason and a review date.
  - model: wh_shop__legacy_fact
    reason:           # why this was built ahead of the design
    approved_by:      # who accepted it
    review_by: 2027-09-08
```

Filling in blanks against a list works. Authoring a file from nothing does not.

## Advice from use

**Owners first.** It is the most common systemic gap and the one that makes
every other finding routable. A finding with no owner is a finding nobody will
pick up.

**Write grain in plain words.** "One row per store per day", not
`store_pk + date_pk`. It goes on the site next to the business name, and it is
the single most useful thing a non-technical reader can be told about a table.

**Set review dates you mean.** An overdue review is a finding. That is the
point: an exception nobody revisits has quietly become permanent.

**Prefer `hunter.yml` for a rule that does not fit how you work.** Use a
register silence for something true that is not being fixed yet. Disabling a
rule that is genuinely wrong for you is honest; silencing it repeatedly is
paperwork.
