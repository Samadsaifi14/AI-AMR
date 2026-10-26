# Feature Specification: Guided first-run and stronger demo

**Feature Branch**: `005-guided-demo`

**Created**: 2026-10-26

**Status**: Implemented; verification pending

**Input**: Make the AMR app usable by people with no machine-learning background; proceed with M1 and make the demo stronger.

## User Scenarios & Testing

### User Story 1 - Complete a guided demo (Priority: P1)

A first-time user starts a synthetic practice experiment from Home, sees what the data represents, starts the analysis with one action, follows understandable progress, and reaches a result explanation that distinguishes missed resistance from false alarms. The demo always identifies synthetic results as software practice, not biological evidence.

**Why this priority**: A successful practice run teaches the core workflow before a user supplies laboratory data.

**Independent Test**: Start the demo from a clean browser session and follow it through training to the result explanation without configuring JSON or using a command line.

**Acceptance Scenarios**:

1. **Given** the Home screen, **When** a user chooses the demo, **Then** the app explains the synthetic cohort, target, and first-run runtime before starting.
2. **Given** the demo is running, **When** the runtime loads and trains, **Then** named progress stages and a usable failure/retry message are shown.
3. **Given** training completes, **When** the result appears, **Then** observed counts come from the actual run, missed resistance and false alarms are explained in plain language, and the synthetic-only limitation is prominent.

### User Story 2 - Resume work on this device (Priority: P2)

A user can return to the same browser and resume the last saved workflow state, including source, settings, selected upload and last result kept locally on the device. The user can clear the saved state at any time.

**Why this priority**: Losing the tab should not erase progress or force a beginner to reconstruct their setup.

**Independent Test**: Select a demo or upload, reload the page, resume, and confirm the source/settings are restored; clear the saved state and confirm it is gone.

**Acceptance Scenarios**:

1. **Given** saved work exists, **When** the app opens, **Then** it offers to resume and states that the saved data is in this browser.
2. **Given** a user clears saved work, **When** the page reloads, **Then** no resume prompt appears.
3. **Given** browser storage is unavailable, **When** the user works, **Then** the app continues in memory and explains that automatic resume is unavailable.

## Edge Cases

- First-time package downloads take longer than expected or fail due to network access.
- The browser blocks IndexedDB or runs out of storage.
- A saved upload exceeds available browser storage or was deleted by browser cleanup.
- A run is interrupted while training; it must not appear as completed or leave a trusted model ready.
- A demo run is blocked by model coverage; the result explanation must show the actual reason without fabricating metrics.

## Requirements

### Functional Requirements

- **FR-001**: Home MUST offer the synthetic demo and a path to use a team's data, with the requirements for each stated plainly.
- **FR-002**: The demo MUST start the existing canonical browser workflow without requiring configuration editing or command-line use.
- **FR-003**: Demo data and outputs MUST be labelled synthetic and non-biological at every point where results are presented.
- **FR-004**: Run progress MUST use named, understandable stages, including first-time engine setup.
- **FR-005**: The demo result MUST explain missed resistance and false alarms using counts produced by the run.
- **FR-006**: The app MUST save the workflow setup, selected upload and last completed result in browser-local storage and offer a resume action when that state exists.
- **FR-007**: A user MUST be able to clear locally saved work.
- **FR-008**: If local persistence is unavailable or fails, the app MUST remain usable and explain the limitation.
- **FR-009**: Closing the tab during an active run MUST trigger a browser warning where supported.
- **FR-010**: Existing scientific calculations, model gates, data provenance, and export contents MUST remain governed by canonical Python modules.

### Key Entities

- **Saved workflow**: Selected source, modeling configuration, local upload content, most recent completed result and export, progress state, and save time.
- **Demo run**: A run using the repository's synthetic fixture, with actual audit and evaluation outputs clearly separated from biological evidence.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A first-time user can start and complete the demo without editing a configuration or opening the guide.
- **SC-002**: Users can identify that demo data is synthetic before starting and that its results are not biological evidence after completion.
- **SC-003**: Users can correctly distinguish a missed resistant isolate from a false alarm using the result explanation.
- **SC-004**: A saved workflow can be resumed after a page reload and cleared by the user.
- **SC-005**: Runtime or storage failures provide an actionable next step instead of a blank or permanently disabled screen.

## Assumptions

- The existing synthetic fixture and canonical training workflow remain the demo's source of truth.
- Browser-local persistence is opt-in through clear disclosure and is user-clearable; nothing is uploaded to a server.
- M1–M4 are implemented in the browser interface. Verification remains pending; see [verification.md](verification.md). XLSX support reads the first worksheet and PDF uses the browser print dialog.
