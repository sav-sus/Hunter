# The problem

Eight problems, stated by the people who have them. All of them turn up on
Rittman Analytics engagements, and none of them is answerable today without
reading a repository by hand. Each is a thing nobody can
answer today without reading the repository by hand.

## The eight

| Problem | What it costs today |
|---|---|
| People merge pull requests without seeing the debt they create | Debt builds up quietly and is found weeks later during unrelated work |
| A team lead cannot tell what is happening across a repository once the team grows | Review depends on the lead reading every change personally. It stops working past three or four contributors |
| Nothing distinguishes a working step from a finished table | Models get consumed that were never meant to last. Intermediate tables end up feeding reports directly |
| Nothing attributes a table or a gap to whoever created it | Nobody can be asked to fix anything, because nobody knows who built it |
| Modelling correctness is unchecked | Tables named as facts behave as dimensions, and the reverse. That produces grain errors, double counting, and the class of reporting discrepancy that takes days to trace |
| dbt and the reporting layer drift apart | A column rename silently breaks a dashboard. The client finds it, not the build |
| Nothing shows what a repository costs to run, or which tables run at all | Money is spent on tables nothing reads, with no basis for a conversation about it |
| Nothing measures whether quality is improving | "Are we actually getting anywhere" cannot be answered with evidence |

## Why existing tools do not close it

Several tools already check parts of this. dbt-score grades models,
dbt-project-evaluator finds structural problems, and dbt-checkpoint runs
pre-commit checks. Each works inside dbt and stops there.

The problems above mostly sit at the joins:

- Between the design and the repository. Nothing compares what was specified
  against what was built.
- Between the repository and the reporting layer. Nothing tells you a dbt
  change will break a LookML field.
- Between the repository and the people in it. Nothing routes a gap to whoever
  can close it.
- Between one sprint and the next. Nothing says whether things improved.

Hunter wraps the existing tools as inputs where it can, and spends its own
effort on the joins.

## What makes this hard

**Nobody agrees what correct looks like.** Layer names, naming conventions and
entity suffixes differ between clients and sometimes between teams. A tool with
built-in opinions is a tool that argues with its users on the first run.
Everything Hunter checks is declared in configuration.

**Findings are cheap and trust is not.** A tool that produces 500 findings on
its first run, or fires on 99% of models, gets muted within a week. Precision
matters more than coverage, and a rule that cannot be trusted is worse than no
rule.

**The audience is not one audience.** A team lead, an engineer, a junior
learning the conventions and a non-technical stakeholder all need the same
underlying facts presented differently. Producing an engineering report and a
separate "executive summary" means one of them is always out of date.

**A score invites an argument.** Any single number can be dismissed as
arbitrary. Every deduction has to name its rule, its evidence and its file, and
the whole ruleset has to be published, or the number will not survive its first
challenge.

## What success looks like

| Measure | Target |
|---|---|
| Score trend on the first repository | Rising over 8 weeks |
| Findings introduced per merged pull request | Falling |
| Time from a breaking dbt change to it being noticed | The same pull request, not a client report |
| Tables with a named owner | Above 90% within 8 weeks |
| Expired exceptions | Trending to zero |
| Repositories using it | 3 within a quarter |
