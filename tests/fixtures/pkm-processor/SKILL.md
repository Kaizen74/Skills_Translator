---
name: pkm-processor
description: Classify and file inbox notes into a PKM vault using a fixed rubric — concepts, people, ventures, crossovers, reading, synthesis.
---

# PKM Processor

## Purpose
Process a raw inbox note into the correct vault folder with consistent structure and links.

## When to use
When the user sends a note, article snippet, or idea starting with "process:".

## Method
1. Read the note and identify its primary type: Concept, Person, Venture, Crossover, Reading, or Synthesis.
2. Score relevance to active ventures on a 1-5 scale.
3. Extract 2-4 key claims in the note's own words — never invent claims.
4. Propose wikilinks to related existing notes.
5. Draft the filed note using the output format below.

## Output format
- **Type:** one of the six types
- **Relevance score:** 1-5 with one-line reasoning
- **Key claims:** bulleted, quoted or closely paraphrased
- **Links:** proposed [[wikilinks]]
- **IMPLICATION FOR PORTFOLIO:** (owner completes — do not fill)

## Example
Input: "process: Article argues vertical AI agents beat horizontal ones in regulated industries."
Output:
- Type: Concept
- Relevance score: 4 — touches the compliance venture directly
- Key claims: "vertical AI agents beat horizontal ones in regulated industries"
- Links: [[AI Agents]], [[Regulated Industries]]
- IMPLICATION FOR PORTFOLIO:

## Escalation
If the note contains more than three distinct claims spanning multiple ventures, escalate to the Claude tier for a full synthesis pass.
