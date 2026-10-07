# Itinerary Form - Amount Input Optimization

## Date: 2026-10-07

## Changes Made

### 1. Imported CurrencyButton Component
- Added import for `CurrencyButton` from `@/components/common/CurrencyButton.vue`
- This component provides currency selection with country flag and symbol, matching the asset form's pattern

### 2. Repositioned Cost Input Field
**Before:** Cost amount and currency were separate fields at the bottom of the form
**After:** Combined cost field placed immediately after the end time field

**New Structure:**
```vue
<!-- Time fields section -->
<van-cell-group inset>
  <van-field v-model="form.start_time" ... />
  <van-field v-model="form.end_time" ... />
  
  <!-- Cost amount with currency selector -->
  <van-field v-model="form.cost_amount" ...>
    <template #left-icon>
      <CurrencyButton v-model="form.cost_currency" />
    </template>
  </van-field>
</van-cell-group>
```

### 3. Removed Redundant Fields
- Removed separate `cost_currency` text input field
- Currency is now selected via the `CurrencyButton` component (with flag + symbol + dropdown)
- Amount and currency are now on the same line, matching the asset form's UX pattern

### 4. Preserved Purchase Date Field
- Purchase date field remains conditionally visible when cost amount is entered
- Moved to its own cell group for better visual separation

## Benefits

1. **Consistency**: Matches the asset form's amount/currency input pattern
2. **Better UX**: Currency selection with visual flag is more intuitive than text input
3. **Improved Layout**: Cost input appears earlier in the form (after time fields), making it more discoverable
4. **Space Efficiency**: Combined currency+amount in one row saves vertical space

## Technical Details

- **Component Used**: `CurrencyButton` - displays currency flag, symbol, and opens currency picker
- **Data Binding**: `form.cost_currency` (string) and `form.cost_amount` (string) remain unchanged
- **TypeScript**: All types remain compatible - no breaking changes
- **Validation**: No changes to validation logic required

## Verification

✅ TypeScript compilation passed
✅ ESLint validation passed
✅ No breaking changes to form submission logic
