---
name: chart-visualization
description: |
  Generate professional charts and visualizations from financial data.
  Intelligently selects the most suitable chart type from 26 options including
  pie charts (asset allocation), line charts (trends), bar charts (comparisons),
  radar charts (financial health), and more.

trigger_phrases:
  - /chart
  - 生成图表
  - 画个图
  - 可视化
  - 图表展示

allowed-tools:
  - get_family_overview
  - get_assets
  - get_liabilities
  - write_file
  - read_file
  - str_replace
  - present_files

thinking: false
---

# Chart Visualization Skill

This skill provides a comprehensive workflow for transforming data into visual charts. It handles chart selection, parameter extraction, and image generation.

## Node.js Compatibility

This skill requires Node.js >= 18.0.0. The generation script uses native `fetch` (available in Node 18+).

## Workflow

To visualize data, follow these steps:

### 1. Intelligent Chart Selection

Analyze the user's data features to determine the most appropriate chart type. Use the following guidelines (and consult `references/` for detailed specs):

#### Financial Chart Selection Guide

| Scenario | Recommended Chart | Tool Name |
|----------|------------------|-----------|
| Asset allocation / portfolio breakdown | Pie chart | `generate_pie_chart` |
| Net worth trend over time | Line chart or area chart | `generate_line_chart` / `generate_area_chart` |
| Category spending comparison | Bar chart or column chart | `generate_bar_chart` / `generate_column_chart` |
| Financial health multi-dimensional | Radar chart | `generate_radar_chart` |
| Income vs expense flow | Sankey diagram | `generate_sankey_chart` |
| Spending distribution (hierarchical) | Treemap | `generate_treemap_chart` |
| Monthly savings progress | Liquid chart | `generate_liquid_chart` |
| Budget utilization | Funnel chart | `generate_funnel_chart` |
| Investment return distribution | Histogram or boxplot | `generate_histogram_chart` / `generate_boxplot_chart` |
| Correlation (income vs spending) | Scatter chart | `generate_scatter_chart` |
| Two different scales (e.g. amount + rate) | Dual axes | `generate_dual_axes_chart` |

#### General Chart Selection Guide

- **Time Series**: Use `generate_line_chart` (trends) or `generate_area_chart` (accumulated trends). Use `generate_dual_axes_chart` for two different scales.
- **Comparisons**: Use `generate_bar_chart` (categorical) or `generate_column_chart`. Use `generate_histogram_chart` for frequency distributions.
- **Part-to-Whole**: Use `generate_pie_chart` or `generate_treemap_chart` (hierarchical).
- **Relationships & Flow**: Use `generate_scatter_chart` (correlation), `generate_sankey_chart` (flow), or `generate_venn_chart` (overlap).
- **Maps**: Use `generate_district_map` (regions), `generate_pin_map` (points), or `generate_path_map` (routes).
- **Hierarchies & Trees**: Use `generate_organization_chart` or `generate_mind_map`.
- **Specialized**:
    - `generate_radar_chart`: Multi-dimensional comparison (great for financial health scores).
    - `generate_funnel_chart`: Process stages (budget utilization pipeline).
    - `generate_liquid_chart`: Percentage/Progress (savings goal completion).
    - `generate_word_cloud_chart`: Text frequency.
    - `generate_boxplot_chart` or `generate_violin_chart`: Statistical distribution.
    - `generate_network_graph`: Complex node-edge relationships.
    - `generate_fishbone_diagram`: Cause-effect analysis.
    - `generate_flow_diagram`: Process flow.
    - `generate_spreadsheet`: Tabular data or pivot tables for structured data display and cross-tabulation.

### 2. Parameter Extraction

Once a chart type is selected, read the corresponding file in the `references/` directory (e.g., `references/generate_line_chart.md`) to identify the required and optional fields.
Extract the data from the user's input and map it to the expected `args` format.

### 3. Chart Generation

Invoke the `scripts/generate.js` script with a JSON payload.

**Payload Format:**
```json
{
  "tool": "generate_chart_type_name",
  "args": {
    "data": [...],
    "title": "...",
    "theme": "...",
    "style": { ... }
  }
}
```

**Execution Command:**
```bash
node scripts/generate.js '<payload_json>'
```

### 4. Result Return

The script will output the URL of the generated chart image.
Return the following to the user:
- The image URL.
- The complete `args` (specification) used for generation.

## Financial Data Tips

### Preparing Data for Charts

When visualizing Numina financial data:

- **Currency formatting**: Use consistent currency symbols (e.g., ¥ for CNY). Format large numbers with万/亿 or K/M suffixes.
- **Date grouping**: Group transactions by month/quarter for trend charts. Use `DATE_TRUNC` patterns if pre-processing with SQL.
- **Category colors**: For pie/treemap charts, assign distinct colors to each category. Use warm colors for expenses, cool colors for income.
- **Negative values**: For bar/column charts showing income and expense, keep negative values for expenses to create waterfall-like visualizations.

### Common Financial Visualizations

**Asset Allocation Pie Chart:**
```json
{
  "tool": "generate_pie_chart",
  "args": {
    "data": [
      { "name": "房产", "value": 3000000 },
      { "name": "股票", "value": 500000 },
      { "name": "存款", "value": 200000 },
      { "name": "基金", "value": 300000 }
    ],
    "title": "家庭资产分布"
  }
}
```

**Monthly Spending Trend Line Chart:**
```json
{
  "tool": "generate_line_chart",
  "args": {
    "data": [
      { "month": "1月", "支出": 12000, "收入": 25000 },
      { "month": "2月", "支出": 9800, "收入": 25000 },
      { "month": "3月", "支出": 15200, "收入": 28000 }
    ],
    "title": "月度收支趋势"
  }
}
```

## Reference Material

Detailed specifications for each chart type are located in the `references/` directory. Consult these files to ensure the `args` passed to the script match the expected schema.

Available references:
- `generate_area_chart.md`
- `generate_bar_chart.md`
- `generate_boxplot_chart.md`
- `generate_column_chart.md`
- `generate_district_map.md`
- `generate_dual_axes_chart.md`
- `generate_fishbone_diagram.md`
- `generate_flow_diagram.md`
- `generate_funnel_chart.md`
- `generate_histogram_chart.md`
- `generate_line_chart.md`
- `generate_liquid_chart.md`
- `generate_mind_map.md`
- `generate_network_graph.md`
- `generate_organization_chart.md`
- `generate_path_map.md`
- `generate_pie_chart.md`
- `generate_pin_map.md`
- `generate_radar_chart.md`
- `generate_sankey_chart.md`
- `generate_scatter_chart.md`
- `generate_spreadsheet.md`
- `generate_treemap_chart.md`
- `generate_venn_chart.md`
- `generate_violin_chart.md`
- `generate_word_cloud_chart.md`

## Security Rules

- Only generate charts from data within the sandbox workspace — never access external data sources
- Do not modify the `scripts/generate.js` or `references/` files
- Validate that user-provided data is well-formed before passing to the generation script
- Chart titles and labels should not contain executable content or HTML injection
- Do not expose internal file paths in chart titles or labels

## License

This `SKILL.md` is adapted from [antvis/chart-visualization-skills](https://github.com/antvis/chart-visualization-skills).
Licensed under the [MIT License](https://github.com/antvis/chart-visualization-skills/blob/master/LICENSE).
