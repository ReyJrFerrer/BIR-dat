# Alphalist dashboard redesign

Date: 8 October 2026  
Status: implementation specification and visual direction  
Deliverables: this document and one image-only desktop dashboard concept

## 1. Goal

Turn the existing long annualization review page into a compact workspace for importing a workbook, completing missing information, checking employees and downloading DAT/PDF files. Use restrained bento cards, strong visual hierarchy and the warm palette of the supplied BIRa LinkedIn cover.

The first screen should answer: which company/year is open, what needs attention, and where are the downloads? Ordinary users should not have to read transformation rules, evidence limits or internal mapping explanations to complete the task.

This is a UI/UX specification based on screenshots, not a code audit. Adapt component names to the existing repository. The image is a visual concept; behavior, labels, amounts and acceptance conditions in this document take precedence over any image-generation typography artifacts.

## 2. Reference inventory and findings

| Supplied image suffix | Observed screen | Design consequence |
| --- | --- | --- |
| 061952 | BIRa cover: almost-black brown, warm off-white text, orange-red accent, fine vertical lines | Adapt the palette and restrained contrast; do not copy the marketing banner into the dashboard |
| 062114 | Import page with oversized hero and narrow upload card | Replace with compact upload state inside the workspace shell |
| 062130 | Review heading, four counters, tabs, large multi-step checklist | Consolidate heading and priority actions; remove redundant checklist |
| 062153 | Missing values, expanded employer editor, reason input | Short actionable issue rows; employer card; no reason input |
| 062201 | Long automatic preparation accordion and optional notes | Replace preparation with a notification; remove technical explanations from ordinary UI |
| 062208 | Employee table | Make this the main working surface, add search/filter and preserve financial meaning |
| 062217 | Reconciliation, correction history, export section | Move totals into a compact summary; history on demand; exports in navigation |
| 062227 | Export controls, official evidence, clear-review button | Remove lower export section and requested hidden controls |
| 062303 | Employee detail page with large empty status panels and sticky reason input | Replace with focused employee drawer; short status and grouped fields |
| 062519 | Preparation table with Rule column | Remove the Rule column and any equivalent Rule tab entirely from user-facing preparation UI |

All reference filenames have the prefix `image(20261008-` and suffix `).png`. No live site or repository was accessed for this specification.

## 3. Required changes: explicit contract

| User request | Required behavior |
| --- | --- |
| Hide optional source review | Remove its section, counter, shared-answers links and employee-level optional-review accordions from the normal UI. Do not replace them with another visible technical checklist. |
| Automatic preparation becomes a notification | Remove the section, accordion, operation counts and KPI tile. Emit one compact completion notification after import or a successful correction. |
| Export review becomes navigation buttons | Sticky top navigation contains Download DAT and Download PDF; draft PDF remains accessible through the PDF control when blocked. No separate Downloads tab or lower export card. |
| Hide official validation evidence | Remove the evidence panel, upload/view controls and related navigation links from this interface. |
| Hide clear this review | Remove the visible clear/reset control. A deliberate new import replaces the workspace through the existing replacement-confirmation flow. |
| Hide Rule tab | Remove any Rule tab AND the Rule column shown in the preparation screenshot. |
| Remove reason/supporting source input | Remove it from employer, employee and shared-answer edit flows. Saving must succeed without it; update request validation and backend requirements accordingly. |
| Remove Download review record (JSON) | Remove the action and associated promotional/helper copy from all menus and screens. |

Hidden UI is not permission to delete original values or correction history. Continue recording before/after values and timestamps automatically where the app already supports this. Do not fabricate a human reason or supporting evidence. Existing legacy reasons may remain stored but are not required for new edits.

Preserve actual export blockers: missing identifiers, invalid data and unsupported cases must still prevent DAT/final PDF creation. Removing optional questionnaires must not convert unknown answers to Yes or change financial classifications. If a genuinely required decision arises, show one concrete question in the affected record, with an explanation of its consequence; do not resurrect a general optional-review panel.

