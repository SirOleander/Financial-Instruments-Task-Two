# Classification lens — accuracy, AUC, confusion matrix

The task is a regression (forward Sharpe). Slide 24 also asks for classification metrics, so we add a classification **lens alongside** the regression — it does not replace it.

## Labelling and leak control

- **Label:** top-third vs bottom-third of realized `future_63d_sharpe`; the middle third is dropped. This matches the strategy (long top-10 / short bottom-10) — the question is whether the model can separate a period's winners from its losers.

- **The tercile cutoffs are fit on TRAIN ROWS ONLY**: inside each CV fold the 33rd/67th percentiles are computed from that fold's *training* rows and then applied to both the training and the validation rows; for the one-shot test evaluation the cutoffs come from the full train+val pool. **Test outcomes never inform any cutoff**, and no cutoff is ever fit on the pooled dataset.

- Same time split (2025-03-31), same TimeSeriesSplit(5, gap=21), same per-fold winsorize → impute → scale pipeline. Selection metric = ROC-AUC.

- Consequence of a train-fitted cutoff: the test regime had higher Sharpes, so the test set is **57.9% one class** (majority baseline accuracy = 0.579). **AUC and balanced accuracy are therefore the metrics to read**; raw accuracy must be compared against that baseline.

- A balanced **within-period** variant (ranked inside each report period, separately within train and within test so no period's cross-section straddles the split) is reported as robustness.

## Test-set metrics — primary (cutoffs fit on train only)

| model | cv_auc | test_auc | test_accuracy | test_balanced_accuracy | test_precision | test_recall | test_f1 |
|---|---|---|---|---|---|---|---|
| LogisticRegression | +0.4787 | +0.5396 | +0.5198 | +0.5388 | +0.6282 | +0.4188 | +0.5026 |
| RandomForest | +0.4794 | +0.5456 | +0.5396 | +0.5398 | +0.6176 | +0.5385 | +0.5753 |
| XGBoost | +0.4820 | +0.5429 | +0.5545 | +0.5446 | +0.6174 | +0.6068 | +0.6121 |
| SVM | +0.5294 | +0.4342 | +0.5050 | +0.4713 | +0.5594 | +0.6838 | +0.6154 |

Majority-class baseline accuracy = **0.579**, chance AUC = **0.500**. n_test = 202.

## Test-set metrics — robustness (balanced within-period tercile)

| model | cv_auc | test_auc | test_accuracy | test_balanced_accuracy | test_f1 |
|---|---|---|---|---|---|
| LogisticRegression | +0.4662 | +0.5495 | +0.5372 | +0.5372 | +0.5029 |
| RandomForest | +0.4997 | +0.5162 | +0.5426 | +0.5426 | +0.5057 |
| XGBoost | +0.4990 | +0.5069 | +0.5160 | +0.5160 | +0.5081 |
| SVM | +0.4967 | +0.4339 | +0.4521 | +0.4521 | +0.5502 |

Balanced by construction; baseline accuracy ≈ 0.5, chance AUC = 0.500. n_test = 188.

## Confusion matrices & ROC

`fig_confusion_matrices.png`, `fig_roc_curves.png`.

## Interpretation

- **AUC is ~0.5 for every model.** Primary scheme test AUC 0.434–0.546; robustness scheme 0.434–0.549 (chance = 0.500). The classifiers cannot rank future winners above future losers better than a coin flip.
- **CV and test AUC disagree in sign.** Cross-validated AUC is mostly *below* chance (0.479–0.529) while test AUC is marginally above it — the hallmark of noise, not a stable edge. No model is consistently above 0.5 across both labelling schemes.
- **Accuracy is not evidence of skill here.** Under the train-fitted cutoff the test set is 57.9% one class, so a model that always predicts the majority scores that accuracy without any information. Balanced accuracy (~0.5) and AUC (~0.5) strip that artefact out.
- The **confusion matrices** show the same thing structurally: predictions are spread across both classes with no concentration on the diagonal.
- The **balanced within-period variant reproduces the verdict** on 50/50 classes, so the result is not an artefact of the class imbalance introduced by the train-fitted cutoff.

- **Verdict:** *a classification framing gives the same answer as the regression — the models cannot separate future winners from losers better than chance.* This is a consistency check that CONFIRMS the near-null regression result, reported straight.