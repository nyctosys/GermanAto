# GermanATO Design System

The structure and restraint follow the Tesla-inspired system the owner supplied: flat surfaces, one action colour, quiet type, colour-only interactions. The colours are taken from the GermanATO logo (`web/public/logo.png`), sampled from the file, not guessed.

## 1. Visual theme and atmosphere

A workshop tool that gets out of the way. Surfaces are white on a light ash floor, with no shadows, no gradients and no decorative borders. Text is near-black graphite. A single chromatic colour, the logo's **GermanATO Red**, marks the primary action on a screen and nothing else. The product's real objects carry the visual weight: the number plate, the inspection report, the invoice. The interface is the frame around them.

**Key characteristics**
- **One action colour:** GermanATO Red (`#D10A01`), only on primary buttons.
- **Brand as identity, not decoration:** the logo's oxblood hexagon (`#6D0000`) appears in the logo itself and as the pressed state of primary buttons.
- **Flat surfaces:** white panels on a Light Ash page. Panels are separated by colour and spacing, never by shadow.
- **Shapes:** 4px corners on every control, 12px on panels.
- **Type:** two weights only, 400 and 500. Normal letter-spacing. No uppercase transforms in the interface.
- **Motion:** colour-only transitions at 0.33s. The pressed colour shows instantly, so a tap feels immediate.

## 2. Colour palette and roles

### Brand (from the logo)

| Name | Hex | In the logo | Role in the app |
|---|---|---|---|
| Logo Red | `#F10A01` | "GERMAN" | Brand reference only. White text on it is 4.4:1, below AA, so it is not used behind text. |
| **GermanATO Red** | `#D10A01` | Logo Red deepened just enough for AA | Brand accents, primary text links, sidebar current bar |
| **Action Teal** | `#0F766E` | — | **Primary buttons** (white text); hover `#0D5F59`, pressed `#0A4A45` |
| Red Hover | `#B80800` | — | Primary button hover (white text 6.8:1) |
| **Hexagon Oxblood** | `#6D0000` | The hexagon (77% of the logo) | Primary button **pressed** state; "German" in the wordmark |
| Logo Black | `#000000` | "ATO" | "ATO" in the wordmark |
| **Tagline Amber** | `#F98B00` | "gets your car road ready" | Warning accents only (a 3px left rule on warning notes). Never text on white (2.4:1). |
| Car Silver | `#D0D0D0` | The car's body | Decorative dividers only |

### Neutrals (Tesla's greys, with the blue undertone removed to match the logo's neutral black)

| Name | Hex | Role | Contrast |
|---|---|---|---|
| Carbon | `#171717` | Headings, primary text, focus ring | 17.9:1 on white |
| Graphite | `#393939` | Body and secondary text | 10.5:1 on Light Ash |
| Pewter | `#5C5C5C` | Tertiary text, hints, table heads | 6.1:1 on Light Ash |
| Silver Fog | `#8E8E8E` | Placeholders, **input borders** (3.3:1, meets the 3:1 boundary rule) | — |
| Car Silver | `#D0D0D0` | Strong dividers | — |
| Cloud Gray | `#EEEEEE` | Table row dividers, list separators | — |
| Light Ash | `#F4F4F4` | Page background, hover fill, skeletons | — |
| White | `#FFFFFF` | Panels, inputs, sidebar | — |

### Status (an app needs them; the marketing site didn't)

| State | Text | Soft fill | Note |
|---|---|---|---|
| Success | `#1E7B34` | `#E8F5EC` | Paid, signed, done |
| Warning | `#8A4B00` | `#FFF3E0` | Low stock, draft, missing proof; 3px Tagline Amber rule |
| Error | `#B80800` | `#FDECEC` | Always paired with words ("This didn't load", "Out"), never colour alone |

### Rules
- **One action colour.** At most one red button per view. Every other action is secondary (white with a Silver Fog border) or ghost.
- **No gradients, no glows, no shadows** on surfaces. The only overlay is the drawer scrim, `rgba(23,23,23,0.4)`.
- **Focus:** a 2px Carbon outline with a 2px offset, visible on every control.

## 3. Typography

- **Family:** Geist, a geometric engineered sans, stands in for Universal Sans, which isn't licensed for this app. Fallbacks: `ui-sans-serif, system-ui`.
- **Weights:** 400 (body) and 500 (headings, labels, buttons). Nothing else.
- **Letter-spacing:** normal everywhere.
- **Case:** sentence case everywhere in the interface. Printed documents reproduce the owner's paper forms, including their capitals.

