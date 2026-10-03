# Charts (BI in the chat)

From `dooers-agents-server` **≥ 0.15**, agents can emit interactive charts that the Dooers app-web renders with Recharts. No custom UI code is required in the agent.

## API

```python
yield send.chart(
    chart_type="bar",  # bar | bar_horizontal | stacked_bar | line | area | pie | donut | scatter
    data=[
        {"month": "Jan", "revenue": 120, "costs": 80},
        {"month": "Feb", "revenue": 180, "costs": 95},
    ],
    x_key="month",
    y_keys=["revenue", "costs"],
    title="Monthly Revenue vs Costs",
    message="Optional markdown caption above the chart.",
    size="medium",  # small | medium | large
    series=[
        send.chart_series("revenue", label="Revenue"),
        send.chart_series("costs", label="Costs"),
    ],
    x_label="Month",
    y_label="USD (k)",
)
```

Each `yield send.chart(...)` is persisted as a thread event (`type: "chart"`) and shown in the Dooers chat UI.

### Sizes

| Size | Behavior |
|------|----------|
| `small` | Compact; consecutive small charts group into a 2-column grid in app-web |
| `medium` | Default card width |
| `large` | Full-width emphasis |

### Typical patterns

1. **Tool → chart** — a tool returns tabular data; the handler yields `send.chart` instead of dumping a markdown table.
2. **Analytics for owners** — when `incoming.context.user.organization_role` is `owner` or `manager`, expose BI tools that emit charts; members get text-only workflows.
3. **Smoke test** — in this starter, send `/test-chart-all` (or `/test-chart-bar`, …) in chat. Implementation: `src/modules/helpers/chart_demo.py`.

## Related

- SDK contract summary: [02-sdk-contract.md](02-sdk-contract.md)
- Reasoning blocks (collapsible): `yield send.reasoning("…")` (≥ 0.14)
- Org-level usage dashboards (turns/tokens) are separate from chat BI charts — see [10-observability.md](10-observability.md)
