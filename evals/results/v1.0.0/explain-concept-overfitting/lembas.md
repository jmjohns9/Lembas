Overfitting is when a model memorizes the noise and quirks of its training data instead of learning the general pattern, so it scores well on training data but poorly on new data. The telltale sign is training accuracy that keeps climbing while validation accuracy stalls or drops.

- Get more training data, since noise is harder to memorize across more examples.
- Use a simpler model or fewer features.
- Add regularization, such as L1/L2 penalties or dropout, to discourage extreme weights.
- Stop training early, once validation loss stops improving.
- Use k-fold cross-validation to confirm performance holds across different splits.

Judge the final model on a held-out test set it never saw during training or tuning.
