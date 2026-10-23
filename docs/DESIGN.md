---
name: Incident Intelligence
description: Evidence-grounded incident diagnoses, laid out as an investigation report.
colors:
  ground: "#f4f5f7"
  paper: "#ffffff"
  paper-sunk: "#f8f9fa"
  ink: "#16181d"
  ink-2: "#3c4250"
  ink-3: "#5d6470"
  rule: "#d9dde3"
  rule-strong: "#16181d"
  field-stroke: "#b8bec8"
  navy: "#1f3a5f"
  navy-deep: "#16304f"
  navy-wash: "#eef2f7"
  navy-ink: "#c9d4e3"
  on-navy: "#ffffff"
  tag: "#f2b705"
  tag-wash: "#fff6d6"
  red: "#b42318"
  red-wash: "#fdeceb"
typography:
  title:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "1.625rem"
    fontWeight: 700
    lineHeight: 1.25
    letterSpacing: "-0.015em"
  cause:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "1.3125rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 700
    lineHeight: 1.5
  body:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
  meta:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Public Sans, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 800
    lineHeight: 1.5
    letterSpacing: "0.12em"
  mono:
    fontFamily: "Source Code Pro, ui-monospace, monospace"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.5
    letterSpacing: "0.02em"
rounded:
  none: "0px"
spacing:
  s-1: "4px"
  s-2: "8px"
  s-3: "12px"
  s-4: "16px"
  s-5: "20px"
  s-6: "24px"
  s-8: "32px"
  s-10: "40px"
components:
  button-primary:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.paper}"
    typography: "{typography.meta}"
    rounded: "{rounded.none}"
    padding: "9px 16px"
  button-primary-hover:
    backgroundColor: "{colors.navy-deep}"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.navy}"
    typography: "{typography.meta}"
    rounded: "{rounded.none}"
    padding: "9px 16px"
  button-secondary-hover:
    backgroundColor: "{colors.navy-wash}"
  exhibit-tag:
    backgroundColor: "{colors.tag}"
    textColor: "{colors.ink}"
    typography: "{typography.mono}"
    rounded: "{rounded.none}"
    padding: "3px 6px"
  exhibit-tag-missing:
    backgroundColor: "{colors.red-wash}"
    textColor: "{colors.red}"
    typography: "{typography.mono}"
    rounded: "{rounded.none}"
    padding: "3px 6px"
  exhibit-row-active:
    backgroundColor: "{colors.tag-wash}"
  input-field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "8px 10px"
  nav-bar:
    backgroundColor: "{colors.navy}"
    textColor: "{colors.navy-ink}"
    height: "48px"
    padding: "0 32px"
  report-sheet:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.none}"
    padding: "32px 40px 40px"
---

# Design System: Incident Intelligence

## Overview

**Creative North Star: "The Probable Cause Report"**

The interface is laid out like an accident investigation report: a white report sheet on a
cool grey desk, the probable cause stated first inside a ruled box, findings numbered 2.1,
2.2 and so on, and every claim pointing at a tagged exhibit that the reader can open and check.
The reader is an on-call engineer under time pressure, so the page is dense, plain and
scannable. Hierarchy comes from type weight, small uppercase section labels and hairline rules,
not from colour fields, cards or shadows.

Colour is scarce and each world colour has one job. Navy carries the bar, section labels,
links and primary actions. Exhibit yellow appears only on exhibit tags and the active exhibit.
Red appears only for high or critical severity and for failed, invalid or missing states. There
is no green: a valid diagnosis is stated in navy text. The system rejects the sidebar app shell
with rounded cards and pills, and the chat or answer-bubble look.

The one interaction the system is built around is the exhibit link: pointing at or focusing an
exhibit tag highlights its row in the exhibits column and brings it into view; clicking pins the
row open with its query, values and source link. Motion is limited to short colour and ring
fades on that link; nothing enters, slides or scales.

**Key Characteristics:**
- One white report sheet per page on a cool grey ground, bounded by a 1px hairline.
- Square corners everywhere; no shadows used for depth.
- The probable cause sits in a 2px ink box with its label set into the top border.
- Numbered findings, timeline and actions as fixed-column tables separated by hairlines.
- Exhibit tags (EX-1, EX-2) in monospace on yellow, the only yellow on the page.
- Public Sans for all text; Source Code Pro for IDs, queries, releases and times.

## Colors

A near-neutral paper-and-ink palette with three world colours, each restricted to one job.