## 4. Visual direction

### Palette

These are proposed implementation tokens inspired by the supplied cover, not official brand specifications.

```css
:root {
  --canvas: #F6F3EE;
  --surface: #FFFFFF;
  --surface-soft: #EEE9E1;
  --espresso: #201A16;
  --espresso-raised: #2D2520;
  --text: #29231F;
  --text-muted: #71665D;
  --border: #E3DDD4;
  --accent: #B9472B;
  --accent-hover: #983B25;
  --accent-tint: #FBEDE6;
  --warning-text: #87500D;
  --warning-tint: #FFF3DD;
  --success-text: #326448;
  --success-tint: #ECF4ED;
  --danger-text: #A92D2D;
  --danger-tint: #FCEEEE;
  --focus: #A63F26;
  --radius-card: 16px;
  --radius-control: 8px;
  --shadow-card: 0 2px 8px rgb(32 26 22 / 3%);
}
```

Use warm cream for the page, white for working cards, espresso for the nav and one summary card, and burnt orange for primary action/highlight. Green is a semantic success color only, replacing the current green-led visual identity. No gradients, glass blur, illustrated heroes, decorative charts or excessive pill badges. Thin dividers and restrained tonal blocks provide structure.

Keep the product name `Alphalist`; use a small orange A monogram if retaining the existing mark. Do not imply official BIR approval, and do not replace the product name with BIRa or invent an endorsement. The palette can match BIRa without copying its full logo.

### Typography and density

- Use the existing sans-serif if legible; otherwise Inter with system fallbacks.
- Main title 26–28px/34px, card titles 16–18px/24px, body and table 14px/20px, metadata 12–13px/18px.
- Large numbers 28–32px with tabular numerals; monetary table cells right aligned with two decimals.
- Avoid all-caps company names except where legally required in outputs. Display `Kalamansi Trading Corporation`; preserve the stored registered value.
- Card padding 20–24px; grid gap 16px; table rows approximately 52–56px. Interactive targets at least 40px desktop and 44px touch.
- Card borders 1px. Use spacing and hierarchy instead of a large shadow on every box.

## 5. Desktop information architecture

Reference viewport: 1440 × 1000, with the core workspace useful at 1440 × 900. Maximum content width 1280px; centered with 24–32px side padding. No permanent sidebar for this small workflow.

### Sticky top navigation, 64px tall

Left: Alphalist monogram and name. Center/left: `Overview` and `Employees` anchors. Right: `Import workbook`, outlined `Download PDF` menu, and primary `Download DAT`.

Overview returns to company heading and correction cards. Employees scrolls to and focuses the employee region. Avoid four page tabs that merely duplicate anchors to long content.

Exports always operate on the current saved review. During an unsaved edit, disable generation and explain `Save your changes before downloading.` A nav status updates after save/recheck; downloads cannot use stale data. Anchor offsets account for the sticky header.

### Compact context heading

One eyebrow: `ANNUAL ALPHALIST / 2025`. Main heading: company name. Below it, a subdued filename with ellipsis and a full-name accessible tooltip. A small chip identifies `Form 1604-C`. Do not add a marketing slogan or a second progress checklist.

### Bento row 1

Use a 12-column grid:

- **4 columns: summary card**, espresso background, warm white text. Heading `Annual summary`. Show `11 Employees` prominently, then annual tax due `₱423,857.50` and present taxable compensation `₱4,100,331.50` as clearly labeled figures. Small link `View totals` opens reconciliation details. No invented chart or completion percentage.
- **8 columns: Needs attention card**, white with a subtle orange accent. Heading `3 fields to complete`; use the actual blocking-field count. Three compact rows: Employer TIN → Add; Employer branch → Add; Liza Garcia · TIN → Fix. Each row has one sentence at most and targets the exact field.

