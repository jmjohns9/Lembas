Overfitting happens when a model learns the noise and quirks of its training data, not just the underlying pattern. Training error keeps falling while validation error stops improving or starts rising. Usually the cause is too much model capacity for too little data: the model has enough freedom to memorize individual examples.

To prevent it, try these in rough order of payoff:
- **More or augmented data.** Use random crops and flips for images, or back-translation for text.
- **Simpler model.** Use fewer layers, shallower trees or fewer features.
- **Regularization.** Add L2 weight decay, L1, dropout (0.1 to 0.5), or a `max_depth`/`min_samples_leaf` limit for trees.
- **Early stopping.** Stop training when validation loss hasn't improved for N epochs.
- **Cross-validation.** Use k-fold to get an honest estimate of how well the model generalizes.

The most common trap is leakage. If you tune hyperparameters against the test set, or fit preprocessing such as scalers on the full dataset before splitting, the model overfits in ways your metrics can't show. Keep a held-out test set that you use only once, at the very end.