# GermanATO — Design system (as implemented)

## Tokens

| Token | Value | Use |
|-------|--------|-----|
| `--orange` | `#DF5B28` | Primary actions, active nav, accents |
| `--black` | `#020202` | Sidebar, dark KPI cards |
| `--offwhite` | `#F0F0F0` | App background, muted cards |
| `--white` | `#FFFFFF` | Surfaces, light cards |
| `--radius` | `16px` | Cards / panels |
| `--font` | Montserrat | Headings, UI |
| `--font-num` | Source Code Pro | KPI numbers, money |

Defined in `web/src/index.css`. Fonts loaded from Google Fonts in `web/index.html`.

## Shell

- Dark collapsible sidebar (`AppShell`): brand mark, permission-filtered nav, collapse control, user + sign out.
- Top bar: page title, role subtitle, global search (cars/plates), notifications indicator, profile → settings.
- Responsive: below 900px sidebar stacks above content.

## Components (`web/src/components/ui.tsx`)

- `PageHeader`, `Panel`, `Field`, `FormGrid`, `ErrorBox`, `SuccessBox`, `Loading`, `Empty`, `Money`
- `KpiCard`, `PillStat`, `DotGrid`, `StatusBadge`, `NextActionBanner`, `Dialog`, `DataTable`

## Conventions

- Numbers and money use Source Code Pro (`.num` / `Money`).
- Primary buttons are orange; secondary outline; danger outline.
- Empty / loading / error states are required on list pages.
- Printables use `web/src/print/print.css` + `PrintShell` (A4).

## Accessibility

- Icon-only controls have `aria-label`.
- Dialog uses `role="dialog"` + backdrop click to close.
- Focusable native controls; status text not color-only (labels + badges).

## UX for workshop staff

- Dashboard KPIs deep-link to work queues.
- Job card / RO pages show **Next:** action banner from `/api/pipeline/next-action`.
- Money In / Money Out facades separate liabilities from revenue.