Count missing employer TIN and employer branch as two fields even if they share one editor. Do not report three problematic employees; only one employee has a missing TIN in this example.

When there are no blockers, replace the contents of the attention card with a compact `Ready to export` state and a brief explanation, or reduce its height and promote the table. This describes the app's checks, never `BIR approved` or `Filed`.

### Bento row 2

- **8 columns: Employees card.** Search, filter, table and pagination. This is the dominant white working surface.
- **4 columns: Employer details card.** Company name and reporting year shown read-only by default; TIN and branch shown as required editable inputs when missing. Compact `Save details` action. If complete, show values with a single Edit button instead of permanent inputs.

Do not mirror the entire attention list inside the employer card. The attention card is navigation and priority; the employer card is the actual form.

The first viewport should show all three blocking issues, the financial summary, employer inputs and at least five employee rows. Remaining records can continue below or paginate. Compact does not mean reducing text until unreadable.

## 6. Import and loading states

Use the same shell before import. Replace the large landing hero with `Create your annual alphalist` and one short subtitle: `Import your workbook to review employees and download your files.`

Show a centered upload card, maximum 640px wide, with a keyboard-accessible drop zone and Select workbook button. Keep the existing accepted XLSX format and 10 MB limit unless the backend differs. Display selected filename, size and Remove selection before import. Do not expose the internal 46-column contract except in a meaningful file-format error.

If a review is already available, show `Continue review` as a secondary action. Importing a different workbook must preserve the current review until the new file is parsed successfully. Use a concise replacement confirmation only when needed to avoid losing saved review context; the removed clear-review button must not reappear under another label.

During parsing show `Preparing your workbook…`, disable duplicate submissions and provide an accessible loading status. On failure, stay in the import state with filename and a clear corrective message. Do not fake a percentage if progress is indeterminate.

## 7. Notifications replace automatic preparation

- After import: `Workbook prepared. 11 employees imported.`
- After a successful correction: `Changes saved. 2 fields left to complete.`
- At zero blockers: `Changes saved. Your files are ready to export.`
- On error: `We couldn't save your changes. Try again.` plus field-specific error where applicable.

Use one toast, top-right below the nav, maximum 380px wide, with a close button. Success messages may disappear after 6 seconds, pause on hover/focus and announce through a polite live region. Errors requiring action remain visible inline; essential errors must never exist only in a temporary toast.

Do not render a preparation section, Rules button, operation counts or preparation notification history panel. Deterministic transformations still run through the existing service; their internal logs are not the product's primary interface. Toast copy must not claim changes were made if the process only validated existing values.

## 8. Employee table and record editing

### Table

Toolbar: `Employees` and count, search by name/employee ID/TIN, `All employees` / `Needs attention` filter. Display the filter's match count. Use 10 rows per page initially; pagination must make all 11 records available. Avoid a tiny scroll box within a long scrolling page.

Columns: Employee (name with smaller ID), TIN, Present taxable, Annual tax due, Status/action. Use an explicit Open/Edit control, not a clickable row without keyboard behavior. Missing TIN displays `Missing TIN`, not an empty cell or zero. Status is `Needs attention` or `No issues found`, not `Approved`.

Default alphabetical order uses the existing supported behavior. A correction deep link or Needs attention filter focuses Liza directly without silently altering default ordering. Do not truncate numeric values; allow horizontal table scrolling at smaller widths. Do not wrap a TIN mid-number.

Demo rows should preserve the actual figures from the screenshots, for example Liza 128,250.00 / 0.00, Maria 449,812.50 / 32,462.50, and Carlo 316,800.00 / 57,260.00. Present taxable and annual tax due can have different employer scope; keep the labels explicit.

### Employee drawer

Open an approximately 520px right-side drawer on desktop, full-screen on mobile. Preserve employee deep links if supported. Header: employee name, ID and Close. A small status line replaces the current large 'No source fields need correction' card.