### Primary
- **Report Navy** (#1f3a5f): the top bar, section labels (FINDINGS, EXHIBITS), links, primary
  buttons, focus rings, chart lines, and the "valid" status text. Its darker step **Pressed
  Navy** (#16304f) is the hover state of navy fills; **Navy Wash** (#eef2f7) is the hover fill of
  outlined navy buttons; **Bar Ink** (#c9d4e3) is secondary text on the navy bar.

### Secondary
- **Exhibit Yellow** (#f2b705): exhibit tags and the tag cell of an exhibit row, nothing else.
  **Exhibit Wash** (#fff6d6) marks the active or pinned exhibit row.

### Tertiary
- **Severity Red** (#b42318): HIGH and CRITICAL severity words, the border and label of an
  invalid or failed probable cause, citation problems, source errors, form errors and tags that
  cite evidence missing from the snapshot. **Red Wash** (#fdeceb) backs a flagged claim, a
  missing tag and the source-error list.

### Neutral
- **Desk Grey** (#f4f5f7): the page ground behind every sheet.
- **Paper** (#ffffff): the report sheet and any surface sitting on it.
- **Sunk Paper** (#f8f9fa): query blocks and table row hover.
- **Ink** (#16181d): body text, and as the strong rule: the cause box, the 2px rule over
  actions and forms, table header rules.
- **Ink 2** (#3c4250): secondary text, summaries, MEDIUM and LOW severity.
- **Ink 3** (#5d6470): captions, meta rows, finding numbers, "Not established" findings.
- **Hairline** (#d9dde3): every row and sheet border.
- **Field Stroke** (#b8bec8): input borders and the scrollbar thumb.

### Named Rules
**The One Job Rule.** Navy, yellow and red each have exactly one job. Yellow is for exhibit
tags and the active exhibit only; red is for high or critical severity and failed, invalid or
missing states only. A new screen that needs emphasis uses weight or a rule, not a new colour.

**The No Green Rule.** There is no success colour. Valid and healthy states are stated in navy
or ink text; the absence of red is the signal.

**The Word Before Colour Rule.** Severity and status are always written as words (HIGH,
"Valid", "failed the citation check"); colour reinforces the word and is never the only signal.

## Typography

**Body Font:** Public Sans (with system-ui, sans-serif), weights 400, 500, 600, 700, 800,
self-hosted.
**Label/Mono Font:** Source Code Pro (with ui-monospace, monospace), weights 400 and 500,
self-hosted.

**Character:** A plain government-report sans carries everything, from the title to the
section labels; a monospace face marks anything an engineer might copy or match against another
system. Numerals are tabular throughout.

### Hierarchy
- **Title** (700, 26px, 1.25, -0.015em): the incident or page title, balanced, at most 40ch.
  Drops to 22px under 720px.
- **Cause** (600, 21px, 1.4, -0.01em): the probable cause statement only, at most 62ch.
- **Headline** (700, 16px): empty-state titles, status page titles, incident links in the list
  (600).
- **Body** (400, 14px, 1.5): running text; summaries capped at 72ch.
- **Meta** (13px): meta rows, cause facts, buttons (600), table secondary text.
- **Label** (800, 12px, 0.12em, uppercase): section headings such as PROBABLE CAUSE,
  FINDINGS, EXHIBITS and table column headers. These are the real headings of their sections.
- **Mono** (500, 12px): exhibit tags, ID lines (investigation, snapshot, diagnosis), queries,
  release names and timeline times.

### Named Rules
**The Copyable Is Mono Rule.** IDs, queries, releases, times and exhibit tags are set in
Source Code Pro; prose never is.

**The Weight Not Size Rule.** The ramp is small (12 to 26px). Emphasis inside a row is a bold
lead-in such as "Ruled out." or a 700 value, not a bigger size.

## Layout

The page is a 48px navy bar over one report sheet, max 1440px wide, centred with 20px top and
32px side padding on the ground. On the incident page the sheet is two columns: the report
(fluid, padding 32px 40px 40px, hairline on its right) and the exhibits column (470px, padding
32px 24px 24px). The exhibits column is sticky and scrolls on its own so a cited exhibit can be
brought into view without moving the report.

Spacing runs on a 4px base (4, 8, 12, 16, 20, 24, 32, 40). Sections are 32px apart; table rows
have 12px vertical padding and a hairline above. Tables use fixed layout so a state change
restyles a row and never reflows it; the citation column is 184px and right-aligned.

Breakpoints: at 1100px the sheet becomes one column with exhibits below the report (a "back"
link returns to the citing claim). At 860px the incident list drops its Opened column. At 720px
the bar wraps with the nav on its own 40px row and shortened labels, tables become stacked
rows, and sheet padding drops to 20px by 16px. At 560px the incident list becomes stacked rows.
Forms sit on a narrower 760px sheet.

## Elevation & Depth

The system is flat. Depth is conveyed by the ground-to-paper step, 1px hairlines and the 2px
ink rule. `box-shadow` appears only as rings: the focus ring, the active nav underline and the
active exhibit-tag outline, never as a drop shadow.

### Shadow Vocabulary
- **Focus ring** (`box-shadow: 0 0 0 2px #ffffff, 0 0 0 4px #1f3a5f`): every focusable element;
  inverted (navy gap, white ring) on the navy bar.
- **Active tag ring** (`box-shadow: 0 0 0 2px #16181d`): an exhibit tag whose exhibit is active
  or pinned.
- **Current nav underline** (`box-shadow: inset 0 -3px 0 #ffffff`): the current page in the bar.

### Named Rules
**The Paper On A Desk Rule.** Surfaces are separated by tone and rules, never by drop shadows.
If something needs to stand out, give it a heavier rule (2px ink) or a wash.

## Shapes

Every corner is square (0px), including inputs and buttons. Form language is ruled: 1px
hairlines between rows, a 2px ink rule above the actions block, form fields and table headers,
and a 2px ink box around the probable cause with its uppercase label cut into the top border on
a paper background. Empty or pending states use a dashed border in Ink 3; invalid or failed
states turn the box border red.

## Components

### Buttons
Plain, rectangular, navy.
- **Shape:** square corners (0px), 1px navy border.
- **Primary:** navy fill, white 13px 600 text, padding 9px 16px (10px 18px on the form submit).
- **Secondary:** paper fill, navy text and border, same size.
- **Hover / Focus:** primary fades to Pressed Navy, secondary to Navy Wash (160ms); focus shows
  the 2px paper plus 2px navy ring.
- **Disabled:** 55% opacity and a not-allowed cursor; the cost of a paid run is stated next to
  the button.

### Exhibit Tags
The signature citation chip.
- **Style:** Exhibit Yellow fill, ink 12px Source Code Pro 500, padding 3px 6px, square, no
  border; text is EX-n.
- **State:** active or pinned adds a 2px ink ring (160ms). A tag citing evidence missing from
  the snapshot is red text on Red Wash with a 1px red inset outline and reads "ev-... not in
  snapshot".

### Probable Cause Box
- **Corner Style:** square.
- **Background:** paper, 2px ink border, padding 20px 24px.
- **Content:** label set into the top border; the 21px statement; a facts row of exhibit tags,
  confidence and service in 13px Ink 3 with values in 700 ink.
- **States:** dashed Ink 3 border for not diagnosed or running; red border and label for invalid
  or failed, with the citation problems listed under a 1px red rule.

### Findings, Timeline and Actions Tables
- **Rows:** hairline above, 12px padding, number or time column (64px or 96px), statement,
  184px right-aligned citation column.
- **Findings:** numbered 2.1, 2.2 in 700 Ink 3, each statement led by its kind in bold
  ("Contributing factor.", "Ruled out.", "Not established."); "Not established" rows are set in
  Ink 3.
- **Flagged claims:** Red Wash row fill with a red "Citation problem" line.

### Exhibit Rows
- **Style:** hairline above; a 52px tag cell and a body of meta (12px Ink 3) and a one-line
  summary (13px).
- **Active:** Exhibit Wash fill (200ms fade) and scrolled into view.
- **Pinned:** expands in place into a facts list, a collapsible query block on Sunk Paper with a
  hairline border, small navy line charts with a dashed ink onset marker, the source link and
  the list of claims citing it.

### Inputs / Fields
- **Style:** 1px Field Stroke border, paper fill, padding 8px 10px, square, max 520px wide;
  labels 600 above the field, hints 12px Ink 3.
- **Focus:** border turns navy plus the standard focus ring; radios use a navy accent colour.
- **Error:** 600 red text under the field.

### Navigation
- **Style:** 48px navy bar; product name in 13px 800 uppercase white; nav links (Incidents, New
  incident) in 500 Bar Ink, white on hover; the current page is white with a 3px white inset
  underline. The diagnosis budget sits at the right in 13px Bar Ink with the spent amount in
  white 600.
- **Mobile:** under 720px the bar wraps, nav moves to a full-width 40px row, and the budget uses
  a short form.

## Do's and Don'ts

### Do:
- **Do** put every page on one white report sheet (#ffffff, 1px #d9dde3 border) on the grey
  ground (#f4f5f7).
- **Do** state the main finding first in the 2px ink box, and cite evidence with EX-n tags
  that link to exhibit rows.
- **Do** separate rows with 1px hairlines and blocks with a 2px ink rule.
- **Do** set IDs, queries, releases and times in Source Code Pro.
- **Do** write status and severity as words, using red only for HIGH, CRITICAL and failed or
  invalid states.
- **Do** keep motion to colour and ring fades of 160 to 200ms on cubic-bezier(0.16, 1, 0.3, 1),
  and honour reduced motion.

### Don't:
- **Don't** use yellow for anything other than exhibit tags and the active exhibit.
- **Don't** introduce green or any other success colour; valid is navy text.
- **Don't** round corners or add drop shadows; depth is tone and rules.
- **Don't** wrap content in cards, pills or a sidebar shell, or present a diagnosis as a chat
  bubble.
- **Don't** animate entrances, slides or scale changes.
- **Don't** let a state change reflow a table row; restyle it in place.
