# Tiny Shop Conceptual Model

## Overview

What the shop needs the warehouse to hold, in business language and before
anyone decides how to build it. The diagram is in
[`conceptual_model.mermaid`](conceptual_model.mermaid).

This is the entry point for anyone who does not read SQL. It names the things
the business cares about and nothing else: no columns, no table names, no code.

## Entities

Entities are organised into entity groups. That makes the warehouse easier to
navigate and maintain, and it gives each group an owner. Everything here sits in
the `shop` group.

| Entity | What it is | State |
|---|---|---|
| orders | An order placed on the shop platform | Built |
| customers | Someone who has ordered at least once | Built |
| products | Something the shop sells | Built |
| daily sales | Order totals rolled up to a day | Built |
| forecasts | Expected units by product and week | Marked as deviating |
| suppliers | Someone the shop buys from | Planned |
| returns | An order or line sent back | Planned |

## Conceptual model design

Colour on the diagram carries the state: plain is built, dashed is planned, and
a red outline with a warning glyph marks something that deviates from the
design.

That colouring is maintained by hand, which means it drifts. Hunter reads the
entity names and the grouping from this file but works out the state itself from
the repository, and reports any entity where the two disagree. Treat the colours
here as a claim rather than as a record.

## Contributing

Add an entity to the diagram first, in business language, before designing a
table for it. An entity here with no design is the backlog, and Hunter reports
it as such rather than as a fault.

## Considerations

The conceptual model captures the requirements gathered when the model was put
together. Refinements are expected. Sign-off sits with the analytics lead or the
domain owner, who is the intended owner of the resulting data assets.
