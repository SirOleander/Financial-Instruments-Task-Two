# Classification lens — accuracy, AUC, confusion matrix

The task is a regression (forward Sharpe). Slide 24 also asks for classification metrics, so we add a classification **lens alongside** the regression — it does not replace it.

## Labelling and leak control

- **Label:** top-third vs bottom-third of realized `future_63d_sharpe`; the middle third is dropped. This matches the strategy (long top-10 / short bottom-10) — the question is whether the model can separate a period's winners from its losers.

- **The tercile cutoffs are fit on TRAIN ROWS ONLY**: inside each CV fold the 33rd/67th percentiles are computed from that fold's *training* rows and then applied to both the training and the validation rows; for the one-shot test evaluation the cutoffs come from the full train+val pool. **Test outcomes never inform any cutoff**, and no cutoff is ever fit on the pooled dataset.

- Same time split (2025-03-31), same TimeSeriesSplit(5, gap=21), same per-fold winsorize → impute → scale pipeline. Selection metric = ROC-AUC.

- Consequence of a train-fitted cutoff: the test regime had higher Sharpes, so the test set is **58.7% one class** (majority baseline accuracy = 0.587). **AUC and balanced accuracy are therefore the metrics to read**; raw accuracy must be compared against that baseline.

- A balanced **within-period** variant (ranked inside each report period, separately within train and within test so no period's cross-section straddles the split) is reported as robustness.

## Test-set metrics — primary (cutoffs fit on train only)

| model | cv_auc | test_auc | test_accuracy | test_balanced_accuracy | test_precision | test_recall | test_f1 |
|---|---|---|---|---|---|---|---|
| LogisticRegression | +0.4808 | +0.5225 | +0.5000 | +0.5184 | +0.6098 | +0.4132 | +0.4926 |
| RandomForest | +0.4713 | +0.5256 | +0.4951 | +0.4950 | +0.5825 | +0.4959 | +0.5357 |
| XGBoost | +0.4738 | +0.5206 | +0.5291 | +0.5134 | +0.5984 | +0.6033 | +0.6008 |
| SVM | +0.5340 | +0.5287 | +0.4854 | +0.4797 | +0.5688 | +0.5124 | +0.5391 |

Majority-class baseline accuracy = **0.587**, chance AUC = **0.500**. n_test = 206.

## Test-set metrics — robustness (balanced within-period tercile)

| model | cv_auc | test_auc | test_accuracy | test_balanced_accuracy | test_f1 |
|---|---|---|---|---|---|
| LogisticRegression | +0.4636 | +0.5362 | +0.5421 | +0.5421 | +0.5246 |
| RandomForest | +0.4839 | +0.4872 | +0.4895 | +0.4895 | +0.4520 |
| XGBoost | +0.4988 | +0.4942 | +0.5105 | +0.5105 | +0.4918 |
| SVM | +0.5102 | +0.4522 | +0.4789 | +0.4789 | +0.5171 |

Balanced by construction; baseline accuracy ≈ 0.5, chance AUC = 0.500. n_test = 190.

## Confusion matrices & ROC

`fig_confusion_matrices.png`, `fig_roc_curves.png`.

## Interpretation

- **AUC is ~0.5 for every model.** Primary scheme test AUC 0.521–0.529; robustness scheme 0.452–0.536 (chance = 0.500). The classifiers cannot rank future winners above future losers better than a coin flip.
- **CV and test AUC disagree in sign.** Cross-validated AUC is mostly *below* chance (0.471–0.534) while test AUC is marginally above it — the hallmark of noise, not a stable edge. No model is consistently above 0.5 across both labelling schemes.
- **Accuracy is not evidence of skill here.** Under the train-fitted cutoff the test set is 58.7% one class, so a model that always predicts the majority scores that accuracy without any information. Balanced accuracy (~0.5) and AUC (~0.5) strip that artefact out.
- The **confusion matrices** show the same thing structurally: predictions are spread across both classes with no concentration on the diagonal.
- The **balanced within-period variant reproduces the verdict** on 50/50 classes, so the result is not an artefact of the class imbalance introduced by the train-fitted cutoff.

- **Verdict:** *a classification framing gives the same answer as the regression — the models cannot separate future winners from losers better than chance.* This is a consistency check that CONFIRMS the near-null regression result, reported straight.