For Liza, begin with the required TIN input and branch control, concise formatting hint and inline validation. Include `Other details` accordion groups: Identity & employment, Present compensation, Tax & withholding, Previous employer. Open the group containing the selected field. Existing legitimate fields remain reachable.

Remove optional-review notes and all reason/supporting-source inputs. Footer: Cancel and Save changes. Save runs checks, updates counts/totals/table/download availability together and emits one toast. Errors keep the drawer open and focus the first failing field. Show required marks and labels; do not use placeholders as labels.

Cancel discards only unsaved edits. Closing a dirty drawer should offer Keep editing / Discard changes. Successful saves may close the drawer for a simple correction; retain it if unresolved field errors remain. Restore focus to the initiating control.

## 9. Exports in navigation

| Saved review state | DAT control | PDF control | Nearby explanation |
| --- | --- | --- | --- |
| No workbook | Disabled | Disabled | Import a workbook to begin |
| Parsing or rechecking | Disabled/loading | Disabled/loading | Preparing workbook or Checking changes |
| Required issues remain | Disabled | Menu: Draft PDF enabled; Final PDF disabled | `Complete 3 fields to enable final downloads` in attention card; accessible button description |
| No blocking issues | Enabled: Download DAT | Menu: Final PDF enabled; Draft PDF secondary if useful | Ready to export |
| Unsaved form edits | Disabled | Disabled | Save changes before downloading |
| Generation failed | Retry available after error | Retry available after error | Concise error naming the failed output |

Disabled controls need a visible/accessible explanation, not a hover-only tooltip. Keep the nav layout stable across states. DAT primary uses burnt orange only when enabled; blocked state is visibly muted. PDF is a secondary outline control. Do not label a draft as a final PDF.

Remove the bottom export card, Downloads anchor, JSON download and evidence panel. Do not add an alternative evidence drawer. Hiding evidence never grants validation or filing status. If the underlying product generates candidates pending official validation, retain that meaning in accessible download text or a short export-menu footer, e.g. `For validation in the BIR application.` Do not repeat it throughout the dashboard.

## 10. Totals, changes and technical settings

`View totals` opens a compact dialog with Original / Current columns and changes highlighted only when nonzero. Preserve six observed measures: present non-taxable, present taxable, present final withholding, previous withholding, annual tax due, present Jan–Nov withholding. Label scope clearly and format currency consistently.

Move correction history into a `Changes` disclosure within the totals dialog or employee record; it is not a dashboard card. Show field, before → after and timestamp. Do not say every change has a reason after removing that input.

Hide DAT encoding controls behind an Advanced options disclosure in employer editing only if a user still genuinely needs to change the existing setting. Keep the tested default and do not silently alter byte encoding as part of a color/layout redesign. If no supported choice is meaningful to the user, keep it in configuration and show only an actionable compatibility error when needed.

Remove fixture filenames, source-cell IDs, hashes, rule citations, operation counters, evidence limits and technical profile labels from default product copy. Source-cell details may appear on demand for a real correction; they should not replace plain labels.

## 11. Responsive and accessible behavior

- At 1024px: retain a two-column layout if table minimum widths permit; compact the nav without truncating buttons into ambiguity.
- Below 900px: stack attention, employer details, summary and employee table in task order. In CSS, maintain coherent keyboard/DOM order; do not create a confusing visual reorder.
- Below 640px: one column, 16px page padding, full-screen editing drawer. Wrap nav into two rows with direct PDF/DAT buttons in the sticky action row; collapse Overview/Employees links if necessary. No horizontal page overflow.
- Table may scroll horizontally within its labeled region; offer name/TIN/status as the essential visible columns. Keep full financial details available in the employee drawer.
- WCAG AA text contrast targets: 4.5:1 normal text, 3:1 large text; verify actual token combinations before implementation sign-off. Do not use orange alone to signal errors or green alone for success.
- Keyboard access for upload, menu, table actions, filters, dialogs and forms. Visible focus rings; proper menu/dialog semantics, focus trapping and focus return; Escape closes safe dialogs.
- Money uses tabular numerals. State labels and icons accompany colors. Support reduced motion; transitions approximately 120–180ms without layout jumps. Check 200% zoom.