| Role | Size | Weight | Line height |
|---|---|---|---|
| Page title | 28px (1.75rem); 24px under 768px | 500 | 1.2 |
| Section title | 18px (1.125rem) | 500 | 1.3 |
| Body / inputs | 16px (1rem); never below 16px on inputs, so iOS doesn't zoom | 400 | 1.5 |
| Labels, buttons, nav | 15px (0.9375rem) | 500 | 1.3 |
| Hints, table heads, meta | 14px (0.875rem) | 400 | 1.4 |
| Figures | Tabular numerals (`.num`) wherever numbers line up | — | — |

## 4. Components

| Component | Spec |
|---|---|
| Primary button | Teal (`#0F766E`), white text, 500, 4px radius, min-height 44px, padding 0 20px. Hover `#0D5F59`; pressed `#0A4A45`, shown instantly. Disabled: 55% opacity. Forward actions: Issue, Send, Record, Approve, Add, Check in. |
| Success button | Success green (`#1E7B34`), white text, same size. Hover `#18662B`; pressed `#124F21`. Use for Save, Save draft, Save as draft, Save changes, and finish/complete actions. |
| Danger button | Error red (`#B80800`), white text, same size. Hover `#9A0600`; pressed Hexagon Oxblood. Use for Delete, Discard, Remove, Void, Retire, Cancel permanently, Reject. |
| Secondary button | White, Carbon text, 1px Silver Fog border, same size. Hover Cloud Gray fill and darker border. Neutral dismiss: Cancel, Keep it, Not now. |
| Ghost button | Cloud Gray fill, Carbon text, no border. Hover Car Silver with a visible border. A quiet action, but always a visible pill: bare text is reserved for links, which are underlined. |
| Inputs and selects | White, 1px Silver Fog border, 4px radius, min-height 44px, 16px text. Focus: Carbon border plus focus ring. Invalid: error border plus a message under the field. |
| Panels (cards) | White on the Light Ash page, 12px radius, **no border, no shadow**. Header separated from the body by a Cloud Gray rule. |
| Tables | Pewter 14px heads in sentence case, Cloud Gray row rules, rows at least 48px. Under 640px each row becomes a labelled stack. |
| Badges | Soft status fill with its text colour, 4px radius, 14px/500. |
| Sidebar | White, no border, separated from the Light Ash content by colour. The current item gets a Light Ash fill, Carbon text at 500, and a 3px GermanATO Red bar on its left edge (the only red outside a button). |
| Drawer (under 960px) | Slides in from the left and leaves the same way, over a scrim. Escape and a tap outside close it. |
| Number plate | The car's identity mark: white, 2px Carbon border, 4px radius, tabular figures. |

## 5. Layout

- **Spacing:** 8px base (8, 16, 24, 32, 48).
- **Content width:** up to 1152px, centred.
- **Gutters:** 16px under 640px, 24px up to 960px, 40px above.
- **Separation:** one panel per idea, separated by 16px of Light Ash, not by lines.
- **Tap targets:** 44px minimum for every tappable thing.

## 6. Depth

| Level | Treatment | Use |
|---|---|---|
| 0 | Flat | Everything |
| 1 | Translucent white (`rgba(255,255,255,0.85)` + blur) | Sticky phone top bar and sticky section nav |
| 2 | Scrim `rgba(23,23,23,0.4)` | Behind the drawer |

## 6b. Pressable things look pressable

- **Buttons** are filled or outlined pills (primary teal, success green, danger red, secondary white with a border, ghost Cloud Gray). Every enabled button darkens or fills on hover; pressed colour lands instantly. Bare text is never a button.
- **Text links** are underlined.
- **A whole row that is a link** (lists of customers, cars, the steps of a job) carries a chevron on its right edge.
- **Every enabled control shows the pointing hand** on a pointer device; disabled ones show the not-allowed cursor.

## 7. Do and don't

**Do**
- Keep teal (`#0F766E`, white text) for the main forward action on each screen; green for save/complete; filled red only for destructive confirms. Brand red remains for text links and the sidebar current bar.
- Let the real object lead each page (plate, report, invoice).
- Keep transitions colour-only at 0.33s, with an instant pressed colour.
- Use sentence case and weights 400/500.

**Don't**
- Use the red for decoration, headings, icons or large fills.
- Use Logo Red `#F10A01` behind text (it fails contrast).
- Add shadows, gradients or borders to panels.
- Use scale or translate effects on hover or press.
- Put amber text on white.

## 8. Responsive behaviour

| Width | Changes |
|---|---|
| Under 640px | Single column. Tables stack. Buttons go full width in forms. |
| 640–960px | Two-column forms. The sidebar becomes a top bar and drawer. |
| Above 960px | Fixed white sidebar (256px). Three-column forms where the fields are short. |
