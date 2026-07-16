# Documentation maintenance policy

## Update in the same change

Update documentation when code changes:

- a domain formula or ranking rule;
- a field definition or unit;
- a rotation/orientation constraint;
- a session schema or serializer contract;
- a shared wrapper/context key;
- a public URL/default/demo;
- a PDF metric or visualization source;
- a catalogue field used by tools;
- a known limitation or benchmark claim.

## Keep AGENTS.md small

`AGENTS.md` contains durable operating rules and routes agents to detailed files. Put formulas and long feature descriptions in `docs/`.

## Verify historical notes

When an agent discovers that a “current implementation note” is outdated:

1. confirm current behaviour with code/tests;
2. update the note and date/context;
3. preserve the durable decision if it still applies;
4. record an intentional architecture change in `engineering/decision-log.md`.

## Do not document guesses as facts

Use the labels from `docs/README.md`. For exact code behaviour not yet inspected, write “repository verification required.”

## Documentation review questions

- Can a new agent identify the source of truth?
- Does the document distinguish intended behaviour from current implementation?
- Are formulas and units explicit?
- Are standalone, Flow, relevant multi-product, SEO, graphics, and report impacts stated?
- Are safety and deployment boundaries clear?
- Is a known regression now preventable by a test or checklist?