## 12. Suggested component migration

Map these conceptual components to the actual codebase:

```text
ReviewShell
  TopNavigation
    ImportAction
    PdfDownloadMenu
    DatDownloadButton
  ImportWorkspace | ReviewWorkspace
    FilingHeading
    SummaryCard
    AttentionCard
    EmployeeTable
    EmployerDetailsCard
  EmployeeDrawer
  TotalsDialog
  NotificationToast
```

Create one derived review-state selector containing blocking fields, employee issues, financial totals, pending-save state and export availability. Components consume the same state so nav buttons, counts and issue rows agree. Use existing server validation and generation endpoints. Do not create independent UI-only financial calculations.

When removing `reason`, update frontend schema, request construction, backend validation, persistence defaults and existing tests together. Preserve backward compatibility for old records carrying reasons. Do not fill the removed field with a pretend user statement. Remove JSON download from all user-facing entry points; removing a button is not a reason to delete data needed internally.

Recommended implementation sequence: establish tokens and shell; remove requested surfaces; relocate downloads; consolidate cards; add employee drawer/search/filter; simplify form contracts; implement notifications; verify responsive and export-state behavior. Preserve legitimate existing functionality while moving it into the new hierarchy.

## 13. Acceptance checklist

- [ ] All eight requested removals/relocations in section 3 are implemented; none reappears inside a renamed default panel.
- [ ] At 1440 × 900, company/year, three issue actions, totals summary, employer fields and first five employee rows are usable without a long introductory scroll.
- [ ] No marketing hero, permanent sidebar, checklist duplication or decorative chart displaces primary work.
- [ ] New palette follows the supplied cover: espresso, warm neutrals and orange; green is semantic only.
- [ ] The demonstrated initial state has 11 employees and 3 missing fields: employer TIN, employer branch and Liza's TIN.
- [ ] Clicking each issue focuses the correct input; saving a value updates the count accurately without counting fields as employees.
- [ ] Saving works without a reason/supporting-source value across frontend and backend.
- [ ] Automatic preparation appears as one notification, never as a section or Rule table.
- [ ] Required blockers still disable DAT and final PDF; draft PDF remains accessible and clearly labeled.
- [ ] Removing optional review does not change unknown answers, calculations, classifications or export eligibility.
- [ ] All employees remain reachable through search, filters and pagination; no one is omitted to simplify the table.
- [ ] Source/current financial totals remain reconcilable; no mockup sample numbers are hardcoded in production.
- [ ] Original data and automatic before/after change records remain intact; no fake reasons or validation evidence are created.
- [ ] No visible official-evidence panel, Clear review control, Rule column/tab or JSON download exists.
- [ ] Failed imports/saves preserve recoverable data; a failed recheck cannot leave downloads enabled against stale records.
- [ ] Keyboard, focus, contrast, zoom, mobile layout, loading and empty/error states pass review.
- [ ] Existing DAT fixture and PDF financial checks still pass after the UI refactor; the redesign does not alter serialization or report math.

## 14. Image mockup brief

Create one high-fidelity, image-only desktop UI concept, front-on with no device frame. Show the imported Kalamansi 2025 workspace in its realistic 3-fields-missing state. Use the design tokens above, espresso sticky nav, orange A mark, direct PDF/DAT controls, compact heading, asymmetric bento layout, dark summary card, actionable white attention card, employee table and employer form. An ephemeral preparation toast may appear near the lower-right edge without obscuring inputs or table actions.

The image illustrates the dashboard state, not a functioning site. It must not show the hidden technical sections. The complete behavior for import, editing, errors, ready state and mobile is defined in this document.
