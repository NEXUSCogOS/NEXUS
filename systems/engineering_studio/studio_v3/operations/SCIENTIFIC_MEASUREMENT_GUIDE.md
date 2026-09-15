# Scientific Measurement Framework for NEXUS

Production-grade measurement and reproducibility system with MLflow integration, causal inference, and comprehensive statistical framework.

## Overview

`scientific_measurement.py` provides:

- **MLflow Standard Tracking**: Dataset hashing, hyperparameter logging, latency percentiles (P50, P95, P99), cost tracking
- **Gold-Tier Reproducibility**: Code snapshots + data hashing + environment capture + verification
- **Complete Parameter Logging**: Every generation step captured with deterministic hashing
- **Causal Inference**: Double Machine Learning for estimating true causal treatment effects
- **Statistical Rigor**: 95% confidence intervals, pre-registration (no p-hacking), hypothesis testing
- **Audit Trail**: Comprehensive logging for every video generation with rollback capability
- **Production Database**: SQLite schema with 8 tables, thread-safe access, ACID guarantees

## Core Components

### 1. ScientificMeasurement (Main Engine)

```python
from systems.engineering_studio.studio_v3.operations.scientific_measurement import (
    ScientificMeasurement, ReproducibilityTier, AuditLevel
)

# Create experiment with GOLD reproducibility
exp = ScientificMeasurement(
    experiment_name="video_generation_v2",
    hypothesis="Double Machine Learning reveals effect of prompt engineering",
    primary_metric="video_quality_score",
    reproducibility_tier=ReproducibilityTier.GOLD,
    audit_level=AuditLevel.STANDARD,
    mlflow_uri="http://localhost:5000"
)
```

**Reproducibility Tiers:**
- `BRONZE`: Code snapshot only
- `SILVER`: Code + data hash
- `GOLD`: Code + data + environment + verification ✓ Recommended

**Audit Levels:**
- `MINIMAL`: Only errors
- `STANDARD`: Key actions (recommended for production)
- `COMPREHENSIVE`: All parameter changes
- `PARANOID`: Debug-level logging

### 2. Hyperparameter Management

```python
# Record hyperparameters with deterministic hashing
hp = exp.record_hyperparameters({
    'temperature': 0.7,
    'top_p': 0.9,
    'max_tokens': 2048
}, seed=42)

print(f"Hyperparam hash: {hp.hash_value}")  # Reproducible across runs
```

**Features:**
- Deterministic SHA256 hashing of parameter sets
- Seed management for reproducibility
- Automatic MLflow logging

### 3. Dataset Versioning

```python
# Record dataset with full provenance
dataset = exp.record_dataset(
    name="youtube_shorts_training",
    version="2.1.0",
    data_path="/path/to/dataset.csv",
    schema={
        'video_id': 'string',
        'transcript': 'text',
        'duration': 'float',
        'engagement_score': 'float'
    },
    source_uri="gs://nexus-datasets/shorts-v2.1.0"
)

print(f"Dataset hash: {dataset.hash_value}")  # Content-addressable
```

### 4. Per-Step Measurement

```python
# Record each generation step with latency and cost
measurement = exp.record_step_measurement(
    step_id="generation_001",
    duration_seconds=2.5,
    parameters={'step': 1, 'model': 'gpt-4'},
    output_hash="sha256_of_generated_content",
    latency_samples=[0.10, 0.12, 0.11, 0.15, 0.13],  # Raw measurements
    cost_usd=0.015,
    tokens_used=850,
    success=True,
    metadata={'model_temperature': 0.7}
)

# Automatic percentile computation
print(f"Latency P50: {measurement.latency_metrics.p50:.3f}s")
print(f"Latency P95: {measurement.latency_metrics.p95:.3f}s")
print(f"Latency P99: {measurement.latency_metrics.p99:.3f}s")
```

### 5. Pre-Registration (Prevents P-Hacking)

```python
# Define hypothesis BEFORE analyzing data (lock parameters)
pre_reg = exp.create_pre_registration(
    hypothesis="Temperature=0.7 improves coherence by 15%",
    primary_metric="coherence_score",
    sample_size=100,
    alpha=0.05,  # Type I error rate
    power=0.80,  # Type II error rate
    effect_size_hypothesis=0.15
)

# Lock before execution - prevents peeking at results
hp = exp.record_hyperparameters({'temperature': 0.7}, seed=42)
exp.lock_pre_registration(pre_reg.registration_id, hp.hash_value)

# Now record measurements - locked hypothesis cannot change
for i in range(100):
    # ... record measurements ...
    pass
```

