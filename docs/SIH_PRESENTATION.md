# SIH26031 - presentation notes

**One-liner:** An AI-powered onion quality inspection system that uses computer vision to detect defects, measure size,
grade lots against configurable procurement standards, and issue a transparent, verifiable digital quality report.

**Problem -> answer**
Subjective manual inspection -> standardised visual inspection -> objective measurements -> rules-based Grade A / URS ->
instant PDF report with QR verification -> fewer disputes.

**Demo script (3 min)**
1. Sign in as operator, click *Start new inspection*, pick a farmer, press *Use demo tray image*, *Run inspection*.
2. Show the annotated image (diameters in mm) and the composition band.
3. Open *Why this result*, then *Standards*: change a Grade A limit, re-run, show the decision change and the version stamped on the report.
4. Download the PDF, scan the QR / open the verify page to show the integrity check.
5. Sign in as the farmer and show that they only see their own lots.

**Module map:** login/roles, batch registration, AI inspection, defect detection, size measurement, rules engine, report, history/transparency (see ARCHITECTURE.md).

**Honest limits to state:** baseline vision is heuristic; accuracy targets and dataset plan are in `ml/README.md`; thresholds in the default standard are placeholders to be replaced with the official specification.
