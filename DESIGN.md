# ARIMA design direction

Direction supplied by the product owner (answers to the direction questions), transcribed here as
data for the agent. Scope of this pass: the accreditation core (shell, dashboard, PDCA matrix,
EP list, document repository, login).

## Identity

Hospital accreditation office. The users are coordinators and pokja admins who read dense tables
all day and then print the result for a surveyor. The interface should read like a well-kept
quality register: quiet, legible, no decoration that competes with the data.

Personality: **calm, administrative, exact.** Not clinical-warm, not SaaS-marketing.

## Dials

`Dial: ENERGY 1 / RHYTHM 2 / MOTION 1`

- ENERGY 1: no gradients, no glows, no oversized type. The data is the loudest thing on screen.
- RHYTHM 2: sections differ by composition (one focal panel, then tables), not by decoration.
- MOTION 1: hover, focus and disclosure only. No scroll reveals, no looping animation.

## Palette

2 cores + 1 accent, plus semantic status colours that only ever mean status.

| Role | Token | Value | Reason |
|---|---|---|---|
| Ink | `--ink-900` | `#141C2E` | Body text, 17.0:1 on white |
| Ink 2 | `--ink-700` | `#33405A` | Secondary text, 10.4:1 |
| Ink 3 | `--ink-500` | `#55637C` | Muted labels, 6.1:1 |
| Canvas | `--canvas` | `#F5F7FA` | App background, separates from white surfaces |
| Rail | `--rail` | `#141C2E` | Navigation rail, same ink family as text |
| Accent | `--accent` | `#4F5BD5` | Kept from the existing system: the hospital's chosen indigo. Actions, links, active nav, focus |
| Success | `--success` | `#15803D` | Score 10 / evidence complete |
| Warning | `--warning` | `#B45309` | Score 5 / partial |
| Danger | `--danger` | `#B91C1C` | Score 0 / missing |

Status colours are never the only signal: every score, badge and bar carries a number or a label.
Colour is used for text and thin rules, not for filled blocks of attention.

## Typography

- **IBM Plex Sans** for everything. Chosen over Inter because the product is institutional and
  document-shaped: Plex was drawn for IBM's technical documentation, has a larger x-height at
  12-14px, and does not read as the default AI stack.
- **IBM Plex Mono** for EP codes, standard codes, scores, percentages, money and timestamps.
  These are identifiers that get compared column to column, so tabular alignment earns the mono.
- No display face. Headings are Plex Sans 600 with `-0.01em` tracking.
- Scale: 12 / 13 / 14 / 16 / 20 / 26 / 34. Body 14/1.5.

## Form

- Radius: 4px badges, 6px controls, 8px buttons, 10px panels. No pills except the status chip
  inside a score control, where the pill shape mirrors the score band.
- Elevation: flat. 1px `--line` borders carry structure. Shadow only on overlays
  (dropdown, modal, toast) because those genuinely float above the page.
- Spacing scale: 4 / 8 / 12 / 16 / 24 / 32 / 48. Section gaps 32, table cell padding 10x12.

## Composition rules for this product

- Every screen answers one question. Dashboard: *how ready are we, and which pokja is behind?*
  Matrix: *what is missing in this standard?* Repository: *where is that document?*
- One focal element per screen. On the dashboard it is the readiness score; the supporting facts
  sit beside it at half the weight, never as four equal cards.
- Tables, not card grids, wherever the user compares rows.
- Empty states name the cause and the next action, never "no data".
- Indonesian copy. No em dashes. No invented numbers, statuses or names: everything rendered
  comes from the database.

## What was removed and why

- Gradient hero and radial glow: decoration that carried no hierarchy (ENERGY 1).
- "SYSTEM: NOMINAL" status chip: a fabricated system status (no such monitor exists).
- Coloured left stripe on metric cards: colour without meaning.
- Vision/mission block on the dashboard: real content, but not this screen's job; it lives on
  Profil RS and in the printed documents.
- Organisation tree on the dashboard: 65 units of nested text; the dedicated Hierarki Unit page
  does it properly.
- Per-year rainbow colours on the Renstra roadmap: the year is the label, not a category.