### 6. Confidence Intervals (95%)

```python
# Compute CIs using multiple methods (normal, bootstrap, bayesian)
import numpy as np

sample_metrics = [0.7 + np.random.normal(0, 0.1) for _ in range(100)]

cis = exp.compute_confidence_intervals(
    metric_name='quality_score',
    samples=sample_metrics,
    confidence_level=0.95
)

# Results computed with three independent methods
for method, ci in cis.items():
    print(f"{method}:")
    print(f"  Estimate: {ci.estimate:.4f}")
    print(f"  95% CI: [{ci.lower:.4f}, {ci.upper:.4f}]")

# All results persisted to database and MLflow
```

### 7. Causal Inference (Double Machine Learning)

```python
import numpy as np

# Estimate causal treatment effect (e.g., effect of prompt engineering)
n_samples = 500
features = np.random.normal(0, 1, (n_samples, 10))
treatment = np.random.binomial(1, 0.5, n_samples)
outcome = 0.3 * treatment + 0.5 * features[:, 0] + np.random.normal(0, 0.1, n_samples)

result = exp.estimate_causal_effect(
    features=features,
    treatment=treatment,
    outcome=outcome,
    confidence_level=0.95
)

print(f"Treatment effect: {result['treatment_effect']:.4f}")
print(f"95% CI: [{result['ci_lower']:.4f}, {result['ci_upper']:.4f}]")
print(f"Std. error: {result['std_error']:.4f}")
```

Uses partialling out + residualization:
1. Fits nuisance models (propensity score, outcome model)
2. Residualizes treatment and outcome
3. Estimates treatment coefficient via OLS
4. Computes standard errors via bootstrap

### 8. Video Generation Audit Trail

```python
# Record complete generation audit trail for reproducibility
exp.record_video_generation(
    video_id="shorts_20240816_001",
    title="AI Shortcut: 10x Your Productivity",
    generation_duration_seconds=45.2,
    parameters_used={
        'temperature': 0.7,
        'top_p': 0.9,
        'max_tokens': 2048,
        'model': 'gpt-4-turbo'
    },
    dataset_hash="abc123def456...",
    execution_log={
        'start_time': '2024-08-16T10:00:00Z',
        'end_time': '2024-08-16T10:00:45Z',
        'steps': [
            {'step': 'script_generation', 'duration': 5.2},
            {'step': 'voiceover', 'duration': 15.3},
            {'step': 'video_synthesis', 'duration': 24.7}
        ]
    },
    verification_checksum="sha256_of_final_video",
    notes="Tested on new prompt engineering framework"
)
```

## Database Schema

### 8 Production Tables:

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `experiments` | Experiment metadata | id, hypothesis, primary_metric, status |
| `measurements` | Step-level results | experiment_id, step_id, latency_p50/95/99, cost_usd |
| `datasets` | Data versioning | hash_value, version, record_count, schema |
| `hyperparameters` | Parameter specs | params, seed, hash_value |
| `pre_registrations` | Locked hypotheses | hypothesis, sample_size, status |
| `statistical_results` | Hypothesis tests | estimate, ci_lower/upper, p_value |
| `audit_log` | Action trail | action, actor, timestamp, details |
| `video_audit_trail` | Video generation logs | video_id, parameters_hash, dataset_hash |

### Example Queries:

```python
# Get all measurements for experiment
measurements = exp.db.query_measurements(exp.experiment_id)

# Get all experiments (active or completed)
all_exps = exp.db.query_experiments(status='active')

# Direct SQL access
with exp.db._get_connection() as conn:
    cursor = conn.execute("""
        SELECT step_id, latency_p95, cost_usd FROM measurements
        WHERE experiment_id = ? AND success = 1
        ORDER BY timestamp
    """, (exp.experiment_id,))
    for row in cursor:
        print(row)
```

## Environment & Code Snapshots

Automatic capture for reproducibility:

```python
# Environment automatically captured
print(f"Python: {exp.environment['python_version']}")
print(f"Platform: {exp.environment['platform']}")
print(f"Environment hash: {exp.environment_hash}")

# Code snapshot (optional)
from systems.engineering_studio.studio_v3.operations.scientific_measurement import CodeSnapshot

code_snapshot = CodeSnapshot.capture_directory(
    path="/path/to/src",
    patterns=['*.py']
)
code_hash = CodeSnapshot.compute_hash(code_snapshot)
```

