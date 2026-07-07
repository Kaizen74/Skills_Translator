---
name: deck-studio
description: Turn a rough idea into an investor-grade slide deck — storyline first, then generate the .pptx file.
---

# Deck Studio

## Purpose
Build persuasive decks in two stages: storyline design (method) and pptx generation (execution).

## Storyline method
1. State the single controlling idea of the deck in one sentence.
2. Structure slides as a pyramid: situation, complication, resolution.
3. Each slide gets one assertion title and at most three supporting points.
4. Write speaker notes that argue, not describe.

## Deck generation
Run `scripts/build_deck.py` to generate the .pptx file from the storyline outline.
This requires the Claude code-execution environment with python-pptx installed.

## Output format
Storyline outline as markdown, then the generated deck.pptx in the output folder.
