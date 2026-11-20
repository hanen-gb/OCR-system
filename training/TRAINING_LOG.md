# Training log

Kaggle limits a GPU session to 12 hours, while one epoch of GLM-OCR on a T4 takes about 2 h 20 min (≈ 2 h 10 min of
training + 9.5 min of evaluation). Training was therefore split into successive sessions: each session saves a
resumable checkpoint after every epoch, and the next session restores the model, optimiser, scheduler and callback
state (best loss, patience counter) before continuing.

The evaluation losses below were read from the `trainer_state.json` file saved with each checkpoint.

## GLM-OCR — invoices

Configuration: LoRA r = 4, α = 8, dropout 0.2, effective batch 8, cosine schedule, weight decay 0.05, NEFTune α = 5,
early stopping patience 25 epochs. Notebook of the last session: [`finetune_invoices.ipynb`](finetune_invoices.ipynb).

| Session | Epochs | Learning rate | Evaluation loss (per epoch) | Note |
|---|---|---|---|---|
| 1 | 1–3 | 5e-6 | 0.0439 · 0.0376 · 0.0514 | Warm-up set as a ratio (10 %) — too long |
| 2 | 4 | 5e-6 | 0.0328 | Warm-up changed to 100 steps |
| 3 | 5–9 | 5e-6 | 0.0298 · 0.0266 · 0.0238 · 0.0214 · 0.0214 | |
| 4 | 10 | 5e-6 | 0.0152 | |
| 5 | 11–15 | 5e-6 | 0.0152 · 0.0141 · 0.0134 · 0.0132 · 0.0128 | |
| 6 | 16–19 | 5e-6 | 0.0125 · 0.0121 · 0.0124 · 0.0122 | Plateau |
| 7 | 20–24 | **2e-6** | 0.0123 · 0.0126 · 0.0123 · 0.0113 · 0.0113 | Learning rate lowered |
| 8 | 25 | 2e-6 | 0.0113 | |
| 9 | 26–34 | 2e-6 | **0.0109** · 0.0110 · 0.0116 · 0.0116 · 0.0114 · 0.0114 · 0.0110 · 0.0110 · 0.0109 | Best checkpoint at epoch 26 |
| 10 | 35–39 | 2e-6 | 0.0111 · 0.0112 · 0.0113 · 0.0113 · 0.0113 | No further improvement — training stopped |

**Selected checkpoint:** epoch 26, evaluation loss **0.0109** (−75 % from 0.0439 after the first epoch).
Total: 39 epochs, ≈ 93 GPU hours on a Tesla T4.

> Epoch numbers inside the notebooks are counted per session (for example "epoch 13" of session 9 is global epoch 26).

## GLM-OCR — bills of exchange

Same LoRA configuration, early stopping patience 20 epochs, learning rate lowered from 5e-6 to 2e-6 in the later
sessions. Notebook of the last session: [`finetune_bills_of_exchange.ipynb`](finetune_bills_of_exchange.ipynb).

| | Value |
|---|---|
| Training / test documents | 4,258 / 1,065 |
| Best evaluation loss | **0.0352** |
| Evaluation loss in the last session | 0.0365 (no improvement — early stopping close) |

## MobileNetV2 — document classifier

Trained in a single session (CPU-friendly model): best checkpoint at epoch 16 (validation loss 0.0048),
early stopping at epoch 26. Curves and logs are in [`train_classifier.ipynb`](train_classifier.ipynb).
