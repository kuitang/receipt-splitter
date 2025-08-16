# Design System Documentation

## Overview
This document outlines the design principles, patterns, and current state of the Receipt Splitter application's user interface. The design emphasizes consistency, clarity, and user-friendliness across all pages.

## Design Principles

### 1. Visual Consistency
- **Unified Typography**: Consistent font sizes and weights across similar elements
- **Color Harmony**: Standardized color palette for text, backgrounds, and interactive elements
- **Spacing Rhythm**: Predictable spacing patterns using Tailwind's spacing scale

### 2. Functional Clarity
- **Clear Visual Hierarchy**: Important information (restaurant name, totals) displayed prominently
- **Intuitive Interactions**: Buttons and inputs behave predictably with clear hover states
- **Mathematical Relationships**: Visual indicators (×, =) show relationships between fields

### 3. User Experience
- **Progressive Disclosure**: Information revealed as needed (processing states, error messages)
- **Responsive Feedback**: Immediate visual feedback for user actions
- **Accessibility**: Focus states, readable contrast ratios, semantic HTML

## Current Design Patterns

### Typography Scale
```
Page Title:         text-3xl font-bold text-gray-900
Section Header:     text-2xl font-semibold
Subsection Header:  text-xl font-semibold text-gray-700
Body Text:          text-base text-gray-700
Secondary Text:     text-sm text-gray-600
Tertiary Text:      text-xs text-gray-500
```

### Container System
```
Page Container:     max-w-4xl mx-auto py-8
Card:               bg-white rounded-lg shadow-lg p-6
Compact Card:       bg-white rounded-lg shadow-lg p-4
```

### Button Styles
```
Primary:            bg-blue-600 hover:bg-blue-700 text-white font-medium
Success:            bg-green-600 hover:bg-green-700 text-white font-medium
Secondary:          bg-gray-200 hover:bg-gray-300 text-gray-800 font-medium
Danger (icon):      text-red-600 hover:text-red-800
```

### Form Inputs
```
Standard Input:     border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500
Number Input:       text-right tabular-nums (for proper number alignment)
Readonly Input:     bg-gray-50 (subtle background difference)
```

## Page-Specific Implementations

### View Page (/r)
- **Header Card**: Restaurant name prominently displayed with metadata
- **Two-Column Layout**: Participants on left, totals on right
- **Item Cards**: Clear separation with border, rounded corners
- **Sticky Footer**: Total and confirm button always visible

### Edit Page (/edit)
- **Editable Header**: Restaurant name as inline-editable title
- **Processing State**: Loading modal with spinner and friendly messaging
- **Item Row Layout**: 
  - Name field (flexible width)
  - Quantity (narrow, w-16)
  - × symbol
  - Price field
  - = symbol
  - Total field (readonly, subtle background)
  - Delete button (outside card)
- **Tax/Tip Display**: Inline formula showing per-item calculations

## Recent Improvements

### Consistency Enhancements
1. **Unified Headers**: Both /r and /edit use same typography scale
2. **Standardized Spacing**: Consistent use of space-y-6, space-y-3, space-y-1
3. **Button Normalization**: All buttons use font-medium instead of mixed weights

### Visual Refinements
1. **Delete Button Positioning**: Moved outside item cards for clearer separation
2. **Mathematical Operators**: Added × and = between fields for clarity
3. **Simplified Totals**: Removed redundant calculation displays

### UX Improvements
1. **Inline Restaurant Name Editing**: Moved to page header for prominence
2. **Cleaner Receipt Details**: Removed unnecessary section headers
3. **Optimized Field Widths**: Quantity field narrowed to appropriate size

## Areas for Improvement (DRY Principle)

### Current Duplication Issues
1. **Tailwind Classes**: Repeated class combinations could be extracted into components
2. **JavaScript Functions**: Similar event handling patterns across multiple files
3. **Template Structures**: Item display logic duplicated between view and edit templates

### Recommended DRY Improvements
1. **Create Reusable Django Template Partials**:
   - `item_display.html` for consistent item rendering
   - `totals_display.html` for receipt totals section
   - `button_styles.html` for standardized button components

2. **Extract Tailwind Component Classes**:
   ```css
   @layer components {
     .btn-primary { @apply bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 font-medium transition-colors; }
     .input-standard { @apply px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500; }
     .card { @apply bg-white rounded-lg shadow-lg p-6; }
   }
   ```

3. **Consolidate JavaScript Utilities**:
   - Create shared validation functions
   - Extract common event handlers
   - Unify AJAX request patterns

4. **Standardize State Management**:
   - Consistent error handling patterns
   - Unified loading states
   - Shared form validation logic

## Color Palette
```
Primary:        blue-600/700
Success:        green-600/700
Warning:        orange-600
Danger:         red-600/700
Text Primary:   gray-900
Text Secondary: gray-700
Text Tertiary:  gray-600
Text Muted:     gray-500
Background:     gray-50
Card:           white
Border:         gray-300
```

## Responsive Design
- Mobile-first approach with md: breakpoints for tablets/desktop
- Flexible layouts using flexbox and CSS grid
- Touch-friendly tap targets (minimum 44x44px)

## Accessibility Considerations
- Focus rings on all interactive elements
- Semantic HTML structure
- ARIA labels where needed
- Sufficient color contrast ratios
- Keyboard navigation support

## Future Considerations
1. **Component Library**: Consider adopting a component system (React/Vue/Alpine)
2. **Design Tokens**: Implement CSS custom properties for theming
3. **Animation System**: Add subtle transitions for state changes
4. **Dark Mode**: Prepare color system for dark mode support
5. **Print Styles**: Optimize receipt display for printing

## Conclusion
The current design system provides a solid foundation for a consistent user experience. The main priority should be reducing duplication through better componentization while maintaining the established visual language. The focus on mathematical clarity and intuitive interactions has created a user-friendly interface for splitting receipts.