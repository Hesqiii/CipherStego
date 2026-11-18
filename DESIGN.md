---
name: CipherStego Workspace
colors:
  surface: '#f7f9fc'
  surface-dim: '#d8dadd'
  surface-bright: '#f7f9fc'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f7'
  surface-container: '#eceef1'
  surface-container-high: '#e6e8eb'
  surface-container-highest: '#e0e3e6'
  on-surface: '#191c1e'
  on-surface-variant: '#434652'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f4'
  outline: '#737784'
  outline-variant: '#c3c6d4'
  surface-tint: '#2c5ab8'
  primary: '#0a45a4'
  on-primary: '#ffffff'
  primary-container: '#315ebd'
  on-primary-container: '#d5deff'
  inverse-primary: '#b1c5ff'
  secondary: '#555f6f'
  on-secondary: '#ffffff'
  secondary-container: '#d6e0f3'
  on-secondary-container: '#596374'
  tertiary: '#414b5f'
  on-tertiary: '#ffffff'
  tertiary-container: '#596377'
  on-tertiary-container: '#d6e0f8'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2ff'
  primary-fixed-dim: '#b1c5ff'
  on-primary-fixed: '#001947'
  on-primary-fixed-variant: '#00419f'
  secondary-fixed: '#d9e3f6'
  secondary-fixed-dim: '#bdc7da'
  on-secondary-fixed: '#121c2a'
  on-secondary-fixed-variant: '#3d4757'
  tertiary-fixed: '#d9e3fb'
  tertiary-fixed-dim: '#bdc7de'
  on-tertiary-fixed: '#111c2d'
  on-tertiary-fixed-variant: '#3d475a'
  background: '#f7f9fc'
  on-background: '#191c1e'
  surface-variant: '#e0e3e6'
typography:
  headline-xl:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Geist
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 22px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: -0.01em
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 16px
  label-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-compact: 0.75rem
  margin: 1.5rem
  margin-compact: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

The design system establishes a clinical, authoritative, and friction-free cryptographic environment. Tailored for enterprise compliance teams, academic researchers, and digital forensics professionals, it prioritizes clarity, data integrity, and deterministic feedback. 

Drawing from modern high-density utility minimalism, the interface relies on precise alignment, subdued neutral surfaces, and intentional chromatic cues. It strips away ornamental distraction in favor of systematic hierarchy, ensuring users can verify cryptographic proofs, inspect hidden steganographic layers, and assess payload metadata without perceptual fatigue.

## Colors

The palette balances utility neutral foundations with semantic precision:
- **Canvas Base**: `#F5F7FA` serves as the low-glare foundation for the workspace.
- **Surface / Card**: `#FFFFFF` provides clean elevation for working panels, data sheets, and document inspectors.
- **Borders & Dividers**: `#E4E7EC` delivers clean structural definition without visual weight.
- **Primary Brand**: `#315EBD` denotes primary actions, active state transitions, and structural focal points.
- **Text & Content**: `#182230` handles high-contrast primary typography; `#667085` provides clear secondary metadata and inactive labels.
- **Functional Semantics**:
  - Validation / Success: `#16835D` (Tamper-free signatures, valid key imports, integrity match)
  - Warning / Alert: `#D97706` (Unsigned payloads, entropy spikes, non-critical mismatches)
  - Critical / Error: `#D92D20` (Signature invalidation, corrupted carrier documents, extraction failure)

## Typography

Typography is calibrated for legibility, scannability, and high-density technical analysis:
- **Structural Headers (Geist)**: Rendered with slight negative tracking to preserve tightness in toolbars, panel headers, and modal views.
- **Interface Copy & Labels (Inter)**: Built with uniform vertical metrics to optimize scanning speeds across complex data layouts. Tabular numbers (`tnum`) must be forced across all table instances and comparative data sets.
- **Cryptographic & Verification Readouts (JetBrains Mono)**: Mandatory for SHA/MD5 checksums, nonces, key fingerprints, hex dumps, and byte-offset indices.

## Layout & Spacing