## Results Export & MLflow Integration

```python
# Export complete results
exp.export_results('/workspace/results/experiment_001.json')
# Contains: summary, measurements, pre-registrations, environment, timestamps

# MLflow artifacts (if connected)
# - All hyperparameters
# - All metrics (latency percentiles, costs)
# - Confidence interval results
# - Experiment summary
# - Full results JSON

# Finalize (close MLflow run)
exp.finalize()
```

## Example: Complete Workflow

```python
from systems.engineering_studio.studio_v3.operations.scientific_measurement import (
    ScientificMeasurement, ReproducibilityTier, AuditLevel
)
import numpy as np

# 1. Create experiment
exp = ScientificMeasurement(
    experiment_name="prompt_engineering_effect",
    hypothesis="Structured prompts improve video quality by 20%",
    primary_metric="quality_score",
    reproducibility_tier=ReproducibilityTier.GOLD,
    audit_level=AuditLevel.STANDARD
)

# 2. Pre-register hypothesis
pre_reg = exp.create_pre_registration(
    hypothesis="Quality score improvement >= 20%",
    primary_metric="quality_score",
    sample_size=50
)

# 3. Record experiment inputs
hp = exp.record_hyperparameters({
    'prompt_template': 'structured',
    'temperature': 0.7
}, seed=42)
exp.lock_pre_registration(pre_reg.registration_id, hp.hash_value)

# 4. Record dataset
dataset = exp.record_dataset(
    name="test_videos",
    version="1.0",
    data_path="/data/test_videos.csv",
    schema={'video_id': 'str', 'topic': 'str'}
)

# 5. Run experiment (50 videos)
quality_scores = []
for i in range(50):
    # Generate video
    latencies = [0.1 + np.random.normal(0, 0.02) for _ in range(5)]
    
    # Record measurement
    exp.record_step_measurement(
        step_id=f"video_{i:03d}",
        duration_seconds=2.0 + np.random.normal(0, 0.3),
        parameters={'video_num': i},
        output_hash=f"output_hash_{i}",
        latency_samples=latencies,
        cost_usd=0.01,
        tokens_used=500,
        success=True
    )
    
    # Track quality
    quality_scores.append(0.8 + np.random.normal(0, 0.1))

# 6. Compute statistics
cis = exp.compute_confidence_intervals(
    'quality_score',
    quality_scores,
    confidence_level=0.95
)

# 7. Generate summary & export
summary = exp.generate_summary()
exp.export_results('/results/prompt_engineering_effect.json')
exp.finalize()

print(f"Experiment {exp.experiment_id} completed successfully")
```

## Installation & Dependencies

Required:
```bash
pip install numpy scipy
```

Optional (for MLflow):
```bash
pip install mlflow
```

Optional (for causal inference):
```bash
pip install scikit-learn
```

## Best Practices

1. **Always pre-register** hypotheses before analyzing data
2. **Use GOLD reproducibility tier** for published results
3. **Capture latency samples** at measurement time (not just final)
4. **Hash all inputs** (data, code, environment) for reproducibility
5. **Export results immediately** after finalization
6. **Use consistent seeds** for deterministic runs: `seed=42`
7. **Log to MLflow** for experiment tracking and comparison
8. **Audit level STANDARD** for production (PARANOID for debugging)

## Thread Safety

All database operations are thread-safe:
```python
# Safe to call from multiple threads
exp.record_step_measurement(...) # Thread-safe
exp.db.record_measurement(...) # Thread-safe
```

## Cost Tracking

```python
# After experiment
total_cost = exp.cost_tracking['total_usd']
total_tokens = exp.cost_tracking['total_tokens']
avg_cost_per_step = total_cost / len(exp.measurements)

print(f"Total cost: ${total_cost:.4f}")
print(f"Tokens used: {total_tokens:,}")
print(f"Cost per step: ${avg_cost_per_step:.4f}")
```

## References

- MLflow: https://mlflow.org
- Double Machine Learning: https://arxiv.org/abs/1608.00060
- Bootstrap CI: https://en.wikipedia.org/wiki/Bootstrapping_(statistics)
- Pre-registration: https://www.cos.io/initiatives/prereg
