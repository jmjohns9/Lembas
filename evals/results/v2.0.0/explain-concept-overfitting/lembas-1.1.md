Overfitting is when a model learns the noise and quirks of its training data rather than the underlying pattern, so it scores well on training data but poorly on new data. You spot it when training error keeps falling while validation error stalls or rises.

The most effective ways to prevent it:

- **More data:** collect more, or augment what you have (crops, flips, paraphrases), so noise is harder to memorize.
- **Simpler model:** use fewer parameters, shallower trees or fewer features.
- **Regularization:** L1/L2 penalties, dropout or weight decay discourage overly complex fits.
- **Early stopping:** halt training when validation loss stops improving.
- **Cross-validation:** k-fold gives a more honest estimate of how the model generalizes.
- **Ensembles:** bagging methods like random forests average out individual models' overfitting.

The most common mistake is data leakage. If you tune hyperparameters on your test set, or fit preprocessing like scaling on the full dataset before splitting it, the test score will look better than the model really is. Keep a held-out test set you touch only once, at the end.