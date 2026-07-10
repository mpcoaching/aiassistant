# Skill: Design UI/UX

## Purpose
Create user interface and user experience designs that translate requirements and architecture into usable, accessible interfaces.

## Inputs
- solution-architecture
- requirements
- interface-specification

## Process

### 1. Review Requirements and Architecture
Read:
- Functional and non-functional requirements
- Solution architecture document
- Interface specification
- User personas and journeys (if available)

### 2. Understand Users
Identify:
- User personas and their goals
- User journeys and workflows
- User pain points and needs
- Accessibility requirements
- Device and platform constraints

### 3. Design Information Architecture
- Organize content and functionality
- Define navigation structure
- Create site maps
- Design information hierarchy

### 4. Create Wireframes
For each key screen/view:
- Low-fidelity wireframes showing layout
- Content placement
- Navigation elements
- Interactive components
- Responsive breakpoints

### 5. Design UI Components
For each reusable component:
- Visual design (colors, typography, spacing)
- States (default, hover, active, disabled, error)
- Variants (primary, secondary, tertiary)
- Sizes (small, medium, large)
- Accessibility attributes (ARIA labels, roles)

### 6. Define Interaction Patterns
Document how users interact with the system:
- Form validation and submission
- Error handling and display
- Loading states
- Success confirmations
- Navigation patterns
- Search and filtering
- Pagination and infinite scroll

### 7. Design User Flows
For each key task:
- Step-by-step flow diagram
- Decision points
- Error paths
- Success paths
- Alternative flows

### 8. Specify Accessibility Requirements
Ensure designs meet:
- WCAG 2.1 Level AA standards
- Keyboard navigation
- Screen reader compatibility
- Color contrast ratios
- Focus indicators
- Alternative text for images

### 9. Create Design Documentation
Create `ui-ux-design.md` with:

```markdown
# UI/UX Design

## Design Principles
[Core principles guiding the design]

## User Personas
[Key user types and their characteristics]

## Information Architecture
- Site Map
- Navigation Structure
- Content Hierarchy

## Wireframes
[Embed or link to wireframes for key screens]

## UI Components

### [Component Name]
- **Purpose**: [What it does]
- **Visual Design**: [Colors, typography, spacing]
- **States**: [Default, hover, active, disabled, error]
- **Variants**: [Primary, secondary, etc.]
- **Accessibility**: [ARIA attributes, keyboard navigation]

## Interaction Patterns
- Form Handling
- Error Display
- Loading States
- Navigation
- Search and Filtering

## User Flows

### [Task Name]
[Step-by-step flow with decision points]

## Accessibility
- WCAG Compliance: [Level]
- Keyboard Navigation: [Details]
- Screen Reader Support: [Details]
- Color Contrast: [Ratios]

## Responsive Design
- Breakpoints: [List]
- Mobile Adaptations: [Details]
- Tablet Adaptations: [Details]
- Desktop Adaptations: [Details]

## Design System
- Colors: [Palette]
- Typography: [Fonts, sizes, weights]
- Spacing: [Scale]
- Icons: [Icon set]
- Images: [Image guidelines]
```

## Output
- ui-ux-design.md
- wireframes/ (directory with wireframe images/diagrams)
- component-library.md (optional)

## Quality Criteria
- **Usability**: Designs are intuitive and easy to use
- **Accessibility**: Meets WCAG 2.1 AA standards
- **Consistency**: Follows design system and patterns
- **Responsiveness**: Works across all target devices
- **Feasibility**: Designs can be implemented with available technology
- **Traceability**: Every design element maps to a requirement