# Evaluation results

Held-out test set: **130 labeled customer messages** (92 with an expected help-center article), written separately from the classifier's training data. Reproduce with `make eval`.

## 1. Intent classification (13 intents)

| Method | Accuracy | Macro F1 |
| --- | ---: | ---: |
| Regex rules (baseline) | 53.8% | 58.5% |
| ML: TF-IDF | 73.1% | 73.8% |
| ML: embeddings | 93.8% | 94.4% |
| ML: TF-IDF + embeddings | 93.1% | 93.5% |

## 2. Knowledge-base retrieval

| Method | Recall@1 | Recall@3 | MRR |
| --- | ---: | ---: | ---: |
| BM25 (baseline) | 51.1% | 69.6% | 0.592 |
| Dense embeddings | 69.6% | 85.9% | 0.774 |
| Hybrid RRF (BM25 + embeddings) | 63.0% | 83.7% | 0.725 |
| Embeddings + intent boost | 73.9% | 88.0% | 0.806 |

## 3. End-to-end: when to hand off to a human

Full pipeline with the offline provider (no LLM), one fresh conversation per message.

| Pipeline | Escalation precision | Escalation recall | Escalation F1 | Self-service rate | Right article | Median latency |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Baseline: regex rules + BM25 | 47.3% | 89.7% | 61.9% | 57.1% | 44.6% | 0 ms |
| Current: ML intents + embedding retrieval | 76.5% | 100.0% | 86.7% | 86.8% | 75.9% | 11 ms |

- **Escalation precision**: of the chats handed to a human, how many really needed one.
- **Escalation recall**: of the chats that needed a human, how many were handed over.
- **Self-service rate**: answerable questions the bot resolved without a human.
- **Right article**: of those, answered from the expected help-center section.

## Remaining intent errors (production model)

| Message | Expected | Predicted |
| --- | --- | --- |
| If I order now, does it go out today? | shipping | order_status |
| I took the tent camping once, can I still bring it back? | returns_refunds | product_info |
| The jacket went on sale two days after I bought it | billing | product_info |
| How do I see what's left on my gift card | billing | order_status |
| How many points do I need for $5 off | account | billing |
| Is there a membership with free shipping | account | shipping |
| Is there an email I can write to | store_info | account |
| Tell me about your company | store_info | complaint |
