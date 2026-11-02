"""Product layer for the two-stage evaluation lifecycle (M8).

One evaluation model serves both the preloaded M7 experiment (a sanitized, versioned dataset derived from the real run) and evaluations launched
from the web product: `projection.project` turns Stage B run directories plus the lifecycle store into the PUBLIC evaluation document, and the
dataset builder serialises exactly that document. Private oracle data is read server-side only and never leaves this package except as counts."""
