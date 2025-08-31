## Portfolio Risk

![portfolio risk](data:image/svg+xml;base64,${{ steps.viz.outputs.badge }})

**Overall:** ${{ steps.portfolio.outputs.score }} (${{ steps.portfolio.outputs.grade }}) · Δ ${{ steps.portfolio.outputs.delta }}

Trend (${{ steps.portfolio.outputs.count }} runs):  
![portfolio trend](data:image/svg+xml;base64,${{ steps.viz.outputs.spark }})

Top risky contracts:
${{ steps.portfolio.outputs.top_contracts }}

**Portfolio artifacts:** audit-portfolio