The layout is architectured as a fixed-sidebar, fluid-workspace system engineered for split-panel document inspection:
- **Grid Structure**: Employs a dense 12-column dynamic grid across main viewports, shifting to independent multi-column sub-grids inside analytical panels.
- **Breakpoints & Adaptation**:
  - **Desktop (1280px+)**: Multi-pane workflow with persistent navigation, dual-document inspection panels (carrier vs. stego output), and a collapsible telemetry drawer.
  - **Compact Desktop / Tablet (768px - 1279px)**: Inspector and payload panels switch to stacked tabs or toggleable slide-over drawers; gutters compress to `0.75rem`.
  - **Mobile (<768px)**: Strict vertical single-column execution optimized for audit confirmation and notification feeds; navigation collapses into an anchored sheet.
- **Density**: Workspaces leverage compact spacing scales (`space-sm` to `space-md`) to ensure dense tables and cryptographic trees remain within the primary viewport.

## Elevation & Depth

Visual hierarchy relies on crisp borders and restrained, functional elevation rather than decorative diffusion:
- **Surface Hierarchy**:
  - **Floor Layer**: `#F5F7FA` (Application background)
  - **Panel & Workbench Layer**: `#FFFFFF` with a 1px border of `#E4E7EC`.
  - **Floating Elements (Menus, Popovers, Tooltips)**: `#FFFFFF` surfaced with an ambient drop-shadow: `0 4px 12px -2px rgba(24, 34, 48, 0.08), 0 2px 4px -1px rgba(24, 34, 48, 0.04)`.
  - **Modals & Dialogs**: Raised with backdrop scrim (`rgba(24, 34, 48, 0.4)`) and layered shadow: `0 20px 24px -4px rgba(24, 34, 48, 0.1), 0 8px 8px -4px rgba(24, 34, 48, 0.04)`.
- **Focus Rings**: All focused interactive controls maintain a deterministic 2px outer ring in `#315EBD` with a 1px offset, guaranteeing strict accessibility conformance across tabular navigation.

## Shapes

The design system enforces a consistent 8px (`0.5rem`) baseline radius across components:
- Standard buttons, text fields, chips, and small cards use `rounded` (8px).
- Larger modal surfaces, carrier file preview containers, and inspector groupings utilize `rounded-lg` (16px) or `rounded-xl` (24px) to subtly soften wide bounds.
- Cryptographic hash badges and status markers maintain consistent internal edge radii to harmonize with adjacent monospace blocks.

## Components

### Buttons
- **Primary**: Solid `#315EBD` background, white label, 8px radius, subtle hover state (`#274C9B`), no drop shadow.
- **Secondary**: `#FFFFFF` background with `#E4E7EC` border, text `#182230`. Hover transitions to background `#F5F7FA`.
- **Danger**: White text on `#D92D20` for irreversible actions (e.g., cryptographic key destruction, payload wiping).
- **Utility / Icon Button**: 32x32px square container, 8px radius, ghost treatment with transparent background, triggering `#F5F7FA` on hover.

### Input Fields & Monospace Editors
- **Text Inputs**: Height 36px (compact) or 40px (standard), background `#FFFFFF`, border `#E4E7EC`, padding horizontal `space-md`.
- **Hash / Nonce Inputs**: Fixed width or fluid container utilizing `JetBrains Mono` (`code-md`), text color `#182230`, with an integrated 1-click "Copy" icon button nested inside the trailing slot.

### Status Chips & Badges
- **Structure**: Height 22px, padding horizontal `space-sm`, radius 6px.
- **Signed / Verified**: Background `#E8F5E9`, text `#16835D`, with a 6px solid green indicator pip.
- **Entropy Warning**: Background `#FEF3C7`, text `#D97706`.
- **Tampered / Fail**: Background `#FEE2E2`, text `#D92D20`.

### Data Cards & Inspection Panels
- Constructed on `#FFFFFF` with continuous `#E4E7EC` 1px borders.
- Header bands separate operational titles from body content using an inner border (`#E4E7EC`) and padding `space-md`.

### Document Comparison Matrix
- Split view comparison modules featuring synchronised scroll bars, structural carrier overlay layers, and integrated bit-plane inspection sliders.