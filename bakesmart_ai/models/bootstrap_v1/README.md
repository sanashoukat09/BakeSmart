# BakeSmart bootstrap model v1

This directory contains a locally trained, multi-task neural network initialized
from random weights. The implementation uses NumPy for matrix operations, while
the forward pass, backpropagation, Adam optimizer, early stopping, metrics, and
deterministic checkpoint format are implemented in BakeSmart's training code.

The four prediction heads are theme, cake, decoration package, and layout. Phase
6 will map those predictions to catalogue items and a coordinated scene contract
so cakes, additional baked items, tables, backdrops, and decorations can later be
displayed together in one 3D scene.

This is a **synthetic bootstrap artifact**, not a production model. Its metrics
measure how well it learned the rule-generated silver labels. They do not measure
real customer preference or professional event-design quality.

Recreate the artifacts from `bakesmart_ai`:

```powershell
python -m training.train_model --allow-synthetic-bootstrap --evaluate-locked-test
```

During architecture or hyperparameter experiments, omit
`--evaluate-locked-test`. Use that flag only for the final selected checkpoint.
