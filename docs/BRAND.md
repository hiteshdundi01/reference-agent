# Brand

A neutral starting point. Replace the palette, the fonts and the mark for each product; keep the rules.

## Fonts

Bundled with the dashboard from the `@fontsource-variable` packages, so no page or test loads them from outside:

- **Headings and body:** Inter
- **Numbers, ids and code:** JetBrains Mono

## Colors

- **Primary:** Indigo `#4F46E5`, white text
- **Success:** Emerald `#059669`, white text
- **Warning:** Amber `#D97706`, white text
- **Danger:** Rose `#E11D48`, white text
- **Information:** Sky `#0284C7`, white text
- **Ink on light backgrounds:** Slate `#0F172A`
- **Ink on dark backgrounds:** Mist `#E2E8F0`
- **Muted text:** `#64748B` on light backgrounds and `#94A3B8` on dark ones
- **Links:** Indigo on light backgrounds, `#A5B4FC` on dark ones, which keeps them readable on a dark panel

A request's state always has the same color:

| State                 | Color   |
| --------------------- | ------- |
| Waiting               | Sky     |
| Working               | Indigo  |
| Held for a supervisor, stalled | Amber |
| Refunded              | Emerald |
| Declined, failed      | Rose    |
| Escalated             | Slate   |

## Surfaces

- **Light mode:** page `#F8FAFC`, white panels
- **Dark mode:** page `#0B1120`, panels `#111827`

Panels have rounded corners, no outline and a faint shadow. The header is a band of Slate across the top of the page (black in dark mode), with white text and the product's name.

Colors, spacing and radii are CSS variables in `dashboard/src/styles.css`. The theme follows the system's setting.

## Icons

Use Lucide icons where an icon says something at a glance: a state, an action's button, a choice. Beside text, an icon is the text's size. Never use emojis.

## Avoid

- Borders on one edge of a panel
- Heavy gradients
- Copy that restates the obvious. Label things plainly and say what an action does.

## Tone

Plain business English in US spelling. Short labels, no jargon and no exclamation marks. Write money in US dollars, such as $1,250.00.
