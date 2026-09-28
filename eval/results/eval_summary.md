# Fraud Investigation AI Agent — Evaluation Scorecard
**Timestamp:** 2026-09-28T16:14:45.756556Z  
**Total Cases Evaluated:** 20  
**Overall Status:** **PASSED** (Composite Score: **99.8 / 100.0**)  

## 1. Executive Summary & Composite Score

| Evaluation Dimension | Weight | Score (0-100) | Weighted Contribution |
| :--- | :--- | :--- | :--- |
| **Verdict Classification (F1)** | 25% | 100.0% | 25.0 / 25.0 |
| **Pattern Identification** | 15% | 100.0% | 15.0 / 15.0 |
| **Next Best Action Alignment** | 20% | 100.0% | 20.0 / 20.0 |
| **SAR Compliance & Narrative** | 15% | 100.0% | 15.0 / 15.0 |
| **Exposure Dollar Accuracy** | 10% | 98.01% | 9.8 / 10.0 |
| **Policy & Route Adherence** | 10% | 100.0% | 10.0 / 10.0 |
| **Determinism & Stability** | 5% | 100.0% | 5.0 / 5.0 |
| **TOTAL COMPOSITE SCORE** | **100%** | **99.8%** | **99.8 / 100.0** (Target: ≥85.0%) |

## 2. Classification Metrics (Confusion Matrix)

- **Accuracy:** `100.0%` (20/20)
- **Precision:** `1.000`
- **Recall (Sensitivity):** `1.000`
- **F1 Score:** `1.000`
- **Specificity:** `1.000`

| | Predicted Fraud | Predicted Legitimate |
| :--- | :---: | :---: |
| **Actual Fraud** | **TP:** 16 | **FN:** 0 |
| **Actual Legitimate** | **FP:** 0 | **TN:** 4 |

## 3. Operational & Policy Metrics

- **Pattern Match Rate:** `100.0%`
- **Mean Action Jaccard Similarity:** `1.000`
- **Critical Action Recall:** `100.0%`
- **SAR Filing Accuracy:** `100.0%`
- **SAR Policy Compliance:** `100.0%`
- **Exposure MAE:** `$1.50`
- **Exposure Mean Relative Error:** `1.0%`
- **Policy & Routing Compliance:** `100.0%`

## 4. Per-Case Evaluation Results

| Case ID | Predicted Verdict | Expected | Pattern Match | Action Jaccard | SAR Correct | Policy Valid | Overall Score |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `HHG-001` | `fraud` | `fraud` | ✓ | `1.00` | ✓ | ✓ | **99.9%** |
| `HHG-002` | `fraud` | `fraud` | ✓ | `1.00` | ✓ | ✓ | **100.0%** |
| `HHG-003` | `legitimate` | `legitimate` | ✓ | `1.00` | ✓ | ✓ | **100.0%** |
| `HHG-004` | `fraud` | `fraud` | ✓ | `1.00` | ✓ | ✓ | **99.9%** |
| `HHG-005` | `fraud` | `fraud` | ✓ | `1.00` | ✓ | ✓ | **99.8%** |
| `HHG-006` | `fraud` | `fraud` | ✓ | `1.00` | ✓ | ✓ | **100.0%** |
| `HHG-007` | `fraud` | `fraud` | ✓ | `1.00` | ✓ | ✓ | **100.0%** |
| `HHG-008` | `fraud` | `fraud` | ✓ | `1.00` | ✓ | ✓ | **99.7%** |
| `HHG-009` | `fraud` | `fraud` | ✓ | `1.00` | ✓ | ✓ | **100.0%** |
| `HHG-010` | `fraud` | `fraud` | ✓ | `1.00` | ✓ | ✓ | **99.8%** |
| `HHG-011` | `fraud` | `fraud` | ✓ | `1.00` | ✓ | ✓ | **100.0%** |
| `HHG-012` | `fraud` | `fraud` | ✓ | `1.00` | ✓ | ✓ | **99.7%** |
| `HHG-013` | `fraud` | `fraud` | ✓ | `1.00` | ✓ | ✓ | **99.8%** |
| `HHG-014` | `fraud` | `fraud` | ✓ | `1.00` | ✓ | ✓ | **100.0%** |
| `HHG-015` | `fraud` | `fraud` | ✓ | `1.00` | ✓ | ✓ | **100.0%** |
| `HHG-016` | `fraud` | `fraud` | ✓ | `1.00` | ✓ | ✓ | **99.9%** |
| `HHG-017` | `legitimate` | `legitimate` | ✓ | `1.00` | ✓ | ✓ | **100.0%** |
| `HHG-018` | `legitimate` | `legitimate` | ✓ | `1.00` | ✓ | ✓ | **100.0%** |
| `HHG-019` | `fraud` | `fraud` | ✓ | `1.00` | ✓ | ✓ | **100.0%** |
| `HHG-020` | `legitimate` | `legitimate` | ✓ | `1.00` | ✓ | ✓ | **100.0%** |